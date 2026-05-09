#! /usr/bin/python3

import argparse
import re
import sys
from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.elections import Ballot, loadFinalBallots


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simulate a Cambridge STV election from .chp + .PRM ballot files",
    )
    parser.add_argument("chp_file", help="ChoicePlus Pro .chp configuration file")
    parser.add_argument("--seats", type=int, help="Override seat count from .chp")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-candidate transfer counts each round")
    return parser


def parse_chp(path: Path) -> Tuple[int, Dict[str, str], List[str]]:
    """Parse .chp file. Returns (seats, code_to_name, include_filenames_in_draw_order)."""
    seats = 0
    code_to_name: Dict[str, str] = {}
    include_files: List[str] = []

    with open(path, encoding='utf8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = re.match(r'^\.ELECT\s+(\d+)', line)
            if m:
                seats = int(m.group(1))
                continue
            m = re.match(r'^\.CANDIDATE\s+(\w+),\s+"(.+)"$', line)
            if m:
                code_to_name[m.group(1)] = m.group(2)
                continue
            m = re.match(r'^\.INCLUDE\s+(\S+)', line)
            if m:
                include_files.append(m.group(1))

    return seats, code_to_name, include_files


def load_ballots(chp_dir: Path, include_files: List[str], code_to_name: Dict[str, str]) -> List[Ballot]:
    """Load ballots in draw order, filter all-tied-rank invalids, remap codes to names."""
    raw: List[Ballot] = []
    for filename in include_files:
        # loadFinalBallots prints "Invalid ballot" lines to stdout; suppress them
        saved, sys.stdout = sys.stdout, StringIO()
        try:
            raw.extend(loadFinalBallots(chp_dir / filename))
        finally:
            sys.stdout = saved

    valid: List[Ballot] = []
    invalid = 0
    for b in raw:
        if not b.candidates:
            invalid += 1  # all-tied-rank ballot: no valid first preference
            continue
        remapped = [code_to_name.get(c, c) for c in b.candidates]
        valid.append(Ballot(b.key, b.holder, remapped))

    print(f"Ballots: {len(valid):,} valid, {invalid:,} all-tied invalid", file=sys.stderr)
    return valid


def droop_quota(total: int, seats: int) -> int:
    return total // (seats + 1) + 1


def next_pref(ballot: Ballot, ineligible: Set[str]) -> Optional[str]:
    for c in ballot.candidates:
        if c not in ineligible:
            return c
    return None


def assign_ballots(ballots: List[Ballot], ineligible: Set[str]) -> Dict[str, List[Ballot]]:
    """Sort ballots into piles by first valid preference."""
    piles: Dict[str, List[Ballot]] = defaultdict(list)
    for b in ballots:
        dest = next_pref(b, ineligible)
        if dest:
            piles[dest].append(b)
    return piles


def do_surplus(
    piles: Dict[str, List[Ballot]],
    candidate: str,
    quota: int,
    ineligible: Set[str],
) -> Dict[str, int]:
    """Cincinnati Method: transfer surplus from an elected candidate.

    Extracts every nth ballot (n = floor(total/surplus)), taking exactly
    surplus ballots at positions n, 2n, ..., surplus*n (1-indexed).
    Exhausted ballots remain with the elected candidate.
    Returns transfer counts by destination.
    """
    pile = piles[candidate]
    total = len(pile)
    surplus = total - quota
    if surplus <= 0:
        return {}

    n = total // surplus
    extract_indices = set(range(n - 1, surplus * n, n))  # 0-indexed

    kept: List[Ballot] = []
    transfers: Dict[str, int] = defaultdict(int)
    for i, ballot in enumerate(pile):
        if i in extract_indices:
            dest = next_pref(ballot, ineligible)
            if dest:
                piles[dest].append(ballot)
                transfers[dest] += 1
            else:
                kept.append(ballot)  # exhausted: stays with elected candidate
        else:
            kept.append(ballot)

    piles[candidate] = kept
    return dict(transfers)


def do_eliminate(
    piles: Dict[str, List[Ballot]],
    candidate: str,
    ineligible: Set[str],
) -> Dict[str, int]:
    """Eliminate a candidate and transfer all their ballots.
    Returns transfer counts by destination.
    """
    transfers: Dict[str, int] = defaultdict(int)
    for ballot in piles.pop(candidate, []):
        dest = next_pref(ballot, ineligible)
        if dest:
            piles[dest].append(ballot)
            transfers[dest] += 1
    return dict(transfers)


def pile_counts(piles: Dict[str, List[Ballot]], candidates: List[str]) -> Dict[str, int]:
    return {c: len(piles.get(c, [])) for c in candidates}


def print_round(
    count: int,
    counts: Dict[str, int],
    elected: List[str],
    eliminated: Set[str],
    quota: int,
    verbose: bool,
    transfers: Optional[Dict[str, int]] = None,
) -> None:
    print(f"\n--- Count {count} ---")
    if transfers and verbose:
        for dest, n in sorted(transfers.items(), key=lambda x: -x[1]):
            print(f"  {'':>8}  +{n:<6,}  {dest}")
    active = {c for c, n in counts.items() if n > 0 or c in elected}
    for c in sorted(active, key=lambda x: -counts[x]):
        n = counts[c]
        if c in elected:
            status = " [elected]"
        elif c in eliminated:
            status = " [eliminated]" if n > 0 else ""
        else:
            status = ""
        if n == 0 and c in eliminated:
            continue
        print(f"  {n:8,}  {c}{status}")
    print(f"  {'quota:':>8}  {quota:,}")


def check_new_elections(
    counts: Dict[str, int],
    piles: Dict[str, List[Ballot]],
    quota: int,
    elected: List[str],
    ineligible: Set[str],
    surplus_queue: List[str],
) -> None:
    """Elect any candidate at or above quota and queue surplus transfers."""
    active_unelected = [c for c in counts if c not in ineligible and counts[c] >= quota]
    for c in sorted(active_unelected, key=lambda x: -counts[x]):
        elected.append(c)
        ineligible.add(c)
        if len(piles.get(c, [])) > quota:
            surplus_queue.append(c)
        print(f"  >> Elected: {c} ({counts[c]:,} votes)")


def do_under50_round(
    piles: Dict[str, List[Ballot]],
    counts: Dict[str, int],
    ineligible: Set[str],
    eliminated: Set[str],
) -> bool:
    """Eliminate all candidates with fewer than 50 votes.
    Returns True if any candidates were eliminated.
    """
    active = [c for c in counts if c not in ineligible]
    under50 = [c for c in active if counts[c] < 50]
    if not under50:
        return False
    print(f"  Under-50 elimination: {', '.join(sorted(under50))}")
    for c in under50:
        eliminated.add(c)
        ineligible.add(c)
        do_eliminate(piles, c, ineligible)
    return True


def do_lowest_elimination(
    piles: Dict[str, List[Ballot]],
    counts: Dict[str, int],
    ineligible: Set[str],
    eliminated: Set[str],
) -> Dict[str, int]:
    """Eliminate the lowest-polling continuing candidate.
    Tie-breaking: not implemented beyond min(); warns if tied.
    Returns transfer counts.
    """
    active = [c for c in counts if c not in ineligible]
    lowest_count = min(counts[c] for c in active)
    tied = [c for c in active if counts[c] == lowest_count]
    if len(tied) > 1:
        print(f"  Warning: tie for last place ({lowest_count:,} votes): {', '.join(sorted(tied))}")
        print(f"  Tie-breaking not implemented; eliminating first alphabetically")
    lowest = sorted(tied)[0]
    print(f"  Eliminating: {lowest} ({lowest_count:,} votes)")
    eliminated.add(lowest)
    ineligible.add(lowest)
    return do_eliminate(piles, lowest, ineligible)


def run_election(ballots: List[Ballot], candidates: List[str], seats: int, *, verbose: bool = False) -> List[str]:
    total = len(ballots)
    quota = droop_quota(total, seats)
    print(f"\n{total:,} valid ballots | {seats} seats | quota = {quota:,}\n")

    elected: List[str] = []
    eliminated: Set[str] = set()
    ineligible: Set[str] = set()
    surplus_queue: List[str] = []
    under50_done = False

    piles = assign_ballots(ballots, ineligible)
    count = 0

    def snapshot_and_check(transfers: Optional[Dict[str, int]] = None) -> None:
        nonlocal count
        count += 1
        counts = pile_counts(piles, candidates)
        print_round(count, counts, elected, eliminated, quota, verbose, transfers)
        check_new_elections(counts, piles, quota, elected, ineligible, surplus_queue)

    snapshot_and_check()

    while len(elected) < seats:
        counts = pile_counts(piles, candidates)

        if surplus_queue:
            src = surplus_queue.pop(0)
            surplus = len(piles.get(src, [])) - quota
            print(f"\n  Surplus transfer: {src} ({surplus:,} votes)")
            transfers = do_surplus(piles, src, quota, ineligible)
            snapshot_and_check(transfers)
            continue

        if not under50_done:
            under50_done = True
            if do_under50_round(piles, counts, ineligible, eliminated):
                snapshot_and_check()
                continue

        transfers = do_lowest_elimination(piles, counts, ineligible, eliminated)
        snapshot_and_check(transfers)

    return elected


def main(args: argparse.Namespace) -> int:
    chp_path = Path(args.chp_file)
    chp_seats, code_to_name, include_files = parse_chp(chp_path)

    seats = args.seats or chp_seats
    if not seats:
        print("Error: seat count not in .chp — use --seats N", file=sys.stderr)
        return 1
    if not include_files:
        print("Error: no .INCLUDE directives found in .chp", file=sys.stderr)
        return 1

    ballots = load_ballots(chp_path.parent, include_files, code_to_name)
    candidates = list(code_to_name.values())

    elected = run_election(ballots, candidates, seats, verbose=args.verbose)

    print(f"\n{'=' * 50}")
    print("Elected (in order):")
    for i, c in enumerate(elected, 1):
        print(f"  {i:2d}. {c}")

    return 0


if __name__ == '__main__':
    sys.exit(main(make_parser().parse_args()))
