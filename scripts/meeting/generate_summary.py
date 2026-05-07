#!/usr/bin/env python3

import argparse
import csv
import os
import re
import sys
from typing import Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

CMA_SECTIONS = ['Reports and Communications', 'Appropriations and Grants', 'Appointments']


def make_parser():
    parser = argparse.ArgumentParser(
        description='Generate a meeting summary skeleton from agenda item CSVs'
    )
    parser.add_argument('directory', help='Directory containing agenda item CSVs')
    parser.add_argument('--date', required=True, help='Meeting date (YYYY-MM-DD)')
    parser.add_argument('--meetings', required=True, help='Path to meetings CSV')
    parser.add_argument('--output', '-o', help='Output file (default: stdout)')
    parser.add_argument('--summary-length', '-s', type=int, default=100,
        help='Characters of item summary to include (default: 100)')
    return parser


def load_meeting_url(meetings_path, date) -> Optional[str]:
    with open(meetings_path, encoding='utf8') as f:
        for row in csv.DictReader(f):
            if row['Date'] == date:
                return row['url']
    return None


def classify_cma(summary) -> str:
    s = summary.lower()
    if re.search(r'\bappointments?\b|\breappointments?\b', s):
        return 'Appointments'
    if re.search(r'\bappropriation\b|\btransfer\b', s):
        return 'Appropriations and Grants'
    return 'Reports and Communications'


def classify_por(summary) -> str:
    s = summary.lower()
    if ('city manager' in s or 'city staff' in s) and re.search(r'\brequest', s):
        return 'Requests that the city...'
    return 'That the council...'


def load_items(directory, filename, date) -> List[Dict]:
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        return []
    items = []
    with open(path, encoding='utf8') as f:
        for row in csv.DictReader(f):
            if row.get('Meeting Date') == date:
                items.append(row)
    return sorted(items, key=lambda r: int(r.get('Agenda Number') or 0))


def truncate_summary(summary, length: int) -> str:
    if not summary or length <= 0:
        return ''
    if len(summary) <= length:
        return summary
    truncated = summary[:length].rsplit(' ', 1)[0]
    return truncated + '...'


def format_item(uid, agenda_num, summary, summary_length: int) -> str:
    text = truncate_summary(summary, summary_length)
    suffix = f" {text}" if text else ''
    return f"- #{agenda_num} ({uid}){suffix}"


def render_section(lines: List[str], header, items: Iterable[Dict], summary_length: int):
    lines.append(header)
    for row in items:
        lines.append(format_item(
            row['Unique Identifier'], row['Agenda Number'],
            row.get('Summary', ''), summary_length,
        ))


def build_cma_sections(cmas: List[Dict]) -> Dict[str, List[Dict]]:
    sections: Dict[str, List[Dict]] = {s: [] for s in CMA_SECTIONS}
    for row in cmas:
        section = classify_cma(row.get('Summary', ''))
        sections[section].append(row)
    return sections


def split_pors(pors: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    charter, city, council = [], [], []
    for row in pors:
        if row.get('Charter Right', '').strip():
            charter.append(row)
        elif classify_por(row.get('Summary', '')) == 'Requests that the city...':
            city.append(row)
        else:
            council.append(row)
    return charter, city, council


def generate_summary(directory, date, meeting_url, summary_length: int) -> str:
    cmas = load_items(directory, 'cma.csv', date)
    pors = load_items(directory, 'policy_orders.csv', date)
    apps = load_items(directory, 'applications_and_petitions.csv', date)

    cma_sections = build_cma_sections(cmas)
    charter_rights, por_city, por_council = split_pors(pors)

    lines: List[str] = []
    lines.append(f"[Meeting Link]({meeting_url or ''})")
    lines.append("")
    lines.append("Note: Some agenda item links may not work until after the meeting has completed")
    lines.append("")
    lines.append("## City Manager's Agenda")
    lines.append("")
    for section in CMA_SECTIONS:
        render_section(lines, f"### {section}", cma_sections[section], summary_length)
        lines.append("")

    lines.append("")
    lines.append("## Policy Orders")
    render_section(lines, "### Requests that the city...", por_city, summary_length)
    render_section(lines, "### That the council...", por_council, summary_length)
    lines.append("")
    lines.append("")
    lines.append("## Charter Rights")
    for row in charter_rights:
        lines.append(format_item(
            row['Unique Identifier'], row['Agenda Number'],
            row.get('Summary', ''), summary_length,
        ))
    lines.append("")
    lines.append("")
    lines.append("## Applications and Petitions")
    for row in apps:
        lines.append(format_item(
            row['Unique Identifier'], row['Agenda Number'],
            row.get('Summary', ''), summary_length,
        ))
    lines.append("")

    return "\n".join(lines)


def main():
    args = make_parser().parse_args()

    meeting_url = load_meeting_url(args.meetings, args.date)
    if meeting_url is None:
        print(f"Warning: no meeting found for date {args.date}", file=sys.stderr)

    content = generate_summary(args.directory, args.date, meeting_url, args.summary_length)

    if args.output:
        with open(args.output, 'w', encoding='utf8') as f:
            f.write(content)
    else:
        print(content)


if __name__ == '__main__':
    main()
