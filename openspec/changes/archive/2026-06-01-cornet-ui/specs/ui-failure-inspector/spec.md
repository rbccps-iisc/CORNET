## ADDED Requirements

### Requirement: Failure inspector lists all FAILURE runs with error details
The frontend SHALL render a "Failures" section below the chart that lists every leaderboard entry with `status == "FAILURE"`. Each entry SHALL display the `variant_id`, the `error` field value, and a link to the `output_dir`.

#### Scenario: There are FAILURE entries in the leaderboard
- **WHEN** the leaderboard contains one or more entries with `status == "FAILURE"`
- **THEN** the failure inspector section renders one block per failure with `variant_id`, `error` message, and `output_dir` path

#### Scenario: There are no FAILURE entries
- **WHEN** no leaderboard entries have `status == "FAILURE"`
- **THEN** the failure inspector section renders a message "No failures." and no failure blocks

### Requirement: Failure entries with no error field display a placeholder
If a FAILURE entry's `error` field is absent or null, the inspector SHALL display "(no error message recorded)" in place of the error text.

#### Scenario: FAILURE entry has no error field
- **WHEN** a leaderboard entry has `status == "FAILURE"` and `error` is null or absent
- **THEN** the inspector renders "(no error message recorded)" for that entry's error line

### Requirement: Failure panel is linked from the FAILURE table row badge
The failure inspector section SHALL have an HTML anchor (`id="failures-panel"`) so that clicking the `[!]` badge in the leaderboard table scrolls to it.

#### Scenario: Failure inspector anchor is present
- **WHEN** the page is rendered and any FAILURE entries exist
- **THEN** the failures section container has `id="failures-panel"` in the HTML

### Requirement: Auto-refresh updates the failure inspector
The failure inspector SHALL be re-rendered whenever the leaderboard data is refreshed (on mtime change from `/api/status` polling). The re-rendered list SHALL reflect the current state of `leaderboard.json`.

#### Scenario: A new failure appears during auto-refresh
- **WHEN** the auto-refresh cycle detects an mtime change and the new leaderboard data includes a new FAILURE entry
- **THEN** the failure inspector adds a new block for the new failure without a page reload
