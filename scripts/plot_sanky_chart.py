#! /usr/bin/python3

import sys

from collections import defaultdict
from typing import Dict, List

import plotly.graph_objects as go

import elections

PLOT=False
DEBUG=True


def main(vote_file, title="Untitled", chart_file=None):
    """Plot sankey graph of election"""
    print(f"Reading '{vote_file}'")
    election = elections.loadElectionsFile(vote_file)
    labels:List[str]        = []
    label_map:Dict[str, int] = {}
    round_votes:List[int] = [0] * election.num_rounds
    source_map = defaultdict(dict)
    target_map:Dict[str, int] = {}
    label_rounds = {}
    previous_label = {}

    ## First pass of candidates
    next_index = 0
    for name, rounds in election.rounds.items():
        for i, e_round in enumerate(rounds):
            if not e_round:
                continue

            n = i + 1
            ## Generate labels, one per candidate per round in which they exist
            label = f"{name} - {n}"
            labels.append(label)
            label_map[label] = next_index
            label_rounds[label] = n
            previous_label[label] = f"{name} - {n-1}"
            next_index += 1
            ## Add to round vote count. This may be less than the total number of votes
            ## as we're not keeping track of candidates that have been elected
            round_votes[i] += e_round.total
            ## Map sources and targets
            if e_round.transfer > 0:
                target_map[label] = e_round.transfer
            elif e_round.transfer < 0:
                source_map[n][label] = e_round.transfer * -1

    ## Track transfers. Note that more than one candidate can lose per round, so transfers
    ## cannot be perfectly accurate in that case
    sources = []
    targets = []
    values  = []
    for label in sorted(target_map.keys(), key=lambda x: label_rounds[x]):
        needed = target_map[label]
        ## Find sources from the correct round
        n = label_rounds[label]
        for source in source_map[n].keys():
            prev_label = previous_label[source]
            sources.append(label_map[prev_label])
            targets.append(label_map[label])
            ## Get needed votes
            available = source_map[n][source]
            if available < 0:
                ## This should never happen
                raise ValueError(f'Label "{source}" ran out of votes. Found {available}')
            elif needed >= available:
                ## Source exhausted
                print(f'Transfer {available} votes from "{prev_label}" to "{label}"')
                print(f"'{source}' eliminated")
                values.append(available)
                needed -= available
                del source_map[n][source]
            else:
                ## Source can provide all needed votes
                print(f'Transfer {needed} votes from "{prev_label}" to "{label}"')
                values.append(needed)
                source_map[n][source] -= needed
                needed = 0

            ## Do we have enough
            if not needed:
                break

    if DEBUG:
        print('label_map', label_map)
        print('sources', sources)
        print('targets', targets)
        print('values', values)

    ## Make plot
    fig = go.Figure(data=[go.Sankey(
        node = dict(
            pad = 15,
            thickness = 20,
            line = dict(color = "black", width = 0.5),
            label = labels,
            color = "blue",
        ),
        link = dict(
            source = sources,
            target = targets,
            value  = values,
        ),
    )])

    fig.update_layout(title_text=title, font_size=10)

    if PLOT:
        fig.show()

    return 0


if __name__ == '__main__':
    usage = f"Usage: {sys.argv[0]} <vote file> <title> [chart file]"
    num_args = len(sys.argv)
    if num_args not in (2, 3, 4):
        print(usage)
        sys.exit(main(sys.argv[1]))

    sys.exit(main(*sys.argv[1:]))
