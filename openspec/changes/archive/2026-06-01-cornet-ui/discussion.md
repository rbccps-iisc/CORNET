# Discussion: cornet-ui

## Challenge Report

### Challenge 1: variant_id parsing breaks when parameter values contain underscores
- **Source**: Design §D2; ui-plotter spec "X-axis dropdown is populated from parsed variant_id keys"
- **Assumption**: Splitting `variant_id` on `_` then on `=` reliably separates key-value pairs. For example, `numerology=1_bandwidth=20` yields `{numerology: "1", bandwidth: "20"}`.
- **Failure mode**: Any parameter whose value contains an underscore (e.g., `model=gpt_4_turbo_bandwidth=20`) produces a malformed parse — `model` gets value `"gpt"` and a spurious key `4` appears. The x-axis dropdown silently shows wrong or nonsensical keys, and chart data is silently mis-plotted. The design mentions a fallback to raw `variant_id` label, but gives no trigger condition, so the parser never knows it failed.
- **Risk category**: correctness
- **Mitigation**: Parse from left-to-right using a known separator convention: split on the LAST `=` in each `_`-delimited token (i.e., for each token, `rsplit("=", 1)`). Alternatively, use a regex that anchors on the pattern `([^=_]+)=([^_]+)` with a defined separator between pairs. Add a parse-validation step that rejects tokens where `key` itself is empty or contains `=`. Fall back to raw label only when the validation fails.

---

### Challenge 2: StaticFiles mount at `/` swallows API routes
- **Source**: ui-server spec "Server serves the static frontend" + "Server exposes leaderboard data as JSON"
- **Assumption**: Mounting `StaticFiles` at `/` and registering API routes at `/api/...` will coexist. FastAPI handles them independently.
- **Failure mode**: FastAPI's `app.mount("/", StaticFiles(...))` is a catch-all Starlette sub-application. It is matched BEFORE decorated route handlers for the same prefix if mounted at the application level before the routes are registered — or if it is the root mount. In FastAPI, `mount()` routes are checked in registration order. If `mount("/", ...)` is called before `@app.get("/api/...")` routes, every request to `/api/*` is handled by the static file server and returns a 404 (file not found) instead of JSON. The UI silently shows empty data.
- **Risk category**: correctness
- **Mitigation**: Always register all `@app.get("/api/...")` route handlers BEFORE calling `app.mount("/", StaticFiles(...))`. Document this ordering constraint explicitly in `server.py` with an inline comment. Alternatively, mount static files under a sub-path (e.g., `/static/`) and serve `index.html` via an explicit `GET /` route handler — this is the more robust pattern.

---

### Challenge 3: x-axis values are strings; Plotly sorts them lexicographically
- **Source**: Design §D2; ui-plotter spec "Chart plots selected runs as x=axis-value, y=primary_metric"
- **Assumption**: Plotly receives x-values parsed from `variant_id` and displays them in numerically meaningful order.
- **Failure mode**: All values extracted from `variant_id` are JavaScript strings (e.g., `"5"`, `"20"`, `"100"`). Plotly's default x-axis sorts string values lexicographically, producing `"100"`, `"20"`, `"5"`. A bandwidth sweep from 5 to 100 Mbps would show the rightmost bar at 20 Mbps with the trend line crossing back on itself — making the chart actively misleading rather than merely cosmetic.
- **Risk category**: correctness
- **Mitigation**: After parsing a parameter value, attempt `Number(val)` coercion in JavaScript. If `!isNaN(Number(val))` is true for all values in the selected x-axis column, pass them as numbers to Plotly. Preserve string x-axis for genuinely categorical parameters (e.g., `modulation=QPSK`). This coercion should happen in the chart-rendering function, not at parse time, since the same value may appear in different contexts.

---

### Challenge 4: TOCTOU race in free-port discovery
- **Source**: Design §D6
- **Assumption**: Binding to `127.0.0.1:0`, reading the assigned port, and then passing that port integer to `uvicorn.run(port=N)` will successfully start the server on that port.
- **Failure mode**: There is a time-of-check to time-of-use window between closing the discovery socket and uvicorn calling `bind()` again on the same port. Another process can claim the port in that interval. On a lightly loaded developer machine this race is rare but on shared research servers it is reproducible. uvicorn will raise `OSError: [Errno 98] Address already in use` and the server never starts.
- **Risk category**: correctness
- **Mitigation**: Use `uvicorn.Config` + `uvicorn.Server` with a pre-bound socket instead of `uvicorn.run(port=N)`. The pattern is: `sock = socket.socket(); sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]` then pass `sock` directly to `uvicorn.Server.serve(sockets=[sock])`. The OS never releases the socket, eliminating the race entirely. This is the pattern used by pytest-asyncio and Starlette's test client.

---

### Challenge 5: `running` heuristic misclassifies long-running and just-completed sweeps
- **Source**: Design §D5; scenario-runner spec "Auto-refresh badge reflects experiment run state"
- **Assumption**: A 30-second mtime recency window reliably distinguishes a live sweep from a completed one.
- **Failure mode**: (a) A sweep where each variant takes >30 seconds to execute will show `● IDLE` between every variant write, then briefly flip to `● LIVE` when the next entry is written. Researchers watching a long-running sweep see flickering IDLE badges and may incorrectly conclude the experiment stalled. (b) A sweep that completed 10 seconds ago shows `● LIVE` for 20 more seconds, potentially misleading a researcher into waiting for more data.
- **Risk category**: ux
- **Mitigation**: The `running` field is cosmetic (the mtime-change trigger for data reload is the authoritative mechanism). Add a spec-level note that the badge is advisory and may lag up to 30 seconds. Optionally increase the threshold to 120 seconds to reduce false IDLE flicker on long variants. Document the threshold as a named constant in `server.py` so it can be tuned without searching.

---

## Counter-Designs

### Option 1: Server-Side Rendering with Jinja2 (no JSON API, full-page interaction)
The FastAPI server renders HTML directly using Jinja2 templates. There are no `/api/*` JSON endpoints. Chart data is embedded as `<script>` tags in the rendered page. Table interactions require form submissions or HTMX partial updates.

**Pros**:
- variant_id parsing happens in Python (easier to test, robust to edge cases)
- No risk of API/StaticFiles route ordering bugs
- No CDN dependency for Plotly (can embed data directly)
- Simpler mental model for researchers unfamiliar with JSON APIs

**Cons**:
- Full-page refresh required for checkbox interactions (or HTMX dependency)
- No live chart update without WebSocket or polling full HTML — increases server load
- Server and presentation are tightly coupled; harder to add a future REST consumer
- More templates to maintain

**Trade-offs**: Trades JS complexity for server-side complexity. Checkbox-driven chart filtering would require HTMX or a full page reload — significantly degrading the interactive feel that is the core value proposition of this feature.

---

### Option 2: Vendored Plotly.js (offline-first, no CDN)
Keep the FastAPI + vanilla JS architecture from the proposal, but ship `plotly.min.js` as a package data file inside `cornet/ui/static/`. The CDN `<script>` tag is replaced with a local `/static/plotly.min.js` reference.

**Pros**:
- Works in air-gapped environments (university HPC clusters often block CDN traffic)
- Removes an external dependency from every page load
- Faster initial render (no round-trip to `cdn.plot.ly`)

**Cons**:
- Adds ~3 MB to the pip package (and to git history if vendored)
- `pyproject.toml` must use `package-data` or `data-files` to include the asset
- Plotly version becomes pinned; updating requires a manual vendor step

**Trade-offs**: Solves the air-gap risk identified in the design's Risks section. The 3 MB addition is significant but one-time. This is a better fit for research environments where CDN access is not guaranteed.

---

### Option 3: WebSocket push with `watchfiles` (real-time, no polling)
Replace the 5-second mtime poll with a `watchfiles.awatch()` coroutine running in the FastAPI server's event loop. When `leaderboard.json` changes, the server pushes a `{"event": "refresh"}` message over a WebSocket to all connected clients.

**Pros**:
- Zero-latency updates (variant results appear in the browser the instant they are written)
- No `setInterval` in the client; browser wakes only on real events
- Cleaner than polling; more correct for fast sweeps (< 5s per variant)

**Cons**:
- Requires `watchfiles` as an additional dependency
- WebSocket handling adds client-side complexity (reconnect logic, fallback if WS fails)
- More server-side code to maintain (async generator, broadcast to multiple connections)
- Overkill for sweeps where variants take 10+ seconds each

**Trade-offs**: Genuine improvement for fast sweeps, unnecessary complexity for slow ones. For a v1 tool where the primary use case is after-the-fact inspection, polling is sufficient.

---

**Recommendation**: Endorse the original proposal (FastAPI + CDN Plotly + polling) with amendments from D2–D5 below. Option 2 (vendored Plotly) is worth adopting as a v1.1 follow-up once the core feature is stable; raise it as a tracked issue. Option 3 is a clean v2 upgrade path.

---

## Decisions Made

- **D1**: Endorse the original architecture (FastAPI + CDN Plotly + vanilla JS + mtime polling) — *the zero-build-toolchain constraint is the primary design driver and all three alternatives require either additional dependencies or sacrificing interactivity.*

- **D2**: The `variant_id` parser SHALL use `rsplit("=", 1)` on each underscore-delimited token, and SHALL validate that no resulting key contains `=` or is empty; fall back to raw `variant_id` as x-axis label only when validation fails — *this prevents silent mis-parse when parameter values contain underscores, which is a realistic scenario (e.g., model names, scheduler policies).*

- **D3**: The chart-rendering function SHALL attempt `Number(val)` coercion on x-axis values before passing to Plotly; if all values in the column are finite numbers, they SHALL be passed as JavaScript `Number` type — *lexicographic ordering of numeric strings produces actively misleading trend lines.*

- **D4**: All `@app.get("/api/...")` route handlers SHALL be registered in `server.py` BEFORE the `app.mount("/", StaticFiles(...))` call; a comment SHALL document this ordering constraint — *FastAPI evaluates mounts before decorated routes for the same prefix when mount order is wrong; this is a silent bug that returns 404 on all API calls.*

- **D5**: The free-port discovery SHALL use the pre-bound socket pattern (`socket.bind(("127.0.0.1", 0))` → read port → pass socket to `uvicorn.Server`) rather than the close-and-reuse pattern — *eliminates the TOCTOU race between port discovery and uvicorn bind; the socket is never released to the OS.*

- **D6**: The `running` badge is advisory only; the 30-second threshold SHALL be a named constant `RUNNING_WINDOW_SECONDS = 30` in `server.py`; the spec and any user-facing help text SHALL describe the badge as "reflects recent activity" not "reflects live status" — *the mtime-change trigger for data reload is the authoritative mechanism; the badge is purely cosmetic and will lag on long-variant sweeps.*
