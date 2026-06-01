from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

from cornet.leaderboard.viewer import show
from cornet.leaderboard.writer import append_entry


def test_append_creates_and_appends_entries(tmp_path: Path) -> None:
    append_entry(str(tmp_path), {"variant_id": "a", "status": "SUCCESS", "metric": 2.0})
    append_entry(str(tmp_path), {"variant_id": "b", "status": "SUCCESS", "metric": 1.0})

    data = json.loads((tmp_path / "leaderboard.json").read_text())
    assert len(data) == 2
    assert data[0]["variant_id"] == "a"
    assert data[1]["variant_id"] == "b"


def test_corrupt_file_is_backed_up_and_reset(tmp_path: Path) -> None:
    (tmp_path / "leaderboard.json").write_text("{bad json")
    append_entry(str(tmp_path), {"variant_id": "a", "status": "SUCCESS", "metric": 2.0})

    assert (tmp_path / "leaderboard.json").exists()
    backups = list(tmp_path.glob("leaderboard.json.bak.*"))
    assert backups
    data = json.loads((tmp_path / "leaderboard.json").read_text())
    assert len(data) == 1


def test_viewer_outputs_sorted_order(tmp_path: Path) -> None:
    append_entry(str(tmp_path), {"variant_id": "slow", "status": "SUCCESS", "metric": 12.5, "output_dir": "r1", "timestamp": "t1"})
    append_entry(str(tmp_path), {"variant_id": "fast", "status": "SUCCESS", "metric": 8.3, "output_dir": "r2", "timestamp": "t2"})
    append_entry(str(tmp_path), {"variant_id": "fail", "status": "FAILURE", "metric": None, "output_dir": "r3", "timestamp": "t3"})

    console = Console(record=True, width=120)
    show(str(tmp_path), higher_is_better=False, console=console)
    output = console.export_text()

    assert "fast" in output
    assert "slow" in output
    assert "fail" in output
    assert output.index("fast") < output.index("slow") < output.index("fail")
