#!/usr/bin/env python3

import argparse
import json
import re
import os
import sys
import time

import requests

VERBOSE=False
DEBUG=False
BASE_URL="https://www.ocpf.us/FilerData/"
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
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
    parser_fetch_filer.add_argument('filers', nargs='*', type=int,
        help="OCPF IDs to fetch specific filers. Overrides --all")


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
    url = os.path.join(url, "GetFilerListings?category=CC&filter=&showClosed=false")
    print_stderr(f"Fetching '{url}'")
    filers = fetch_json(url)
    return [x for x in filers if x['officeDistrictSought'] == "City Councilor, Cambridge"]


def fetch_filer(cpfid, url):
    url = os.path.join(url, f"GetFiler?cpfId={cpfid}")
    print_stderr(f"Fetching '{url}'")
    return fetch_json(url)


def fetch_list_hdlr(args):
    ## Get the list of filers
    filers = fetch_filers(BASE_URL)
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

def fetch_filer_hdlr(args):
    if not fetch_filer_args_ok(args):
        return 1

    ## Get the list of filers
    cpfids = args.filers
    if not cpfids and args.all:
        ## Fetch them from OCPF
        cpfids = [x['cpfId'] for x in fetch_filers(BASE_URL)]

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

        filer = fetch_filer(cpfid, BASE_URL)
        if args.out:
            with open(os.path.join(args.out, f"{cpfid}.json"), 'w', encoding='utf8') as f:
                json.dump(filer, f, indent=4)
        else:
            if fetched:
                print("---")

            print(json.dumps(filer, indent=4))

        ## Rate limit
        if args.ratelimit:
            time.sleep(args.ratelimit)

        fetched += 1
        if args.max and fetched >= args.max:
            break

    return 0


def main(args):
    return args.subcmd(args)


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
