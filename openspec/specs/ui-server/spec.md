## ADDED Requirements

### Requirement: Server exposes leaderboard data as JSON
The server SHALL read `leaderboard.json` from the task directory and expose it at `GET /api/leaderboard`, returning a JSON array of all run entries.

#### Scenario: Leaderboard file exists
- **WHEN** `GET /api/leaderboard` is called and `leaderboard.json` exists in the task directory
- **THEN** the server returns HTTP 200 with a JSON array containing all run entries from the file

#### Scenario: Leaderboard file does not exist
- **WHEN** `GET /api/leaderboard` is called and `leaderboard.json` does not exist
- **THEN** the server returns HTTP 200 with an empty JSON array `[]`

### Requirement: Server exposes config data as JSON
The server SHALL read `config.yaml` from the task directory and expose it at `GET /api/config`, returning the parsed config as a JSON object.

#### Scenario: Config file exists
- **WHEN** `GET /api/config` is called and `config.yaml` exists in the task directory
- **THEN** the server returns HTTP 200 with the parsed config as a JSON object

#### Scenario: Config file does not exist
- **WHEN** `GET /api/config` is called and `config.yaml` does not exist
- **THEN** the server returns HTTP 200 with an empty JSON object `{}`

### Requirement: Server exposes mtime-based status for auto-refresh
The server SHALL expose `GET /api/status` returning a JSON object with `mtime` (float, Unix timestamp of `leaderboard.json`'s last modification time) and `running` (boolean, `True` when `mtime` is within the last 30 seconds).

#### Scenario: Leaderboard file has been modified recently
- **WHEN** `GET /api/status` is called and `leaderboard.json` was modified within the last 30 seconds
- **THEN** the server returns `{"mtime": <float>, "running": true}`

#### Scenario: Leaderboard file has not been modified recently
- **WHEN** `GET /api/status` is called and `leaderboard.json` was last modified more than 30 seconds ago
- **THEN** the server returns `{"mtime": <float>, "running": false}`

#### Scenario: Leaderboard file does not exist
- **WHEN** `GET /api/status` is called and `leaderboard.json` does not exist
- **THEN** the server returns `{"mtime": 0.0, "running": false}`

### Requirement: Server serves the static frontend
The server SHALL mount `cornet/ui/static/` at the root path `/` and serve `index.html` as the default document for `GET /`.

#### Scenario: Browser navigates to root
- **WHEN** a browser sends `GET /` to the server
- **THEN** the server returns HTTP 200 with the contents of `index.html`

### Requirement: Server binds to localhost only
The server SHALL bind exclusively to `127.0.0.1` and SHALL NOT accept connections from external network interfaces.

#### Scenario: Server starts
- **WHEN** the server is started via `cornet ui`
- **THEN** uvicorn binds to `host="127.0.0.1"` and the chosen port
