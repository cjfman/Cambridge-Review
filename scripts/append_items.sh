#!/bin/bash

USAGE="$0 [-s|--src SOURCE_DIR] <[-d|--dst DESTINATION_DIR]|[-y|--year YEAR]> [--replace]"

## Defaults
SRC=meeting_data/processed/current
DST_BASE=meeting_data/processed
DST=
REPLACE=0

## Arg parse
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--src)
            SRC=$2
            shift ## past argument
            shift ## past value
            ;;
        -d|--dst)
            DST=$2
            shift ## past argument
            shift ## past value
            ;;
        -y|--year)
            YEAR=$2
            shift ## past argument
            shift ## past value
            ;;
        --replace|-r)
            REPLACE=1
            shift
            ;;
        -*|--*)
            echo "Unknown option $1"
            echo $USAGE
            exit 1
            ;;
        *)
            echo "Unknown argument $1"
            echo $USAGE
            exit 1
    esac
done

## Make destination
if [[ ! -z $YEAR ]]; then
    if [[ ! -z $DST ]]; then
        echo "--dst and --year are mutually exclusive options"
        echo $USAGE
        exit 1
    fi
    DST="$DST_BASE/$YEAR"
fi

if [[ -z $DST ]]; then
    echo "One of --dst or --year required"
    echo $USAGE
    exit 1
fi

echo "Using SRC=$SRC"
echo "Using DST=$DST"

for FILE in $(ls "$SRC"); do
    if [[ ! -f "$SRC/$FILE" ]] || [[ ! -f "$DST/$FILE" ]]; then
        continue
    fi

    if [[ $REPLACE -eq 1 ]]; then
        ## Rebuild DST: keep rows whose UID is not in SRC, then append all SRC rows
        TMP=$(mktemp)
        awk -F',' '
            NR==FNR { if (FNR > 1) seen[$1]=1; next }
            FNR==1 || !seen[$1]
        ' "$SRC/$FILE" "$DST/$FILE" > "$TMP"
        tail -n +2 "$SRC/$FILE" >> "$TMP"
        ADDED=$(( $(wc -l < "$TMP") - $(wc -l < "$DST/$FILE") ))
        mv "$TMP" "$DST/$FILE"
        echo "$SRC/$FILE >> $DST/$FILE (replaced; net $(( ADDED )) rows)"
    else
        ## Append only rows from SRC whose UID does not already exist in DST
        ## Ensure DST ends with a newline before appending; $(tail -c1) strips
        ## trailing newlines in command substitution, so an empty result means
        ## the file already ends with \n.
        [[ -n "$(tail -c1 "$DST/$FILE")" ]] && printf '\n' >> "$DST/$FILE"
        BEFORE=$(wc -l < "$DST/$FILE")
        awk -F',' '
            NR==FNR { if (FNR > 1) seen[$1]=1; next }
            FNR > 1 && !seen[$1]
        ' "$DST/$FILE" "$SRC/$FILE" >> "$DST/$FILE"
        AFTER=$(wc -l < "$DST/$FILE")
        echo "$SRC/$FILE >> $DST/$FILE (added $(( AFTER - BEFORE )) rows)"
    fi
done
