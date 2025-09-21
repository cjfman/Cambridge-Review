#!/usr/bin/env python3

import datetime as dt
import json
import os
import re

import dateutil

from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order
from typing import Dict, List

from .utils import format_dollar, strip_currency, eprint

VERBOSE=False
FORCE_ACTIVE = [17259, 18437]

class Filer:
    def __init__(self, cpfid:int, committee_name, candidate_name="", *, reports=None, cash_on_hand:float=0):
        self.cpfid               = cpfid
        self.committee_name      = committee_name
        self.candidate_name      = candidate_name
        self.cash_on_hand        = cash_on_hand
        self.reports             = reports or []
        self.treasurer           = ""
        self.comm_address_line_1 = ""
        self.comm_address_city   = ""
        self.comm_address_state  = ""
        self.comm_address_zip    = ""
        self.website             = ""
        self.position            = ""
        self.organization_date   = None
        self.data                = None

    @classmethod
    def fromJson(cls, obj, *, simple=False):
        if isinstance(obj, str):
            obj = json.loads(obj)

        filer = None
        if simple:
            filer = Filer(obj['cpfId'], obj['committeeName'], obj['filerName'])
        else:
            filer = Filer(obj['filer']['cpfId'], obj['filer']['committeeName'], obj['filer']['fullName'])
            treas = obj['filer']['treasurer']
            filer.treasurer           = treas['fullName']
            filer.comm_address_line_1 = treas['streetAddress']
            filer.comm_address_city   = treas['city']
            filer.comm_address_state  = treas['state']
            filer.comm_address_zip    = treas['zipCode']

        filer.data = obj
        return filer

    @classmethod
    def fromFile(cls, path):
        with open(path, encoding='utf8') as f:
            return cls.fromJson(json.load(f))

    def active(self):
        if self.cpfid in FORCE_ACTIVE:
            if VERBOSE:
                eprint(f"{self.committee_name} forced to be active")
            return True

        ## Was the account opened in the past year?
        if self.organization_date and (dt.datetime.now() - self.organization_date) < 365:
            if VERBOSE:
                eprint(f"{self.committee_name} found active due to organization date {self.organization_date}")
            return True

        ## Check recent transactions
        for report in self.reports[:3]:
            if report.credit_total and report.expenditure_total - report.credit_total:
                exp = format_dollar(report.expenditure_total)
                crd = format_dollar(report.credit_total)
                if VERBOSE:
                    eprint(f"{self.committee_name} found active due to report {report.reporting_period}: Exp {exp} Credits {crd}")
                return True

        if VERBOSE:
            eprint(f"{self.committee_name} is inactive")
        return False

    def missing_recent_report(self, *, months=1) -> bool:
        if not self.reports:
            return True

        then = dt.datetime.now().date() - dateutil.relativedelta.relativedelta(months=months)
        return (self.reports and self.reports[0].end_date < then)

    def load_reports(self, path):
        reports = None
        if os.path.isfile(path):
            reports = read_reports(path)
        elif os.path.isdir(path):
            reports = read_reports(os.path.join(path, f"{self.cpfid}_reports.json"))

        if reports is not None:
            self.reports = reports

        return reports

    def __str__(self):
        return f"{self.committee_name}({self.cpfid}) {self.candidate_name}"


class Report:
    def __init__(self):
        self.cpfid             = 0
        self.report_id         = 0
        self.committee_name    = ""
        self.filer_name        = ""
        self.reporting_period  = None
        self.start_date        = None
        self.end_date          = None
        self.startBalance      = 0
        self.endBalance        = 0
        self.cash_on_hand      = 0
        self.expenditure_total = 0
        self.credit_total      = 0
        self.other             = {}

    @classmethod
    def fromJson(cls, obj):
        if isinstance(obj, str):
            obj = json.loads(obj)

        report = cls()
        report.cpfid             = obj['cpfId']
        report.report_id         = obj['reportId']
        report.committee_name    = obj['committeeName']
        report.filer_name        = obj['filerFullName']
        report.reporting_period  = obj['reportingPeriod']
        report.start_date        = dt.datetime.strptime(obj['startDate'], "%m/%d/%Y").date()
        report.end_date          = dt.datetime.strptime(obj['endDate'],   "%m/%d/%Y").date()
        report.startBalance      = strip_currency(obj['startBalance'])
        report.endBalance        = strip_currency(obj['endBalance'])
        report.cash_on_hand      = strip_currency(obj['cashOnHand'])
        report.expenditure_total = strip_currency(obj['expenditureTotal'])
        report.credit_total      = strip_currency(obj['creditTotal'])
        report.other             = obj

        return report


@dataclass
class Contribution:
    date: str
    amount: float
    street: str
    city_state: str

    @classmethod
    def fromJson(cls, data):
        amt = strip_currency(data['amount'])
        return cls(data['date'], amt, data['streetAddress'], data['cityStateZip'])

    @property
    def city(self):
        match = re.search(r"^([^,]+)\s*,\s*[A-Z]{2}\s+\S+", self.city_state)
        if match:
            return match.groups()[0]

        return None

    @property
    def state(self):
        match = re.search(r"^[^,]+\s*,\s*([A-Z]{2})\s+\S+", self.city_state)
        if match:
            return match.groups()[0]

        return None


class Contributor:
    @staticmethod
    def make_key(name, addr):
        return f"{name}-{addr}"

    @classmethod
    def make_key_from_json(cls, data):
        return cls.make_key(data['fullNameReverse'], address_from_record(data))

    def __init__(self, name, addr, coord=None):
        self.name    = name
        self.address = addr
        self.coord   = coord
        self.contributions = []

    @classmethod
    def fromJson(cls, data, *, addr_map=None):
        coord = None
        addr = address_from_record(data)
        if addr_map:
            coord = addr_map[addr]

        contributor = cls(data['fullNameReverse'], addr, coord)
        contributor.contributions.append(Contribution.fromJson(data))
        return contributor

    @property
    def total(self):
        return sum([x.amount for x in self.contributions])

    def key(self):
        return self.make_key(self.name, self.address)

    def addRecord(self, record):
        self.contributions.append(record)

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return (self.name == other.name and self.address == other.address)

    def __lt__(self, other):
        return (self.total < other.total)

    def __str__(self):
        if self.coord:
            coord = tuple([f"{x:.5f}" for x in self.coord])
            return f"Name: {self.name}; Address {self.address}; Coordinates: {coord}"

        return f"Name: {self.name}; Address {self.address}"

    def __repr__(self):
        return f"[Contributor {self}]"


def read_reports(path):
    data = None
    try:
        with open(path, encoding='utf8') as f:
            data = json.load(f)
    except OSError as e:
        eprint(f"Failed to open reports file '{path}': {e}")
        return None

    try:
        reports = sorted([Report.fromJson(x) for x in data['items']], key=lambda x: x.end_date, reverse=True)
        return reports
    except (KeyError, ValueError) as e:
        eprint(f"Reports file wasn't properly formatted: {e}")
        return None

    return reports


def read_report_and_filer(path) -> Filer:
    """Read a report and infer the filer"""
    reports = read_reports(path)
    if not reports:
        return None

    recent = reports[0]
    return Filer(recent.cpfid, recent.committee_name, recent.filer_name, cash_on_hand=recent.cash_on_hand, reports=reports)


def address_from_record(record):
    return f"{record['streetAddress']}, {record['cityStateZip']}"


def records_to_contributors(records, *, addr_map) -> Dict[str, Contributor]:
    contributors = {}
    for record in records:
        if record['fullNameReverse'] == "Aggregated Unitemized Receipts":
            continue

        key = Contributor.make_key_from_json(record)
        if key in contributors:
            contributors[key].addRecord(Contribution.fromJson(record))
        else:
            c = Contributor.fromJson(record, addr_map=addr_map)
            if c.coord is not None:
                contributors[key] = c
            else:
                print(f"No coordindates found for {c}")

    return list(contributors.values())


def sum_contributions(*, contributors=None, contributions=None):
    if (contributors is None and contributions is None) or (contributors is not None and contributions is not None):
        raise ValueError("Exactly one argument is required")

    if contributors is not None:
        contributions = []
        for c in contributors:
            contributions.extend(c.contributions)

    city  = 0
    state = 0
    total = 0
    for c in contributions:
        total += c.amount
        if c.state == 'MA':
            state += c.amount
            if c.city == 'Cambridge':
                city += c.amount

    return (city, state, total)
