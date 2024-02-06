#!/bin/bash

##########
## Sankey
##########

# City Council HTML
for Y in 01 03 05 07 09 11 13 15 17 19 21 23; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_20$Y.html
done

# City Council HTML - Fixed Size
for Y in 01 03 05 07 13 15 19; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_fixed_size_20$Y.html
done

./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 2009" \
    --copyright "Charles J. Franklin" --copyright-tight                                \
    elections/csvs_cc/cc_election_2009.csv                                             \
    charts/city_council/sankey/html/cc_election_sankey_fixed_size_2009.html

for Y in 11 17 21 23; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        --width-ratio 500 --two-line-count 1000 \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_fixed_size_20$Y.html
done

for Y in 17 21 23; do
    ./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 20$Y" \
        --width-ratio 450 --two-line-count 1200 --copyright-tight                          \
        elections/csvs_cc/cc_election_20$Y.csv                                             \
        charts/city_council/sankey/html/cc_election_sankey_fixed_size_20$Y.html
done

./scripts/plot_sankey_chart.py --force-fixed-size --title "City Council Election 2023" \
    --width-ratio 450 --two-line-count 1500 --copyright-tight                          \
    elections/csvs_cc/cc_election_2023.csv                                             \
    charts/city_council/sankey/html/cc_election_sankey_fixed_size_2023.html


# City Council PNGs
for Y in 07; do
./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
    --width-ratio 200 --two-line-count 800 \
    elections/csvs_cc/cc_election_20$Y.csv                          \
    charts/city_council/sankey/png/cc_election_sankey_20$Y.png
done

for Y in 05 09 15; do
./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
    --width-ratio 250 --two-line-count 800 \
    elections/csvs_cc/cc_election_20$Y.csv                          \
    charts/city_council/sankey/png/cc_election_sankey_20$Y.png
done

for Y in 01 03 05 11 13; do
    ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
        --width-ratio 300 --two-line-count 800 \
        elections/csvs_cc/cc_election_20$Y.csv                          \
        charts/city_council/sankey/png/cc_election_sankey_20$Y.png
done

for Y in 19 21 23; do
    ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
        --width-ratio 300 --two-line-count 800 \
        elections/csvs_cc/cc_election_20$Y.csv                          \
        charts/city_council/sankey/png/cc_election_sankey_20$Y.png
done

for Y in 17; do
    ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
        --width-ratio 350 --two-line-count 800 \
        elections/csvs_cc/cc_election_20$Y.csv                          \
        charts/city_council/sankey/png/cc_election_sankey_20$Y.png
done

## School Committee HTML
for Y in 03 05 07 09 11 13 15 17 19 21 23; do
    ./scripts/plot_sankey_chart.py --title "School Committee Election 20$Y" \
        elections/csvs_sc/sc_election_20$Y.csv                              \
        charts/school_committee/sankey/html/sc_election_sankey_20$Y.html
done
