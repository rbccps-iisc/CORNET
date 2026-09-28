from __future__ import annotations

from cornet.bench.grids import expand_suite, format_dry_run
from cornet.bench.report import classify_rows
from cornet.bench.worlds import generate_world, resolve_world
from cornet.plugins.network.ns3_plugin import script_supports_timing


def test_quick_grid_skips_one_factor_sweeps() -> None:
    quick = expand_suite("ns3", quick=True)
    full = expand_suite("ns3", quick=False)
    assert len(quick) < len(full)
    assert all(run["suite"] == "ns3" for run in quick)
    ids = {run["id"] for run in quick}
    assert "baseline" in ids
    assert "single_cell_pendulum" in ids
    pendulum = next(run for run in quick if run["id"] == "single_cell_pendulum")
    assert pendulum["sectors"] == 1
    assert pendulum["ues_per_cell"] == 1
    assert any(item.startswith("fact-") for item in ids)
    assert not any(item.startswith("sweep-") for item in ids)


def test_dry_run_text_lists_count() -> None:
    runs = expand_suite("ns3", quick=True)
    text = format_dry_run(runs)
    assert text.startswith(f"planned runs: {len(runs)}")
    assert "suite=ns3" in text


def test_combined_quick_is_first_scenario_only() -> None:
    runs = expand_suite("combined", quick=True)
    names = {run["name"] for run in runs}
    assert names == {"single_cell_pendulum"}


def test_gazebo_limited_classification() -> None:
    rows = [
        {
            "suite": "ns3",
            "mode": "speed",
            "config_id": "speed",
            "sites": "1",
            "sectors": "1",
            "ues_per_cell": "1",
            "traffic": "periodic",
            "channel_update_ms": "100",
            "numerology": "1",
            "wraparound": "False",
            "scheduler": "rr",
            "speed_factor": "2.0",
            "error": "",
        },
        {
            "suite": "combined",
            "mode": "combined",
            "config_id": "single_cell_pendulum",
            "sites": "1",
            "sectors": "1",
            "ues_per_cell": "1",
            "traffic": "periodic",
            "channel_update_ms": "100",
            "numerology": "1",
            "wraparound": "False",
            "scheduler": "rr",
            "lag_p99": "0.3",
            "rtf_p5": "0.7",
            "tap": "False",
            "tap_status": "",
            "error": "",
        },
    ]
    reports = classify_rows(rows)
    assert reports[0]["classification"] == "gazebo-limited"
    assert "NS-3-follows-Gazebo" in reports[0]["recommendation"]


def test_incomplete_without_standalone_speed() -> None:
    rows = [
        {
            "suite": "combined",
            "mode": "combined",
            "config_id": "only-combined",
            "sites": "7",
            "sectors": "3",
            "ues_per_cell": "10",
            "traffic": "periodic",
            "channel_update_ms": "100",
            "numerology": "1",
            "wraparound": "False",
            "scheduler": "rr",
            "lag_p99": "0.2",
            "rtf_p5": "0.99",
            "tap": "False",
            "tap_status": "",
            "error": "",
        }
    ]
    assert classify_rows(rows)[0]["classification"] == "incomplete"


def test_tap_row_preferred() -> None:
    common = {
        "suite": "combined",
        "mode": "combined",
        "config_id": "cell",
        "sites": "1",
        "sectors": "1",
        "ues_per_cell": "1",
        "traffic": "periodic",
        "channel_update_ms": "100",
        "numerology": "1",
        "wraparound": "False",
        "scheduler": "rr",
        "error": "",
    }
    rows = [
        {
            "suite": "ns3",
            "mode": "speed",
            "config_id": "s",
            "speed_factor": "3",
            "error": "",
            **{k: common[k] for k in (
                "sites", "sectors", "ues_per_cell", "traffic",
                "channel_update_ms", "numerology", "wraparound", "scheduler",
            )},
        },
        {**common, "tap": "False", "tap_status": "", "lag_p99": "0.1", "rtf_p5": "0.5"},
        {**common, "tap": "True", "tap_status": "tun-setup", "lag_p99": "0.2", "rtf_p5": "0.99"},
    ]
    report = classify_rows(rows)[0]
    assert report["tap_label"] == "tap"
    assert report["classification"] == "realtime-ok"


def test_dry_run_does_not_start_simulators(capsys, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("simulator started")

    monkeypatch.setattr("cornet.bench.runner.run_ns3_suite", boom)
    from cornet.bench.runner import execute

    execute("ns3", quick=True, dry_run=True)
    assert "planned runs:" in capsys.readouterr().out


def test_missing_world_and_generation(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CORNET_SMALL_WAREHOUSE", str(tmp_path / "nope"))
    monkeypatch.delenv("CORNET_LARGE_WAREHOUSE", raising=False)
    # Known local paths may exist on this machine; generation of empty always works.
    world = generate_world(
        tmp_path / "empty.sdf",
        world="empty",
        robots=2,
        actors=1,
        camera=True,
        step_ms=2,
        update_rate=0,
    )
    assert world is not None
    text = world.read_text()
    assert "turtlebot3_waffle" in text
    assert "walker0" in text
    assert "<real_time_update_rate>0</real_time_update_rate>" in text
    assert "<max_step_size>0.002</max_step_size>" in text
    assert resolve_world("empty") is None
    monkeypatch.setattr("cornet.bench.worlds._known_worlds", lambda: {"small": [], "large": []})
    monkeypatch.setattr("cornet.bench.worlds._catalog_worlds", lambda: {"small": [], "large": []})
    assert resolve_world("small") is None


def test_gz_stats_duration_is_integer(monkeypatch, tmp_path) -> None:
    from cornet.bench.runner import _gz_factors

    seen: list[list[str]] = []

    class _Proc:
        def poll(self) -> int:
            return 0

        def terminate(self) -> None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            return 0

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))

        class _Result:
            stdout = "1.00, 1, 1, F\n"
            returncode = 0

        return _Result()

    monkeypatch.setattr("cornet.bench.runner.subprocess.Popen", lambda *a, **k: _Proc())
    monkeypatch.setattr("cornet.bench.runner.subprocess.run", fake_run)
    monkeypatch.setattr("cornet.bench.runner.time.sleep", lambda _s: None)
    world = generate_world(
        tmp_path / "empty.sdf",
        world="empty",
        robots=0,
        actors=0,
        camera=False,
        step_ms=1,
        update_rate=1000,
    )
    assert world is not None
    assert _gz_factors(world, 8.0, "") == [1.0]
    flag = seen[0][seen[0].index("-d") + 1]
    assert flag == "8"


def test_bundled_timing_scripts() -> None:
    assert script_supports_timing("remote_robot_control-default")
    assert script_supports_timing("/tmp/bench_nr_multicell-default.cc")
    assert not script_supports_timing("my_custom_scenario")
