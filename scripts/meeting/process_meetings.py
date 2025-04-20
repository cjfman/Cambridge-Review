#! /usr/bin/python3.8
## pylint: disable=too-many-locals,too-many-branches

import argparse
import csv
import json
import os
import re
import sys
import traceback

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests
from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

## pylint: disable=import-error,wrong-import-order
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.councillors import getCouncillorNames, setCouncillorInfo, lookUpCouncillorName
from citylib.utils import print_green, print_red, overlayKeys, toTitleCase, setDefaultValue

VERBOSE = False
ALLOWED_TYPES = ('regular', 'special')
MAX_MSG_LEN = 48
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

SUPPORTED_TITLES = (
    "City Manager's Agenda",
    "Communications",
    "Resolutions",
    "Policy Order and Resolution List",
    "Applications and Petitions",
    "Communications and Reports from Other City Officers",
    "Unfinished Business",
)

UNSUPPORTED_TITLES = (
    "Charter Right",
    "Calendar",
    "Committee Reports",
    "Communications and Reports from Other City Officers",
)

CMA_HDRS = (
    "Unique Identifier",
    "Meeting",
    "Meeting Date",
    "Agenda Number",
    "Category",
    "Awaiting Report",
    "Policy Order",
    "Charter Right",
    "Outcome",
    "Vote",
    "Yeas",
    "Nays",
    "Present",
    "Absent",
    "Recused",
    "Link",
    "Notes",
    "Summary",
)

APP_HDRS = (
    "Unique Identifier",
    "Meeting",
    "Meeting Date",
    "Agenda Number",
    "Category",
    "Name",
    "Address",
    "Subject",
    "Charter Right",
    "Outcome",
    "Vote",
    "Yeas",
    "Nays",
    "Present",
    "Absent",
    "Recused",
    "Link",
    "Notes",
)

COM_HDRS = (
    "Unique Identifier",
    "Agenda Number",
    "Meeting",
    "Meeting Date",
    "Name",
    "Address",
    "Subject",
    "Link",
    "Notes",
)

RES_HDRS = (
    "Unique Identifier",
    "Agenda Number",
    "Meeting",
    "Meeting Date",
    "Category",
    "Sponsor",
    "Outcome",
    "Vote",
    "Yeas",
    "Nays",
    "Present",
    "Absent",
    "Recused",
    "Link",
    "Summary",
    "Notes",
)

POR_HDRS = (
    "Unique Identifier",
    "Agenda Number",
    "Meeting",
    "Meeting Date",
    "Sponsor",
    "Co-Sponsors",
    "Charter Right",
    "Amended",
    "Outcome",
    "Vote",
    "Yeas",
    "Nays",
    "Present",
    "Absent",
    "Recused",
    "Link",
    "Summary",
    "Notes",
)

ORD_HDRS = (
    "Unique Identifier",
    "Meeting",
    "Meeting Date",
    "CMA",
    "Policy Order",
    "Application",
    "Sponsor",
    "Co-Sponsors",
    "Amended",
    "Outcome",
    "Vote",
    "Yeas",
    "Nays",
    "Present",
    "Absent",
    "Recused",
    "Link",
    "Summary",
    "Notes",
)

AR_HDRS = (
    "Unique Identifier",
    "Department",
    "Category",
    "Policy Order",
    "Link",
    "Description",
)


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://cambridgema.iqm2.com",
        help="The base URL")
    parser.add_argument("--cache-dir", required=True,
        help="Where to cache downloads from the city website")
    parser.add_argument("--force-fetch", action="store_true",
        help="Force fetching of the meeting html")
    parser.add_argument("--exit-on-error", action="store_true",
        help="Stop processing meetings if there is an error")
    parser.add_argument("--num-meetings", type=int, default=0,
        help="The maximum number of meetings to process. Set 0 for no limit")
    parser.add_argument("--meeting",
        help="Process this specific meeting")
    parser.add_argument("--councillor-info", required=True,
        help="File with councillor info")
    parser.add_argument("--session", type=int,
        help="The session year. Defaults to most recent one found in councillor info file")
    parser.add_argument("--final-actions",
        help="Json file with the final actions")
    parser.add_argument("--aggrigate-votes", action="store_true",
        help="Add aggrigate vote columns")
    parser.add_argument("--set-attendance", action="store_true",
        help="Update attendance in the meetings file. Has no affect without --final-actions")
    parser.add_argument("--set-attendance-only", action="store_true",
        help="Set attendance without processing the meetings")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="Be verbose")
    parser.add_argument("meetings_file",
        help="The html file containing meeting info")
    parser.add_argument("output_dir",
       help="Where to save all of the output files")

    return parser.parse_args()


class AgendaItem:
    """Abstract class"""
    ## pylint: disable=no-member,attribute-defined-outside-init,access-member-before-definition
    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        if hasattr(self, 'name'):
            msg = " ".join([self.uid, self.name, self.meeting_uid])
            if len(self.subject) > MAX_MSG_LEN:
                return msg + self.subject[:MAX_MSG_LEN] + "..."

            return msg + self.subject

        return None

    def setNotes(self, notes):
        self.notes = notes
        lower = notes.lower()

        ## Check for affirmative vote
        if hasattr(self, 'vote') and not self.vote:
            match = re.match(r"(?:by )?(?:the|an?)? ?((?:Affirmative|Voice) Vote) of \w+ Members", self.notes, re.IGNORECASE)
            if match:
                self.vote = toTitleCase(match.groups()[0])

        ## Check charter right
        if hasattr(self, 'charter_right') and not self.charter_right          \
            and ("charter right" in lower                                     \
                or self.action == "Charter Right" and "exercised by" in lower \
            ):
            match = re.search(r"exercised by (?:councill?or|vice mayor|mayor) (\w+)", self.notes, re.IGNORECASE)
            if match:
                self.charter_right = lookUpCouncillorName(match.groups()[0])
            else:
                ## Some mistake has been made
                self.charter_right = "!!!"


@dataclass
class Meeting:
    uid: str
    body: str
    type: str
    other: str
    session: str
    date: str
    time: str
    status: str
    id: str
    url: str
    agenda_summary: str
    agenda_packet: str
    final_actions: str
    minutes: str
    attendance: str=None

    def __str__(self):
        return f"{self.body} - {self.type} {self.date} ({self.id})"

    def __repr__(self):
        return f"[Meeting {str(self)}]"


@dataclass
class CMA(AgendaItem):
    uid:      str
    num:      int
    category: str
    awaiting: str
    order:    str
    url:      str
    action:   str
    vote:     str
    charter_right: str  = ""
    description:   str  = ""
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "CMA"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Awaiting Report":   self.awaiting,
            "Policy Order":      self.order,
            "Link":              self.url,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Charter Right":     self.charter_right,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.action, f"[{self.vote}]", self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[CMA: {str(self)}]"


@dataclass
class Application(AgendaItem):
    uid:      str
    num:      int
    category: str
    name:     str
    subject:  str
    url:      str
    action:   str
    vote:     str
    charter_right: str  = ""
    address:       str  = ""
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "APP"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Name":              self.name,
            "Subject":           self.subject,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Address":           self.address,
            "Charter Right":     self.charter_right,
            "Link":              self.url,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self):
        return f"[Application: {str(self)}]"


@dataclass
class Communication(AgendaItem):
    uid:     str
    num:     int
    name:    str
    address: str
    subject: str
    url:     str
    meeting_uid:  str = ""
    meeting_date: str = ""
    notes:        str = ""
    final_action: dict = None

    @property
    def type(self):
        return "COM"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Name":              self.name,
            "Address":           self.address,
            "Subject":           self.subject,
            "Link":              self.url,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = None
        if self.address:
            msg = " ".join([self.uid, self.name, f'"{self.address}"', self.meeting_uid])
        else:
            msg = " ".join([self.uid, self.name, self.meeting_uid])

        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self):
        return f"[Communication: {str(self)}]"


@dataclass
class Resolution(AgendaItem):
    uid:      str
    num:      int
    category: str
    url:      str
    sponsor:  str
    cosponsors:   str  = ""
    action:       str  = ""
    vote:         str  = ""
    description:  str  = ""
    final_action: dict = None
    meeting_uid:  str  = ""
    meeting_date: str  = ""
    notes:        str  = ""

    @property
    def type(self):
        return "RES"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Link":              self.url,
            "Sponsor":           self.sponsor,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.sponsor, self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[Resolution: {str(self)}]"


@dataclass
class PolicyOrder(AgendaItem):
    uid:      str
    num:      int
    url:      str
    sponsor:  str
    cosponsors:    str  = ""
    action:        str  = ""
    vote:          str  = ""
    amended:       str  = ""
    charter_right: str  = ""
    description:   str  = ""
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "POR"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Link":              self.url,
            "Sponsor":           self.sponsor,
            "Co-Sponsors":       ",".join(self.cosponsors),
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Amended":           self.amended,
            "Charter Right":     self.charter_right,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.charter_right:
            msg += f" - charter right {self.charter_right}"
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[PolicyOrder: {str(self)}]"


@dataclass
class Ordinance(AgendaItem):
    uid: str
    url: str
    cma:           str  = ""
    order:         str  = ""
    application:   str  = ""
    sponsor:       str  = ""
    cosponsors:    str  = ""
    action:        str  = ""
    vote:          str  = ""
    amended:       str  = ""
    description:   str  = ""
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "ORD"

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Link":              self.url,
            "CMA":               self.cma,
            "Policy Order":      self.order,
            "Application":       self.application,
            "Sponsor":           self.sponsor,
            "Co-Sponsors":       ",".join(self.cosponsors),
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Amended":           self.amended,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[Ordinance: {str(self)}]"


@dataclass
class AwaitingReport(AgendaItem):
    uid: str
    url: str
    description:  str = ""
    department:   str = ""
    category:     str = ""
    policy_order: str = ""
    notes:        str = ""
    final_action: dict = None

    @property
    def type(self):
        return "AR"

    def setMeeting(self, meeting):
        pass

    def update(self, **kwargs):
        if 'description' in kwargs:
            self.description = kwargs['description']
        if 'department' in kwargs:
            self.department = kwargs['department']
        if 'category' in kwargs:
            self.category = kwargs['category']
        if 'policy_order' in kwargs:
            self.policy_order = kwargs['policy_order']

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Department":        self.department,
            "Category":          self.category,
            "Policy Order":      self.policy_order,
            "Link":              self.url,
            "Description":       self.description,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.url])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[AwaitingReport: {str(self)}]"

@dataclass
class ItemInfo:
    category:      str  = ""
    charter_right: str  = ""
    cma:           str  = ""
    order:         str  = ""
    app:           str  = ""
    awaiting:      str  = ""
    action:        str  = ""
    amended:       str  = ""
    history:       dict = None
    sponsor:       list = None
    cosponsors:    list = None


def expandUrl(base, url) -> str:
    """Expand a URL found from HTML"""
    if url[0] == '/':
        return os.path.join(base, url[1:])
    if re.search(r"^\w+\.aspx", url):
        return os.path.join(base, 'Citizens', url)

    return url


def findTag(node, tag, cls=None):
    """Find a tag in a soup node"""
    if cls is None:
        return node.find(tag)

    return node.find(tag, {'class': cls})


def findAllTags(node, tag, cls=None):
    """Find all matching tags in a soup node"""
    if cls is None:
        return node.find_all(tag)

    return node.find_all(tag, {'class': cls})


def findATag(node, tag=None, cls=None) -> Tuple[str, str]:
    """Find an A tag in a soup node. Return the text and href"""
    if tag is not None:
        node = findTag(node, tag, cls)
    if node is None:
        raise Exception(f"Couldn't find a '{tag}' tag")

    a_tag = node.find('a')
    if a_tag is None:
        raise Exception("Couldn't find an 'a' tag")

    return (a_tag.text.strip(), a_tag['href'])


def findText(node, tag=None, cls=None) -> str:
    """Find the text in a soup node"""
    found = None
    if tag is None:
        found = node
    else:
        found = findTag(node, tag, cls)

    if found is None:
        return ''

    return found.text.strip()


def findAllText(node, tag, cls=None) -> List[str]:
    """Find all the text in a soup node"""
    found = findAllTags(node, tag, cls)
    return [x.text.strip() for x in found if x is not None]


def uidToFileSafe(uid) -> str:
    """Take a meeting agenda item UID and make it file name safe"""
    return uid.replace(' ', '_').replace('#', 'no')


def buildRow(item, hdrs, final_action=None, *, aggrigate_votes=False):
    """Make a csv row from an agenda item"""
    d = item.to_dict()
    action_map = {
        'yeas':    'yes',
        'nays':    'no',
        'present': 'present',
        'absent':  'absent',
        'recused': 'recused',
    }

    ## Replace with found final action from item if one wasn't provided
    replaceable = (not final_action or not final_action['action'] or final_action['action'] == "Charter Right")
    if replaceable and item.final_action and item.final_action['vote']:
        if d['Outcome'] == "Charter Right":
            if 'Charter Right' in d and d['Charter Right']:
                item.final_action['charter_right'] = d['Charter Right']
            elif final_action is not None and final_action['charter_right']:
                item.final_action['charter_right'] = final_action['charter_right']
            elif item.final_action['charter_right']:
                ## This is probably a boolean, so replace it
                item.final_action['charter_right'] = "!!!"
        final_action = item.final_action

    ## Update with final actions
    if final_action is not None:
        d['Vote'] = final_action['vote'] or d['Vote']
        d['Amended'] = (('Amended' in d and d['Amended']) or final_action['amended'])
        ## Update the charter righing councilor
        if ('Charter Right' not in d or not d['Charter Right']) and final_action['charter_right']:
            d['Charter Right'] = lookUpCouncillorName(final_action['charter_right'])
        ## Update the final action
        #no_outcome = ('Outcome' not in d or not d['Outcome'] or d['Outcome'] == 'Charter Right')
        if final_action['action'] and final_action['vote']:
            d['Outcome'] = final_action['action']
        if d['Vote'] is None:
            if action_map:
                d['Vote'] = "Roll Call"
            elif d['Outcome']:
                d['Vote'] = "Voice Vote"

        for key, val in action_map.items():
            column = key.title()
            if aggrigate_votes:
                d[column] = ",".join(final_action[key])
            for name in final_action[key]:
                d[name] = val

    ## Check vote type
    if ('Vote' not in d or d['Vote'] is None) and ('Outcome' in d and d['Outcome'] and d['Outcome'] != "Charter Right"):
        d['Vote'] = "Voice Vote"

    ## Every row dict must have exactly the keys in the header
    row = {}
    for key in hdrs:
        if key in d and d[key] is not None:
            row[key] = str(d[key])
        else:
            row[key] = ""

    return row


def setCouncillorColumns(names):
    """Add councillor names to headers"""
    ## pylint: disable=global-statement
    global CMA_HDRS, APP_HDRS, RES_HDRS, POR_HDRS, ORD_HDRS
    ## CMA
    idx = CMA_HDRS.index("Vote") + 1
    CMA_HDRS = CMA_HDRS[:idx] + names + CMA_HDRS[idx:]

    ## APP
    idx = APP_HDRS.index("Vote") + 1
    APP_HDRS = APP_HDRS[:idx] + names + APP_HDRS[idx:]

    ## RES
    idx = RES_HDRS.index("Vote") + 1
    RES_HDRS = RES_HDRS[:idx] + names + RES_HDRS[idx:]

    ## POR
    idx = POR_HDRS.index("Vote") + 1
    POR_HDRS = POR_HDRS[:idx] + names + POR_HDRS[idx:]

    ## ORD
    idx = ORD_HDRS.index("Vote") + 1
    ORD_HDRS = ORD_HDRS[:idx] + names + ORD_HDRS[idx:]


def processKeyWordTable(table) -> Dict[str, str]:
    """Take a table from a city agenda item website and process it into a dictionary"""
    ths = []
    tds = []
    for row in table.find_all('tr'):
        ths.extend([x.text.strip().replace(':', '') for x in row.find_all('th')])
        tds.extend([x.text.strip().replace(':', '') for x in row.find_all('td')])

    return dict(zip(ths, tds))


def processResLinks(node) -> Dict[str, List[Tuple[str, str]]]:
    links = defaultdict(list)
    for reslink in findAllTags(node, 'div', 'ResLink'):
        ## Process each link type
        try:
            name = findText(reslink, 'span', 'LinkType').lower()
            links[name].append(findATag(reslink))
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

def parseAction(line):
    ## Check for voice vote
    match = re.match(r"(?:Order )?(.+?)\s+(?:by|on) (?:an |am )?(affirmative vote|voice vote)", line, re.IGNORECASE)
    if match:
        action, vote_type = match.groups()
        return (toTitleCase(action), toTitleCase(vote_type))

    ## Check for vote count
    match = re.match(r"(?:Order )?(.+?)\s\[?((?:\d-\d-\d(?:-\d)?)|(?:\d+ to \d+)|Unanimous)\]?", line, re.IGNORECASE)
    if match:
        action, vote = match.groups()
        return (toTitleCase(action), toTitleCase(vote))

    match = re.match(r"(?:Order )(.+)", line, re.IGNORECASE)
    if match:
        action = match.groups()[0]
        return (toTitleCase(action), "")

    return (line, "")


def findCouncillorsInRow(row):
    councillors = findText(findAllTags(row, 'td')[1]).split(',')
    return [lookUpCouncillorName(x.strip()) for x in councillors]


def extractAction(action) -> str:
    """Find the simple action from an action string"""
    if action == "Failed of Adoption":
        action = 'Failed'
    else:
        match = re.match(r"(Fail(?:s|ed) to )?Pass(?:ed)? to be (\w+)", action, re.IGNORECASE)
        if match:
            if match.groups()[0]:
                action = 'Failed'
            else:
                action = match.groups()[1]

    ## Cleanup
    if action == "Ordainded":
        action = "Ordained"

    return action


def processHistory(history_table):
    history = {}
    ## Look for a vote record
    for results_table in findAllTags(history_table, 'table', 'VoteRecord'):
        rows = findAllTags(results_table, 'tr')
        if not rows:
            continue
        for row in rows:
            role = findText(row, 'td', 'Role')
            if not role:
                continue

            ## Check for the type of vote
            role = role.lower().replace(':', '')
            if role == "result":
                result = findText(row, 'td', 'Result').lower()
                if result == "charter right":
                    ## Found a charter right
                    history['charter_right'] = True
                else:
                    ## Try and parse an action
                    action, vote = parseAction(result)
                    if action is not None:
                        history['action'] = action.strip()
                        history['vote']   = vote.strip()
            elif role in ('yeas', 'nays', 'present', 'absent', 'recused'):
                history[role] = findCouncillorsInRow(row)

    if not history:
        ## Look for affirmative vote
        txt = findText(history_table, 'p').lower()
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
            history['action'] = extractAction(history['action'])

        ## Set absence
        if history['yeas']:
            all_councillors = set(getCouncillorNames())
            councillors = set(history['yeas'] + history['nays'] + history['present'])
            history['absent'] = list(sorted(all_councillors.difference(councillors)))

    return history



def findCharterRight(soup):
    header = findTag(soup, 'h1', 'LegiFileHeading').text
    match = re.search(r"charter right exercised by (?:councill?or|vice mayor|mayor) (\w+) in\b", header, re.IGNORECASE)
    if match:
        return lookUpCouncillorName(match.groups()[0])

    return ""


def processItem(args, row, num):
    """Process a meeting agenda item"""
    ## Process the title and link
    title, link = findATag(row, 'td', 'Title')
    link = expandUrl(args.base_url, link)
    match = re.match(r"((CMA|APP|COM|RES|POR|COF|ORD) \d+ # ?\d+)\s(?:: )(.*)", title)
    if not match:
        ## Maybe it's an awaiting report
        match = re.match(r"(AR-\d+-\d+)\s(?:: )(.*)", title)
        if match:
            uid, description = match.groups()
            return AwaitingReport(uid, link, description)

        if VERBOSE:
            print_red(f"Failed to process item type '{title}'")

        return None

    uid, itype, title = match.groups()

    ## Process the result
    result = findText(row, 'span', 'ItemVoteResult')
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
        'CMA': processCma,
        'APP': processApp,
        'COM': processCom,
        'RES': processRes,
        'POR': processPor,
        'ORD': processOrd,
    }
    if itype in handlers:
        return handlers[itype](args, uid, num, title, link, vote, action)

    return None


def processItemInfo(args, uid, link, action) -> ItemInfo:
    ## Fetch CMA page from city website
    path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, path, force=args.force_fetch)
    soup = BeautifulSoup(fetched, 'html.parser')
    charter_right = findCharterRight(soup)

    ## Category
    info_div = findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(findTag(info_div, 'table', 'LegiFileSectionContents'))
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
    action = extractAction(action)

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
    history_table = findTag(soup, 'table', 'MeetingHistory')
    history = None
    if history_table:
        try:
            history = processHistory(history_table)
        except Exception as e:
            print_red(f"Error: Failed to process history for {uid}: {e}")
            if VERBOSE or args.exit_on_error:
                traceback.print_exc()
            if args.exit_on_error:
                raise e

    return ItemInfo(category, charter_right, cma, order, app, awaiting, action, amended, history, sponsors[0], sponsors[1:])


def processCma(args, uid, num, title, link, vote, action) -> CMA:
    """Process a CMA agenda item"""
    ## Clean up title
    title = re.sub(r"(?:A|Transmitting) ?communication (?:transmitted )?from (?:.+), City Manager, relative to ", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^the (?=appropriation|(?:re-?)?appointment|transfer)", "", title, flags=re.IGNORECASE).capitalize()

    ## Process info
    info = processItemInfo(args, uid, link, action)
    return CMA(uid, num, info.category, info.awaiting, info.order, link, action, vote, info.charter_right, title, info.history)


def processApp(args, uid, num, title, link, vote, action) -> Application:
    """Process an application agenda item"""
    ## pylint: disable=unused-argument
    info = processItemInfo(args, uid, link, action)

    ## Attempt to get the name
    name    = ""
    subject = ""
    options = "|".join(("regarding", "to amend", "transmitting", "petitioning", "opposing", "urging"))
    regex = re.compile(fr"An? (?:application|(?:zoning )?petition|request) (?:has been|was) (?:received? ?from|filed by) (.+?),? ((?:requesting ?(?:permission|that)?|{options}) .+)", re.IGNORECASE)
    match = regex.search(title)
    if match:
        name, subject = match.groups()
    else:
        subject = title

    ## Attempt to get address
    address = ""
    match = re.search(r"at the premises numbered ([^;]+)(?:;|\. Approval)", subject)
    if match:
        address = match.groups()[0]

    return Application(uid, num, info.category, name, subject, link, action, vote, info.charter_right, address, info.history)


def processCom(args, uid, num, title, link, vote, action) -> Communication:
    """Process a communication agenda item"""
    ## pylint: disable=unused-argument
    name    = ""
    subject = ""
    address = ""

    ## Attempt to match the name of a person
    types = "|".join(["communication", "email", "e-mail", "written protest", "zoning petition"])
    options = "|".join((
        "regarding", "expressing", "transmitting", "commenting", "stating", "re", "relating to", "relative to", "noting that", "concerning", "stated", "raising",
        "announcing that", "outlining", "spoke about",
    ))
    opinions = (
        "supporting", "in support", "on support", "supported", "endorsing", "in favor", "urging", "requesting", "thanking", "encouraging", "to amend",
        "opposing", "in opposition",
    )
    options += "|" + "|".join(opinions)
    match = re.search(fr"(?:\w+ )?(?:{types})s? (?:was|were|has been)? ?(?:received )?from ?(.+?)(?:, (\d.+?))?,? ({options})[,:]? (.+)", title, re.IGNORECASE)
    if match:
        name, address, option, subject = match.groups()
        address = address or ""
        if option in opinions:
            subject = f"{option} {subject}"

    ## Attempt to match 'Sundry'
    if match is None:
        match = re.search(fr"Sundry (communication|e-?mail)s? (?:(?:was|were|have been)? ?(?:received|regarding))?,? ?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Sundry'
            subject = match.groups()[0]

    ## Attempt to match 'anonymous'
    if match is None:
        match = re.search(fr"(?:A|An)? ?(anonymous|unidentified) (?:{types})s? (?:(?:was|were|have been)? ?received)?,? ?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Anonymous'
            subject = match.groups()[0]
    if match is None:
        match = re.search(fr"A (?:{types}) (?:(?:was|were|have been)? ?received)?,? ?(?:anonymously )?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Anonymous'
            subject = match.groups()[0]

    ## Backup
    if not subject:
        subject = title

    return Communication(uid, num, name, address, subject, link)


def processRes(args, uid, num, title, link, vote, action) -> Resolution:
    """Process a resolution agenda item"""
    info = processItemInfo(args, uid, link, action)
    return Resolution(uid, num, info.category, link, info.sponsor, info.cosponsors, info.action, vote, title, info.history)


def processPor(args, uid, num, title, link, vote, action) -> PolicyOrder:
    """Process a policy order agenda item"""
    info = processItemInfo(args, uid, link, action)
    return PolicyOrder(uid, num, link, info.sponsor, info.cosponsors, info.action, vote, info.amended, info.charter_right, title, info.history)


def processOrd(args, uid, num, title, link, vote, action) -> Ordinance:
    """Process an ordinance agenda item"""
    ## pylint: disable=unused-argument
    info = processItemInfo(args, uid, link, action)
    if 'action' in info.history:
        action = info.history['action']

    return Ordinance(uid, link, info.cma, info.order, info.app, info.sponsor, info.cosponsors, action, vote, info.amended, title, info.history)


def processAr(args, item):
    ## Fetch AR page from the city website
    ar_path = os.path.join(args.cache_dir, f"{uidToFileSafe(item.uid)}.html")
    fetched = fetchUrl(item.url, ar_path, force=args.force_fetch)
    soup = BeautifulSoup(fetched, 'html.parser')

    ## Additional info
    info_div = findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(findTag(info_div, 'table', 'LegiFileSectionContents'))
    category   = table['Category']
    department = table['Department']

    ## Origin if any
    order = ""
    links = processResLinks(soup)
    link_names = processResLinkNames(soup)
    if 'origin' in link_names:
        order = link_names['origin']['por']

    item.update(department=department, category=category, policy_order=order)
    return item


def processNewArs(args, ar_map, items, writer:csv.DictWriter):
    """Process awaiting reports"""
    ## Unlike most agenda items, the list of awaiting reports tends to grow, so track
    ## ARs across meetings
    total = 0
    for item in items:
        if item.uid in ar_map:
            continue

        if VERBOSE:
            print(f"New awaiting report: {item}")

        ar_map[item.uid] = processAr(args, item)
        writer.writerow(buildRow(item, AR_HDRS, aggrigate_votes=args.aggrigate_votes))
        total += 1

    print_green(f"Wrote {total} awaiting reports")


def processMeeting(args, meeting) -> Dict[str, List[Any]]:
    """Process a meeting"""
    meeting_path = os.path.join(args.cache_dir, f"meeting_{meeting.id}.html")
    meeting_html = fetchUrl(meeting.url, meeting_path, verbose=True, force=args.force_fetch)
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
        td = findTag(row, 'td', 'Title')
        if td is not None:
            ## Enable or disable processessing baesd upon section
            title = td.text.strip()
            if not enabled and title in SUPPORTED_TITLES:
                if VERBOSE:
                    print(f"""Found section "{title}". Enable agenda item processing""")
                enabled = True
                continue
            if enabled and title in UNSUPPORTED_TITLES:
                if VERBOSE:
                    print(f"""Found section "{title}". Disable agenda item processing""")

                enabled = False
                continue

        if not enabled:
            continue

        ## Look for agenda item number
        td = findTag(row, 'td', 'Num')
        if td is not None and re.match(r"\d+\.?", td.text.strip()):
            if VERBOSE:
                print(f"Processing row: {row.text}")
            num = td.text.strip().replace('.', '')
            try:
                item = processItem(args, row, num)
            except Exception as e:
                print_red(f"Failed to process item '{row}': {e}")
                raise e

            if item is not None:
                items[item.type].append(item)
        elif item is not None:
            ## Look for comments
            td = findTag(row, 'td', 'Comments')
            if td is not None:
                ## Set comment for most recent item
                item.setNotes(". ".join(findAllText(td, 'span')))
        elif td is not None:
            if VERBOSE:
                print_red(f"Tag td didn't match anything: {td.text}")
        else:
            if VERBOSE:
                print_red(f"Couldn't find a td with class 'Num'")

    print(f"Found {len(items)} for meeting '{meeting}'")
    for item in [x for l in items.values() for x in l]:
        item.setMeeting(meeting)
        if VERBOSE and item.type != "AR":
            print(item)

    return items


def processMeetings(args, meetings, writers, final_actions=None):
    num = 0
    ar_map = {}
    for meeting in meetings:
        try:
            if args.meeting and meeting.id != args.meeting and args.meeting != meeting.date:
                continue
            if meeting.body.lower() != 'city council' or meeting.type.lower() not in ALLOWED_TYPES:
                print(f"Skipping meeting '{meeting}'")
                continue
            if meeting.status == 'cancelled':
                print(f"Meeting '{meeting}' was cancelled. Skipping")
                continue

            print(f"Processing meeting '{meeting}'")
            items = processMeeting(args, meeting)
            if items is not None:
                if final_actions is not None and meeting.id in final_actions:
                    print(f"Found final actions for meeting '{meeting}'")
                    postProcessItems(writers, items, final_actions[meeting.id])
                else:
                    if final_actions is not None:
                        print_red(f"No final actions for meeting '{meeting}'")

                    postProcessItems(writers, items)

                ## Process awaiting reports
                if 'AR' in items:
                    processNewArs(args, ar_map, items['AR'], writers['AR'])

            ## Maybe end processing now
            num += 1
            if args.num_meetings and num >= args.num_meetings:
                break
        except Exception as e:
            print_red(f"Error: Failed to process meeting '{meeting}': {e}")
            if VERBOSE or args.exit_on_error:
                traceback.print_exc()
            if args.exit_on_error:
                raise e


def fetchUrl(url, cache_path=None, *, verbose=False, force=False) -> str:
    """Fetch the data from a URL. Optionally cache it locally to disk"""
    if cache_path is not None and not force and os.path.isfile(cache_path):
        if VERBOSE or verbose:
            print(f"Reading '{url}' from cache '{cache_path}'")

        with open(cache_path, 'r', encoding='utf8') as f:
            return f.read()

    print(f"Fetching '{url}'")
    content = requests.get(url, headers=REQUEST_HDR).content.decode('utf8')
    if cache_path is not None:
        print(f"Caching '{cache_path}'")
        try:
            with open(cache_path, 'w', encoding='utf8') as f:
                f.write(content)
        except Exception as e:
            ## Remove bad cached file
            if os.path.isfile(cache_path):
                os.remove(cache_path)

            raise e

    return content


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


def postProcessItems(writers, items, final_actions=None):
    sets = (
        ('CMA', CMA_HDRS),
        ('APP', APP_HDRS),
        ('COM', COM_HDRS),
        ('RES', RES_HDRS),
        ('POR', POR_HDRS),
        ('ORD', ORD_HDRS),
    )
    for key, hdrs in sets:
        for item in items[key]:
            if final_actions is not None and item.uid in final_actions:
                writers[key].writerow(buildRow(item, hdrs, final_actions[item.uid]))
            else:
                writers[key].writerow(buildRow(item, hdrs))

    types = [x for x, y in sets]
    msg = " ".join([f"{k}:{len(v)}" for k, v in items.items() if k in types])
    total = sum([len(v) for k, v in items.items() if k in types])
    print_green(f"Wrote {total} items. {msg}")


def setupOutputFiles(output_dir):
    """Open output files"""
    print("Opening output files")
    files   = {}
    writers = {}
    sets = (
        ('CMA', CMA_HDRS, "cma.csv"),
        ('APP', APP_HDRS, "applications_and_petitions.csv"),
        ('COM', COM_HDRS, "communications.csv"),
        ('RES', RES_HDRS, "resolutions.csv"),
        ('POR', POR_HDRS, "policy_orders.csv"),
        ('ORD', ORD_HDRS, "ordinances.csv"),
        ('AR',  AR_HDRS,  "awaiting_reports.csv"),
    )
    for key, hdrs, name in sets:
        path = os.path.join(output_dir, name)
        try:
            f = open(path, 'w', encoding='utf8')
            w = csv.DictWriter(f, fieldnames=hdrs, lineterminator='\n')
            w.writeheader()
            files[key]   = f
            writers[key] = w
        except Exception as e:
            print_red(f"Failed to open file '{path}' for writing: {e}")
            return None

    return (files, writers)


def openMeetings(path, *, session=None):
    meetings = []
    with open(path, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "Unique Identifier" in row:
                row['uid'] = row['Unique Identifier']
                del row['Unique Identifier']
            else:
                row['uid'] = f"{row['Date']} {row['Type']}"
            if 'Session' not in row and session is not None:
                row['Session'] = session
            meetings.append(Meeting(**{ k.lower().replace(' ', '_'): v for k, v in row.items() }))

    return meetings


def setAttenance(args, final_actions):
    ## Load meetings
    meetings = None
    with open(args.meetings_file, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        meetings = list(reader)

    if not meetings:
        return

    ## Add attendance to header if needed
    headers = list(meetings[0].keys())
    if 'Attendance' not in headers:
        headers.insert(headers.index('url'), 'Attendance')

    ## Update each meeting using the final actions
    for meeting in meetings:
        if meeting['Id'] not in final_actions:
            continue

        #votes = ('yeas', 'nays', 'present', 'recused')
        attendance = set()
        for action in final_actions[meeting['Id']].values():
            attendance.update(action['yeas'] + action['nays'] + action['present'] + action['recused'])
        meeting['Attendance'] = ",".join(sorted(attendance))

    ## Write back to meetings file
    with open(args.meetings_file, 'w', encoding='utf8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, lineterminator='\n')
        writer.writeheader()
        for meeting in meetings:
            writer.writerow(meeting)


def main(args):
    if args.verbose:
        global VERBOSE ## pylint: disable=global-statement
        VERBOSE = args.verbose

    ## Check args
    skip_processing = False
    if args.set_attendance_only:
        args.set_attendance = True
        skip_processing = True

    ## Set councillor info
    if args.councillor_info is not None:
        if not setCouncillorInfo(args.councillor_info, args.session):
            print_red(f"Failed to set up councillor info")
            return 1

        setCouncillorColumns(getCouncillorNames())

    ## Open meetings file
    meetings = openMeetings(args.meetings_file, session=args.session)
    output_files = None
    final_actions = None
    if args.final_actions:
        final_actions = processFinalActions(args.final_actions)

    print(f"Read {len(meetings)} meetings from '{args.meetings_file}'")
    ## Do work
    try:
        ## Process meetings
        if not skip_processing:
            output_files, writers = setupOutputFiles(args.output_dir)
            if output_files is None:
                return 1

            processMeetings(args, meetings, writers, final_actions)

        ## Update attendance
        if args.set_attendance and final_actions is not None:
            print("Updating attendance")
            setAttenance(args, final_actions)
    except KeyboardInterrupt:
        print(f"User requested exit")
        return 1
    finally:
        ## Close all files
        if output_files is not None:
            for f in output_files.values():
                f.close()


    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
