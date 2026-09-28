"""Expand benchmark YAML into concrete runs."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import yaml

_REPO = Path(__file__).resolve().parents[2]
_SUITES = {
    "ns3": _REPO / "benchmarks" / "ns3.yaml",
    "gazebo": _REPO / "benchmarks" / "gazebo.yaml",
    "combined": _REPO / "benchmarks" / "combined.yaml",
}


def suite_path(name: str) -> Path:
    if name not in _SUITES:
        raise ValueError(f"unknown suite {name!r}; expected ns3, gazebo, combined or all")
    return _SUITES[name]


def load_suite(name: str) -> dict[str, Any]:
    path = suite_path(name)
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a mapping")
    return data


def _dedupe(configs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for cfg in configs:
        key = tuple(sorted((k, repr(v)) for k, v in cfg.items() if k != "id"))
        if key in seen:
            continue
        seen.add(key)
        out.append(cfg)
    return out


def expand_factor_grid(doc: dict[str, Any], *, quick: bool) -> list[dict[str, Any]]:
    """Baseline, optional one-factor sweeps, and the factorial core."""
    baseline = dict(doc["baseline"])
    baseline["id"] = "baseline"
    configs = [baseline]
    if not quick:
        for key, values in (doc.get("sweeps") or {}).items():
            for value in values:
                cfg = dict(doc["baseline"])
                cfg[key] = value
                cfg["id"] = f"sweep-{key}-{value}"
                configs.append(cfg)
    for extra in doc.get("include") or []:
        cfg = dict(doc["baseline"])
        cfg.update(extra)
        cfg.setdefault("id", "include")
        configs.append(cfg)
    factorial = doc.get("factorial") or {}
    if factorial:
        keys = list(factorial)
        for combo in itertools.product(*(factorial[k] for k in keys)):
            cfg = dict(doc["baseline"])
            for key, value in zip(keys, combo):
                cfg[key] = value
            cfg["id"] = "fact-" + "-".join(f"{k}={v}" for k, v in zip(keys, combo))
            configs.append(cfg)
    configs = _dedupe(configs)
    repeats = int(doc.get("repeats", 3))
    runs: list[dict[str, Any]] = []
    for cfg in configs:
        for repeat in range(repeats):
            run = dict(cfg)
            run["repeat"] = repeat
            run["seed"] = repeat + 1
            runs.append(run)
    return runs


def expand_combined(doc: dict[str, Any], *, quick: bool) -> list[dict[str, Any]]:
    """One run per scenario × pin × tap × repeat. ``--quick`` keeps the first scenario only."""
    scenarios = list(doc.get("scenarios") or [])
    if quick and scenarios:
        scenarios = scenarios[:1]
    repeats = int(doc.get("repeats", 3))
    runs: list[dict[str, Any]] = []
    for scenario in scenarios:
        pins = scenario.get("pin_cpu") or [False]
        taps = scenario.get("tap") or [False]
        for pin, tap in itertools.product(pins, taps):
            for repeat in range(repeats):
                runs.append(
                    {
                        "id": scenario["name"],
                        "name": scenario["name"],
                        "ns3": dict(scenario["ns3"]),
                        "gazebo": dict(scenario["gazebo"]),
                        "pin_cpu": bool(pin),
                        "tap": bool(tap),
                        "repeat": repeat,
                        "seed": repeat + 1,
                        "duration_s": doc.get("duration_s", 15),
                        "sim_time_s": doc.get("sim_time_s", 15),
                    }
                )
    return runs


def expand_suite(name: str, *, quick: bool) -> list[dict[str, Any]]:
    if name == "all":
        runs: list[dict[str, Any]] = []
        for part in ("ns3", "gazebo", "combined"):
            for run in expand_suite(part, quick=quick):
                run = dict(run)
                run["suite"] = part
                runs.append(run)
        return runs
    doc = load_suite(name)
    if name == "combined":
        runs = expand_combined(doc, quick=quick)
    else:
        runs = expand_factor_grid(doc, quick=quick)
    for run in runs:
        run["suite"] = name
        if name == "ns3":
            run["sim_time_s"] = doc.get("sim_time_s", 20)
        if name == "gazebo":
            run["duration_s"] = doc.get("duration_s", 10)
    return runs


def format_dry_run(runs: list[dict[str, Any]]) -> str:
    lines = [f"planned runs: {len(runs)}"]
    for index, run in enumerate(runs, start=1):
        suite = run.get("suite", "")
        ident = run.get("id", run.get("name", ""))
        lines.append(
            f"[{index}] suite={suite} id={ident} repeat={run.get('repeat')} "
            f"seed={run.get('seed')} pin_cpu={run.get('pin_cpu', False)} tap={run.get('tap', False)}"
        )
    return "\n".join(lines) + "\n"
