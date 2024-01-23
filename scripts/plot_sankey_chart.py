#! /usr/bin/python3

import argparse
import re
import sys

from collections import defaultdict
from typing import Dict, List

import plotly
import plotly.graph_objects as go

import elections

PLOT=True
DEBUG=False
SQUEEZE=True

COLORS_FOR_NODES = ['steelblue', 'gold', 'steelblue', 'green', 'maroon']
COLORS_FOR_LINKS = ['goldenrod', 'lightgreen', 'LightSkyBlue', 'indianred']
## https://davidmathlogic.com/colorblind/#%23332288-%23117733-%2344AA99-%2388CCEE-%23DDCC77-%23CC6677-%23AA4499-%23882255
COLOR_BLIND_FRIENDLY_HEX = [
    "#332288", ## Dark Blue
    "#117733", ## Green
    "#44AA99", ## Turquoise
    "#88CCEE", ## Light Blue
    "#DDCC77", ## Yellow
    "#CC6677", ## Salmon
    "#AA4499", ## Purple
    "#882255", ## Dark Pink
]
COLOR_BLIND_FRIENDLY = [
    (51, 34, 136),   ## Dark Blue
    (17, 119, 51),   ## Green
    (68, 170, 153),  ## Turquoise
    (136, 204, 238), ## Light Blue
    (221, 204, 119), ## Yellow
    (204, 102, 119), ## Salmon
    (170, 68, 153),  ## Purple
    (136, 34, 85),   ## Dark Pink
]
GREY = (68, 68, 68)


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--height-ratio", type=int, default=10,
        help="Ratio of votes to height")
    parser.add_argument("--height", type=int,
        help="Height of graph. Overrides --height-ratio")
    parser.add_argument("--width-ratio", type=int, default=375,
        help="Ratio used to calculate the width of a round. This will scale with the label length")
    parser.add_argument("--width", type=int,
        help="Width of the graph. Overrides --width-factor")
    parser.add_argument("--font-size-ratio", type=int, default=14,
        help="The font size to be used with 10k votes. Will scale with number of votes")
    parser.add_argument("--font-size-min", type=int, default=14,
        help="The minimum font size")
    parser.add_argument("vote_file",
        help="CSV of vote counts")
    parser.add_argument("title", nargs="?", default="Election Results",
        help="Title of the graph")
    parser.add_argument("chart_file", nargs="?",
        help="Where to save the chart. If no extention is provided '.png' will be added.")
    return parser.parse_args()


def boundNumber(num, bottom, top):
    return min(top, max(bottom, num))


def mockColors(num, colors, alpha=1):
    return ['rgba' + str(colors[i%len(colors)] + (alpha,)) for i in range(num)]


def makeColors(colors, alpha=1):
    return ['rgba' + str((r, g, b, alpha)) for r, g, b in colors]


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


def calcXYPositions(election, round_labels, label_total, label_rounds, previous_labels):
    """Calcualte X/Y positions"""
    x_pos_map = {}
    y_pos_map = {}
    y_used    = {}
    round_order = {}
    for n in sorted(round_labels):
        round_count = sum([label_total[x] for x in round_labels[n]])
        y_used[n] = round((election.total - round_count) / election.total, 5)
        if DEBUG:
            print(f"Starting round {n} at {y_used[n]}")
        if n > 1:
            ## Consider position in previous round
            previous_round = round_order[n-1]
            round_order[n] = sorted(
                round_labels[n],
                reverse=True,
                key=lambda x: (label_total[x], -1*previous_round.index(previous_labels[x]))
            )
        else:
            ## Only order by vote total for that round
            round_order[n] = sorted(round_labels[n], key=lambda x: label_total[x], reverse=True)

        ## Make sure 'Exhausted' is last
        if 'Exhausted' not in round_order[n][-1]:
            for i in range(len(round_order[n])):
                if 'Exhausted' in round_order[n][i]:
                    round_order[n] = round_order[n][:i] + round_order[n][i+1:] + [round_order[n][i]]

        ## Determine position for each label
        for label in round_order[n]:
            votes = label_total[label]
            if not votes:
                continue

            ## Calculate Y position
            height = round(votes / election.total, 5)
            y_pos_map[label] = boundNumber(y_used[n], 0.001, 0.999)
            y_used[n] += height

            ## Calculate X position
            denom = election.num_rounds
            xtra = 0
            if SQUEEZE and n < election.num_rounds:
                ## Squeeze together all but the last round
                xtra = 1/election.num_rounds/3
                denom = election.num_rounds + 0.25

            x_pos = (label_rounds[label] / denom) - xtra
            x_pos_map[label] = boundNumber(x_pos, 0.001, 0.999)
            if DEBUG:
                x_pos = round(x_pos_map[label], 3)
                y_pos = round(y_pos_map[label], 3)
                print(f"Label '{label}' votes:{votes} height:{height} y-pos:{y_pos} x-pos:{x_pos}")

    return x_pos_map, y_pos_map


#def main(vote_file, title="Untitled", chart_file=None):
def main(args):
    """Plot sankey graph of election"""
    ## pylint: disable=too-many-nested-blocks,too-many-locals,too-many-branches,too-many-statements
    print(f"Reading '{args.vote_file}'")
    election = elections.loadElectionsFile(args.vote_file, include_exhausted=True)
    election.printStats()

    ## Mappings and info
    ## Labels are text fields used to identify graph nodes in both visually and in code
    ## Each node represents the votes any particular candidate has in a given round
    ## The order of the labels is important, as plotly uses their indices to identify
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

    ## Candidate colors
    num_colors = len(COLOR_BLIND_FRIENDLY)
    candidate_colors = {
        name: COLOR_BLIND_FRIENDLY[i % num_colors] for i, name in enumerate(election.candidates)
    }
    candidate_colors['Exhausted'] = GREY
    label_colors = {}

    ## Add initial count
    init_label = "Valid votes"
    labels.append(init_label)
    label_rounds[init_label]    = 0 ## psudo round
    round_labels[0].append(init_label)
    label_colors[init_label]    = GREY
    source_map[1][init_label]   = election.total ## All votes are availabel as a source in round 1
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
            #label = f"{name} - {n}: {e_round.total:,}"
            label = f"{name} - {n}"
            if election.electedInRound(name, n):
                label += f"<br>ELECTED"

            label += f": {e_round.total:,}"

            candidate_labels[name][n] = label
            labels.append(label)
            label_rounds[label] = n
            round_labels[n].append(label)
            label_total[label] = e_round.total
            label_colors[label] = candidate_colors[name]

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
                    ## Candidate is still in the running
                    if e_round.transfer >= 0:
                        ## Candidate is still in the running or won with no extra votes
                        self_transfers[(prev_label, label)] = e_round.total - e_round.transfer
                    else:
                        ## Candidate won with extra votes
                        label_total[label] = 0 ## Zero out count to hide node

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
    x_pos_map, y_pos_map = calcXYPositions(election, round_labels, label_total, label_rounds, previous_labels)

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
            'line':      dict(color="black", width=0.5),
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
    node_colors = makeColors([label_colors[x] for x in labels])
    link_colors = makeColors([label_colors[labels[x]] for x in sources], alpha=0.6)
    fig.update_traces(node_color=node_colors, link_color=link_colors)

    ## Title and text
    fig.update_layout(title_text=args.title, font_size=12)

    ## Save to file
    if args.chart_file:
        chart_file = args.chart_file
        height = election.total / args.height_ratio
        w_factor = int(args.width_ratio*max(30, max(map(len, labels)))/30)
        ## Goal is for 14 when vote total is 10k
        font_size = max(args.font_size_min, int(args.font_size_min*election.total / 10000))
        if re.search(r"\.html$", chart_file, re.IGNORECASE):
            plotly.offline.plot(fig, filename=chart_file)
        elif re.search(r"\.svg$", chart_file, re.IGNORECASE):
            height *= 3/4
            font_size = max(10, int(font_size*5/6))
            fig.update_layout(font_size=font_size, width=election.num_rounds*w_factor, height=height)
            fig.write_image(chart_file)
        else:
            fig.update_layout(font_size=font_size, width=election.num_rounds*w_factor, height=height)
            if '.' not in chart_file:
                chart_file += ".png"
                print(f"Saving as png '{chart_file}'")
            else:
                print(f"Saving as '{chart_file}'")

            fig.write_image(chart_file)
    elif PLOT:
        ## Plot now
        fig.show()

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
