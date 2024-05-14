#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import math
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
    'control': False,
}

WARD_BOUNDARIES = {
    'name': "Wards",
    'geo_path': os.path.join(GEOJSON, "WardsPrecincts2020.geojson"),
    'weight': 1,
    'tooltip': "WardPrecinct",
    'show': True,
    'sticky': False,
    'control': False,
}

NEIGHBORHOOD_BOUNDARIES = {
    'name': "Neighborhoods",
    'geo_path': os.path.join(GEOJSON, "BOUNDARY_CDDNeighborhoods.geojson"),
    'weight': 5,
    'tooltip': "NAME",
}


def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
#    parser.add_argument("--ward-geojson", default=os.path.join(GEOJSON, "WardsPrecincts2020.geojson"),
#        help="Ward geojson")
    parser.add_argument("--census-year", required=True,
        help="Census year. Used to look up geojson")
    parser.add_argument("--title", default="Precinct Election Map",
        help="Map title")
    who_group = parser.add_mutually_exclusive_group(required=True)
    who_group.add_argument("--all", action="store_true",
        help="Plot all candidates")
    who_group.add_argument("--candidate",
        help="Only plot this candidate")
    who_group.add_argument("--winners", action="store_true",
        help="Plot winners for each ward")
    parser.add_argument("vote_file",
        help="CSV of vote counts")
    parser.add_argument("out_file",
        help="Output file")

    args = parser.parse_args()

    ## Update geojson path
    WARD_BOUNDARIES['geo_path'] = os.path.join(GEOJSON, f"WardsPrecincts{args.census_year}.geojson")

    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True

    return args


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

    geo_path = WARD_BOUNDARIES['geo_path']
    if args.all:
        plotAllCandidatesGeoJson(args.title, geo_path, args.out_file, election, template=template)
    elif args.winners:
        plotWinnerGeoJson(args.title, geo_path, args.out_file, election.p_winners, max_count=election.max_count, totals=election.p_totals, template=template)
    else:
        plotGeoJson(args.title, geo_path, args.out_file, election.p_votes, args.candidate, max_count=election.max_count, totals=election.p_totals, template=template)


def plotGeoJson(name, geo_path, out_path, precincts, metric, *, max_count, totals, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    gradient = cs.ColorGradient(cs.BlueRedYellow, max_count)

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
    ## Plot labels
    makeLabelLayer(geojson, precincts).add_to(m)

    ## Plot wards
    geo = folium.GeoJson(geojson.geojson, name=name, style_function=style_function)
    folium.GeoJsonTooltip(fields=['WardPrecinct', metric], aliases=['Ward', metric], sticky=False).add_to(geo)
    geo.add_to(m)

    ## Plot extra layers
    makeLayer(**WARD_BOUNDARIES).add_to(m)
    makeLayer(**NEIGHBORHOOD_BOUNDARIES).add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        key_values = list(range(0, gradient.max + 1, gradient.max//4))
        color_key = makeColorKey(name, gradient, values=key_values)
        template = template.replace("{{SVG1}}", color_key)
        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    m.save(out_path)
    print(f"Wrote to {out_path}")


def plotWinnerGeoJson(name, geo_path, out_path, precincts, *, max_count, totals, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    gradient = cs.ColorGradient(cs.BlueRedYellow, max_count)

    winners = set()
    values = {}
    geojson.setProperty('winner', "N/A")
    for precinct, results in precincts.items():
        geoid = geojson.getGeoId(precinct)
        if geoid is None:
            print(f"Skipping {precinct}")
            continue

        winner, count = results
        winners.add(winner)
        values[geoid] = count
        count = "%d (%.2f%%)" % (count, 100 * count / totals[precinct])
        geojson.setProperty('winner', winner, geoid)
        geojson.setProperty('vote_count', count, geoid)
        if DEBUG:
            print(precinct, geoid, winner, count)

    ## Make style function
    num_colors = len(cs.COLOR_BLIND_FRIENDLY_HEX)
    candidate_colors = {
        name: cs.COLOR_BLIND_FRIENDLY_HEX[i % num_colors] for i, name in enumerate(sorted(winners))
    }
    style_gradient = lambda x: {
        'fillColor': gradient.pick(float(noThrow(values, x['id']) or 0) or None),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }
    style_solid = lambda x: {
        'fillColor': noThrow(candidate_colors, x['properties']['winner']),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14, tiles=None)
    base_map = folium.FeatureGroup(name='Basemap', overlay=True, control=False)
    folium.TileLayer(tiles='OpenStreetMap').add_to(base_map)
    base_map.add_to(m)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(base_map)

    ## Plot labels
    makeLabelLayer(geojson, precincts).add_to(m)

    ## Plot wards
    styles = (
        ('Winners', style_solid),
        ("Vote Count", style_gradient),
    )
    for layer_name, style in styles:
        layer = folium.FeatureGroup(name=layer_name, overlay=False)
        geo = folium.GeoJson(geojson.geojson, name=layer_name, style_function=style)
        folium.GeoJsonTooltip(fields=['WardPrecinct', 'winner', 'vote_count'], aliases=['Ward', 'Winner', 'Votes'], sticky=False).add_to(geo)
        geo.add_to(layer)
        layer.add_to(m)

    ## Plot extra layers
    makeLayer(**NEIGHBORHOOD_BOUNDARIES).add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        key_values = list(range(0, gradient.max + 1, gradient.max//4))
        color_key = makeColorKey(name, gradient, values=key_values)
        candidate_key = makeCandidateKey("Ward Winners", candidate_colors)
        template = template.replace("{{SVG1}}", color_key)
        template = template.replace("{{SVG2}}", candidate_key)


        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    m.save(out_path)
    print(f"Wrote to {out_path}")


def plotAllCandidatesGeoJson(name, geo_path, out_path, election, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    gradient = cs.ColorGradient(cs.BlueRedYellow, election.max_count, scale_fn=lambda x: math.log(1 + x/50))

    all_precincts = set()
    precinct_totals = defaultdict(int)

    ## Set property values for each candidate
    values = defaultdict(dict)
    for candidate, results in election.c_votes.items():
        geojson.setProperty(candidate, "N/A")
        for precinct, count in results.items():
            geoid = geojson.getGeoId(precinct)
            if geoid is None:
                continue

            all_precincts.add(precinct)
            precinct_totals[geoid] += count
            values[candidate][geoid] = count
            count_txt = "%d (%.2f%%)" % (count, 100 * count / election.p_totals[precinct])
            if election.p_winners[precinct][0] == candidate:
                count_txt += "*"
            geojson.setProperty(candidate, count_txt, geoid)

    ## Make map
    m = folium.Map(location=[42.378, -71.11], zoom_start=14, tiles=None)
    base_map = folium.FeatureGroup(name='Basemap', overlay=True, control=False)
    folium.TileLayer(tiles='OpenStreetMap').add_to(base_map)
    base_map.add_to(m)
    city_boundary = makeLayer(**CITY_BOUNDARY)
    city_boundary.add_to(base_map)
    makeLayer(**WARD_BOUNDARIES).add_to(m)

    ## Plot labels
    makeLabelLayer(geojson, all_precincts).add_to(m)

    ## Add total layer
    print(f"Plot Totals")
    layer = folium.FeatureGroup(name="Totals", overlay=False)
    geo = makeTotalLayer(geojson, sorted(election.c_votes.keys()), precinct_totals, gradient, show=False)
    geo.add_to(layer)
    layer.add_to(m)

    ## Add candidates
    for candidate, precincts in sorted(values.items()):
        print(f"Plot {candidate}")
        layer = folium.FeatureGroup(name=candidate, overlay=False)
        geo = makeCandidateLayer(geojson, candidate, precincts, gradient)
        geo.add_to(layer)
        layer.add_to(m)

    ## Plot extra layers
    makeLayer(**NEIGHBORHOOD_BOUNDARIES).add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        half = gradient.max//2
        key_values = list(range(0, half, gradient.max//10))
        key_values += list(range(half, gradient.max - 1, gradient.max//5))[1:]
        key_values[-1] = gradient.max
        color_key = makeColorKey(name, gradient, values=key_values)
        template = template.replace("{{SVG1}}", color_key)
        macro = MacroElement()
        macro._template = Template(template) ## pylint: disable=protected-access
        m.get_root().add_child(macro)

    m.save(out_path)
    print(f"Wrote to {out_path}")


def noThrow(values, key):
    if key not in values:
        if DEBUG:
            print(f"Failed to find key: {key}")

        return None

    return values[key]


def htmlElemGen(tag, data='', **kwargs):
    attrs = " ".join([f'{k.replace("_", "-")}="{v}"' for k, v in kwargs.items()])
    return f'<{tag} {attrs}>{data}</{tag}>'


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


def makeLabelLayer(geojson, precincts):
    layer = folium.FeatureGroup(name='Labels', overlay=True, control=True)
    for precinct in precincts:
        centroid = geojson.getCentroid(geojson.getGeoId(precinct))
        label = makeLabel(precinct, centroid)
        label.add_to(layer)

    return layer


def makeTotalLayer(geojson, candidates, precincts, gradient, *, show=False):
    ## Make style function
    style_function = lambda x: {
        'fillColor': gradient.pick(float(noThrow(precincts, x['id']) or 0) or None),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }

    fields = ['WardPrecinct']
    fields.extend(candidates)
    aliases = ['Ward']
    aliases.extend(candidates)
    geo = folium.GeoJson(geojson.geojson, name="Totals", style_function=style_function, show=show)
    folium.GeoJsonTooltip(fields=fields, aliases=aliases, sticky=False).add_to(geo)
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


def makeCandidateKey(title, candidates, box_size=8):
    ## Add elements
    y_off = 20
    x_off = 10
    text_h = 15
    els = []

    ## Title
    els.append(Text(title, x=x_off, y=y_off))
    y_off += text_h / 2

    ## Add candidates
    for name, color in sorted(candidates.items()):
        els.append(Element(
            'rect', x=x_off, y=y_off, width=box_size, height=box_size,
            stroke='black', stroke_width=1,
            fill=color,
        ))
        els.append(Text(name, x=x_off+box_size*2, y=y_off+box_size))
        y_off += box_size*2

    y_off -= box_size

    ## Create SVG
    width = min(15 * max([len(x) for x in candidates]), 150)
    height = y_off
    return Element('svg', els, width=width, height=height).to_html()


def makeLabel(text, coord, size='16pt', weight='bold'):
    return folium.map.Marker(
        coord,
        icon=folium.features.DivIcon(
            icon_size=(50/4*len(text), 0),
            icon_anchor=(5, 5),
            html=f'<div style="font-size: {size}; font-weight: {weight}">{text}</div>',
            )
        )


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
