#! /usr/bin/python3

import csv
import re

from collections import defaultdict, namedtuple
from textwrap import dedent
from typing import Dict, List, Sequence


VotePair = namedtuple("VotePair", "transfer total")
CandidateRounds = List[VotePair]


def truncateList(l:Sequence, *, key=None) -> Sequence:
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



def isWritein(name, *, unnamed=False):
    if not unnamed:
        return bool(re.search(r"^(?:write|written)[ \-]?in\b", name, re.IGNORECASE))

    return bool(re.search(r"^(?:write|written)[ \-]?in\s+(?:P?\d+|other)", name, re.IGNORECASE))


def isNamedWritein(name):
    return (isWritein(name) and not isWritein(name, unnamed=True))


def candidateSortKey(name):
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

    def getNamedCandidates(self):
        return [x for x in self.candidates if not isWritein(x, unnamed=True)]

    def getLastName(self, name):
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

    def electedInRound(self, candidate, n):
        return (candidate in self.elected and (n == len(self.truncated[candidate]) or self.truncated2[candidate][-1].transfer < 0))

    def printStats(self):
        print(dedent(f"""\
            Election stats
            Total: {self.total}
            Quota: {self.quota}
            Number of rounds: {self.num_rounds}
            Number of candidates: {len(self.candidates)}
        """))

    def generateTableRows(self, *, separate_writeins=True, include_total=True):
        ## |Candidate |Round1 Count| |Round2 Transfer|Round2 Count| |Round3 Transfer|Round3 Count| |Round4 Transfer|Round4 Count| |Round5 Transfer|Round5 Count|
        rows = []
        headers = ["Candidate", "Round1 Count"]
        for n in range(2, self.num_rounds + 1):
            headers.extend([" ", f"Round{n} Transfer", f"Round{n} Count"])

        rows.append(headers)

        ## Candidates
        for candidate in self.candidates:
            if separate_writeins and isWritein(candidate):
                rows.append([])
                separate_writeins = False

            rounds = self.rounds[candidate]
            row = [candidate, format(rounds[0].total, ",")]
            for tx, total in rounds[1:]:
                row.extend([" ", format(tx, ","), format(total, ",")])

            rows.append(row)

        if include_total:
            rows.append([])
            rows.append(["Total", format(self.total,",")])

        return rows


def toIntMaybe(x):
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


def loadElectionsFile(path, include_exhausted=False) -> Election:
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
    missing = [x for x in ('total', 'quota', 'invalid', 'date') if x not in stats]
    if missing:
        raise FormatError("Missing required stats: " + ", ".join(missing))

    stats['total'] = stats['total'] - stats['invalid']
    return Election(
        round_count, candidates, elected, counted_on=counted_on, **stats,
    )

class WardElection:
    def __init__(self, precincts, candidates, totals, votes, writein, blank_inv):
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

    def printStats(self):
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
    with open(path, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
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
