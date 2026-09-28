from __future__ import annotations

import json
import os
import textwrap
import threading
from pathlib import Path

import yaml

from cornet.research.agents import FORBIDDEN_TOOLS, local_options, send_with_retry, tool_allowlist
from cornet.research.brief import load_brief
from cornet.research.critic import caveats_for, deterministic_checks, guard_metric_flags, parse_challenge_report
from cornet.research.gitwork import foreign_changes, revert_paths
from cornet.research.harness import run_session
from cornet.research.jobs import JobQueue, _subprocess_executor
from cornet.research.session import new_session, privilege_error
from cornet.research.stats import compare_samples
from cornet.research.tools import TOOL_NAMES, ToolContext, build_tools


class Scripted:
    def __init__(self, replies: list[str], agent_id: str = "scripted") -> None:
        self.replies = list(replies)
        self.agent_id = agent_id

    def send(self, _prompt: str) -> str:
        return self.replies.pop(0)


def _task(tmp_path: Path, name: str = "pendulum_nr_control") -> Path:
    task = tmp_path / "tasks" / name
    task.mkdir(parents=True)
    (task / "config.yaml").write_text(
        """
_schema: unified-v1
network:
  plugin: ns3
  type: ns3
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: pendulum_nr_control
  duration: 1.0
  output_dir: results
  primary_metric: mean_aoi_ms
  seed: 1
""".strip()
    )
    eval_dir = task / "eval"
    eval_dir.mkdir()
    (eval_dir / "eval_tool.py").write_text("class EvalTool:\n    pass\n")
    return task


def _brief_text() -> str:
    return textwrap.dedent(
        """
        question: Does edf lower AoI versus pf?
        hypotheses:
          - id: h1
            claim: edf lowers AoI
            prediction: edf mean is lower
            falsification: a significant difference in the other direction
            expect: a_lower
        independent_variables:
          - path: network.schedulerType
            values: [edf, pf]
        dependent_variables: [mean_aoi_ms]
        controls: [single cell]
        standard: true
        lane: v2.4-ns3.38
        repeats: 5
        decisions:
          - name: scheduler
            status: derived
            justification: the question compares schedulers
        """
    ).strip()


def test_brief_rejects_missing_falsification_and_isd() -> None:
    try:
        load_brief("question: q\nhypotheses:\n  - id: h\n    claim: c\n    prediction: p\n")
    except ValueError as exc:
        assert "h" in str(exc)
    else:
        raise AssertionError("expected missing falsification")
    try:
        load_brief(
            "question: q\nhypotheses:\n  - id: h\n    claim: c\n    prediction: p\n    falsification: f\n"
            "independent_variables:\n  - path: network.radio_sites.isd_m\n    values: [100]\n"
        )
    except ValueError as exc:
        assert "ISD" in str(exc)
    else:
        raise AssertionError("expected ISD rejection")


def test_compare_inconclusive_and_supported() -> None:
    quiet = compare_samples([1, 2, 3, 4, 5], [1.2, 2.1, 2.8, 4.1, 4.9], expect="different")
    assert quiet["verdict"] == "inconclusive"
    loud = compare_samples([1, 1, 1, 1, 1], [5, 5, 5, 5, 5], expect="a_lower")
    assert loud["verdict"] == "supported"
    assert loud["test"] in {"welch", "mannwhitney"}
    assert "effect_size" in loud and "ci95" in loud


def test_tool_registration_override_freeze_and_queue(tmp_path: Path) -> None:
    task = _task(tmp_path)
    session = new_session(task, "q")
    session.eval_hash = "frozen"
    (task / "research" / "brief.yaml").write_text(_brief_text())
    jobs = JobQueue(lambda *_args: {"variant_id": "edf", "seed": 1})
    tools = build_tools(ToolContext(session, jobs, tmp_path))
    assert set(tools) == set(TOOL_NAMES)
    queued = tools["ask_user"].execute({"prompt": "Which scheduler?", "options": ["edf", "pf"]})
    assert queued == "question queued; end your turn"
    assert session.questions[0]["answer"] is None
    denied = tools["submit_experiment"].execute({"overrides": {"robot.count": 2}})
    assert "robot.count" in denied["error"]
    frozen = tools["submit_experiment"].execute({"overrides": {"network.schedulerType": "edf"}})
    assert frozen["error"] == "evaluation is frozen"
    rejected = tools["record_hypothesis"].execute(
        {
            "status": "supported",
            "hypothesis": {
                "id": "h1",
                "claim": "c",
                "prediction": "p",
                "falsification": "f",
            },
        }
    )
    assert "compare" in rejected["error"]


def test_jobs_queue_and_survive_crashes(tmp_path: Path) -> None:
    task = _task(tmp_path)
    gate = threading.Event()
    seen: list[str] = []

    def executor(task_dir, overrides, seed, hypothesis_id):
        seen.append(f"{seed}")
        if seed == 1:
            gate.wait(2)
        if seed == 3:
            raise RuntimeError("preflight failed")
        return {"variant_id": f"v{seed}", "seed": seed}

    jobs = JobQueue(executor)
    first = jobs.submit(task, {}, 1, 1)
    second = jobs.submit(task, {}, 1, 2)
    assert jobs.status(second.job_id).status == "queued"
    gate.set()
    assert jobs.wait(first.job_id).status == "finished"
    assert jobs.wait(second.job_id).status == "finished"
    crashed = jobs.submit(task, {}, 1, 3)
    assert jobs.wait(crashed.job_id).status == "failed"
    assert "preflight" in crashed.error


def test_executor_passes_seed_and_overrides(monkeypatch, tmp_path: Path) -> None:
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen["env"] = kwargs["env"]
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("cornet.research.jobs.subprocess.run", fake_run)
    task = tmp_path / "tasks" / "pendulum_nr_control"
    task.mkdir(parents=True)
    _subprocess_executor(task, {"network.schedulerType": "edf"}, 4, "h1")
    assert seen["env"]["CORNET_EXPERIMENT_SEED"] == "4"
    assert seen["env"]["CORNET_HYPOTHESIS_ID"] == "h1"
    assert json.loads(seen["env"]["CORNET_OVERRIDES"]) == {"network.schedulerType": "edf"}


def test_failed_trial_does_not_spend_the_budget(tmp_path: Path) -> None:
    task = _task(tmp_path)

    def executor(*_args):
        raise RuntimeError("ros2 launch exited early")

    session = run_session(
        task,
        "Does edf lower AoI?",
        researcher=Scripted([_brief_text(), '{"hypothesis_id": "h1", "repeats": 1, "groups": [{"name": "edf", "overrides": {"network.schedulerType": "edf"}, "seed": 1}]}', "The launch failed."]),
        critic=Scripted(["### Challenge 1: none\n- **severity**: minor\nNo blocking issue.\n"]),
        executor=executor,
        repo=tmp_path,
        input_fn=lambda _prompt="": "",
        output_fn=lambda *_a, **_k: None,
    )
    assert session.phase == "done"
    assert session.consumed["trials"] == 0
    assert session.consumed.get("sim_seconds", 0) == 0


def test_leaderboard_summary_is_not_a_dump(tmp_path: Path) -> None:
    task = _task(tmp_path)
    rows = [
        {"variant_id": f"v{i}", "metric": float(i), "hypothesis_id": "h1", "seed": i}
        for i in range(300)
    ]
    (task / "leaderboard.json").write_text(json.dumps(rows))
    session = new_session(task, "q")
    tools = build_tools(ToolContext(session, JobQueue(lambda *_a: {}), tmp_path))
    summary = tools["leaderboard_summary"].execute({})
    assert summary["count"] == 300
    assert len(summary["top"]) == 5
    assert summary["by_hypothesis"]["h1"]["n"] == 300


def test_mininet_without_root_is_reported(tmp_path: Path) -> None:
    if os.geteuid() == 0:
        return
    task = tmp_path / "uav"
    task.mkdir()
    (task / "config.yaml").write_text(
        """
_schema: unified-v1
network:
  plugin: mininet
  type: mininet
  nodes: []
robot:
  plugin: gazebo
  robots: []
experiment:
  name: uav
  duration: 1.0
  output_dir: results
""".strip()
    )
    assert "root is required" in (privilege_error(task) or "")


def test_deterministic_rules_and_caveats() -> None:
    brief = load_brief(_brief_text())
    blocked = deterministic_checks(
        brief,
        [{"network.radio_sites.deployment": "3gpp_umi", "population.count": 4}],
    )
    assert any("confounding" in item["detail"] or item["title"] == "confounding" for item in blocked)
    indoor = load_brief(
        _brief_text()
        + "\nscenario:\n  robot: turtlebot3\n  world: warehouse_small\n  network: nr\n"
        + "  radio_sites:\n    deployment: 3gpp_inh_office\n    robot_anchor: edge\n    wraparound: false\n"
    )
    indoor.lane = "no-such-lane"
    problems = deterministic_checks(indoor)
    assert any("wrap-around" in item["title"] for item in problems)
    labels = caveats_for(
        {"variant_id": "r", "standard": False, "rtf_mean": 0.4, "timing_ok": False, "caveat": "aerial path loss only"},
        scenario={"world": "warehouse_small", "radio_sites": {"deployment": "3gpp_inh_office"}},
    )
    assert "InH approximation" in labels
    assert "slowed co-simulation (rtf < 1)" in labels
    assert "timing assumption violated" in labels
    assert "aerial path loss only" in labels
    flags = guard_metric_flags(brief, primary_delta=-1.0, guards={"delivery": -0.2})
    brief.guard_metrics = []  # type: ignore[attr-defined]
    from cornet.research.brief import GuardMetric

    brief.guard_metrics = [GuardMetric(name="delivery", tolerance=0.05, higher_is_better=True)]
    flags = guard_metric_flags(brief, primary_delta=-1.0, guards={"delivery": -0.2})
    assert flags and flags[0]["severity"] == "major"
    parsed = parse_challenge_report("### Challenge 1: lane\n- **severity**: blocking\n")
    assert parsed[0]["severity"] == "blocking"


def test_agent_tools_exclude_shell_edit_and_task(tmp_path: Path) -> None:
    task = _task(tmp_path)
    session = new_session(task, "q")
    tools = build_tools(ToolContext(session, JobQueue(lambda *_a: {}), tmp_path))
    options = local_options(task, tools, allow_web_search=True)
    assert "cloud" not in options
    assert FORBIDDEN_TOOLS.isdisjoint(options["tools"])
    assert options["tools"] == ["mcp", "webSearch"]
    assert tool_allowlist(allow_web_search=False) == ["mcp"]
    assert options["local"]["setting_sources"] == []


def test_retry_waits_on_retryable_startup(monkeypatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("cornet.research.agents.time.sleep", lambda seconds: slept.append(seconds))

    class CursorAgentError(Exception):
        def __init__(self) -> None:
            self.is_retryable = True
            self.retry_after = "0"

    class Agent:
        agent_id = "agent-1"

        def __init__(self) -> None:
            self.calls = 0

        def send(self, _prompt: str):
            self.calls += 1
            if self.calls == 1:
                raise CursorAgentError()
            return "ok"

    logged: list[tuple] = []
    result = send_with_retry(Agent(), "go", lambda agent_id, run_id: logged.append((agent_id, run_id)))
    assert result == "ok"
    assert slept == [0.0]
    assert logged[0][0] == "agent-1"


def test_allowlist_reverts_config_edits(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    task = repo / "tasks" / "demo"
    task.mkdir(parents=True)
    (task / "config.yaml").write_text("seed: 1\n")
    (task / "research").mkdir()
    (task / "research" / "journal.md").write_text("note\n")
    import subprocess

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (task / "config.yaml").write_text("seed: 2\n")
    bad = foreign_changes(repo, "tasks/demo")
    assert any(path.endswith("config.yaml") for path in bad)
    revert_paths(repo, bad)
    assert (task / "config.yaml").read_text() == "seed: 1\n"


def test_end_to_end_pendulum_session(tmp_path: Path) -> None:
    task = _task(tmp_path, "pendulum_nr_control")
    batch = json.dumps(
        {
            "hypothesis_id": "h1",
            "repeats": 5,
            "groups": [
                {"name": "edf", "overrides": {"network.schedulerType": "edf"}, "seed": 1},
                {"name": "pf", "overrides": {"network.schedulerType": "pf"}, "seed": 11},
            ],
        }
    )

    def executor(task_dir: Path, overrides: dict, seed: int, hypothesis_id: str | None) -> dict:
        from cornet.leaderboard.writer import append_entry

        value = next(iter(overrides.values()))
        metric = 1.0 if value == "edf" else 5.0
        variant = f"{value}_run{seed}"
        append_entry(
            str(task_dir),
            {
                "variant_id": variant,
                "status": "SUCCESS",
                "metric": metric,
                "seed": seed,
                "hypothesis_id": hypothesis_id,
                "primary_metric": "mean_aoi_ms",
                "config_hash": "abc",
                "output_dir": "results",
                "timestamp": "t",
            },
        )
        return {"variant_id": variant, "seed": seed}

    researcher = Scripted([_brief_text(), batch, "edf is lower in this sample."])
    critic = Scripted(["### Challenge 1: none\n- **severity**: minor\nNo blocking issue.\n"])
    session = run_session(
        task,
        "Does edf lower AoI versus pf for a remote pendulum?",
        researcher=researcher,
        critic=critic,
        executor=executor,
        repo=tmp_path,
        input_fn=lambda _prompt="": "",
        output_fn=lambda *_a, **_k: None,
    )
    assert session.phase == "done"
    report = (task / "research" / "report.md").read_text()
    assert "Verdict: supported" in report
    assert "edf is lower" in report
    assert "config_hash=abc" in report
    data = yaml.safe_load((task / "research" / "session.json").read_text())
    assert data["phase"] == "done"


def _run_scripted(tmp_path: Path, task: Path, question: str, brief: str):
    batch = json.dumps(
        {
            "hypothesis_id": "h1",
            "repeats": 5,
            "groups": [
                {"name": "edf", "overrides": {"network.schedulerType": "edf"}, "seed": 1},
                {"name": "pf", "overrides": {"network.schedulerType": "pf"}, "seed": 11},
            ],
        }
    )

    def executor(task_dir: Path, overrides: dict, seed: int, hypothesis_id: str | None) -> dict:
        from cornet.leaderboard.writer import append_entry

        value = next(iter(overrides.values()))
        metric = 1.0 if value == "edf" else 5.0
        variant = f"{value}_run{seed}"
        append_entry(
            str(task_dir),
            {
                "variant_id": variant,
                "status": "SUCCESS",
                "metric": metric,
                "seed": seed,
                "hypothesis_id": hypothesis_id,
                "primary_metric": "mean_aoi_ms",
                "config_hash": "abc",
                "output_dir": "results",
                "timestamp": "t",
            },
        )
        return {"variant_id": variant, "seed": seed}

    return run_session(
        task,
        question,
        researcher=Scripted([brief, batch, "The lower scheduler won in this sample."]),
        critic=Scripted(["### Challenge 1: none\n- **severity**: minor\nNo blocking issue.\n"]),
        executor=executor,
        repo=tmp_path,
        input_fn=lambda _prompt="": "",
        output_fn=lambda *_a, **_k: None,
    )


def test_end_to_end_aoi_and_turtlebot(tmp_path: Path) -> None:
    aoi = _task(tmp_path, "aoi_5phase_eval")
    aoi_session = _run_scripted(tmp_path, aoi, "Which scheduler lowers AoI?", _brief_text())
    assert aoi_session.phase == "done"
    assert (aoi / "research" / "report.md").is_file()

    holder = _task(tmp_path, "holder")
    brief = _brief_text() + textwrap.dedent(
        """
        scenario:
          id: tb_warehouse
          robot: turtlebot3
          world: warehouse_small
          network: wifi_ns3
          radio_sites:
            deployment: single_cell
        """
    )
    session = _run_scripted(
        tmp_path,
        holder,
        "How does WiFi serve a TurtleBot in a small warehouse?",
        brief,
    )
    assert session.phase == "done"
    assert (tmp_path / "tasks" / "tb_warehouse" / "config.yaml").is_file()
    assert (tmp_path / "tasks" / "tb_warehouse" / "research" / "report.md").is_file()


def test_aoi_eval_tool_scores_mean(tmp_path: Path) -> None:
    import importlib.util

    stats = tmp_path / "analysis"
    stats.mkdir()
    (stats / "aoi_statistics.json").write_text(json.dumps({"flow": {"mean": 12.5}}))
    path = Path("tasks/aoi_5phase_eval/eval/eval_tool.py")
    spec = importlib.util.spec_from_file_location("aoi_eval", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.EvalTool().run_evaluation(str(tmp_path)).startswith("SUCCESS, 12.5")
