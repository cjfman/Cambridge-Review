#! /usr/bin/python3

import re
import sys

from typing import List, Sequence

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import elections


def nextOpenVPostition(
        existing:Sequence[float],
        max_v:float,
        scale:float=250,
        fontsize:float=plt.rcParams["font.size"],
        dec=2
    ) -> float:
    """Return the next highest space available for a new line of text"""
    if not existing:
        return max_v

    lowest = min(existing)
    return round(lowest - max_v/scale*fontsize, dec)


def filterTickmarks(ticks:Sequence[list], add:Sequence[list], exclude:Sequence[list]) -> List[float]:
    """Remove any tickmarks that are too close to protected ticks"""
    ## This lamda purpusfully references the 'exclude' list
    filter_fn = lambda tik: not any(map(lambda x: tik and abs(tik-x)/tik < 0.05, exclude))
    add = list(filter(filter_fn, add))
    exclude = exclude + add ## Modify exclude, knowing that 'filter_fn' lambda will pick it up
    ticks = list(filter(filter_fn, ticks))
    return ticks + add


def main(vote_file, title, chart_file=None):
    """Plot line graph of election"""
    print(f"Reading '{vote_file}'")
    election = elections.loadElectionsFile(vote_file)
    top_line = election.quota
    if election.max_votes > top_line:
        top_line *= 1.10

    print(f"Generating plot")

    ## Make figure
    f = plt.figure()
    f.set_figheight(10)
    f.set_figwidth(f.get_figheight()*1.2)

    ## Y-axis
    ax = f.add_subplot(111)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.get_yaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ','))
    )

    ## X axis
    plt.xticks(list(range(election.num_rounds + 1)))
    ax.set_xlim([1, election.num_rounds])

    ## Add quota line and tick mark
    plt.plot(
        np.array(range(1, election.num_rounds+1)),
        np.array([election.quota]*election.num_rounds),
        color='black',
        linewidth=3,
    )
    plt.text(
        election.num_rounds,
        election.quota,
        "- " + format(election.quota, ','),
        va='center',
        ha='left',
        weight='bold',
    )

    ## Add vote lines
    line_labels = []
    for name, votes in sorted(tuple(election.truncated.items()), key=lambda x: x[1]):
        ## Skip write-ins with no votes
        #if "write-in" in name.lower() and not votes[0]:
        if re.match(r"write-in (\d+|other)", name, re.IGNORECASE):
            continue

        ## Plot line
        round_count = len(votes)
        p = None
        if not votes[-1]:
            ## Candidate lost
            p = plt.plot(np.array(range(1, round_count)), np.array(votes[:-1]), linewidth=1)
            plt.text(round_count-1, votes[-2], "x", va='center', ha='center', color='red', size=15)
        else:
            ## Candidate won
            ## Were they at or above quota?
            if round_count == 1 or votes[-2] > election.quota:
                ## Place win diamon on round where they won, not the transfer round
                votes_cropped = list(map(lambda x: min(x, top_line), votes))
                p = plt.plot(np.array(range(1, round_count + 1)), np.array(votes_cropped), linewidth=1, zorder=-1)
                color = p[-1].get_color()
                plt.scatter(round_count-1, votes_cropped[-2], marker='D', color=color, zorder=10000)
            else:
                p = plt.plot(np.array(range(1, round_count + 1)), np.array(votes), linewidth=1)
                color = p[-1].get_color()
                plt.scatter(round_count, votes[-1], marker='D', color=color, zorder=10000)

        line_labels.append((votes[0], name, { 'color': p[-1].get_color() }))


    ## Write names in order of most #1 votes to least
    ## Order is important for nextOpenVPostition(...)
    line_labels.append((election.quota, 'Quota', { 'color': 'black', 'weight': 'bold' }))
    text_v_pos = []
    over_quota = 0
    for vote_count, name, opts in sorted(line_labels, reverse=True):
        ## Plot name and avoid overlapping with other names
        v_pos = min([vote_count, top_line, nextOpenVPostition(text_v_pos, top_line, scale=600)])
        ## Label vote count if it above the top line
        if vote_count > top_line:
            h_pos = 1 + 0.1*(1+over_quota)
            over_quota += 1
            plt.text(1, v_pos, name + ' ', va='bottom', ha='right', **opts)
            plt.text(h_pos, v_pos, format(vote_count, ','), va='bottom', ha='left', weight='bold', **opts)
        else:
            plt.text(1, v_pos, name + ' ', va='center', ha='right', **opts)

        text_v_pos.append(v_pos)

    ## Set Y axis limit and add tickmarks
    ax.set_ylim(bottom=0, top=top_line)
    plt.yticks(filterTickmarks(list(plt.yticks()[0]), [top_line], [election.quota]))

    ## Legend
    legend_elements = [
        Line2D([0], [0], marker='D', color='black', label="Elected",  lw=0),
        Line2D([0], [0], marker='x', color='red',   label="Defeated", lw=0, markersize=10),
    ]
    ax.legend(handles=legend_elements)

    ## Add labels and plot
    ax.set_ylim(bottom=0, top=top_line)
    plt.xlabel('Round',   weight='bold')
    plt.ylabel('Votes',   weight='bold')
    plt.title(title, weight='bold')
    plt.tight_layout()
    plt.grid()
    if chart_file:
        if '.' not in chart_file:
            chart_file += ".png"
            print(f"Saving as png '{chart_file}'")
        else:
            print(f"Saving as '{chart_file}'")

        plt.savefig(chart_file)
    else:
        print("Showing plot")
        plt.show()

    return 0


if __name__ == '__main__':
    usage = f"Usage: {sys.argv[0]} <vote file> <title> [chart file]"
    num_args = len(sys.argv)
    if num_args == 3:
        sys.exit(main(sys.argv[1], sys.argv[2]))
    elif num_args == 4:
        sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
    else:
        print(usage)
        sys.exit(1)
