# Cambridge Review

Civic journalism/data project covering Cambridge, MA local government. Processes raw election results, campaign finance records, and City Council meeting agendas into charts, maps, and HTML pages published to [cambridgereview.org](https://cambridgereview.org).

All generated HTML (~9,000 files) is tracked in git as a distribution mechanism for deploying from other machines.

## Setup

```bash
pip install -r requirements.txt
```

All scripts are run from the **repo root**, not from within `scripts/`. Scripts add `scripts/` to `sys.path` themselves to import `citylib`.

## Pipelines

### Elections

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

Data flow:
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

### Campaign finance

```bash
# Query OCPF API for reports and contributions
scripts/election/ocpf.py query-reports        <cpfid> candidate_data/reports/<cpfid>_reports.json
scripts/election/ocpf.py query-contributions  <cpfid> candidate_data/contributions/<cpfid>_contributions.json

# Draw contribution maps for all filers in candidate_data/filers.json
scripts/election/run_on_filers.sh

# Draw map for a single filer
scripts/election/draw_contributions.py --google-api-key credentials/maps_key \
    single-filer candidate_data/contributions/<cpfid>_contributions.json \
    maps/contributions/contributions_<cpfid>.html
```

Data flow:
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

### City Council meetings

```bash
# Fetch City Council meetings from the PrimeGov API into a CSV
scripts/meeting/find_meetings.py primegov [output_csv] [--year YYYY]

# Parse a downloaded IQM2 meeting calendar HTML into a CSV (legacy)
scripts/meeting/find_meetings.py iqm2 <meetings_html_file> [output_csv] [--council-only]

# Process meetings: fetch agendas, extract actions, write CSVs and JSON
scripts/meeting/process_meetings.py [args]

# Sync data to Google Sheets
scripts/meeting/sync_sheets.py
```

Data flow:
```
Cambridge meeting portal (PrimeGov)
  → find_meetings.py     → CSV of meeting IDs and URLs
  → process_meetings.py  → meeting_data/cache/  (HTML/PDF per meeting)
                         → meeting_data/processed/
  → sync_sheets.py       → Google Sheets and AirTable
```

### Post-generation

After generating any HTML output file, inject cache-busting headers:

```bash
scripts/add_no_cache.pl path/to/output.html
```

Called automatically by `plot_all_charts.sh` and `draw_all_maps.sh`; must be called manually for one-off outputs.

### Deploying images and charts to the website

```bash
# Preview what would be uploaded
scripts/sync_to_remote.py --dry-run

# Upload all changed files
scripts/sync_to_remote.py

# Force-upload everything regardless of modification time
scripts/sync_to_remote.py --force

# Touch all remote files to reset sync state
scripts/sync_to_remote.py --touch-all
```

Requires `sync_config.yaml` (gitignored). Copy `sync_config.yaml.example` and fill in credentials.

## Architecture

### `scripts/citylib/` — shared library

| Module | Purpose |
|---|---|
| `elections.py` | `Election`, `WardElection`, `Ballot` data classes; CSV loaders |
| `filers.py` | `Filer`, `Report`, `Contribution`, `Contributor` data classes; OCPF JSON parsers |
| `agenda.py` | `AgendaItem` hierarchy for parsing City Council agenda items and votes |
| `primegov_portal.py` | Scrapes the PrimeGov meeting portal to extract agenda items and vote records |
| `iqm2_portal.py` | Scrapes the legacy IQM2 meeting portal |
| `councillors.py` | Loads councillor name/alias data from a YAML file; resolves vote attributions |
| `utils/utils.py` | `fetch_url` (with disk cache), `insertCopyright`, `insertNoCache`, currency helpers |
| `utils/html_parsing.py` | BeautifulSoup helper wrappers |
| `utils/simplehtml.py` | Minimal HTML generation utilities |
| `utils/gis.py` | GIS/coordinate utilities |
| `utils/color_schemes.py` | Color palettes (including colorblind-friendly set used by Sankey charts) |

### Data directories

| Path | Contents |
|---|---|
| `elections/csvs_cc/`, `elections/csvs_sc/` | Canonical RCV result CSVs — source of truth for all charts |
| `elections/wards/council/` | Per-precinct vote counts by candidate |
| `candidate_data/filers.json` | Master list of OCPF filer IDs and committee names |
| `meeting_data/councilors.yml` | Current and past city councillors with name aliases |
| `meeting_data/meeting_sessions/` | CSVs of council meeting listings |
| `meeting_data/processed/` | CSVs of council meeting agenda items |
| `summaries/` | Markdown meeting summaries by date |
| `geojson/` | Cambridge ward/precinct boundary files used by folium maps |
| `charts/` | Generated election charts (HTML and PNG) |
| `maps/` | Generated ward and contribution maps |
| `wp_html/` | Generated WordPress post HTML |
| `credentials/` | API keys (gitignored) |
