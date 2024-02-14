#! /usr/bin/python3

import argparse
import csv
import datetime as dt
import sys

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--columns", required=True,
        help="The name of the columns to be converted, comma separated")
    parser.add_argument("input_file",
        help="The csv file with the dates to be converted")
    parser.add_argument("--in-format", default="%x",
        help="The date format of the input")
    parser.add_argument("--out-format", default="%Y-%m-%d",
        help="The date format of the output")
    parser.add_argument("output_file", nargs='?',
        help="The output csv file. Overwrite input file otherwise")

    return parser.parse_args()


def main(args):
    rows = None
    names = args.columns.split(",")
    if args.output_file is None:
        args.output_file = args.input_file

    with open(args.input_file, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        rows = [x for x in reader]

    if not rows:
        return 1

    missing = set(names).difference(set(rows[0].keys()))
    if missing:
        print("The following column names are invalid:")
        print("\t" + ",".join(missing))
        return 1

    for row in rows:
        for name in names:
            if name in row:
                row[name] = dt.datetime.strptime(row[name], args.in_format).strftime(args.out_format)

    with open(args.output_file, 'w', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    return 0

if __name__ == '__main__':
    sys.exit(main(parseArgs()))
