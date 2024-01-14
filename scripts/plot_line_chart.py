#! /usr/bin/python3

import sys

import matplotlib.pyplot as plt
import numpy as np

import elections

FILE = "/home/charles/Projects/cambridge_review/elections/csvs_sc/sc_election_2005.csv"


def main():
    election = elections.loadElectionsFile(FILE)
    ## Add vote lines
    for name, votes in election.truncated.items():
        round_count = len(votes)
        if not votes[-1]:
            plt.plot(np.array(range(1, round_count)), np.array(votes[:-1]), label=name)
            if round_count > 2:
                plt.text(round_count-1, votes[-2], "X", verticalalignment='center')
        else:
            plt.plot(np.array(range(1, round_count + 1)), np.array(votes), label=name)

    ## Add quota line
    plt.plot(
        np.array(range(1, election.num_rounds+1)),
        np.array([election.quota]*election.num_rounds),
        color='black',
        linewidth=3,
    )


    ## Add lables to plot
    plt.xlabel("Round")
    plt.ylabel("Votes")
    plt.title("Election")
    plt.legend(loc='best', ncol=1)
    plt.show()

    return 0


if __name__ == '__main__':
    sys.exit(main())
