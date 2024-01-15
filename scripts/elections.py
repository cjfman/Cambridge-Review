#! /usr/bin/python3

import csv

from collections import namedtuple
from typing import Dict, List, Sequence


VotePair = namedtuple("VotePair", "transfer total")
CandidateRounds = List[VotePair]


def truncateList(l:Sequence) -> Sequence:
    """Remove duplicate values from the end of a list"""
    if len(l) < 2:
        return l

    last_val = l[-1]
    last_idx = len(l) - 1
    for i in range(last_idx, 0, -1):
        if l[i] == last_val:
            last_idx = i
        else:
            break

    return l[:last_idx+1]


class FormatError(Exception):
    pass


class Election:
    def __init__(self, num_rounds:int, all_rounds:Dict[str, CandidateRounds], elected:Sequence[str], total, quota):
        self.candidates = list(all_rounds.keys())
        self.num_rounds = num_rounds
        self.rounds     = all_rounds
        self.votes      = {}
        self.truncated  = {}
        self.elected    = elected
        self.total      = total
        self.quota      = quota
        self.eliminated = {}
        self.max_votes  = 0

        ## Preprocessing
        for name, rounds in self.rounds.items():
            ## Find eliminated
            for i, vp in enumerate(rounds):
                if not vp.count:
                    self.eliminated[name] = i + 1
                    break

            ## Extract just the votes from the rounds
            self.votes[name]     = [x.total for x in rounds]
            self.truncated[name] = truncateList(self.votes[name])
            self.max_votes = max(self.max_votes, max(self.votes[name]))


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
    state = 'start'
    round_count = 0
    candidates = {}
    stats = {}
    elected = []
    exclude = ['invalid', 'total']
    if not include_exhausted:
        exclude.append('exhausted')

    ## Open file and parse it
    with open(path, 'r', encoding='utf8') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            col1 = row[0]
            if state == 'start':
                ## Get the round count
                round_count = getRoundCount(row)
                state = 'candidate'
            elif state == 'candidate':
                ## Collect candidate info
                if col1 == '':
                    state = 'stats'
                elif col1.lower() not in exclude:
                    ## Check number of rows
                    if len(row) != round_count * 2:
                        raise FormatError(f"Candidate '{col1}' doesn't have the correct number of columns. Found {len(row)} expected {round_count*2}")

                    try:
                        candidates[col1] = processCandidate(row[1:])
                    except Exception as e:
                        raise FormatError(f"Error when processing candidate '{col1}'") from e
            elif state == 'stats':
                if col1 == 'Elected':
                    state = 'elected'
                else:
                    stats[col1.lower()] = toIntMaybe(row[1])
            elif state == 'elected':
                if col1 == '':
                    state = 'stats'
                elif int(col1) - 1 != len(elected):
                    raise FormatError(f"Elected candidate out of order. Found '{col1}'")

                elected.append(row[1])

    ## Check for required stats
    missing = [x for x in ('total', 'quota') if x not in stats]
    if missing:
        raise FormatError("Missing required stats: " + ", ".join(missing))

    return Election(round_count, candidates, elected, stats['total'], stats['quota'])
