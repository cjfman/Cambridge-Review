#!/usr/bin/env python3

import argparse
import datetime as dt
import re
import sys

from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

import plotly
import plotly.graph_objects as go

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib import elections
from citylib.utils import insertCopyright, insertNoCache

VERBOSE=False
DEBUG=False
SQUEEZE=True

#HOVERCOLORS      = ['midnightblue', 'lightskyblue', 'gold', 'mediumturquoise', 'lightgreen', 'cyan']
HOVERCOLORS      = ['#648FFF', '#785EF0', '#DC267F', '#FE6100', '#FFB000']
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
COLOR_BLIND_FRIENDLY.reverse()
GREY = (68, 68, 68)


def parseArgs():
    parser = argparse.ArgumentParser()

    parser.set_defaults(func=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--config",
        help="Election configuration")
    subparsers = parser.add_subparsers()

    ## plot cmd
    plot_parser = subparsers.add_parser('plot',
        help="Plot first transfer")
    plot_parser.set_defaults(func=plot_hdlr)
    plot_parser.add_argument("ballots_file",
        help="Ballot piles file")
    plot_parser.add_argument("chart_file", nargs="?",
        help="Where to save the chart. If no extention is provided '.png' will be added.")

    ## counts
    plot_parser = subparsers.add_parser('count',
        help="Count ballot positions")
    plot_parser.set_defaults(func=count_hdlr)
    plot_parser.add_argument("--holders", action='store_true')
    plot_parser.add_argument("ballots_file",
        help="Ballot piles file")
    #plot_parser.add_argument("chart_file", nargs="?",
    #    help="Where to save the chart. If no extention is provided '.png' will be added.")

    ## Final parse
    args = parser.parse_args()

    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True

    return args

def plot_hdlr(args):
    print(f"Reading '{args.ballots_file}'")
    ballots = elections.loadFlattenedBallotPiles(args.ballots_file)
    pairs = set() ## Pairs of source and targets
    transfers = defaultdict(lambda: defaultdict(int))
    transposed = defaultdict(lambda: defaultdict(int))
    label_names:Dict[str] = {}
    source_labels = set()
    target_labels = set()

    ## Sum the transfers
    for ballot in ballots:
        source = ballot[0]
        target = ballot[1] if len(ballot) > 1 else source
        transfers[source][target] += 1
        transposed[target][source] += 1
        if target == "CAND_EXHAUSTED":
            continue

        ## Generate lables
        src_label = f"{source} - #1s"
        source_labels.add(src_label)
        label_names[src_label] = source
        dst_label = f"{target} - #2s"
        pairs.add((src_label, dst_label))
        target_labels.add(dst_label)
        label_names[dst_label] = target

    labels = list(sorted(source_labels)) + list(sorted(target_labels))
    pairs  = sorted(pairs)
    label_map = { x: i for i, x in enumerate(labels) }
    sources = [label_map[x[0]] for x in pairs]
    targets = [label_map[x[1]] for x in pairs]
    values  = [transfers[label_names[x[0]]][label_names[x[1]]] for x in pairs]

    ## Colors
    hovercolors = HOVERCOLORS
    hovercolors *= len(pairs) // len(hovercolors)
    hovercolors += hovercolors[:len(pairs) % len(hovercolors)]

    ## Custom nodes
    out_text_map = { src: f"{src} #1s<br><br>" + "<br>".join([f"{dst}: {val}" for dst, val in sorted(dsts.items())]) for src, dsts in transfers.items() }
    in_text_map  = { dst: f"{dst} #2s<br><br>" + "<br>".join([f"{src}: {val}" for src, val in sorted(srcs.items())]) for dst, srcs in transposed.items() }
    text_map = { x: out_text_map[label_names[x]] for x in source_labels }
    text_map.update({ x: in_text_map[label_names[x]] for x in target_labels })
    node_txt = [text_map[x] for x in labels]
    src_steps = len(source_labels)
    dst_steps = len(target_labels)
    x_vals = [0.2]*src_steps + [0.8]*dst_steps
    y_vals = [min(0.99, x/src_steps+0.01) for x in range(src_steps)]
    y_vals += [min(0.99, x/dst_steps+0.01) for x in range(dst_steps)]

    fig = go.Figure(data=[go.Sankey(
        arrangement='fixed',
        node={
            'pad':       20,
            'thickness': 20,
            'line':      dict(color='black', width=0.5),
            'label':     [''] * len(labels),
            'color':     'blue',
            'customdata': node_txt,
            'hovertemplate': '%{customdata}',
            'x': x_vals,
            'y': y_vals,
        },
        link={
            'source':     sources,
            'target':     targets,
            'value':      values,
            'color':      'rgba(0, 0, 0, .05)',
            'hovercolor': hovercolors,
        },
    )])

    fig.update_layout(title_text="Basic Sankey Diagram", font_size=10)

    for i, label in enumerate(labels):
        is_source = i < src_steps
        x_shift = 0.0125 * 2 / 3
        x_ann = x_vals[i] - x_shift if is_source else x_vals[i] + x_shift
        fig.add_annotation(
            x=x_ann, y=1.0 - y_vals[i],
            xref='paper', yref='paper',
            text=label,
            showarrow=False,
            xanchor='right' if is_source else 'left',
            yanchor='middle',
            align='right' if is_source else 'left',
            font=dict(size=10),
        )

    if not args.chart_file:
        fig.show()
    else:
        print(f"Saving as '{args.chart_file}'")
        plotly.offline.plot(fig, filename=args.chart_file, auto_open=False)
        if insertNoCache(args.chart_file):
            print(f"Inserted no-cache lines into '{args.chart_file}'")

    return 0


def count_hdlr(args):

    elec_config = None
    if args.config is not None:
        print(f"Reading '{args.config}'")
        elec_config = elections.load_election_configuration(args.config)

    code_to_name = lambda x: elec_config.candidates[x] if elec_config and x in elec_config.candidates else x

    print(f"Reading '{args.ballots_file}'")
    ballots = None
    if args.holders:
        ballots = elections.loadFlattenedBallotPiles(args.ballots_file)
    else:
        ballots = elections.loadFinalBallots(args.ballots_file)

    max_rank = 0
    candidates = defaultdict(lambda: defaultdict(int))
    for ballot in ballots:
        if args and ballot.holder:
            candidates[ballot.holder]['holder'] += 1
        for i, candidate in enumerate(ballot.candidates):
            n = i + 1
            candidates[candidate][n] += 1
            max_rank = max(max_rank, n)

    ## Print header
    ranks = list(range(1, max_rank+1))
    if not args.holders:
        print("Candidate," + ",".join(map(str, ranks)))
    else:
        print("Candidate,holding," + ",".join(map(str, ranks)))
    for candidate in sorted(candidates.keys()):
        name = code_to_name(candidate)
        if not args.holders:
            print(f"{name}," + ",".join([str(candidates[candidate][x]) for x in ranks]))
        else:
            print(f"{name},{candidates[candidate]['holder']}," + ",".join([str(candidates[candidate][x]) for x in ranks]))

    return 0


def main(args):
    if args.func is None:
        print("Didn't find a handler")
        return 1

    return args.func(args)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
