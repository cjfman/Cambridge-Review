#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import sys

from pathlib import Path

import folium

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.utils.gis import CITY_BOUNDARY

VERBOSE   = False
DEBUG     = False

def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("contributions_file",
        help="JSON file of contriutions")
    parser.add_argument("out_file",
        help="Output file")

    args = parser.parse_args()

    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True

    return args

def main(args):
    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)

    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    icon = folium.Icon(**pin_args)
    folium.Marker([42.378, -71.11], icon=icon, tooltip='test').add_to(m)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
