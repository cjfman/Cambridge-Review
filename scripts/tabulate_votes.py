#! /usr/bin/python3.8
## pylint: disable=too-many-locals,too-many-branches,too-many-statements

import argparse
import json
import re
import sys

columns = ('uid', 'action', 'vote', 'charter_right')


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("final_actions",
        help="The file containing the final actions")

    return parser.parse_args()


def main(args):
    items = []
    item = None
    state = 'search'
    with open(args.final_actions, 'r', encoding='utf8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            try:
                ## Check for section header
                match = re.search(r"^[ivxlcdm]+\.\s", line, re.IGNORECASE)
                if match:
                    state = 'header'
                    print(f"Found section: {line}", file=sys.stderr)
                    if "COMMITTEE REPORTS" in line:
                        break

                    if item is not None:
                        items.append(item)
                        item = None
                    continue

                ## Check for agenda item description
                match = re.search(r"^\d+\.\s", line)
                if match:
                    print(f"Found agenda item description: {line[:20]}", file=sys.stderr)
                    state = 'description'
                    if item is not None:
                        items.append(item)
                        item = None
                    continue

                ## Check for item UID
                #match = re.match(r"CMA|APP|ORD|COM|RES|POR|COF \d+ #\d+", title)
                match = re.match(r"(?:CMA|APP|RES|POR) \d+ #\d+", line)
                if match:
                    print(f"Found agenda item ID: {line}", file=sys.stderr)
                    if item is not None:
                        items.append(item)

                    item = { 'uid': line }
                    state = 'item'
                    continue

                ## Stop if there is no item
                if item is None:
                    continue

                ## Check for result
                match = re.match(r"RESULT: (.+?)\s(\[\d-\d-\d(?:-\d)?\])", line)
                if match:
                    action, vote = match.groups()
                    item['action'] = action
                    item['vote']   = vote
                    print(f"Found result: action:{action} vote:{vote}", file=sys.stderr)
                    continue

                ## Check for charter right
                match = re.match(f"RESULT: CHARTER RIGHT EXERCISED BY (COUNCILLOR|VICE MAYOR|MAYOR) (.*) IN COUNCIL", line)
                if match:
                    name = match.groups()[0]
                    print(f"Charter righted by {name}", file=sys.stderr)
                    item['action'] = 'charter right'
                    item['charter_right'] = name
                    continue

                ## Check for other result
                match = re.match(f"RESULT: (.+)", line)
                if match:
                    result = match.groups()[0]
                    print(f"Found result: {result}", file=sys.stderr)
                    item['action'] = result

                ## Check for YEAS
                match = re.match(r"YEAS: (.+)", line)
                if match:
                    yeas = match.groups()[0].replace(", ", ",")
                    print(f"Found yeas: {yeas}", file=sys.stderr)
                    item['yeas'] = yeas
                    if yeas[-1] == ',':
                        state = 'yeas'
                    else:
                        state = 'search'

                    continue

                ## Check for NAYS
                match = re.match(r"NAYS: (.+)", line)
                if match:
                    nays = match.groups()[0].replace(", ", ",")
                    print(f"Found nays: {nays}", file=sys.stderr)
                    item['nays'] = nays
                    if nays[-1] == ',':
                        state = 'nays'
                    else:
                        state = 'search'

                    continue

                ## Check for PRESENT
                match = re.match(r"PRESENT: (.+)", line)
                if match:
                    present = match.groups()[0].replace(", ", ",")
                    print(f"Found present: {present}", file=sys.stderr)
                    item['present'] = present
                    if present[-1] == ',':
                        state = 'present'
                    else:
                        state = 'search'

                    continue

                ## Nothing matched. Must be a continuation of the previous state
                if state == 'yeas':
                    print(f"Found more yeas: {line}", file=sys.stderr)
                    item['yeas'] += line.replace(", ", ",")
                    if line[-1] != ',':
                        state = 'search'
                elif state == 'nays':
                    print(f"Found more nays: {line}", file=sys.stderr)
                    item['nays'] += line.replace(", ", ",")
                    if line[-1] != ',':
                        state = 'search'
                elif state == 'present':
                    print(f"Found more present: {line}", file=sys.stderr)
                    item['present'] += line.replace(", ", ",")
                    if line[-1] != ',':
                        state = 'search'

            except Exception as e:
                print(f"Error when processing line: {line}", file=sys.stderr)
                raise e

        ## Get the last item
        if item is not None:
            items.append(item)
            item = None

        for item in items:
            for key in columns:
                if key not in item:
                    item[key] = ""

    print(json.dumps(items, sort_keys=True, indent=4))
    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
