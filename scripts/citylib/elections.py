#! /usr/bin/python3

## pylint: disable=line-too-long

import csv
import re

from collections import defaultdict, namedtuple
from dataclasses import dataclass
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


VotePair = namedtuple("VotePair", "transfer total")
CandidateRounds = List[VotePair]


def truncateList(l: Sequence, *, key: Optional[Callable] = None) -> Sequence:
    """Remove duplicate values from the end of a list"""
    if len(l) < 2:
        return l

    l2 = l
    if key is not None:
        l2 = [key(x) for x in l]

    last_val = l2[-1]
    last_idx = len(l) - 1
    for i in range(last_idx, 0, -1):
        if l2[i] == last_val:
            last_idx = i
        else:
            break

    return l[:last_idx+1]


class FormatError(Exception):
    pass



def isWritein(name, *, unnamed: bool = False) -> bool:
    if not unnamed:
        return bool(re.search(r"^(?:write|written)[ \-]?in\b", name, re.IGNORECASE))

    return bool(re.search(r"^(?:write|written)[ \-]?in\s+(?:P?\d+|other)", name, re.IGNORECASE))


def isNamedWritein(name) -> bool:
    return (isWritein(name) and not isWritein(name, unnamed=True))


def candidateSortKey(name) -> Tuple[int, str]:
    match = re.match(r"^write[ \-]in\b\D*(\d+)?", name, re.IGNORECASE)
    if not match:
        return (-1, name)

    groups = match.groups()
    if groups and groups[0] is not None:
        return (int(groups[0]), name)
    elif 'other' in name.lower():
        return (100, name)

    return (0, name)


class Election:
    def __init__(self, num_rounds:int, all_rounds:Dict[str, CandidateRounds], elected:Sequence[str], *, total=0, quota=0, date=None, counted_on=None, source=None, **kwargs):
        self.candidates = sorted(all_rounds.keys(), key=candidateSortKey)
        self.num_rounds = num_rounds
        self.rounds     = all_rounds
        self.source     = source
        self.elected    = elected
        self.total      = total
        self.quota      = quota
        self.date       = date
        self.counted_on = counted_on or [date]
        self.votes      = {}
        self.truncated  = {}
        self.truncated2 = {}
        self.eliminated = {}
        self.max_votes  = 0
        self.last_round = {}
        self.last_names = {}

        ## Preprocessing
        for name, rounds in self.rounds.items():
            ## Find eliminated
            for i, vp in enumerate(rounds):
                if not vp.count:
                    self.eliminated[name] = i + 1
                    break

            ## Extract just the votes from the rounds
            self.votes[name]      = [x.total for x in rounds]
            self.truncated[name]  = truncateList(self.votes[name])
            self.truncated2[name] = truncateList(self.rounds[name], key=lambda x: x.total)
            self.max_votes = max(self.max_votes, max(self.votes[name]))

        ## Last round
        for name, rounds in self.truncated.items():
            self.last_round[name] = len(rounds)

    def getNamedCandidates(self) -> List[str]:
        return [x for x in self.candidates if not isWritein(x, unnamed=True)]

    def getLastName(self, name) -> str:
        if self.last_names:
            return self.last_names[name]

        has_commas = all([',' in x or ' ' not in x or isWritein(x) for x in self.candidates])
        if has_commas:
            for fullname in self.candidates:
                self.last_names[fullname] = fullname.split(',')[0]
        else:
            for fullname in self.candidates:
                split = fullname.split(' ')
                if split[-1].lower().replace('.', '') in ('jr', 'md', 'phd'):
                    self.last_names[fullname] = " ".join(split[-2:])
                else:
                    self.last_names[fullname] = split[-1]

        return self.last_names[name]

    def electedInRound(self, candidate, n: int) -> bool:
        return (candidate in self.elected and (n == len(self.truncated[candidate]) or self.truncated2[candidate][-1].transfer < 0))

    def printStats(self) -> None:
        print(dedent(f"""\
            Election stats
            Total: {self.total}
            Quota: {self.quota}
            Number of rounds: {self.num_rounds}
            Number of candidates: {len(self.candidates)}
        """))

    def generateTableRows(self, *, separate_writeins: bool = True, include_total: bool = True) -> List[List]:
        ## |Candidate |Round1 Count|Round2 Transfer|Round2 Count|Round3 Transfer|Round3 Count|Round4 Transfer|Round4 Count|Round5 Transfer|Round5 Count|
        rows = []
        headers = ["Candidate", "Round1 Count"]
        for n in range(2, self.num_rounds + 1):
            headers.extend([f"Round{n} Transfer", f"Round{n} Count"])

        rows.append(headers)

        ## Candidates
        for candidate in self.candidates:
            if separate_writeins and isWritein(candidate):
                rows.append([])
                separate_writeins = False

            rounds = self.rounds[candidate]
            row = [candidate, format(rounds[0].total, ",")]
            for tx, total in rounds[1:]:
                row.extend([format(tx, ","), format(total, ",")])

            rows.append(row)

        if include_total:
            rows.append([])
            rows.append(["Total", format(self.total,",")])

        return rows


def toIntMaybe(x: Any) -> Any:
    try:
        return int(x)
    except ValueError:
        return x


def getRoundCount(headers:Sequence[str]) -> int:
    ## Validate row
    num_headers = len(headers)
    if num_headers < 2 or num_headers % 2 != 0:
        raise FormatError("Expected an even number of headers")
    if headers[0].lower() not in ('candidate', 'candidates'):
        print(type(headers[0]), headers[0], headers[0][0], 'CATCH!', headers[0][1])
        raise FormatError(f"First column header isn't 'Candidate'. Found '{headers[0]}'")
    if headers[1] != 'Count 1':
        raise FormatError(f"First column header isn't 'Count 1'. Found '{headers[1]}'")

    round_count = num_headers // 2
    for i in range(1, round_count):
        n = i+1
        if headers[i*2] != f"Transfer {n}":
            raise FormatError(f"Expected 'Transfer {n}'. Found '{headers[i*2]}'")
        if headers[i*2+1] != f"Count {n}":
            raise FormatError(f"Expected 'Count {n}'. Found '{headers[i*2+1]}'")

    return round_count


def processCandidate(votes:Sequence[str]) -> CandidateRounds:
    rounds = []
    count1 = int(votes[0])
    rounds.append(VotePair(count1, count1))
    for i in range(1, len(votes), 2):
        rounds.append(VotePair(int(votes[i]), int(votes[i+1])))

    return rounds


def loadElectionsFile(path, include_exhausted: bool = False) -> Election:
    ## pylint: disable=too-many-nested-blocks,too-many-locals,too-many-branches,too-many-statements
    state = 'start'
    round_count = 0
    candidates = {}
    stats = {}
    elected = []
    counted_on = None

    ## Open file and parse it
    with open(path, 'r', encoding='utf8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            col1 = row[0]
            col_low = col1.lower()
            if state == 'start':
                ## Get the round count
                round_count = getRoundCount(row)
                state = 'candidate'
            elif state == 'candidate':
                ## Collect candidate info
                if col1 == '':
                    state = 'stats'
                elif col_low == 'invalid':
                    stats['invalid'] = int(row[1])
                elif col_low == 'total':
                    stats['total'] = int(row[1])
                elif col_low == 'exhausted' and not include_exhausted:
                    pass
                else:
                    ## Check number of rows
                    if len(row) != round_count * 2:
                        raise FormatError(f"Candidate '{col1}' doesn't have the correct number of columns. Found {len(row)} expected {round_count*2}")

                    try:
                        candidates[col1] = processCandidate(row[1:])
                    except Exception as e:
                        raise FormatError(f"Error when processing candidate '{col1}'") from e
            elif state == 'stats':
                if col_low == 'elected':
                    state = 'elected'
                elif col_low == 'counted dates':
                    counted_on = [x for x in row[1:] if x != '']
                else:
                    stats[col1.lower()] = toIntMaybe(row[1])
            elif state == 'elected':
                if col1 == '':
                    state = 'stats'
                elif int(col1) - 1 != len(elected):
                    raise FormatError(f"Elected candidate out of order. Found '{col1}'")
                else:
                    elected.append(row[1])

    if 'election date' in stats:
        stats['date'] = stats['election date']
        del stats['election date']

    ## Check for required stats
    if 'invalid' not in stats:
        stats['invalid'] = 0

    missing = [x for x in ('total', 'quota', 'date') if x not in stats]
    if missing:
        raise FormatError("Missing required stats: " + ", ".join(missing))

    stats['total'] = stats['total'] - stats['invalid']
    return Election(
        round_count, candidates, elected, counted_on=counted_on, **stats,
    )

class WardElection:
    def __init__(self, precincts: List[str], candidates: List[str], totals: Dict[str, int], votes: Dict[str, Dict[str, int]], writein: Dict[str, int], blank_inv: Dict[str, int]) -> None:
        self.precincts  = precincts
        self.candidates = candidates
        self.c_totals   = totals ## Dict[candidate, Dict[precinct, count]]
        self.c_votes    = votes
        self.writein    = writein
        self.blank_inv  = blank_inv
        self.p_totals   = defaultdict(int)
        self.p_votes    = defaultdict(dict) ## Dict[precinct, Dict[candidate, count]]
        self.max_count  = 0
        self.winners    = set()
        self.p_winners  = defaultdict(lambda: ('', 0))

        ## Organize votes by precinct
        for name, c_votes in self.c_votes.items():
            for precinct, count in c_votes.items():
                count = int(count)
                self.p_votes[precinct][name] = count
                self.p_totals[precinct] += count
                if precinct != "Total":
                    self.max_count = max(self.max_count, count)
                    if self.p_winners[precinct][1] < count:
                        self.winners.add(name)
                        self.p_winners[precinct] = (name, count)

    def printStats(self) -> None:
        print(dedent(f"""\
            Election stats
            Number of precincts: {len(self.precincts)}
            Number of candidates: {len(self.candidates)}
            Max Count: {self.max_count}
        """))

def loadWardElectionFile(path) -> WardElection:
    ## pylint: disable=too-many-nested-blocks,too-many-locals,too-many-branches,too-many-statements
    precincts = None
    candidates = {}
    ## Open file and do basic processing
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if 'Candidate' not in reader.fieldnames:
            raise KeyError(f"Wards file '{path}' not properly formatted. Missing column 'Candidate'. Found {reader.fieldnames}")

        precincts = reader.fieldnames[2:]
        for row in reader:
            candidate = row['Candidate']
            votes = { x: int(y) for x, y in row.items() if y.isnumeric() }
            candidates[candidate] = votes
            for p in precincts:
                if p not in votes or not votes[p]:
                    votes[p] = 0

    totals    = candidates['Total']
    blank_inv = candidates['Blank / Invalid']
    writein   = candidates['Write-In']
    del candidates['Total']
    del candidates['Blank / Invalid']
    del candidates['Write-In']
    return WardElection(precincts, list(candidates.keys()), totals, candidates, writein, blank_inv)


class Ballot:
    def __init__(self, key, holder, candidates: Sequence[str]) -> None:
        self.key        = key
        self.holder     = holder
        self.candidates = candidates

    def __len__(self) -> int:
        return len(self.candidates)

    def __contains__(self, key) -> bool:
        return key in self.candidates

    def __getitem__(self, idx: int) -> str:
        return self.candidates[idx]


def loadBallotPiles(path) -> Dict[str, List[Ballot]]:
    valid_count = 0
    invalid_count = 0
    name = None
    piles = {}
    candidate_codes = {}
    code_to_name = lambda x: candidate_codes[x] if x in candidate_codes else x
    with open(path, encoding='utf8') as f:
        for line in f:
            ## Register a candidate
            match = re.match(r'^.CANDIDATE (\w+), "(.+)"$', line)
            if match:
                candidate_codes[match.groups()[0]] = match.groups()[1]
                name = None
                continue

            ## Start of a pile
            match = re.match(r"^.FINAL-PILE (\w+)", line)
            if match:
                name = code_to_name(match.groups()[0])
                piles[name] = []
                continue

            ## Other unsupported command
            if line.startswith('.'):
                name = None

            ## Add ballot to the pile
            ## Ex: 000203-00-09060000167208, 1) C17,C08,C05,C04,C07,C14
            match = re.match(r"(\S+), (\d+)\) ([C0-9,=]+)$", line)
            if match:
                key = match.groups()[0]
                valid = bool(int(match.groups()[1]))
                if not valid:
                    invalid_count += 1
                    continue

                valid_count += 1
                names = [code_to_name(x) for x in match.groups()[2].split(",") if '=' not in x]
                piles[name].append(Ballot(key, name, names))

    return piles


def loadFlattenedBallotPiles(path) -> List[Ballot]:
    return [ballot for pile in loadBallotPiles(path).values() for ballot in pile]


def loadFinalBallots(path) -> List[Ballot]:
    ## 001001-00-00290000006098,00112,001,1) C19[1],C08[2],C12[3],C17[4],C07[5],C13[6]
    invalid = 0
    ballots = []
    with open(path, encoding='utf8') as f:
        ## Parse each line
        for line in f:
            line = line.strip()
            #match = re.match(r"^(\S+)(?:,\d+)+\) ((?:C|WI)\d+\[\d+\](?:,(?:C|WI)\d+\[\d+\])*)", line)
            match = re.match(r"^(\S+)(?:,\d+)+\) ([CWI0-9,=\[\]]+)$", line)
            if not match:
                print(f"Invalid ballot: {line}")
                invalid += 1
                continue

            key = match.groups()[0]
            entries = match.groups()[1].split(',')
            ranks = {}

            ## Parse each entry
            for entry in entries:
                match = re.match(r"^([CWI0-9]+)\[(\d+)\]$", entry)
                if match:
                    name = match.groups()[0]
                    rank = int(match.groups()[1])
                    if rank in ranks:
                        ranks[rank] = ""
                    else:
                        ranks[rank] = name

            ## Sort candidates
            candidates = [x[1] for x in sorted(ranks.items()) if x[1]]
            ballots.append(Ballot(key, None, candidates))

    print(f"Invalid ballots: {invalid}")
    return ballots


@dataclass
class ElectionConfiguration:
    titles:List[str]
    contest:str
    elect:int
    candidates:Dict[str,str]


def load_election_configuration(path) -> ElectionConfiguration:
    titles = []
    contest = ""
    elect = 0
    candidates = {}
    with open(path, encoding='utf8') as f:
        for line in f:
            ## Get title
            match = re.match(r'^.TITLE (\S+)', line)
            if match:
                titles.append(match.groups()[0])
                continue

            match = re.match(r'^.CONTEST (\S+)', line)
            if match:
                contest = match.groups()[0]
                continue

            match = re.match(r'^.ELECT (\d+)', line)
            if match:
                contest = int(match.groups()[0])
                continue

            ## Register a candidate
            match = re.match(r'^.CANDIDATE (\w+), "(.+)"$', line)
            if match:
                candidates[match.groups()[0]] = match.groups()[1]
                continue

    return ElectionConfiguration(titles, contest, elect, candidates)
