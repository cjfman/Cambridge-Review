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
from dataclasses import dataclass ## pylint: disable=import-error,wrong-import-order

from pathlib import Path

import folium
from branca.element import Template, MacroElement

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')

from citylib import filers, utils
from citylib.filers import Contributor, Contribution, Filer, address_from_record
from citylib.utils import gis, format_dollar, strip_currency
from citylib.utils import color_schemes as cs
from citylib.utils.addresses import AddressMap
from citylib.utils.gis import CITY_BOUNDARY, STATE_BOUNDARY
from citylib.utils.simplehtml import Element, LinearGradient, Text, TickMark

VERBOSE = False
DEBUG   = False

FUZZ_DIST  = 30 ## 30 meters
DISCLAIMER = f"Contributor locations are purposefully off by {FUZZ_DIST}m"
GRADIENT   = cs.ColorGradient(cs.BlueRedYellow, 1000, scale_fn=lambda x: math.log(1 + x/50))
SCALE_ARGS = {
    'max_val': 13,
    'min_val': 3,
    'scale':   1000,
}


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.set_defaults(subcmd=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--address-cache", default="address_coordindates.json",
        help="File that contains address coordinates")
    parser.add_argument("--google-api-key",
        help="The file to the google API key")

    shared_parser = argparse.ArgumentParser(description="The shared parser")
    shared_parser.add_argument("--title",
        help="Map title")
    shared_parser.add_argument("--subtitle",
        help="Map subtitle")
    shared_parser.add_argument("-m", "--mobile", action="store_true",
        help="Generate mobile version of map")

    ## Subparsers
    subparsers = parser.add_subparsers()

    ## single filer cmd
    single_parser = subparsers.add_parser('single-filer', parents=[shared_parser], add_help=False,
        help="create a map for a single filer")
    single_parser.set_defaults(subcmd=single_filer_hdlr)
    single_parser.add_argument("--filer",
        help="The filer's id")
    single_parser.add_argument("records_file",
        help="JSON file of contriutions")
    single_parser.add_argument("out_file",
        help="Output file")

    ## many filers cmd
    many_parser = subparsers.add_parser('many-filers', parents=[shared_parser], add_help=False,
        help="create a map for many filers")
    many_parser.set_defaults(subcmd=many_filers_hdlr)
    many_parser.add_argument("--out-file",
        help="Output file")
    many_parser.add_argument("records_files", nargs='+',
        help="JSON files of contriutions")

    ## Parse args
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


def makeMapKey(title, *, subtitles=None, box_size=8, horizontal=False):
    ## Add elements
    y_off = 20
    x_off = 10
    text_h = 15
    els = []

    ## Title
    els.append(Text(title, x=x_off, y=y_off))
    y_off += text_h / 2
    if subtitles is not None:
        y_off += text_h / 2
        for subtitle in subtitles:
            if subtitle:
                els.append(Text(subtitle, x=x_off, y=y_off))
                y_off += text_h
            else:
                y_off += text_h / 2
        y_off -= text_h / 2

    ## Add circles
    circ_off = size_scale(1000, **SCALE_ARGS)
    if horizontal:
        ## Move row down by half of the biggest circle
        y_off += circ_off*1.1

    txts = []
    for x in (1, 10, 100, 500, 1000):
        radius = size_scale(x, **SCALE_ARGS)
        if not horizontal:
            y_off += radius*1.2 + 3

        els.append(Element(
            'circle',
            cx=(x_off + circ_off*1.1),
            cy=y_off,
            r=radius,
            stroke=GRADIENT.pick(x),
            stroke_width=1,
            fill=GRADIENT.pick(x),
        ))
        txt = f"${x}"
        txts.append(txt)
        if not horizontal:
            els.append(Text(txt, x=x_off+circ_off*2.4, y=y_off, dominant_baseline="central"))
            y_off += radius*1.1 + 3
        else:
            x_off += max(radius*2 + 10, 20)
            els.append(Text(txt, x=x_off, y=y_off, dominant_baseline="central"))
            x_off += 8*len(txt) + 10

    ## Create SVG
    if not horizontal:
        width = min(15 * max([len(x) for x in txts]), 150) + circ_off*2.2
        width = max(8*len(title), width)
        height = y_off
    else:
        width = x_off + 10
        height = y_off + circ_off

    return Element('svg', els, width=width, height=height).to_html()


def makeContributionBox(title, in_city, in_state, total, *, cbox_h=20, cbox_w=400, subtxt=None):
    ## Add elements
    y_off = 10
    x_off = 5
    text_h = 15
    els = []

    ## Title
    title = f"{title}: {format_dollar(total)}"
    if not total:
        return f"<p>{title}</p>"

    els.append(Text(title, x=x_off, y=y_off))
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
        'city':  f"{format_dollar(in_city)} ({int(fractions['city']*100)}%)",
        'state': f"{format_dollar(in_state)} ({int(fractions['state']*100)}%)",
        'total': f"{format_dollar(total)}",
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

    if subtxt:
        y_off += text_h *1.5
        els.append(Text(subtxt, x=x_off, y=y_off))

    ## Create SVG
    width = txt_end + max([10*len(perc_txts[x]) + widths[x] for x in ('city', 'state', 'total')])
    height = y_off+5
    return Element('svg', els, width=width, height=height).to_html()


def plotRecord(m, record, addr_map):
    addr = address_from_record(record)
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
    radius = size_scale(contributor.total, **SCALE_ARGS)
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
    radius = size_scale(total, **SCALE_ARGS)
    color = GRADIENT.pick(total)
    folium.CircleMarker(
        coord,
        radius=radius,
        stroke=True,
        weight=1,
        color=color,
        fill_color=color,
        fill_opacity=0.6,
        tooltip=tooltip,
    ).add_to(m)


def processTemplate(m, template, *, contributors=None, title=None, subtitle=None, mobile=False):
    ## Make the map key
    map_key = None
    if not mobile:
        map_key = makeMapKey("Contribution Scale")
    else:
        ## Incldue the map titles
        subtitles = []
        if subtitle:
            subtitles.append(subtitle)
        subtitles.extend(["", "Contribution Scale"])
        map_key = makeMapKey(title, subtitles=subtitles, horizontal=True)

    ## Make the contribution box
    contr_box = None
    if contributors is not None:
        if not mobile:
            contr_box = makeContributionBox("Contribution Total", *filers.sum_contributions(contributors=contributors))
        else:
            contr_box = makeContributionBox(
                "Contribution Total",
                subtxt=DISCLAIMER,
                cbox_w=100,
                *filers.sum_contributions(contributors=contributors),
            )

        template = template.replace("{{CONTRIBUTIONS}}", contr_box)

    ## Do replacements
    template = template.replace("{{SVG1}}", map_key)
    if not mobile:
        template = template.replace("{{DISCLAIMER}}", DISCLAIMER)
        if title:
            template = template.replace("{{TITLE}}", f"<h2>{title}</h2><p>{subtitle or ''}</p>")
    macro = MacroElement()
    macro._template = Template(template) ## pylint: disable=protected-access
    m.get_root().add_child(macro)


def plotContributions(contributors, m):
    grouped = defaultdict(list)
    for c in contributors:
        grouped[c.address].append(c)

    for group in sorted(grouped.values(), reverse=True):
        if not group[0].coord:
            print(f"Skipping group")
            continue

        plotColocatedContributors(group, group[0].coord, group[0].address, m)


def makeMap(contributors, m, title=None, subtitle=None, mobile=False):
    plotContributions(contributors, m)

    ## Load template
    template = None
    with open("templates/map_contributions.html") as f:
        template = f.read()

    if template is not None:
        processTemplate(m, template, contributors=contributors, title=title, subtitle=subtitle, mobile=mobile)


def getFiler(cpfid):
    try:
        return Filer.fromFile(f"candidate_data/filers/{cpfid}.json")
    except Exception as e:
        print(f"Couldn't load filer {cpfid}: {e}")
        return None


def makeTitles(summary, args):
    title = args.title
    subtitle = args.subtitle
    cpfid = args.filer
    if cpfid is None and 'filerCpfId' in summary:
        cpfid = summary['filerCpfId']
    if cpfid:
        filer = getFiler(cpfid)
        if filer:
            title = filer.candidate_name + " Contributions"
            print(f"Using title: {title}")
        else:
            print(f"No such filer {cpfid}")

    else:
        title = "Contributions"

    if subtitle is None and summary['start'] and summary['end']:
        subtitle = f"{summary['start']} to {summary['end']}"

    return (title, subtitle)


def makeLayer(name, geo_path, show=False, weight=2, tooltip=None, tooltip_name=None, sticky=False, control=True, geo_args=None, interactive=None, **kwargs):
    if interactive is None:
        interactive = bool(tooltip)
    else:
        interactive = False

    geo_args = geo_args or {}
    geojson = gis.GisGeoJson(geo_path, **geo_args)
    style_function = lambda x: {
        'fillColor': '#000000',
        'fillOpacity': 0.0,
        'weight': weight,
        'color': '#000000',
        'opacity': 1,
    }

    geo = folium.GeoJson(
        geojson.geojson,
        name=name,
        show=show,
        interactive=interactive,
        control=control,
        style_function=style_function,
    )

    if tooltip is not None:
        tooltip_name = tooltip_name or tooltip
        folium.GeoJsonTooltip(fields=[tooltip], aliases=[tooltip], sticky=sticky).add_to(geo)

    return geo


def single_filer_hdlr(args):
    ## Get info
    addr_map = AddressMap(api_key=utils.load_file(args.google_api_key), cache_path=args.address_cache)
    data = utils.load_json(args.records_file)
    summary = data['summary']
    records = data['items']
    title, subtitle = makeTitles(summary, args)

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14, tiles="Cartodb Positron")

    ## Keep anything that could fail during or after the coordindates are loaded in this try block
    try:
        contributors = filers.records_to_contributors(records, addr_map=addr_map)

        ## Make bounds and plot map
        makeMap(contributors, m, title=title, subtitle=subtitle, mobile=args.mobile)
        makeLayer(**CITY_BOUNDARY).add_to(m)
        #makeLayer(**STATE_BOUNDARY).add_to(m)

        if contributors:
            all_coords = [tuple(c.coord) for c in contributors]
            sw = min(all_coords)
            ne = max(all_coords)
            m.fit_bounds([sw, ne])

        m.save(args.out_file)
        print(f"Wrote to {args.out_file}")
    finally:
        addr_map.save()


def addRecords(m, addr_map, name, contributors, *, bounds=None):

    ## Get bounds
    if bounds is not None:
        all_coords = [tuple(c.coord) for c in contributors]
        sw = min(all_coords)
        ne = max(all_coords)
        bounds.append([sw, ne])


def many_filers_hdlr(args):
    ## Get info
    addr_map = AddressMap(api_key=utils.load_file(args.google_api_key), cache_path=args.address_cache)
    args.title = args.title or "Contributions"
    candidates = {}
    for records_path in args.records_files:
        try:
            data = utils.load_json(records_path)
            candidates[data['summary']['filerFullName']] = filers.records_to_contributors(data['items'], addr_map=addr_map)
        except Exception as e:
            print(f"Failed to add records from file '{records_path}': {e}")
    addr_map.save()

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14, tiles=None)
    base_map = folium.FeatureGroup(name='Basemap', overlay=True, control=False)
    folium.TileLayer(tiles="Cartodb Positron").add_to(base_map)
    base_map.add_to(m)
    bounds = []

    ## Plot contributions
    show = True
    for name, contributors in sorted(candidates.items()):
        addRecords(m, addr_map, name, contributors, bounds=bounds)
        group = folium.map.FeatureGroup(name, overlay=False, show=show)
        group.add_to(m)
        plotContributions(contributors, group)
        makeLayer(**CITY_BOUNDARY).add_to(group)
        bounds.extend([tuple(c.coord) for c in contributors])
        show = False

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    template = None
    with open("templates/map_contributions.html") as f:
        template = f.read()

    if template is not None:
        processTemplate(m, template, title=args.title, subtitle=args.subtitle, mobile=args.mobile)

    ## Finalize map
    if bounds:
        m.fit_bounds(bounds)
    m.save(args.out_file)
    print(f"Wrote to {args.out_file}")


def main(args):
    if args.google_api_key is None and args.address_cache is None:
        print("At least one of --address-cache and --google-api-key must be specififed")
        return 1

    return args.subcmd(args)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
