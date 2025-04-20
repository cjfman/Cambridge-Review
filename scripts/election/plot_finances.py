#!/usr/bin/env python3

import argparse
import calendar
import datetime as dt
import random
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
        'month':        10,
        'start':        2713.18,
        'end':          350.57,
        'receipts':     350.57,
        'expenditures': 211.88,
    },
    {
        'month':        11,
        'start':        2851.87,
        'end':          2851.39,
        'receipts':     14.40,
        'expenditures': 14.88,
    },
    {
        'month':        12,
        'start':        2851.39,
        'receipts':     4402.92,
        'expenditures': 14.88,
        'end':          7239.43,
    },
    {
        'month':        1,
        'start':        7239.43,
        'receipts':     110.44,
        'expenditures': 164.81,
        'end':          7185.06,

    },
    {
        'month':        2,
        'start':        7185.06,
        'receipts':     110.45,
        'expenditures': 34.58,
        'end':          7260.93,
    },
    {
        'month':        3,
        'start':        7260.93,
        'receipts':     974.90,
        'expenditures': 14.88,
        'end':          8220.95,
    },
]


def parseArgs():
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--title", default='Finances')
    parser.add_argument("--out", required=True,
        help="Write to this file",
    )
    parser.add_argument("--months", type=int, default=3,
        help="How many months to include",
    )
    parser.add_argument("--dual", action="store_true",
        help="Use dual axes. Ignored unless --coh is set",
    )
    parser.add_argument("--coh", action="store_true",
        help="Show cash on hand line",
    )
    parser.add_argument("--copyright", default="Charles Jessup Franklin",
        help="The copyright holder")
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


def plot_expenses(args, reports):
    months = []
    recpts = []
    expncs = []
    cashes = []
    for report in reports:
        months.append(calendar.month_abbr[report['month']])
        recpts.append(report['receipts'])
        expncs.append(report['expenditures']*-1)
        cashes.append(report['end'])

    #fig = go.Figure()
    recpts_txts = ['${:,.2f}'.format(x) for x in recpts]
    expncs_txts = ['${:,.2f}'.format(x) for x in expncs]
    cashes_txts = ['${:,.2f}'.format(x) for x in cashes]
    fig = make_subplots(specs=[[{"secondary_y": args.dual}]])
    fig.add_trace(go.Bar(x=months, y=recpts, name="Receipts",    text=recpts_txts, textposition='auto'))
    fig.add_trace(go.Bar(x=months, y=expncs, name="Expenditure", text=expncs_txts, textposition='auto'))
    if args.coh:
        fig.add_trace(go.Scatter(
            x=months,
            y=cashes,
            name="Cash on Hand",
            text=cashes_txts,
            textposition="bottom center",
            mode="lines+markers+text",
        ), secondary_y=args.dual)
        #fig.add_trace(go.Scatter(x=months, y=cashes, name="Cash on Hand"), secondary_y=args.dual)

    min_val = min(expncs)
    fig.update_xaxes(title_text="Month")
    if args.dual and args.coh:
        fig.update_yaxes(title_text="Receipts/Expenditures", secondary_y=False)
        fig.update_yaxes(title_text="Cash on Hand",          secondary_y=True)
        y_fmt   = {'tickformat': "$,", 'range': [min_val, max(recpts)*1.2]}
        y_fmt_2 = {'tickformat': "$,", 'range': [min_val, max(cashes)*1.2]}
        fig.update_layout(yaxis=y_fmt, yaxis2=y_fmt_2)
    else:
        fig.update_yaxes(title_text="Amount (dollars)")
        fig.update_layout(yaxis_tickformat="$,")

    fig.update_layout(barmode='relative', title_text='Jivan Finances')
    if args.out is not None:
        plotly.offline.plot(fig, filename=args.out)
    else:
        fig.show()


def plot_months(args):
    now = dt.datetime.now()
    last_month_idx = (now.month - 1) % 12
    months = [calendar.month_abbr[(x % 12) + 1] for x in range(last_month_idx - args.months, last_month_idx)]
    gen_nums = lambda x, y, z: [random.randint(y, z) for _ in range(x)]
    x = months

    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=gen_nums(args.months, 0, 10), name="Receipts"))
    fig.add_trace(go.Bar(x=x, y=gen_nums(args.months, -10, 0), name="Expenditure"))
    fig.add_trace(go.Scatter(x=x, y=gen_nums(args.months, -10, 10), name="Cash on Hand"))

    fig.update_layout(barmode='relative', title_text='Relative Barmode')
    if args.out is not None:
        plotly.offline.plot(fig, filename=args.out)
    else:
        fig.show()


def finalPlot(args, fig):
    chart_file = args.lout
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
    plot_expenses(args, EXAMPLE_DATA)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
