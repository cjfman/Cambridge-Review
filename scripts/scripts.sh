## Remove empty files
du final_actions_meeting_*.json | perl -ne '/^(\d+)\s+(.*)/; print "$2\n" if !$1;' | xargs rm

## Join actions files
pushd meeting_data; echo '{' > final_actions.json; for ID in `du cache/final_actions_meeting_*.json | perl -ne '/(\d+).json/; print "$1\n" if $1'`; do echo -n "\"$ID\": "; cat cache/final_actions_meeting_$ID.json; echo ","; done | head -n -1 >> final_actions.json; echo -e '\n}' >> final_actions.json; perl -i -pe 's/\]\n/]/' final_actions.json; popd
