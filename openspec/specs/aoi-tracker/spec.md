## ADDED Requirements

### Requirement: Per-flow AoI tracking with generation-time stamping
The system SHALL implement `AoITracker` in `cornet/middleware/aoi.py`. A flow SHALL be identified by a `(src_ip: str, dst_ip: str)` tuple. For each update, the tracker SHALL record `generation_time` (when the packet was generated at the source, from the physics clock) and `receive_time` (when it was delivered by PacketDispatcher). AoI at receive time SHALL be computed as `receive_time - generation_time`.

#### Scenario: AoI computed on packet delivery
- **WHEN** a packet from `192.168.1.1` to `192.168.1.2` was generated at physics_time=1.0 and delivered at physics_time=1.050
- **THEN** `tracker.update(("192.168.1.1","192.168.1.2"), gen_time=1.0, recv_time=1.050)` SHALL record AoI = 0.050 seconds for that flow

#### Scenario: Multiple flows tracked independently
- **WHEN** two flows `(A→B)` and `(A→C)` both receive updates
- **THEN** `tracker.get_flow_stats("A","B")` SHALL return statistics only for the A→B flow
- **THEN** `tracker.get_flow_stats("A","C")` SHALL return statistics only for the A→C flow

### Requirement: CSV trace output per flow
The tracker SHALL write one CSV row per update to a per-flow trace file at `<output_dir>/aoi_<src>_<dst>.csv`. Columns SHALL be: `physics_time`, `generation_time`, `receive_time`, `aoi_s`. The CSV SHALL be flushed after each row so partial traces are readable if the experiment is interrupted.

#### Scenario: Trace file created and populated
- **WHEN** `tracker.open(output_dir)` is called and two updates are recorded for flow (A→B)
- **THEN** a file `aoi_A_B.csv` SHALL exist in `output_dir`
- **THEN** it SHALL contain a header row plus one data row per update
- **THEN** each row's `aoi_s` SHALL equal `receive_time - generation_time`

#### Scenario: Interrupted experiment produces partial trace
- **WHEN** the experiment is stopped before `tracker.close()` is called
- **THEN** all previously flushed rows SHALL be present in the CSV file
- **THEN** the CSV SHALL be parseable (no partial rows)

### Requirement: Per-flow summary statistics (stdlib only)
After `tracker.close()`, `tracker.summary()` SHALL return a dict keyed by `(src_ip, dst_ip)` tuples. Each value SHALL contain: `count`, `mean_s`, `std_s`, `p50_s`, `p95_s`, `p99_s` computed using Python's `statistics` module and linear-interpolation percentiles. No `numpy` dependency SHALL be required.

#### Scenario: Summary statistics computed correctly
- **WHEN** 100 AoI samples are recorded for a flow
- **THEN** `summary[(src,dst)]["mean_s"]` SHALL equal the arithmetic mean of all AoI values
- **THEN** `summary[(src,dst)]["p95_s"]` SHALL equal the 95th percentile via linear interpolation
- **THEN** `summary[(src,dst)]["count"]` SHALL equal 100

#### Scenario: Empty flow returns zero stats
- **WHEN** no updates have been recorded for a flow
- **THEN** `get_flow_stats(src, dst)` SHALL return `None`
- **THEN** `summary` SHALL NOT contain an entry for that flow

### Requirement: JSON summary export
`tracker.export_json(output_dir)` SHALL write `aoi_summary.json` to `output_dir` containing the full summary dict with flow tuples serialized as `"src_ip:dst_ip"` string keys.

#### Scenario: JSON summary file created
- **WHEN** `tracker.export_json(output_dir)` is called after an experiment with 2 flows
- **THEN** `aoi_summary.json` SHALL exist and be valid JSON
- **THEN** it SHALL contain entries for each observed flow
- **THEN** each entry SHALL include `count`, `mean_s`, `p50_s`, `p95_s`, `p99_s`
