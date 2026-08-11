"""Live view S1: ingest + feed contract for website/backend/routers/live.py.

Runs the router on a bare FastAPI app (no site middleware, no DB) — the
contract under test is the ring buffer, the cursor semantics and the
internal-secret gate, all process-local.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

live = importlib.import_module("website.backend.routers.live")


@pytest.fixture()
def client(monkeypatch):
    # Fresh buffer per test — the module is process-global by design.
    monkeypatch.setattr(live, "_events", type(live._events)(maxlen=live._BUFFER_MAX))  # noqa: SLF001
    monkeypatch.setattr(live, "_seq", 0)  # noqa: SLF001
    monkeypatch.setenv("INTERNAL_API_SECRET", "test-secret")
    app = FastAPI()
    app.include_router(live.router, prefix="/api/live")
    return TestClient(app)


def _post(client, events, token="test-secret"):  # noqa: S107 — test fixture value, not a credential
    headers = {"X-Internal-Token": token} if token else {}
    return client.post("/api/live/events", json={"events": events}, headers=headers)


def test_ingest_requires_internal_secret(client):
    assert _post(client, [{"type": "KILL"}], token=None).status_code in (401, 403)
    assert _post(client, [{"type": "KILL"}], token="wrong").status_code in (401, 403)


def test_feed_cursor_semantics(client):
    r = _post(client, [
        {"type": "ROUND_START", "level_ms": 1000},
        {"type": "KILL", "level_ms": 2000, "fields": {"killer": "a", "victim": "b", "mod": "MOD_MP40"}},
    ])
    assert r.status_code == 200 and r.json()["accepted"] == 2

    page1 = client.get("/api/live/feed?since=0").json()
    assert [e["type"] for e in page1["events"]] == ["ROUND_START", "KILL"]
    assert page1["events"][1]["killer"] == "a"

    cursor = page1["last_seq"]
    assert client.get(f"/api/live/feed?since={cursor}").json()["events"] == []

    _post(client, [{"type": "ROUND_END"}])
    page2 = client.get(f"/api/live/feed?since={cursor}").json()
    assert [e["type"] for e in page2["events"]] == ["ROUND_END"]


def test_unknown_types_are_dropped_not_stored(client):
    r = _post(client, [
        {"type": "TEAM_CHAT_REDACTED"},
        {"type": "TOTALLY_MADE_UP"},
        {"type": "POPUP", "fields": {"team": "allies", "verb": "stole", "objective": "Gold"}},
    ])
    assert r.json()["accepted"] == 1
    events = client.get("/api/live/feed").json()["events"]
    assert [e["type"] for e in events] == ["POPUP"]


def test_batch_size_cap(client):
    r = _post(client, [{"type": "KILL"}] * (live._POST_MAX_EVENTS + 1))  # noqa: SLF001
    assert r.status_code == 413


def test_status_reports_freshness(client):
    s0 = client.get("/api/live/status").json()
    assert s0["buffered"] == 0 and s0["newest_age_seconds"] is None
    _post(client, [{"type": "MAP", "fields": {"map_name": "supply"}}])
    s1 = client.get("/api/live/status").json()
    assert s1["buffered"] == 1
    assert s1["newest_age_seconds"] is not None and s1["newest_age_seconds"] < 5
