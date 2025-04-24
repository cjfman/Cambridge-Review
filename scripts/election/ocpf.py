#!/usr/bin/env python3

import argparse
import datetime as dt
import dateutil.relativedelta
import json
import re
import os
import sys
import time
import traceback

import requests

from pathlib import Path

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.utils import url_format_dt

VERBOSE=False
DEBUG=False
API_URL="https://api.ocpf.us/"
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

#https://api.ocpf.us/reports/reportList/17146?reportYear=0&baseReportTypeId=1&reportStartDate=10%2F1%2F2024&reportEndDate=4%2F1%2F2025&pagesize=50&startIndex=1&sortField=&sortDirection=DESC&withSummary=true
RECORD_TYPE = {
    "IndividualContribution":       201,
    "CommitteeContribution":        202,
    "UnionAssociationContribution": 203,
    "NonContributionReceipt":       204,
    "BankInterest":                 205,
    "CandidateLoan":                206,
    "TransferFromSavings":          207,
    "RegisteredPACs":               299,
    "AggregatedUnItemizedReceipts": 220,
    "IndividualInkindContribution": 401,
    "CommitteeInkindContribution":  402,
    "UnionInKindContribution":      403,
    "CandidateLoanForgiveness":     404,
    "UnitemizedInkindTotal":        420,
    "VoluntaryPayrollDeduction":    210,
}


def print_stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def parseArgs():
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.set_defaults(subcmd=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")

    subparsers = parser.add_subparsers()

    ## Fetch list subparser
    parser_fetch_list = subparsers.add_parser('fetch-list',
        help="Add rows to the google sheets"
    )
    parser_fetch_list.set_defaults(subcmd=fetch_list_hdlr)
    parser_fetch_list.add_argument('-o', '--out', type=str)

    ## Fetch filer subparser
    parser_fetch_filer = subparsers.add_parser('fetch-filer',
        help="Add rows to the google sheets"
    )
    parser_fetch_filer.set_defaults(subcmd=fetch_filer_hdlr)
    parser_fetch_filer.add_argument('-a', '--all', action='store_true',
        help="Get details on all filers. Requires --out")
    parser_fetch_filer.add_argument('-o', '--out',
        help="Output directory")
    parser_fetch_filer.add_argument('-r', '--ratelimit', type=float,
        help="Time to wait between fetches. Set to 0 to disable")
    parser_fetch_filer.add_argument('-m', '--max', type=int, default=10,
        help="The maximum number of filers to fetch. Set to 0 to fetch all of trhem")
    parser_fetch_filer.add_argument('--no-refetch', action='store_true',
        help="Don't fetch a filer that is already saved. Requires --out")
    parser_fetch_filer.add_argument('--keys',
        help="Dump these comma seperated keys to stdout")
    parser_fetch_filer.add_argument('filers', nargs='*', type=int,
        help="OCPF IDs to fetch specific filers. Overrides --all")

    ## Get reports
    parser_query_reports = subparsers.add_parser('query-reports',
        help="Query finalcial reports"
    )
    parser_query_reports.set_defaults(subcmd=query_reports_hdlr)
    parser_query_reports.add_argument('filer', type=int,
        help="OCPF ID to fetch reports of")
    parser_query_reports.add_argument('path',
        help="Save path")

    ## Final parse
    args = parser.parse_args()
    if args.subcmd is None:
        print_stderr("Must specify a subcmd")
        parser.print_help()
        sys.exit(1)

    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args


def fetch_json(url):
    content = requests.get(url, headers=REQUEST_HDR).content.decode('utf8')
    return json.loads(content)


def fetch_filers(url):
    url = os.path.join(url, "filers/listings/CC?first200=false&excludeClosed=true")
    print_stderr(f"Fetching '{url}'")
    filers = fetch_json(url)
    return [x for x in filers if x['officeSought'] == "City Councilor, Cambridge"]


def fetch_filer(cpfid, url):
    url = os.path.join(url, f"filer/payload/{cpfid}")
    print_stderr(f"Fetching '{url}'")
    filer = fetch_json(url)
    if 'raceActivityReports' in filer:
        del filer['raceActivityReports']

    return filer


def fetch_list_hdlr(args):
    ## Get the list of filers
    filers = fetch_filers(API_URL)
    if args.out is not None:
        with open(args.out, 'w', encoding='utf8') as f:
            json.dump(filers, f, indent=4)
    else:
        print(json.dumps(filers, indent=4))

    return 0


def known_cfids(path):
    cfids = []
    for name in os.listdir(path):
        match = re.match(r"(\d+).json", name)
        if match:
            cfids.append(int(match.groups()[0]))

    return cfids

def fetch_filer_args_ok(args):
    if args.all and (args.out is None or not os.path.isdir(args.out)):
        print_stderr("--all requires a directory to be specificed by --out")
        return False

    if not args.all and not args.filers:
        print_stderr("Must either pass --all or specify cpf IDs")
        return False

    if args.no_refetch and not args.out:
        print_stderr("--no-refetch requires --out")
        return False

    return True


def format_filer_keys(filer, keys):
    return "\n".join(f"{x}: {filer[x]}" for x in keys)


def fetch_and_store_filer(cpfid, *, out=None, keys=None, fetched=None):
    filer = fetch_filer(cpfid, API_URL)
    msg = None
    if keys:
        msg = format_filer_keys(filer['filer'], keys)
    if out:
        with open(os.path.join(out, f"{cpfid}.json"), 'w', encoding='utf8') as f:
            json.dump(filer, f, indent=4)
    elif not keys:
        msg = json.dumps(filer, indent=4)

    if msg:
        if fetched:
            print("---")

        print(msg)

    return filer


def fetch_filer_hdlr(args):
    if not fetch_filer_args_ok(args):
        return 1

    ## Get the list of filers
    cpfids = args.filers
    if not cpfids and args.all:
        ## Fetch them from OCPF
        cpfids = [x['cpfId'] for x in fetch_filers(API_URL)]

    keys = []
    if args.keys is not None:
        keys = args.keys.split(',')

    ignore = []
    if args.no_refetch:
        ignore = known_cfids(args.out)

    ## Get the full details on every filer
    fetching = len(cpfids) - len(ignore)
    print_stderr(f"Fetching {fetching} filers")
    if ignore:
        print_stderr(f"Not refetching {len(ignore)} filers")

    fetched = 0
    for cpfid in cpfids:
        if cpfid in ignore:
            print_stderr(f"Skipping {cpfid}")
            continue

        try:
            fetch_and_store_filer(cpfid, out=args.out, keys=keys, fetched=fetched)
        except Exception as e:
            print(f"Got error while fetching cpfid {cpfid}: {e}")
            traceback.print_exc()

        ## Rate limit
        if args.ratelimit:
            time.sleep(args.ratelimit)

        fetched += 1
        if args.max and fetched >= args.max:
            break

    return 0


def format_report_query_url(cpfid, start:dt.datetime, end:dt.datetime):

    return "https://api.ocpf.us/reports/reportList/{cpfid}?reportYear=0&baseReportTypeId=1&reportStartDate={start}&reportEndDate={end}&pagesize=50&startIndex=1&sortField=&sortDirection=DESC&withSummary=true".format(
        cpfid=cpfid,
        start=url_format_dt(start),
        end=url_format_dt(end),
    )

def query_reports_hdlr(args):
    now = dt.datetime.now()
    then = now - dateutil.relativedelta.relativedelta(months=6)
    url = format_report_query_url(args.filer, then, now)
    print_stderr(f"Fetching {url}")
    reports = fetch_json(url)
    with open(args.path, 'w', encoding='utf8') as f:
        print_stderr(f"Writting to {args.path}")
        json.dump(reports, f, indent=4)

    return 0


def main(args):
    return args.subcmd(args)


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
