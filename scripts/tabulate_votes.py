#! /usr/bin/python3.8
## pylint: disable=too-many-locals,too-many-branches,too-many-statements

import argparse
import json
import re
import sys

from councillors import getCouncillorNames, setCouncillorInfo
from utils import print_red, toTitleCase

columns = ('uid', 'action', 'vote', 'charter_right', 'amended')


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--councillor-info",
        help="File with councillor info")
    parser.add_argument("--session", type=int,
        help="The session year. Defaults to most recent one found in councillor info file")
    parser.add_argument("final_actions",
        help="The file containing the final actions")

    return parser.parse_args()


def processResult(line, item):
    ## Check for voice vote
    match = re.match(r"(.+?)\s+by voice vote", line, re.IGNORECASE)
    if match:
        item['action'] = toTitleCase(match.groups()[0])
        item['vote'] = "Voice Vote"
        print(f"Found result: action:'{item['action']}' by voice vote", file=sys.stderr)
        return 'search'

    ## Check for charter right
    match = re.search(f"^charter right\s?(?:exercised|excersied) by (?:councillor|councollor||vice mayor|mayor) (?:(.+)(?: in council.*)?)", line, re.IGNORECASE)
    if match:
        name = match.groups()[0].replace(" IN COUNCIL", "").lower()
        print(f"Charter righted by {name}", file=sys.stderr)
        item['action'] = 'Charter Right'
        item['charter_right'] = name
        return 'search'

    ## Check for vote count
    match = re.match(r"(.+?)\s\[?((?:\d-\d-\d(?:-\d)?)|(?:\d+ to \d+)|Unanimous)\]?", line, re.IGNORECASE)
    if match:
        action, vote = match.groups()
        item['action'] = toTitleCase(action)
        item['vote']   = vote.lower()
        print(f"Found result: action:{action} vote:{vote}", file=sys.stderr)
        return 'search'

    ## Check again
    match = re.match(r"\[?((?:\d-\d-\d(?:-\d)?)|(?:\d+ to \d+)|Unanimous)\]?", line, re.IGNORECASE)
    if match:
        item['vote'] = match.groups()[0]
        print(f"Found result: vote:{item['vote']}", file=sys.stderr)
        return 'result'

    ## No match. Append line to action
    if 'action' not in item:
        item['action'] = toTitleCase(line)
    else:
        item['action'] += "\n" + toTitleCase(line)

    return 'result'


def processCouncillors(line, item, key, *, valid_names=None):
    ## Make sure this line contains some councilors
    if valid_names is not None:
        lline = line.lower()
        if not any([x in lline for x in valid_names]):
            return 'search'

    ## Process names
    print(f"Found {key}: {line}", file=sys.stderr)
    councilors = line.replace(", ", ",")
    if key not in item:
        item[key] = councilors
    else:
        item[key] += ' ' + councilors

    return key


def postProcess(items):
    for item in items:
        action = re.sub(r"^Order\s+", "", item['action'])

        ## Check for voice vote
        match = re.match(f"^(.*) (?:by|on) (?:an |am )?(?:Affirmative|Voice) Vote of (\w+) (?:Memebers|Members|Councillors)", action, re.IGNORECASE)
        if match:
            action = match.groups()[0]
            item['vote'] = "Voice Vote"

        ## Check for as amended
        if 'as amended' in action.lower():
            rr = re.compile(r"\s+as amended(?:\s+.*)?", re.IGNORECASE)
            action = rr.sub("", action)
            item['amended'] = 'Yes'
        elif action.lower() == "failed of adoption":
            action = "Failed"
        elif "no action taken" in action.lower():
            action = "No Action Taken"

        item['action'] = action

    return items


def tabulateVotes(lines, *, valid_names=None):
    items = []
    item = None
    state = 'search'
    for line in lines:
        #print(f"State: {state}", file=sys.stderr)
        line = line.strip()
        if not line:
            if state != 'search':
                print(f"Reset state", file=sys.stderr)

            state = 'search'
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
            match = re.match(r"^(?:CMA|APP|RES|POR) \d+ #\d+$", line)
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
            match = re.match(r"RESULT:\s*(.*)", line)
            if match:
                print("Start result", file=sys.stderr)
                msg = match.groups()[0]
                state = 'result'
                if msg:
                    line = msg
                else:
                    continue

            ## Check for YEAS, NAYS, PRESENT
            match = re.match(r"(YEAS|NAYS|PRESENT|RECUSED):\s*(.*)", line)
            if match:
                key, msg = match.groups()
                key = key.lower()
                if key in item:
                    print(f"Found a repeated {key} for item {item['uid']}. Dropping item", file=sys.stderr)
                    item = None
                    state = 'search'
                    continue

                print(f"Start {key}", file=sys.stderr)
                state = key
                if msg:
                    line = msg
                else:
                    continue

            ## Nothing matched. Must be a continuation of the previous state
            if state == 'result':
                state = processResult(line, item)
            elif state == 'yeas':
                state = processCouncillors(line, item, 'yeas', valid_names=valid_names)
            elif state == 'nays':
                state = processCouncillors(line, item, 'nays', valid_names=valid_names)
            elif state == 'present':
                state = processCouncillors(line, item, 'present', valid_names=valid_names)
            elif state == 'recused':
                state = processCouncillors(line, item, 'recused', valid_names=valid_names)

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

    print(json.dumps(postProcess(items), sort_keys=True, indent=4))


def main(args):
    ## Set councillor info
    if args.councillor_info is not None:
        if not setCouncillorInfo(args.councillor_info, args.session):
            print_red(f"Failed to set up councillor info", file=sys.stderr)
            return 1

    with open(args.final_actions, 'r', encoding='utf8') as f:
        if args.councillor_info is not None:
            tabulateVotes(f, valid_names=getCouncillorNames(include_aliases=True))
        else:
            tabulateVotes(f)

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
