#!/usr/bin/env python3

import argparse
import csv
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

CMA_SECTIONS = ['Reports and Communications', 'Appropriations and Grants', 'Appointments']

ITEM_RE = re.compile(r'^- #\d+ \(([A-Z]+ \d{4}-\d+)\) (.+)$')


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
    parser.add_argument('--summarize', action='store_true',
        help='Rewrite item summaries using Claude to be more concise and natural')
    parser.add_argument('--examples',
        help='Directory of summary markdown files to use as style examples with --summarize')
    parser.add_argument('--verbose', '-v', action='store_true',
        help='Print the Claude prompt to stderr')
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


def load_uid_summaries(search_dir) -> Dict[str, str]:
    """Walk the processed data directory tree and build a UID → raw summary map."""
    uid_map: Dict[str, str] = {}
    for dirpath, _, filenames in os.walk(search_dir):
        for fname in filenames:
            if not fname.endswith('.csv'):
                continue
            try:
                with open(os.path.join(dirpath, fname), encoding='utf8') as f:
                    for row in csv.DictReader(f):
                        uid = row.get('Unique Identifier', '').strip()
                        summary = row.get('Summary', '').strip()
                        if uid and summary:
                            uid_map[uid] = summary
            except Exception:
                continue
    return uid_map


def load_examples(summaries_dir, uid_map: Dict[str, str], max_examples: int = 12) -> List[Tuple[Optional[str], str]]:
    """Extract (raw, written) pairs from recent summary markdown files."""
    files = sorted(
        [f for f in os.listdir(summaries_dir) if re.match(r'\d{4}-\d{2}-\d{2}\.md$', f)],
        reverse=True,
    )
    examples: List[Tuple[Optional[str], str]] = []
    seen_uids: set = set()
    for fname in files:
        if len(examples) >= max_examples:
            break
        with open(os.path.join(summaries_dir, fname), encoding='utf8') as f:
            for line in f:
                m = ITEM_RE.match(line.strip())
                if not m:
                    continue
                uid, written = m.group(1), m.group(2)
                if uid in seen_uids:
                    continue
                seen_uids.add(uid)
                examples.append((uid_map.get(uid), written))
                if len(examples) >= max_examples:
                    break
    return examples


def build_summarize_prompt(examples: List[Tuple[Optional[str], str]]) -> str:
    lines = [
        "Rewrite Cambridge City Council agenda item descriptions to be concise and natural. "
        'Use plain English, sentence case, and omit procedural boilerplate like '
        '"the City Manager is requested to". '
        "Return only the rewritten text, no trailing punctuation, nothing else.",
        "",
    ]
    if examples:
        lines.append("Examples of the desired writing style:")
        lines.append("")
        for raw, written in examples:
            if raw:
                lines.append(f"Original: {raw}")
                lines.append(f"Rewritten: {written}")
            else:
                lines.append(f"Example: {written}")
            lines.append("")
    return "\n".join(lines)


def rewrite_summary(client: Any, text, prompt: str) -> str:
    full = prompt + f"Original: {text}\nRewritten:"
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": full}],
    )
    return response.content[0].text.strip()


def rewrite_item_summaries(client: Any, items: List[Dict], prompt: str) -> List[Dict]:
    result = []
    for row in items:
        row = dict(row)
        if row.get('Summary'):
            row['Summary'] = rewrite_summary(client, row['Summary'], prompt)
        result.append(row)
    return result


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


def generate_summary(directory, date, meeting_url, summary_length: int,
                     client: Any = None, summarize_prompt: str = '') -> str:
    cmas = load_items(directory, 'cma.csv', date)
    pors = load_items(directory, 'policy_orders.csv', date)
    apps = load_items(directory, 'applications_and_petitions.csv', date)

    # Classify on original summaries before any rewriting
    cma_sections = build_cma_sections(cmas)
    charter_rights, por_city, por_council = split_pors(pors)

    if client is not None:
        rewrite = lambda items: rewrite_item_summaries(client, items, summarize_prompt)
        cma_sections = {k: rewrite(v) for k, v in cma_sections.items()}
        charter_rights = rewrite(charter_rights)
        por_city = rewrite(por_city)
        por_council = rewrite(por_council)
        apps = rewrite(apps)
        summary_length = sys.maxsize

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


def build_client_and_prompt(args: argparse.Namespace) -> Tuple[Any, str]:
    import anthropic
    client = anthropic.Anthropic()
    examples: List[Tuple[Optional[str], str]] = []
    if args.examples:
        uid_map = load_uid_summaries(args.directory)
        examples = load_examples(args.examples, uid_map)
    return client, build_summarize_prompt(examples)


def main():
    args = make_parser().parse_args()

    meeting_url = load_meeting_url(args.meetings, args.date)
    if meeting_url is None:
        print(f"Warning: no meeting found for date {args.date}", file=sys.stderr)

    client, summarize_prompt = None, ''
    if args.summarize:
        client, summarize_prompt = build_client_and_prompt(args)
        if args.verbose:
            print(summarize_prompt, file=sys.stderr)

    content = generate_summary(
        args.directory, args.date, meeting_url,
        args.summary_length, client, summarize_prompt,
    )

    if args.output:
        with open(args.output, 'w', encoding='utf8') as f:
            f.write(content)
    else:
        print(content)


if __name__ == '__main__':
    main()
