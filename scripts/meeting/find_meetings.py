#! /usr/bin/python3

import argparse
import csv
import datetime as dt
import os
import re
import sys

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

## https://cambridgema.iqm2.com/Citizens/Calendar.aspx?From=1/1/2020&To=12/31/2021

PRIMEGOV_BASE = "https://cambridgema.primegov.com"
CITY_COUNCIL_COMMITTEE_ID = 1
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}
CSV_HEADERS = (
    'Unique Identifier',
    'Body', 'Type', 'Other', 'Session', 'Date', 'Time', 'Status', 'Id', 'url',
    'Agenda Summary', 'Agenda Packet', 'Final Actions', 'Minutes',
)


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://cambridgema.iqm2.com",
        help="The base URL (IQM2 mode only)")
    parser.add_argument("--council-only", action="store_true",
        help="Only get council meetings")
    parser.add_argument("--primegov", action="store_true",
        help="Fetch meetings from the PrimeGov API instead of a local HTML file")
    parser.add_argument("--year", type=int, default=dt.date.today().year,
        help="Year to fetch archived meetings for (PrimeGov mode only)")
    parser.add_argument("meetings_file", nargs='?',
        help="The html file containing meeting info (IQM2 mode only)")
    parser.add_argument("output_file", nargs='?',
        help="The output csv file. Print to stdout otherwise")
    return parser.parse_args()


## ── IQM2 mode ─────────────────────────────────────────────────────────────────

def getDate(date):
    try:
        return dt.datetime.strptime(date, "%b %d, %Y %I:%M %p")
    except ValueError:
        return dt.datetime.strptime(date, "%b %d, %Y")


def findATag(div, cls=None):
    if cls is not None:
        div = div.find('div', {'class': cls})

    a_tag = div.find('a')
    return (a_tag.text.strip(), a_tag['href'])


def findAllATags(div, cls=None):
    if cls is not None:
        div = div.find('div', {'class': cls})

    if div is None:
        return []

    a_tags = div.find_all('a')
    if a_tags is None:
        return []

    return [(a_tag.text.strip(), a_tag['href']) for a_tag in a_tags]


def parseMeetingIqm2(args, meeting_row) -> dict:
    ## Get meeting type
    details_txt = meeting_row.find('div', {'class': 'RowDetails'}).text.strip()
    details     = details_txt.split(' - ')
    body        = details[0]
    mtype       = details[1].replace(" Meeting", "")
    other       = ''
    status      = 'completed'
    m_id        = ''
    if len(details) > 2:
        other = " - ".join(details[2:])

    ## Filter
    if (args.council_only and body != "City Council") or mtype == "TEST MEETING":
        return None

    ## Extract the date and main link
    date, url = findATag(meeting_row, 'RowLink')
    date = getDate(date)
    session = date.year
    if args.base_url not in url and url[0] == '/':
        url = os.path.join(args.base_url, url[1:])

    match = re.search(r"Detail_Meeting.aspx\?.*\bID=(\d+)", url, re.IGNORECASE)
    if match:
        m_id = match.groups()[0]

    ## Get other links
    links = { x: y for x, y in findAllATags(meeting_row, 'MeetingLinks') }
    if meeting_row.find('span', {'class': 'MeetingCancelled'}) is not None:
        status = 'cancelled'

    for name in ('Agenda Summary', 'Agenda Packet', 'Final Actions', 'Minutes'):
        if name not in links:
            links[name] = ''
        elif "FileOpen" == links[name][:8]:
            links[name] = os.path.join(args.base_url, 'Citizens', links[name])
        elif links[name] and links[name][0] == '/':
            links[name] = os.path.join(args.base_url, 'Citizens', links[name])

    ## Clean data
    date_str = date.strftime("%Y-%m-%d")
    if mtype == "Hearing ‚Äì Remote":
        mtype = "Hearing - Remote"
    if mtype == "Roundtable/Working":
        mtype = "Roundtable"
    if "Committee" in body and mtype == "Regular":
        mtype = "Committee"
    if date > dt.datetime.now():
        status = "scheduled"

    return {
        'Unique Identifier': f"{date_str} {mtype}",
        'Body':           body,
        'Type':           mtype,
        'Other':          other,
        'Session':        session,
        'Date':           date_str,
        'Time':           date.strftime("%I:%M %p"),
        'Status':         status,
        'Id':             m_id,
        'url':            url,
        'Agenda Summary': links['Agenda Summary'],
        'Agenda Packet':  links['Agenda Packet'],
        'Final Actions':  links['Final Actions'],
        'Minutes':        links['Minutes'],
    }


def mainIqm2(args):
    if not args.meetings_file:
        print("Error: meetings_file is required in IQM2 mode", file=sys.stderr)
        return 1

    soup = None
    with open(args.meetings_file, 'r', encoding='utf8') as f:
        soup = BeautifulSoup(f.read(), 'html5lib')

    meetings = soup.find_all('div', {'class': 'MeetingRow'})
    data = []
    for meeting_row in meetings:
        meeting = parseMeetingIqm2(args, meeting_row)
        if meeting is not None:
            data.append(meeting)

    writeCsv(sys.stdout if not args.output_file else open(args.output_file, 'w', encoding='utf8'), data)
    return 0


## ── PrimeGov mode ─────────────────────────────────────────────────────────────

def _primegov_doc_url(meeting_json, template_name: str) -> str:
    """Return the HTML compiled-document URL for the given template name, or ''."""
    for doc in meeting_json.get('documentList', []):
        if doc.get('templateName') == template_name and doc.get('compileOutputType') == 3:
            return f"{PRIMEGOV_BASE}/Portal/Meeting?meetingTemplateId={doc['templateId']}"
    return ''


def fetchPrimegovMeetings(year: int):
    """Fetch City Council meetings from the PrimeGov API for the given year."""
    import requests  ## pylint: disable=import-outside-toplevel
    meetings = []

    archived_url = (
        f"{PRIMEGOV_BASE}/api/v2/PublicPortal/ListArchivedMeetings"
        f"?committeeId={CITY_COUNCIL_COMMITTEE_ID}&year={year}"
    )
    resp = requests.get(archived_url, headers=REQUEST_HDR)
    resp.raise_for_status()
    meetings.extend(resp.json())

    upcoming_url = f"{PRIMEGOV_BASE}/api/v2/PublicPortal/ListUpcomingMeetings"
    resp = requests.get(upcoming_url, headers=REQUEST_HDR)
    resp.raise_for_status()
    for m in resp.json():
        if m.get('committeeId') == CITY_COUNCIL_COMMITTEE_ID:
            meetings.append(m)

    return meetings


def _classify_meeting_title(title: str) -> str:
    """Map a PrimeGov meeting title to a meeting type string."""
    t = title.lower()
    if 'do not use' in t:
        return None
    if 'special' in t:
        return 'Special'
    if 'inaugural' in t:
        return 'Inaugural'
    if 'executive session' in t:
        return 'Executive Session'
    if 'roundtable' in t or 'round table' in t or 'working' in t:
        return 'Roundtable'
    if 'hearing' in t:
        return 'Hearing'
    return 'Regular'


def parseMeetingPrimegov(meeting_json) -> dict:
    """Convert a PrimeGov meeting JSON object into a CSV-row dict.
    Returns None for meetings that should be skipped.
    """
    title = meeting_json.get('title', '')
    mtype = _classify_meeting_title(title)
    if mtype is None:
        return None

    meeting_dt = dt.datetime.fromisoformat(meeting_json['dateTime'])
    date_str   = meeting_dt.strftime('%Y-%m-%d')
    time_str   = meeting_dt.strftime('%I:%M %p')
    session    = meeting_dt.year

    meeting_state = meeting_json.get('meetingState', 0)
    status = 'scheduled'
    if 'cancelled' in title.lower():
        status = 'cancelled'
    elif meeting_dt <= dt.datetime.now() and meeting_state == 3:
        status = 'completed'

    url_agenda = _primegov_doc_url(meeting_json, 'HTML Agenda')
    url_final  = _primegov_doc_url(meeting_json, 'HTML Final Actions')
    url_packet = _primegov_doc_url(meeting_json, 'HTML Packet')

    return                   {
        'Unique Identifier': f"{date_str} {mtype}",
        'Body':              'City Council',
        'Type':              mtype,
        'Other':             '',
        'Session':           session,
        'Date':              date_str,
        'Time':              time_str,
        'Status':            status,
        'Id':                str(meeting_json['id']),
        'url':               url_agenda,
        'Agenda Summary':    url_agenda,
        'Agenda Packet':     url_packet,
        'Final Actions':     url_final,
        'Minutes':           '',
    }


def mainPrimegov(args):
    meetings_json = fetchPrimegovMeetings(args.year)

    ## Filter to City Council only (the API does not filter server-side)
    council = [m for m in meetings_json if m.get('committeeId') == CITY_COUNCIL_COMMITTEE_ID]
    data = [parseMeetingPrimegov(m) for m in council]
    data = [r for r in data if r is not None]

    ## Deduplicate by Unique Identifier (archived + upcoming may overlap)
    seen = set()
    unique = []
    for row in data:
        key = row['Unique Identifier']
        if key not in seen:
            seen.add(key)
            unique.append(row)

    ## Sort by date
    unique.sort(key=lambda r: r['Date'])

    f = open(args.output_file, 'w', encoding='utf8') if args.output_file else sys.stdout
    writeCsv(f, unique)
    return 0


## ── shared ────────────────────────────────────────────────────────────────────

def writeCsv(f, rows):
    writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
    writer.writeheader()
    writer.writerows(rows)


def main(args):
    if args.primegov:
        return mainPrimegov(args)
    return mainIqm2(args)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
