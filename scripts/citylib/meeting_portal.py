## pylint: disable=too-many-branches
import re

import citylib.utils.html_parsing as hp

from citylib import agenda
from citylib.councillors import getCouncillorNames, lookUpCouncillorName
from citylib.utils import setDefaultValue


def findCouncillorsInRow(row):
    councillors = hp.findText(hp.findAllTags(row, 'td')[1]).split(',')
    return [lookUpCouncillorName(x.strip()) for x in councillors]


def processHistory(history_table):
    history = {}
    ## Look for a vote record
    for results_table in hp.findAllTags(history_table, 'table', 'VoteRecord'):
        rows = hp.findAllTags(results_table, 'tr')
        if not rows:
            continue
        for row in rows:
            role = hp.findText(row, 'td', 'Role')
            if not role:
                continue

            ## Check for the type of vote
            role = role.lower().replace(':', '')
            if role == "result":
                result = hp.findText(row, 'td', 'Result').lower()
                if result == "charter right":
                    ## Found a charter right
                    history['charter_right'] = True
                else:
                    ## Try and parse an action
                    action, vote = agenda.parseAction(result)
                    if action is not None:
                        history['action'] = action.strip()
                        history['vote']   = vote.strip()
            elif role in ('yeas', 'nays', 'present', 'absent', 'recused'):
                history[role] = findCouncillorsInRow(row)

    if not history:
        ## Look for affirmative vote
        txt = hp.findText(history_table, 'p').lower()
        if 'affirmative' in txt:
            history['vote'] = "Affirmative Vote"
        elif 'voice' in txt:
            history['vote'] = "Voice Vote"

    if history:
        ## Set default values
        setDefaultValue(history, "", ('action', 'vote', 'charter_right', 'amended'))
        setDefaultValue(history, list, ('yeas', 'nays', 'recused', 'present', 'absent'))

        ## Check action
        if history['action']:
            ## Check for amended
            match = re.match(r"(.+) as amended", history['action'], re.IGNORECASE)
            if match:
                history['action'] = match.groups()[0]
                history['amended'] = 'yes'

            ## Other actions
            history['action'] = agenda.extractAction(history['action'])

        ## Set absence
        if history['yeas']:
            all_councillors = set(getCouncillorNames())
            councillors = set(history['yeas'] + history['nays'] + history['present'])
            history['absent'] = list(sorted(all_councillors.difference(councillors)))

    return history
