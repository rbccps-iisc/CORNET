"""Atomic leaderboard writer for CORNET tasks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return out or None


def provenance_fields(config: Any, output_dir: str | Path | None = None) -> dict[str, Any]:
    """Provenance attached to every leaderboard entry.

    ``rtf_mean`` is included only when ``timing.json`` recorded a Gazebo RTF mean.
    ``timing_ok`` is ``unavailable`` when that file is absent or unreadable.
    """
    payload = config.model_dump(mode="json")
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    fields: dict[str, Any] = {
        "config_hash": hashlib.sha256(encoded.encode()).hexdigest(),
        "git_sha": _git_sha(),
        "seed": int(config.experiment.seed),
        "hypothesis_id": os.environ.get("CORNET_HYPOTHESIS_ID") or None,
        "lane": os.environ.get("CORNET_NS3_TAG") or "none",
        "standard": True,
        "timing_ok": "unavailable",
    }
    catalog = getattr(config, "catalog", None)
    if catalog is not None:
        fields["standard"] = bool(catalog.standard)
    if output_dir is not None:
        timing_path = Path(output_dir) / "timing.json"
        if timing_path.is_file():
            try:
                report = json.loads(timing_path.read_text())
            except (OSError, json.JSONDecodeError):
                report = {}
            timing_ok = report.get("timing_ok", "unavailable")
            if timing_ok not in (True, False, "unavailable"):
                timing_ok = "unavailable"
            fields["timing_ok"] = timing_ok
            gazebo = report.get("gazebo_rtf")
            if isinstance(gazebo, dict) and isinstance(gazebo.get("mean"), (int, float)):
                fields["rtf_mean"] = float(gazebo["mean"])
    return fields


def append_entry(task_dir: str, entry: dict) -> Path:
    task_path = Path(task_dir)
    leaderboard_path = task_path / "leaderboard.json"
    tmp_path = task_path / "leaderboard.json.tmp"

    existing = []
    if leaderboard_path.exists():
        try:
            existing = json.loads(leaderboard_path.read_text())
            if not isinstance(existing, list):
                raise ValueError("leaderboard root must be a list")
        except Exception:
            backup = task_path / f"leaderboard.json.bak.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            leaderboard_path.rename(backup)
            existing = []

    existing.append(entry)
    tmp_path.write_text(json.dumps(existing, indent=2))
    tmp_path.replace(leaderboard_path)
    return leaderboard_path
