#! /usr/bin/python3

import sys

from typing import List, Sequence

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

import elections

FILE = "/home/charles/Projects/cambridge_review/elections/csvs_sc/sc_election_2023.csv"


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
    exclude = exclude + add
    ticks = filter(lambda tik: not any(map(lambda x: tik and abs(tik-x)/tik < 0.1, exclude)), ticks)
    return list(ticks) + add


def main():
    """Plot line graph of election"""
    election = elections.loadElectionsFile(FILE)

    ## Y-axis
    f = plt.figure()
    ax = f.add_subplot(111)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")
    ax.set_ylim(bottom=0, top=max(election.max_votes, election.quota)*1.05)
    ax.get_yaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda x, p: format(int(x), ','))
    )

    ## X axis
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
    for name, votes in election.truncated.items():
        ## Skip write-ins with no votes
        if "write-in" in name.lower() and not votes[0]:
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
                p = plt.plot(np.array(range(1, round_count + 1)), np.array(votes), linewidth=1, zorder=-1)
                color = p[-1].get_color()
                plt.scatter(round_count-1, votes[-2], marker='D', color=color, zorder=10000)
            else:
                p = plt.plot(np.array(range(1, round_count + 1)), np.array(votes), linewidth=1)
                color = p[-1].get_color()
                plt.scatter(round_count, votes[-1], marker='D', color=color, zorder=10000)

        line_labels.append((votes[0], name, { 'color': p[-1].get_color() }))


    ## Write names in order of most #1 votes to least
    ## Order is important for nextOpenVPostition(...)
    line_labels.append((election.quota, 'Quota', { 'color': 'black', 'weight': 'bold' }))
    text_v_pos = []
    for vpos, name, opts in sorted(line_labels, reverse=True):
        v = min(vpos, nextOpenVPostition(text_v_pos, election.max_votes))
        plt.text(1, v, name + ' ', va='center', ha='right', **opts)
        text_v_pos.append(v)

    ## Add extra tick mark for max votes
    if election.max_votes > election.quota:
        plt.yticks(filterTickmarks(list(plt.yticks()[0]), [election.max_votes], [election.quota]))

    ## Legend
    legend_elements = [
        Line2D([0], [0], marker='D', color='black', label="Elected",  lw=0),
        Line2D([0], [0], marker='x', color='red',   label="Defeated", lw=0, markersize=10),
    ]
    ax.legend(handles=legend_elements)

    ## Add labels and plot
    plt.xlabel('Round',   weight='bold')
    plt.ylabel('Votes',   weight='bold')
    plt.title('School Comittee Election 2023', weight='bold')
    plt.tight_layout()
    plt.grid()
    plt.show()

    return 0


if __name__ == '__main__':
    sys.exit(main())
