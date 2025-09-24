#!/bin/bash

FILERS=$(perl -ne 'print "$1\n" if /"cpfId": (\d+)/;' candidate_data/filers.json)
for FILER in $FILERS; do
    #CHART="charts/filers/reports/${FILER}_report_chart.html"
    #./scripts/election/ocpf.py query-reports $FILER "candidate_data/reports/${FILER}_reports.json"

    #./scripts/election/ocpf.py query-contributions $FILER "candidate_data/contributions/${FILER}_contributions.json"

    #./scripts/election/draw_contributions.py --google-api-key credentials/maps_key \
    #    candidate_data/contributions/${FILER}_contributions.json maps/contributions/contributions_$FILER.html

    ./scripts/election/draw_contributions.py -m --google-api-key credentials/maps_key \
        candidate_data/contributions/${FILER}_contributions.json maps/contributions/contributions_mobile_$FILER.html

    #./scripts/election/plot_finances.py --out "$CHART" --in-file "candidate_data/reports/${FILER}_reports.json" --copyright-tight --h-legend
#    if [[ ! -f "$CHART" ]]; then
#        echo "Making blank chart for $CHART"
#        cp charts/filers/reports/empty_report_chart.html "$CHART"
#    fi
done
