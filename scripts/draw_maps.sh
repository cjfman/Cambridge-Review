#!/bin/bash

./scripts/plot_wards_map.py --census-year 2010 --all     elections/wards/council/wards_2021.csv maps/ward_all_2021.html
./scripts/plot_wards_map.py --census-year 2010 --winners elections/wards/council/wards_2021.csv maps/ward_winners_2021.html

./scripts/plot_wards_map.py --census-year 2020 --all     elections/wards/council/wards_2023.csv maps/ward_all_2023.html
./scripts/plot_wards_map.py --census-year 2020 --winners elections/wards/council/wards_2023.csv maps/ward_winners_2023.html
