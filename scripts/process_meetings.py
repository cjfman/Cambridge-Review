#! /usr/bin/python3.8
## pylint: disable=too-many-locals,too-many-branches

import argparse
import csv
import os
import re
import sys

from collections import defaultdict
from typing import Any, Dict, List, Tuple

import requests
from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

import html5lib ## pylint: disable=unused-import
import yaml
from bs4 import BeautifulSoup
from termcolor import colored

VERBOSE = False
ALLOWED_TYPES = ('regular', 'special')
MAX_MSG_LEN = 48
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

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
    "Link",
    "Notes",
)

APP_HDRS = (
    "Unique Identifier",
    "Meeting",
    "Meeting Date",
    "Agenda Number",
    "Category",
    "Name",
    "Address",
    "Charter Right",
    "Outcome",
    "Vote",
    "Subject",
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
    "Outcome",
    "Vote",
    "Link",
    "Description",
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
    "Outcome",
    "Vote",
    "Amended",
    "Link",
    "Description",
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
    parser.add_argument("--exit-on-error", action="store_true",
        help="Stop processing meetings if there is an error")
    parser.add_argument("--num-meetings", type=int, default=0,
        help="The maximum number of meetings to process. Set 0 for no limit")
    parser.add_argument("--meeting",
        help="Process this specific meeting")
    parser.add_argument("--councillor-info",
        help="File with councillor info")
    parser.add_argument("--session", type=int,
        help="The session year. Defaults to most recent one found in councillor info file")
    parser.add_argument("-v", "--verbose", action="store_true",
        help="Be verbose")
    parser.add_argument("meetings_file",
        help="The html file containing meeting info")
    parser.add_argument("output_dir",
       help="Where to save all of the output files")

    return parser.parse_args()


@dataclass
class Meeting:
    body: str
    type: str
    other: str
    date: str
    time: str
    status: str
    id: str
    url: str
    agenda_summary: str
    agenda_packet: str
    final_actions: str
    minutes: str

    @property
    def uid(self):
        return f"{self.date} {self.type}"

    def __str__(self):
        return f"{self.body} - {self.type} {self.date}"

    def __repr__(self):
        return f"[Meeting {str(self)}]"


@dataclass
class CMA:
    uid:      str
    num:      int
    category: str
    awaiting: str
    order:    str
    url:      str
    action:   str
    vote:     str
    charter_right: str = ""
    description:   str = ""
    meeting_uid:   str = ""
    meeting_date:  str = ""
    notes:         str = ""

    @property
    def type(self):
        return "CMA"

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

    def setNotes(self, notes):
        self.notes = notes

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
            "Description":       self.description,
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
class Application:
    uid:      str
    num:      int
    category: str
    name:     str
    subject:  str
    url:      str
    action:   str
    vote:     str
    charter_right: str = ""
    meeting_uid:   str = ""
    meeting_date:  str = ""
    notes:         str = ""

    @property
    def type(self):
        return "APP"

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        msg = " ".join([self.uid, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + self.subject[:MAX_MSG_LEN] + "..."

        return msg + self.subject

    def setNotes(self, notes):
        self.notes = notes

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Name":              self.name,
            "Subject":           self.subject,
            "Outcome":           self.action,
            "Vote":              self.vote,
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
class Communication:
    uid:     str
    num:     int
    name:    str
    address: str
    subject: str
    url:     str
    meeting_uid:  str = ""
    meeting_date: str = ""
    notes:        str = ""

    @property
    def type(self):
        return "COM"

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        msg = " ".join([self.uid, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + self.subject[:MAX_MSG_LEN] + "..."

        return msg + self.subject

    def setNotes(self, notes):
        self.notes = notes

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
class Resolution:
    uid:      str
    num:      int
    category: str
    url:      str
    sponsor:  str
    cosponsors:   str = ""
    action:       str = ""
    vote:         str = ""
    description:  str = ""
    meeting_uid:  str = ""
    meeting_date: str = ""
    notes:        str = ""

    @property
    def type(self):
        return "RES"

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

    def setNotes(self, notes):
        self.notes = notes

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Link":              self.url,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Description":       self.description,
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
class PolicyOrder:
    uid:      str
    num:      int
    url:      str
    sponsor:  str
    cosponsors:    str = ""
    action:        str = ""
    vote:          str = ""
    amended:       str = ""
    charter_right: str = ""
    description:   str = ""
    meeting_uid:   str = ""
    meeting_date:  str = ""
    notes:         str = ""

    @property
    def type(self):
        return "POR"

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

    def setNotes(self, notes):
        self.notes = notes
        if "charter right" in self.notes.lower() and not self.charter_right:
            ## Some mistake has been made
            self.charter_right = "!!!"

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
            "Description":       self.description,
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
class AwaitingReport:
    uid: str
    url: str
    description:  str = ""
    department:   str = ""
    category:     str = ""
    policy_order: str = ""
    notes:        str = ""

    @property
    def type(self):
        return "AR"

    def setMeeting(self, meeting):
        pass

    def setNotes(self, notes):
        self.notes = notes

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


def print_red(msg):
    print(colored(msg, 'red'))


def print_green(msg):
    print(colored(msg, 'green'))


def expandUrl(base, url) -> str:
    """Expand a URL found from HTML"""
    if url[0] == '/':
        return os.path.join(base, url[1:])
    elif re.search(r"^\w+\.aspx", url):
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


def findText(node, tag, cls=None) -> str:
    """Find the text in a soup node"""
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


def buildRow(item, hdrs):
    """Make a csv row from an agenda item"""
    ## Every row dict must have exactly the keys in the header
    row = {}
    d = item.to_dict()
    for key in hdrs:
        if key in d and d[key] is not None:
            row[key] = str(d[key])
        else:
            row[key] = ""

    return row


_councillor_info = {}
_councillor_quick_lookup = {}
def setCouncillorInfo(path, year=None) -> bool:
    ## pylint: disable=too-many-return-statements,too-many-branches
    ## Load file
    all_info = None
    try:
        with open(path, 'r', encoding='utf8') as f:
            all_info = yaml.load(f)
    except Exception as e:
        print_red(f"Failed to councillor info file '{path}': {e}")
        return False

    ## Validation
    if 'sessions' not in all_info:
        print_red(f"Councillor info file missing 'sessions' key")
        return False
    if 'councillors' not in all_info:
        print_red(f"Councillor info file missing 'councillors' key")
        return False

    if year is None:
        year = max(all_info['sessions'])

    if year not in all_info['sessions']:
        print_red(f"Couldn't find year {year} in councillor info file {path}")
        return False

    session = all_info['sessions'][year]
    councillors = { x['name']: x for x in all_info['councillors'] }

    ## Set up mayor
    if 'mayor' not in session:
        print_red(f"Session year {year} doens't have a mayor")
        return False
    if session['mayor'] not in councillors:
        print_red(f"""Mayor "{session['mayor']}" not found in councillors list""")
        return False

    _councillor_info[session['mayor']] = dict(councillors[session['mayor']])
    _councillor_info[session['mayor']]['position'] = 'Mayor'

    ## Set up vice mayor
    if 'vice_mayor' not in session:
        print_red(f"Session year {year} doens't have a vice mayor")
        return False
    if session['vice_mayor'] not in councillors:
        print_red(f"""Vice Mayor "{session['vice_mayor']}" not found in councillors list""")
        return False

    _councillor_info[session['vice_mayor']] = dict(councillors[session['vice_mayor']])
    _councillor_info[session['vice_mayor']]['position'] = 'Vice Mayor'

    ## Set up councillors
    if 'councillors' not in session:
        print_red(f"Session year {year} doesn't have any councillors")
        return False

    for name in session['councillors']:
        if name not in councillors:
            print_red(f"Councillor {name} not found in councillors list")
            return False

        _councillor_info[name] = dict(councillors[name])
        _councillor_info[name]['position'] = "Councillor"

    ## Create quick lookups for every name combination
    for name, info in _councillor_info.items():
        position = info['position']
        aliases = [name, f"{position} {name}"]
        for alias in info['aliases']:
            aliases.append(alias)
            aliases.append(f"{position} {alias}")

        for alias in aliases:
            _councillor_quick_lookup[alias]         = name
            _councillor_quick_lookup[alias.lower()] = name

    ## Add names to headers
    ## pylint: disable=global-statement
    global CMA_HDRS, APP_HDRS, RES_HDRS, POR_HDRS
    ## CMA
    idx = CMA_HDRS.index("Vote") + 1
    CMA_HDRS = CMA_HDRS[:idx] + tuple(_councillor_info.keys()) + CMA_HDRS[idx:]

    ## APP
    idx = APP_HDRS.index("Vote") + 1
    APP_HDRS = APP_HDRS[:idx] + tuple(_councillor_info.keys()) + APP_HDRS[idx:]

    ## RES
    idx = RES_HDRS.index("Vote") + 1
    RES_HDRS = RES_HDRS[:idx] + tuple(_councillor_info.keys()) + RES_HDRS[idx:]

    ## POR
    idx = POR_HDRS.index("Vote") + 1
    POR_HDRS = POR_HDRS[:idx] + tuple(_councillor_info.keys()) + POR_HDRS[idx:]

    return True


def lookUpCouncillorName(name):
    ## Quick look up
    if name in _councillor_quick_lookup:
        return _councillor_quick_lookup[name]
    if name.lower() in _councillor_quick_lookup:
        return _councillor_quick_lookup[name.lower()]

    ## Remove title
    orig_name = name
    name = name.lower()
    name = name.replace("vice mayor", "").strip()
    name = name.replace("mayor", "").strip()
    name = name.replace("councilor", "").strip()
    if name in _councillor_quick_lookup:
        return _councillor_quick_lookup[name]

    print_red(f"""Didn't find full name for councillor "{orig_name}". Using fallback""")
    return name


def processKeyWordTable(table) -> Dict[str, str]:
    """Take a table from a city agenda item website and process it into a dictionary"""
    ths = []
    tds = []
    for row in table.find_all('tr'):
        ths.extend([x.text.strip().replace(':', '') for x in row.find_all('th')])
        tds.extend([x.text.strip().replace(':', '') for x in row.find_all('td')])

    return { x: y for x, y in zip(ths, tds) }


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


def findCharterRight(soup):
    header = findTag(soup, 'h1', 'LegiFileHeading').text
    match = re.search(r"charter right exercised by (?:councillor|vice mayor|mayor) (\w+) in\b", header, re.IGNORECASE)
    if match:
        return lookUpCouncillorName(match.groups()[0])

    return ""


def processItem(args, row, num):
    """Process a meeting agenda item"""
    ## Process the title and link
    title, link = findATag(row, 'td', 'Title')
    link = expandUrl(args.base_url, link)
    match = re.match(r"((CMA|APP|COM|RES|POR|COF) \d+ #\d+)\s(?:: )(.*)", title)
    if not match:
        ## Maybe it's an awaiting report
        match = re.match(r"(AR-\d+-\d+)\s(?:: )(.*)", title)
        if match:
            uid, description = match.groups()
            return AwaitingReport(uid, link, description)

        return None

    uid, itype, title = match.groups()

    ## Process the result
    result = findText(row, 'span', 'ItemVoteResult')
    action = result
    vote   = ""
    match = re.match(r"(?:order\s+)?(\w+(?: \w+)*)\s?(?:\[([^\]]+)\])?", result, re.IGNORECASE)
    if match:
        action, vote = match.groups()

    ## Action
    if action == "ADOPTED":
        action = "Adopted"
    elif action == "PLACED ON FILE":
        action = "Placed on File"
    elif action == "REFERRED TO COMMITTEE":
        action = "Referred to Committee"

    ## Init item type
    handlers = {
        'CMA': processCma,
        'APP': processApp,
        'COM': processCom,
        'RES': processRes,
        'POR': processPor,
    }
    if itype in handlers:
        return handlers[itype](args, uid, num, title, link, vote, action)

    return None


def processCma(args, uid, num, title, link, vote, action) -> CMA:
    """Process a CMA agenda item"""
    ## Fetch CMA page from city website
    cma_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, cma_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    charter_right = findCharterRight(soup)

    ## Category
    info_div = findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(findTag(info_div, 'table', 'LegiFileSectionContents'))
    category = table['Category']

    ## Origins if any
    awaiting = ""
    order = ""
    links = processResLinks(soup)
    if 'origin' in links:
        for o_name, _ in links['origin']:
            match = re.search(r"^(AR\S+)\s+:", o_name)
            if match:
                awaiting = match.groups()[0]
            match = re.search(r"^(POR \d+ #\d+)\s+:", o_name)
            if match:
                order = match.groups()[0]

    return CMA(uid, num, category, awaiting, order, link, action, vote, charter_right, title)


def processApp(args, uid, num, title, link, vote, action) -> Application:
    """Process an application agenda item"""
    ## pylint: disable=unused-argument
    app_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, app_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    charter_right = findCharterRight(soup)
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))
    category = table['Category']

    ## Attempt to get the name
    name    = ""
    subject = ""
    match = re.search(r"An application was received from (.+?),? (requesting permission .+)", title)
    if match:
        name, subject = match.groups()
    else:
        subject = title

    return Application(uid, num, category, name, subject, link, action, vote, charter_right)


def processCom(args, uid, num, title, link, vote, action) -> Communication:
    """Process a communication agenda item"""
    ## pylint: disable=unused-argument
    name    = ""
    subject = ""
    address = ""

    ## Attempt to match the name of a person
    match = re.search(r"A communication was received from (.+?)(?:, (\d.+?))?,? regarding (.+)", title)
    if match:
        name, address, subject = match.groups()
        address = address or ""

    ## Attempt to match 'Sundry'
    match = re.search(r"Sundry communications were received regarding(?:,)? (.+)", title)
    if match:
        name = 'Sundry'
        subject = match.groups()[0]

    ## Backup
    if not subject:
        subject = title

    return Communication(uid, num, name, address, subject, link)


def processRes(args, uid, num, title, link, vote, action) -> Resolution:
    """Process a resolution agenda item"""
    ## Fetch Res page from city website
    res_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, res_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))
    category = table['Category']
    sponsors = [lookUpCouncillorName(x.strip()) for x in table['Sponsors'].split(',')]
    return Resolution(uid, num, category, link, sponsors[0], sponsors[1:], action, vote, title)


def processPor(args, uid, num, title, link, vote, action) -> PolicyOrder:
    """Process a policy order agenda item"""
    ## Fetch Res page from city website
    por_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, por_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))
    sponsors = [lookUpCouncillorName(x.strip()) for x in table['Sponsors'].split(',')]
    charter_right = findCharterRight(soup)

    ## Amended
    amended = ""
    if action == "Adopted as Amended":
        amended = "Yes"
        action = "Adopted"

    return PolicyOrder(uid, num, link, sponsors[0], sponsors[1:], action, vote, amended, charter_right, title)


def processAr(args, item):
    ## Fetch AR page from the city website
    ar_path = os.path.join(args.cache_dir, f"{uidToFileSafe(item.uid)}.html")
    fetched = fetchUrl(item.url, ar_path)
    soup = BeautifulSoup(fetched, 'html.parser')

    ## Additional info
    info_div = findTag(soup, 'div', 'LegiFileInfo')
    table = processKeyWordTable(findTag(info_div, 'table', 'LegiFileSectionContents'))
    category   = table['Category']
    department = table['Department']

    ## Origin if any
    order = ""
    links = processResLinks(soup)
    if 'origin' in links:
        for o_name, _ in links['origin']:
            match = re.search(r"^(POR \d+ #\d+)\s+:", o_name)
            if match:
                order = match.groups()[0]
                break

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
        writer.writerow(buildRow(item, AR_HDRS))
        total += 1

    print_green(f"Wrote {total} awaiting reports")


def processMeeting(args, meeting) -> Dict[str, List[Any]]:
    """Process a meeting"""
    meeting_path = os.path.join(args.cache_dir, f"meeting_{meeting.id}.html")
    soup = BeautifulSoup(fetchUrl(meeting.url, meeting_path, verbose=True), 'html.parser')

    ## Iterate through agenda table
    table = soup.find('table', {'class': 'MeetingDetail'})
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
            if not enabled and title in ("City Manager's Agenda", "Communications", "Resolutions", "Policy Order and Resolution List", "Applications and Petitions"):
                if VERBOSE:
                    print(f"""Found section "{title}". Enable agenda item processing""")
                enabled = True
                continue
            elif enabled and title in ("Charter Right", "Calendar"):
                if VERBOSE:
                    print(f"""Found section "{title}". Disable agenda item processing""")

                enabled = False
                continue

        if not enabled:
            continue

        ## Look for agenda item number
        td = findTag(row, 'td', 'Num')
        if td is not None and re.match(r"\d+\.?", td.text.strip()):
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


def fetchUrl(url, cache_path=None, *, verbose=False) -> str:
    """Fetch the data from a URL. Optionally cache it locally to disk"""
    if cache_path is not None and os.path.isfile(cache_path):
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


def postProcessItems(writers, items):
    sets = (
        ('CMA', CMA_HDRS),
        ('APP', APP_HDRS),
        ('COM', COM_HDRS),
        ('RES', RES_HDRS),
        ('POR', POR_HDRS),
    )
    for key, hdrs in sets:
        for item in items[key]:
            writers[key].writerow(buildRow(item, hdrs))

    types = [x for x, y in sets]
    msg = " ".join([f"{k}:{len(v)}" for k, v in items.items() if k in types])
    total = sum([len(v) for k, v in items.items() if k in types])
    print_green(f"Wrote {total} items. {msg}")


def setupOutputFiles(output_dir):
    ## Open output files
    files   = {}
    writers = {}
    sets = (
        ('CMA', CMA_HDRS, "cma.csv"),
        ('APP', APP_HDRS, "applications_and_petitions.csv"),
        ('COM', COM_HDRS, "communications.csv"),
        ('RES', RES_HDRS, "resolutions.csv"),
        ('POR', POR_HDRS, "policy_orders.csv"),
        ('AR',  AR_HDRS,  "awaiting_reports.csv"),
    )
    for key, hdrs, name in sets:
        path = os.path.join(output_dir, name)
        try:
            f = open(path, 'w', encoding='utf8')
            w = csv.DictWriter(f, fieldnames=hdrs)
            w.writeheader()
            files[key]   = f
            writers[key] = w
        except Exception as e:
            print_red(f"Failed to open file '{path}' for writing: {e}")
            return None

    return (files, writers)


def main(args):
    ## pylint: disable=too-many-branches
    if args.verbose:
        global VERBOSE ## pylint: disable=global-statement
        VERBOSE = args.verbose

    ## Set councillor info
    if args.councillor_info is not None:
        if not setCouncillorInfo(args.councillor_info, args.session):
            print_red(f"Failed to set up councillor info")
            return 1

    ## Open meetings file
    meetings = []
    with open(args.meetings_file, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            meetings.append(Meeting(**{ k.lower().replace(' ', '_'): v for k, v in row.items() }))

    print(f"Read {len(meetings)} meetings from '{args.meetings_file}'")
    print("Opening output files")
    output_files, writers = setupOutputFiles(args.output_dir)
    if output_files is None:
        return 1

    ## Process each meeting
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
            postProcessItems(writers, items)
            if 'AR' in items:
                processNewArs(args, ar_map, items['AR'], writers['AR'])

            ## Maybe end processing now
            if args.meeting:
                break

            num += 1
            if args.num_meetings and num >= args.num_meetings:
                break
        except KeyboardInterrupt:
            print(f"User requested exit")
            break
        except Exception as e:
            print_red(f"Error: Failed to process meeting '{meeting}': {e}")
            if args.exit_on_error:
                ## Close all files
                for f in output_files.values():
                    f.close()
                raise e


    ## Close files
    for f in output_files.values():
        f.close()

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
