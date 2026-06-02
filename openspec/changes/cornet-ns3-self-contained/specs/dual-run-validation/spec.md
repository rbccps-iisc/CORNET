## ADDED Requirements

### Requirement: ns3-version-tag-injection
The orchestrator reads `CORNET_NS3_TAG` env var and appends it to the
`variant_id` of each leaderboard entry as `{variant_id}@{ns3_tag}`.

#### Scenario: tag appended when env var set
- **WHEN** `CORNET_NS3_TAG=ns3-v24 python -m cornet tasks/pendulum_nr_control`
- **THEN** the leaderboard entry `variant_id` is `pendulum_nr_control@ns3-v24`

#### Scenario: no tag when env var absent
- **WHEN** `CORNET_NS3_TAG` is not set
- **THEN** `variant_id` is unchanged (existing behaviour preserved)

### Requirement: make-validate-target
`make validate` runs `pendulum_nr_control` against both installed NS-3
versions sequentially, writing separate leaderboard entries.

#### Scenario: dual-version validation run
- **WHEN** `make validate` is run with both `~/ns-3-dev-v24` and `~/ns-3-dev-v47` installed
- **THEN** two leaderboard entries are written: one with `@ns3-v24`, one with `@ns3-v47`
- **THEN** `make validate` exits non-zero if either run fails

#### Scenario: partial install graceful failure
- **WHEN** `make validate` is run but `~/ns-3-dev-v47` is not installed
- **THEN** the v4.2 run is skipped with a clear warning; exit code is 0 (not hard fail)

### Requirement: ui-variant-filter
The `/api/leaderboard` endpoint accepts a `variant` query parameter for
client-side filtering. The web UI exposes a dropdown to select the active filter.

#### Scenario: API filtering by variant substring
- **WHEN** `GET /api/leaderboard?variant=ns3-v24`
- **THEN** only entries whose `variant_id` contains `ns3-v24` are returned

#### Scenario: API returns all entries by default
- **WHEN** `GET /api/leaderboard` (no `variant` param) or `?variant=all`
- **THEN** all entries are returned (existing behaviour)

#### Scenario: UI dropdown reflects available variants
- **WHEN** the leaderboard contains entries with `@ns3-v24` and `@ns3-v47` tags
- **THEN** the frontend `<select>` shows options: "All versions", "ns3-v24", "ns3-v47"
- **WHEN** a variant is selected
- **THEN** the table and chart update to show only that variant's entries
