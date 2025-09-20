#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import json
import os
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
    parser.add_argument("--address-cache", default="address_coordindates.json",
        help="File that contains address coordinates")
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


class AddressMap:
    def __init__(self, api_key, cache_path=None):
        self.api_key    = api_key
        self.cache_path = cache_path
        self.cache      = {}
        self.updated    = False
        if self.cache_path:
            self.load()

    def load(self):
        if not os.path.isfile(self.cache_path):
            print(f"Can't load address cache file '{self.cache_path}'")
            return

        try:
            with open(self.cache_path, encoding='utf8') as f:
                self.cache = json.load(f)
        except Exception as e:
            print(f"Failed to load address cache file '{self.cache_path}': {e}")

    def save(self):
        if not self.updated:
            print("Cache wasn't updated. Not writing to file")
            return

        print("Cache changed size. Writing cache to file")
        try:
            with open(self.cache_path, 'w', encoding='utf8') as f:
                json.dump(self.cache, f)
        except Exception as e:
            print(f"Failed to save address cache file '{self.cache_path}': {e}")

    def query_address(self, addr):
        if addr in self.cache:
            return self.cache[addr]

        if not self.api_key:
            print("Cannot access google maps API without an access key")
            return None

        coord = utils.address_to_coordinates(addr, self.api_key)
        print(f"{addr} >> {coord}")
        self.cache[addr] = coord


    def __getitem__(self, key):
        if key not in self.cache:
            val = self.query_address(key)
            if val:
                self.cache[key] = val

            return val

        return self.cache[key]

    def __setitem__(self, key, value):
        self.updated = True
        self.cache[key] = value

    def __contains__(self, item):
        return (item in self.cache)


def getContributions(path):
    with open(path, encoding='utf8') as f:
        return json.load(f)['items']


def plotRecord(m, record, addr_map):
    addr = f"{record['streetAddress']} {record['cityStateZip']}"
    coord = addr_map[addr]
    if not coord:
        print(f"Skipping record with address '{addr}'")
        return

    print(f"Plotting record with address {addr} at {coord}")
    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    icon = folium.Icon(**pin_args)
    tooltip = "<br />".join([f"{x}: {record[x]}" for x in ('fullNameReverse', 'amount')])
    folium.Marker(coord, icon=icon, tooltip=tooltip).add_to(m)


def main(args):
    ## Get info
    addr_map = AddressMap(utils.load_file(args.google_api_key), args.address_cache)
    records = getContributions(args.records_file)

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)

    try:
        for record in records:
            plotRecord(m, record, addr_map)

        m.save(args.out_file)
        print(f"Wrote to {args.out_file}")
    finally:
        addr_map.save()


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
