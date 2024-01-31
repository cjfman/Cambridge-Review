#! /usr/bin/python3.8

import argparse
import csv
import os
import re
import sys

import requests
from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

VERBOSE = False
ALLOWED_TYPES = ('regular', 'special')
MAX_MSG_LEN = 48
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

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
    url:      str
    action:   str = ""
    vote:     str = ""
    description:  str = ""
    meeting_uid:  str = ""
    meeting_date: str = ""
    notes:        str = ""

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

    def setNotes(self, notes):
        self.notes = notes

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
    meeting_uid:  str = ""
    meeting_date: str = ""

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        msg = " ".join([self.uid, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + self.subject[:MAX_MSG_LEN] + "..."

        return msg + self.subject

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self):
        return f"[Application: {str(self)}]"


@dataclass
class Communication:
    uid: str
    num: int
    name: str
    address: str
    subject: str
    link: str
    meeting_uid:  str = ""
    meeting_date: str = ""

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        msg = " ".join([self.uid, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + self.subject[:MAX_MSG_LEN] + "..."

        return msg + self.subject

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

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

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
    cosponsors:   str = ""
    action:       str = ""
    vote:         str = ""
    description:  str = ""
    meeting_uid:  str = ""
    meeting_date: str = ""

    def setMeeting(self, meeting):
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date

    def __str__(self):
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
        return f"[Resolution: {str(self)}]"



def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://cambridgema.iqm2.com",
        help="The base URL")
    parser.add_argument("--cache-dir", required=True,
        help="Where to cache downloads from the city website")
    parser.add_argument("--exit-on-error", action="store_true",
        help="Stop processing meetings if there is an error")
    parser.add_argument("--num-meetings", type=int, default=0,
        help="The maximum number of meetings to process. Set 0 for no limit")
    parser.add_argument("meetings_file",
        help="The html file containing meeting info")
#    parser.add_argument("output_dir",
#        help="Where to save all of the output files")

    return parser.parse_args()


def expandUrl(base, url):
    if url[0] == '/':
        return os.path.join(base, url[1:])
    elif re.search(r"^\w+\.aspx", url):
        return os.path.join(base, 'Citizens', url)

    return url


def findTag(con, tag, cls=None):
    if cls is None:
        return con.find(tag)

    return con.find(tag, {'class': cls})


def findATag(con, tag=None, cls=None):
    if tag is not None:
        con = findTag(con, tag, cls)
    if con is None:
        raise Exception(f"Couldn't find a '{tag}' tag")

    a_tag = con.find('a')
    if a_tag is None:
        raise Exception("Couldn't find an 'a' tag")

    return (a_tag.text.strip(), a_tag['href'])


def findText(con, tag, cls=None):
    found = findTag(con, tag, cls)
    if found is None:
        return ''

    return found.text.strip()


def uidToFileSafe(uid):
    return uid.replace(' ', '_').replace('#', 'no')


def processKeyWordTable(table):
    ths = []
    tds = []
    for row in table.find_all('tr'):
        ths.extend([x.text.strip().replace(':', '') for x in row.find_all('th')])
        tds.extend([x.text.strip().replace(':', '') for x in row.find_all('td')])

    return { x: y for x, y in zip(ths, tds) }


def processItem(args, row, num):
    ## Process the title and link
    title, link = findATag(row, 'td', 'Title')
    link = expandUrl(args.base_url, link)
    match = re.match(r"((CMA|APP|COM|RES|POR|COF) \d+ #\d+)(?: : )(.*)", title)
    if not match:
        return None

    uid, itype, title = match.groups()

    ## Process the result
    result = findText(row, 'span', 'ItemVoteResult')
    action = result
    vote   = ""
    match = re.match(r"(?:order\s+)?(\w+(?: \w+)*)\s?(?:\[([^\]]+)\])?", result, re.IGNORECASE)
    if match:
        action, vote = match.groups()

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


def processCma(args, uid, num, title, link, vote, action):
    ## Fetch CMA page from city website
    cma_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, cma_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))

    return CMA(uid, num, table['Category'], link, action, vote, title)


def processApp(args, uid, num, title, link, vote, action):
    ## pylint: disable=unused-argument
    app_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, app_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))

    ## Attempt to get the name
    name    = ""
    subject = ""
    match = re.search(r"An application was received from (.+?),? (requesting permission .+)", title)
    if match:
        name, subject = match.groups()
    else:
        subject = title

    return Application(uid, num, table['Category'], name, subject, link)


def processCom(args, uid, num, title, link, vote, action):
    ## pylint: disable=unused-argument
    ## Attempt to get the name
    name    = ""
    subject = ""
    address = ""
    match = re.search(r"A communication was received from (.+?)(?:, (\d.+?))?,? regarding (.+)", title)
    if match:
        name, address, subject = match.groups()
        address = address or ""
    else:
        subject = title

    return Communication(uid, num, name, address, subject, link)


def processRes(args, uid, num, title, link, vote, action):
    ## Fetch Res page from city website
    cma_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, cma_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))
    category = table['Category']
    sponsors = table['Sponsors'].split(',')
    return Resolution(uid, num, category, link, sponsors[0], sponsors[1:], action, vote, title)


def processPor(args, uid, num, title, link, vote, action):
    ## Fetch Res page from city website
    cma_path = os.path.join(args.cache_dir, f"{uidToFileSafe(uid)}.html")
    fetched = fetchUrl(link, cma_path)
    soup = BeautifulSoup(fetched, 'html.parser')
    table = processKeyWordTable(findTag(soup, 'table', 'LegiFileSectionContents'))
    sponsors = table['Sponsors'].split(',')
    return PolicyOrder(uid, num, link, sponsors[0], sponsors[1:], action, vote, title)


def processMeeting(args, meeting):
    meeting_path = os.path.join(args.cache_dir, f"meeting_{meeting.id}.html")
    soup = BeautifulSoup(fetchUrl(meeting.url, meeting_path), 'html.parser')

    ## Iterate through agenda table
    table = soup.find('table', {'class': 'MeetingDetail'})
    item  = None
    items = []
    rows = table.find_all('tr')
    print(f"Checking {len(rows)} rows")
    for row in rows:
        ## Look for agenda item number
        td = findTag(row, 'td', 'Num')
        if td is not None and re.match(r"\d+\.?", td.text.strip()):
            num = td.text.strip().replace('.', '')
            item = processItem(args, row, num)
            if item is not None:
                items.append(item)
        elif item is not None:
            ## Look for comments
            td = findTag(row, 'Comments')
            if td is not None:
                ## Set comment for most recent item
                items[-1].setNotes(findText(td, 'span'))
        elif td is not None:
            if VERBOSE:
                print(f"Tag td didn't match anything: {td.text}")
        else:
            if VERBOSE:
                print(f"Couldn't find a td with class 'Num'")

    print(f"Found {len(items)} for meeting '{meeting}'")
    for item in items:
        item.setMeeting(meeting)
        print(item)

    return items


def fetchUrl(url, cache_path=None):
    if cache_path is not None and os.path.isfile(cache_path):
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


def main(args):
    ## Open meetings file
    meetings = []
    with open(args.meetings_file, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            meetings.append(Meeting(**{ k.lower().replace(' ', '_'): v for k, v in row.items() }))

    print(f"Read {len(meetings)} meetings from '{args.meetings_file}'")

    ## Process each meeting
    num = 0
    for meeting in meetings:
        try:
            if meeting.body.lower() != 'city council' or meeting.type.lower() not in ALLOWED_TYPES:
                print(f"Skipping meeting '{meeting}'")
                continue

            print(f"Processing meeting '{meeting}'")
            processMeeting(args, meeting)

            ## Finalize
            num += 1
            if args.num_meetings and num >= args.num_meetings:
                break
        except Exception as e:
            print(f"Failed to process meeting '{meeting}': {e}")
            if args.exit_on_error:
                raise e

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
