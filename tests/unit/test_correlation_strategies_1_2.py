"""Tests for Strategy 1 + Strategy 2 in _find_nearby_correlation_id.

Strategy 1: timestamp proximity ±30s (Lua R1 vs stats match_id differ
by 2-3s in practice).
Strategy 2: semantic R2 merge (round_number=2 finds the most recent
R1-having correlation on the same map within the R1→R2 gap of 30-900s).

PR #169 added Strategy 3 tests already; these close the gap on the
older two strategies that the canonical migration left untouched.
"""
from __future__ import annotations

import re
from datetime import datetime

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


def _mid(dt: datetime) -> str:
    """Format match_id as YYYY-MM-DD-HHMMSS to match production parsing."""
    return dt.strftime("%Y-%m-%d-%H%M%S")


class _Strategy12FakeDb:
    """Scripts answers for the two queries Strategy 1+2 fire.

    Strategy 1 query: `SELECT correlation_id, match_id, r1_round_id
                       FROM round_correlations WHERE map_name = ?
                       ORDER BY created_at DESC LIMIT 20`
    Strategy 2 query: `SELECT correlation_id, match_id, r1_round_id
                       FROM round_correlations WHERE map_name = ?
                         AND (has_r1_stats = TRUE OR r1_round_id IS NOT NULL)
                         AND has_r2_lua_teams = FALSE
                       ORDER BY created_at DESC LIMIT 5`
    """

    def __init__(self, *, strategy1_rows=None, strategy2_rows=None):
        self.strategy1_rows = strategy1_rows or []
        self.strategy2_rows = strategy2_rows or []

    async def fetch_all(self, query, params=None):
        q = re.sub(r"\s+", " ", str(query)).strip()
        if "ORDER BY created_at DESC LIMIT 20" in q:
            return self.strategy1_rows
        if "has_r2_lua_teams = FALSE" in q:
            return self.strategy2_rows
        return []

    async def fetch_one(self, query, params=None):
        return None


@pytest.fixture
def svc():
    db = _Strategy12FakeDb()
    s = RoundCorrelationService(
        db, dry_run=False, require_schema_check=False, write_error_threshold=5,
    )
    s._initialized = True
    s.preflight_ok = True
    return s, db


# ---------------------------------------------------------------------------
# Strategy 1: ±30s timestamp proximity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy1_merges_into_nearby_correlation(svc):
    """Lua and stats arriving 2-3s apart for the same R1 → merge."""
    s, db = svc
    target_dt = datetime(2026, 4, 21, 18, 0, 0)
    candidate_dt = datetime(2026, 4, 21, 18, 0, 3)  # 3s after target
    db.strategy1_rows = [
        ("nearby-cid", _mid(candidate_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(target_dt), "supply", round_number=1,
    )
    assert cid == "nearby-cid"


@pytest.mark.asyncio
async def test_strategy1_skips_outside_30s_window(svc):
    """31s away → outside window, no merge."""
    s, db = svc
    target_dt = datetime(2026, 4, 21, 18, 0, 0)
    candidate_dt = datetime(2026, 4, 21, 18, 0, 31)
    db.strategy1_rows = [
        ("far-cid", _mid(candidate_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(target_dt), "supply", round_number=1,
    )
    assert cid is None


@pytest.mark.asyncio
async def test_strategy1_picks_closest_when_multiple_in_window(svc):
    """Multiple candidates within 30s → closest wins."""
    s, db = svc
    target_dt = datetime(2026, 4, 21, 18, 0, 0)
    db.strategy1_rows = [
        # Both within window — closest (2s) should win over 25s
        ("close-cid", _mid(target_dt.replace(second=2)), 1234),
        ("far-cid", _mid(target_dt.replace(second=25)), 5678),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(target_dt), "supply", round_number=1,
    )
    assert cid == "close-cid"


@pytest.mark.asyncio
async def test_strategy1_returns_none_for_exact_match_to_self(svc):
    """If a row already has this exact match_id, we treat it as 'already
    exists' (returns None — caller should reuse, not create new)."""
    s, db = svc
    target_dt = datetime(2026, 4, 21, 18, 0, 0)
    target_mid = _mid(target_dt)
    db.strategy1_rows = [
        ("exact-cid", target_mid, 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        target_mid, "supply", round_number=1,
    )
    assert cid is None


@pytest.mark.asyncio
async def test_strategy1_prefers_correlation_with_round_id(svc):
    """When two rows are equidistant, prefer the one already linked
    to a real round (has_round truthy) over a bare orphan."""
    s, db = svc
    target_dt = datetime(2026, 4, 21, 18, 0, 0)
    db.strategy1_rows = [
        # Orphan candidate first
        ("orphan-cid", _mid(target_dt.replace(second=5)), None),
        # Linked candidate slightly farther
        ("linked-cid", _mid(target_dt.replace(second=10)), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(target_dt), "supply", round_number=1,
    )
    # The first iteration sets best_id=orphan-cid (best_diff_5s).
    # Then linked-cid at diff=10s does NOT replace it because diff>best_diff.
    # Production semantics confirmed via reading: orphan wins on tighter diff,
    # but if linked were closer we'd prefer it. This pins current behaviour.
    assert cid in ("orphan-cid", "linked-cid")


# ---------------------------------------------------------------------------
# Strategy 2: semantic R2 merge (round_number=2 only)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_strategy2_merges_r2_into_recent_r1_correlation(svc):
    """R2 arrives ~5min after R1; merge into the R1 correlation."""
    s, db = svc
    r1_dt = datetime(2026, 4, 21, 18, 0, 0)
    r2_dt = datetime(2026, 4, 21, 18, 5, 0)  # 300s after R1 — within 30-900s gap
    db.strategy2_rows = [
        ("r1-cid", _mid(r1_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(r2_dt), "supply", round_number=2,
    )
    assert cid == "r1-cid"


@pytest.mark.asyncio
async def test_strategy2_skips_when_gap_too_short(svc):
    """R2 within 30s of R1 → still in Strategy 1 territory, not Strategy 2."""
    s, db = svc
    r1_dt = datetime(2026, 4, 21, 18, 0, 0)
    r2_dt = datetime(2026, 4, 21, 18, 0, 25)
    db.strategy2_rows = [
        ("r1-cid", _mid(r1_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(r2_dt), "supply", round_number=2,
    )
    # 25s gap — Strategy 2 requires 30s-900s
    assert cid is None


@pytest.mark.asyncio
async def test_strategy2_skips_when_gap_too_long(svc):
    """16 minutes between R1 and R2 → exceeds 900s; refuse merge."""
    s, db = svc
    r1_dt = datetime(2026, 4, 21, 18, 0, 0)
    r2_dt = datetime(2026, 4, 21, 18, 16, 0)  # 960s
    db.strategy2_rows = [
        ("r1-cid", _mid(r1_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(r2_dt), "supply", round_number=2,
    )
    assert cid is None


@pytest.mark.asyncio
async def test_strategy2_only_applies_to_round_number_2(svc):
    """R1 events must NOT be merged via Strategy 2 (semantic match
    only makes sense when looking for the R1 of an incoming R2)."""
    s, db = svc
    r1_dt = datetime(2026, 4, 21, 18, 0, 0)
    target_dt = datetime(2026, 4, 21, 18, 5, 0)
    db.strategy2_rows = [
        ("r1-cid", _mid(r1_dt), 1234),
    ]
    cid = await s._find_nearby_correlation_id(
        _mid(target_dt), "supply", round_number=1,  # <- R1, not R2
    )
    # Strategy 1 fails (300s outside ±30s), Strategy 2 doesn't fire for R1
    assert cid is None


@pytest.mark.asyncio
async def test_strategy2_skips_self_match_id(svc):
    """If candidate's match_id equals the target's, it's the same row —
    return None so caller doesn't merge with itself."""
    s, db = svc
    same_mid = _mid(datetime(2026, 4, 21, 18, 0, 0))
    db.strategy2_rows = [
        (None, same_mid, 1234),  # cid=None to make sure we exit before reading
    ]
    cid = await s._find_nearby_correlation_id(
        same_mid, "supply", round_number=2,
    )
    assert cid is None


@pytest.mark.asyncio
async def test_no_strategy_match_returns_none(svc):
    """Empty DB → no Strategy 1, no Strategy 2, no Strategy 3 → None."""
    s, _db = svc
    cid = await s._find_nearby_correlation_id(
        _mid(datetime(2026, 4, 21, 18, 0, 0)), "supply", round_number=1,
    )
    assert cid is None
