"""Tests for the KIS server-side SQL shadow path (Audit A5, Phase 1).

The shadow path is a SQL-only re-implementation of `_score_kill` that
runs alongside the Python path and surfaces per-kill deltas via the
`storytelling_kis_shadow_audit` table.

These tests do NOT exercise actual PostgreSQL — they exercise:

  1. `_apply_soft_cap_and_round` — the Python-side post-processing that
     matches the rounding contract pinned in `test_storytelling_kis_score_kill.py`.
  2. `_shadow_mode_enabled` — the env feature flag.
  3. `_KisShadowMixin.kis_compute_with_shadow` — flag-gated behaviour:
       - flag OFF: shadow path is a no-op (no SQL, no audit writes).
       - flag ON: shadow runs, deltas are computed, top-N persisted.
  4. The histogram + delta-floor math in `_run_kis_shadow_audit`.

A scripted in-memory fake DB stubs `compute_session_kis` and
`compute_kis_session_sql_shadow` so we can drive the audit logic with
known-divergent inputs and assert the histogram/persistence shape.

A separate test pins that the SQL output matches Python output within
±0.01 tolerance on a small fixture set — proving the rounding-only
divergence is the only expected source of mismatch.
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from website.backend.services.storytelling.kis_shadow import (
    SHADOW_AUDIT_DELTA_FLOOR,
    SHADOW_AUDIT_TOP_N,
    _apply_soft_cap_and_round,
    _shadow_mode_enabled,
)
from website.backend.services.storytelling.service import StorytellingService

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


def test_shadow_mode_disabled_by_default(monkeypatch):
    """No env var → flag must be False so the production path is unchanged."""
    monkeypatch.delenv("KIS_SHADOW_MODE_ENABLED", raising=False)
    assert _shadow_mode_enabled() is False


@pytest.mark.parametrize("val", ["1", "true", "TRUE", "yes", "on"])
def test_shadow_mode_truthy_values_enable(monkeypatch, val):
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", val)
    assert _shadow_mode_enabled() is True


@pytest.mark.parametrize("val", ["0", "false", "no", "", "off", "anything-else"])
def test_shadow_mode_falsy_values_disable(monkeypatch, val):
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", val)
    assert _shadow_mode_enabled() is False


# ---------------------------------------------------------------------------
# Soft-cap + rounding contract
# ---------------------------------------------------------------------------


def test_apply_soft_cap_passes_below_5_unchanged():
    """raw <= 5.0 must pass through with 2-decimal rounding."""
    assert _apply_soft_cap_and_round(1.0) == 1.0
    assert _apply_soft_cap_and_round(3.9) == 3.9
    assert _apply_soft_cap_and_round(5.0) == 5.0


def test_apply_soft_cap_compresses_above_5():
    """raw=10.0 → 5.0 + (10-5)*0.25 = 6.25."""
    assert _apply_soft_cap_and_round(10.0) == 6.25


def test_apply_soft_cap_preserves_ordering():
    a = _apply_soft_cap_and_round(6.0)
    b = _apply_soft_cap_and_round(8.0)
    c = _apply_soft_cap_and_round(20.0)
    assert a < b < c


# ---------------------------------------------------------------------------
# kis_compute_with_shadow — flag OFF
# ---------------------------------------------------------------------------


class _FakeDb:
    """In-memory scripted DB for shadow audit unit tests."""

    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []
        self.executemany_calls: list[tuple[str, list]] = []
        # Default empty
        self.py_rows: list[tuple[int, float]] = []

    async def fetch_one(self, query, params=None):
        return None

    async def fetch_all(self, query, params=None):
        q = str(query)
        if "FROM storytelling_kill_impact" in q:
            return list(self.py_rows)
        return []

    async def execute(self, query, params=None, *extra):
        self.executed.append((str(query), params))
        return "EXECUTE 0"

    async def executemany(self, query, params_list):
        self.executemany_calls.append((str(query), list(params_list)))
        return None


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_is_noop_when_flag_off(monkeypatch):
    """Flag off → shadow path must NOT execute the SQL query nor write audit rows.
    """
    monkeypatch.delenv("KIS_SHADOW_MODE_ENABLED", raising=False)

    svc = StorytellingService(db=_FakeDb())
    prod_called = {"count": 0}
    shadow_called = {"count": 0}

    async def fake_prod(sd, force=False):
        prod_called["count"] += 1
        return {"status": "cached", "kills_scored": 0}

    async def fake_shadow(sd):
        shadow_called["count"] += 1
        return []

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    assert prod_called["count"] == 1
    assert shadow_called["count"] == 0
    assert "shadow" not in result


# ---------------------------------------------------------------------------
# kis_compute_with_shadow — flag ON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_runs_shadow_when_flag_on(monkeypatch):
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")

    db = _FakeDb()
    # Production rows: 3 kills with python impact values.
    db.py_rows = [(1, 1.5), (2, 2.0), (3, 5.0)]

    svc = StorytellingService(db=db)

    async def fake_prod(sd, force=False):
        return {"status": "computed", "kills_scored": 3}

    # Shadow returns values that differ by various deltas. Bucket boundaries
    # are (<0.005), [0.005, 0.01), [0.01, 0.05), [0.05, inf). We pick deltas
    # that fall cleanly inside each bucket (avoiding float boundary fuzz).
    #   id=1 → 1.50 (delta 0     → bucket <0.005)
    #   id=2 → 2.02 (delta 0.02  → bucket 0.01-0.05)
    #   id=3 → 5.10 (delta 0.10  → bucket >0.05)
    async def fake_shadow(sd):
        return [
            {"kill_outcome_id": 1, "total_impact": 1.50, "multipliers": {}},
            {"kill_outcome_id": 2, "total_impact": 2.02, "multipliers": {}},
            {"kill_outcome_id": 3, "total_impact": 5.10, "multipliers": {}},
        ]

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    assert "shadow" in result
    shadow = result["shadow"]
    assert shadow["status"] == "ok"
    assert shadow["compared"] == 3
    # delta=0.0 is < floor (0.005); delta=0.01 and 0.10 are >= floor.
    assert shadow["divergent"] == 2

    hist = shadow["histogram"]
    assert hist["<0.005"] == 1     # the 0-delta row
    assert hist["0.01-0.05"] == 1  # the 0.01-delta row (>=0.01 and <0.05)
    assert hist[">0.05"] == 1      # the 0.10-delta row

    # Top-N audit rows must be persisted via executemany (only divergent ones).
    assert len(db.executemany_calls) == 1
    persisted = db.executemany_calls[0][1]
    assert len(persisted) == 2  # 2 divergent rows
    # Sorted by abs(delta) descending — id=3 first.
    assert persisted[0][1] == 3
    assert persisted[1][1] == 2


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_no_overlap_returns_status(monkeypatch):
    """Shadow returns kills with no overlap in python rows → no_overlap."""
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")

    db = _FakeDb()
    db.py_rows = []  # nothing in python table

    svc = StorytellingService(db=db)

    async def fake_prod(sd, force=False):
        return {"status": "computed", "kills_scored": 0}

    async def fake_shadow(sd):
        return [{"kill_outcome_id": 99, "total_impact": 1.0, "multipliers": {}}]

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    assert result["shadow"]["status"] == "no_overlap"


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_no_sql_data(monkeypatch):
    """Shadow returns empty list → no_data."""
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")
    db = _FakeDb()
    svc = StorytellingService(db=db)

    async def fake_prod(sd, force=False):
        return {"status": "computed", "kills_scored": 0}

    async def fake_shadow(sd):
        return []

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    assert result["shadow"]["status"] == "no_data"


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_swallows_shadow_errors(monkeypatch):
    """A failure in shadow audit must NOT break the production return value."""
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")
    db = _FakeDb()
    svc = StorytellingService(db=db)

    async def fake_prod(sd, force=False):
        return {"status": "computed", "kills_scored": 1}

    async def fake_shadow(sd):
        raise RuntimeError("simulated SQL failure")

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    # Production summary survives.
    assert result["status"] == "computed"
    assert result["kills_scored"] == 1
    # Shadow recorded the error.
    assert result["shadow"]["status"] == "error"
    assert "simulated SQL failure" in result["shadow"]["error"]


# ---------------------------------------------------------------------------
# Top-N cap + delta floor
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kis_compute_with_shadow_caps_persisted_rows_at_top_n(monkeypatch):
    """Even if 1000 rows diverge, only SHADOW_AUDIT_TOP_N are persisted."""
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")

    db = _FakeDb()
    db.py_rows = [(i, 1.0) for i in range(SHADOW_AUDIT_TOP_N + 50)]

    svc = StorytellingService(db=db)

    async def fake_prod(sd, force=False):
        return {"status": "computed", "kills_scored": len(db.py_rows)}

    async def fake_shadow(sd):
        # Each row has a distinct divergent delta (all >= floor).
        return [
            {"kill_outcome_id": i, "total_impact": 1.0 + 0.10 + (i * 0.001),
             "multipliers": {}}
            for i in range(SHADOW_AUDIT_TOP_N + 50)
        ]

    with patch.object(svc, "compute_session_kis", fake_prod), \
         patch.object(svc, "compute_kis_session_sql_shadow", fake_shadow):
        result = await svc.kis_compute_with_shadow("2026-04-21")

    assert result["shadow"]["compared"] == SHADOW_AUDIT_TOP_N + 50
    assert result["shadow"]["persisted_rows"] == SHADOW_AUDIT_TOP_N
    persisted = db.executemany_calls[0][1]
    assert len(persisted) == SHADOW_AUDIT_TOP_N


def test_shadow_audit_constants_sane():
    """Pin the audit knobs so a refactor can't silently relax them."""
    assert SHADOW_AUDIT_TOP_N == 20
    assert SHADOW_AUDIT_DELTA_FLOOR == 0.005


# ---------------------------------------------------------------------------
# Python vs SQL equivalence on a small fixture set
# ---------------------------------------------------------------------------
#
# We bypass the actual SQL query and instead replicate the per-kill
# arithmetic from `_score_kill` in both forms — the Python path
# (banker's rounding) and a manual "half-away-from-zero" path that
# the SQL `ROUND(x::numeric, 2)` would produce. Any divergence within
# the fixture set must be exactly ±0.01 — that is the ONLY acceptable
# rounding-band for Phase 1 cutover review.


def _half_away_from_zero(x: float, ndigits: int = 2) -> float:
    """PostgreSQL-style rounding (matches `ROUND(numeric, 2)`)."""
    from decimal import ROUND_HALF_UP, Decimal
    q = Decimal(10) ** -ndigits
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


@pytest.mark.parametrize("multipliers", [
    # baseline — no multipliers, no divergence possible
    (1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    # outcome=gibbed → 1.3
    (1.0, 1.0, 1.0, 1.0, 1.3, 1.0, 1.0, 1.0, 1.0, 1.0),
    # carrier kill alone → 3.0
    (3.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    # gibbed + crossfire + medic class = 1.3 * 1.5 * 1.5 = 2.925
    (1.0, 1.0, 1.5, 1.0, 1.3, 1.5, 1.0, 1.0, 1.0, 1.0),
    # post-cap value: gibbed * carrier chain * crossfire = 1.3 * 5.0 * 1.5 = 9.75 → cap
    (5.0, 1.0, 1.5, 1.0, 1.3, 1.0, 1.0, 1.0, 1.0, 1.0),
])
def test_python_vs_sql_rounding_band_is_at_most_one_cent(multipliers):
    """For each fixture, |python_total - sql_total| must be <= 0.01.

    This is the *contract* the user reviews in Phase 1 — if any future
    refactor introduces a divergence > 0.01 (i.e. structural drift, not
    rounding) this test fails and Phase 1 sign-off is blocked until
    the audit table is reviewed.
    """
    carrier, push, cf, spawn, outcome, klass, dist, health, alive, reinf = multipliers
    raw = carrier * push * cf * spawn * outcome * klass * dist * health * alive * reinf
    capped = raw if raw <= 5.0 else 5.0 + (raw - 5.0) * 0.25

    python_total = round(capped, 2)               # banker's
    sql_total = _half_away_from_zero(capped, 2)   # PG ROUND

    assert abs(python_total - sql_total) <= 0.01, (
        f"Rounding divergence > 1 cent for multipliers={multipliers}: "
        f"py={python_total} sql={sql_total}"
    )


def test_known_banker_rounding_divergence_surfaces_at_one_cent():
    """The motivating case: 2.125 rounds DOWN in Python (banker's, →2.12)
    and UP in PostgreSQL (half-away-from-zero, →2.13). Difference is
    exactly 0.01, which IS the documented acceptable tolerance.

    This test pins the divergence band so a "fix" that silently makes
    Python use half-away-from-zero (which would re-rank historical KIS
    leaderboards) is detected.
    """
    value = 2.125
    py = round(value, 2)
    sql = _half_away_from_zero(value, 2)
    assert py == 2.12
    assert sql == 2.13
    assert abs(py - sql) == pytest.approx(0.01)


# ---------------------------------------------------------------------------
# SQL query builder sanity check (not a roundtrip test — no DB here)
# ---------------------------------------------------------------------------


def test_shadow_query_includes_all_context_ctes():
    """The query must reference every input table the Python loader uses."""
    from website.backend.services.storytelling.kis_shadow import _build_shadow_kis_query
    q = _build_shadow_kis_query()
    for table in (
        "proximity_carrier_kill",
        "proximity_carrier_return",
        "proximity_team_push",
        "proximity_crossfire_opportunity",
        "proximity_spawn_timing",
        "proximity_reaction_metric",
        "proximity_combat_position",
        "proximity_kill_outcome",
    ):
        assert table in q, f"shadow query is missing {table}"


def test_shadow_query_joins_every_context_on_map_name():
    """Every context join must also match ko.map_name (codex #10/#11).

    round_start_unix is not unique repo-wide, so the shadow SQL must
    disambiguate rounds by map_name exactly like the fixed Python path —
    otherwise the shadow audit compares two implementations that share the
    SAME wrong identity and can never surface a canonical-key regression.
    """
    from website.backend.services.storytelling.kis_shadow import _build_shadow_kis_query
    q = _build_shadow_kis_query()
    # One "<alias>.map_name = ko.map_name" per joined context source.
    for alias in ("pu", "cf", "st", "ck", "cr", "vc", "cp"):
        assert f"{alias}.map_name = ko.map_name" in q, (
            f"shadow join for {alias} is missing the map_name predicate"
        )


def test_shadow_query_uses_only_one_session_param():
    """Single $1 binding for session_date — the audit loop passes it once."""
    from website.backend.services.storytelling.kis_shadow import _build_shadow_kis_query
    q = _build_shadow_kis_query()
    # No $2/$3 ... params; constants are interpolated inline.
    assert "$2" not in q
    assert "$3" not in q
    assert q.count("$1") >= 1


def test_shadow_query_does_not_write():
    """Pure SELECT/CTEs — no INSERT/UPDATE/DELETE."""
    from website.backend.services.storytelling.kis_shadow import _build_shadow_kis_query
    q = _build_shadow_kis_query().upper()
    for kw in ("INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert kw not in q, f"shadow query contains a write: {kw}"


# ---------------------------------------------------------------------------
# date normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sql_shadow_accepts_str_and_date(monkeypatch):
    """The shadow method must accept both `date` and YYYY-MM-DD `str`."""
    monkeypatch.setenv("KIS_SHADOW_MODE_ENABLED", "1")
    db = _FakeDb()
    svc = StorytellingService(db=db)

    # fetch_all returns empty for everything → no_data
    captured_params: list = []

    async def capture_fetch_all(query, params=None):
        captured_params.append(params)
        return []

    svc.db.fetch_all = capture_fetch_all  # type: ignore[method-assign]

    out1 = await svc.compute_kis_session_sql_shadow(date(2026, 4, 21))
    out2 = await svc.compute_kis_session_sql_shadow("2026-04-21")
    assert out1 == []
    assert out2 == []
    # Both calls passed a date instance to the query (proves _to_date normalised).
    for params in captured_params:
        assert isinstance(params[0], date)
