#! /usr/bin/python3

import argparse
import csv
import datetime as dt
import os
import re
import sys

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="https://cambridgema.iqm2.com",
        help="The base URL")
    parser.add_argument("meetings_file",
        help="The html file containing meeting info")
    parser.add_argument("output_file", nargs='?',
        help="The output csv file. Print to stdout otherwise")
    return parser.parse_args()


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


def parseMeeting(args, meeting_row):
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

    ## Extract the date and main link
    date, url = findATag(meeting_row, 'RowLink')
    date = getDate(date)
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

    ## Return all data
    data = {
        'Body':           body,
        'Type':           mtype,
        'Other':          other,
        'Date':           date.strftime("%x"),
        'Time':           date.strftime("%I:%M %p"),
        'Status':         status,
        'Id':             m_id,
        'url':            url,
        'Agenda Summary': links['Agenda Summary'],
        'Agenda Packet':  links['Agenda Packet'],
        'Final Actions':  links['Final Actions'],
        'Minutes':        links['Minutes'],
    }
    return data


def writeCsv(f, rows):
    headers = (
        'Body', 'Type', 'Other', 'Date', 'Time', 'Status', 'Id', 'url',
        'Agenda Summary', 'Agenda Packet', 'Final Actions', 'Minutes',
    )
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)


def main(args):
    soup = None
    with open(args.meetings_file, 'r', encoding='utf8') as f:
        soup = BeautifulSoup(f.read(), 'html5lib')

    ## Find all the meetings
    meetings = soup.find_all('div', {'class': 'MeetingRow'})
    data = []
    for meeting_row in meetings:
        data.append(parseMeeting(args, meeting_row))

    if args.output_file:
        with open(args.output_file, 'w', encoding='utf8') as f:
            writeCsv(f, data)
    else:
        writeCsv(sys.stdout, data)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
