## pylint: disable=too-many-branches,too-many-locals
import json
import os
import re

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

import citylib.utils.html_parsing as hp
from citylib.utils import print_red, fetch_url

from citylib import agenda
from citylib.councillors import getCouncillorNames, lookUpCouncillorName
from citylib.utils import setDefaultValue, toTitleCase, overlayKeys


def expandUrl(base, url) -> str:
    """Expand a URL found from HTML"""
    if url[0] == '/':
        return os.path.join(base, url[1:])
    if re.search(r"^\w+\.aspx", url):
        return os.path.join(base, 'Citizens', url)

    return url


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


def processItemInfo(uid, link, action, cache_dir, *, force_fetch=False) -> agenda.ItemInfo:
    ## Fetch CMA page from city website
    path = os.path.join(cache_dir, f"{agenda.uidToFileSafe(uid)}.html")
    fetched = fetch_url(link, path, force=force_fetch)
    soup = BeautifulSoup(fetched, 'html.parser')
    charter_right = findCharterRight(soup)

    ## Category
    info_div = hp.findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(hp.findTag(info_div, 'table', 'LegiFileSectionContents'))
    sponsors = [lookUpCouncillorName(x.strip()) for x in table['Sponsors'].split(',')]
    category = table['Category']
    if category.lower() == "transmitting communication":
        category = "Communication"

    ## Amended
    amended = ""
    match = re.match(r"(.*) as Amended", action, re.IGNORECASE)
    if match:
        amended = "yes"
        action = match.groups()[0]

    ## Other actions
    action = agenda.extractAction(action)

    ## Cleanup
    if action == "Ordainded":
        action = "Ordained"

    ## Origins if any
    cma      = ""
    order    = ""
    app      = ""
    awaiting = ""
    link_names = processResLinkNames(soup)
    if 'origin' in link_names:
        cma      = link_names['origin']['cma']
        order    = link_names['origin']['por']
        app      = link_names['origin']['app']
        awaiting = link_names['origin']['ar']

    for names in link_names.values():
        cma      = cma      or names['cma']
        order    = order    or names['por']
        app      = app      or names['app']
        awaiting = awaiting or names['ar']

    ## History
    history_table = hp.findTag(soup, 'table', 'MeetingHistory')
    history = None
    if history_table:
        try:
            history = processHistory(history_table)
        except Exception as e:
            print_red(f"Error: Failed to process history for {uid}: {e}")

    return agenda.ItemInfo(category, charter_right, cma, order, app, awaiting, action, amended, history, sponsors[0], sponsors[1:])


def processAr(item, cache_dir, *, force_fetch=False):
    ## Fetch AR page from the city website
    ar_path = os.path.join(cache_dir, f"{agenda.uidToFileSafe(item.uid)}.html")
    fetched = fetch_url(item.url, ar_path, force=force_fetch)
    soup = BeautifulSoup(fetched, 'html.parser')

    ## Additional info
    info_div = hp.findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(hp.findTag(info_div, 'table', 'LegiFileSectionContents'))
    category   = table['Category']
    department = table['Department']

    ## Origin if any
    order = ""
    #links = processResLinks(soup)
    link_names = processResLinkNames(soup)
    if 'origin' in link_names:
        order = link_names['origin']['por']

    item.update(department=department, category=category, policy_order=order)
    return item


def processItem(base_url, cache_dir, row, num, *, force_fetch=False):
    """Process a meeting agenda item"""
    ## Process the title and link
    title, link = hp.findATag(row, 'td', 'Title')
    link = expandUrl(base_url, link)
    match = re.match(r"((CMA|APP|COM|RES|POR|COF|ORD) \d+ # ?\d+)\s(?:: )(.*)", title)
    if not match:
        ## Maybe it's an awaiting report
        match = re.match(r"(AR-\d+-\d+)\s(?:: )(.*)", title)
        if match:
            uid, description = match.groups()
            return agenda.AwaitingReport(uid, link, description)

        print_red(f"Failed to process item type '{title}'")
        return None

    uid, itype, title = match.groups()

    ## Process the result
    result = hp.findText(row, 'span', 'ItemVoteResult')
    action = result
    vote   = ""
    match = re.match(r"(?:Order )?(.*) by (?:the|an?) ((?:Affirmative|Voice) Vote) of \w+ Members", result, re.IGNORECASE)
    if match:
        action, vote = match.groups()
        action = toTitleCase(action)
        vote = toTitleCase(vote)

    ## Try something else
    if match is None:
        match = re.match(r"(?:order\s+)?(\w+(?: \w+)*)\s?(?:\[([^\]]+)\])?", result, re.IGNORECASE)
        if match:
            action, vote = match.groups()

    ## Action
    if action.lower() == "failed of adoption":
        action = 'Failed'
    else:
        action = toTitleCase(action)

    ## Init item type
    handlers = {
        'CMA': agenda.processCma,
        'APP': agenda.processApp,
        'COM': agenda.processCom,
        'RES': agenda.processRes,
        'POR': agenda.processPor,
        'ORD': agenda.processOrd,
    }
    if itype in handlers:
        info = processItemInfo(uid, link, action, cache_dir, force_fetch=force_fetch)
        return handlers[itype](info, uid, num, title, link, vote, action)

    return None


def processMeeting(meeting, base_url, cache_dir, *, force_fetch=False, verbose=False) -> Dict[str, List[Any]]:
    """Process a meeting"""
    ## pylint: disable=too-many-statements
    if 'iqm2.com' not in (meeting.url or ''):
        print_red(f"URL for meeting '{meeting}' wasn't for iqm2.com")
        return None

    meeting_path = os.path.join(cache_dir, f"meeting_{meeting.id}.html")
    meeting_html = fetch_url(meeting.url, meeting_path, verbose=True, force=force_fetch)
    soup = BeautifulSoup(meeting_html, 'html.parser')

    ## Iterate through agenda table
    table = soup.find('table', {'class': 'MeetingDetail'})
    if table is None:
        print_red("Error: Failed to find meeting details")
        try:
            os.remove(meeting_path)
        except:
            pass
        return None

    item  = None
    items = defaultdict(list)
    rows = table.find_all('tr')
    enabled = False
    print(f"Checking {len(rows)} rows")
    for row in rows:
        ## Look for section title
        td = hp.findTag(row, 'td', 'Title')
        if td is not None:
            ## Enable or disable processessing baesd upon section
            title = td.text.strip()
            if not enabled and title in agenda.SUPPORTED_TITLES:
                if verbose:
                    print(f"""Found section "{title}". Enable agenda item processing""")
                enabled = True
                continue
            if enabled and title in agenda.UNSUPPORTED_TITLES:
                if verbose:
                    print(f"""Found section "{title}". Disable agenda item processing""")

                enabled = False
                continue

        if not enabled:
            continue

        ## Look for agenda item number
        td = hp.findTag(row, 'td', 'Num')
        if td is not None and re.match(r"\d+\.?", td.text.strip()):
            if verbose:
                print(f"Processing row: {row.text}")
            num = td.text.strip().replace('.', '')
            try:
                item = processItem(base_url, cache_dir, row, num, force_fetch=force_fetch)
            except Exception as e:
                print_red(f"Failed to process item '{row}': {e}")
                raise e

            if item is not None:
                items[item.type].append(item)
        elif item is not None:
            ## Look for comments
            td = hp.findTag(row, 'td', 'Comments')
            if td is not None:
                ## Set comment for most recent item
                item.setNotes(". ".join(hp.findAllText(td, 'span')))
        elif td is not None:
            if verbose:
                print_red(f"Tag td didn't match anything: {td.text}")
        else:
            if verbose:
                print_red("Couldn't find a td with class 'Num'")

    print(f"Found {len(items)} for meeting '{meeting}'")
    for item in [x for l in items.values() for x in l]:
        item.setMeeting(meeting)
        if verbose and item.type != "AR":
            print(item)

    return items
