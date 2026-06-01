## Why

The `cornet view` command renders a static terminal table. Researchers need to compare variant metrics interactively, inspect failure error messages, and plot metric vs sweep axis across runs — none of which are possible in the current terminal output.

## What Changes

- **`cornet/ui/server.py`** — new FastAPI server serving three JSON API endpoints (`/api/leaderboard`, `/api/config`, `/api/status`) and mounting a static frontend
- **`cornet/ui/static/index.html`** — single-file browser frontend: leaderboard table with run checkboxes, x-axis dropdown picker, Plotly.js scatter/line chart, failure inspector panel
- **`cornet/__main__.py`** — add `ui` subcommand: `python -m cornet ui tasks/<name>` starts the server and opens the browser
- **`pyproject.toml`** — add `fastapi` and `uvicorn` as optional `[ui]` dependencies

## Capabilities

### New Capabilities

- `ui-server`: FastAPI server that exposes leaderboard and config data as JSON endpoints and serves the static frontend; includes mtime-based poll endpoint for auto-refresh detection
- `ui-leaderboard-table`: Interactive browser leaderboard table — sortable, per-row checkboxes to include/exclude runs from the plotter, status colour coding, failure indicator badge
- `ui-plotter`: Plotly.js scatter/line chart — x-axis selectable from parsed sweep axes (dropdown), y-axis always primary metric, gaps for FAILURE variants, hover tooltips; repeat runs grouped with individual dots + mean marker
- `ui-failure-inspector`: Panel listing all FAILURE runs with their `error` field message and output directory path

### Modified Capabilities

- `scenario-runner`: `cornet ui` subcommand added to the CLI entry point

## Impact

- **New files**: `cornet/ui/__init__.py`, `cornet/ui/server.py`, `cornet/ui/static/index.html`, `cornet/ui/static/style.css`
- **Modified**: `cornet/__main__.py` (~15 lines), `pyproject.toml` (optional dep group)
- **New dependencies**: `fastapi`, `uvicorn[standard]` (optional install: `pip install cornet[ui]`)
- **No breaking changes**: existing `run` and `view` subcommands unchanged; `leaderboard.json` schema unchanged
