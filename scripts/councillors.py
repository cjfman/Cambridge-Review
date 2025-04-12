from typing import Tuple

import yaml

from utils import print_red


_session_year = None
_councillor_info = {}
_councillor_quick_lookup = {}
_councillor_all_lookup = {}
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
        print(f"No year specified. Using year {year}")

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
        for alias in expandName(name, info):
            _councillor_quick_lookup[alias] = name
            _councillor_all_lookup[alias] = name

    for name, info in councillors.items():
        if name not in _councillor_info:
            info['position'] = 'non-sitting'
            for alias in expandName(name, info):
                _councillor_all_lookup[alias] = name

    global _session_year
    _session_year = year
    return True


def expandName(name, info):
    position = info['position']
    aliases = [name, f"{position} {name}"]
    modified = []
    for alias in info['aliases']:
        aliases.append(alias)
        aliases.append(f"{position} {alias}")

    for alias in aliases:
        modified.append(alias)
        modified.append(alias.lower())
        modified.append(alias.replace(' ', ''))
        modified.append(alias.replace(' ', '').lower())
        modified.append(alias.replace('.', ''))
        modified.append(alias.replace('.', '').lower())

    return aliases + modified


def lookUpCouncillorName(name, *, include_all=True):
    if not name:
        return ""
    if not _councillor_quick_lookup:
        return name
    if not isinstance(name, str):
        print_red(f"Error: '{name}' is not a valid name. Blanking out")
        return "!!!"
    if name.lower().startswith("city clerk"):
        print_red(f"Error: '{name}' is not a city councillor. Blanking out")
        return "!!!"

    ## Quick look up
    lookup = _councillor_quick_lookup
    if include_all:
        lookup = _councillor_all_lookup
    if not name[-1].isalpha():
        name = name[:-1]

    if name in lookup:
        return lookup[name]
    if name.lower() in lookup:
        return lookup[name.lower()]

    ## Remove title
    orig_name = name
    name = name.lower()
    name = name.replace("vice mayor", "").strip()
    name = name.replace("mayor", "").strip()
    name = name.replace("councilor", "").strip()
    name = name.replace("councillor", "").strip()
    if name in lookup:
        return lookup[name]

    print_red(f"""Error: Didn't find full name for councillor "{orig_name}". Using fallback "{name}".""")
    return name

def getSessionYear():
    return _session_year
