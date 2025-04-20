#!/usr/bin/env python3

import argparse
import calendar
import datetime as dt
import random
import sys

import plotly
import plotly.graph_objects as go

from plotly.subplots import make_subplots

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
    parser.add_argument("--out", required=True)
    parser.add_argument("--months", type=int, default=3)
    parser.add_argument("--dual", action="store_true")

#    subparsers = parser.add_subparsers()
#
#    ## Add cmd
#    add_parser = subparsers.add_parser('add',
#        help="Add rows to the google sheets"
#    )
#    add_parser.set_defaults(func=add_hdlr)

    ## Final parse
    args = parser.parse_args()
#    if args.subcmd is None:
#        print("Must specify a subcmd")
#        parser.print_help()
#        sys.exit(1)

    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args


#def add_hdlr(args):
#    return 0


def plot_jivan(args):
    months = []
    recpts = []
    expnds = []
    cashes = []
    for report in EXAMPLE_DATA:
        months.append(calendar.month_abbr[report['month']])
        recpts.append(report['receipts'])
        expnds.append(report['expenditures']*-1)
        cashes.append(report['end'])

    #fig = go.Figure()
    fig = make_subplots(specs=[[{"secondary_y": args.dual}]])
    fig.add_trace(go.Bar(x=months,     y=recpts, name="Receipts"))
    fig.add_trace(go.Bar(x=months,     y=expnds, name="Expenditure"))
    fig.add_trace(go.Scatter(x=months, y=cashes, name="Cash on Hand"), secondary_y=args.dual)
    min_val = min(expnds)

    fig.update_xaxes(title_text="Month")
    if args.dual:
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


def plot_exp(args):
    x = [1, 2, 3, 4]

    fig = go.Figure()
    fig.add_trace(go.Bar(x=x, y=[1, 4, 9, 16]))
    fig.add_trace(go.Bar(x=x, y=[6, -8, -4.5, 8]))
    fig.add_trace(go.Bar(x=x, y=[-15, -3, 4.5, -8]))
    fig.add_trace(go.Bar(x=x, y=[-1, 3, -3, -4]))

    fig.update_layout(barmode='relative', title_text='Relative Barmode')
    if args.out is not None:
        plotly.offline.plot(fig, filename=args.out)
    else:
        fig.show()


def main(args):
    #return args.subcmd(args)
    plot_jivan(args)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
