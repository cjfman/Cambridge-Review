import datetime as dt
import json
import os
import re
import requests
import sys

from textwrap import dedent
from typing import Any, Iterable, List, Optional

USE_TERMCOLOR = True
REQUEST_HDR = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.105 Safari/537.36'
}

try:
    from termcolor import colored
except:
    print("Cannot import termcolor. Disabling terminal coloring", file=sys.stderr)
    USE_TERMCOLOR=False

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def print_red(msg, **kwargs):
    if USE_TERMCOLOR:
        print(colored(msg, 'red'), **kwargs)
    else:
        print(msg, **kwargs)


def print_green(msg, **kwargs):
    if USE_TERMCOLOR:
        print(colored(msg, 'green'), **kwargs)
    else:
        print(msg, **kwargs)


def overlayKeys(original: dict, other: dict, keys: Iterable):
    for key in keys:
        original[key] = other[key]


def toTitleCase(txt) -> str:
    if not txt:
        return txt

    words = [x.title() if len(x) > 3 else x.lower() for x in txt.split(' ')]
    words[0]  = words[0].title()
    words[-1] = words[-1].title()
    return " ".join(words)


def capitalizeFirst(txt) -> str:
    """Capitalize only the first character, preserving existing capitalization
    (e.g. proper nouns) in the rest of the string."""
    if not txt:
        return txt
    return txt[0].upper() + txt[1:]


def setDefaultValue(d: dict, v: Any, keys: Iterable):
    for key in keys:
        if key not in d:
            if callable(v):
                d[key] = v()
            else:
                d[key] = v


def simpleFormatDateTime(stamp: dt.datetime, *, date_only: bool = False) -> str:
    if date_only:
        return stamp.strftime('%-m/%-d/%Y')

    return stamp.strftime('%-m/%-d/%Y %-I:%-M %p')


def insertLineInFile(path, match, line, *, after: bool = True, stop: bool = True, replace: bool = False, regex: bool = False, re_args: Optional[List] = None) -> bool:
    """Insert a line into the file after a matching line"""
    check_match = lambda x: (not regex and match in x) or (regex and re.search(match, line, re_args))
    update = False
    re_args = re_args or []
    with open(path, "r+", encoding='utf8') as f:
        contents = f.readlines()
        ## Handle last line now to avoid IndexError
        if check_match(contents[-1]):
            if after:
                contents.append(line)
            else:
                contents.insert(-1, line)

            update = True
        if not update or not stop:
            ## Check all other lines
            for i, old_line in enumerate(contents):
                if check_match(old_line) and line != contents[i+1]:
                    if replace:
                        contents[i] = line
                    elif after:
                        contents.insert(i + 1, line)
                    else:
                        contents.insert(i, line)

                    update = True
                    if stop:
                        break

        ## Write the changes back to disk
        if update:
            f.seek(0)
            f.writelines(contents)

    return update


def insertCopyright(path, holder, *, tight: bool = False, blocking: bool = False) -> bool:
    """Insert a copyright notice"""
    year = dt.date.today().year
    style = 'style="position:absolute; right:1%; bottom: 1%;"'
    notice = f"<p {style}>Copyright &#169; {year}, {holder}. All rights reserved.</p>\n"
    if tight:
        holder = holder.replace("\n", "<br>")
        style = 'style="position:absolute; left:1%; bottom: 0px;"'
        notice = f"<p {style}>Copyright &#169; {year}<br>{holder}<br>All rights reserved.</p>\n"
    if blocking:
        notice = f"<div>{notice}</div>"
    return insertLineInFile(path, "</body>", notice, after=False)


def insertNoCache(path) -> bool:
    replace = '<head><meta charset="utf-8" /></head>'
    no_cache = dedent("""\
        <head>
            <meta charset="utf-8" />
            <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
            <meta http-equiv="Pragma" content="no-cache" />
            <meta http-equiv="Expires" content="0" />
        </head>
    """)
    return insertLineInFile(path, replace, no_cache, replace=True)


def insertDate(path, prefix, *, blocking=False) -> bool:
    txt = prefix + ": " + simpleFormatDateTime(dt.datetime.now())
    style = 'style="position:absolute; right:1%; bottom: 1%;"'
    return insertLineInFile(path, "</body>", notice, after=False)


def url_format_dt(stamp:dt.datetime) -> str:
    return "%2F".join([str(x) for x in [stamp.month, stamp.day, stamp.year]])


def strip_currency(cash) -> float:
    if cash[0] == '$':
        return float(cash[1:].replace(',', ''))

    raise ValueError(f"Cannot convert '{cash}' currency to float")


def format_dollar(val:float) -> str:
    return '${:,.2f}'.format(val)


def load_file(path, *, encoding='utf8', quiet: bool = True) -> Optional[str]:
    try:
        with open(path, encoding=encoding) as f:
            return f.read()
    except Exception as e:
        if not quiet:
            print(f"Failed to read file '{path}': {e}")

        return None


def load_json(path, *, encoding='utf8', quiet: bool = True) -> Optional[Any]:
    try:
        with open(path, encoding=encoding) as f:
            return json.load(f)
    except Exception as e:
        if not quiet:
            print(f"Failed to read file '{path}': {e}")

        return None


def fetch_url(url, cache_path=None, *, verbose: bool = False, force: bool = False) -> str:
    """Fetch the data from a URL. Optionally cache it locally to disk"""
    if cache_path is not None and not force and os.path.isfile(cache_path):
        if verbose:
            print(f"Reading '{url}' from cache '{cache_path}'")

        with open(cache_path, 'r', encoding='utf8') as f:
            return f.read()

    print(f"Fetching '{url}'")
    content = requests.get(url, headers=REQUEST_HDR).content.decode('utf8')
    if cache_path is not None:
        print(f"Caching '{cache_path}'")
        try:
            with open(cache_path, 'w', encoding='utf8') as f:
                f.write(content)
        except Exception as e:
            ## Remove bad cached file
            if os.path.isfile(cache_path):
                os.remove(cache_path)

            raise e

    return content
