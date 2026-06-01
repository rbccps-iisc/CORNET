## 1. Project Scaffolding

- [x] 1.1 Create `cornet/ui/__init__.py` (empty module marker)
- [x] 1.2 Create `cornet/ui/static/` directory placeholder (`.gitkeep` or `style.css`)
- [x] 1.3 Add `fastapi` and `uvicorn[standard]` as optional `[ui]` extras in `pyproject.toml`

## 2. FastAPI Server

- [x] 2.1 Create `cornet/ui/server.py` with a `create_app(task_dir: Path) -> FastAPI` factory function
- [x] 2.2 Implement `GET /api/leaderboard` — reads `leaderboard.json`, returns `[]` if absent
- [x] 2.3 Implement `GET /api/config` — reads and YAML-parses `config.yaml`, returns `{}` if absent
- [x] 2.4 Implement `GET /api/status` — returns `{"mtime": float, "running": bool}` using `RUNNING_WINDOW_SECONDS = 30` constant; returns `{"mtime": 0.0, "running": false}` if `leaderboard.json` absent
- [x] 2.5 Register all `/api/*` route handlers BEFORE mounting `StaticFiles` at `/`; add ordering comment
- [x] 2.6 Mount `cornet/ui/static/` directory at root `/` using `StaticFiles(html=True)`
- [x] 2.7 Server SHALL bind exclusively to `127.0.0.1` (enforce in `create_app` or server startup)

## 3. Free-Port Discovery (D5)

- [x] 3.1 Implement `find_free_port() -> tuple[socket.socket, int]` helper that binds `127.0.0.1:0` and returns the live socket + assigned port
- [x] 3.2 Use `uvicorn.Config` + `uvicorn.Server` with `sockets=[sock]` to start the server on the pre-bound socket (eliminates TOCTOU race)

## 4. `cornet ui` Subcommand

- [x] 4.1 Add `ui` subparser to `cornet/__main__.py` with positional `task_dir` and optional `--port INT` arguments
- [x] 4.2 Validate that `task_dir` exists and is a directory; print error to stderr and `sys.exit(1)` if not
- [x] 4.3 If `--port` is given, bind directly to that port; otherwise use `find_free_port()`
- [x] 4.4 Print `http://localhost:<port>` to stderr before starting the server
- [x] 4.5 Call `webbrowser.open(f"http://localhost:{port}")` after printing the URL

## 5. Frontend — Leaderboard Table

- [x] 5.1 Create `cornet/ui/static/index.html` with page skeleton: header (task name + live badge), table section, chart section, failures section
- [x] 5.2 Implement `fetchLeaderboard()` — `GET /api/leaderboard`, stores data in module-level array
- [x] 5.3 Render leaderboard table with columns: checkbox, variant_id, status, metric, timestamp, output_dir
- [x] 5.4 Apply colour coding: SUCCESS → green, FAILURE → red, RUNNING → amber (CSS classes)
- [x] 5.5 Render `[!]` badge on FAILURE rows; clicking badge scrolls to `#failures-panel` and highlights that entry
- [x] 5.6 Checkbox `change` event handler updates chart (calls `renderChart()`) immediately

## 6. Frontend — x-axis Parsing and Plotter (D2, D3)

- [x] 6.1 Implement `parseVariantId(variantId)` — splits on `_`, then `rsplit("=", 1)` per token; validates no key is empty or contains `=`; returns `{}` on failure (triggers raw-label fallback)
- [x] 6.2 Implement `stripRunSuffix(variantId)` — removes trailing `_run\d+` to recover the base combo key for repeat grouping
- [x] 6.3 Implement `buildAxisKeys(entries)` — returns union of all parameter keys across all parsed `variant_id` values
- [x] 6.4 Populate x-axis dropdown from `buildAxisKeys()`; default to first key alphabetically; re-populate on data refresh
- [x] 6.5 Implement `coerceXValues(vals)` — if all values are finite numbers via `Number(v)`, return as `Number[]`; otherwise return as `string[]`
- [x] 6.6 Implement `renderChart()` — for each checked row, parse x-value for selected axis; skip FAILURE entries; coerce x-values numerically; render Plotly scatter trace
- [x] 6.7 Render repeat-group mean markers: group by `stripRunSuffix(variant_id)`, compute mean y per group, overlay as larger marker on same x

## 7. Frontend — Failure Inspector

- [x] 7.1 Implement `renderFailures(entries)` — renders failure blocks below chart; shows `variant_id`, `error` (fallback: "(no error message recorded)"), `output_dir`
- [x] 7.2 Ensure failures container has `id="failures-panel"` for anchor scroll from `[!]` badge
- [x] 7.3 Re-render failure panel on every data refresh cycle

## 8. Frontend — Auto-Refresh

- [x] 8.1 Implement `pollStatus()` — `GET /api/status` every 5 seconds; compare returned `mtime` to last-seen value
- [x] 8.2 On mtime change: re-fetch `/api/leaderboard`, re-render table, re-render chart (respecting current checkbox state), re-render failure panel
- [x] 8.3 Update header badge: show `● LIVE` (green) when `running == true`, `● IDLE` (grey) when `false`

## 9. Static Styles

- [x] 9.1 Create `cornet/ui/static/style.css` with minimal styles: status colour classes, badge styles, table layout, failure block formatting

## 10. Tests

- [x] 10.1 Create `tests/test_ui_server.py` — test `GET /api/leaderboard` returns `[]` when file absent, returns entries when present
- [x] 10.2 Test `GET /api/status` returns `mtime=0.0, running=false` when file absent; returns correct mtime and `running=true` for recently-modified file
- [x] 10.3 Test `GET /api/config` returns `{}` when file absent, returns parsed dict when present
- [x] 10.4 Test that `GET /api/leaderboard` is reachable (returns 200) and static route does not shadow it (mount ordering regression)
- [x] 10.5 Test `find_free_port()` returns a usable port and that the socket is valid
