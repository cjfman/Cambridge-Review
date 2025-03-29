#!/usr/bin/env python3

import argparse
import csv
import os
import re
import sys

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from councillors import getCouncillorNames, getSessionYear, setCouncillorInfo
from prompts import query_yes_no


VERBOSE=False
DEBUG=False

## If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

SHEETS = {
    2018: "1Fm2qnK6BCkWJvB-iUsDshZa_o0qfHHfjOEnVXhWYj7E",
    2020: "17T1GYly0AZo55iFpjiq9tD-oNRDG4-x0HRvhZ_nJ3j8",
    2022: "1BBS7C-TwU9kBNJo48EQnz1sDTVOhAHlvjQbKjVvWZ4A",
    2024: "17qiYpxVFX8zwDrMJKpK_C-hZL9-Y8y5QU3GhVhi4xeg",
    2025: "1BEBniAqsR0bb3gU7Cy9PJW4lTQO1x2TlekJsyS89vNA",
}

item_sheet_keys = (
    'cma',
    'app',
    'com',
    'res',
    'por',
    'ord',
    'ar',
)

sheet_name_map = {
    'meetings': 'Meetings',
    'cma':      'CMA',
    'app':      "Applications and Petitions",
    'com':      'Communications',
    'res':      'Resolutions',
    'por':      "Policy Orders",
    'ord':      "Ordinances",
    'ar':       "Awaiting Reports",
}

item_csv_map = {
    'ar':  'awaiting_reports.csv',
    'app': 'applications_and_petitions.csv',
    'cma': 'cma.csv',
    'com': 'communications.csv',
    'por': 'policy_orders.csv',
    'ord': 'ordinances.csv',
    'res': 'resolutions.csv',
}

item_vote_col = {
    'por': 'L',
    'cma': 'L',
    'app': 'L',
    'res': 'J',
    'ord': 'K',
}

por_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Sponsor":           'E',
    "Co-Sponsors":       'F',
    "Charter Right":     'G',
    "Amended":           'H',
    "Outcome":           'I',
    "Link":              'Y',
    "Summary":           'Z',
}
por_idx_map = { x: ord(y.upper()) - ord('A') for x, y in por_col_map.items() }
por_row_size = max(por_idx_map.values()) + 1

cma_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Category":          'E',
    "Awaiting Report":   'F',
    "Policy Order":      'G',
    "Charter Right":     'H',
    "Outcome":           'I',
    "Link":              'Y',
    "Summary":           'Z',
}
cma_idx_map = { x: ord(y.upper()) - ord('A') for x, y in cma_col_map.items() }
cma_row_size = max(cma_idx_map.values()) + 1

app_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Category":          'E',
    "Name":              'F',
    "Address":           'G',
    "Charter Right":     'H',
    "Outcome":           'I',
    "Link":              'Y',
    "Summary":           'Z',
}
app_idx_map = { x: ord(y.upper()) - ord('A') for x, y in app_col_map.items() }
app_row_size = max(app_idx_map.values()) + 1

com_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Name":              'E',
    "Address":           'F',
    "Subject":           'G',
    "Link":              'H',
    "Notes":             'I',
}
com_idx_map = { x: ord(y.upper()) - ord('A') for x, y in com_col_map.items() }
com_row_size = max(com_idx_map.values()) + 1

res_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Category":          'E',
    "Sponsor":           'F',
    "Outcome":           'G',
    "Link":              'W',
    "Summary":           'X',
    "Notes":             'Y',
}
res_idx_map = { x: ord(y.upper()) - ord('A') for x, y in res_col_map.items() }
res_row_size = max(res_idx_map.values()) + 1

ord_col_map  = {
    "Unique Identifier": 'A',
    "Meeting":           'B',
    "Meeting Date":      'C',
    "CMA":               'D',
    "Policy Order":      'E',
    "Application":       'F',
    "Sponsor":           'G',
    "Co-Sponsors":       'H',
    "Amended":           'I',
    "Outcome":           'J',
    "Link":              'X',
    "Summary":           'Y',
    "Notes":             'Z',
}
ord_idx_map  = { x: ord(y.upper()) - ord('A') for x, y in ord_col_map.items() }
ord_row_size = max(ord_idx_map.values()) + 1

ar_col_map = {
    "Unique Identifier": "A",
    "Department":        "B",
    "Category":          "C",
    "Policy Order":      "D",
    "Link":              "E",
    "Description":       "F",
}
ar_idx_map = { x: ord(y.upper()) - ord('A') for x, y in ar_col_map.items() }
ar_row_size = max(ar_idx_map.values()) + 1

meetings_cols = (
    "Unique Identifier",
    "Body",
    "Type",
    "Other",
    "Session",
    "Date",
    "Time",
    "Status",
    "Id",
    "url",
    "Agenda Summary",
    "Agenda Packet",
    "Final Actions",
    "Minutes",
)
meetings_idx_map = { name: i for i, name in enumerate(meetings_cols) }
meetings_col_map = { name: chr(ord('A') + i) for name, i in meetings_idx_map.items() }
meetings_row_size = max(meetings_idx_map.values()) + 1

item_mappings = {
    'por': (por_col_map, por_idx_map, por_row_size),
    'cma': (cma_col_map, cma_idx_map, cma_row_size),
    'app': (app_col_map, app_idx_map, app_row_size),
    'com': (com_col_map, com_idx_map, com_row_size),
    'res': (res_col_map, res_idx_map, res_row_size),
    'ord': (ord_col_map, ord_idx_map, ord_row_size),
    'ar':  (ar_col_map, ar_idx_map, ar_row_size),
    'meetings':  (meetings_col_map, meetings_idx_map, meetings_row_size),
}


def parseArgs():
    """Parse command arguments"""
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.set_defaults(func=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--credentials", default="google_credentials/credentials.json",
        help="Google API JSON credentials")
    parser.add_argument("--token", default="google_credentials/token.json",
        help="Google API JSON token. Will be created if one doesn't exist")
    parser.add_argument("--sheet-id",
        help="The google sheets ID")

    subparsers = parser.add_subparsers()

    ## Add cmd
    add_parser = subparsers.add_parser('add',
        help="Add rows to the google sheets"
    )
    add_parser.set_defaults(func=add_hdlr)
    add_parser.add_argument("--councillor-info", required=True,
        help="File with councillor info")
    add_parser.add_argument("--session", type=int,
        help="The session year. Defaults to most recent one found in councillor info file")
    add_parser.add_argument("--force-add", action="store_true",
        help="Add rows even if the unique ID already exists")
    add_parser.add_argument("--processed-dir", required=True,
        help="Directory that contains the processed agenda item csvs")

    ## Meetings cmd
    meetings_parser = subparsers.add_parser('meetings',
        help="Update meeting rows to the google sheets"
    )
    meetings_parser.set_defaults(func=meetings_hdlr)
    meetings_parser.add_argument("--force-add", action="store_true",
        help="Add rows even if the unique ID already exists")
    meetings_parser.add_argument("--file", required=True,
        help="File that contains the meetings")

    ## Check credentials cmd
    parser.set_defaults(check_creds=False)
    check_parser = subparsers.add_parser('check-credentials',
        help="Check google credentials"
    )
    check_parser.add_argument("-d", "--delete-on-fail", action="store_true",
        help="Delete existing token if it fails to validate")
    check_parser.set_defaults(check_creds=True)

    ## Download
    down_parser = subparsers.add_parser('download',
        help="Downloads all sheets",
    )
    down_parser.set_defaults(func=download_hdlr)
    down_parser.add_argument("--dir", required=True,
        help="Directory for the download")
    down_parser.add_argument("--session", type=int, default=2025,
        help="The session year. Defaults to most recent one found in councillor info file")

    ## Final parse
    args = parser.parse_args()
    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args


def getCreds(credentials_path, token_path):
    """Get Google API credentials"""
    creds = None
    ## The file token.json stores the user's access and refresh tokens, and is
    ## created automatically when the authorization flow completes for the first
    ## time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    ## If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                  credentials_path, SCOPES
                  )
            creds = flow.run_local_server(port=0, open_browser=False)
    ## Save the credentials for the next run
    with open(token_path, "w") as token:
        token.write(creds.to_json())

    return creds


def setCouncillorColumns(names):
    """Add councillor names to column maps"""
    names = tuple(enumerate(names))
    for item_key, col in item_vote_col.items():
        col_map, idx_map, _ = item_mappings[item_key]
        start = ord(col) - ord('A')
        for i, name in names:
            idx = start + i
            col_map[name] = chr(idx + ord('A'))
            idx_map[name] = idx

def append(service, sheet_id, sheet_range, rows, *, user_entered=True):
    input_opt = 'USER_ENTERED' if user_entered else 'RAW'
    sheet = service.spreadsheets()
    result = sheet.values().append(
        spreadsheetId=sheet_id,
        range=sheet_range,
        body={
            'values': rows,
            'majorDimension': 'ROWS',
        },
        valueInputOption=input_opt,
        insertDataOption='INSERT_ROWS',
    ).execute()
    return result.get('updates', None)


def update(service, sheet_id, sheet_range, rows, *, user_entered=True):
    input_opt = 'USER_ENTERED' if user_entered else 'RAW'
    sheet = service.spreadsheets()
    result = sheet.values().update(
        spreadsheetId=sheet_id,
        range=sheet_range,
        body={
            'values': rows,
            'majorDimension': 'ROWS',
        },
        valueInputOption=input_opt,
    ).execute()
    return result


def getAllUids(service, sheet_id):
    """Get all agenda item UIDs"""
    sheet_keys = tuple(sheet_name_map.keys())
    sheet = service.spreadsheets()
    result = sheet.values().batchGet(
        spreadsheetId=sheet_id,
        ranges=[f"{sheet_name_map[x]}!A2:A" for x in sheet_keys],
        majorDimension='COLUMNS',
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    values = result.get("valueRanges", [])
    if not values:
        return None

    return dict(zip(sheet_keys, (x['values'][0] if 'values' in x else [] for x in values)))


def loadCsvDict(path):
    """Load CSV"""
    if not os.path.exists(path):
        if query_yes_no(f"File '{path}' doesn't exist. Continue?"):
            return tuple()
        else:
            sys.exit(1)

    with open(path, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        return tuple(reader)


def loadAndProcessItems(item_type, dir_path, existing_uids=None):
    """Load agenda items from file and convert them to sheets rows"""
    path = os.path.join(dir_path, item_csv_map[item_type])
    print(f'Loading "{item_type}" agenda items from "{path}"')
    items = loadCsvDict(path)
    return processItems(item_type, items, existing_uids)


def processItems(item_type, items, existing_uids=None):
    ## Don't add rows if they already exist
    if existing_uids is not None:
        count = len(items)
        items = [x for x in items if x["Unique Identifier"] not in existing_uids]
        count = count - len(items)
        print(f"Skipping {count} {item_type} items")

    ## Convert item to sheets row by placing values in the correct column
    _, idx_map, row_size = item_mappings[item_type]
    rows = []
    for item in items:
        row = [""] * row_size
        for k, v in item.items():
            if k in idx_map:
                row[idx_map[k]] = v

        rows.append(row)

    return rows


def add_item_type(service, sheet_id, item_type, rows):
    if not rows:
        print(f"No '{item_type}' rows to add")
        return

    ## Add rows
    sheet_name = sheet_name_map[item_type]
    print(f"Adding {len(rows)} to '{sheet_name}'")
    results = append(service, sheet_id, sheet_name, rows)
    if results is None:
        print(f"Failed to add rows to '{sheet_name}'")
        return

    if item_type not in item_vote_col:
        print("Not updating vote aggrigation formulas")
        return

    ## Figure out vote columns
    print("Updating vote aggrigation formulas")
    c_start = item_vote_col[item_type]
    c_end   = chr(ord(c_start) + 8)
    c_yeas  = chr(ord(c_start) + 9)
    c_pres  = chr(ord(c_start) + 11)
    c_absnt = chr(ord(c_start) + 12)

    ## Update formula rows
    r_start, r_end = tuple(int(re.search(r"\d+", x).group()) for x in results['updatedRange'].split('!')[1].split(':'))
    rows = []
    for i in range(r_start, r_end + 1):
        rows.append([f'=ARRAY_CONSTRAIN(ARRAYFORMULA(TEXTJOIN(", ",TRUE,{x})), 1, 1)' for x in [
            f'IF("yes"=LOWER(${c_start}{i}:${c_end}{i}),${c_start}$1:${c_end}$1,"")',
            f'IF("no"=LOWER(${c_start}{i}:${c_end}{i}),${c_start}$1:${c_end}$1,"")',
            f'IF(LOWER({c_pres}$1)=LOWER(${c_start}{i}:${c_end}{i}),${c_start}$1:${c_end}$1,"")',
            f'IF(LOWER({c_absnt}$1)=LOWER(${c_start}{i}:${c_end}{i}),${c_start}$1:${c_end}$1,"")',
        ]])

    sheet_range = f'{sheet_name}!{c_yeas}{r_start}:{c_absnt}{r_end}'
    results = update(service, sheet_id, sheet_range, rows)


def downloadAllSheets(service, sheet_id):
    """Get all rows from a sheet"""
    sheet = service.spreadsheets()
    result = sheet.values().batchGet(
        spreadsheetId=sheet_id,
        ranges=[f"{sheet_name_map[x]}!A:Z" for x in item_sheet_keys],
        majorDimension='ROWS',
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    values = result.get("valueRanges", [])
    if not values:
        return None

    return dict(zip(item_sheet_keys, [x['values'] for x in values]))


def add_hdlr(args, service):
    ## Set councillor info
    if args.councillor_info is not None:
        if not setCouncillorInfo(args.councillor_info, args.session):
            print(f"Failed to set up councillor info")
            return 1

        setCouncillorColumns(getCouncillorNames())
    if not args.session:
        print(f"Using session year {args.session}")
        args.session = getSessionYear()

    ## Sheet ID
    if args.sheet_id is None:
        if args.session not in SHEETS:
            print(f"Cannot find sheet ID for session {args.session}")

        args.sheet_id = SHEETS[args.session]

    ## Get UIDs
    uids = { x: None for x in item_sheet_keys }
    if not args.force_add:
        print("Getting existing UIDs")
        uids = getAllUids(service, args.sheet_id)
    else:
        print("Force adding")

    ## Add rows
    for item_type in item_sheet_keys:
        rows = loadAndProcessItems(item_type, args.processed_dir, uids[item_type])
        add_item_type(service, args.sheet_id, item_type, rows)

    return 0


def meetings_hdlr(args, service):
    ## Get UIDs
    uids = None
    if not args.force_add:
        print("Getting existing UIDs")
        uids = getAllUids(service, args.sheet_id)['meetings']
        print(f"Found {len(uids)} existing meetings")
    else:
        print("Force adding")

    ## Load and process meetings
    print(f'Loading meetings from "{args.file}"')
    rows = processItems('meetings', loadCsvDict(args.file), uids)
    add_item_type(service, args.sheet_id, 'meetings', rows)
    return 0


def download_hdlr(args, service):
    if args.sheet_id is None:
        args.sheet_id = SHEETS[args.session]

    sheets = downloadAllSheets(service, args.sheet_id)
    for item_type, rows in sheets.items():
        path = os.path.join(args.dir, item_csv_map[item_type])
        with open(path, 'w', encoding='utf8', newline='') as f:
            writer = csv.writer(f, dialect=csv.unix_dialect)
            for row in rows:
                writer.writerow(row)


def check_credentials(args):
    try:
        getCreds(args.credentials, args.token)
        return 0
    except RefreshError as e:
        print(f"Failed to validate credentials: {e}")
        if not args.delete_on_fail:
            return 1

    try:
        os.remove(args.token)
    except OSError:
        pass

    getCreds(args.credentials, args.token)
    return 0


def main(args):
    if args.check_creds:
        ## Do this instead of anything else
        return check_credentials(args)

    if args.func is None:
        args.print_usage()
        return 1

    ## Run command
    creds = getCreds(args.credentials, args.token)
    service = build("sheets", "v4", credentials=creds)
    return args.func(args, service)


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except HttpError as e:
        print(e)
        sys.exit(1)
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
