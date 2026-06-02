"""Tests for /api/leaderboard variant filter (Discussion D4)."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from cornet.ui.server import create_app


def _make_app(tmp_path, entries):
    lb = tmp_path / "leaderboard.json"
    lb.write_text(json.dumps(entries))
    (tmp_path / "config.yaml").write_text("name: test\n")
    return create_app(tmp_path)


ENTRIES = [
    {"variant_id": "pendulum_nr_control@ns3-v24", "status": "SUCCESS", "metric": 5.0},
    {"variant_id": "pendulum_nr_control@ns3-v47", "status": "SUCCESS", "metric": 6.0},
    # Legacy synthetic entry — no "@" separator
    {"variant_id": "pendulum_nr_control", "status": "SUCCESS", "metric": 12.0},
]


def test_no_filter_returns_all(tmp_path):
    client = TestClient(_make_app(tmp_path, ENTRIES))
    resp = client.get("/api/leaderboard")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3


def test_variant_all_returns_all(tmp_path):
    client = TestClient(_make_app(tmp_path, ENTRIES))
    resp = client.get("/api/leaderboard?variant=all")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_variant_v24_returns_only_v24(tmp_path):
    client = TestClient(_make_app(tmp_path, ENTRIES))
    resp = client.get("/api/leaderboard?variant=ns3-v24")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["variant_id"] == "pendulum_nr_control@ns3-v24"


def test_variant_v47_returns_only_v47(tmp_path):
    client = TestClient(_make_app(tmp_path, ENTRIES))
    resp = client.get("/api/leaderboard?variant=ns3-v47")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["variant_id"] == "pendulum_nr_control@ns3-v47"


def test_variant_filter_excludes_legacy_entries(tmp_path):
    """Entries without '@' must NOT appear in any specific variant filter (D4)."""
    client = TestClient(_make_app(tmp_path, ENTRIES))
    # Request the tag that would substring-match "pendulum_nr_control" if
    # we used substring matching — but we use exact equality, so it must not match.
    resp = client.get("/api/leaderboard?variant=pendulum_nr_control")
    assert resp.status_code == 200
    assert resp.json() == []


def test_variant_unknown_returns_empty(tmp_path):
    client = TestClient(_make_app(tmp_path, ENTRIES))
    resp = client.get("/api/leaderboard?variant=ns3-v99")
    assert resp.status_code == 200
    assert resp.json() == []


def test_no_leaderboard_file_returns_empty(tmp_path):
    (tmp_path / "config.yaml").write_text("name: test\n")
    app = create_app(tmp_path)
    client = TestClient(app)
    resp = client.get("/api/leaderboard?variant=ns3-v24")
    assert resp.status_code == 200
    assert resp.json() == []
