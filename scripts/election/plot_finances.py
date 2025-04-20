#!/usr/bin/env python3

import argparse
import datetime as dt
import json
import re
import sys

from pathlib import Path

import plotly
import plotly.graph_objects as go

from plotly.subplots import make_subplots

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.utils import insertCopyright

VERBOSE=False
DEBUG=False

EXAMPLE_DATA = [
    {
        'reportingPeriod':  "10/1/2024 - 10/31/2024",
        'startBalance':     2713.18,
        'endBalance':       350.57,
        'creditTotal':      350.57,
        'expenditureTotal': 211.88,
    },
    {
        'reportingPeriod':  "11/1/2024 - 11/30/2024",
        'startBalance':     2851.87,
        'endBalance':       2851.39,
        'creditTotal':      14.40,
        'expenditureTotal': 14.88,
    },
    {
        'reportingPeriod':  "12/1/2024 - 12/31/2024",
        'startBalance':     2851.39,
        'creditTotal':      4402.92,
        'expenditureTotal': 14.88,
        'endBalance':       7239.43,
    },
    {
        'reportingPeriod':  "1/1/2025 - 1/31/2025",
        'startBalance':     7239.43,
        'creditTotal':      110.44,
        'expenditureTotal': 164.81,
        'endBalance':       7185.06,

    },
    {
        'reportingPeriod':  "2/1/2025 - 2/28/2025",
        'startBalance':     7185.06,
        'creditTotal':      110.45,
        'expenditureTotal': 34.58,
        'endBalance':       7260.93,
    },
    {
        'reportingPeriod':  "3/1/2025 - 3/31/2025",
        'startBalance':     7260.93,
        'creditTotal':      974.90,
        'expenditureTotal': 14.88,
        'endBalance':       8220.95,
    },
]

CURRENCY_KEYS = (
    'startBalance',
    'creditTotal',
    'expenditureTotal',
    'endBalance',
    'cashOnHand',
)


def parseArgs():
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--title",
        help="Title of the chart. Default: 'Finances - <committeeName>'")
    parser.add_argument("--out", required=True,
        help="Write to this file")
    parser.add_argument("--in-file", required=True,
        help="JSON file of reports")
    parser.add_argument("--max-reports", type=int, default=6,
        help="Maximum number of reports to include")
    parser.add_argument("--dual", action="store_true",
        help="Use dual axes. Ignored unless --coh is set")
    parser.add_argument("--coh", action="store_true",
        help="Show cash on hand line")
    parser.add_argument("--copyright", default="Charles Jessup Franklin",
        help="The copyright holder")
    parser.add_argument("--copyright-tight", action="store_true",
        help="Put the copyright notice in the bottom right corner")
    parser.add_argument("--no-copyright", action="store_true",
        help="Don't set a copyright holder. Overrides --copyright")

    ## Final parse
    args = parser.parse_args()
    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args


def read_reports(path):
    print(f"Opening reports file '{path}'")
    data = None
    try:
        with open(path, encoding='utf8') as f:
            data = json.load(f)
    except OSError as e:
        print(f"Failed to open reports file '{path}': {e}")
        return None

    try:
        reports = data['items']
        for report in reports:
            for key in CURRENCY_KEYS:
                report[key] = float(report[key][1:].replace(',', ''))
        return reports
    except KeyError as e:
        print(f"Reports file wasn't properly formatted: {e}")
        return None


def plot_expenses(args, reports):
    title = args.title or f"Finances - {reports[0]['committeeName']}"
    stacks = []
    recpts = []
    expncs = []
    cashes = []
    for report in reports:
        stacks.append(report['reportingPeriod'])
        recpts.append(report['creditTotal'])
        expncs.append(report['expenditureTotal']*-1)
        cashes.append(report['cashOnHand'])

    #fig = go.Figure()
    recpts_txts = ['${:,.2f}'.format(x) for x in recpts]
    expncs_txts = ['${:,.2f}'.format(x) for x in expncs]
    cashes_txts = ['${:,.2f}'.format(x) for x in cashes]
    fig = make_subplots(specs=[[{"secondary_y": args.dual}]])
    fig.add_trace(go.Bar(x=stacks, y=recpts, name="Receipts",    text=recpts_txts, textposition='auto'))
    fig.add_trace(go.Bar(x=stacks, y=expncs, name="Expenditure", text=expncs_txts, textposition='auto'))
    if args.coh:
        fig.add_trace(go.Scatter(
            x=stacks,
            y=cashes,
            name="Cash on Hand",
            text=cashes_txts,
            textposition="bottom center",
            mode="lines+markers+text",
        ), secondary_y=args.dual)
        #fig.add_trace(go.Scatter(x=stacks, y=cashes, name="Cash on Hand"), secondary_y=args.dual)

    min_val = min(expncs)
    fig.update_xaxes(title_text="Report Period")
    if args.dual and args.coh:
        fig.update_yaxes(title_text="Receipts/Expenditures", secondary_y=False)
        fig.update_yaxes(title_text="Cash on Hand",          secondary_y=True)
        y_fmt   = {'tickformat': "$,", 'range': [min_val, max(recpts)*1.2]}
        y_fmt_2 = {'tickformat': "$,", 'range': [min_val, max(cashes)*1.2]}
        fig.update_layout(yaxis=y_fmt, yaxis2=y_fmt_2)
    else:
        fig.update_yaxes(title_text="Amount (dollars)")
        fig.update_layout(yaxis_tickformat="$,")

    fig.update_layout(barmode='relative', title_text=title)
    if args.out is not None:
        finalPlot(args, fig)
    else:
        fig.show()


def finalPlot(args, fig):
    chart_file = args.out
    if re.search(r"\.html$", chart_file, re.IGNORECASE):
        print(f"Saving as '{chart_file}'")
        plotly.offline.plot(fig, filename=chart_file)
        if args.copyright and not args.no_copyright:
            insertCopyright(chart_file, args.copyright, tight=args.copyright_tight)
    elif re.search(r"\.svg$", chart_file, re.IGNORECASE):
        ## Write an svg file
        print(f"Saving as '{chart_file}'")
        fig.write_image(chart_file)
    else:
        ## Write something else, png if not specified
        if '.' not in chart_file:
            chart_file += ".png"
            print(f"Saving as png '{chart_file}'")
        else:
            print(f"Saving as '{chart_file}'")

        fig.write_image(chart_file)


def main(args):
    plot_expenses(args, read_reports(args.in_file)[:args.max_reports])
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
