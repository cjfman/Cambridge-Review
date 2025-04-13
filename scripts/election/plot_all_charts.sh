#!/bin/bash -x

DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

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
            SANKEY=1
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
    echo "Must specify either --council or --school"
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
                $DIR/gcplot_sankey_chart.py --title "City Council Election 20$Y" \
                    --short --tight $CC_CSVS/cc_election_20$Y.csv                \
                    $CC_SANKEY/html/cc_election_sankey_20$Y.html
                $DIR/gcadd_no_cache.pl $CC_SANKEY/html/cc_election_sankey_20$Y.html
            done

            # City Council HTML - Fixed Size
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                $DIR/gcplot_sankey_chart.py --title "City Council Election 20$Y" \
                    --force-fixed-size --two-line-count 1500 --short --tight     \
                    $CC_CSVS/cc_election_20$Y.csv                                \
                    $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
                $DIR/gcadd_no_cache.pl $CC_SANKEY/html/cc_election_sankey_fixed_size_20$Y.html
            done

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
            for Y in $ALL_CC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                $DIR/gcplot_sankey_chart.py --title "City Council Election 20$Y" \
                    --two-line-count 750 --short --font-size 26 --tight          \
                    $CC_CSVS/cc_election_20$Y.csv                                \
                    $CC_SANKEY/png/cc_election_sankey_20$Y.png
            done

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
                $DIR/gcplot_sankey_chart.py --title "School Committee Election 20$Y" \
                    --short --tight $SC_CSVS/sc_election_20$Y.csv                    \
                    $SC_SANKEY/html/sc_election_sankey_20$Y.html
                $DIR/gcadd_no_cache.pl $SC_SANKEY/html/sc_election_sankey_20$Y.html
            done
            file_check "$ALL_SC_YEARS" $SC_SANKEY/html/sc_election_sankey_20 html
        fi ## HTML
        ## School Committee PNGs
        if [ ! -z $PNG ]; then
            ## Remove old files
            for Y in $ALL_SC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                rm -f $SC_SANKEY/png/sc_election_sankey_20$Y.png;
            done

            ## Make charts
            for Y in $ALL_SC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                $DIR/gcplot_sankey_chart.py --title "School Committee Election 20$Y" \
                    --two-line-count 750 --short --font-size 26 --tight              \
                    $SC_CSVS/sc_election_20$Y.csv                                    \
                    $SC_SANKEY/png/sc_election_sankey_20$Y.png
            done

            ## File check and add copyright
            file_check "$ALL_SC_YEARS" $SC_SANKEY/png/sc_election_sankey_20 png
            for Y in $ALL_SC_YEARS; do
                if [[ ! -z "$YEARS" && ! "$YEARS" = *$Y* ]]; then continue; fi
                echo "Adding copyright to sc_election_sankey_20$Y.png"
                convert $SC_SANKEY/png/sc_election_sankey_20$Y.png                   \
                    -gravity SouthEast -pointsize 30 -annotate +40+40                \
                    'Copyright © 2024, Charles Jessup Franklin. All rights reserved' \
                    $SC_SANKEY/png/sc_election_sankey_20$Y.png
            done
        fi ## PNG
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
            $DIR/gcplot_line_chart.py $CC_CSVS/cc_election_20$Y.csv \
                "City Council Election 20$Y"                        \
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
            $DIR/gcplot_line_chart.py $SC_CSVS/sc_election_20$Y.csv \
                "School Committee Election 20$Y"                    \
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
