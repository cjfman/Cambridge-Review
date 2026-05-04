#!/usr/bin/env python3
## pylint: disable=too-many-locals,too-many-branches

import argparse
import copy
import csv
import datetime as dt
import os
import sys
import traceback

from typing import IO, Any, Dict, Iterable, List, Optional, Tuple

from pathlib import Path

## pylint: disable=import-error,wrong-import-order,wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib import agenda, iqm2_portal, primegov_portal
from citylib.councillors import getCouncillorNames, setCouncillorInfo, lookUpCouncillorName
from citylib.utils import print_green, print_red

VERBOSE = False
ALLOWED_TYPES = ('regular', 'special')
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


def parseArgs() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.set_defaults(skip_processing=False)
    parser.add_argument("--base-url", default="https://cambridgema.iqm2.com",
        help="The base URL (IQM2 meetings only; ignored for PrimeGov meetings)")
    parser.add_argument("--cache-dir", required=True,
        help="Where to cache downloads from the city website")
    parser.add_argument("--force-fetch", action="store_true",
        help="Force fetching of the meeting html")
    parser.add_argument("--exit-on-error", action="store_true",
        help="Stop processing meetings if there is an error")
    parser.add_argument("--num-meetings", type=int, default=0,
        help="The maximum number of meetings to process. Set 0 for no limit")
    ex_group_1 = parser.add_mutually_exclusive_group()
    ex_group_1.add_argument("--meeting",
        help="Process this specific meeting")
    ex_group_1.add_argument("--meetings",
        help="Process specific meetings, comma seperated. Overrides --meeting")
    ex_group_1.add_argument("--next-meeting", action="store_true",
        help="Process the next meeting to occur")
    ex_group_1.add_argument("--last-meeting", action="store_true",
        help="Process the most recent meeting to occur")
    parser.add_argument("--councillor-info", required=True,
        help="File with councillor info")
    parser.add_argument("--session", type=int,
        help="The session year. Defaults to most recent one found in councillor info file")
    parser.add_argument("--final-actions",
        help="JSON file with final actions (IQM2 meetings only; PrimeGov meetings read votes from the meeting page)")
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


def buildRow(item: agenda.AgendaItem, hdrs: Iterable[str], final_action: Optional[Dict] = None, *, aggrigate_votes: bool = False) -> Dict[str, str]:
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
        if 'Outcome' in d and d['Outcome'] == "Charter Right":
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

        yeas = final_action.get('yeas', [])
        nays = final_action.get('nays', [])
        present = final_action.get('present', [])
        recused = final_action.get('recused', [])
        if yeas:
            unanimous = not nays and not present and not recused
            d['Vote'] = 'Unanimous' if unanimous else 'Roll Call'

        for key, val in action_map.items():
            column = key.title()
            if aggrigate_votes:
                d[column] = ",".join(final_action[key])
            if d.get('Vote') != 'Unanimous':
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


def setCouncillorColumns(names: Iterable[str]):
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


def processNewArs(args: argparse.Namespace, ar_map: Dict, items: Iterable[Any], writer: csv.DictWriter):
    """Process awaiting reports"""
    ## Unlike most agenda items, the list of awaiting reports tends to grow, so track
    ## ARs across meetings
    total = 0
    for item in items:
        if item.uid in ar_map:
            continue

        if VERBOSE:
            print(f"New awaiting report: {item}")

        ar_map[item.uid] = iqm2_portal.processAr(item, args.cache_dir, force_fetch=args.force_fetch)
        writer.writerow(buildRow(item, AR_HDRS, aggrigate_votes=args.aggrigate_votes))
        total += 1

    print_green(f"Wrote {total} awaiting reports")


def processMeeting(meeting: agenda.Meeting, base_url, cache_dir, *, force_fetch: bool = False, verbose: bool = False) -> Dict[str, List[Any]]:
    """Process a meeting. Dispatches to PrimeGov parser for primegov.com URLs."""
    if 'primegov.com' in (meeting.url or ''):
        return primegov_portal.processMeeting(meeting, cache_dir, force_fetch=force_fetch, verbose=verbose)

    return iqm2_portal.processMeeting(meeting, base_url, cache_dir, force_fetch=force_fetch, verbose=verbose)


def processMeetings(args: argparse.Namespace, meetings: Iterable[agenda.Meeting], writers: Dict[str, csv.DictWriter], final_actions: Optional[Dict] = None):
    num = 0
    ar_map = {}
    for meeting in meetings:
        try:
            if args.meetings and meeting.id not in args.meetings and meeting.date not in args.meetings:
                continue
            if meeting.body.lower() != 'city council' or meeting.type.lower() not in ALLOWED_TYPES:
                print(f"Skipping meeting '{meeting}'")
                continue
            if meeting.status == 'cancelled':
                print(f"Meeting '{meeting}' was cancelled. Skipping")
                continue

            print(f"Processing meeting '{meeting}'")
            items = processMeeting(meeting, args.base_url, args.cache_dir, force_fetch=args.force_fetch, verbose=args.verbose)
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


def postProcessItems(writers: Dict[str, csv.DictWriter], items: Dict[str, List[Any]], final_actions: Optional[Dict] = None):
    sets = (
        ('CMA', CMA_HDRS),
        ('APP', APP_HDRS),
        ('COM', COM_HDRS),
        ('RES', RES_HDRS),
        ('POR', POR_HDRS),
        ('ORD', ORD_HDRS),
    )
    for key, hdrs in sets:
        for item in sorted(items[key], key=lambda x: x.uid):
            if final_actions is not None and item.uid in final_actions:
                writers[key].writerow(buildRow(item, hdrs, final_actions[item.uid]))
            else:
                writers[key].writerow(buildRow(item, hdrs))

    types = [x for x, y in sets]
    msg = " ".join([f"{k}:{len(v)}" for k, v in items.items() if k in types])
    total = sum([len(v) for k, v in items.items() if k in types])
    print_green(f"Wrote {total} items. {msg}")


def setupOutputFiles(output_dir) -> Optional[Tuple[Dict[str, IO], Dict[str, csv.DictWriter]]]:
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
            f = open(path, 'w', encoding='utf8') ## pylint: disable=consider-using-with
            w = csv.DictWriter(f, fieldnames=hdrs, lineterminator='\n')
            w.writeheader()
            files[key]   = f
            writers[key] = w
        except Exception as e:
            print_red(f"Failed to open file '{path}' for writing: {e}")
            return None

    return (files, writers)


def openMeetings(path, *, session: Optional[int] = None) -> List[agenda.Meeting]:
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
            meeting = agenda.Meeting(**{ k.lower().replace(' ', '_'): v for k, v in row.items() })
            if meeting.body.lower() == 'city council' and meeting.type.lower() in ALLOWED_TYPES:
                meetings.append(meeting)

    return meetings


def setAttenance(args: argparse.Namespace, final_actions: Dict):
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


def getNextMeeting(meetings: Iterable[agenda.Meeting]) -> Optional[agenda.Meeting]:
    today = dt.datetime.now()
    previous = list(sorted([x for x in meetings if x.getDate() >= today]))
    if previous:
        return previous[0]

    return None


def getLastMeeting(meetings: Iterable[agenda.Meeting]) -> Optional[agenda.Meeting]:
    today = dt.datetime.now()
    previous = list(sorted([x for x in meetings if x.getDate() < today]))
    if previous:
        return previous[-1]

    return None


def preprocessArgs(args: argparse.Namespace) -> Optional[argparse.Namespace]:
    args = copy.copy(args)
    if args.verbose:
        global VERBOSE ## pylint: disable=global-statement
        VERBOSE = args.verbose

    ## Processing
    if args.set_attendance_only:
        args.set_attendance = True
        args.skip_processing = True

    ## Set councillor info
    if args.councillor_info is not None:
        if not setCouncillorInfo(args.councillor_info, args.session):
            print_red("Failed to setup councillor info")
            return None

        setCouncillorColumns(getCouncillorNames())

    return args


def main(args: argparse.Namespace) -> int:
    ## Check args
    args = preprocessArgs(args)
    if args is None:
        print_red("Failed to process the args")
        return 1

    ## Open meetings file
    meetings = openMeetings(args.meetings_file, session=args.session)
    if args.next_meeting:
        meeting = getNextMeeting(meetings)
        if meeting is None:
            print("No next meeting found")
            return 1

        print(f"Using next meeting date {meeting.getDate().date()}")
        args.meeting = meeting.id
    if args.last_meeting:
        meeting = getLastMeeting(meetings)
        if meeting is None:
            print("No last meeting found")
            return 1

        print(f"Using last meeting date {meeting.getDate().date()}")
        args.meeting = meeting.id
    if args.meetings is None and args.meeting is not None:
        args.meetings = [args.meeting]

    ## Meetings and final actions
    output_files = None
    final_actions = None
    if args.final_actions:
        final_actions = iqm2_portal.processFinalActions(args.final_actions)

    print(f"Read {len(meetings)} meetings from '{args.meetings_file}'")
    ## Do work
    try:
        ## Process meetings
        if not args.skip_processing:
            output_files, writers = setupOutputFiles(args.output_dir)
            if output_files is None:
                return 1

            processMeetings(args, meetings, writers, final_actions)

        ## Update attendance
        if args.set_attendance and final_actions is not None:
            print("Updating attendance")
            setAttenance(args, final_actions)
    except KeyboardInterrupt:
        print("User requested exit")
        return 1
    finally:
        ## Close all files
        if output_files is not None:
            for f in output_files.values():
                f.close()

    return 0


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
