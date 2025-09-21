#!/usr/bin/env python3

import argparse
import json
import re
import sys

from collections import defaultdict
from pathlib import Path

import plotly
import plotly.graph_objects as go

from plotly.subplots import make_subplots

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib import utils
from citylib.filers import Contribution, Filer, Report, read_reports, read_report_and_filer, sum_contributions
from citylib.utils import insertCopyright, format_dollar

VERBOSE=False
DEBUG=False

def parseArgs():
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")

    ## Shared arguments
    shared_parser = argparse.ArgumentParser(description="The shared parser")
    shared_parser.add_argument("--out", required=False,
        help="Write to this file")
    shared_parser.add_argument("--dual", action="store_true",
        help="Use dual axes. Ignored unless --coh is set")
    shared_parser.add_argument("--coh", action="store_true",
        help="Show cash on hand line")
    shared_parser.add_argument("--copyright", default="Charles Jessup Franklin",
        help="The copyright holder")
    shared_parser.add_argument("--copyright-tight", action="store_true",
        help="Put the copyright notice in the bottom right corner")
    shared_parser.add_argument("--no-copyright", action="store_true",
        help="Don't set a copyright holder. Overrides --copyright")
    shared_parser.add_argument("--font-size", type=int, default=14,
        help="Font size")
    shared_parser.add_argument("--scale", type=int, default=1,
        help="Scale used when saving images")
    shared_parser.add_argument("--h-legend", action="store_true",
        help="Make the legend horizontal")

    ## Subparsers
    subparsers = parser.add_subparsers()

    ## Single filer CMD
    single_parser = subparsers.add_parser('single-filer', parents=[shared_parser], add_help=False,
        help="Create a chart for a single filer")
    single_parser.set_defaults(func=single_filer_hdlr)
    single_parser.add_argument("--title",
        help="Title of the chart. Default: 'Finances - <committeeName>'")
    single_parser.add_argument("--in-file", required=True,
        help="JSON file of reports")
    single_parser.add_argument("--max-reports", type=int, default=6,
        help="Maximum number of reports to include")

    ## Many filers CMD
    many_parser = subparsers.add_parser('many-filers', parents=[shared_parser], add_help=False,
        help="Create a chart for a many filer")
    many_parser.set_defaults(func=many_filer_hdlr)
    many_parser.add_argument("--title",
         help="Title of the chart. Default: Finances <REPORT PERIOD>")
    many_parser.add_argument("reports", nargs='+',
        help="Filer report files")

    ## Contributions CMD
    contributions_parser = subparsers.add_parser('contributions', parents=[shared_parser], add_help=False,
        help="Create a chart for a contributions filer")
    contributions_parser.set_defaults(func=contributions_hdlr)
    contributions_parser.add_argument("--title",
          help="Title of the chart. Defautt: Contributions <REPORT PERIOD>")
    contributions_parser.add_argument("--subtitle",
        help="Subtitle of the chart")
    contributions_parser.add_argument("contributions", nargs='+',
        help="Contribution files")

    ## Final parse
    args = parser.parse_args()
    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args


def plot_expenses(args, title, stacks, recpts, expncs, *, cashes=None, subtitle=None, x_title="Category"):
    #fig = go.Figure()
    fig = make_subplots(specs=[[dict(secondary_y=args.dual)]])
    fig.add_trace(go.Bar(x=stacks, y=recpts, name="Credits",      text=[format_dollar(x) for x in recpts], textposition='auto'))
    fig.add_trace(go.Bar(x=stacks, y=expncs, name="Expenditures", text=[format_dollar(x) for x in expncs], textposition='auto'))
    if args.coh and cashes:
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
    fig.update_xaxes(title_text=x_title)
    if args.dual and args.coh and cashes:
        fig.update_yaxes(title_text="Credits/Expenditures", secondary_y=False)
        fig.update_yaxes(title_text="Cash on Hand",          secondary_y=True)
        y_fmt   = dict(tickformat="$,", range=[min_val, max(recpts)*1.2])
        y_fmt_2 = dict(tickformat="$,", range=[min_val, max(cashes)*1.2])
        fig.update_layout(yaxis=y_fmt, yaxis2=y_fmt_2)
    else:
        fig.update_yaxes(title_text="Amount (dollars)")
        fig.update_layout(yaxis_tickformat="$,")

    ## Title info
    title_info = { 'text': title }
    if subtitle is not None:
        title_info['subtitle'] = { 'text': subtitle }

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


def plot_coh(args, title, names, cashes, *, subtitle=None, x_title="Category"):
    #fig = go.Figure()
    fig = make_subplots(specs=[[dict(secondary_y=args.dual)]])
    fig.add_trace(go.Bar(x=names, y=cashes, name="Cash on Hand", text=[format_dollar(x) for x in cashes], textposition='auto'))

    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text="Amount (dollars)")
    fig.update_layout(yaxis_tickformat="$,")

    ## Title info
    title_info = { 'text': title }
    if subtitle is not None:
        title_info['subtitle'] = { 'text': subtitle }

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

        fig.write_image(chart_file, scale=args.scale)


def plot_filer_expenses(args, reports):
    title = args.title or f"Finances - {reports[0].committee_name}"
    stacks = []
    recpts = []
    expncs = []
    cashes = []
    for report in reversed(reports):
        stacks.append(report.reporting_period)
        recpts.append(report.credit_total)
        expncs.append(report.expenditure_total*-1)
        cashes.append(report.cash_on_hand)

    plot_expenses(args, title, stacks, recpts, expncs, subtitle=f"Cash on Hand: ${cashes[-1]:,.2f}", cashes=cashes, x_title="Report Period")


def plot_filers_last_report(args, filers):
    stacks = []
    recpts = []
    expncs = []
    cashes = []
    for filer in sorted(filers, key=lambda x: x.committee_name):
        stacks.append(filer.committee_name)
        recpts.append(filer.reports[0].credit_total)
        expncs.append(filer.reports[0].expenditure_total*-1)
        cashes.append(filer.reports[0].cash_on_hand)

    if args.coh:
        title = args.title or f"Cash on Hand as of {filers[0].reports[0].end_date.strftime('%-m/%-d/%Y')}"
        plot_coh(args, title, stacks, cashes, x_title="Committe")
        return

    title = args.title or f"Finances for period {filers[0].reports[0].reporting_period}"
    print(title)
    plot_expenses(args, title, stacks, recpts, expncs, x_title="Committe")


def single_filer_hdlr(args):
    reports = read_reports(args.in_file)
    if reports is None:
        return 1

    if not reports:
        print("No reports were found")
        return 1

    plot_filer_expenses(args, reports[:args.max_reports])
    return 0


def many_filer_hdlr(args):
    ## Load filers and their reports
    filers = [x for x in map(read_report_and_filer, args.reports) if x is not None and x.active()]
    if not filers:
        return 1

    ## Group filers by most recent report period
    grouped = defaultdict(list)
    for filer in filers:
        key = (filer.reports[0].end_date, filer.reports[0].start_date)
        grouped[key].append(filer)
    if len(grouped.keys()) > 1:
        key = sorted(grouped.keys())[-1]
        date_txt = " ".join([x.strftime('%-m/%-d/%Y') for x in key])
        print(f"Most recent report for all filers isn't the same. Choosing the most recent one: {date_txt}")
        filers = grouped[key]
        print("\n".join(map(str, filers)))

    plot_filers_last_report(args, filers)
    return 0


def contributions_hdlr(args):
    ## Build filers
    filers = {}
    all_contributions = []
    for path in args.contributions:
        data = utils.load_json(path)
        if 'filerFullName' not in data['summary']:
            if args.verbose:
                print(f"File '{path}' doesn't have a candidate name. Skipping")
            continue

        name = data['summary']['filerFullName']
        contributions = list(map(Contribution.fromJson, data['items']))
        all_contributions.extend(contributions)
        summed = sum_contributions(contributions=contributions)
        if summed:
            filers[name] = summed
            if args.verbose:
                print(f"Candidate {name}: {summed}")
        elif args.verbose:
            print(f"Candidate {name} has no contributions. Skipping")

    if not filers:
        print("No contributions were found")
        return 1

    ## Start chart
    in_city  = []
    in_state = []
    totals   = []
    names    = list(sorted(filers.keys()))
    for name in names:
        city, state, total = filers[name]
        in_city.append(city)
        in_state.append(state)
        totals.append(total)

    ## Calculate percentages
    in_city_prc  = [x*100//y for x, y in zip(in_city, totals)]
    in_state_prc = [x*100//y for x, y in zip(in_state, totals)]

    ## Make chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names,
        y=in_city,
        name='Cambridge',
        marker_color='#6C8EBF',
        customdata=[[x] for x in in_city_prc],
        hovertemplate="%{x} %{y} (%{customdata[0]}%)",
    ))
    fig.add_trace(go.Bar(
        x=names,
        y=in_state,
        name='Massachusetts',
        marker_color='orange',
        customdata=[[x] for x in in_state_prc],
        hovertemplate="%{x} %{y} (%{customdata[0]}%)",
    ))
    fig.add_trace(go.Bar(
        x=names,
        y=in_state,
        name='Total',
        marker_color='red',
        hovertemplate="%{x} %{y}",
    ))

    ## Make subtitle
    if args.title is None:
        dates = sorted([x.date for x in all_contributions])
        start = utils.simpleFormatDateTime(dates[0], date_only=True)
        end = utils.simpleFormatDateTime(dates[-1], date_only=True)
        args.title = f"Contributions from {start} to {end}"

    ## Finalize plot
    title_info = { 'text': args.title }

    fig.update_yaxes(title_text="Amount (dollars)")
    fig.update_xaxes(title_text="Candidate")
    fig.update_layout(barmode='group', xaxis_tickangle=-45, title=title_info, yaxis=dict(tickformat="$,"))
    if args.out is not None:
        finalPlot(args, fig)
    else:
        fig.show()

    return 0


def main(args):
    return args.func(args)


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
