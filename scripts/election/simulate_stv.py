#! /usr/bin/python3

import argparse
import random
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
    parser.add_argument("--no-batching", action="store_true",
                        help="One operation per count (default batches surplus transfers "
                             "from newly-elected candidates into the triggering count, "
                             "matching ChoicePlus Pro's count structure)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-candidate transfer counts each round")
    parser.add_argument("--randomize-order", action="store_true",
                        help="Shuffle ballot order before counting (affects Cincinnati surplus sampling)")
    parser.add_argument("--seed", type=int,
                        help="Random seed for --randomize-order (for reproducibility)")
    parser.add_argument("--compare-piles",
                        help="Path to official Final Piles Report.txt; cross-tabulate final ballot assignments")
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
    elected_votes: Dict[str, int],
    eliminated: Set[str],
    quota: int,
    verbose: bool,
    transfers: Optional[Dict[str, int]] = None,
) -> None:
    print(f"\n--- Count {count} ---")
    if transfers and verbose:
        for dest, n in sorted(transfers.items(), key=lambda x: -x[1]):
            print(f"  {'':>8}  +{n:<6,}  {dest}")
    elected_set = set(elected)
    active = {c for c, n in counts.items() if n > 0 or c in elected}

    def sort_key(x):
        if x in elected_set:
            return (0, elected.index(x))   # elected first, in election order
        return (1, -counts[x])             # then continuing, by vote count

    for c in sorted(active, key=sort_key):
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


def detect_elections(
    counts: Dict[str, int],
    piles: Dict[str, List[Ballot]],
    quota: int,
    elected: List[str],
    elected_votes: Dict[str, int],
    ineligible: Set[str],
    surplus_queue: List[str],
    seats: int,
) -> None:
    """Elect any candidate at or above quota (silent — caller prints announcements)."""
    active_unelected = [c for c in counts if c not in ineligible and counts[c] >= quota]
    for c in sorted(active_unelected, key=lambda x: -counts[x]):
        if len(elected) >= seats:
            break
        elected.append(c)
        elected_votes[c] = counts[c]
        ineligible.add(c)
        if len(piles.get(c, [])) > quota:
            surplus_queue.append(c)


def announce_elections(elected: List[str], elected_votes: Dict[str, int], announced: List[int]) -> None:
    """Print election announcements for newly elected candidates since last call."""
    for i in range(announced[0], len(elected)):
        c = elected[i]
        print(f"  >> Elected: {c} ({elected_votes[c]:,} votes)")
    announced[0] = len(elected)


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
    Tie-breaking: warns if tied; eliminates first alphabetically as fallback.
    Returns transfer counts.
    """
    active = [c for c in counts if c not in ineligible]
    lowest_count = min(counts[c] for c in active)
    tied = [c for c in active if counts[c] == lowest_count]
    if len(tied) > 1:
        print(f"  Warning: tie for last ({lowest_count:,} votes): {', '.join(sorted(tied))}")
        print(f"  Tie-breaking not implemented; eliminating first alphabetically")
    lowest = sorted(tied)[0]
    print(f"  Eliminating: {lowest} ({lowest_count:,} votes)")
    eliminated.add(lowest)
    ineligible.add(lowest)
    return do_eliminate(piles, lowest, ineligible)


def drain_surplus_queue(
    piles: Dict[str, List[Ballot]],
    surplus_queue: List[str],
    quota: int,
    candidates: List[str],
    elected: List[str],
    elected_votes: Dict[str, int],
    ineligible: Set[str],
    eliminated: Set[str],
    seats: int,
    verbose: bool,
) -> Dict[str, int]:
    """Transfer all pending surpluses in sequence (batch mode).
    Detects new elections after each transfer and queues their surpluses too.
    Returns accumulated transfer counts.
    """
    merged: Dict[str, int] = {}
    while surplus_queue and len(elected) < seats:
        src = surplus_queue.pop(0)
        surplus = len(piles.get(src, [])) - quota
        if surplus <= 0:
            continue
        print(f"    + Surplus: {src} ({surplus:,} votes)")
        transfers = do_surplus(piles, src, quota, ineligible)
        for k, v in transfers.items():
            merged[k] = merged.get(k, 0) + v
        detect_elections(
            pile_counts(piles, candidates), piles, quota,
            elected, elected_votes, ineligible, surplus_queue, seats,
        )
    return merged


def run_election(
    ballots: List[Ballot],
    candidates: List[str],
    seats: int,
    *,
    verbose: bool = False,
    batch: bool = True,
) -> List[str]:
    total = len(ballots)
    quota = droop_quota(total, seats)
    print(f"\n{total:,} valid ballots | {seats} seats | quota = {quota:,}\n")

    elected: List[str] = []
    elected_votes: Dict[str, int] = {}
    eliminated: Set[str] = set()
    ineligible: Set[str] = set()
    surplus_queue: List[str] = []
    announced = [0]  # mutable int for announce_elections
    under50_done = False
    count = 0

    piles = assign_ballots(ballots, ineligible)

    def show_count(transfers: Optional[Dict[str, int]] = None) -> None:
        nonlocal count
        count += 1
        counts = pile_counts(piles, candidates)
        print_round(count, counts, elected, elected_votes, eliminated, quota, verbose, transfers)
        announce_elections(elected, elected_votes, announced)

    def elect_and_maybe_drain(base_transfers: Optional[Dict[str, int]] = None) -> Dict[str, int]:
        """Detect elections, then in batch mode drain all resulting surplus transfers."""
        detect_elections(
            pile_counts(piles, candidates), piles, quota,
            elected, elected_votes, ineligible, surplus_queue, seats,
        )
        if not batch or not surplus_queue or len(elected) >= seats:
            return base_transfers or {}
        extra = drain_surplus_queue(
            piles, surplus_queue, quota, candidates,
            elected, elected_votes, ineligible, eliminated, seats, verbose,
        )
        merged = dict(base_transfers) if base_transfers else {}
        for k, v in extra.items():
            merged[k] = merged.get(k, 0) + v
        return merged

    # Count 1: initial tally
    detect_elections(
        pile_counts(piles, candidates), piles, quota,
        elected, elected_votes, ineligible, surplus_queue, seats,
    )
    show_count()

    while len(elected) < seats:
        counts = pile_counts(piles, candidates)

        if surplus_queue:
            src = surplus_queue.pop(0)
            surplus = len(piles.get(src, [])) - quota
            if surplus > 0:
                print(f"\n  Surplus transfer: {src} ({surplus:,} votes)")
                transfers = do_surplus(piles, src, quota, ineligible)
            else:
                transfers = {}
            # Each surplus transfer is its own count; don't batch further surpluses here.
            detect_elections(
                pile_counts(piles, candidates), piles, quota,
                elected, elected_votes, ineligible, surplus_queue, seats,
            )
            show_count(transfers)
            continue

        if not under50_done:
            under50_done = True
            if do_under50_round(piles, counts, ineligible, eliminated):
                # Under-50 redistribution is its own count; surplus transfers are not batched here
                detect_elections(
                    pile_counts(piles, candidates), piles, quota,
                    elected, elected_votes, ineligible, surplus_queue, seats,
                )
                show_count()
                continue

        transfers = do_lowest_elimination(piles, counts, ineligible, eliminated)
        transfers = elect_and_maybe_drain(transfers)
        show_count(transfers)

    return elected, piles


def parse_piles_report(path: Path, code_to_name: Dict[str, str]) -> Dict[str, str]:
    """Parse official Final Piles Report. Returns {ballot_id: candidate_name}.
    Maps CAND_EXHAUSTED to 'Exhausted'. Skips invalid (validity=0) ballots.
    """
    result: Dict[str, str] = {}
    current: Optional[str] = None
    with open(path, encoding='utf8') as f:
        for line in f:
            line = line.strip()
            m = re.match(r'^\.FINAL-PILE\s+(\S+)', line)
            if m:
                code = m.group(1)
                current = 'Exhausted' if code == 'CAND_EXHAUSTED' else code_to_name.get(code, code)
                continue
            if current is None:
                continue
            m = re.match(r'^(\S+),\s+(\d+)\)', line)
            if m and int(m.group(2)):
                result[m.group(1)] = current
    return result


def compare_piles(official: Dict[str, str], sim_piles: Dict[str, List[Ballot]]) -> None:
    # ballot.key includes batch+contest suffix (e.g. "000101-...,00108,001"); strip to serial only
    simulated: Dict[str, str] = {}
    for cand, pile in sim_piles.items():
        for ballot in pile:
            simulated[ballot.key.split(',')[0]] = cand

    elected_official = {bid: c for bid, c in official.items() if c != 'Exhausted'}

    same = 0
    cross: Dict[Tuple[str, str], int] = defaultdict(int)
    only_official: List[str] = []

    for bid, off_cand in elected_official.items():
        sim_cand = simulated.get(bid)
        if sim_cand is None:
            only_official.append(bid)
        elif sim_cand == off_cand:
            same += 1
        else:
            cross[(off_cand, sim_cand)] += 1

    only_sim = [bid for bid in simulated if bid not in official]

    total = len(elected_official)
    diffs = sum(cross.values())
    print(f"\nPiles comparison: {total:,} ballots in official elected piles")
    print(f"  Identical assignment: {same:,}")
    print(f"  Different candidate:  {diffs:,}")
    if only_official:
        print(f"  In official only:     {len(only_official):,}  (exhausted in simulation)")
    if only_sim:
        print(f"  In simulation only:   {len(only_sim):,}  (exhausted in official, kept by elected candidate in ours)")

    if cross:
        print("\nSwitched ballots (Official candidate → Simulated candidate):  count")
        for (off, sim), n in sorted(cross.items(), key=lambda x: -x[1]):
            print(f"  {off:<35}  →  {sim:<35}  {n:,}")


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

    if args.randomize_order:
        rng = random.Random(args.seed)
        rng.shuffle(ballots)
        seed_note = f" (seed={args.seed})" if args.seed is not None else ""
        print(f"Ballot order randomized{seed_note}", file=sys.stderr)

    elected, final_piles = run_election(
        ballots, candidates, seats,
        verbose=args.verbose,
        batch=not args.no_batching,
    )

    print(f"\n{'=' * 50}")
    print("Elected (in order):")
    for i, c in enumerate(elected, 1):
        print(f"  {i:2d}. {c}")

    if args.compare_piles:
        official = parse_piles_report(Path(args.compare_piles), code_to_name)
        compare_piles(official, final_piles)

    return 0


if __name__ == '__main__':
    sys.exit(main(make_parser().parse_args()))
