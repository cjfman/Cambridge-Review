#!/usr/bin/env python3

import argparse
import csv
import os
import re
import requests
import sys

from pathlib import Path

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

## pylint: disable=import-error,wrong-import-order
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.utils import fetch_url
from citylib.utils import html_parsing as hp


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url",
        help="The base URL")
    parser.add_argument("first_page",
        help="The first page of the election data")
    parser.add_argument("out_file",
        help="The output CSV")

    return parser.parse_args()


def processFirstPage(page_path):
    fetched = fetch_url(page_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    tables = hp.findAllTags(soup, 'table')
    links = getPageLinks(tables[0])
    count = None
    candidates = None
    quota = None
    for text in hp.findAllText(soup, 'th'):
        if 'valid ballots' not in text:
            continue

        match = re.search(r"([,0-9]) valid ballots", text)
        if match:
            count = int(match.groups()[0].replace(',', ''))

        match = re.search(r"Electing (\d+) candidates", text)
        if match:
            candidates = int(match.groups()[0])

        match = re.search(r"Quota is (\d+) votes", text)
        if match:
            quota = int(match.groups()[0])

    return (count, candidates, quota, links)


def getCandidatesFromPage(node):
    candidates = {}
    for row in hp.findAllTags(node, 'tr'):
        if any(["CANDIDATE" in x for x in hp.findAllText(row, 'th')]):
            continue

        candidate = hp.findText(row, 'th')
        if any([(x in candidate) for x in ['EXHAUSTED', 'TOTALS']]):
            continue
        try:
            transfer, total, action = [x.text.strip() for x in hp.findAllTags(row, 'td')]
            candidates[candidate] = (int(transfer), int(total), action)
        except:
            continue

    return candidates


def getPageLinks(node):
    links = {}
    for link in hp.findAllTags(node, 'a'):
        val = link.text.strip()
        try:
            val = int(val)
        except:
            pass

        links[val] = link['href']

    return links


def processPage(page_path):
    fetched = fetch_url(page_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    tables = hp.findAllTags(soup, 'table')
    candidates = getCandidatesFromPage(tables[1])
    links = getPageLinks(tables[0])
    return candidates, links


def printCsv(out_path, rounds, first_page):
    candidates = list(rounds[0].keys())
    with open(out_path, 'w') as csvfile:
        writer = csv.writer(csvfile)
        header = ['Candidate']
        for i in range(len(rounds)):
            n = i + 1
            if n > 1:
                header.append(f"Transfer {n}")
            header.append(f"Count {n}")

        writer.writerow(header)
        for name in candidates:
            row = [name]
            for i in range(len(rounds)):
                transfer, total, action = rounds[i][name]
                if i > 0:
                    row.append(transfer)
                row.append(total)
            writer.writerow(row)

        count, candidates, quota, _ = first_page
        writer.writerow(['Total', count])
        writer.writerow(['Quota', quota])


def main(args):
    rounds = []
    first_page = processFirstPage(os.path.join(args.base_url, args.first_page))
    links = first_page[3]
    round_num = 1
    while round_num in links:
        print(f"Loading round {round_num}")
        round_n, links = processPage(os.path.join(args.base_url, links[round_num]))
        rounds.append(round_n)
        round_num += 1

    if 'Final' in links:
        print("Loading final round")
        round_n, links = processPage(os.path.join(args.base_url, links['Final']))
        rounds.append(round_n)
    else:
        print("No final round")

    printCsv(args.out_file, rounds, first_page)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
