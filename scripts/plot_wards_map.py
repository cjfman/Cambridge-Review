#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import os
import sys

from collections import defaultdict

import folium

from branca.element import Template, MacroElement

import color_schemes as cs
import gis
from simplehtml import Element, LinearGradient, Text, TickMark

import elections

ROOT      = "/home/charles/Projects/cambridge_review/"
GEOJSON   = os.path.join(ROOT, "geojson")
OVERWRITE = True
VERBOSE   = False
DEBUG     = False

CITY_BOUNDARY = {
    'name': "City Boundary",
    'geo_path': os.path.join(GEOJSON, "BOUNDARY_CityBoundary.geojson"),
    'show': True,
    'weight': 5,
}

ADDITIONAL_LAYERS = [
    {
        'name': "Wards",
        'geo_path': os.path.join(GEOJSON, "WardsPrecincts2020.geojson"),
        'weight': 5,
        'tooltip': "WardPrecinct",
        'show': True,
    },
    {
        'name': "Neighborhoods",
        'geo_path': os.path.join(GEOJSON, "BOUNDARY_CDDNeighborhoods.geojson"),
        'weight': 5,
        'tooltip': "NAME",
    },
]


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--geojson", default=os.path.join(GEOJSON, "WardsPrecincts2020.geojson"),
        help="Ward geojson")
    parser.add_argument("--title", default="Precinct Election Map",
        help="Map title")
    parser.add_argument("--all", action="store_true",
        help="Plot all candidates")
    parser.add_argument("vote_file",
        help="CSV of vote counts")
    parser.add_argument("out_file",
        help="Output file")

    return parser.parse_args()


def cleanTitle(title):
    for x in [' ', '/']:
        title = title.replace(x, '_')

    return title

def main(args):
    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True


    print(f"Reading '{args.vote_file}'")
    election = elections.loadWardElectionFile(args.vote_file)
    election.printStats()
    template = None
    with open(os.path.join(ROOT, "templates/map.html")) as f:
        template = f.read()

    if args.all:
        plotAllCandidatesGeoJson(args.title, args.geojson, args.out_file, election.c_votes, max_count=election.max_count, template=template)
    else:
        plotGeoJson(args.title, args.geojson, args.out_file, election.p_votes, 'Siddiqui', max_count=election.max_count, template=template)


def plotGeoJson(name, geo_path, out_path, precincts, metric, *, max_count, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    gradient = cs.ColorGradient(cs.BlueRedYellow, max_count)
    #gradient = cs.ColorGradient(cs.BlueRedYellow, int(values.max()), scale_fn=lambda x: math.log(1 + x))

    values = {}
    geojson.setProperty(metric, "N/A")
    for precinct, results in precincts.items():
        geoid = geojson.getGeoId(precinct)
        if geoid is None:
            print(f"Skipping {precinct}")
            continue

        values[geoid] = results[metric]
        geojson.setProperty(metric, results[metric], geoid)

    ## Make style function
    style_function = lambda x: {
        'fillColor': gradient.pick(float(noThrow(values, x['id']) or 0) or None),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)
    geo = folium.GeoJson(geojson.geojson, name=name, style_function=style_function)
    folium.GeoJsonTooltip(fields=[metric], aliases=[metric], sticky=False).add_to(geo)
    geo.add_to(m)

    ## Plot extra layers
    for layer_def in ADDITIONAL_LAYERS:
        layer = makeLayer(**layer_def)
        layer.add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        #key_values = list(np.arange(gradient.min, 3, 0.5))
        #key_values += list(np.arange(3, gradient.max, 1))
        #key_values = [int(x) for x in key_values] + [gradient.max]
        key_values = list(range(0, gradient.max + 1, gradient.max//4))
        color_key = makeColorKey(name, gradient, values=key_values)
        #color_key = makeColorKey(name, gradient)
        template = template.replace("{{SVG}}", color_key)
        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    m.save(out_path)
    print(f"Wrote to {out_path}")


def plotAllCandidatesGeoJson(name, geo_path, out_path, candidates, *, max_count, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    gradient = cs.ColorGradient(cs.BlueRedYellow, max_count)

    values = defaultdict(dict)
    for candidate, results in candidates.items():
        geojson.setProperty(candidate, "N/A")
        for precinct, count in results.items():
            geoid = geojson.getGeoId(precinct)
            if geoid is None:
                continue
            geojson.setProperty(candidate, count, geoid)
            values[candidate][geoid] = count

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(m)
    for candidate, precincts in values.items():
        print(f"Plot {candidate}")
        geo = makeCandidateLayer(geojson, candidate, precincts, gradient)
        geo.add_to(m)

    ## Plot extra layers
    for layer_def in ADDITIONAL_LAYERS:
        layer = makeLayer(**layer_def)
        layer.add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        key_values = list(range(0, gradient.max + 1, gradient.max//4))
        color_key = makeColorKey(name, gradient, values=key_values)
        #color_key = makeColorKey(name, gradient)
        template = template.replace("{{SVG}}", color_key)
        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    m.save(out_path)
    print(f"Wrote to {out_path}")


def noThrow(values, key):
    if key not in values:
        return None

    return values[key]


def htmlElemGen(tag, data='', **kwargs):
    attrs = " ".join([f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()])
    return f'<{tag} {attrs}>{data}</{tag}>'


def makeLayer(name, geo_path, show=False, weight=2, tooltip=None, tooltip_name=None, **kwargs):
    geojson = gis.GisGeoJson(geo_path)
    style_function = lambda x: {
        'fillColor': '#000000',
        'fillOpacity': 0.0,
        'weight': weight,
        'color': '#000000',
        'opacity': 1,
    }

    geo = folium.GeoJson(geojson.geojson, name=name, show=show, control=True, style_function=style_function)
    if tooltip is not None:
        tooltip_name = tooltip_name or tooltip
        folium.GeoJsonTooltip(fields=[tooltip], aliases=[tooltip], sticky=False).add_to(geo)

    return geo


def makeCandidateLayer(geojson, name, precincts, gradient, *, show=False):
    ## Make style function
    style_function = lambda x: {
        'fillColor': gradient.pick(float(noThrow(precincts, x['id']) or 0) or None),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }

    geo = folium.GeoJson(geojson.geojson, name=name, style_function=style_function, show=show)
    folium.GeoJsonTooltip(fields=['WardPrecinct', name], aliases=['Ward', name], sticky=False).add_to(geo)
    return geo


def makeColorKey(title, gradient, cbox_h=20, cbox_w=400, tick_h=10, values=None):
    values = values or []
    ## Add data
    color_tag = "color-scheme-red"
    gradient_el = LinearGradient(gradient, color_tag)

    ## Add elements
    y_off = 20
    x_off = 10
    text_h = 15
    els = []

    ## Title
    els.append(Text(title, x=x_off, y=y_off))
    y_off += text_h

    els.append(Text('Votes', x=x_off, y=y_off))
    y_off += text_h/2

    ## Create Color box
    els.append(Element('defs', gradient_el))
    els.append(Element(
        'rect', x=x_off, y=y_off, width=cbox_w, height=cbox_h,
        stroke='black', stroke_width=2,
        fill=f"url(#{color_tag})",
    ))
    y_off += cbox_h

    ## Create Ticks
    ticks = []
    for i, value in enumerate(values):
        x = x_off + int(cbox_w*gradient.percent(value)/100)
        text_y = y_off + int(tick_h*1.1) + text_h
        ticks.append(TickMark(x=x, y=y_off, height=tick_h, width=2))
        if i == len(values) - 1:
            x -= len(str(value)) * 4
        elif i > 0:
            x -= len(str(value)) * 3
        if value < gradient.max:
            ticks.append(Text(str(value), x=x, y=text_y))
        else:
            ticks.append(Text(str(value), x=x-10, y=text_y))
            break

    y_off += int(tick_h*1.1) + text_h
    els.append(Element('g', ticks))

    ## Create SVG
    width = cbox_w + 20
    height = y_off
    return Element('svg', els, width=width, height=height).to_html()


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
