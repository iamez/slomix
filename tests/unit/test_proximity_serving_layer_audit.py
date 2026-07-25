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


_req_counter = 0


async def _get(db, path, params):
    # Unique X-Forwarded-For per request: slowapi's limiter keys on the
    # client IP and its in-memory storage is shared across every FastAPI
    # app built in the same pytest process — running the full suite (KROGT
    # tests hit the same /leaderboards route) blew the 10/minute budget and
    # 429'd the later requests here (failed exactly this way in CI).
    global _req_counter
    _req_counter += 1
    transport = ASGITransport(app=_app(db))
    async with AsyncClient(transport=transport, base_url="http://t") as client:
        return await client.get(
            path, params=params,
            headers={"X-Forwarded-For": f"10.99.{_req_counter // 250}.{_req_counter % 250}"},
        )


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


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    {"session_date": "not-a-date"},
    {"round_number": -1},
    {"round_start_unix": -5},
])
async def test_weapon_accuracy_invalid_scope_is_400_not_500(bad):
    """Validation runs BEFORE the broad `except Exception`, which would
    otherwise turn a client input error into a 500 + error log (review
    on #548)."""
    db = _CaptureDB()
    resp = await _get(db, "/api/proximity/weapon-accuracy", bad)
    assert resp.status_code == 400, resp.text[:200]


# ---------------------------------------------------------------------------
# Round-quality gate must be OFF for tables without a round_id column
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quality_signal_without_round_id_omits_the_gate():
    """storytelling_kill_impact has no round_id column, so the shared gate
    (which joins through it) must be omitted for that source — otherwise
    Postgres rejects the signal query and EVERY /proximity/quality request
    degrades to `error` (review on #548, P1).

    Verified by running the real signal collector against a capturing DB
    and inspecting the SQL it emits, not by reading the source."""
    from website.backend.routers import proximity_quality

    sources = {s["key"]: s for s in proximity_quality._SIGNAL_SOURCES}  # noqa: SLF001
    no_round_id = sources["storytelling_kill_impact"]
    with_round_id = sources["proximity_kill_outcome"]
    assert no_round_id["has_round_id"] is False
    assert with_round_id["has_round_id"] is True

    for source, gate_expected in ((no_round_id, False), (with_round_id, True)):
        db = _CaptureDB()
        await proximity_quality._collect_signal(  # noqa: SLF001
            db, source, range_days=30, session_date="2026-07-18",
            map_name=None, round_number=None, round_start_unix=None,
        )
        sql = db.joined()
        assert sql, f"{source['key']} issued no query"
        assert (GATE_FRAGMENT in sql) is gate_expected, (
            f"{source['key']}: gate present={GATE_FRAGMENT in sql}, "
            f"expected={gate_expected}"
        )


# ---------------------------------------------------------------------------
# S13 — cohesion timeline: keep both teams, concatenate rounds
# ---------------------------------------------------------------------------

def test_cohesion_timeline_concatenates_rounds_without_wallclock_gaps():
    """Rounds hours apart must render back-to-back: anchoring on epoch time
    let the real downtime eat the canvas width (review on #548)."""
    from website.backend.routers.proximity_teamplay import (
        _ROUND_GAP_MS,
        _concatenated_timeline,
    )

    # (sample_time, team, dispersion, round_start_unix) — two rounds 3h apart
    rows = [
        (0, "AXIS", 100.0, 1_000_000), (0, "ALLIES", 110.0, 1_000_000),
        (60_000, "AXIS", 120.0, 1_000_000), (60_000, "ALLIES", 130.0, 1_000_000),
        (0, "AXIS", 140.0, 1_010_800), (0, "ALLIES", 150.0, 1_010_800),
        (30_000, "AXIS", 160.0, 1_010_800), (30_000, "ALLIES", 170.0, 1_010_800),
    ]
    out = _concatenated_timeline(rows)

    assert len(out) == 8
    # both teams survive
    assert {p["team"] for p in out} == {"AXIS", "ALLIES"}
    # first round starts at 0, second begins right after it (+ the gap),
    # NOT 3 hours later
    assert out[0]["time"] == 0
    second_round = [p for p in out if p["round_start_unix"] == 1_010_800]
    assert min(p["time"] for p in second_round) == 60_000 + _ROUND_GAP_MS
    # total width is play time + one gap, not wall-clock span
    assert max(p["time"] for p in out) == 60_000 + _ROUND_GAP_MS + 30_000
    # in-round offset preserved for annotation
    assert second_round[0]["round_time"] == 0


def test_cohesion_timeline_empty_is_safe():
    from website.backend.routers.proximity_teamplay import _concatenated_timeline
    assert _concatenated_timeline([]) == []
    assert _concatenated_timeline(None) == []
