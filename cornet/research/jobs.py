"""One-at-a-time experiment subprocesses."""

from __future__ import annotations

import queue
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


Executor = Callable[[Path, dict, int, str | None], dict]


@dataclass
class Job:
    job_id: str
    task_dir: Path
    overrides: dict
    repeats: int
    seed: int
    hypothesis_id: str | None
    status: str = "queued"
    error: str = ""
    entries: list[dict] = field(default_factory=list)


class JobQueue:
    """Concurrency is 1. A second submit waits until the running job finishes."""

    def __init__(self, executor: Executor | None = None) -> None:
        self._executor = executor or _subprocess_executor
        self._jobs: dict[str, Job] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="cornet-research-jobs", daemon=True)
        self._thread.start()

    def submit(
        self,
        task_dir: Path,
        overrides: dict,
        repeats: int,
        seed: int,
        hypothesis_id: str | None = None,
    ) -> Job:
        job = Job(
            job_id=uuid.uuid4().hex[:12],
            task_dir=task_dir,
            overrides=dict(overrides),
            repeats=repeats,
            seed=seed,
            hypothesis_id=hypothesis_id,
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._queue.put(job.job_id)
        return job

    def status(self, job_id: str) -> Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    def wait(self, job_id: str, timeout: float = 3600) -> Job:
        import time

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            job = self.status(job_id)
            if job.status in {"finished", "failed"}:
                return job
            time.sleep(0.02)
        raise TimeoutError(job_id)

    def _loop(self) -> None:
        while True:
            job_id = self._queue.get()
            job = self.status(job_id)
            job.status = "running"
            try:
                for offset in range(job.repeats):
                    entry = self._executor(
                        job.task_dir,
                        job.overrides,
                        job.seed + offset,
                        job.hypothesis_id,
                    )
                    job.entries.append(entry)
                job.status = "finished"
            except Exception as exc:  # crash isolation
                job.status = "failed"
                job.error = str(exc)


def _subprocess_executor(task_dir: Path, overrides: dict, seed: int, hypothesis_id: str | None) -> dict:
    import os

    env = os.environ.copy()
    env["CORNET_EXPERIMENT_SEED"] = str(seed)
    if hypothesis_id:
        env["CORNET_HYPOTHESIS_ID"] = hypothesis_id
    completed = subprocess.run(
        ["python3", "-m", "cornet", "run", str(task_dir)],
        cwd=str(task_dir.parents[1] if task_dir.parent.name == "tasks" else task_dir.parent),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()
        detail = tail[-1] if tail else f"exit {completed.returncode}"
        raise RuntimeError(detail)
    return {"seed": seed, "overrides": overrides, "returncode": 0}
