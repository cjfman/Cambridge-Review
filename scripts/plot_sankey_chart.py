#! /usr/bin/python3

import sys

from collections import defaultdict
from typing import Dict, List

import plotly.graph_objects as go

import elections

PLOT=True
DEBUG=True


def boundNumber(num, bottom, top):
    return min(top, max(bottom, num))


def fixOrder(sources, targets, values):
    zipped = list(sorted(zip(sources, targets, values)))
    src = [x[0] for x in zipped]
    dst = [x[1] for x in zipped]
    val = [x[2] for x in zipped]
    return (src, dst, val)


def makeNodes(source_map, target_map, label_rounds, previous_labels):
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
            prev_label = previous_labels[source]
            sources.append(prev_label)
            targets.append(label)
            ## Get needed votes
            availabel = source_map[n][source]
            if availabel < 0:
                ## This should never happen
                raise ValueError(f'Label "{source}" ran out of votes. Found {availabel}')
            elif needed >= availabel:
                ## Source exhausted
                print(f'Transfer {availabel} votes from "{prev_label}" to "{label}"')
                print(f"'{source}' eliminated")
                values.append(availabel)
                needed -= availabel
            elif needed < availabel:
                ## Source can provide all needed votes
                print(f'Transfer {needed} votes from "{prev_label}" to "{label}"')
                values.append(needed)
                source_map[n][source] -= needed
                needed = 0

            ## Do we have enough
            if not needed:
                break

        if needed:
            raise ValueError(f'Failed to get enough votes for "{label}". Still need {needed}')

    return sources, targets, values


def calcXYPositions(election, round_labels, label_total, label_rounds):
    """Calcualte X/Y positions"""
    x_pos_map = {}
    y_pos_map = {}
    y_used    = {}
    for n in sorted(round_labels):
        round_count = sum([label_total[x] for x in round_labels[n]])
        y_used[n] = round((election.total - round_count) / election.total / 2, 5)
        print(f"Starting round {n} at {y_used[n]}")
        for label in sorted(round_labels[n], key=lambda x: label_total[x], reverse=False):
            votes = label_total[label]
            if not votes:
                continue

            height = round(votes / election.total, 5)
            y_pos_map[label] = boundNumber(y_used[n], 0.001, 0.99)
            y_used[n] += height + 0.02
            x_pos = label_rounds[label]/election.num_rounds
            x_pos_map[label] = boundNumber(x_pos, 0.001, 0.99)
            if DEBUG:
                x_pos = round(x_pos_map[label], 3)
                y_pos = round(y_pos_map[label], 3)
                print(f"Label '{label}' votes:{votes} height:{height} y-pos:{y_pos} x-pos:{x_pos}")

    return x_pos_map, y_pos_map


def main(vote_file, title="Untitled", chart_file=None):
    """Plot sankey graph of election"""
    print(f"Reading '{vote_file}'")
    election = elections.loadElectionsFile(vote_file, include_exhausted=True)
    election.printStats()
    labels:List[str]        = []
    label_map:Dict[str, int] = {}
    source_map = defaultdict(dict)
    target_map:Dict[str, int] = {}
    label_rounds = {}
    round_labels = defaultdict(list)
    previous_labels = {}
    self_transfers = {}
    label_total = {}

    ## Add initial count
    init_label = "Valid votes"
    labels.append(init_label)
    label_rounds[init_label] = 0
    round_labels[0].append(init_label)
    source_map[1][init_label] = election.total
    label_total[init_label] = election.total
    previous_labels[init_label] = init_label

    ## First pass of candidates
    for name, rounds in election.truncated2.items():
        for i, e_round in enumerate(rounds):
            if not e_round:
                continue

            n = i + 1
            ## Generate labels, one per candidate per round in which they exist
            label = f"{name} - {n}"
            prev_label = f"{name} - {n-1}"
            labels.append(label)
            label_rounds[label] = n
            round_labels[n].append(label)
            previous_labels[label] = prev_label
            label_total[label] = e_round.total

            ## Map sources and targets
            if e_round.transfer > 0:
                target_map[label] = e_round.transfer
            elif e_round.transfer < 0:
                source_map[n][label] = e_round.transfer * -1

            if n > 1 and e_round.total:
                if e_round.transfer > 0:
                    self_transfers[(prev_label, label)] = e_round.total - e_round.transfer
                else:
                    if not e_round.transfer:
                        self_transfers[(prev_label, label)] = e_round.total
                    else:
                        label_total[label ] = 0 ## Zero out count for winners



    ## Make nodes
    sources, targets, values = makeNodes(source_map, target_map, label_rounds, previous_labels)

    ## Add self transfers
    for key, total in self_transfers.items():
        if not total:
            print(f'Skip pass through from "{src}" to "{dst}"')
            continue

        src, dst = key
        sources.append(src)
        targets.append(dst)
        values.append(total)
        print(f'Pass through {total} votes from "{src}" to "{dst}"')

    ## Calcualte X/Y positions
    x_pos_map, y_pos_map = calcXYPositions(election, round_labels, label_total, label_rounds)

    ## Convert labels to indices
    labels = [x for x in labels if label_total[x]]
    #labels.sort(key=lambda x: (label_rounds[x], election.total - label_total[x]))
    labels.sort(key=lambda x: (label_rounds[x], label_total[x]))
    label_map = { x: i for i, x in enumerate(labels) }
    sources = [label_map[x] for x in sources]
    targets = [label_map[x] for x in targets]
    sources, targets, values = fixOrder(sources, targets, values)

    ## Print values
    if DEBUG:
        print('labels', labels)
        print('label_map', label_map)
        print('sources', sources)
        print('targets', targets)
        print('values', values)

    ## Make plot
    fig = go.Figure(data=[go.Sankey(
        arrangement = 'snap',
        node = {
            'pad':       15,
            'thickness': 20,
            'line':      dict(color = "black", width = 0.5),
            'label':     labels,
            'color':     "blue",
            'x': [x_pos_map[x] for x in labels],
            'y': [y_pos_map[x] for x in labels],
        },
        link = {
            'source': sources,
            'target': targets,
            'value':  values,
        },
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
