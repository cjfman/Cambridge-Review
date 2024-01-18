#! /usr/bin/python3

import sys

from collections import defaultdict
from typing import Dict, List

import plotly.graph_objects as go

import elections

PLOT=True
DEBUG=False

COLORS_FOR_NODES = ['steelblue', 'gold', 'steelblue', 'green', 'maroon']
COLORS_FOR_LINKS = ['goldenrod', 'lightgreen', 'LightSkyBlue', 'indianred']


def boundNumber(num, bottom, top):
    return min(top, max(bottom, num))


def mockColors(num, colors):
    return [colors[i%len(colors)] for i in range(num)]


def fixOrder(sources, targets, values):
    """Order by source, then target, then value"""
    ## This is nessessary because plotly is sensitive to order
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
        y_used[n] = round((election.total - round_count) / election.total, 5)
        print(f"Starting round {n} at {y_used[n]}")
        for label in sorted(round_labels[n], key=lambda x: label_total[x], reverse=True):
            votes = label_total[label]
            if not votes:
                continue

            height = round(votes / election.total, 5)
            y_pos_map[label] = boundNumber(y_used[n], 0.001, 0.999)
            y_used[n] += height
            x_pos = label_rounds[label]/election.num_rounds
            x_pos_map[label] = boundNumber(x_pos, 0.001, 0.999)
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

    ## Mappings and info
    ## Labels are text fields used to identify graph nodes in both visually and in code
    ## Each node represents the votes any particular candidate has in a given round
    ## The order of the lables is important, as plotly uses their indices to identify
    ## transfers
    labels:List[str]          = []                ## Label per candidate per round
    source_map                = defaultdict(dict) ## Sources of transfer votes each round
    target_map:Dict[str, int] = {}                ## Candidates receiving transfers each round
    label_rounds              = {}                ## Maps labels to their respective rounds
    round_labels              = defaultdict(list) ## List of labels in each round
    candidate_labels          = defaultdict(dict) ## List of labels for each candidate per round
    previous_labels           = {}                ## Mapping of previous label for a label
    self_transfers            = {}                ## Pairs of nodes for same candidate transfers
    label_total               = {}                ## The number of votes for a given label

    ## Add initial count
    init_label = "Valid votes"
    labels.append(init_label)
    label_rounds[init_label]    = 0 ## psudo round
    round_labels[0].append(init_label)
    source_map[1][init_label]   = election.total ## All votes are available as a source in round 1
    label_total[init_label]     = election.total
    previous_labels[init_label] = init_label     ## This is needed so that the makeNodes(...)
                                                 ## function knows what source to use in round 1

    ## First pass of candidates
    for name, rounds in election.truncated2.items():
        ## Loop over every round for a candidate
        for i, e_round in enumerate(rounds):
            ## Exclude candidates that have no votes
            if not e_round:
                continue

            n = i + 1 ## Round number
            ## Generate labels, one per candidate per round in which they exist
            label = f"{name} - {n}: {e_round.total:,}"
            candidate_labels[name][n] = label
            labels.append(label)
            label_rounds[label] = n
            round_labels[n].append(label)
            label_total[label] = e_round.total

            ## Map sources and targets
            if e_round.transfer > 0:
                target_map[label] = e_round.transfer
            elif e_round.transfer < 0:
                source_map[n][label] = e_round.transfer * -1

            ## Do additional mappings if this isn't the first round
            if n > 1:
                prev_label = candidate_labels[name][n-1]
                previous_labels[label] = prev_label
                if e_round.total:
                    ## The candidate is still in the running
                    if e_round.transfer > 0:
                        ## The candidate is receiving transfer votes
                        self_transfers[(prev_label, label)] = e_round.total - e_round.transfer
                    else:
                        if not e_round.transfer:
                            ## Transfer carry over votes to the next round
                            self_transfers[(prev_label, label)] = e_round.total
                        else:
                            ## The candidate was elected
                            label_total[label] = 0 ## Zero out count for winners

    ## Make nodes
    sources, targets, values = makeNodes(source_map, target_map, label_rounds, previous_labels)

    ## Add self transfers
    for key, total in self_transfers.items():
        src, dst = key
        if not total:
            ## Don't add 0 vote transfers
            print(f'Skip pass through from "{src}" to "{dst}"')
            continue

        sources.append(src)
        targets.append(dst)
        values.append(total)
        print(f'Pass through {total} votes from "{src}" to "{dst}"')

    ## Calcualte X/Y positions
    x_pos_map, y_pos_map = calcXYPositions(election, round_labels, label_total, label_rounds)

    ## Convert labels to indices
    ## Plotly is sensitive to ordering. Nodes should be in the order from top to bottom, left to right
    ## Sort them by round, then decreasing vote total
    labels = [x for x in labels if label_total[x]]
    labels.sort(key=lambda x: (label_rounds[x], election.total - label_total[x]))
    label_map = { x: i for i, x in enumerate(labels) }
    sources = [label_map[x] for x in sources]
    targets = [label_map[x] for x in targets]
    sources, targets, values = fixOrder(sources, targets, values)
    x_vals = [x_pos_map[x] for x in labels]
    y_vals = [y_pos_map[x] for x in labels]

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
            'x': x_vals,
            'y': y_vals,
        },
        link = {
            'source': sources,
            'target': targets,
            'value':  values,
        },
    )])

    ## Colors
    node_colors = mockColors(len(labels), COLORS_FOR_NODES)
    link_colors = mockColors(len(sources), COLORS_FOR_LINKS)
    fig.update_traces(node_color=node_colors, link_color=link_colors)

    ## Title and text
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
