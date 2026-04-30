# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cambridge Review is a civic journalism/data project covering Cambridge, MA local government. It processes raw election results, campaign finance records, and City Council meeting agendas into charts, maps, and HTML pages published to a WordPress site.

All generated HTML (~9,000 files) is intentionally tracked in git as a distribution mechanism for deploying from other machines.

## Setup

```bash
pip install -r requirements.txt
```

All scripts are run from the **repo root**, not from within `scripts/`. Scripts add `scripts/` to `sys.path` themselves to import `citylib`.

## Key Commands

### Election pipeline

```bash
# Scrape ranked-choice results from the city website into a CSV
scripts/election/get_election_results.py <base_url> <first_page> elections/csvs_cc/cc_election_YYYY.csv

# Generate Sankey (vote transfer) charts — HTML and/or PNG, for council or school committee
scripts/election/plot_all_charts.sh --sankey --html --council --years 25
scripts/election/plot_all_charts.sh --sankey --png  --council --years 25
scripts/election/plot_all_charts.sh -a   # all charts, all years

# Generate ward/precinct maps
scripts/election/draw_all_maps.sh YYYY

# Generate WordPress HTML for a single election year
scripts/election/generate_cc_wp_html.py elections/csvs_cc/cc_election_YYYY.csv
scripts/election/generate_sc_wp_html.py elections/csvs_sc/sc_election_YYYY.csv
```

### Campaign finance pipeline

```bash
# Query OCPF API for reports and contributions
scripts/election/ocpf.py query-reports   <cpfid> candidate_data/reports/<cpfid>_reports.json
scripts/election/ocpf.py query-contributions <cpfid> candidate_data/contributions/<cpfid>_contributions.json

# Draw contribution maps for all filers in candidate_data/filers.json
scripts/election/run_on_filers.sh

# Draw map for a single filer
scripts/election/draw_contributions.py --google-api-key credentials/maps_key \
    single-filer candidate_data/contributions/<cpfid>_contributions.json \
    maps/contributions/contributions_<cpfid>.html
```

### Meeting pipeline

```bash
# Parse a downloaded meeting calendar HTML into a CSV of meeting IDs/URLs
scripts/meeting/find_meetings.py <meetings_html_file> <output_csv>

# Process meetings: fetch agendas, extract actions, write CSVs and JSON
scripts/meeting/process_meetings.py [args]

# Join per-meeting final_actions JSON files into one (run from repo root)
# See scripts/meeting/scripts.sh for the exact shell one-liner

# Sync data to Google Sheets
scripts/meeting/sync_sheets.py
```

### Post-generation steps

After generating any HTML output file, run `add_no_cache.pl` to inject cache-busting headers:

```bash
scripts/add_no_cache.pl path/to/output.html
```

This is called automatically by `plot_all_charts.sh` and `draw_all_maps.sh` but must be called manually for one-off outputs.

## Architecture

### `scripts/citylib/` — shared library

All pipeline scripts import from this package. Scripts locate it via `sys.path.append(str(Path(__file__).parent.parent.absolute()) + '/')`.

| Module | Purpose |
|---|---|
| `elections.py` | `Election`, `WardElection`, `Ballot` data classes; CSV loaders (`loadElectionsFile`, `loadWardElectionFile`, `loadBallotPiles`) |
| `filers.py` | `Filer`, `Report`, `Contribution`, `Contributor` data classes; OCPF JSON parsers |
| `agenda.py` | `AgendaItem` hierarchy for parsing City Council agenda items and votes |
| `meeting_portal.py` | Scrapes the Cambridge meeting portal (IQM2) to extract agenda items and vote records |
| `councillors.py` | Loads councillor name/alias data from a YAML file; used to resolve vote attributions |
| `utils/utils.py` | `fetch_url` (with optional disk cache), `insertCopyright`, `insertNoCache`, currency helpers, colored terminal output |
| `utils/html_parsing.py` | BeautifulSoup helper wrappers |
| `utils/simplehtml.py` | Minimal HTML generation utilities |
| `utils/gis.py` | GIS/coordinate utilities |
| `utils/color_schemes.py` | Color palettes (including colorblind-friendly set used by Sankey charts) |

### Election data flow

```
City website HTML
  → get_election_results.py
  → elections/csvs_cc/cc_election_YYYY.csv   (round-by-round RCV counts)

elections/csvs_cc/cc_election_YYYY.csv
  → plot_sankey_chart.py  → charts/city_council/sankey/html/*.html  (interactive)
                          → charts/city_council/sankey/png/*.png    (static)
  → plot_line_chart.py    → charts/city_council/line/*.png
  → generate_cc_wp_html.py → wp_html/city_council/cc_wp_YYYY.html  (WordPress post)
  → generate_summary.py   → (summary CSV rows)

elections/wards/council/wards_YYYY.csv
  → draw_wards_map.py → maps/wards/ward_all_YYYY.html
                      → maps/wards/ward_winners_YYYY.html
```

### Campaign finance data flow

```
OCPF API
  → ocpf.py → candidate_data/filers.json
             → candidate_data/reports/<cpfid>_reports.json
             → candidate_data/contributions/<cpfid>_contributions.json

candidate_data/contributions/<cpfid>_contributions.json
  → draw_contributions.py → maps/contributions/contributions_<cpfid>.html
                          → maps/contributions/contributions_mobile_<cpfid>.html
  → plot_finances.py      → charts/filers/reports/<cpfid>_report_chart.html
```

### Meeting data flow

```
Cambridge meeting portal (IQM2)
  → find_meetings.py     → CSV of meeting IDs and URLs
  → process_meetings.py  → meeting_data/cache/  (HTML/PDF per meeting)
                         → meeting_data/cache/final_actions_meeting_<id>.json
                         → meeting_data/meetings_html/ (raw scraped HTML)

Per-meeting JSON files
  → scripts.sh one-liner → meeting_data/final_actions.json  (combined)
  → tabulate_votes.py    → per-councillor vote tallies
  → sync_sheets.py       → Google Sheets
```

### Data directories

| Path | Contents |
|---|---|
| `elections/csvs_cc/`, `elections/csvs_sc/` | Canonical RCV result CSVs (source of truth for charts) |
| `elections/wards/council/` | Per-precinct vote counts by candidate |
| `elections/official/` | Official results PDFs/data by year |
| `candidate_data/filers.json` | Master list of OCPF filer IDs and committee names |
| `candidate_data/contributions/`, `candidate_data/reports/` | Per-filer OCPF API responses |
| `meeting_data/cache/` | Cached meeting HTML/PDF and per-meeting JSON (gitignored for PDFs) |
| `summaries/` | Markdown meeting summaries by date |
| `geojson/` | Cambridge ward/precinct boundary files used by folium maps |
| `address_coordinates.json` | Geocoded address→coordinate cache for contribution maps |
| `credentials/` | API keys (gitignored) |
