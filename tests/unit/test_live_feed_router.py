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



def test_livex_types_ingest_and_feed_through(client):
    """LIVEX events (from live_events.lua via slomix-live.log) must survive
    ingest and appear in the feed — the two-tailer path end to end."""
    r = _post(client, [
        {"type": "LIVE_KILL", "level_ms": 1786480915000, "fields": {
            "killer_slot": 3, "victim_slot": 5, "mod_id": 34,
            "killer_pos": {"x": 1024, "y": -512, "z": 64}, "distance": 137}},
        {"type": "LIVE_AGGREGATE", "level_ms": 1786480920000, "fields": {
            "slot": 3, "damage_given": 640, "damage_received": 120,
            "kills": 2, "deaths": 0}},
        {"type": "LIVE_MOVEMENT", "level_ms": 1786480920000, "fields": {
            "players": [{"slot": 3, "x": 1024, "y": -512}]}},
        {"type": "LIVE_MAP", "level_ms": 1786480914000, "fields": {"map_name": "supply"}},
        # a legacy KILL alongside, as the two-tailer setup produces
        {"type": "KILL", "level_ms": 1, "fields": {"killer": "vid", "victim": "lgz", "mod": "MOD_MP40"}},
    ])
    assert r.status_code == 200 and r.json()["accepted"] == 5
    types = [e["type"] for e in client.get("/api/live/feed").json()["events"]]
    assert types == ["LIVE_KILL", "LIVE_AGGREGATE", "LIVE_MOVEMENT", "LIVE_MAP", "KILL"]
    # LIVE_KILL carries its enriched fields through unchanged
    lk = client.get("/api/live/feed").json()["events"][0]
    assert lk["distance"] == 137 and lk["killer_slot"] == 3
