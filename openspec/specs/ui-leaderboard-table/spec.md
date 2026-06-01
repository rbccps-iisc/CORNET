## ADDED Requirements

### Requirement: Leaderboard table displays all run entries
The frontend SHALL render an HTML table showing all entries from `/api/leaderboard`, with one row per entry and columns: select (checkbox), variant_id, status, metric value, timestamp, and output directory.

#### Scenario: Leaderboard has entries
- **WHEN** the page loads and `/api/leaderboard` returns one or more entries
- **THEN** the table renders a row for each entry with all columns populated

#### Scenario: Leaderboard is empty
- **WHEN** the page loads and `/api/leaderboard` returns `[]`
- **THEN** the table renders a single row with the message "No runs yet."

### Requirement: Status column is colour-coded
The table's status column SHALL render each status value in a visually distinct style: SUCCESS entries in green, FAILURE entries in red, RUNNING entries in amber.

#### Scenario: Row with SUCCESS status
- **WHEN** an entry has `status == "SUCCESS"`
- **THEN** the status cell renders the text "SUCCESS" with a green background or text colour

#### Scenario: Row with FAILURE status
- **WHEN** an entry has `status == "FAILURE"`
- **THEN** the status cell renders the text "FAILURE" with a red background or text colour

### Requirement: Rows can be selected/deselected to filter the plotter
Each table row SHALL have a checkbox in the select column. Checking or unchecking a row SHALL immediately update the Plotly chart to include or exclude that run's data point.

#### Scenario: User deselects a run
- **WHEN** the user unchecks the checkbox for a row
- **THEN** that run's data point is removed from the Plotly chart without a page reload

#### Scenario: User reselects a run
- **WHEN** the user checks the checkbox for a previously deselected row
- **THEN** that run's data point is restored in the Plotly chart

### Requirement: FAILURE rows display a failure badge linking to the failure panel
Each FAILURE row SHALL display a `[!]` badge that, when clicked, scrolls the page to the failure inspector panel and highlights the corresponding failure entry.

#### Scenario: User clicks the failure badge on a FAILURE row
- **WHEN** the user clicks the `[!]` badge on a row with `status == "FAILURE"`
- **THEN** the page scrolls to the failure inspector panel and the matching entry is highlighted
