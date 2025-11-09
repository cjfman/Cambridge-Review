#!/usr/bin/env python3

## pylint: disable=too-many-locals

import argparse
import math
import os
import sys

from collections import defaultdict
from pathlib import Path

import folium

from branca.element import Template, MacroElement

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib import elections
from citylib.utils import color_schemes as cs
from citylib.utils import gis
from citylib.utils.simplehtml import Element, LinearGradient, Text, TickMark
from citylib.utils.gis import CITY_BOUNDARY, WARD_BOUNDARIES, NEIGHBORHOOD_BOUNDARIES

#ROOT      = "/home/charles/Projects/cambridge_review/"
ROOT      = "./"
GEOJSON   = os.path.join(ROOT, "geojson")
OVERWRITE = True
VERBOSE   = False
DEBUG     = False

def parseArgs():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser()
    parser.set_defaults(all=False)
    parser.set_defaults(winners=False)
    parser.set_defaults(candidate=False)
    parser.set_defaults(candidate_diff=False)
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
#    parser.add_argument("--ward-geojson", default=os.path.join(GEOJSON, "WardsPrecincts2020.geojson"),
#        help="Ward geojson")
    parser.add_argument("--census-year", required=True,
        help="Census year. Used to look up geojson")
    parser.add_argument("--title", default="Precinct Election Map",
        help="Map title")

    subparsers = parser.add_subparsers()
    parser_all = subparsers.add_parser('all',
        help="Plot all candidates")
    parser_all.set_defaults(all=True)
    parser_all.add_argument("vote_file",
        help="CSV of vote counts")
    parser_all.add_argument("out_file",
        help="Output file")

    parser_winners = subparsers.add_parser('winners',
        help="Plot winners for each ward")
    parser_winners.set_defaults(winners=True)
    parser_winners.add_argument("vote_file",
        help="CSV of vote counts")
    parser_winners.add_argument("out_file",
        help="Output file")

    parser_candidate = subparsers.add_parser('candidate',
        help="Only plot this candidate")
    parser_candidate.set_defaults(candidate=True)
    parser_candidate.add_argument("name",
        help="The name of the candidate")
    parser_candidate.add_argument("vote_file",
        help="CSV of vote counts")
    parser_candidate.add_argument("out_file",
        help="Output file")

    parser_candidate_diff = subparsers.add_parser('candidate-diff',
        help="Plot the difference between two elections for a given candidate")
    parser_candidate_diff.set_defaults(candidate_diff=True)
    parser_candidate_diff.add_argument("name",
        help="The name of the candidate")
    parser_candidate_diff.add_argument("vote_file_1",
        help="CSV of vote counts 1")
    parser_candidate_diff.add_argument("vote_file_2",
        help="CSV of vote counts 2")
    parser_candidate_diff.add_argument("out_file",
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


def loadElection(vote_file):
    print(f"Reading '{vote_file}'")
    election = elections.loadWardElectionFile(vote_file)
    election.printStats()
    return election


def main(args):
    global VERBOSE ## pylint: disable=global-statement
    global DEBUG   ## pylint: disable=global-statement
    if args.debug:
        VERBOSE = True
        DEBUG = True
    elif args.verbose:
        VERBOSE = True

    template = None
    with open(os.path.join(ROOT, "templates/map.html")) as f:
        template = f.read()

    geo_path = WARD_BOUNDARIES['geo_path']
    if args.all:
        election = loadElection(args.vote_file)
        plotAllCandidatesGeoJson(args.title, geo_path, args.out_file, election, template=template)
    elif args.winners:
        election = loadElection(args.vote_file)
        plotWinnerGeoJson(
            args.title, geo_path, args.out_file, election.p_winners,
            max_count=election.max_count, totals=election.p_totals, template=template,
        )
    elif args.candidate:
        election = loadElection(args.vote_file)
        plotGeoJson(
            args.title, geo_path, args.out_file, election.p_votes, args.name,
            max_count=election.max_count, totals=election.p_totals, template=template
        )
    elif args.candidate_diff:
        election_1 = loadElection(args.vote_file_1)
        election_2 = loadElection(args.vote_file_2)
        plotCandidateDiffGeoJson(args.title, geo_path, args.out_file, args.name, election_1, election_2, template=template)
    else:
        print("Error: No valid subcommand chosen")
        return 1

    return 0


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
    show = True
    for layer_name, style in styles:
        layer = folium.FeatureGroup(name=layer_name, overlay=False, show=show)
        show = False
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
                if precinct != "Total":
                    print(f"Couldn't find geoid for precinct {precinct}")
                continue

            all_precincts.add(precinct)
            precinct_totals[geoid] += count
            values[candidate][geoid] = count
            count_txt = "%d (%.2f%%)" % (count, 100 * count / election.p_totals[precinct])
            if election.p_winners[precinct][0] == candidate:
                count_txt += "*"
            if VERBOSE:
                print(f"Setting geojson id {geoid} property '{candidate}' to {count_txt}")
            geojson.setProperty(candidate, count_txt, geoid)

    for geoid, total in precinct_totals.items():
        if VERBOSE:
            print(f"Setting geojson id {geoid} property 'Total' to {total}")
        geojson.setProperty("Total", total, geoid)

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

    ## Add candidates
    show = True
    for candidate, precincts in sorted(values.items()):
        print(f"Plot {candidate}")
        layer = folium.FeatureGroup(name=candidate, overlay=False, show=show)
        show = False
        geo = makeCandidateLayer(geojson, candidate, precincts, gradient, show=True)
        geo.add_to(layer)
        layer.add_to(m)

    ## Add total layer
    print(f"Plot Totals")
    layer = folium.FeatureGroup(name="Totals", overlay=False, show=False)
    geo = makeTotalLayer(geojson, sorted(election.c_votes.keys()), precinct_totals, gradient, show=True)
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


def plotCandidateDiffGeoJson(name, geo_path, out_path, candidate, election_1, election_2, template=None):
    print(f"Generating {name}")
    print(f"Reading {geo_path}")
    geojson = gis.GisGeoJson(geo_path, secondary_id_key='WardPrecinct')
    geojson.setProperty('count_d', "N/A")
    values = {}
    percents = {}
    for precinct in set(list(election_1.p_votes.keys()) + list(election_2.p_votes.keys())):
        if precinct not in election_1.p_votes or precinct not in election_2.p_votes:
            print(f"Precinct {precinct} didn't exist in both elections. Skipping it")
            continue

        geoid = geojson.getGeoId(precinct)
        if geoid is None:
            print(f"Skipping {precinct}")
            continue

        count_1 = election_1.p_votes[precinct][candidate]
        total_1 = election_1.p_totals[precinct]
        count_2 = election_2.p_votes[precinct][candidate]
        total_2 = election_2.p_totals[precinct]
        count_d = count_2 - count_1
        count_p = count_2/total_2 - count_1/total_1
        count_txt_1 = "%d (%.2f%%)" % (count_1, 100 * count_1 / total_1)
        count_txt_2 = "%d (%.2f%%)" % (count_2, 100 * count_2 / total_2)
        count_txt_d = str(count_d)
        if count_1:
            count_txt_d = "%+d (%+.2f%%)" % (count_d, 100 * count_d / count_1)
        count_txt_p = "%+.2f%%" % (count_p*100)
        geojson.setProperty('count_d', count_txt_d, geoid)
        geojson.setProperty('count_1', count_txt_1, geoid)
        geojson.setProperty('count_2', count_txt_2, geoid)
        geojson.setProperty('count_p', count_txt_p, geoid)
        values[geoid] = count_d
        percents[geoid] = count_p*100

    max_count   = max(map(abs, values.values()))
    max_percent = int(max(map(abs, percents.values())))
    gradient = cs.ColorGradient(cs.BlueYellow, max_count, -max_count)
    gradient_p = cs.ColorGradient(cs.BlueYellow, max_percent, -max_percent)

    ## Make style function
    style_function_count = lambda x: {
        'fillColor': gradient.pick(float(noThrow(values, x['id']) or 0) or 0),
        'fillOpacity': 0.7,
        'weight': 2,
        'color': '#000000',
        'opacity': 0.2,
    }
    style_function_percent = lambda x: {
        'fillColor': gradient_p.pick(float(noThrow(percents, x['id']) or 0) or 0),
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

    ## Plot extra layers
    makeLayer(**WARD_BOUNDARIES).add_to(m)
    makeLayer(**NEIGHBORHOOD_BOUNDARIES).add_to(m)

    ## Plot labels
    makeLabelLayer(geojson, election_1.p_winners).add_to(m)

    ## Plot vote counts
    fields  = ['WardPrecinct', 'count_1',  'count_2', 'count_d',    'count_p']
    aliases = ['Ward',         'Previous', 'Current', 'Count Diff', 'Points Diff']
    layer = folium.FeatureGroup(name="Count", overlay=False, show=True)
    geo = folium.GeoJson(geojson.geojson, name=name, style_function=style_function_count)
    folium.GeoJsonTooltip(
        fields=fields,
        aliases=aliases,
        sticky=False,
    ).add_to(geo)
    geo.add_to(layer)
    layer.add_to(m)

    ## Plot vote percents
    layer = folium.FeatureGroup(name="Percents", overlay=False, show=False)
    geo = folium.GeoJson(geojson.geojson, name=name, style_function=style_function_percent)
    folium.GeoJsonTooltip(
        fields=fields,
        aliases=aliases,
        sticky=False,
    ).add_to(geo)
    geo.add_to(layer)
    layer.add_to(m)

    folium.LayerControl(position='topleft', collapsed=False).add_to(m)

    ## Load template
    if template is not None:
        ## Counts
        key_values = list(range(gradient.min, gradient.max + 1, gradient.range//8))
        color_key = makeColorKey(name, gradient, values=key_values, subtitle="Vote Counts")
        template = template.replace("{{SVG1}}", color_key)

        ## Percentage
        key_values = list(range(gradient_p.min, gradient_p.max + 1, gradient_p.range//8 or 1))
        color_key = makeColorKey("Percentage Points", gradient_p, values=key_values, subtitle=None)
        template = template.replace("{{SVG2}}", color_key)

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
    num_colors = len(cs.COLOR_BLIND_FRIENDLY_HEX)
    style_function = lambda x: {
        'fillColor': cs.COLOR_BLIND_FRIENDLY_HEX[x['id'] % num_colors],
        'fillOpacity': 0.7,
        'weight': 4,
        'color': '#000000',
        'opacity': 0.2,
    }

    fields = ['WardPrecinct', 'Total']
    fields.extend(candidates)
    aliases = ['Ward', 'Total']
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


def makeColorKey(title, gradient, cbox_h=20, cbox_w=400, tick_h=10, values=None, subtitle="Vote"):
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

    if subtitle is not None:
        els.append(Text(subtitle, x=x_off, y=y_off))
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
