"""Numeric report sections. The agent only supplies the discussion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cornet.research.critic import caveats_for


def render_report(
    *,
    question: str,
    brief_summary: str,
    hypotheses: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    leaderboard: list[dict[str, Any]],
    discussion: str,
    scenario: dict[str, Any] | None = None,
) -> str:
    by_id = {row.get("variant_id"): row for row in leaderboard}
    lines = [
        f"# Research report",
        "",
        f"## Question",
        "",
        question,
        "",
        "## Brief",
        "",
        brief_summary.strip(),
        "",
    ]
    for hypothesis in hypotheses:
        comp = next((item for item in comparisons if item.get("hypothesis_id") == hypothesis.get("id")), None)
        lines.append(f"## Hypothesis {hypothesis.get('id')}")
        lines.append("")
        lines.append(f"Verdict: {hypothesis.get('status')}")
        if comp:
            lines.append(f"Effect size: {comp.get('effect_size')}")
            lines.append(f"95% CI: {comp.get('ci95')}")
            lines.append(f"p-value: {comp.get('p_value')}")
            evidence = comp.get("evidence") or []
            lines.append("Evidence:")
            for run_id in evidence:
                entry = by_id.get(run_id, {})
                lines.append(f"- {run_id} config_hash={entry.get('config_hash')}")
        lines.append("")
    lines.extend(["## Caveats", ""])
    any_caveat = False
    for entry in leaderboard:
        labels = caveats_for(entry, scenario=scenario)
        if not labels:
            continue
        any_caveat = True
        lines.append(f"- {entry.get('variant_id')}: {', '.join(labels)}")
    if not any_caveat:
        lines.append("None.")
    lines.extend(["", "## Discussion", "", discussion.strip(), ""])
    return "\n".join(lines)


def check_evidence(report: str, leaderboard_path: Path) -> list[str]:
    """Return run ids cited in the report that are missing or hash-mismatched."""
    if not leaderboard_path.is_file():
        return ["leaderboard missing"]
    rows = json.loads(leaderboard_path.read_text())
    known = {row.get("variant_id"): row.get("config_hash") for row in rows}
    problems = []
    for line in report.splitlines():
        if not line.startswith("- ") or "config_hash=" not in line:
            continue
        body = line[2:]
        run_id, _, hashed = body.partition(" config_hash=")
        if run_id not in known:
            problems.append(run_id)
        elif known[run_id] and hashed and hashed != "None" and known[run_id] != hashed:
            problems.append(run_id)
    return problems
