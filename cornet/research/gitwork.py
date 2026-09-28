"""One git worktree per session, with an editable-path backstop."""

from __future__ import annotations

import subprocess
from pathlib import Path

_ALLOWED = {
    "research/brief.yaml",
    "research/journal.md",
    "research/hypotheses.jsonl",
    "research/session.json",
    "research/report.md",
    "leaderboard.json",
}


def branch_name(task_id: str, session_id: str) -> str:
    return f"research/{task_id}/{session_id}"


def ensure_worktree(repo: Path, task_id: str, session_id: str) -> Path:
    branch = branch_name(task_id, session_id)
    dest = repo.parent / f"{repo.name}-{session_id}"
    if dest.exists():
        return dest
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(dest), "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return dest


def foreign_changes(repo: Path, task_rel: str) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", task_rel],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    bad: list[str] = []
    prefix = task_rel.rstrip("/") + "/"
    for line in completed.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        relative = path[len(prefix):] if path.startswith(prefix) else path
        if relative not in _ALLOWED and not relative.startswith("research/"):
            # research/session and report are allowed; other research files too
            if not any(relative == allowed or path.endswith(allowed) for allowed in _ALLOWED):
                bad.append(path)
    return bad


def revert_paths(repo: Path, paths: list[str]) -> None:
    if not paths:
        return
    subprocess.run(["git", "checkout", "--", *paths], cwd=repo, check=True, capture_output=True)


def commit_accepted(repo: Path, task_rel: str, message: str) -> None:
    allowed = [f"{task_rel.rstrip('/')}/{name}" for name in _ALLOWED]
    subprocess.run(["git", "add", "--", *allowed], cwd=repo, check=False, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
