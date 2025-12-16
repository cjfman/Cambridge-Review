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
from citylib.utils import insertCopyright

VERBOSE=False
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
COLOR_BLIND_FRIENDLY.reverse()
GREY = (68, 68, 68)


def parseArgs():
    parser = argparse.ArgumentParser()

    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("ballots_file",
        help="Ballot piles file")
    parser.add_argument("chart_file", nargs="?",
        help="Where to save the chart. If no extention is provided '.png' will be added.")

    args = parser.parse_args()

    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True

    return args


def main(args):
    print(f"Reading '{args.ballots_file}'")
    ballots = elections.loadFlattenedBallotPiles(args.ballots_file)
    labels = set() ## Label per candidate per side
    pairs = set() ## Pairs of source and targets
    transfers = defaultdict(lambda: defaultdict(int))
    label_names:Dict[str] = {}

    ## Sum the transfers
    for ballot in ballots:
        source = ballot[0]
        target = ballot[1] if len(ballot) > 1 else source
        transfers[source][target] += 1
        if target == "CAND_EXHAUSTED":
            continue

        ## Generate lables
        src_label = f"{source} - source"
        labels.add(src_label)
        label_names[src_label] = source
        dst_label = f"{target} - target"
        pairs.add((src_label, dst_label))
        labels.add(dst_label)
        label_names[dst_label] = target

    pairs  = sorted(pairs)
    labels = sorted(list(labels))
    label_map = { x: i for i, x in enumerate(labels) }
    sources = [label_map[x[0]] for x in pairs]
    targets = [label_map[x[1]] for x in pairs]
    values  = [transfers[label_names[x[0]]][label_names[x[1]]] for x in pairs]
    hovercolors = ['midnightblue', 'lightskyblue', 'gold', 'mediumturquoise', 'lightgreen', 'cyan']
    hovercolors *= len(pairs) // len(hovercolors)
    hovercolors += hovercolors[:len(pairs) % len(hovercolors)]
    out_text_map = { src: f"{src}<br><br>" + "<br>".join([f"{dst}: {val}" for dst, val in sorted(dsts.items())]) for src, dsts in transfers.items() }
    node_txt = [out_text_map[label_names[x]] for x in labels]

    fig = go.Figure(data=[go.Sankey(
        node={
            'pad':       15,
            'thickness': 20,
            'line':      dict(color='black', width=0.5),
            'label':     labels,
            'color':     'blue',
            'customdata': node_txt,
            'hovertemplate': '%{customdata}',
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
    if not args.chart_file:
        fig.show()
    else:
        print(f"Saving as '{args.chart_file}'")
        plotly.offline.plot(fig, filename=args.chart_file)

    return 0

if __name__ == '__main__':
    sys.exit(main(parseArgs()))
