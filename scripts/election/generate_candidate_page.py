#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path
from textwrap import dedent

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')
from citylib.filers import Filer

VERBOSE=False
DEBUG=False

def parseArgs():
    ## pylint: disable=global-statement
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("path")

    ## Final parse
    args = parser.parse_args()
    if args.verbose:
        global VERBOSE
        VERBOSE = args.verbose
    if args.debug:
        global DEBUG
        DEBUG = args.debug

    return args

CANDIDATE_PAGE_TEMPLATE = dedent("""\
    <!-- wp:heading -->
    <h2 class="wp-block-heading">Quick Facts</h2>
    <!-- /wp:heading -->

    <!-- wp:list -->
    <ul class="wp-block-list"><!-- wp:list-item -->
    <li>Current Position: {position}</li>
    <!-- /wp:list-item -->

    <!-- wp:list-item -->
    <li>Candidate Status: {status}</li>
    <!-- /wp:list-item -->

    <!-- wp:list-item -->
    <li>Website: <a href="{website}" target="_blank" rel="noreferrer noopener">{website}</a></li>
    <!-- /wp:list-item -->

    <!-- wp:list-item -->
    <li>Committee Registration: <a href="https://www.ocpf.us/Filers?q={cpfid}" data-type="link" data-id="https://www.ocpf.us/Filers?q={cpfid}" target="_blank" rel="noreferrer noopener">OCPF ID {cpfid}</a></li>
    <!-- /wp:list-item --></ul>
    <!-- /wp:list -->

    <!-- wp:paragraph -->
    <p></p>
    <!-- /wp:paragraph -->

    <!-- wp:heading -->
    <h2 class="wp-block-heading">{overview_hdr}</h2>
    <!-- /wp:heading -->

    <!-- wp:paragraph -->
    <p>{overview}</p>
    <!-- /wp:paragraph -->

    <!-- wp:paragraph -->
    <p></p>
    <!-- /wp:paragraph -->

    <!-- wp:heading -->
    <h2 class="wp-block-heading">Previous Work and Positions</h2>
    <!-- /wp:heading -->

    <!-- wp:paragraph -->
    <p></p>
    <!-- /wp:paragraph -->

    <!-- wp:heading {{"style":{{"spacing":{{"margin":{{"bottom":"0.5em"}}}}}}}} -->
    <h2 class="wp-block-heading" style="margin-bottom:0.5em">Finances</h2>
    <!-- /wp:heading -->

    <!-- wp:columns -->
    <div class="wp-block-columns"><!-- wp:column {{"verticalAlignment":"top","width":"20%","layout":{{"type":"default"}}}} -->
    <div class="wp-block-column is-vertically-aligned-top" style="flex-basis:20%"><!-- wp:paragraph -->
    <p><em>Committee Name</em><br>{committee_name}</p>
    <!-- /wp:paragraph -->

    <!-- wp:paragraph -->
    <p><em>Treasurer</em><br>{treasurer}</p>
    <!-- /wp:paragraph -->

    <!-- wp:paragraph -->
    <p><em>Committee Address</em><br>{address_street}<br>{address_city_state_zip}</p>
    <!-- /wp:paragraph -->

    <!-- wp:paragraph -->
    <p><a href="https://www.ocpf.us/Filers?q={cpfid}" data-type="link" data-id="https://www.ocpf.us/Filers?q={cpfid}" target="_blank" rel="noreferrer noopener">further details</a></p>
    <!-- /wp:paragraph --></div>
    <!-- /wp:column -->

    <!-- wp:column {{"width":"80%","layout":{{"type":"constrained"}}}} -->
    <div class="wp-block-column" style="flex-basis:80%"><!-- wp:html -->
    <div class="gbvc-hide-on-mobile gbvc-hide-on-tablet">
    <iframe src="/candidate-data/report-charts/{cpfid}_report_chart.html" width="100%" height="600"></iframe>
    </div>
    <div class="gbvc-hide-on-desktop">
    <img src="/candidate-data/report-charts/{cpfid}_report_chart.png"></img>
    </div>
    <!-- /wp:html --></div>
    <!-- /wp:column --></div>
    <!-- /wp:columns -->
""")


def generate_candidate_page(filer:Filer, *, status="", website=""):
    return CANDIDATE_PAGE_TEMPLATE.format(
        cpfid=filer.cpfid,
        committee_name=filer.committee_name,
        treasurer=filer.treasurer,
        address_street=filer.comm_address_line_1,
        address_city_state_zip=f"{filer.comm_address_city}, {filer.comm_address_state} {filer.comm_address_zip}",
        position=filer.position,
        status=status,
        website=website,
        overview_hdr="Overview",
        overview="",
    )


def main(args):
    print(generate_candidate_page(Filer.fromFile(args.path)))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(parseArgs()))
    except KeyboardInterrupt:
        print("User requested exit")
        sys.exit(1)
