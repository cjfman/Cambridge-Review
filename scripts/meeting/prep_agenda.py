#!/usr/bin/env python3

import argparse
import csv
import datetime as dt
import os
import subprocess
import sys
from typing import List, Optional

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_CACHE_DIR       = "meeting_data/cache"
DEFAULT_COUNCILLOR_INFO = "configs/councilors.yml"
DEFAULT_PROCESSED_DIR   = "meeting_data/processed/current"
DEFAULT_SUMMARIES_DIR   = "summaries"
DEFAULT_EXAMPLES_CONFIG = "configs/summary_examples.yaml"


def make_parser():
    year = dt.date.today().year
    default_meetings = f"meeting_data/meeting_sessions/meetings_session_{year}.csv"
    parser = argparse.ArgumentParser(
        description='Prepare the Cambridge City Council agenda: fetch, process, summarize, and sync'
    )
    parser.add_argument('--meetings-file', default=default_meetings,
        help=f'Meetings CSV used for all steps (default: {default_meetings})')
    parser.add_argument('--cache-dir', default=DEFAULT_CACHE_DIR)
    parser.add_argument('--councillor-info', default=DEFAULT_COUNCILLOR_INFO)
    parser.add_argument('--processed-dir', default=DEFAULT_PROCESSED_DIR)
    parser.add_argument('--summaries-dir', default=DEFAULT_SUMMARIES_DIR)
    parser.add_argument('--examples-config', default=DEFAULT_EXAMPLES_CONFIG,
        help='YAML style examples config for Claude summarization')
    parser.add_argument('--force-fetch', action='store_true',
        help='Force re-fetch of meeting agenda from the city website')
    parser.add_argument('--summarize', action='store_true',
        help='Do claude summarization when generating thes summary draft')
    parser.add_argument('--skip-fetch', action='store_true',
        help='Skip updating the meetings list from PrimeGov')
    parser.add_argument('--skip-google', action='store_true',
        help='Skip syncing to Google Sheets')
    parser.add_argument('-v', '--verbose', action='store_true',
        help='Print each command before running it')
    return parser


def script(name) -> str:
    return os.path.join(SCRIPTS_DIR, name)


def run(cmd: List[str], *, step: str, verbose: bool = False) -> int:
    print(f"\n=== {step} ===")
    if verbose:
        print(' '.join(cmd))
    return subprocess.run(cmd).returncode


def read_meeting_date(processed_dir) -> Optional[str]:
    for fname in ('cma.csv', 'policy_orders.csv', 'applications_and_petitions.csv'):
        path = os.path.join(processed_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf8') as f:
            for row in csv.DictReader(f):
                date = row.get('Meeting Date', '').strip()
                if date:
                    return date
    return None


def step_fetch_meetings(args: argparse.Namespace) -> int:
    return run(
        [sys.executable, script('find_meetings.py'), 'primegov', args.meetings_file],
        step='Fetching meeting list from PrimeGov',
        verbose=args.verbose,
    )


def step_process_agenda(args: argparse.Namespace) -> int:
    cmd = [
        sys.executable, script('process_meetings.py'),
        '--cache-dir', args.cache_dir,
        '--councillor-info', args.councillor_info,
        '--next-meeting',
    ]
    if args.force_fetch:
        cmd.append('--force-fetch')
    cmd += [args.meetings_file, args.processed_dir]
    return run(cmd, step='Processing next meeting agenda', verbose=args.verbose)


def step_generate_summary(args: argparse.Namespace, date) -> int:
    output = os.path.join(args.summaries_dir, f'{date}-draft.md')
    cmd = [
        sys.executable, script('generate_summary.py'),
        args.processed_dir,
        '--date', date,
        '--meetings', args.meetings_file,
        '--output', output,
    ]
    if args.summarize:
        cmd.append('--summarize')
        if os.path.isfile(args.examples_config):
            cmd += ['--examples-config', args.examples_config]
    return run(cmd, step=f'Generating summary draft → {output}', verbose=args.verbose)


def step_sync_google(args: argparse.Namespace) -> int:
    return run(
        [
            sys.executable, script('sync_sheets.py'),
            'add',
            '--councillor-info', args.councillor_info,
            '--processed-dir', args.processed_dir,
        ],
        step='Syncing to Google Sheets',
        verbose=args.verbose,
    )


def main() -> int:
    args = make_parser().parse_args()

    if not args.skip_fetch:
        if step_fetch_meetings(args) != 0:
            print('\nError: Failed to fetch meeting list from PrimeGov.', file=sys.stderr)
            return 1

    if step_process_agenda(args) != 0:
        print('\nError: Failed to process meeting agenda. The agenda may not be published yet.', file=sys.stderr)
        return 1

    date = read_meeting_date(args.processed_dir)
    if not date:
        print('\nError: No agenda items found in processed output. The agenda may not be published yet.', file=sys.stderr)
        return 1

    if step_generate_summary(args, date) != 0:
        print('\nError: Failed to generate summary draft.', file=sys.stderr)
        return 1

    if not args.skip_google:
        if step_sync_google(args) != 0:
            print('\nError: Google Sheets sync failed.', file=sys.stderr)
            print(
                'To check and refresh your Google API token, run:\n'
                '  scripts/meeting/sync_sheets.py check-credentials --delete-on-fail\n'
                '\nThen retry the sync with:\n'
                f'  scripts/meeting/sync_sheets.py add'
                f' --councillor-info {args.councillor_info}'
                f' --processed-dir {args.processed_dir}',
                file=sys.stderr,
            )
            return 1

    print('\nDone.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
