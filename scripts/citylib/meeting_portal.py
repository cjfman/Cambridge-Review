## pylint: disable=too-many-branches,too-many-locals
import json
import re

from collections import defaultdict
from typing import Dict, List, Tuple

import citylib.utils.html_parsing as hp

from citylib import agenda
from citylib.councillors import getCouncillorNames, lookUpCouncillorName
from citylib.utils import setDefaultValue, toTitleCase, overlayKeys


def findCouncillorsInRow(row):
    councillors = hp.findText(hp.findAllTags(row, 'td')[1]).split(',')
    return [lookUpCouncillorName(x.strip()) for x in councillors]


def processHistory(history_table):
    history = {}
    ## Look for a vote record
    for results_table in hp.findAllTags(history_table, 'table', 'VoteRecord'):
        rows = hp.findAllTags(results_table, 'tr')
        if not rows:
            continue
        for row in rows:
            role = hp.findText(row, 'td', 'Role')
            if not role:
                continue

            ## Check for the type of vote
            role = role.lower().replace(':', '')
            if role == "result":
                result = hp.findText(row, 'td', 'Result').lower()
                if result == "charter right":
                    ## Found a charter right
                    history['charter_right'] = True
                else:
                    ## Try and parse an action
                    action, vote = agenda.parseAction(result)
                    if action is not None:
                        history['action'] = action.strip()
                        history['vote']   = vote.strip()
            elif role in ('yeas', 'nays', 'present', 'absent', 'recused'):
                history[role] = findCouncillorsInRow(row)

    if not history:
        ## Look for affirmative vote
        txt = hp.findText(history_table, 'p').lower()
        if 'affirmative' in txt:
            history['vote'] = "Affirmative Vote"
        elif 'voice' in txt:
            history['vote'] = "Voice Vote"

    if history:
        ## Set default values
        setDefaultValue(history, "", ('action', 'vote', 'charter_right', 'amended'))
        setDefaultValue(history, list, ('yeas', 'nays', 'recused', 'present', 'absent'))

        ## Check action
        if history['action']:
            ## Check for amended
            match = re.match(r"(.+) as amended", history['action'], re.IGNORECASE)
            if match:
                history['action'] = match.groups()[0]
                history['amended'] = 'yes'

            ## Other actions
            history['action'] = agenda.extractAction(history['action'])

        ## Set absence
        if history['yeas']:
            all_councillors = set(getCouncillorNames())
            councillors = set(history['yeas'] + history['nays'] + history['present'])
            history['absent'] = list(sorted(all_councillors.difference(councillors)))

    return history


def processFinalActions(path):
    final_actions = None
    print(f"Opening final actions file '{path}'")
    with open(path, 'r', encoding='utf8') as f:
        final_actions = json.load(f)

    regrouped = {}
    items = {}
    required = (
        'action', 'charter_right', 'uid', 'vote', 'yeas', 'nays',
        'present', 'absent', 'recused',
    )
    all_councillors = set(getCouncillorNames())
    for uid, actions in final_actions.items():
        meeting = {}
        regrouped[uid] = meeting
        for action in actions:
            action_uid = action['uid']
            meeting[action_uid] = action

            ## Update action text
            match = re.match(r"(?:Order )?(.*) by (?:the|an?) ((?:Affirmative|Voice) Vote) of \w+ Members", action['action'], re.IGNORECASE)
            if match:
                action_txt, vote = match.groups()
                action['action'] = toTitleCase(action_txt)
                action['vote'] = toTitleCase(vote)
            if match is None:
                match = re.match(r"(?:Order )?(.*) \w+ Members", action['action'], re.IGNORECASE)
                if match:
                    action['action'] = toTitleCase(match.groups()[0])
                    action['vote'] = "Voice Vote"
            if match is None:
                action['action'] = toTitleCase(action['action'])

            ## Convert votes to lists of names and calculate absent
            action.update({key: "" for key in required if key not in action})
            action['yeas']    = [lookUpCouncillorName(x) for x in action['yeas'].split(",") if x]
            action['nays']    = [lookUpCouncillorName(x) for x in action['nays'].split(",") if x]
            action['present'] = [lookUpCouncillorName(x) for x in action['present'].split(",") if x]
            action['recused'] = [lookUpCouncillorName(x) for x in action['recused'].split(",") if x]
            councillors = set(action['yeas'] + action['nays'] + action['present'])
            if action['vote'] and action['vote'].lower() not in ("affirmative vote", "voice vote"):
                if councillors:
                    action['absent'] = list(sorted(all_councillors.difference(councillors)))
                elif action['vote'].lower() in ("9-0-0", 'unanimous'):
                    action['yeas'] = list(all_councillors)

            ## Overlay on previous item if it was charter righted
            if action_uid in items and items[action_uid]['charter_right']:
                keys = ('yeas', 'nays', 'present', 'recused', 'absent', 'vote', 'action')
                overlayKeys(items[action_uid], action, keys)
            else:
                items[action_uid] = action

    return regrouped


def processResLinks(node) -> Dict[str, List[Tuple[str, str]]]:
    links = defaultdict(list)
    for reslink in hp.findAllTags(node, 'div', 'ResLink'):
        ## Process each link type
        try:
            name = hp.findText(reslink, 'span', 'LinkType').lower()
            links[name].append(hp.findATag(reslink))
        except:
            pass

    return links


def processResLinkNames(node) -> Dict[str, Dict[str, str]]:
    links = processResLinks(node)
    names = defaultdict(lambda: defaultdict(str))
    for link_type in links.keys():
        for o_name, _ in links[link_type]:
            ## Look for CMA
            match = re.search(r"CMA \d+ # ?\d+", o_name)
            if match:
                names[link_type]['cma'] = match.group()

            ## Look for POR
            match = re.search(r"POR \d+ # ?\d+", o_name)
            if match:
                names[link_type]['por'] = match.group()

            ## Look for APP
            match = re.search(r"APP \d+ # ?\d+", o_name)
            if match:
                names[link_type]['app'] = match.group()

            ## Look for AR
            match = re.search(r"^(AR\S+)\s+:", o_name)
            if match:
                names[link_type]['ar'] = match.groups()[0]

    return names


def findCharterRight(soup):
    header = hp.findTag(soup, 'h1', 'LegiFileHeading').text
    match = re.search(r"charter right exercised by (?:councill?or|vice mayor|mayor) (\w+) in\b", header, re.IGNORECASE)
    if match:
        return lookUpCouncillorName(match.groups()[0])

    return ""


def processKeyWordTable(table) -> Dict[str, str]:
    """Take a table from a city agenda item website and process it into a dictionary"""
    ths = []
    tds = []
    for row in table.find_all('tr'):
        ths.extend([x.text.strip().replace(':', '') for x in row.find_all('th')])
        tds.extend([x.text.strip().replace(':', '') for x in row.find_all('td')])

    return dict(zip(ths, tds))
