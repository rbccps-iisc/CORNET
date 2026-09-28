"""Append-only journal and hypothesis records."""

from __future__ import annotations

import json
from pathlib import Path

from cornet.research.brief import Hypothesis

_OPEN = "open"
_VERDICTS = {"supported", "refuted", "inconclusive"}


def journal_path(task_dir: Path) -> Path:
    return task_dir / "research" / "journal.md"


def hypotheses_path(task_dir: Path) -> Path:
    return task_dir / "research" / "hypotheses.jsonl"


def append_journal(task_dir: Path, text: str) -> None:
    path = journal_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def load_hypotheses(task_dir: Path) -> list[dict]:
    path = hypotheses_path(task_dir)
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def record_hypothesis(task_dir: Path, hypothesis: Hypothesis, *, status: str = _OPEN) -> dict:
    if status != _OPEN:
        raise ValueError("verdicts come from compare; record_hypothesis only opens a hypothesis")
    rows = [row for row in load_hypotheses(task_dir) if row.get("id") != hypothesis.id]
    record = {
        "id": hypothesis.id,
        "claim": hypothesis.claim,
        "prediction": hypothesis.prediction,
        "falsification": hypothesis.falsification,
        "expect": hypothesis.expect,
        "status": _OPEN,
        "evidence": [],
    }
    rows.append(record)
    _write(task_dir, rows)
    return record


def set_verdict(task_dir: Path, hypothesis_id: str, status: str, evidence: list[str]) -> dict:
    if status not in _VERDICTS:
        raise ValueError(f"unknown verdict {status}")
    rows = load_hypotheses(task_dir)
    found = None
    for row in rows:
        if row.get("id") == hypothesis_id:
            row["status"] = status
            row["evidence"] = list(evidence)
            found = row
    if found is None:
        raise ValueError(f"unknown hypothesis {hypothesis_id}")
    _write(task_dir, rows)
    return found


def _write(task_dir: Path, rows: list[dict]) -> None:
    path = hypotheses_path(task_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
