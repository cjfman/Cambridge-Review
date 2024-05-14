#!/bin/bash

./scripts/draw_wards_map.py --census-year 2010 --all --title "Election 2019 Precinct Map" \
    elections/wards/council/wards_2019.csv maps/ward_all_2019.html
./scripts/draw_wards_map.py --census-year 2010 --winners --title "Election 2019 Precinct Map" \
    elections/wards/council/wards_2019.csv maps/ward_winners_2019.html

./scripts/draw_wards_map.py --census-year 2010 --all --title "Election 2021 Precinct Map" \
    elections/wards/council/wards_2021.csv maps/ward_all_2021.html
./scripts/draw_wards_map.py --census-year 2010 --winners --title "Election 2021 Precinct Map" \
    elections/wards/council/wards_2021.csv maps/ward_winners_2021.html

./scripts/draw_wards_map.py --census-year 2020 --all --title "Election 2023 Precinct Map" \
    elections/wards/council/wards_2023.csv maps/ward_all_2023.html
./scripts/draw_wards_map.py --census-year 2020 --winners --title "Election 2023 Precinct Map" \
    elections/wards/council/wards_2023.csv maps/ward_winners_2023.html
