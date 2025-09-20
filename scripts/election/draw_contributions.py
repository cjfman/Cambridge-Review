#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import json
import math
import os
import sys

from typing import Dict, List

from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

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


def size_scale(val, max_val, min_val=0, scale=None):
    scale = math.log(1 + scale)
    val = math.log(1 + val)
    if scale:
        val *= max_val / scale

    print(val)
    return min(max_val, max(min_val, val))


def addressFromRecord(record):
    return f"{record['streetAddress']}, {record['cityStateZip']}"


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
                json.dump(self.cache, f, indent=4)
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
        self.updated = True
        return coord

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


@dataclass
class Contribution:
    date: str
    amount: float

    @classmethod
    def fromJson(cls, data):
        amt = float(data['amount'][1:].replace(',', ''))
        return cls(data['date'], amt)


class Contributor:
    @staticmethod
    def make_key(name, addr):
        return f"{name}-{addr}"

    @classmethod
    def make_key_from_json(cls, data):
        return cls.make_key(data['fullNameReverse'], addressFromRecord(data))

    def __init__(self, name, addr, coord=None):
        self.name    = name
        self.address = addr
        self.coord   = coord
        self.contributions = []

    @classmethod
    def fromJson(cls, data, *, addr_map=None):
        coord = None
        addr = addressFromRecord(data)
        if addr_map:
            coord = addr_map[addr]

        contributor = cls(data['fullNameReverse'], addr, coord)
        contributor.contributions.append(Contribution.fromJson(data))
        return contributor

    @property
    def total(self):
        return sum([x.amount for x in self.contributions])

    def key(self):
        return self.make_key(self.name, self.address)

    def addRecord(self, record):
        self.contributions.append(record)

    def __hash__(self):
        return hash(self.key())

    def __eq__(self, other):
        return (self.name == other.name and self.address == other.address)

    def __lt__(self, other):
        return (self.total < other.total)

    def __str__(self):
        if self.coord:
            coord = tuple([f"{x:.5f}" for x in self.coord])
            return f"Name: {self.name}; Address {self.address}; Coordinates: {coord}"

        return f"Name: {self.name}; Address {self.address}"

    def __repr__(self):
        return f"[Contributor {self}]"


def getContributions(path) -> List[Dict]:
    with open(path, encoding='utf8') as f:
        return json.load(f)['items']


def recordsToContributors(records, *, addr_map) -> Dict[str, Contributor]:
    contributors = {}
    for record in records:
        key = Contributor.make_key_from_json(record)
        if key in contributors:
            contributors[key].addRecord(Contribution.fromJson(record))
        else:
            c = Contributor.fromJson(record, addr_map=addr_map)
            if c.coord is not None:
                contributors[key] = c
            else:
                print(f"No coordindates found for {c}")

    return list(contributors.values())


def plotRecord(m, record, addr_map):
    addr = addressFromRecord(record)
    coord = addr_map[addr]
    if not coord:
        print(f"Skipping record with address '{addr}'")
        return

    print(f"Plotting record with address {addr} at {coord}")
    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    icon = folium.Icon(**pin_args)
    tooltip_txt = "<br />".join([f"{x}: {record[x]}" for x in ('fullNameReverse', 'amount')])
    tooltip = folium.map.Tooltip(tooltip_txt, style="font-size: 24px;", sticky=True)
    folium.Marker(coord, icon=icon, tooltip=tooltip).add_to(m)


def plotContributor(contributor, m):
    if not contributor.coord:
        print(f"Skipping {contributor}")
        return

    print(f"Plotting {contributor}")
    lines = [
        f"Name: {contributor.name}",
        f"Address: {contributor.address}",
        f"Total: ${contributor.total:.2f}",
        'Contributions',
    ]
    for c in contributor.contributions:
        lines.append(f" - {c.date} ${c.amount:.2f}")

    tooltip_txt = "<br />".join(lines)
    tooltip = folium.map.Tooltip(tooltip_txt, style="font-size: 1.5em;", sticky=False)
    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
#    radius = size_scale(contributor.total, max_val=100, min_val=20, scale=1000)
#    folium.Circle(contributor.coord, radius=radius, tooltip=tooltip, color="black", fill_color="orange", fill_opacity=0.4).add_to(m)
    radius = size_scale(contributor.total, max_val=20, min_val=2, scale=1000)
    folium.CircleMarker(contributor.coord, radius=radius, tooltip=tooltip, color="black", fill_color="orange", fill_opacity=0.4).add_to(m)


def makeMap(contributors, m, out_file):
    for c in sorted(contributors, reverse=True):
        plotContributor(c, m)

    ## Make bounds and plot map
    all_coords = [c.coord for c in contributors]
    sw = min(all_coords)
    ne = max(all_coords)
    m.fit_bounds([sw, ne])
    m.save(out_file)
    print(f"Wrote to {out_file}")


def main(args):
    ## Get info
    addr_map = AddressMap(utils.load_file(args.google_api_key), args.address_cache)
    records = getContributions(args.records_file)
    contributors = recordsToContributors(records, addr_map=addr_map)

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)#, tiles="Cartodb Positron")
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)

    try:
        makeMap(contributors, m, args.out_file)
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
