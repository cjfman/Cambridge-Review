#!/usr/bin/env python3
"""Sync local files to a remote cPanel server via SFTP."""

import argparse
import fnmatch
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import paramiko
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.absolute()

SKIP_NAMES = {'.DS_Store', '__pycache__', 'Thumbs.db', '.git'}
SKIP_EXTENSIONS = {'.pyc', '.pyo'}


def should_skip(path: Path) -> bool:
    name = path.name
    if name.startswith('.'):
        return True
    if name in SKIP_NAMES:
        return True
    if path.suffix in SKIP_EXTENSIONS:
        return True
    return False


def matches_filter(rel_path: str, pattern: Optional[str]) -> bool:
    if pattern is None:
        return True
    return fnmatch.fnmatch(rel_path, pattern)


def load_config(config_path) -> Dict[str, Any]:
    with open(config_path) as f:
        return yaml.safe_load(f)


def remote_mtime(sftp: paramiko.SFTPClient, remote_path) -> Optional[float]:
    try:
        return sftp.stat(remote_path).st_mtime
    except FileNotFoundError:
        return None
    except IOError:
        return None


def ensure_remote_dir(sftp: paramiko.SFTPClient, remote_dir):
    is_absolute = remote_dir.startswith('/')
    parts = [p for p in remote_dir.split('/') if p]
    for i in range(1, len(parts) + 1):
        segment = '/'.join(parts[:i])
        if is_absolute:
            segment = '/' + segment
        try:
            sftp.stat(segment)
        except (FileNotFoundError, IOError):
            sftp.mkdir(segment)


def collect_files(
    local_root: Path,
    filter_pattern: Optional[str],
) -> List[Tuple[Path, str]]:
    result = []
    for dirpath, dirnames, filenames in os.walk(local_root):
        dirpath_obj = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not should_skip(Path(d))]
        for filename in filenames:
            file_path = dirpath_obj / filename
            if should_skip(file_path):
                continue
            rel_path = str(file_path.relative_to(local_root)).replace(os.sep, '/')
            if not matches_filter(rel_path, filter_pattern):
                continue
            result.append((file_path, rel_path))
    return result


def collect_mapping_files(
    mapping: Dict[str, Any],
    filter_pattern: Optional[str],
) -> Optional[List[Tuple[Path, str]]]:
    local_dir = PROJECT_ROOT / mapping['local']
    if not local_dir.exists():
        print(f"Warning: local path does not exist, skipping: {local_dir}", file=sys.stderr)
        return None
    if local_dir.is_file():
        return [(local_dir, local_dir.name)]
    files = collect_files(local_dir, filter_pattern)
    mapping_filter = mapping.get('filter')
    if mapping_filter:
        files = [(p, r) for p, r in files if matches_filter(r, mapping_filter)]
    return files


def sync_file(
    sftp: paramiko.SFTPClient,
    local_path: Path,
    remote_path,
    dry_run: bool,
    quiet: bool = False,
    force: bool = False,
) -> Optional[str]:
    """Upload local_path to remote_path if local is newer. Returns 'create', 'update', or None if up to date."""
    r_mtime = remote_mtime(sftp, remote_path)

    if not force and r_mtime is not None and r_mtime >= local_path.stat().st_mtime:
        return None

    action = 'create' if r_mtime is None else 'update'

    if not quiet:
        print(f"{'[dry-run] ' if dry_run else ''}{action}: {local_path} -> {remote_path}")

    if not dry_run:
        remote_dir = str(Path(remote_path).parent)
        try:
            ensure_remote_dir(sftp, remote_dir)
            sftp.put(str(local_path), remote_path)
        except (FileNotFoundError, IOError) as e:
            print(f"Error uploading {local_path}: {e}", file=sys.stderr)
            return None

    return action


def sync_mapping(
    sftp: paramiko.SFTPClient,
    mapping: Dict[str, Any],
    filter_pattern: Optional[str],
    dry_run: bool,
    quiet: bool = False,
    force: bool = False,
) -> Tuple[int, int, int]:
    """Sync one mapping entry. Returns (created, updated, up_to_date) counts."""
    remote_dir = mapping['remote'].rstrip('/')
    files = collect_mapping_files(mapping, filter_pattern)
    if files is None:
        return 0, 0, 0

    created = 0
    updated = 0
    up_to_date = 0
    for local_path, rel_path in files:
        remote_path = f"{remote_dir}/{rel_path}"
        action = sync_file(sftp, local_path, remote_path, dry_run, quiet, force)
        if action == 'create':
            created += 1
        elif action == 'update':
            updated += 1
        else:
            up_to_date += 1
    return created, updated, up_to_date


def touch_remote(sftp: paramiko.SFTPClient, remote_path, dry_run: bool, quiet: bool = False) -> bool:
    """Set mtime of remote_path to now. Returns False if the file doesn't exist remotely."""
    if remote_mtime(sftp, remote_path) is None:
        return False
    if not quiet:
        print(f"{'[dry-run] ' if dry_run else ''}touch: {remote_path}")
    if not dry_run:
        now = time.time()
        sftp.utime(remote_path, (now, now))
    return True


def touch_mapping(
    sftp: paramiko.SFTPClient,
    mapping: Dict[str, Any],
    filter_pattern: Optional[str],
    dry_run: bool,
    quiet: bool = False,
) -> Tuple[int, int]:
    """Touch all remotely mapped files. Returns (touched, not_found) counts."""
    remote_dir = mapping['remote'].rstrip('/')
    files = collect_mapping_files(mapping, filter_pattern)
    if files is None:
        return 0, 0

    touched = 0
    not_found = 0
    for local_path, rel_path in files:
        remote_path = f"{remote_dir}/{rel_path}"
        if touch_remote(sftp, remote_path, dry_run, quiet):
            touched += 1
        else:
            not_found += 1
    return touched, not_found


def connect(config: Dict[str, Any]) -> paramiko.SFTPClient:
    host = config['host']
    port = config.get('port', 22)
    username = config['username']
    password = config.get('password')
    key_path = config.get('private_key')

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: Dict[str, Any] = {}
    if password:
        connect_kwargs['password'] = password
    if key_path:
        connect_kwargs['key_filename'] = os.path.expanduser(key_path)

    print(f"Connecting to {username}@{host}:{port}...")
    try:
        ssh.connect(host, port=port, username=username, **connect_kwargs)
    except socket.gaierror:
        print(f"Error: could not resolve host '{host}'", file=sys.stderr)
        sys.exit(1)
    except paramiko.AuthenticationException:
        print(f"Error: authentication failed for {username}@{host}", file=sys.stderr)
        sys.exit(1)
    except (OSError, paramiko.SSHException) as e:
        print(f"Error: could not connect to {host}:{port}: {e}", file=sys.stderr)
        sys.exit(1)
    return ssh.open_sftp()


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync files to a remote cPanel server via SFTP')
    parser.add_argument('--config', default='sync_config.yaml', help='Path to config file (default: sync_config.yaml)')
    parser.add_argument('--filter', dest='filter_pattern', metavar='PATTERN', help='Bash-style wildcard filter on relative file paths, e.g. "*.html"')
    parser.add_argument('--dry-run', action='store_true', help='Print what would be transferred without actually uploading')
    parser.add_argument('--quiet', action='store_true', help='Suppress per-file transfer log')
    parser.add_argument('--force', action='store_true', help='Upload all files regardless of modification time')
    parser.add_argument('--touch-all', action='store_true', help='Touch all remote files to prevent re-syncing on next run')
    return parser


def run_sync(
    sftp: paramiko.SFTPClient,
    mappings: List[Dict[str, Any]],
    filter_pattern: Optional[str],
    dry_run: bool,
    quiet: bool = False,
    force: bool = False,
):
    created = 0
    updated = 0
    up_to_date = 0
    for mapping in mappings:
        n_created, n_updated, n_up_to_date = sync_mapping(sftp, mapping, filter_pattern, dry_run, quiet, force)
        created += n_created
        updated += n_updated
        up_to_date += n_up_to_date
    dry_txt = '[dry-run] ' if dry_run else ''
    would_txt = 'would ' if dry_run else ''
    print(f"\n{dry_txt}{would_txt}create {created}, {would_txt}update {updated}, {up_to_date} already up to date.")


def run_touch_all(
    sftp: paramiko.SFTPClient,
    mappings: List[Dict[str, Any]],
    filter_pattern: Optional[str],
    dry_run: bool,
    quiet: bool = False,
):
    touched = 0
    not_found = 0
    for mapping in mappings:
        n_touched, n_not_found = touch_mapping(sftp, mapping, filter_pattern, dry_run, quiet)
        touched += n_touched
        not_found += n_not_found
    dry_txt = '[dry-run] ' if dry_run else ''
    would_txt = 'would ' if dry_run else ''
    print(f"\n{dry_txt}{would_txt}touch {touched}, {not_found} not found remotely.")


def main():
    args = make_parser().parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = PROJECT_ROOT / config_path
    if not config_path.exists():
        print(f"Error: config file not found: {config_path} (use --config to specify a path)", file=sys.stderr)
        sys.exit(1)

    config = load_config(config_path)
    mappings = config.get('mappings', [])
    if not mappings:
        print("Error: no mappings defined in config.", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print("[dry-run] No files will be transferred.\n")

    sftp = connect(config)
    try:
        if args.touch_all:
            run_touch_all(sftp, mappings, args.filter_pattern, args.dry_run, args.quiet)
        else:
            run_sync(sftp, mappings, args.filter_pattern, args.dry_run, args.quiet, args.force)
    finally:
        sftp.close()


if __name__ == '__main__':
    main()
