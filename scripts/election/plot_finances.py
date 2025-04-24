#!/usr/bin/env python3

import argparse
import json
import re
import sys

from pathlib import Path

import plotly
import plotly.graph_objects as go

from plotly.subplots import make_subplots

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.filers import Report
from citylib.utils import insertCopyright, format_dollar

VERBOSE=False
DEBUG=False
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

    subparsers = parser.add_subparsers()

    ## Single filer CMD
    single_parser = subparsers.add_parser('single-filer',
        help="Create a chart for a single filer")
    single_parser.set_defaults(func=single_filer_hdlr)
    single_parser.add_argument("--title",
        help="Title of the chart. Default: 'Finances - <committeeName>'")
    single_parser.add_argument("--out", required=True,
        help="Write to this file")
    single_parser.add_argument("--in-file", required=True,
        help="JSON file of reports")
    single_parser.add_argument("--max-reports", type=int, default=6,
        help="Maximum number of reports to include")
    single_parser.add_argument("--dual", action="store_true",
        help="Use dual axes. Ignored unless --coh is set")
    single_parser.add_argument("--coh", action="store_true",
        help="Show cash on hand line")
    single_parser.add_argument("--copyright", default="Charles Jessup Franklin",
        help="The copyright holder")
    single_parser.add_argument("--copyright-tight", action="store_true",
        help="Put the copyright notice in the bottom right corner")
    single_parser.add_argument("--no-copyright", action="store_true",
        help="Don't set a copyright holder. Overrides --copyright")
    single_parser.add_argument("--font-size", type=int, default=14,
        help="Font size")
    single_parser.add_argument("--h-legend", action="store_true",
        help="Make the legend horizontal")

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
        reports = [Report.fromJson(x) for x in data['items']]
        reports.reverse()
        return reports
    except (KeyError, ValueError) as e:
        print(f"Reports file wasn't properly formatted: {e}")
        return None

    return reports


def plot_expenses(args, reports):
    title = args.title or f"Finances - {reports[0].committee_name}"
    stacks = []
    recpts = []
    expncs = []
    cashes = []
    for report in reports:
        stacks.append(report.reporting_period)
        recpts.append(report.credit_total)
        expncs.append(report.expenditure_total*-1)
        cashes.append(report.cash_on_hand)

    #fig = go.Figure()
    fig = make_subplots(specs=[[dict(secondary_y=args.dual)]])
    fig.add_trace(go.Bar(x=stacks, y=recpts, name="Credits",      text=[format_dollar(x) for x in recpts], textposition='auto'))
    fig.add_trace(go.Bar(x=stacks, y=expncs, name="Expenditures", text=[format_dollar(x) for x in expncs], textposition='auto'))
    if args.coh:
        fig.add_trace(go.Scatter(
            x=stacks,
            y=cashes,
            name="Cash on Hand",
            text=[format_dollar(x) for x in cashes],
            textposition="bottom center",
            mode="lines+markers+text",
        ), secondary_y=args.dual)
        #fig.add_trace(go.Scatter(x=stacks, y=cashes, name="Cash on Hand"), secondary_y=args.dual)

    min_val = min(expncs)
    fig.update_xaxes(title_text="Report Period")
    if args.dual and args.coh:
        fig.update_yaxes(title_text="Credits/Expenditures", secondary_y=False)
        fig.update_yaxes(title_text="Cash on Hand",          secondary_y=True)
        y_fmt   = dict(tickformat="$,", range=[min_val, max(recpts)*1.2])
        y_fmt_2 = dict(tickformat="$,", range=[min_val, max(cashes)*1.2])
        fig.update_layout(yaxis=y_fmt, yaxis2=y_fmt_2)
    else:
        fig.update_yaxes(title_text="Amount (dollars)")
        fig.update_layout(yaxis_tickformat="$,")

    title_info = dict(text=title, subtitle=dict(text=f"Cash on Hand: ${cashes[0]:,.2f}"))
    if not args.h_legend:
        fig.update_layout(barmode='relative', title=title_info, legend_title_text="Legend")
    else:
        fig.update_layout(barmode='relative', title=title_info, legend=dict(
            yanchor="bottom",
            xanchor="right",
            x=1,
            y=1,
            orientation="h",
        ))
    if args.out is not None:
        finalPlot(args, fig)
    else:
        fig.show()


def finalPlot(args, fig):
    chart_file = args.out
    font_size  = args.font_size
    fig.update_layout(font_size=font_size)
    if re.search(r"\.html$", chart_file, re.IGNORECASE):
        print(f"Saving as '{chart_file}'")
        plotly.offline.plot(fig, filename=chart_file)
        if args.copyright and not args.no_copyright:
            insertCopyright(chart_file, args.copyright, tight=args.copyright_tight, blocking=True)
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



def single_filer_hdlr(args):
    reports = read_reports(args.in_file)
    if reports is None:
        return 1

    plot_expenses(args, reports[:args.max_reports])
    return 0


def main(args):
    return args.func(args)


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
