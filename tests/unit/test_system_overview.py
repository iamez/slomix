"""Router-level tests for GET /api/system/overview.

The endpoint's job is to tell "nobody played" apart from "something broke".
Those two read identically in the raw numbers, so the interpretation is what
these tests lock in:

- an idle week is `idle`, never a failure
- a capture that never became a linked round is `warn` (the real break signal)
- a session with rounds but no Kill Impact rows is `warn`
- the headline is the WORST stage, so one broken link cannot hide behind four
  healthy ones
- a failing source degrades to `unknown` for that stage only — the response
  still renders

The SQL gates themselves (bot rounds excluded, counting by `round_date`
because `round_start_unix` is sparse) are verified live against the database,
not here: a fake DB cannot prove a WHERE clause.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from website.backend.dependencies import get_db
from website.backend.routers import diagnostics_router


class FakeSystemDB:
    """Routes by SQL fingerprint across the three pipeline queries."""

    def __init__(self):
        # (last_capture_at, unlinked_48h)
        self.capture_row: tuple | None = (datetime.now(timezone.utc), 0)
        # (last_round_date, last_round_unix, rounds_7d)
        self.rounds_row: tuple | None = ("2026-08-11", None, 14)
        # (gsid, rounds, kis_rows, proximity_kills)
        self.derived_row: tuple | None = (144, 14, 61, 507)
        self.select_one_fails = False
        self.fail_on: set[str] = set()

    async def fetch_one(self, query: str, params=None) -> Any:
        q = " ".join(query.split())
        if "FROM lua_round_teams" in q and "captured_at" in q:
            if "capture" in self.fail_on:
                raise RuntimeError("capture query exploded")
            return self.capture_row
        if "FROM rounds" in q and "round_date" in q and "COUNT(*) FILTER" in q:
            if "rounds" in self.fail_on:
                raise RuntimeError("rounds query exploded")
            return self.rounds_row
        if "storytelling_kill_impact" in q:
            if "derived" in self.fail_on:
                raise RuntimeError("derived query exploded")
            return self.derived_row
        if q.strip().upper().startswith("SELECT 1"):
            if self.select_one_fails:
                raise RuntimeError("database gone")
            return (1,)
        raise AssertionError(f"unexpected query: {q[:120]}")

    async def fetch_all(self, query: str, params=None) -> list[tuple]:
        return []

    async def fetch_val(self, query: str, params=None) -> Any:
        return None


class _FakeServer:
    online = True
    map_name = "supply"
    player_count = 6
    max_players = 16
    ping_ms = 7


def _build_app(db: FakeSystemDB) -> FastAPI:
    app = FastAPI()

    async def _db_override():
        yield db

    app.dependency_overrides[get_db] = _db_override
    app.include_router(diagnostics_router.router, prefix="/api")
    return app


async def _get(db: FakeSystemDB, monkeypatch, *, linkage=None, server=_FakeServer()):
    """Call the endpoint with the two out-of-process sources stubbed."""
    monkeypatch.setattr(
        diagnostics_router, "query_game_server", lambda host, port: server, raising=True
    )

    async def _fake_linkage(_db, **_kw):
        if linkage is None:
            return {"metrics": {"unlinked_lua_ratio": 0.0}, "breaches": []}
        return linkage

    monkeypatch.setattr(
        diagnostics_router, "assess_round_linkage_anomalies", _fake_linkage, raising=True
    )

    transport = httpx.ASGITransport(app=_build_app(db))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/system/overview")
    assert resp.status_code == 200
    return resp.json()


def _stage(body: dict, key: str) -> dict:
    return next(s for s in body["stages"] if s["key"] == key)


@pytest.mark.asyncio
async def test_healthy_pipeline_reports_ok(monkeypatch):
    body = await _get(FakeSystemDB(), monkeypatch)
    assert body["overall"] == "ok"
    assert {s["key"] for s in body["stages"]} == {
        "game_server", "capture", "parser", "derived", "api",
    }
    assert _stage(body, "parser")["detail"]["rounds_last_7d"] == 14
    assert _stage(body, "derived")["detail"]["gaming_session_id"] == 144


@pytest.mark.asyncio
async def test_quiet_week_is_idle_not_broken(monkeypatch):
    """Gathers run a few times a week — silence is not a failure."""
    db = FakeSystemDB()
    db.capture_row = (datetime.now(timezone.utc) - timedelta(days=9), 0)
    db.rounds_row = ("2026-07-20", None, 0)
    body = await _get(db, monkeypatch)

    assert _stage(body, "capture")["state"] == "idle"
    assert _stage(body, "parser")["state"] == "idle"
    assert body["overall"] == "idle"


@pytest.mark.asyncio
async def test_capture_without_a_linked_round_warns(monkeypatch):
    """The one signal that genuinely means the chain is broken."""
    db = FakeSystemDB()
    db.capture_row = (datetime.now(timezone.utc), 3)
    body = await _get(db, monkeypatch)

    capture = _stage(body, "capture")
    assert capture["state"] == "warn"
    assert "3" in capture["summary"]
    assert capture["detail"]["unlinked_last_48h"] == 3
    assert body["overall"] == "warn"


@pytest.mark.asyncio
async def test_session_without_smart_stats_warns(monkeypatch):
    db = FakeSystemDB()
    db.derived_row = (144, 14, 0, 507)
    body = await _get(db, monkeypatch)

    assert _stage(body, "derived")["state"] == "warn"
    assert "144" in _stage(body, "derived")["summary"]


@pytest.mark.asyncio
async def test_offline_game_server_is_down_and_wins_the_headline(monkeypatch):
    class _Offline(_FakeServer):
        online = False

    db = FakeSystemDB()
    body = await _get(db, monkeypatch, server=_Offline())

    assert _stage(body, "game_server")["state"] == "down"
    assert body["overall"] == "down"          # worst state wins
    assert _stage(body, "parser")["state"] == "ok"   # others still reported


@pytest.mark.asyncio
async def test_failing_section_degrades_alone(monkeypatch):
    """A broken source must cost its own stage, not the whole response."""
    db = FakeSystemDB()
    db.fail_on = {"capture", "derived"}
    body = await _get(db, monkeypatch)

    assert _stage(body, "capture")["state"] == "unknown"
    assert _stage(body, "derived")["state"] == "unknown"
    assert _stage(body, "parser")["state"] == "ok"
    assert _stage(body, "game_server")["state"] == "ok"


@pytest.mark.asyncio
async def test_pipeline_failure_still_lists_its_stages(monkeypatch):
    """A page that renders four green rows out of five reads as healthy — so a
    pipeline that could not be measured must still appear, as unknown."""
    db = FakeSystemDB()
    db.fail_on = {"capture"}

    async def _explode(_self_db):
        raise RuntimeError("pipeline section exploded")

    monkeypatch.setattr(diagnostics_router, "_system_pipeline", _explode, raising=True)
    body = await _get(db, monkeypatch)

    keys = [s["key"] for s in body["stages"]]
    assert {"capture", "parser", "derived"}.issubset(set(keys))
    for key in ("capture", "parser", "derived"):
        assert _stage(body, key)["state"] == "unknown"
    assert body["overall"] in {"unknown", "warn", "down"}


@pytest.mark.asyncio
async def test_database_loss_is_reported_not_raised(monkeypatch):
    db = FakeSystemDB()
    db.select_one_fails = True
    body = await _get(db, monkeypatch)

    assert _stage(body, "api")["state"] == "down"
    assert body["overall"] == "down"


@pytest.mark.asyncio
async def test_linkage_exposes_metrics_and_breaches_but_no_row_samples(monkeypatch):
    linkage = {
        "metrics": {"unlinked_lua_ratio": 0.092, "wrong_start_lua_rows": 0},
        "breaches": [{"metric": "round_number_mismatch_rows", "value": 1, "threshold": 0}],
        "samples": {"lua_link_mismatches": [{"id": 42, "map_name": "supply"}]},
    }
    body = await _get(FakeSystemDB(), monkeypatch, linkage=linkage)

    assert body["linkage"]["available"] is True
    assert body["linkage"]["breach_count"] == 1
    assert body["linkage"]["breaches"][0]["metric"] == "round_number_mismatch_rows"
    # Row-level samples are deliberately not part of the public payload.
    assert "samples" not in body["linkage"]


@pytest.mark.asyncio
async def test_linkage_failure_does_not_fail_the_page(monkeypatch):
    async def _boom(_db, **_kw):
        raise RuntimeError("linkage service down")

    monkeypatch.setattr(
        diagnostics_router, "assess_round_linkage_anomalies", _boom, raising=True
    )
    monkeypatch.setattr(
        diagnostics_router, "query_game_server", lambda host, port: _FakeServer(), raising=True
    )

    transport = httpx.ASGITransport(app=_build_app(FakeSystemDB()))
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/system/overview")

    assert resp.status_code == 200
    assert resp.json()["linkage"] == {"available": False}
