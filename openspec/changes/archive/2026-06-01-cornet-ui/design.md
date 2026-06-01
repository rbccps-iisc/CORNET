## Context

CORNET experiments produce `leaderboard.json` files as runs complete (written by `leaderboard/writer.py`). The existing `cornet view` command renders this data as a Rich terminal table — useful for quick inspection but limited: no charts, no failure detail, no interactive comparison. Researchers running parameter sweeps (e.g., 12-variant grids) need to compare metric trends and diagnose why specific variants failed, which requires a browser-based interactive UI.

The leaderboard JSON has a stable schema: `{timestamp, variant_id, status, metric, output_dir, primary_metric, error}`. The `variant_id` encodes the parameter combination as `key=val_key=val` (underscore-separated). The orchestrator is unchanged by this work; the UI is a pure read-only consumer of existing output files.

## Goals / Non-Goals

**Goals:**
- Interactive leaderboard table in the browser (per-row selection, status colour coding)
- Plotly.js chart: x-axis = any sweep parameter (dropdown), y-axis = primary metric
- Failure inspector: surfaces `error` field from `FAILURE` entries
- Auto-refresh when `leaderboard.json` changes during an active sweep (mtime poll)
- Zero build toolchain: one `pip install cornet[ui]` and `cornet ui tasks/<name>`

**Non-Goals (v1):**
- Multi-task comparison (compare across task directories)
- Analysis-JSON deep dive (per-variant output logs/plots)
- CSV/HTML export or report generation
- Config editing through the UI
- Authentication or network exposure (localhost only)
- Real-time streaming / WebSocket push (mtime poll is sufficient)

## Decisions

### D1 — FastAPI + uvicorn for the server; Plotly.js via CDN; single `index.html`

**Chosen:** FastAPI (async request handling, clean route definitions, automatic JSON serialisation) with `uvicorn[standard]` as the ASGI runner. Plotly.js loaded from `cdn.plot.ly` in the HTML `<head>`. All frontend logic in a single `index.html` + `style.css`; no build step, no npm, no bundler.

**Alternatives considered:**
- *Flask*: simpler but lacks async and auto-serialisation; no real advantage for this use case.
- *http.server (stdlib)*: no routing primitives; would require manual JSON parsing; rejected.
- *React/Vue with build step*: richer component model but adds `npm`, `node`, and a build pipeline — hostile to a research CLI tool installed via `pip`.

**Rationale:** Researchers install CORNET via `pip`. Adding a JS build step for a monitoring UI would be a significant barrier. Plotly.js from CDN is 3 MB loaded once; acceptable for a local tool.

### D2 — `variant_id` parsed client-side; `_run\d+` suffix stripped for repeat grouping

**Chosen:** The browser parses each `variant_id` string by splitting on `_` then on `=` to recover `{key: val}` pairs. A trailing `_run<N>` suffix (e.g., `_run1`, `_run2`) is stripped before grouping, so all runs with the same parameter combination are treated as repeats.

**Alternatives considered:**
- *Server-side parsing (`/api/variants`)*: adds a second endpoint and duplicates data already in `/api/leaderboard`; not worth it.
- *Requiring structured metadata in leaderboard.json*: would require orchestrator changes; rejected to keep this PR read-only on the orchestrator.

**Rationale:** The `variant_id` format is already defined in the parameter-sweep spec and is stable. Client-side parsing keeps the server thin and the full `variant_id` available as a tooltip.

### D3 — X-axis candidates = union of all parsed variant_id keys; dropdown populated dynamically

**Chosen:** On page load (and each refresh), the frontend builds a set of all parameter keys seen across all `variant_id` values. The x-axis dropdown is populated from this set. Default selection is the first key alphabetically.

**Alternatives considered:**
- *Derive from `config.yaml` sweep axes*: requires the `/api/config` endpoint and YAML parsing; also fails for tasks without a sweep (no axes). Kept `/api/config` for future use but x-axis derivation uses leaderboard data only.

**Rationale:** Works for all tasks including those with no `sweep` block (dropdown has one or zero items; chart gracefully shows nothing). No coupling to config parsing.

### D4 — FAILURE variants shown as gaps in Plotly chart; listed in failure panel below chart

**Chosen:** Variants with `status == "FAILURE"` are excluded from the chart data series (Plotly automatically renders a gap for missing x values when using `connectgaps: false`). A separate "Failures" accordion section below the chart lists each failure's `variant_id`, `error` message, and `output_dir` link.

**Alternatives considered:**
- *Plot FAILURE as y=0 or NaN markers*: visually misleading (zero is a valid metric value); rejected.
- *Red error markers at y-axis bottom*: clutters the chart; not useful for diagnosing errors.

**Rationale:** Clean separation between metric visualisation (chart) and diagnostic info (panel). Researchers can glance at the chart for trends and scroll to the failure panel for root-cause.

### D5 — mtime-based auto-refresh: `/api/status` returns `leaderboard.json` mtime; client polls every 5 s

**Chosen:** The server exposes `GET /api/status` returning `{"mtime": <float>, "running": <bool>}` where `mtime` is `os.path.getmtime(leaderboard_path)` and `running` is `True` when the file was modified within the last 30 seconds. The browser stores the last seen mtime and triggers a full data reload when it changes. A badge in the header shows `● LIVE` (green) or `● IDLE` (grey).

**Alternatives considered:**
- *WebSocket push from orchestrator*: requires orchestrator modification; rejected (UI is read-only).
- *Full-page polling every N seconds regardless*: wastes bandwidth and causes chart flicker; rejected.
- *inotify via `watchfiles`*: adds a dependency and complicates the server; overkill for 5 s poll.

**Rationale:** mtime diff is a single `os.path.getmtime` call — near-zero overhead. The 5 s interval is imperceptible in practice. No orchestrator coupling.

### D6 — `cornet ui tasks/<name>` finds a free port, starts uvicorn, opens browser via `webbrowser.open()`

**Chosen:** The `ui` subparser resolves the task directory path, finds a free TCP port (bind to `127.0.0.1:0`), passes it to `uvicorn.run()`, then calls `webbrowser.open(f"http://localhost:{port}")`.

**Alternatives considered:**
- *Fixed port (e.g., 8000)*: conflicts when multiple CORNET UI instances run simultaneously; rejected.
- *User-specified `--port` flag with fixed default*: acceptable but adds CLI noise; a random free port is more ergonomic and still overridable with `--port` as an optional argument.

**Rationale:** Researchers often have multiple terminal sessions. Automatic port selection prevents "port already in use" errors with no user action required.

## Risks / Trade-offs

- **CDN dependency**: Plotly.js is loaded from `cdn.plot.ly`. Air-gapped environments will see a blank chart. Mitigation: document that `pip install cornet[ui]` works offline except for Plotly.js; provide an `--offline` flag (v2) that bundles the asset.
- **Large leaderboard files**: `/api/leaderboard` loads the full JSON on every request. At 10 000 variants this could be slow. Mitigation: acceptable for v1 (sweeps rarely exceed 200 variants); add pagination in v2 if needed.
- **`variant_id` format assumptions**: parsing logic assumes the `key=val_key=val` format defined in the parameter-sweep spec. If a future sweep plugin uses a different format, the x-axis dropdown may show garbage. Mitigation: fall back to showing raw `variant_id` as x-axis label.
- **Browser open on headless servers**: `webbrowser.open()` silently fails on headless CI machines. Mitigation: log the URL to stderr so the user can copy-paste it; this is the standard pattern used by Jupyter.

## Open Questions

- None — all design decisions resolved in explore session.
