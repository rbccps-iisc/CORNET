"""Per-run timing telemetry. Monitoring only: it does not change simulator scheduling."""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_NS3_LOG_NAME = "ns3_timing.log"


def percentile(values: list[float], p: float) -> float:
    """Linear-interpolated percentile. ``p`` is in 0..100."""
    if not values:
        raise ValueError("percentile of empty sample")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (p / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[int(rank)]
    weight = rank - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _summarize_rtf(samples: list[float]) -> dict[str, float] | str:
    if not samples:
        return "unavailable"
    return {
        "mean": sum(samples) / len(samples),
        "p5": percentile(samples, 5),
        "min": min(samples),
    }


def _summarize_lag(samples: list[float]) -> dict[str, float] | str:
    if not samples:
        return "unavailable"
    return {
        "mean": sum(samples) / len(samples),
        "p95": percentile(samples, 95),
        "p99": percentile(samples, 99),
        "max": max(samples),
    }


def parse_ns3_timing_log(path: Path) -> list[float]:
    """Return lag samples (ms) from ``sim_s,lag_ms`` lines."""
    if not path.is_file():
        return []
    lags: list[float] = []
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        if len(parts) < 2:
            continue
        try:
            lags.append(float(parts[1]))
        except ValueError:
            continue
    return lags


def parse_gz_stats_factors(text: str) -> list[float]:
    """Pull the Factor column from ``gz stats -p`` output."""
    factors: list[float] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("factor"):
            continue
        token = line.split(",")[0].strip()
        try:
            factors.append(float(token))
        except ValueError:
            continue
    return factors


def build_timing_report(
    *,
    wall_s: float,
    rtf_samples: list[float],
    lag_samples: list[float],
    cpu_percent: dict[str, float],
    rtf_min: float,
    lag_budget_ms: float,
) -> dict[str, Any]:
    """Assemble the ``timing.json`` document and ``timing_ok``."""
    gazebo = _summarize_rtf(rtf_samples)
    ns3 = _summarize_lag(lag_samples)
    violations: list[str] = []
    checked = False
    ok = True
    if isinstance(gazebo, dict):
        checked = True
        if gazebo["p5"] < rtf_min:
            ok = False
            violations.append("rtf_min")
    if isinstance(ns3, dict):
        checked = True
        if ns3["p99"] > lag_budget_ms:
            ok = False
            violations.append("lag_budget_ms")
    if not checked:
        timing_ok: bool | str = "unavailable"
    else:
        timing_ok = ok
    return {
        "wall_s": wall_s,
        "gazebo_rtf": gazebo,
        "ns3_lag_ms": ns3,
        "cpu_percent": cpu_percent,
        "thresholds": {"rtf_min": rtf_min, "lag_budget_ms": lag_budget_ms},
        "timing_ok": timing_ok,
        "violations": violations,
    }


def timing_warning(report: dict[str, Any]) -> str | None:
    """Return a WARNING message when ``timing_ok`` is false, else None."""
    if report.get("timing_ok") is not False:
        return None
    names = ", ".join(report.get("violations") or ["threshold"])
    return f"timing_ok is false; violated {names}"


def _classify_process(name: str, cmdline: str) -> str | None:
    blob = f"{name} {cmdline}".lower()
    if "gzserver" in blob or "gzclient" in blob:
        return "gzserver"
    if "ns3" in blob or "bench_nr_multicell" in blob or "remote_robot_control" in blob:
        return "ns3"
    if "ros2" in blob or "robot_state_publisher" in blob or "component_container" in blob:
        return "ros_nodes"
    return None


class TelemetrySession:
    """Sample Gazebo RTF, NS-3 lag and CPU while an experiment runs."""

    def __init__(
        self,
        output_dir: Path,
        *,
        gazebo_active: bool,
        rtf_min: float,
        lag_budget_ms: float,
        ns3_timing_log: Path | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.gazebo_active = gazebo_active
        self.rtf_min = rtf_min
        self.lag_budget_ms = lag_budget_ms
        self.ns3_timing_log = ns3_timing_log or (self.output_dir / _NS3_LOG_NAME)
        self._stop = threading.Event()
        self._gz: subprocess.Popen | None = None
        self._gz_text: list[str] = []
        self._cpu_samples: dict[str, list[float]] = {
            "ns3": [],
            "gzserver": [],
            "ros_nodes": [],
            "other": [],
        }
        self._threads: list[threading.Thread] = []
        self._t0 = 0.0
        self.started = False

    def start(self) -> None:
        self._t0 = time.monotonic()
        self.started = True
        self._stop.clear()
        if self.gazebo_active and shutil.which("gz"):
            self._gz = subprocess.Popen(
                ["gz", "stats", "-p"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            thread = threading.Thread(target=self._read_gz, name="cornet-gz-stats", daemon=True)
            thread.start()
            self._threads.append(thread)
        cpu = threading.Thread(target=self._sample_cpu_loop, name="cornet-cpu", daemon=True)
        cpu.start()
        self._threads.append(cpu)

    def stop(self) -> dict[str, Any]:
        """Stop samplers and write ``timing.json``. Safe to call once."""
        wall_s = time.monotonic() - self._t0 if self._t0 else 0.0
        self._stop.set()
        if self._gz is not None and self._gz.poll() is None:
            self._gz.terminate()
            try:
                self._gz.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._gz.kill()
        for thread in self._threads:
            thread.join(timeout=2)
        rtf_samples = parse_gz_stats_factors("".join(self._gz_text))
        lag_samples = parse_ns3_timing_log(self.ns3_timing_log)
        cpu_percent = {
            key: (sum(vals) / len(vals) if vals else 0.0) for key, vals in self._cpu_samples.items()
        }
        report = build_timing_report(
            wall_s=wall_s,
            rtf_samples=rtf_samples,
            lag_samples=lag_samples,
            cpu_percent=cpu_percent,
            rtf_min=self.rtf_min,
            lag_budget_ms=self.lag_budget_ms,
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "timing.json").write_text(json.dumps(report, indent=2) + "\n")
        message = timing_warning(report)
        if message:
            logger.warning(message)
        return report

    def _read_gz(self) -> None:
        if self._gz is None or self._gz.stdout is None:
            return
        for line in self._gz.stdout:
            self._gz_text.append(line)
            if self._stop.is_set():
                break

    def _sample_cpu_loop(self) -> None:
        try:
            import psutil
        except ImportError:
            logger.warning("psutil is not installed; CPU samples will be empty")
            return
        while not self._stop.is_set():
            buckets = {"ns3": 0.0, "gzserver": 0.0, "ros_nodes": 0.0, "other": 0.0}
            seen = {"ns3": False, "gzserver": False, "ros_nodes": False, "other": False}
            for proc in psutil.process_iter(["name", "cmdline"]):
                try:
                    info = proc.info
                    name = info.get("name") or ""
                    cmdline = " ".join(info.get("cmdline") or [])
                    group = _classify_process(name, cmdline)
                    if group is None:
                        continue
                    buckets[group] += proc.cpu_percent(interval=None)
                    seen[group] = True
                except (psutil.Error, OSError):
                    continue
            for key, value in buckets.items():
                if seen[key]:
                    self._cpu_samples[key].append(value)
            self._stop.wait(1.0)
