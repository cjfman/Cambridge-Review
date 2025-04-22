#!/bin/bash

FILERS=$(perl -ne 'print "$1\n" if /"cpfId": (\d+)/;' candidate_data/filers.json)
for FILER in $FILERS; do
    CHART="charts/filers/reports/${FILER}_report_chart.html"
    #./scripts/election/ocpf.py query-reports $FILER "candidate_data/reports/${FILER}_reports.json"
    #./scripts/election/plot_finances.py --out "$CHART" --in-file "candidate_data/reports/${FILER}_reports.json" --copyright-tight --h-legend
    #./scripts/add_no_cache.pl "$CHART"
    if [[ ! -f "$CHART" ]]; then
        echo "Making blank chart for $CHART"
        cp charts/filers/reports/empty_report_chart.html "$CHART"
    fi
done
