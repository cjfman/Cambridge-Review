#! /usr/bin/python3

import argparse
import csv
import re
import sys

from pathlib import Path

import glob

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib import elections


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file",
        help="Output file")
    parser.add_argument("--title", required=True,
        help="Title to give each election")
    parser.add_argument("--slug", required=True,
        help="Slug to give each election")
    parser.add_argument("election_files", nargs='+',
        help="Election files to be parsed")

    return parser.parse_args()


def main(args):
    paths = [path for raw_path in args.election_files for path in glob.glob(raw_path)]
    rows = [["title", "slug", "election_date", "counted_dates", "total", "quota"]]
    for path in paths:
        print(f"Opening '{path}'")
        elcn = elections.loadElectionsFile(path)
        match = re.search(r"(\d{4})", elcn.date)
        if not match:
            raise Exception("Election date doesn't have a year in it")

        year = match.groups()[0]
        title = args.title + " " + year
        slug = args.slug + "-" + year
        rows.append([title, slug, elcn.date, ", ".join(elcn.counted_on), elcn.total, elcn.quota])

    if args.output_file is not None:
        print(f"Writing to '{args.output_file}'")
        with open(args.output_file, 'w', encoding='utf8') as f:
            writer = csv.writer(f)
            writer.writerows(rows)
    else:
        writer = csv.writer(sys.stdout)
        writer.writerows(rows)

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
