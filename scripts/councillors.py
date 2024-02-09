from typing import Tuple

import yaml

from utils import print_red


_councillor_info = {}
_councillor_quick_lookup = {}
def getCouncillorNames(*, include_aliases=False) -> Tuple[str]:
    if not _councillor_info:
        return tuple()
    if include_aliases:
        return tuple(_councillor_quick_lookup.keys())

    return tuple(_councillor_info.keys())


def setCouncillorInfo(path, year=None) -> bool:
    ## pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
    ## Load file
    all_info = None
    try:
        with open(path, 'r', encoding='utf8') as f:
            all_info = yaml.load(f)
    except Exception as e:
        print_red(f"Failed to open councillor info file '{path}': {e}")
        return False

    ## Validation
    if 'sessions' not in all_info:
        print_red(f"Councillor info file missing 'sessions' key")
        return False
    if 'councillors' not in all_info:
        print_red(f"Councillor info file missing 'councillors' key")
        return False

    if year is None:
        year = max(all_info['sessions'])

    if year not in all_info['sessions']:
        print_red(f"Couldn't find year {year} in councillor info file {path}")
        return False

    session = all_info['sessions'][year]
    councillors = { x['name']: x for x in all_info['councillors'] }

    ## Set up mayor
    if 'mayor' not in session:
        print_red(f"Session year {year} doens't have a mayor")
        return False
    if session['mayor'] not in councillors:
        print_red(f"""Mayor "{session['mayor']}" not found in councillors list""")
        return False

    _councillor_info[session['mayor']] = dict(councillors[session['mayor']])
    _councillor_info[session['mayor']]['position'] = 'Mayor'

    ## Set up vice mayor
    if 'vice_mayor' not in session:
        print_red(f"Session year {year} doens't have a vice mayor")
        return False
    if session['vice_mayor'] not in councillors:
        print_red(f"""Vice Mayor "{session['vice_mayor']}" not found in councillors list""")
        return False

    _councillor_info[session['vice_mayor']] = dict(councillors[session['vice_mayor']])
    _councillor_info[session['vice_mayor']]['position'] = 'Vice Mayor'

    ## Set up councillors
    if 'councillors' not in session:
        print_red(f"Session year {year} doesn't have any councillors")
        return False

    for name in session['councillors']:
        if name not in councillors:
            print_red(f"Councillor {name} not found in councillors list")
            return False

        _councillor_info[name] = dict(councillors[name])
        _councillor_info[name]['position'] = "Councillor"

    ## Create quick lookups for every name combination
    for name, info in _councillor_info.items():
        position = info['position']
        aliases = [name, f"{position} {name}"]
        for alias in info['aliases']:
            aliases.append(alias)
            aliases.append(f"{position} {alias}")

        for alias in aliases:
            _councillor_quick_lookup[alias]         = name
            _councillor_quick_lookup[alias.lower()] = name
            _councillor_quick_lookup[alias.replace(' ', '')]         = name
            _councillor_quick_lookup[alias.replace(' ', '').lower()] = name

    return True


def lookUpCouncillorName(name):
    if not _councillor_quick_lookup:
        return name

    ## Quick look up
    if name in _councillor_quick_lookup:
        return _councillor_quick_lookup[name]
    if name.lower() in _councillor_quick_lookup:
        return _councillor_quick_lookup[name.lower()]

    ## Remove title
    orig_name = name
    name = name.lower()
    name = name.replace("vice mayor", "").strip()
    name = name.replace("mayor", "").strip()
    name = name.replace("councilor", "").strip()
    if name in _councillor_quick_lookup:
        return _councillor_quick_lookup[name]

    print_red(f"""Error: Didn't find full name for councillor "{orig_name}". Using fallback""")
    return name
