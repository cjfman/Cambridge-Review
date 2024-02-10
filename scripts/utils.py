import re

from termcolor import colored

def print_red(msg, **kwargs):
    print(colored(msg, 'red'), **kwargs)


def print_green(msg, **kwargs):
    print(colored(msg, 'green'), **kwargs)


def overlayKeys(original, other, keys):
    for key in keys:
        original[key] = other[key]


def toTitleCase(txt) -> str:
    if not txt:
        return txt

    words = [x.title() if len(x) > 3 else x.lower() for x in txt.split(' ')]
    words[0]  = words[0].title()
    words[-1] = words[-1].title()
    return " ".join(words)


def insertLineInFile(path, match, line, *, after=True, stop=True, regex=False, re_args=None) -> bool:
    """Insert a line into the file after a matching line"""
    check_match = lambda x: (not regex and match in x) or (regex and re.search(match, line, re_args))
    update = False
    re_args = re_args or []
    with open(path, "r+", encoding='utf8') as f:
        contents = f.readlines()
        ## Hadnle last line now to avoid IndexError
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
                    if after:
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
