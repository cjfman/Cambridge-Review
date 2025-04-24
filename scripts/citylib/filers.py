#!/usr/bin/env python3

import datetime as dt
import json

from . import utils

FORCE_ACTIVE = [17259]

class Filer:
    def __init__(self, cpfid:int, committee_name, *, reports=None, cash_on_hand:float=0):
        self.cpfid               = cpfid
        self.committee_name      = committee_name
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

    @classmethod
    def fromJson(cls, obj):
        if isinstance(obj, str):
            obj = json.loads(obj)

        filer = Filer(obj['filer']['cpfId'], obj['filer']['committeeName'])
        treas = obj['filer']['treasurer']
        filer.treasurer           = treas['fullName']
        filer.comm_address_line_1 = treas['streetAddress']
        filer.comm_address_city   = treas['city']
        filer.comm_address_state  = treas['state']
        filer.comm_address_zip    = treas['zipCode']
        return filer

    @classmethod
    def fromFile(cls, path):
        with open(path, encoding='utf8') as f:
            return cls.fromJson(json.load(f))

    def active(self):
        if self.cpfid in FORCE_ACTIVE:
            return True

        ## Was the account opened in the past year?
        if self.organization_date and (dt.datetime.now() - self.organization_date) < 365:
            print(f"{self.committee_name} found active due to organization date {self.organization_date}")
            return True

        ## Check recent transactions
        for report in self.reports[:3]:
            if report.credit_total and report.expenditure_total - report.credit_total:
                exp = utils.format_dollar(report.expenditure_total)
                crd = utils.format_dollar(report.credit_total)
                print(f"{self.committee_name} found active due to report {report.reporting_period}: Exp {exp} Credits {crd}")
                return True

        print(f"{self.committee_name} is inactive")
        return False



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
        report.startBalance      = utils.strip_currency(obj['startBalance'])
        report.endBalance        = utils.strip_currency(obj['endBalance'])
        report.cash_on_hand      = utils.strip_currency(obj['cashOnHand'])
        report.expenditure_total = utils.strip_currency(obj['expenditureTotal'])
        report.credit_total      = utils.strip_currency(obj['creditTotal'])
        report.other             = obj

        return report
