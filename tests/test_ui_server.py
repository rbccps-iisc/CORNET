"""Tests for cornet.ui.server (ui-server spec)."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

# FastAPI TestClient requires httpx; skip whole module if ui extras absent.
pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")

from fastapi.testclient import TestClient

from cornet.ui.server import create_app, find_free_port, RUNNING_WINDOW_SECONDS


# ─── /api/leaderboard ────────────────────────────────────────────────────────

def test_leaderboard_returns_empty_list_when_file_absent(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    assert resp.json() == []


def test_leaderboard_returns_entries_when_file_present(tmp_path: Path) -> None:
    entries = [
        {"variant_id": "bw=10", "status": "SUCCESS", "metric": 0.9},
        {"variant_id": "bw=20", "status": "FAILURE", "metric": None, "error": "timeout"},
    ]
    (tmp_path / "leaderboard.json").write_text(json.dumps(entries))
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["variant_id"] == "bw=10"
    assert data[1]["status"] == "FAILURE"


# ─── /api/config ─────────────────────────────────────────────────────────────

def test_config_returns_empty_dict_when_file_absent(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_config_returns_parsed_yaml_when_present(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text("name: test_task\nversion: 1\n")
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/config")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test_task"
    assert data["version"] == 1


# ─── /api/status ─────────────────────────────────────────────────────────────

def test_status_returns_zero_mtime_when_file_absent(tmp_path: Path) -> None:
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mtime"] == 0.0
    assert data["running"] is False


def test_status_running_true_for_recently_modified_file(tmp_path: Path) -> None:
    lb = tmp_path / "leaderboard.json"
    lb.write_text("[]")
    # File was just written — mtime is within RUNNING_WINDOW_SECONDS
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["mtime"] > 0.0
    assert data["running"] is True


def test_status_running_false_for_old_file(tmp_path: Path, monkeypatch) -> None:
    lb = tmp_path / "leaderboard.json"
    lb.write_text("[]")
    # Fake time so the file appears stale
    monkeypatch.setattr(time, "time", lambda: lb.stat().st_mtime + RUNNING_WINDOW_SECONDS + 1)
    client = TestClient(create_app(tmp_path))
    resp = client.get("/api/status")
    data = resp.json()
    assert data["running"] is False


# ─── Route ordering regression: /api/* must not be shadowed by StaticFiles ───

def test_api_routes_not_shadowed_by_static_mount(tmp_path: Path) -> None:
    """Regression: StaticFiles mount at '/' must not intercept /api/* routes."""
    client = TestClient(create_app(tmp_path))
    # All three API endpoints must return 200, not 404
    assert client.get("/api/leaderboard").status_code == 200
    assert client.get("/api/config").status_code == 200
    assert client.get("/api/status").status_code == 200


# ─── find_free_port ───────────────────────────────────────────────────────────

def test_find_free_port_returns_usable_port() -> None:
    sock, port = find_free_port()
    try:
        assert isinstance(port, int)
        assert 1 <= port <= 65535
        # Socket must still be bound (not closed)
        addr = sock.getsockname()
        assert addr[1] == port
    finally:
        sock.close()
