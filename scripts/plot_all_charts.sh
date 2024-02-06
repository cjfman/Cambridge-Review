#!/bin/bash

##########
## Sankey
#########

# City Council HTML
for Y in 01 03 05 07 09 11 13 15 17 19 21 23; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_fixed_size_20$Y.html
done

for Y in ; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_fixed_size_20$Y.html
done

## School Committee HTML
for Y in 03 05 07 09 11 13 15 17 19 21 23; do
    ./scripts/plot_sankey_chart.py --title "School Committee Election 20$Y" \
        elections/csvs_sc/sc_election_20$Y.csv                              \
        charts/school_committee/sankey/html/sc_election_sankey_20$Y.html
done
