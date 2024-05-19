#!/bin/bash -x

if [[ ! -z $1 ]]; then
    YEAR="$1"
    CYEAR=2020
    if [[ $YEAR < 2022 ]]; then
        CYEA=2010
    fi
    echo "Generating election ward maps for election year $YEAR using the $CYEAR census"
    ./scripts/draw_wards_map.py --census-year 2010 --all --title "Election $YEAR Precinct Map" \
        elections/wards/council/wards_$YEAR.csv maps/ward_all_$YEAR.html
    ./scripts/draw_wards_map.py --census-year 2010 --winners --title "Election $YEAR Precinct Map" \
        elections/wards/council/wards_$YEAR.csv maps/ward_winners_$YEAR.html
    exit;
fi

for YY in 15 17 19 21; do
    ./scripts/draw_wards_map.py --census-year 2010 --all --title "Election 20$YY Precinct Map" \
        elections/wards/council/wards_2019.csv maps/ward_all_2019.html
    ./scripts/draw_wards_map.py --census-year 2010 --winners --title "Election 20$YY Precinct Map" \
        elections/wards/council/wards_20$YY.csv maps/ward_winners_20$YY.html
done

./scripts/draw_wards_map.py --census-year 2020 --all --title "Election 2023 Precinct Map" \
    elections/wards/council/wards_2023.csv maps/ward_all_2023.html
./scripts/draw_wards_map.py --census-year 2020 --winners --title "Election 2023 Precinct Map" \
    elections/wards/council/wards_2023.csv maps/ward_winners_2023.html
