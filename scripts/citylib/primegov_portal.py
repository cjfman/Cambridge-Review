## pylint: disable=too-many-branches,too-many-locals
import os
import re

from collections import defaultdict
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup

from citylib import agenda
from citylib.councillors import lookUpCouncillorName
from citylib.utils import print_red, toTitleCase

BASE_URL = "https://cambridgema.primegov.com"
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}


def _fetch(url: str, cache_path: str = None, *, verbose=False, force=False) -> str:
    import requests
    if cache_path and not force and os.path.isfile(cache_path):
        if verbose:
            print(f"Reading '{url}' from cache '{cache_path}'")
        with open(cache_path, 'r', encoding='utf8') as f:
            return f.read()

    print(f"Fetching '{url}'")
    content = requests.get(url, headers=REQUEST_HDR).content.decode('utf8')
    if cache_path:
        print(f"Caching '{cache_path}'")
        try:
            with open(cache_path, 'w', encoding='utf8') as f:
                f.write(content)
        except Exception as e:
            if os.path.isfile(cache_path):
                os.remove(cache_path)
            raise e

    return content


def _check_sponsor_paragraph(p) -> Optional[str]:
    """If <p> is a sponsor line (bold + text-transform:uppercase), return the councillor name."""
    for span in p.find_all('span'):
        style = span.get('style', '')
        text = span.get_text().strip()
        if not text:
            continue
        if 'text-transform:uppercase' in style and 'font-weight:bold' in style:
            for prefix in ('VICE MAYOR ', 'COUNCILLOR ', 'MAYOR '):
                if text.upper().startswith(prefix):
                    return lookUpCouncillorName(text[len(prefix):].strip())
    return None


def _check_uid_paragraph(p) -> Optional[str]:
    """If <p> has a bold span matching a UID pattern, return the UID string."""
    for span in p.find_all('span'):
        style = span.get('style', '')
        text = span.get_text().strip()
        if not text:
            continue
        if 'font-weight:bold' in style and 'text-transform:uppercase' not in style:
            if re.match(r'^(CMA|APP|COM|RES|POR|COF|ORD)\s+\d{4}-\d+$', text):
                return text
            if re.match(r'^AR-\d{2,4}-\d+$', text):
                return text
    return None


def _is_vote_only_paragraph(text: str) -> bool:
    """True if this paragraph is entirely a vote-result line, not a description."""
    return bool(re.match(
        r'^(?:REFERRED TO\b|PASSED TO A SECOND READING\b|ELIGIBLE TO BE ORDAINED\b|CHARTER RIGHT EXERCISED BY\b)',
        text.strip(), re.IGNORECASE
    ))


def _parse_vote_text(text: str) -> tuple:
    """Parse (action, vote, amended, charter_right) from vote result text.

    Works for both standalone vote paragraphs and text with an embedded vote
    appended to a description (e.g. the charter right case).
    """
    upper = text.strip().upper()

    if 'CHARTER RIGHT' in upper:
        match = re.search(
            r'CHARTER RIGHT EXERCISED\s+BY\s+(?:COUNCILL?OR|VICE MAYOR|MAYOR)\s+(\S+)',
            text, re.IGNORECASE
        )
        cr = lookUpCouncillorName(match.group(1)) if match else '!!!'
        return ('Charter Right', '', '', cr)

    if 'REFERRED TO' in upper:
        return ('Referred', 'Voice Vote', '', '')

    if 'PASSED TO A SECOND READING' in upper:
        return ('Passed', 'Voice Vote', '', '')

    if 'ELIGIBLE TO BE ORDAINED' in upper:
        return ('', '', '', '')

    return ('', '', '', '')


def _parse_vote_lists(text: str) -> tuple:
    """Split YEAS/NAYS/PRESENT/ABSENT sections from result text.

    Returns (yeas, nays, present, absent, remaining_text) where remaining_text
    is the portion of text before the vote lists begin.
    """
    yeas: List[str] = []
    nays: List[str] = []
    present: List[str] = []
    absent: List[str] = []

    m = re.search(r'\bYEAS?\s*:', text, re.IGNORECASE)
    if not m:
        return yeas, nays, present, absent, text

    remaining = text[:m.start()].strip()
    vote_section = text[m.start():]

    parts = re.split(r'\b(YEAS?|NAYS?|PRESENT|ABSENT)\s*:', vote_section, flags=re.IGNORECASE)
    i = 1
    while i < len(parts) - 1:
        label = parts[i].strip().upper()
        names_text = parts[i + 1].strip()
        names = [
            lookUpCouncillorName(n.strip())
            for n in re.split(r',\s*', names_text)
            if n.strip() and n.strip().replace('\xa0', '').upper() != 'NONE'
        ]
        names = [n for n in names if n]
        if 'YEA' in label:
            yeas = names
        elif 'NAY' in label:
            nays = names
        elif 'PRESENT' in label:
            present = names
        elif 'ABSENT' in label:
            absent = names
        i += 2

    return yeas, nays, present, absent, remaining


def _parse_result_row(row) -> tuple:
    """Parse (action, vote, amended, yeas, nays, present, absent, charter_right) from a RESULT: row."""
    text = row.get_text(' ').strip()
    match = re.match(r'RESULT:\s*(.+)', text, re.IGNORECASE)
    if not match:
        return ('', '', '', [], [], [], [], '')

    result_text = match.group(1).strip()

    if 'CHARTER RIGHT' in result_text.upper():
        cr_match = re.search(
            r'CHARTER RIGHT EXERCISED\s+BY\s+(?:COUNCILL?OR|VICE MAYOR|MAYOR)\s+(\S+)',
            result_text, re.IGNORECASE
        )
        cr = lookUpCouncillorName(cr_match.group(1)) if cr_match else '!!!'
        return ('Charter Right', '', '', [], [], [], [], cr)

    vote = ''
    amended = ''

    yeas, nays, present, absent, result_text = _parse_vote_lists(result_text)

    code_match = re.search(r'\[([^\]]+)\]', result_text)
    if code_match:
        code = code_match.group(1)
        result_text = (result_text[:code_match.start()] + result_text[code_match.end():]).strip()
        if code.upper().startswith('VV'):
            vote = 'Voice Vote'
        elif re.match(r'\d+-\d+', code):
            vote = code
        elif code.lower() == 'unanimous':
            vote = 'Unanimous'
        else:
            vote = code

    if re.search(r'\bas amended\b', result_text, re.IGNORECASE):
        amended = 'yes'
        result_text = re.sub(r'\s*\bas amended\b', '', result_text, flags=re.IGNORECASE).strip()

    action = toTitleCase(agenda.extractAction(result_text))
    return (action, vote, amended, yeas, nays, present, absent, '')


def _strip_inline_vote(text: str) -> str:
    """Remove inline vote text appended to a description paragraph."""
    text = re.sub(
        r'\s*CHARTER RIGHT EXERCISED BY\s+(?:COUNCILL?OR|VICE MAYOR|MAYOR)\s+\S+(?:\s+IN COUNCIL[^.]*)?',
        '', text, flags=re.IGNORECASE
    )
    text = re.sub(
        r'\s*REFERRED TO(?:\s+THE)?\s+[A-Z][A-Z\s]+?IN COUNCIL[^.]*',
        '', text, flags=re.IGNORECASE
    )
    text = re.sub(r'\s*PASSED TO A SECOND READING[^.]*', '', text, flags=re.IGNORECASE)
    return text.strip().rstrip('. ').strip()


def _parse_item_table(table, template_id: str) -> Optional[agenda.AgendaItem]:
    """Parse one PrimeGov item table. Returns None for section headers and unrecognised rows."""
    if table.get('data-sectionid'):
        return None

    rows = table.find_all('tr', recursive=False)
    if not rows:
        return None

    first_row = rows[0]
    cells = first_row.find_all('td', recursive=False)
    if len(cells) < 2:
        return None

    # Walk cells. The first cell is an attachment-icon cell that has empty text due
    # to a duplicate class= attribute which causes BeautifulSoup to misread it.
    # Identify cells by text: skip empty cells (icon) and optionalButtonsCell.
    num_cell = None
    content_cell = None
    for cell in cells:
        classes = cell.get('class') or []
        if isinstance(classes, str):
            classes = [classes]
        if 'optionalButtonsCell' in classes:
            continue
        if not cell.get_text().strip():
            continue  # attachment icon cell — empty text
        if num_cell is None:
            num_cell = cell
        elif content_cell is None:
            content_cell = cell
            break

    if not num_cell or not content_cell:
        return None

    # Item number must be a plain integer
    num_text = num_cell.get_text().strip().rstrip('.')
    if not re.match(r'^\d+$', num_text):
        return None

    # Parse direct <p> children of the content cell
    description = None
    sponsors: List[str] = []
    uid: Optional[str] = None
    action = ''
    vote = ''
    amended = ''
    charter_right = ''
    yeas: List[str] = []
    nays: List[str] = []
    present: List[str] = []
    absent: List[str] = []

    for child in content_cell.children:
        if not hasattr(child, 'name') or child.name != 'p':
            continue
        p_text = child.get_text(' ').strip()
        if not p_text or not p_text.replace('\xa0', '').replace(' ', '').strip():
            continue

        # Sponsor line: bold + text-transform:uppercase span
        sponsor_name = _check_sponsor_paragraph(child)
        if sponsor_name is not None:
            sponsors.append(sponsor_name)
            continue

        # UID line: bold span matching item-type pattern
        found_uid = _check_uid_paragraph(child)
        if found_uid:
            uid = found_uid
            continue

        # Standalone vote-result paragraph
        if _is_vote_only_paragraph(p_text):
            v_action, v_vote, v_amended, v_cr = _parse_vote_text(p_text)
            if v_action and not action:
                action, vote, amended, charter_right = v_action, v_vote, v_amended, v_cr
            continue

        # Description paragraph (first one wins); may have inline vote appended
        if description is None:
            v_action, v_vote, v_amended, v_cr = _parse_vote_text(p_text)
            if v_action and not action:
                action, vote, amended, charter_right = v_action, v_vote, v_amended, v_cr
            description = _strip_inline_vote(p_text)

    if uid is None:
        return None

    # Check subsequent rows for a RESULT: line
    for row in rows[1:]:
        row_text = row.get_text(' ').strip()
        if re.match(r'RESULT:\s*\S', row_text, re.IGNORECASE):
            r_action, r_vote, r_amended, r_yeas, r_nays, r_present, r_absent, r_cr = _parse_result_row(row)
            if r_action:
                action = r_action
                vote = r_vote
                yeas = r_yeas
                nays = r_nays
                present = r_present
                absent = r_absent
                if r_cr and not charter_right:
                    charter_right = r_cr
                if r_amended:
                    amended = r_amended
            break

    # Item URL: prefer "View Item Details" searchItemId link
    item_url = f"{BASE_URL}/Portal/Meeting?meetingTemplateId={template_id}"
    search_link = table.find('a', href=re.compile(r'searchItemId=\d+'))
    if search_link:
        href = search_link.get('href', '')
        item_url = href if href.startswith('http') else BASE_URL + href

    info = agenda.ItemInfo(
        category='',
        charter_right=charter_right,
        cma='',
        order='',
        app='',
        awaiting='',
        action=action,
        amended=amended,
        history=None,
        sponsor=sponsors[0] if sponsors else '',
        cosponsors=sponsors[1:],
    )

    uid_type = re.match(r'^(CMA|APP|COM|RES|POR|COF|ORD|AR)', uid)
    if not uid_type:
        return None
    itype = uid_type.group(1)

    handlers = {
        'CMA': agenda.processCma,
        'APP': agenda.processApp,
        'COM': agenda.processCom,
        'RES': agenda.processRes,
        'POR': agenda.processPor,
        'ORD': agenda.processOrd,
    }

    if itype == 'AR':
        return agenda.AwaitingReport(uid, item_url, description or '')

    if itype not in handlers:
        return None

    item = handlers[itype](info, uid, num_text, description or '', item_url, vote, action)

    # Embed vote result so buildRow can use it without a separate final_actions JSON
    if item is not None and (action or vote or charter_right):
        item.final_action = {
            'action': action,
            'vote': vote,
            'charter_right': charter_right,
            'amended': amended,
            'yeas': yeas,
            'nays': nays,
            'present': present,
            'absent': absent,
            'recused': [],
        }

    return item


def _apply_result_table(result_tr, item) -> None:
    """Apply a standalone RESULT table row's data to an already-parsed item."""
    r_action, r_vote, r_amended, r_yeas, r_nays, r_present, r_absent, r_cr = _parse_result_row(result_tr)
    if not r_action:
        return

    existing = item.final_action or {}
    existing_cr = r_cr or existing.get('charter_right', '') or getattr(item, 'charter_right', '')

    item.final_action = {
        'action': r_action,
        'vote': r_vote,
        'charter_right': existing_cr,
        'amended': r_amended or existing.get('amended', ''),
        'yeas': r_yeas,
        'nays': r_nays,
        'present': r_present,
        'absent': r_absent,
        'recused': [],
    }

    if hasattr(item, 'action'):
        item.action = r_action
    if hasattr(item, 'vote'):
        item.vote = r_vote
    if hasattr(item, 'charter_right') and existing_cr:
        item.charter_right = existing_cr
    if hasattr(item, 'amended') and (r_amended or existing.get('amended', '')):
        item.amended = r_amended or existing.get('amended', '')


def processMeeting(meeting, cache_dir, *, force_fetch=False, verbose=False) -> Dict[str, List[Any]]:
    """Fetch and parse a PrimeGov meeting page.

    Uses the Final Actions HTML when meeting.final_actions is set (post-meeting),
    otherwise falls back to the Agenda HTML (meeting.url).
    """
    url = (meeting.final_actions or '').strip() or meeting.url
    if not url:
        print_red(f"No URL for meeting '{meeting}'")
        return None

    template_id_match = re.search(r'meetingTemplateId=(\d+)', url)
    if not template_id_match:
        print_red(f"Cannot extract meetingTemplateId from '{url}'")
        return None
    template_id = template_id_match.group(1)

    cache_path = os.path.join(cache_dir, f"meeting_pg_{template_id}.html")
    html = _fetch(url, cache_path, verbose=verbose, force=force_fetch)
    soup = BeautifulSoup(html, 'html.parser')

    all_tables = soup.find_all('table')
    item_tables = [t for t in all_tables if 'item-table-fromdocx' in (t.get('class') or [])]
    print(f"Checking {len(item_tables)} item tables for meeting '{meeting}'")

    items: Dict[str, List] = defaultdict(list)
    last_item = None
    for table in all_tables:
        classes = table.get('class') or []
        if 'item-table-fromdocx' in classes:
            try:
                item = _parse_item_table(table, template_id)
                last_item = item  # None for section headers; prevents RESULT bleed across sections
                if item is not None:
                    items[item.type].append(item)
                    if verbose:
                        print(item)
            except Exception as e:  ## pylint: disable=broad-except
                last_item = None
                print_red(f"Error parsing item table: {e}")
                if verbose:
                    import traceback  ## pylint: disable=import-outside-toplevel
                    traceback.print_exc()
        elif last_item is not None:
            first_tr = table.find('tr')
            if first_tr and re.match(r'RESULT:\s*\S', first_tr.get_text(' ').strip(), re.IGNORECASE):
                _apply_result_table(first_tr, last_item)

    total = sum(len(v) for v in items.values())
    print(f"Found {total} items for meeting '{meeting}'")
    for item in [x for lst in items.values() for x in lst]:
        item.setMeeting(meeting)

    return items
