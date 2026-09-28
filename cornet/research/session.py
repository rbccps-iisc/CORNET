"""Persisted research session."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ResearchSession:
    session_id: str
    task_id: str
    task_dir: Path
    phase: str
    question: str
    questions: list[dict[str, Any]] = field(default_factory=list)
    eval_hash: str | None = None
    primary_metric: str | None = None
    budget: dict[str, float] = field(default_factory=dict)
    consumed: dict[str, float] = field(default_factory=dict)
    agent_ids: dict[str, str] = field(default_factory=dict)
    allow_web_search: bool = False
    allow_code_edits: bool = False
    wall_started: float = 0.0

    def path(self) -> Path:
        return self.task_dir / "research" / "session.json"

    def save(self) -> None:
        payload = {
            "session_id": self.session_id,
            "task_id": self.task_id,
            "task_dir": str(self.task_dir),
            "phase": self.phase,
            "question": self.question,
            "questions": self.questions,
            "eval_hash": self.eval_hash,
            "primary_metric": self.primary_metric,
            "budget": self.budget,
            "consumed": self.consumed,
            "agent_ids": self.agent_ids,
            "allow_web_search": self.allow_web_search,
            "allow_code_edits": self.allow_code_edits,
            "wall_started": self.wall_started,
        }
        path = self.path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n")

    @classmethod
    def load(cls, path: Path) -> ResearchSession:
        data = json.loads(path.read_text())
        return cls(
            session_id=data["session_id"],
            task_id=data["task_id"],
            task_dir=Path(data["task_dir"]),
            phase=data["phase"],
            question=data.get("question", ""),
            questions=list(data.get("questions") or []),
            eval_hash=data.get("eval_hash"),
            primary_metric=data.get("primary_metric"),
            budget=dict(data.get("budget") or {}),
            consumed=dict(data.get("consumed") or {}),
            agent_ids=dict(data.get("agent_ids") or {}),
            allow_web_search=bool(data.get("allow_web_search")),
            allow_code_edits=bool(data.get("allow_code_edits")),
            wall_started=float(data.get("wall_started") or 0.0),
        )


def new_session(task_dir: Path, question: str, *, budget: dict | None = None) -> ResearchSession:
    session = ResearchSession(
        session_id=uuid.uuid4().hex[:8],
        task_id=task_dir.name,
        task_dir=task_dir,
        phase="intake",
        question=question,
        budget=budget
        or {
            "max_trials": 40,
            "max_sim_seconds": 3600,
            "max_wall_hours": 8,
            "max_agent_runs": 40,
        },
        consumed={"trials": 0, "sim_seconds": 0, "agent_runs": 0},
    )
    session.save()
    return session


def find_session(repo: Path, session_id: str) -> ResearchSession:
    for path in (repo / "tasks").glob("*/research/session.json"):
        session = ResearchSession.load(path)
        if session.session_id == session_id:
            return session
    raise FileNotFoundError(session_id)


def hash_eval(task_dir: Path) -> str | None:
    path = task_dir / "eval" / "eval_tool.py"
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def budget_exhausted(session: ResearchSession, *, now: float | None = None) -> str | None:
    consumed = session.consumed
    budget = session.budget
    if consumed.get("trials", 0) >= budget.get("max_trials", 1e18):
        return "max_trials"
    if consumed.get("sim_seconds", 0) >= budget.get("max_sim_seconds", 1e18):
        return "max_sim_seconds"
    if consumed.get("agent_runs", 0) >= budget.get("max_agent_runs", 1e18):
        return "max_agent_runs"
    if now is not None and session.wall_started:
        hours = (now - session.wall_started) / 3600
        if hours >= budget.get("max_wall_hours", 1e18):
            return "max_wall_hours"
    return None


def has_cap_net_admin() -> bool:
    cap_net_admin = 1 << 12
    status = Path("/proc/self/status")
    if not status.is_file():
        return False
    for line in status.read_text().splitlines():
        if line.startswith("CapEff:"):
            return bool(int(line.split()[1], 16) & cap_net_admin)
    return False


def privilege_error(task_dir: Path) -> str | None:
    """Return a requirement string when the process cannot run the task."""
    from cornet.config.loader import load_unified

    config_path = task_dir / "config.yaml"
    if not config_path.is_file():
        return None
    config = load_unified(config_path)
    plugin = config.network.plugin or ""
    if "mininet" in plugin and os.geteuid() != 0:
        return "root is required for Mininet"
    middleware = config.network.middleware
    if middleware is not None and middleware.enabled and not has_cap_net_admin():
        return "CAP_NET_ADMIN is required for middleware TUN devices"
    return None
