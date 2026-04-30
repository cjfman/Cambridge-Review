## pylint: disable=too-many-locals,too-many-branches,line-too-long,missing-function-docstring

import datetime as dt
import re

from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

from citylib.councillors import lookUpCouncillorName
from citylib.utils import toTitleCase

MAX_MSG_LEN = 48

class AgendaItem:
    """Abstract class"""
    ## pylint: disable=no-member,attribute-defined-outside-init,access-member-before-definition
    def setMeeting(self, meeting):
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

    def getDate(self):
        if self._dt is not None:
            return self._dt

        self._dt = dt.datetime.fromisoformat(self.date)
        return self._dt

    def __lt__(self, other):
        return (self.getDate() < other.getDate())

    def __str__(self):
        return f"{self.body} - {self.type} {self.date} ({self.id})"

    def __repr__(self):
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
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "CMA"

    def to_dict(self):
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

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.action, f"[{self.vote}]", self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
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
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "APP"

    def to_dict(self):
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

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.name, self.meeting_uid])
        if len(self.subject) > MAX_MSG_LEN:
            return msg + " - " + self.subject[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.subject

    def __repr__(self):
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
    final_action: dict = None

    @property
    def type(self):
        return "COM"

    def to_dict(self):
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
    final_action: dict = None
    meeting_uid:  str  = ""
    meeting_date: str  = ""
    notes:        str  = ""

    @property
    def type(self):
        return "RES"

    def to_dict(self):
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

    def __str__(self):
        msg = " ".join([self.uid, self.category, self.sponsor, self.meeting_uid])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
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
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "POR"

    def to_dict(self):
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

    def __str__(self):
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.charter_right:
            msg += f" - charter right {self.charter_right}"
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
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
    final_action:  dict = None
    meeting_uid:   str  = ""
    meeting_date:  str  = ""
    notes:         str  = ""

    @property
    def type(self):
        return "ORD"

    def to_dict(self):
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

    def __str__(self):
        msg = " ".join([self.uid, self.sponsor, self.meeting_uid])
        if self.notes:
            msg += " - " + self.notes
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
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
    final_action: dict = None

    @property
    def type(self):
        return "AR"

    def setMeeting(self, meeting):
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

    def to_dict(self):
        return {
            "Unique Identifier": self.uid,
            "Department":        self.department,
            "Category":          self.category,
            "Policy Order":      self.policy_order,
            "Link":              self.url,
            "Description":       self.description,
        }

    def __str__(self):
        msg = " ".join([self.uid, self.url])
        if len(self.description) > MAX_MSG_LEN:
            return msg + " - " + self.description[:MAX_MSG_LEN] + "..."

        return msg + " - " + self.description

    def __repr__(self):
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
    history:       dict = None
    sponsor:       list = None
    cosponsors:    list = None


def parseAction(line):
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
