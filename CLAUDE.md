# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Cambridge Review is a civic journalism/data project covering Cambridge, MA local government. See README.md for full architecture, data flow, and pipeline documentation.

All generated HTML (~9,000 files) is intentionally tracked in git as a distribution mechanism for deploying from other machines.

## Setup

```bash
pip install -r requirements.txt
```

All scripts are run from the **repo root**, not from within `scripts/`. Scripts add `scripts/` to `sys.path` themselves to import `citylib`.

## Key Commands

See README.md for full pipeline commands. Quick reference:

```bash
scripts/election/plot_all_charts.sh -a          # all election charts, all years
scripts/election/draw_all_maps.sh YYYY          # ward/precinct maps
scripts/meeting/find_meetings.py primegov       # fetch meeting list from PrimeGov
scripts/meeting/process_meetings.py             # process agendas and extract actions
scripts/sync_to_remote.py --dry-run             # preview deploy to website
```

After generating any HTML output file, inject cache-busting headers:

```bash
scripts/add_no_cache.pl path/to/output.html
```

Called automatically by `plot_all_charts.sh` and `draw_all_maps.sh`; must be called manually for one-off outputs.

## Important prior sessions

44fa7ed7-9eb9-4662-b559-987bc5953f23
The foundational session — analyzed the codebase, created CLAUDE.md, and built the PrimeGov portal integration (primegov_portal.py)
to replace the old IQM2-only meeting pipeline. Ran out of context and was continued twice.

33f53b89-9afd-42a5-a7c0-5354604e98e8
Refactored find_meetings.py to use iqm2/primegov subcommands; fixed _parse_vote_text treating "PASSED TO A SECOND READING" as
"Passed"; removed unused return values from that function; fixed malformed settings.json.

43630346-e6ac-4e1f-b769-8ea18e082e7a
Built out the summary/prep pipeline (generate_summary.py, prep_agenda.py)

f7187432-2132-4231-9e5d-8da893f9c897
Added type hints to process_meetings.py and the scripts/citylib module.

89dc3315-c344-4a19-9c5c-4e839319ee8a
Created a new script `sync_to_remote.py` to assist with syncing charts and images to a remote cPanel server

