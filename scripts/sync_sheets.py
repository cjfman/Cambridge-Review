#!/usr/bin/env python3

import argparse
import csv
import os
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


VERBOSE=False
DEBUG=False

## If modifying these scopes, delete the file token.json.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]
TRACKER_SHEET_ID = "17qiYpxVFX8zwDrMJKpK_C-hZL9-Y8y5QU3GhVhi4xeg"

item_sheet_keys = (
    'cma',
    'app',
    'com',
    'res',
    'por',
    'ar',
)

sheet_name_map = {
    'meetings': 'Meetings',
    'cma':      'CMA',
    'app':      "Applications and Petitions",
    'com':      'Communications',
    'res':      'Resolutions',
    'por':      "Policy Orders",
    'ar':       "Awaiting Reports",
}

item_csv_map = {
    'ar':  'awaiting_reports.csv',
    'app': 'applications_and_petitions.csv',
    'cma': 'cma.csv',
    'com': 'communications.csv',
    'por': 'policy_orders.csv',
    'res': 'resolutions.csv'
}

pos_col_map = {
    "Unique Identifier": 'A',
    "Agenda Number":     'B',
    "Meeting":           'C',
    "Meeting Date":      'D',
    "Sponsor":           'E',
    "Co-Sponsors":       'F',
    "Charter Right":     'G',
    "Amended":           'H',
    "Link":              'Y',
    "Summary":           'Z',
}
pos_idx_map = { x: ord(y.upper()) - ord('A') for x, y in pos_col_map.items() }
pos_row_size = max(pos_idx_map.values()) + 1

item_mappings = {
    'por': (pos_col_map, pos_idx_map, pos_row_size),
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
    parser.add_argument("--sheet-id", default=TRACKER_SHEET_ID,
        help="The google sheets ID")
    parser.add_argument("--processed-dir", required=True,
        help="Directory that contains the processed agenda item csvs")

    subparsers = parser.add_subparsers()

    add_parser = subparsers.add_parser('add',
        help="Add rows to the google sheets"
    )
    add_parser.set_defaults(func=add_hdlr)
    add_parser.add_argument("--force-add", action="store_true",
        help="Add rows even if the unique ID already exists")

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
            creds = flow.run_local_server(port=0)
    ## Save the credentials for the next run
    with open(token_path, "w") as token:
        token.write(creds.to_json())

    return creds


def append(service, sheet_id, sheet_range, rows):
    sheet = service.spreadsheets()
    result = sheet.values().append(
        spreadsheetId=sheet_id,
        range=sheet_range,
        body={
            'values': rows,
            'majorDimension': 'ROWS',
        },
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
    ).execute()
    return result


def getAllUids(service, sheet_id):
    """Get all agenda item UIDs"""
    sheet = service.spreadsheets()
    result = sheet.values().batchGet(
        spreadsheetId=sheet_id,
        ranges=[f"{sheet_name_map[x]}!A2:A" for x in item_sheet_keys],
        majorDimension='COLUMNS',
        valueRenderOption='UNFORMATTED_VALUE',
    ).execute()
    values = result.get("valueRanges", [])
    if not values:
        return None

    return dict(zip(item_sheet_keys, (x['values'][0] for x in values)))


def loadItems(item_type, dir_path):
    """Load agenda items from a file"""
    path = os.path.join(dir_path, item_csv_map[item_type])
    print(f'Loading "{item_type}" agenda items from "{path}"')
    with open(path, 'r', encoding='utf8') as f:
        reader = csv.DictReader(f)
        return tuple(reader)


def processRowsToAdd(item_type, dir_path, existing_uids=None):
    """Load agenda items from file and convert them to sheets rows"""
    items = loadItems(item_type, dir_path)

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


def add_hdlr(args, service):
    uids = { x: None for x in item_sheet_keys }
    if not args.force_add:
        print("Getting existing UIDs")
        uids = getAllUids(service, args.sheet_id)
    else:
        print("Force adding")

    for item_type in ['por']:
        rows = processRowsToAdd(item_type, args.processed_dir, uids[item_type])
        if not rows:
            print(f"No {item_type} rows to add")
            continue

        ## Add rows
        sheet_name = sheet_name_map[item_type]
        print(f"Adding {len(rows)} to '{sheet_name}'")
        results = append(service, args.sheet_id, sheet_name, rows)
        if 'updatedRange' not in results:
            print(f"Failed to add rows to '{sheet_name}'")
            continue

        ## Update formula rows
        #sheet_range = results['updatedRange'].split('!')[1]

    return 0


def main(args):
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
