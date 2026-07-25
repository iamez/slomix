"""Serving-layer correctness fixes from the 2026-07-25 data audit (S2-S14).

Each test pins one serving-layer defect the audit confirmed on the live
/proximity/ page:
  S2  weapon-accuracy silently dropped the page's session/round scope
  S3  leaderboards used `session_date >= X` — the chosen session PLUS every
      later one — and could not disambiguate a map replayed in one night
  S4  crossfire-angle averaged per-side averages unweighted
  S5  fabricated constants (dodge 5000ms / support 3000ms) competed inside
      percentile pools
  S6  no bot-round/validity gate anywhere in the proximity routers
  S14 self-rows (killer == target) polluted engagement denominators
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from website.backend.dependencies import get_db
from website.backend.routers.proximity_helpers import (
    ProximityQueryBuilder,
    _build_proximity_where_clause,
    _round_quality_gate_sql,
)
from website.backend.routers.proximity_scoring import router as scoring_router

GATE_FRAGMENT = "rq.is_bot_round IS DISTINCT FROM TRUE"


class _CaptureDB:
    """Returns empty result sets while recording every query."""

    def __init__(self):
        self.queries: list[tuple[str, tuple]] = []

    def _note(self, query, params):
        self.queries.append((" ".join(query.split()), tuple(params or ())))

    async def fetch_all(self, query, params=None):
        self._note(query, params)
        return []

    async def fetch_one(self, query, params=None):
        self._note(query, params)
        return None

    async def fetch_val(self, query, params=None):
        self._note(query, params)
        return 0

    def joined(self) -> str:
        return "\n".join(q for q, _ in self.queries)


def _app(db) -> FastAPI:
    app = FastAPI()
    app.include_router(scoring_router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: db
    return app


async def _get(db, path, params):
    transport = ASGITransport(app=_app(db))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(path, params=params)


# ---------------------------------------------------------------------------
# S6 — the shared round-quality gate
# ---------------------------------------------------------------------------

def test_where_clause_builder_appends_quality_gate():
    where_sql, params, _ = _build_proximity_where_clause(
        30, "2026-07-18", None, None, None
    )
    assert GATE_FRAGMENT in where_sql
    assert "rq.is_valid IS DISTINCT FROM FALSE" in where_sql
    # NULL round_id rows are kept — unlinked orphans can't be attributed
    assert "round_id IS NULL OR EXISTS" in where_sql
    # gate adds no params
    assert len(params) == 1


def test_where_clause_builder_gate_can_be_disabled_for_tables_without_round_id():
    where_sql, _, _ = _build_proximity_where_clause(
        30, "2026-07-18", None, None, None, round_quality_gate=False
    )
    assert GATE_FRAGMENT not in where_sql


def test_query_builder_gate_method():
    where_sql, _ = (
        ProximityQueryBuilder()
        .with_session_scope("2026-07-18", 30)
        .with_round_quality_gate()
        .build()
    )
    assert GATE_FRAGMENT in where_sql


def test_gate_sql_uses_prefix():
    assert "ce.round_id" in _round_quality_gate_sql("ce.")


# ---------------------------------------------------------------------------
# S3 — leaderboard scope: exact date, round_start_unix, gate
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_leaderboards_selected_date_filters_exact_not_gte():
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/leaderboards",
                      {"category": "survivors", "session_date": "2026-07-18"})
    assert resp.status_code == 200
    sql = db.joined()
    assert "session_date = $1" in sql
    assert "session_date >= $1" not in sql
    assert GATE_FRAGMENT in sql


@pytest.mark.asyncio
async def test_leaderboards_range_window_keeps_gte():
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/leaderboards",
                      {"category": "survivors", "range_days": 14})
    assert resp.status_code == 200
    assert "session_date >= $1" in db.joined()


@pytest.mark.asyncio
async def test_leaderboards_accept_round_start_unix():
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/leaderboards",
                      {"category": "survivors", "session_date": "2026-07-18",
                       "round_number": 2, "round_start_unix": 1784402640})
    assert resp.status_code == 200
    sql, params = db.queries[0]
    assert "round_start_unix = $" in sql
    assert 1784402640 in params


# ---------------------------------------------------------------------------
# S14 — self-rows excluded from engagement denominators
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_survivors_excludes_self_rows():
    db = _CaptureDB()
    await _get(db, "/api/proximity/leaderboards",
               {"category": "survivors", "session_date": "2026-07-18"})
    assert "killer_guid IS DISTINCT FROM target_guid" in db.joined()


# ---------------------------------------------------------------------------
# S4 — weighted crossfire angle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crossfire_angle_weighted_by_count():
    db = _CaptureDB()
    await _get(db, "/api/proximity/leaderboards",
               {"category": "crossfire", "session_date": "2026-07-18"})
    sql = db.joined()
    assert "SUM(sum_angle) / NULLIF(SUM(cnt), 0)" in sql
    assert "AVG(avg_angle)" not in sql


# ---------------------------------------------------------------------------
# S2 — weapon-accuracy honours the page scope
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_weapon_accuracy_accepts_session_and_round_scope():
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/weapon-accuracy",
                      {"session_date": "2026-07-18", "round_number": 1,
                       "round_start_unix": 1784402640})
    assert resp.status_code == 200
    sql, params = db.queries[0]
    assert "session_date = $" in sql
    # exact-round scope resolves via round_id -> rounds (table has no
    # round columns of its own)
    assert "round_id IN (SELECT r.id FROM rounds r WHERE" in sql
    assert 1784402640 in params
    assert GATE_FRAGMENT in sql


@pytest.mark.asyncio
async def test_weapon_accuracy_without_date_keeps_range_window():
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/weapon-accuracy", {"range_days": 30})
    assert resp.status_code == 200
    assert "CURRENT_DATE" in db.queries[0][0]
