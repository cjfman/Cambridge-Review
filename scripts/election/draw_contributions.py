#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import json
import math
import random
import re
import os
import sys

from collections import defaultdict
from typing import Dict, List

from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

from pathlib import Path

import folium
from branca.element import Template, MacroElement

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')

from citylib import utils
from citylib.filers import Filer
from citylib.utils import gis
from citylib.utils.gis import CITY_BOUNDARY
from citylib.utils.simplehtml import Element, LinearGradient, Text, TickMark

VERBOSE = False
DEBUG   = False

FUZZ_DIST  = 30 ## 30 meters
DISCLAIMER = f"Contribution locations are purposefully off by {FUZZ_DIST} meters"

def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--address-cache", default="address_coordindates.json",
        help="File that contains address coordinates")
    parser.add_argument("--google-api-key", required=True,
        help="The file to the google API key")
    parser.add_argument("--title",
        help="Map title")
    parser.add_argument("--subtitle",
        help="Map subtitle")
    parser.add_argument("--filer",
        help="The filer's id")
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

    return min(max_val, max(min_val, val))


def fuzzCoords(coord, length=FUZZ_DIST):
    ## Calculate basic info
    lon = coord[0]
    lat = coord[1]
    earth = 40008 * 1000 ## Earth circumference in meters
    lat_circ = earth * math.cos(lat*2*math.pi/180)

    ## Choose a direction and move the circle
    angle = random.randint(0, 350)
    radians = angle*2*math.pi/360
    dy = length*math.sin(radians)
    dx = length*math.cos(radians)
    lat += dx*360/earth
    lon += dy*360/lat_circ
    return (lon, lat)


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
            if VERBOSE:
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
    street: str
    city_state: str

    @classmethod
    def fromJson(cls, data):
        amt = float(data['amount'][1:].replace(',', ''))
        return cls(data['date'], amt, data['streetAddress'], data['cityStateZip'])

    @property
    def city(self):
        match = re.search(r"^([^,]+)\s*,\s*[A-Z]{2}\s+\S+", self.city_state)
        if match:
            return match.groups()[0]

        return None

    @property
    def state(self):
        match = re.search(r"^[^,]+\s*,\s*([A-Z]{2})\s+\S+", self.city_state)
        if match:
            return match.groups()[0]

        return None


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


def sumContributions(*, contributors=None, contributions=None):
    if (contributors is None and contributions is None) or (contributors is not None and contributions is not None):
        raise ValueError("Exactly one argument is required")

    if contributors is not None:
        contributions = []
        for c in contributors:
            contributions.extend(c.contributions)

    city  = 0
    state = 0
    total = 0
    for c in contributions:
        total += c.amount
        if c.state == 'MA':
            state += c.amount
            if c.city == 'Cambridge':
                city += c.amount

    return (city, state, total)


def makeMapKey(title, box_size=8):
    ## Add elements
    y_off = 20
    x_off = 10
    text_h = 15
    els = []

    ## Title
    els.append(Text(title, x=x_off, y=y_off))
    y_off += text_h / 2

    ## Add circles
    txts = []
    circ_off = size_scale(1000, max_val=20, min_val=2, scale=1000)
    for x in (1, 10, 100, 500, 1000):
        radius = size_scale(x, max_val=20, min_val=2, scale=1000)
        y_off += radius*1.1 + 3
        els.append(Element(
            'circle',
            cx=(x_off + circ_off*1.1),
            cy=y_off,
            r=radius,
            stroke='black',
            stroke_width=3,
            fill='orange',
        ))
        txt = f"${x}"
        txts.append(txt)
        els.append(Text(txt, x=x_off+circ_off*2.4, y=y_off, dominant_baseline="central"))
        y_off += radius*1.1 + 3

    ## Create SVG
    width = min(15 * max([len(x) for x in txts]), 150) + circ_off*2.2
    width = max(8*len(title), width)
    height = y_off
    return Element('svg', els, width=width, height=height).to_html()


def makeContributionBox(title, in_city, in_state, total, cbox_h=20, cbox_w=400):
    ## Add elements
    y_off = 20
    x_off = 10
    text_h = 15
    els = []

    ## Title
    els.append(Text(f"{title}: ${total:.2f}", x=x_off, y=y_off))
    y_off += text_h

    ## Boxes
    headers = {
        'city':  "Cambridge",
        'state': "Massachusetts",
        'total': "Total",
    }
    fractions = {
        'city': in_city/total,
        'state': in_state/total,
        'total': 1,
    }
    perc_txts = {
        'city':  f"${int(in_city)} ({int(fractions['city']*100)}%)",
        'state': f"${int(in_state)} ({int(fractions['state']*100)}%)",
        'total': f"${int(total)}",
    }
    widths = {
        'city': int(cbox_w*fractions['city']),
        'state': int(cbox_w*fractions['state']),
        'total': cbox_w,
    }
    colors = {
        'city': '#6C8EBF',
        'state': 'orange',
        'total': '#FFF178',
    }
    txt_end = x_off + 20*(len(max(headers.values())))
    box_off = txt_end + 10

    for location in ('city', 'state', 'total'):
        txt_off = y_off+cbox_h//2 - 2
        els.append(Text(headers[location], x=txt_end, y=txt_off, dominant_baseline="central", text_anchor='end'))
        els.append(Element(
            'rect', x=box_off, y=y_off, width=widths[location], height=cbox_h,
            #stroke='black', stroke_width=2,
            fill=colors[location],
        ))
        perc_off = box_off + widths[location] + 10
        els.append(Text(perc_txts[location], x=perc_off, y=txt_off, dominant_baseline="central"))
        y_off += cbox_h - 1

    ## Create SVG
    width = txt_end + max([10*len(perc_txts[x]) + widths[x] for x in ('city', 'state', 'total')])
    height = y_off+10
    return Element('svg', els, width=width, height=height).to_html()


def plotRecord(m, record, addr_map):
    addr = addressFromRecord(record)
    coord = addr_map[addr]
    if not coord:
        print(f"Skipping record with address '{addr}'")
        return

    if VERBOSE:
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

    if VERBOSE:
        print(f"Plotting {contributor}")

    coord = fuzzCoords(contributor.coord)
    lines = [
        f"Name: {contributor.name}",
        f"Total: ${contributor.total:.2f}",
        'Contributions',
    ]
    for c in contributor.contributions:
        lines.append(f" - {c.date} ${c.amount:.2f}")

    tooltip_txt = "<br />".join(lines)
    tooltip = folium.map.Tooltip(tooltip_txt, style="font-size: 1.5em;", sticky=False)
    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    radius = size_scale(contributor.total, max_val=20, min_val=2, scale=1000)
    folium.CircleMarker(coord, radius=radius, tooltip=tooltip, color="black", fill_color="orange", fill_opacity=0.4, stroke_width=3).add_to(m)


def plotColocatedContributors(contributors, coord, addr, m):
    if VERBOSE:
        print(f"Plotting contributor group at {addr}")

    coord = fuzzCoords(coord)
    lines = []
    total = 0
    for c in contributors:
        total += c.total
        lines.extend([
            f"Name: {c.name}",
            f"Total: ${c.total:.2f}",
            'Contributions',
        ])

        for d in c.contributions:
            lines.append(f" - {d.date} ${d.amount:.2f}")

        lines.append("---")

    del lines[-1]

    tooltip_txt = "<br />".join(lines)
    tooltip = folium.map.Tooltip(tooltip_txt, style="font-size: 1.5em;", sticky=False)
    angle = 1
    pin_args = { 'prefix': 'fa', 'color': 'green', 'icon': 'arrow-up' }
    radius = size_scale(total, max_val=20, min_val=2, scale=1000)
    folium.CircleMarker(coord, radius=radius, tooltip=tooltip, color="black", fill_color="orange", fill_opacity=0.4).add_to(m)


def makeMap(contributors, m, out_file, title=None, subtitle=None):
    grouped = defaultdict(list)
    for c in contributors:
        grouped[c.address].append(c)

    for group in sorted(grouped.values(), reverse=True):
        if not group[0].coord:
            print(f"Skipping group")
            continue

        plotColocatedContributors(group, group[0].coord, group[0].address, m)

    ## Load template
    template = None
    with open("templates/map_contributions.html") as f:
        template = f.read()

    if template is not None:
        contr_box = makeContributionBox("Contribution Total", *sumContributions(contributors=contributors))
        template = template.replace("{{SVG1}}", makeMapKey("Contribution Scale"))
        template = template.replace("{{DISCLAIMER}}", DISCLAIMER)
        template = template.replace("{{CONTRIBUTIONS}}", contr_box)
        if title:
            template = template.replace("{{TITLE}}", f'<h2>{title}</h2><p>{subtitle or ''}</p>')
        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    ## Make bounds and plot map
    all_coords = [c.coord for c in contributors]
    sw = min(all_coords)
    ne = max(all_coords)
    m.fit_bounds([sw, ne])
    m.save(out_file)
    print(f"Wrote to {out_file}")


def getFiler(cpfid):
    try:
        return Filer.fromFile(f"candidate_data/filers/{cpfid}.json")
    except Exception as e:
        print(f"Couldn't load filer {cpfid}: {e}")
        return None


def main(args):
    ## Get info
    addr_map = AddressMap(utils.load_file(args.google_api_key), args.address_cache)
    records = getContributions(args.records_file)
    contributors = recordsToContributors(records, addr_map=addr_map)
    title = args.title
    filer = None
    if args.filer:
        filer = getFiler(args.filer)
        title = filer.candidate_name + " Contributions"
        print(f"Using title: {title}")
    else:
        title = "Contributions"


    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)#, tiles="Cartodb Positron")
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)

    try:
        makeMap(contributors, m, args.out_file, title=title, subtitle=args.subtitle)
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
