## ADDED Requirements

### Requirement: `cornet ui` subcommand starts the web UI server for a task
The `cornet` CLI SHALL accept a `ui` subcommand: `cornet ui <task_dir>`. When invoked, it SHALL start the FastAPI/uvicorn server bound to `127.0.0.1` on a free port, log the URL to stderr, and open the URL in the default system browser.

#### Scenario: User runs `cornet ui tasks/pendulum_nr_control`
- **WHEN** the user runs `python -m cornet ui tasks/pendulum_nr_control`
- **THEN** the server starts on a free port bound to `127.0.0.1`
- **THEN** the URL `http://localhost:<port>` is printed to stderr
- **THEN** `webbrowser.open()` is called with that URL

#### Scenario: Task directory does not exist
- **WHEN** the user runs `cornet ui tasks/nonexistent`
- **THEN** the CLI prints an error message to stderr and exits with a non-zero code without starting the server

### Requirement: `cornet ui` accepts an optional `--port` argument
The `ui` subcommand SHALL accept `--port <int>` as an optional argument. When provided, the server SHALL bind to that specific port. When omitted, the server SHALL bind to a free ephemeral port chosen by the OS.

#### Scenario: User specifies a port
- **WHEN** the user runs `cornet ui tasks/pendulum_nr_control --port 8080`
- **THEN** the server binds to `127.0.0.1:8080`

#### Scenario: User omits the port
- **WHEN** the user runs `cornet ui tasks/pendulum_nr_control` without `--port`
- **THEN** the server binds to a free ephemeral port automatically

### Requirement: Auto-refresh badge reflects experiment run state
The browser UI SHALL display a status badge in the page header: `● LIVE` (green) when `running == true` from `/api/status`, and `● IDLE` (grey) when `running == false`. The badge SHALL update every 5 seconds via polling.

#### Scenario: Experiment is actively writing results
- **WHEN** `/api/status` returns `{"running": true, ...}`
- **THEN** the badge displays `● LIVE` in green

#### Scenario: No recent updates to leaderboard.json
- **WHEN** `/api/status` returns `{"running": false, ...}`
- **THEN** the badge displays `● IDLE` in grey

#### Scenario: mtime changes between polls
- **WHEN** the client polls `/api/status` and receives an `mtime` different from the last seen value
- **THEN** the client re-fetches `/api/leaderboard` and re-renders the table and chart without a full page reload
