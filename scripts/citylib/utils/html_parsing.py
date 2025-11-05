from typing import Any, Dict, List, Tuple

import html5lib ## pylint: disable=unused-import
from bs4 import BeautifulSoup

def findTag(node, tag, cls=None):
    """Find a tag in a soup node"""
    if cls is None:
        return node.find(tag)

    return node.find(tag, {'class': cls})


def findAllTags(node, tag, cls=None):
    """Find all matching tags in a soup node"""
    if cls is None:
        return node.find_all(tag)

    return node.find_all(tag, {'class': cls})


def findATag(node, tag=None, cls=None) -> Tuple[str, str]:
    """Find an A tag in a soup node. Return the text and href"""
    if tag is not None:
        node = findTag(node, tag, cls)
    if node is None:
        raise Exception(f"Couldn't find a '{tag}' tag")

    a_tag = node.find('a')
    if a_tag is None:
        raise Exception("Couldn't find an 'a' tag")

    return (a_tag.text.strip(), a_tag['href'])


def findText(node, tag=None, cls=None) -> str:
    """Find the text in a soup node"""
    found = None
    if tag is None:
        found = node
    else:
        found = findTag(node, tag, cls)

    if found is None:
        return ''

    return found.text.strip()


def findAllText(node, tag, cls=None) -> List[str]:
    """Find all the text in a soup node"""
    found = findAllTags(node, tag, cls)
    return [x.text.strip() for x in found if x is not None]

