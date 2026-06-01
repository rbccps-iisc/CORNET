## ADDED Requirements

### Requirement: X-axis dropdown is populated from parsed variant_id keys
The frontend SHALL parse all `variant_id` values from `/api/leaderboard`, extract the parameter key names (by splitting each `variant_id` on `_` then on `=` to get `{key: val}` pairs), and populate an x-axis dropdown with the union of all keys found.

#### Scenario: Leaderboard has variant entries with parameter keys
- **WHEN** the page loads and entries include `variant_id` values such as `"numerology=1_bandwidth=20"`
- **THEN** the x-axis dropdown contains the options `numerology` and `bandwidth`

#### Scenario: Leaderboard has only one unique parameter key
- **WHEN** all entries share only one parameter key
- **THEN** the x-axis dropdown is pre-selected on that key and the chart renders immediately

### Requirement: Chart plots selected runs as x=axis-value, y=primary_metric
The Plotly chart SHALL plot each selected run as a scatter point where the x-coordinate is the value of the chosen x-axis parameter (parsed from `variant_id`) and the y-coordinate is the `metric` field of the leaderboard entry. The chart title SHALL include the `primary_metric` name.

#### Scenario: User selects an x-axis parameter
- **WHEN** the user selects `bandwidth` from the x-axis dropdown and runs are selected in the table
- **THEN** the Plotly chart renders with x = bandwidth values and y = metric values for the selected runs

#### Scenario: Selected run's variant_id does not contain the chosen x-axis key
- **WHEN** a selected run's `variant_id` does not include the current x-axis key
- **THEN** that run is omitted from the chart (no error is thrown)

### Requirement: FAILURE variants appear as gaps in the chart
Runs with `status == "FAILURE"` SHALL be excluded from the Plotly data series. `connectgaps` SHALL be `false` so that missing x-values appear as visual gaps rather than connected lines.

#### Scenario: Some runs have FAILURE status
- **WHEN** some entries in the leaderboard have `status == "FAILURE"`
- **THEN** those entries have no data point in the Plotly chart and the line has a gap at their x position

### Requirement: Repeat runs are grouped and annotated with a mean marker
Runs whose `variant_id` values differ only by a `_run<N>` suffix (where N is a positive integer) SHALL be treated as repeats of the same parameter combination. Individual repeat scatter points SHALL be plotted, and a larger mean marker at the same x-value SHALL be overlaid.

#### Scenario: Multiple runs with the same parameter combo and different run indices
- **WHEN** the leaderboard contains `bandwidth=20_run1` and `bandwidth=20_run2` both with SUCCESS status
- **THEN** two scatter points appear at x=20, and a distinct mean marker appears at x=20 at y=mean(metric values)

### Requirement: Hover tooltips show variant_id and metric value
Each scatter point SHALL have a Plotly hover tooltip displaying the full `variant_id` string and the `metric` value.

#### Scenario: User hovers over a data point
- **WHEN** the user hovers the mouse over a scatter point in the chart
- **THEN** the tooltip displays the `variant_id` and formatted `metric` value
