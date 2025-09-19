#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import json
import sys

from pathlib import Path

import folium

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')

from citylib import utils
from citylib.utils import gis
from citylib.utils.gis import CITY_BOUNDARY

VERBOSE   = False
DEBUG     = False

def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--google-api-key", required=True,
        help="The file to the google API key")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("records_file",
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


def getContributions(path):
    with open(path, encoding='utf8') as f:
        return json.load(f)['items']


def contributionCoordinates(record, key):
    addr = f"{record['streetAddress']} {record['cityStateZip']}"
    coord = utils.address_to_coordinates(addr, key)
    print(f"{addr} >> {coord}")
    return coord


def main(args):
    ## Get info
    key = utils.load_file(args.google_api_key)
    records = getContributions(args.records_file)
    coord = contributionCoordinates(records[0], key)

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)

    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    icon = folium.Icon(**pin_args)
    folium.Marker(coord, icon=icon, tooltip='test').add_to(m)
    m.save(args.out_file)
    print(f"Wrote to {args.out_file}")


def makeLayer(name, geo_path, show=False, weight=2, tooltip=None, tooltip_name=None, sticky=False, control=True, **kwargs):
    geojson = gis.GisGeoJson(geo_path)
    style_function = lambda x: {
        'fillColor': '#000000',
        'fillOpacity': 0.0,
        'weight': weight,
        'color': '#000000',
        'opacity': 1,
    }

    geo = folium.GeoJson(geojson.geojson, name=name, show=show, control=control, style_function=style_function)
    if tooltip is not None:
        tooltip_name = tooltip_name or tooltip
        folium.GeoJsonTooltip(fields=[tooltip], aliases=[tooltip], sticky=sticky).add_to(geo)

    return geo


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
