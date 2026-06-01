## ADDED Requirements

### Requirement: Leaderboard JSON written per task
The framework SHALL maintain an append-only `tasks/<name>/leaderboard.json` file. Every completed experiment run (single or sweep variant) SHALL append one entry. The file SHALL be valid JSON at all times; partial writes SHALL NOT corrupt it.

#### Scenario: Entry appended after each run
- **WHEN** a run completes and `collect()` finishes
- **THEN** an entry SHALL be appended to `tasks/<name>/leaderboard.json` with fields: `timestamp` (ISO 8601), `variant_id`, `status` (`SUCCESS` or `FAILURE`), `metric` (float or null), `output_dir` (relative path)

#### Scenario: Leaderboard file created on first run
- **WHEN** `leaderboard.json` does not exist and the first run completes
- **THEN** the file SHALL be created with a JSON array containing one entry

#### Scenario: Corrupt leaderboard file is backed up and reset
- **WHEN** `leaderboard.json` exists but is not valid JSON (e.g. partial write from a crash)
- **THEN** the orchestrator SHALL rename it to `leaderboard.json.bak.<timestamp>` and create a fresh empty `leaderboard.json` before writing the new entry

### Requirement: Terminal leaderboard view command
The command `python -m framework view tasks/<name>` SHALL print a sorted leaderboard table to stdout using the `rich` library. Rows SHALL be sorted by `metric` ascending (or descending if `higher_is_better: true`). FAILURE rows SHALL appear at the bottom.

#### Scenario: Leaderboard sorted by metric
- **WHEN** three runs have metrics `12.5`, `8.3`, `15.1` and `higher_is_better: false`
- **THEN** the table SHALL display rows in order: `8.3`, `12.5`, `15.1`
- **THEN** the best row SHALL be highlighted (e.g. bold or green)

#### Scenario: Leaderboard shows sweep variants
- **WHEN** a 6-variant sweep has all completed
- **THEN** each variant SHALL appear as a separate row with its `variant_id` in the first column

#### Scenario: Leaderboard view with no entries
- **WHEN** `leaderboard.json` is empty or does not exist
- **THEN** the command SHALL print `"No runs recorded yet for task <name>."` and exit 0

#### Scenario: Leaderboard supersedes compare scripts
- **WHEN** a researcher wants to compare AoI scheduler phases
- **THEN** running `python -m framework view tasks/aoi_5phase_eval` SHALL display all 5 phase results in one table
- **THEN** no separate `compare_aoi_phases.py` script SHALL need to be invoked
