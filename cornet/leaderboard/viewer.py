"""Terminal leaderboard viewer using rich tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table


def _sort_key(entry: dict[str, Any], higher_is_better: bool) -> tuple[int, float]:
    status = entry.get("status")
    metric = entry.get("metric")
    if status != "SUCCESS" or metric is None:
        return (1, 0.0)
    metric_value = float(metric)
    return (0, -metric_value if higher_is_better else metric_value)


def show(task_dir: str, higher_is_better: bool = False, console: Console | None = None) -> None:
    console = console or Console()
    task_path = Path(task_dir)
    leaderboard_path = task_path / "leaderboard.json"

    if not leaderboard_path.exists():
        console.print(f"No runs recorded yet for task {task_path.name}.")
        return

    entries = json.loads(leaderboard_path.read_text())
    if not entries:
        console.print(f"No runs recorded yet for task {task_path.name}.")
        return

    sorted_entries = sorted(entries, key=lambda entry: _sort_key(entry, higher_is_better))

    table = Table(title=f"CORNET Leaderboard — {task_path.name}")
    table.add_column("Variant")
    table.add_column("Status")
    table.add_column("Metric", justify="right")
    table.add_column("Output Dir")
    table.add_column("Timestamp")

    best_index = None
    for idx, entry in enumerate(sorted_entries):
        if entry.get("status") == "SUCCESS":
            best_index = idx
            break

    for idx, entry in enumerate(sorted_entries):
        style = "bold green" if idx == best_index else None
        table.add_row(
            str(entry.get("variant_id", "")),
            str(entry.get("status", "")),
            "" if entry.get("metric") is None else f"{float(entry['metric']):.6f}",
            str(entry.get("output_dir", "")),
            str(entry.get("timestamp", "")),
            style=style,
        )

    console.print(table)
