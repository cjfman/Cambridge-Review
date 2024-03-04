#!/bin/bash

ALL_CC_YEARS="01 03 05 07 09 11 13 15 17 19 21 23"
ALL_SC_YEARS="03 05 07 09 11 13 15 17 19 21 23"
SANKEY=
LINE=
COUNCIL=
SCHOOL=
PNG=
HTML=
YEARS=

CC_CSVS=elections/csvs_cc
CC_SANKEY=charts/city_council/sankey
CC_LINE=charts/city_council/line

SC_CSVS=elections/csvs_sc
SC_SANKEY=charts/school_committee/sankey
SC_LINE=charts/school_committee/line

while [[ $# -gt 0 ]]; do
    case $1 in
        --sankey)
            SANKEY=1
            shift
            ;;
        --line)
            LINE=1
            shift
            ;;
        --council)
            COUNCIL=1
            shift
            ;;
        --school)
            SCHOOL=1;
            shift
            ;;
        --png)
            PNG=1
            shift
            ;;
        --html)
            HTML=1
            shift
            ;;
        --years)
            YEARS="$2"
            shift ## option name
            shift ## argument
            ;;
        -a|--all)
            SANKEY=1
            LINE=1
            COUNCIL=1
            SCHOOL=1
            PNG=1
            HTML=1
            ;;
        -*|--*)
            echo "Unknown option $1"
            exit 1
            ;;
        *)
            POSITIONAL_ARGS+=("$1") # save positional arg
            shift # past argument
            ;;
    esac
done


## Arguments check
ERROR=
if [[ -z $COUNCIL && -z $SCHOOL ]]; then
    echo "Must specify either --council or --line"
    ERROR=1
fi
if [[ -z $SANKEY && -z $LINE ]]; then
    echo "Must specify either --sankey or --line"
    ERROR=1
fi
if [[ ! -z $SANKEY && -z $PNG && -z $HTML ]]; then
    echo "Must specify either --png or --html when using --sankey"
    ERROR=1
fi
if [ ! -z $ERROR ]; then
    exit 1;
fi


function file_check() {
    CHECK_YEARS=$1
    FILE_BASE=$2
    EXT=$3
    MISSING=
    for Y in $CHECK_YEARS; do
        FILE="$FILE_BASE$Y.$EXT"
        if [ ! -f "$FILE" ]; then
            echo "Missing file \"$FILE\""
            MISSING=1
        fi
    done
    if [ ! -z $MISSING ]; then
        exit 1;
    fi
}


##########
## Sankey
##########
if [ ! -z $SANKEY ]; then
    if [ ! -z $COUNCIL ]; then
        # City Council HTML
        if [ ! -z $HTML ]; then
            ## Clear old files
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                rm -f $CC_SANKEY/html/cc_election_sankey_20$Y.html
                rm -f $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
            done

            ## Make new flexible charts
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    $CC_CSVS/cc_election_20$Y.csv                                   \
                    $CC_SANKEY/html/cc_election_sankey_20$Y.html
            done

            # City Council HTML - Fixed Size
            for Y in 01 03 05 07 13 15 19; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    --force-fixed-size $CC_CSVS/cc_election_20$Y.csv                \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
            done

            if [[ -z "$YEARS" || "$YEARS" = *09* ]]; then
                ./scripts/plot_sankey_chart.py --title "City Council Election 2009"        \
                    --force-fixed-size --copyright "Charles J. Franklin" --copyright-tight \
                    $CC_CSVS/cc_election_2009.csv                                          \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_2009.html
            fi

            for Y in 11 17 21 23; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    --force-fixed-size --width-ratio 500 --two-line-count 1000      \
                    $CC_CSVS/cc_election_20$Y.csv                                   \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
            done

            for Y in 17 21; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y"              \
                    --force-fixed-size --width-ratio 450 --two-line-count 1200 --copyright-tight \
                    $CC_CSVS/cc_election_20$Y.csv                                                \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
            done

            if [[ -z "$YEARS" || "$YEARS" = *23* ]]; then
                ./scripts/plot_sankey_chart.py --title "City Council Election 2023"              \
                    --force-fixed-size --width-ratio 450 --two-line-count 1500 --copyright-tight \
                    $CC_CSVS/cc_election_2023.csv                                                \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_2023.html
            fi

            ## Do file check
            file_check "$ALL_CC_YEARS" $CC_SANKEY/html/cc_election_sankey_20 html
            file_check "$ALL_CC_YEARS" $CC_SANKEY/html/cc_election_sankey_fixed_size_20 html
        fi ## HTML

        ## City Council PNGs
        if [ ! -z $PNG ]; then
            ## Remove old files
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                rm -f $CC_SANKEY/png/cc_election_sankey_20$Y.png;
            done

            ## Make charts
            if [[ -z "$YEARS" || "$YEARS" = *07* ]]; then
                ./scripts/plot_sankey_chart.py --title "City Council Election 2007" \
                    --width-ratio 200 --two-line-count 800                          \
                    $CC_CSVS/cc_election_2007.csv                                   \
                    $CC_SANKEY/png/cc_election_sankey_2007.png
            fi
            for Y in 05 09 15; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    --width-ratio 250 --two-line-count 800                          \
                    $CC_CSVS/cc_election_20$Y.csv                                   \
                    $CC_SANKEY/png/cc_election_sankey_20$Y.png
            done

            for Y in 01 03 05 11 13; do
                if [[ ! -z "$YEARS" && ! "$YEARS" == *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    --width-ratio 300 --two-line-count 800                          \
                    $CC_CSVS/cc_election_20$Y.csv                                   \
                    $CC_SANKEY/png/cc_election_sankey_20$Y.png
            done

            for Y in 19 21 23; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "City Council Election 20$Y" \
                    --width-ratio 300 --two-line-count 800                          \
                    $CC_CSVS/cc_election_20$Y.csv                                   \
                    $CC_SANKEY/png/cc_election_sankey_20$Y.png
            done

            if [[ -z "$YEARS" || "$YEARS" = *17* ]]; then
                ./scripts/plot_sankey_chart.py --title "City Council Election 2017" \
                    --width-ratio 350 --two-line-count 800                          \
                    $CC_CSVS/cc_election_2017.csv                                   \
                    $CC_SANKEY/png/cc_election_sankey_2017.png
            fi

            ## File check and add copyright
            file_check "$ALL_CC_YEARS" $CC_SANKEY/png/cc_election_sankey_20 png
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                echo "Adding copyright to cc_election_sankey_20$Y.png"
                convert $CC_SANKEY/png/cc_election_sankey_20$Y.png                   \
                    -gravity SouthEast -pointsize 30 -annotate +40+40                \
                    'Copyright © 2024, Charles Jessup Franklin. All rights reserved' \
                    $CC_SANKEY/png/cc_election_sankey_20$Y.png
            done
        fi ## PNG
    fi ## Council

    if [ ! -z $SCHOOL ]; then
        ## School Committee HTML
        if [ ! -z $HTML ]; then
            ## Remove old files
            for Y in $ALL_SC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                rm -f $CC_SANKEY/html/sc_election_sankey_20$Y.html
            done

            ## Make new charts
            for Y in $ALL_SC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                ./scripts/plot_sankey_chart.py --title "School Committee Election 20$Y" \
                    $SC_CSVS/sc_election_20$Y.csv                                       \
                    $SC_SANKEY/html/sc_election_sankey_20$Y.html
            done
            file_check "$ALL_SC_YEARS" $SC_SANKEY/html/sc_election_sankey_20 html
        fi ## HTML
    fi ## School
fi ## Sankey


##########
## Line
##########
if [ ! -z $LINE ]; then
    if [ ! -z $COUNCIL ]; then
        ## City Council
        for Y in $ALL_CC_YEARS; do
            if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
            ./scripts/plot_line_chart.py $CC_CSVS/cc_election_20$Y.csv \
                "City Council Election 20$Y"                           \
                $CC_LINE/cc_election_20${Y}_linechart.png
            echo "Adding copyright to cc_election_linechart_20$Y.png"
            convert $CC_LINE/cc_election_20${Y}_linechart.png                    \
                -gravity SouthEast -pointsize 12 -annotate +10+10                \
                'Copyright © 2024, Charles Jessup Franklin. All rights reserved' \
                $CC_LINE/cc_election_20${Y}_linechart.png
        done

        file_check "$ALL_CC_YEARS" $CC_LINE/cc_election_20${Y}_linechart.png
    fi ## Council
    if [ ! -z $SCHOOL ]; then
        ## School Committee
        for Y in $ALL_SC_YEARS; do
            if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
            rm -f $CS_LINE/sc_election_20${Y}_linechart.png
        done

        for Y in $ALL_SC_YEARS; do
            if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
            ./scripts/plot_line_chart.py $SC_CSVS/sc_election_20$Y.csv \
                "School Committee Election 20$Y"                       \
                $CS_LINE/sc_election_20${Y}_linechart.png
            echo "Adding copyright to sc_election_linechart_20$Y.png"
            convert $CS_LINE/sc_election_20${Y}_linechart.png \
                -gravity SouthEast -pointsize 12 -annotate +10+10                 \
                'Copyright © 2024, Charles Jessup Franklin. All rights reserved'  \
                $CS_LINE/sc_election_20${Y}_linechart.png
        done

        file_check "$ALL_SC_YEARS" $SC_LINE/sc_election_20${Y}_linechart.png
    fi ## School
fi ## Line
