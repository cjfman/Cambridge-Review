#! /usr/bin/python3

import argparse
import re
import sys

from textwrap import dedent

from markdown_table_generator import generate_markdown, table_from_string_list, Alignment

import elections


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-file",
        help="Output file")
    parser.add_argument("--title", default="Election",
        help="Title to give each election")
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
    f.write(f"wp-content/uploads/election_charts/school_committee/line/sc_election_{year}_linechart.png\n")

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
    f.write(f"/wp-content/uploads/election_charts/school_committee/sankey/sc_election_sankey_{year}.png\n")

    ## Table
    f.write("\n------\n\nVote Table\n\n")
    table = generate_markdown(table_from_string_list(elcn.generateTableRows(), Alignment.RIGHT))
    ## Switch first row to be left aligned
    lines = table.split("\n")
    formatter = lines[1]
    formatter = formatter.replace(':', '-', 1)
    formatter = formatter.replace('-', ':', 1)
    lines[1] = formatter
    f.write("\n".join(lines))
    f.write("\n")


def main(args):
    print(f"Opening '{args.election_file}'")
    elcn = elections.loadElectionsFile(args.election_file)
    match = re.search(r"(\d{4})", elcn.date)
    if not match:
        raise Exception("Election date doesn't have a year in it")

    year = match.groups()[0]
    title = args.title + " " + year
    if args.output_file is not None:
        print(f"Writing to '{args.output_file}'")
        with open(args.output_file, 'w', encoding='utf8') as f:
            write(f, elcn, title, year)
    else:
        print("Writing to stdout")
        write(sys.stdout, elcn, title, year)


if __name__ == '__main__':
    sys.exit(main(parseArgs()))
