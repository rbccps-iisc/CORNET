"""FastAPI server for the CORNET web UI.

Usage (internal – called from __main__.py):
    from cornet.ui.server import create_app, find_free_port

IMPORTANT: API route handlers are registered BEFORE the StaticFiles mount.
FastAPI evaluates mounts in registration order; mounting StaticFiles at "/"
before the /api/* routes would cause the catch-all to intercept all API
requests and return 404.
"""

from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

import yaml
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

# Advisory threshold: leaderboard.json modified within this window → running=True.
# This is cosmetic only; the mtime-change trigger for data reload is authoritative.
RUNNING_WINDOW_SECONDS: int = 30

_STATIC_DIR = Path(__file__).parent / "static"


def create_app(task_dir: Path) -> FastAPI:
    """Return a configured FastAPI application for *task_dir*."""
    task_dir = task_dir.resolve()
    leaderboard_path = task_dir / "leaderboard.json"
    config_path = task_dir / "config.yaml"

    app = FastAPI(title="CORNET UI", docs_url=None, redoc_url=None)

    # ------------------------------------------------------------------
    # API routes — MUST be registered before the StaticFiles mount below
    # ------------------------------------------------------------------

    @app.get("/api/leaderboard")
    def get_leaderboard() -> JSONResponse:
        """Return all leaderboard entries, or [] if the file does not exist."""
        if not leaderboard_path.exists():
            return JSONResponse([])
        entries = json.loads(leaderboard_path.read_text(encoding="utf-8"))
        return JSONResponse(entries)

    @app.get("/api/config")
    def get_config() -> JSONResponse:
        """Return parsed config.yaml, or {} if the file does not exist."""
        if not config_path.exists():
            return JSONResponse({})
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        return JSONResponse(data)

    @app.get("/api/status")
    def get_status() -> JSONResponse:
        """Return leaderboard.json mtime and a cosmetic 'running' flag."""
        if not leaderboard_path.exists():
            return JSONResponse({"mtime": 0.0, "running": False})
        mtime = os.path.getmtime(leaderboard_path)
        running = (time.time() - mtime) < RUNNING_WINDOW_SECONDS
        return JSONResponse({"mtime": mtime, "running": running})

    # ------------------------------------------------------------------
    # Static file mount — registered LAST so /api/* routes take priority
    # ------------------------------------------------------------------
    app.mount("/", StaticFiles(directory=str(_STATIC_DIR), html=True), name="static")

    return app


def find_free_port(host: str = "127.0.0.1") -> tuple[socket.socket, int]:
    """Bind to an ephemeral port and return the live socket and port number.

    The caller is responsible for passing the socket directly to uvicorn so
    the OS never releases it (eliminating the TOCTOU race of close-then-reuse).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, 0))
    port: int = sock.getsockname()[1]
    return sock, port
