## pylint: disable=too-many-locals,too-many-branches,line-too-long,missing-function-docstring

import datetime as dt
import re

from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order
from typing import Any, Dict, List, Optional, Tuple

from citylib.councillors import lookUpCouncillorName
from citylib.utils import toTitleCase

MAX_MSG_LEN = 48
SUPPORTED_TITLES = (
    "City Manager's Agenda",
    "Communications",
    "Resolutions",
    "Policy Order and Resolution List",
    "Applications and Petitions",
    "Communications and Reports from Other City Officers",
    "Unfinished Business",
)

UNSUPPORTED_TITLES = (
    "Charter Right",
    "Calendar",
    "Committee Reports",
    "Communications and Reports from Other City Officers",
)

class AgendaItem:
    """Abstract class"""
    ## pylint: disable=no-member,attribute-defined-outside-init,access-member-before-definition
    def setMeeting(self, meeting: 'Meeting') -> Optional[str]:
        self.meeting_uid  = meeting.uid
        self.meeting_date = meeting.date
        if hasattr(self, 'name'):
            msg = " ".join([self.uid, self.name, self.meeting_uid])
            if len(self.subject) > MAX_MSG_LEN:
                return msg + self.subject[:MAX_MSG_LEN] + "..."

            return msg + self.subject

        return None

    def setNotes(self, notes):
        self.notes = notes
        lower = notes.lower()

        ## Check for affirmative vote
        if hasattr(self, 'vote') and not self.vote:
            match = re.match(r"(?:by )?(?:the|an?)? ?((?:Affirmative|Voice) Vote) of \w+ Members", self.notes, re.IGNORECASE)
            if match:
                self.vote = toTitleCase(match.groups()[0])

        ## Check charter right
        if hasattr(self, 'charter_right') and not self.charter_right          \
            and ("charter right" in lower                                     \
                or self.action == "Charter Right" and "exercised by" in lower \
            ):
            match = re.search(r"exercised by (?:councill?or|vice mayor|mayor) (\w+)", self.notes, re.IGNORECASE)
            if match:
                self.charter_right = lookUpCouncillorName(match.groups()[0])
            else:
                ## Some mistake has been made
                self.charter_right = "!!!"


@dataclass
class Meeting:
    uid: str
    body: str
    type: str
    other: str
    session: str
    date: str
    time: str
    status: str
    id: str
    url: str
    agenda_summary: str
    agenda_packet: str
    final_actions: str
    minutes: str
    attendance: str=None
    _dt=None

    def getDate(self) -> dt.datetime:
        if self._dt is not None:
            return self._dt

        self._dt = dt.datetime.fromisoformat(self.date)
        return self._dt

    def __lt__(self, other: 'Meeting') -> bool:
        return (self.getDate() < other.getDate())

    def __str__(self) -> str:
        return f"{self.body} - {self.type} {self.date} ({self.id})"

    def __repr__(self) -> str:
        return f"[Meeting {str(self)}]"


@dataclass
class CMA(AgendaItem):
    uid:      str
    num:      int
    category: str
    awaiting: str
    order:    str
    url:      str
    action:   str
    vote:     str
    charter_right: str  = ""
    description:   str  = ""
    final_action:  Optional[Dict] = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "CMA"

    def to_dict(self) -> Dict[str, Any]:
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
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.category, self.action, f"[{self.vote}]", self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self) -> str:
        return f"[CMA: {str(self)}]"


@dataclass
class Application(AgendaItem):
    uid:      str
    num:      int
    category: str
    name:     str
    subject:  str
    url:      str
    action:   str
    vote:     str
    charter_right: str  = ""
    address:       str  = ""
    final_action:  Optional[Dict] = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "APP"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Name":              self.name,
            "Subject":           self.subject,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Address":           self.address,
            "Charter Right":     self.charter_right,
            "Link":              self.url,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.category, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self) -> str:
        return f"[Application: {str(self)}]"


@dataclass
class Communication(AgendaItem):
    uid:     str
    num:     int
    name:    str
    address: str
    subject: str
    url:     str
    meeting_uid:  str = ""
    meeting_date: str = ""
    notes:        str = ""
    final_action: Optional[Dict] = None

    @property
    def type(self):
        return "COM"

    def to_dict(self) -> Dict[str, Any]:
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

    def __str__(self) -> str:
        msg = None
        if self.address:
            msg = " ".join([self.uid, self.name, f'"{self.address}"', self.meeting_uid])
        else:
            msg = " ".join([self.uid, self.name, self.meeting_uid])

        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self) -> str:
        return f"[Communication: {str(self)}]"


@dataclass
class Resolution(AgendaItem):
    uid:      str
    num:      int
    category: str
    url:      str
    sponsor:  str
    cosponsors:   str  = ""
    action:       str  = ""
    vote:         str  = ""
    description:  str  = ""
    final_action: Optional[Dict] = None
    meeting_uid:  str  = ""
    meeting_date: str  = ""
    notes:        str  = ""

    @property
    def type(self):
        return "RES"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Unique Identifier": self.uid,
            "Agenda Number":     self.num,
            "Category":          self.category,
            "Link":              self.url,
            "Sponsor":           self.sponsor,
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.category, self.sponsor, self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self) -> str:
        return f"[Resolution: {str(self)}]"


@dataclass
class PolicyOrder(AgendaItem):
    uid:      str
    num:      int
    url:      str
    sponsor:  str
    cosponsors:    str  = ""
    action:        str  = ""
    vote:          str  = ""
    amended:       str  = ""
    charter_right: str  = ""
    description:   str  = ""
    final_action:  Optional[Dict] = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "POR"

    def to_dict(self) -> Dict[str, Any]:
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
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.charter_right:
            msg += f" - charter right {self.charter_right}"
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self) -> str:
        return f"[PolicyOrder: {str(self)}]"


@dataclass
class Ordinance(AgendaItem):
    uid: str
    url: str
    cma:           str  = ""
    order:         str  = ""
    application:   str  = ""
    sponsor:       str  = ""
    cosponsors:    str  = ""
    action:        str  = ""
    vote:          str  = ""
    amended:       str  = ""
    description:   str  = ""
    final_action:  Optional[Dict] = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "ORD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Unique Identifier": self.uid,
            "Link":              self.url,
            "CMA":               self.cma,
            "Policy Order":      self.order,
            "Application":       self.application,
            "Sponsor":           self.sponsor,
            "Co-Sponsors":       ",".join(self.cosponsors),
            "Outcome":           self.action,
            "Vote":              self.vote,
            "Amended":           self.amended,
            "Summary":           self.description,
            "Meeting":           self.meeting_uid,
            "Meeting Date":      self.meeting_date,
            "Notes":             self.notes,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self) -> str:
        return f"[Ordinance: {str(self)}]"


@dataclass
class AwaitingReport(AgendaItem):
    uid: str
    url: str
    description:  str = ""
    department:   str = ""
    category:     str = ""
    policy_order: str = ""
    notes:        str = ""
    final_action: Optional[Dict] = None

    @property
    def type(self):
        return "AR"

    def setMeeting(self, meeting: 'Meeting'):
        pass

    def update(self, **kwargs):
        if 'description' in kwargs:
            self.description = kwargs['description']
        if 'department' in kwargs:
            self.department = kwargs['department']
        if 'category' in kwargs:
            self.category = kwargs['category']
        if 'policy_order' in kwargs:
            self.policy_order = kwargs['policy_order']

    def to_dict(self) -> Dict[str, Any]:
        return {
            "Unique Identifier": self.uid,
            "Department":        self.department,
            "Category":          self.category,
            "Policy Order":      self.policy_order,
            "Link":              self.url,
            "Description":       self.description,
        }

    def __str__(self) -> str:
        msg = " ".join([self.uid, self.url])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self) -> str:
        return f"[AwaitingReport: {str(self)}]"

@dataclass
class ItemInfo:
    category:      str  = ""
    charter_right: str  = ""
    cma:           str  = ""
    order:         str  = ""
    app:           str  = ""
    awaiting:      str  = ""
    action:        str  = ""
    amended:       str  = ""
    history:       Optional[Dict]       = None
    sponsor:       Optional[List[str]]  = None
    cosponsors:    Optional[List[str]]  = None


def parseAction(line) -> Tuple[str, str]:
    ## Check for voice vote
    match = re.match(r"(?:Order )?(.+?)\s+(?:by|on) (?:an |am )?(affirmative vote|voice vote)", line, re.IGNORECASE)
    if match:
        action, vote_type = match.groups()
        return (toTitleCase(action), toTitleCase(vote_type))

    ## Check for vote count
    match = re.match(r"(?:Order )?(.+?)\s\[?((?:\d-\d-\d(?:-\d)?)|(?:\d+ to \d+)|Unanimous)\]?", line, re.IGNORECASE)
    if match:
        action, vote = match.groups()
        return (toTitleCase(action), toTitleCase(vote))

    match = re.match(r"(?:Order )(.+)", line, re.IGNORECASE)
    if match:
        action = match.groups()[0]
        return (toTitleCase(action), "")

    return (line, "")


def extractAction(action) -> str:
    """Find the simple action from an action string"""
    if action == "Failed of Adoption":
        action = 'Failed'
    else:
        match = re.match(r"(Fail(?:s|ed) to )?Pass(?:ed)? to be (\w+)", action, re.IGNORECASE)
        if match:
            if match.groups()[0]:
                action = 'Failed'
            else:
                action = match.groups()[1]

    ## Cleanup
    if action == "Ordainded":
        action = "Ordained"

    return action


def processCma(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> CMA:
    """Process a CMA agenda item"""
    ## Clean up title
    title = re.sub(r"(?:A|Transmitting) ?communication (?:transmitted )?from (?:.+), City Manager, relative to ", "", title, flags=re.IGNORECASE)
    title = re.sub(r"^the (?=appropriation|(?:re-?)?appointment|transfer)", "", title, flags=re.IGNORECASE).capitalize()
    return CMA(uid, num, info.category, info.awaiting, info.order, link, action, vote, info.charter_right, title, info.history)


def processApp(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> Application:
    """Process an application agenda item"""
    ## Attempt to get the name
    name    = ""
    subject = ""
    options = "|".join(("regarding", "to amend", "transmitting", "petitioning", "opposing", "urging"))
    regex = re.compile(fr"An? (?:application|(?:zoning )?petition|request) (?:has been|was) (?:received? ?from|filed by) (.+?),? ((?:requesting ?(?:permission|that)?|{options}) .+)", re.IGNORECASE)
    match = regex.search(title)
    if match:
        name, subject = match.groups()
    else:
        subject = title

    ## Attempt to get address
    address = ""
    match = re.search(r"at the premises numbered ([^;]+)(?:;|\. Approval)", subject)
    if match:
        address = match.groups()[0]

    return Application(uid, num, info.category, name, subject, link, action, vote, info.charter_right, address, info.history)


def processCom(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> Communication:
    """Process a communication agenda item"""
    ## pylint: disable=unused-argument
    name    = ""
    subject = ""
    address = ""

    ## Attempt to match the name of a person
    types = "|".join(["communication", "email", "e-mail", "written protest", "zoning petition"])
    options = "|".join((
        "regarding", "expressing", "transmitting", "commenting", "stating", "re", "relating to", "relative to", "noting that", "concerning", "stated", "raising",
        "announcing that", "outlining", "spoke about",
    ))
    opinions = (
        "supporting", "in support", "on support", "supported", "endorsing", "in favor", "urging", "requesting", "thanking", "encouraging", "to amend",
        "opposing", "in opposition",
    )
    options += "|" + "|".join(opinions)
    match = re.search(fr"(?:\w+ )?(?:{types})s? (?:was|were|has been)? ?(?:received )?from ?(.+?)(?:, (\d.+?))?,? ({options})[,:]? (.+)", title, re.IGNORECASE)
    if match:
        name, address, option, subject = match.groups()
        address = address or ""
        if option in opinions:
            subject = f"{option} {subject}"

    ## Attempt to match 'Sundry'
    if match is None:
        match = re.search(fr"Sundry (communication|e-?mail)s? (?:(?:was|were|have been)? ?(?:received|regarding))?,? ?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Sundry'
            subject = match.groups()[0]

    ## Attempt to match 'anonymous'
    if match is None:
        match = re.search(fr"(?:A|An)? ?(anonymous|unidentified) (?:{types})s? (?:(?:was|were|have been)? ?received)?,? ?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Anonymous'
            subject = match.groups()[0]
    if match is None:
        match = re.search(fr"A (?:{types}) (?:(?:was|were|have been)? ?received)?,? ?(?:anonymously )?(?:{options})[,:]? (.+)", title, re.IGNORECASE)
        if match:
            name = 'Anonymous'
            subject = match.groups()[0]

    ## Backup
    if not subject:
        subject = title

    return Communication(uid, num, name, address, subject, link)


def processRes(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> Resolution:
    """Process a resolution agenda item"""
    ## pylint: disable=unused-argument
    return Resolution(uid, num, info.category, link, info.sponsor, info.cosponsors, info.action, vote, title, info.history)


def processPor(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> PolicyOrder:
    """Process a policy order agenda item"""
    ## pylint: disable=unused-argument
    return PolicyOrder(uid, num, link, info.sponsor, info.cosponsors, info.action, vote, info.amended, info.charter_right, title, info.history)


def processOrd(info: 'ItemInfo', uid, num: int, title, link, vote, action) -> Ordinance:
    """Process an ordinance agenda item"""
    ## pylint: disable=unused-argument
    ## Clean up title
    title = re.sub(r"(?:An? )Ordinance (?:.+ )?has been received (?:from City Clerk(?: .+)?)?,?.*?relative to ", "", title, flags=re.IGNORECASE)

    ## Process info
    if info.history is not None and 'action' in info.history:
        action = info.history['action']

    return Ordinance(uid, link, info.cma, info.order, info.app, info.sponsor, info.cosponsors, action, vote, info.amended, title, info.history)


def uidToFileSafe(uid) -> str:
    """Take a meeting agenda item UID and make it file name safe"""
    return uid.replace(' ', '_').replace('#', 'no')
