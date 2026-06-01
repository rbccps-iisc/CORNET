"""Atomic leaderboard writer for CORNET tasks."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


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
