#! /usr/bin/python3

import sys

from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np

import elections

FILE = "/home/charles/Projects/cambridge_review/elections/csvs_sc/sc_election_2005.csv"


def nextOpenVPostition(
        existing:Sequence[float],
        max_v:float,
        scale:float=250,
        fontsize:float=plt.rcParams["font.size"],
        dec=2
    ) -> float:
    if not existing:
        return max_v

    lowest = min(existing)
    return round(lowest - max_v/scale*fontsize, dec)


def main():
    election = elections.loadElectionsFile(FILE)

    ## Y-axis
    f = plt.figure()
    ax = f.add_subplot(111)
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position("right")

    ## X-axis
    ax.set_xlim([1, election.num_rounds])

    ## Add quota line
    plt.plot(
        np.array(range(1, election.num_rounds+1)),
        np.array([election.quota]*election.num_rounds),
        color='black',
        linewidth=3,
    )

    ## Add vote lines
    line_labels = [(election.quota, 'Quota', 'black')]
    for name, votes in election.truncated.items():
        round_count = len(votes)
        p = None
        ## Plot line
        if not votes[-1]:
            ## Candidate lost
            p = plt.plot(np.array(range(1, round_count)), np.array(votes[:-1]), label=name)
            plt.text(round_count-1, votes[-2], "X", verticalalignment='center', color='red')
        else:
            ## Candidate won
            p = plt.plot(np.array(range(1, round_count + 1)), np.array(votes), label=name)

        line_labels.append((votes[0], name, p[-1].get_color()))


    ## Write names in order
    text_v_pos = []
    for vpos, name, color in sorted(line_labels, reverse=True):
        v = min(vpos, nextOpenVPostition(text_v_pos, election.max_votes))
        plt.text(1, v, name + ' ', horizontalalignment='right', color=color)
        text_v_pos.append(v)
        print(f"{name} {vpos} -> {v}")

    ## Add labels to plot
    plt.xlabel("Round")
    plt.ylabel("Votes")
    plt.title("Election")
    #plt.legend(loc='best', ncol=1)
    plt.tight_layout()
    plt.show()

    return 0


if __name__ == '__main__':
    sys.exit(main())
