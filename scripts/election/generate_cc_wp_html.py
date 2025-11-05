#!/usr/bin/env python3

import argparse
import re
import sys

from pathlib import Path
from textwrap import dedent

from markdown_table_generator import generate_markdown, table_from_string_list, Alignment

## pylint: disable=wrong-import-position
sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')

from citylib import elections


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file",
        help="Output file")
    parser.add_argument("--title", default="Election",
        help="Title to give each election")
    parser.add_argument("--full", action="store_true",
        help="Generate full wordpress HTML")
    parser.add_argument("--table-only", action="store_true",
        help="Only generate the markdown table")
    parser.add_argument("--iframe-only", action="store_true",
        help="Only generate the interactive iframe page")
    parser.add_argument("--force", action="store_true")

    parser.add_argument("election_file",
        help="Election file to be parsed")

    return parser.parse_args()


def formatList(l):
    size = len(l)
    if size == 1:
        return l[0]
    if size == 2:
        return " and ".join(l)
        #return f"{l[0]} and {l[1]}"

    return ", ".join(l[:-1]) + f" and {l[-1]}"


def summarizeElection(elcn):
    ## pylint: disable=too-many-branches
    lines = []
    rounds = [dict() for i in range(elcn.num_rounds)]
    ## Organize rounds by round number
    for name, c_rounds in elcn.truncated2.items():
        for i, v_round in enumerate(c_rounds):
            if v_round.total and v_round.transfer < 0:
                rounds[i-1][name] = v_round
            else:
                rounds[i][name] = v_round

    all_elected = set()
    for i, candidates in enumerate(rounds):
        ## Skip first round
        ## Treat transfers from subsequent rounds as if they happened in the previous one
        n = i + 1
        elected = []
        eliminated = []
        excess = 0
        transfered = 0
        for name, v_round in candidates.items():
            if v_round.total and v_round.transfer < 0:
                elected.append(name)
                excess += abs(v_round.transfer)
            elif elcn.last_round[name] == n:
                if v_round.total and name not in all_elected:
                    elected.append(name)
                    excess += abs(v_round.transfer)
                elif not v_round.total:
                    eliminated.append(name)
                    transfered += abs(v_round.transfer)

        ## Make summary line
        line = f"Round {n}: "
        if elected:
            line += formatList(elected) + " elected. "
            if excess and n != elcn.num_rounds:
                line += f"Excesss {excess} votes transfered. "

        if eliminated:
            if n == elcn.num_rounds:
                line += "All others defeated."
            else:
                line += formatList(eliminated) + " eliminated"
                if transfered and n != elcn.num_rounds:
                    line += f" with {transfered} votes transfered."

        if not elected and not eliminated:
            line += "Distribute votes from previous round"

        lines.append(line)
        all_elected.union(elected)

    return lines


def makeTable(elcn):
    table = generate_markdown(table_from_string_list(elcn.generateTableRows(), Alignment.RIGHT))
    ## Switch first row to be left aligned
    lines = table.split("\n")
    formatter = lines[1]
    formatter = formatter.replace(':', '-', 1)
    formatter = formatter.replace('-', ':', 1)
    lines[1] = formatter
    return lines


def write(f, elcn, title, year):
    f.write(f"{title}\n\n")

    ## Basic info
    counted_on = ", ".join(elcn.counted_on)
    f.write("Basic info\n\n")
    f.write(dedent(f"""\
        Election Date: {elcn.date}
        Counted Dates: {counted_on}
        Total: {elcn.total}
        Quota: {elcn.quota}
    """))

    ## Image URL
    f.write("\n------\n\nSankey URL\n\n")
    f.write(f"wp-content/uploads/election_charts/city_council/line/cc_election_{year}_linechart.png\n")

    ## Candidates
    f.write("\n------\n\nCandidates\n\n")
    f.write("<ul>")
    for can in elcn.candidates:
        f.write(f"<li>{can}</li>\n")

    f.write("</ul>\n")

    ## Elected
    f.write("\n------\n\nElected\n\n")
    f.write("<ol>")
    for can in elcn.elected:
        f.write(f"<li>{can}</li>\n")

    f.write("</ol>\n")

    ## Summary
    f.write("\n------\n\nSummary\n\n")
    f.write("\n".join(summarizeElection(elcn)))

    ## Image URL
    f.write("\n------\n\nSankey URL\n\n")
    f.write(f"/wp-content/uploads/election_charts/city_council/sankey/cc_election_sankey_{year}.png\n")

    ## Table
    f.write("\n------\n\nVote Table\n\n")
    f.write("\n".join(makeTable(elcn)))
    f.write("\n")


def writeTable(f, elcn):
    f.write("\n".join(makeTable(elcn)))


def writeFull(f, elcn, year):
    ## Do not change any newliens that look extemporaneous
    counted_on = ", ".join(elcn.counted_on)
    ## Basic info, image, and start of "All Candidates" list
    f.write(dedent(f"""\
        <!-- wp:heading -->
        <h2 class="wp-block-heading">Basic Stats</h2>
        <!-- /wp:heading -->

        <!-- wp:paragraph -->
        <p>Election Date: {elcn.date}<br>Counted Dates: {counted_on}<br>Total: {elcn.total}<br>Quota: {elcn.quota}</p>
        <!-- /wp:paragraph -->

    """))
    f.write(dedent("""\
        <!-- wp:image {"align":"center","lightbox":{"enabled":true},"width":"722px","height":"auto","sizeSlug":"full","linkDestination":"none"} -->
    """))
    f.write(dedent(f"""\
        <figure class="wp-block-image aligncenter size-full is-resized"><img src="/wp-content/uploads/election_charts/city_council/line/cc_election_{year}_linechart.png" alt="" style="width:722px;height:auto"/></figure>
    """))
    f.write(dedent("""\
        <!-- /wp:image -->

        <!-- wp:group {"layout":{"type":"flex","flexWrap":"nowrap","verticalAlignment":"top"}} -->
        <div class="wp-block-group"><!-- wp:columns -->
        <div class="wp-block-columns"><!-- wp:column {"verticalAlignment":"top"} -->
        <div class="wp-block-column is-vertically-aligned-top"><!-- wp:heading -->
        <h2 class="wp-block-heading">All Candidates</h2>
        <!-- /wp:heading -->

        <!-- wp:list -->
    """))

    ## Candidates list
    f.write("<ul>")
    candidate_txts = []
    for name in elcn.getNamedCandidates():
        candidate_txts.append(dedent(f"""\
            <!-- wp:list-item -->
            <li>{name}</li>
            <!-- /wp:list-item -->"""
    ))

    f.write("\n\n".join(candidate_txts))
    f.write("</ul>\n")

    ## End Candidate list and start elected list
    f.write(dedent("""\
        <!-- /wp:list --></div>
        <!-- /wp:column --></div>
        <!-- /wp:columns -->

        <!-- wp:columns -->
        <div class="wp-block-columns"><!-- wp:column {"verticalAlignment":"top"} -->
        <div class="wp-block-column is-vertically-aligned-top"><!-- wp:heading -->
        <h2 class="wp-block-heading">Elected</h2>
        <!-- /wp:heading -->

        <!-- wp:list {"ordered":true} -->
    """))

    ## Elected list
    f.write("<ol>")
    candidate_txts = []
    for name in elcn.elected:
        candidate_txts.append(dedent(f"""\
            <!-- wp:list-item -->
            <li>{name}</li>
            <!-- /wp:list-item -->"""
    ))

    f.write("\n\n".join(candidate_txts))
    f.write("</ol>\n")

    ## End elected list and start voting round summary
    f.write(dedent("""\
        <!-- /wp:list --></div>
        <!-- /wp:column --></div>
        <!-- /wp:columns --></div>
        <!-- /wp:group -->

        <!-- wp:heading -->
        <h2 class="wp-block-heading">Voting Rounds</h2>
        <!-- /wp:heading -->

        <!-- wp:heading {"level":3} -->
        <h3 class="wp-block-heading">Summary</h3>
        <!-- /wp:heading -->

        <!-- wp:list -->
    """))

    ## Voting rounds summary list
    f.write("<ul>")
    rounds_txts = []
    for line in summarizeElection(elcn):
        rounds_txts.append(dedent(f"""\
            <!-- wp:list-item -->
            <li>{line}</li>
            <!-- /wp:list-item -->"""
    ))

    f.write("\n\n".join(rounds_txts))
    f.write("</ul>\n")

    ## End voting rounds summary list and do sankey image
    f.write(dedent("""\
        <!-- /wp:list -->

        <!-- wp:image {"align":"center","lightbox":{"enabled":true},"width":"1330px","height":"auto","sizeSlug":"full","linkDestination":"none"} -->
    """))
    f.write(dedent(f"""\
        <figure class="wp-block-image aligncenter size-full is-resized"><img src="/wp-content/uploads/election_charts/city_council/sankey/cc_election_sankey_{year}.png" alt="" style="width:1330px;height:auto"/></figure>
        <!-- /wp:image -->
        <!-- wp:paragraph -->
        <p><a href="/wp-content/uploads/election_charts/city_council/sankey/cc_election_sankey_{year}.png" target="_blank" rel="noreferrer noopener">Full Image</a><br><a href="/election/city-council-election-{year}-interactive/" target="_blank" rel="noreferrer noopener">Interactive</a></p>
        <!-- /wp:paragraph -->

    """))

    ## Markdown table
    table_lines = makeTable(elcn)
    table_txt = "\\n".join(table_lines).replace("--", "\\u002d\\u002d")
    f.write('<!-- wp:jetpack/markdown {"source":"\\n')
    f.write(table_txt)
    f.write('","className":"table-wrapper"} -->\n')
    f.write('<div class="wp-block-jetpack-markdown table-wrapper"></div>\n')

    ## End markdown table and do table only link
    f.write(dedent(f"""\
        <!-- /wp:jetpack/markdown -->

        <!-- wp:paragraph -->
        <p><a href="/election/city-council-election-{year}-table/" target="_blank" rel="noreferrer noopener">View Full Table</a></p>
        <!-- /wp:paragraph -->

    """))

    if elcn.source is not None:
        f.write(dedent(f"""\
            <!-- wp:paragraph -->
            <p>Source: <a href="{elcn.source}" target="_blank" rel="noreferrer noopener">{elcn.source}</a></p>
            <!-- /wp:paragraph -->

        """))


def writeIFrame(f, title, year):
    f.write(f"<!-- {title} - Interactive -->\n")
    f.write(dedent("""\
        <script>
        function squeezeToWidth(squeeze) {
          var flexible_chart = document.getElementById("chart_flexible");
          var fixed_chart = document.getElementById("chart_fixed_size");

          // If the checkbox is checked, display the output text
          if (squeeze){
            fixed_chart.style.display = "none";
            flexible_chart.style.display = "block";
          }
          else {
            fixed_chart.style.display = "block";
            flexible_chart.style.display = "none";
          }
          window.dispatchEvent(new Event('resize'));
        }
        </script>
    """))
    f.write(dedent(f"""\
        <div style="position: absolute; right: 5%; z-index: 99 !important;">
            <label class="switch"><input type="checkbox" id="squeeze-switch" onclick="squeezeToWidth(this.checked)" /><span class="slider round"></span></label>
            <b style="margin-left: 0px">Fit to width of screen</b>
        </div>
        <div class="responsiveWrapper" style="margin-top: -25px;">
            <iframe id="chart_flexible" src="/election-charts/city-council/cc_election_sankey_{year}.html" allowfullscreen frameborder="0"></iframe>
            <iframe id="chart_fixed_size" src="/election-charts/city-council/cc_election_sankey_fixed_size_{year}.html" allowfullscreen frameborder="0"></iframe>
        </div>
        <script>squeezeToWidth(document.getElementById("squeeze-switch").checked)</script>"""))


def runDecider(args, elcn, year, f):
    ## Make title
    title = args.title
    if year not in title:
        title += " " + year

    ## Pick generation type
    if args.table_only:
        writeTable(f, elcn)
    elif args.iframe_only:
        writeIFrame(f, title, year)
    elif args.full:
        writeFull(f, elcn, year)
    else:
        write(f, elcn, title, year)


def main(args):
    ## Files should have city council in them
    if not args.force \
        and not re.search(r"city[_\-\s]council|cc_election", args.election_file, re.IGNORECASE) \
        :
        print(f"Are you sure this is the election file you want? {args.election_file}", file=sys.stderr)
        return 1

    if args.output_file is not None and not args.force \
        and not re.search(r"city[_\-\s]council|cc_election", args.output_file, re.IGNORECASE) \
        :
        print(f"Are you sure this is the output file you want? {args.output_file}", file=sys.stderr)
        return 1

    ## Read elections file
    print(f"Opening '{args.election_file}'", file=sys.stderr)
    elcn = elections.loadElectionsFile(args.election_file)
    match = re.search(r"(\d{4})", elcn.date)
    if not match:
        raise Exception("Election date doesn't have a year in it")

    year = match.groups()[0]
    if args.output_file is not None:
        print(f"Writing to '{args.output_file}'", file=sys.stderr)
        with open(args.output_file, 'w', encoding='utf8') as f:
            runDecider(args, elcn, year, f)
    else:
        print("Writing to stdout", file=sys.stderr)
        runDecider(args, elcn, year, sys.stdout)
        print("", file=sys.stdout) ## Extra newline

    return 0

if __name__ == '__main__':
    sys.exit(main(parseArgs()))
