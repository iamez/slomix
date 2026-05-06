"""Strategy 3 (round_id linkage) priority + tolerance regression tests.

Reproduces the back-to-back same-map cross-pollination scenario that
forced the Strategy 3 rewrite (round_end_unix priority over round_start_unix,
both clamped to ±90s). See bot/services/round_correlation_service.py
_find_nearby_correlation_id for the production code under test.
"""
from __future__ import annotations

import re

import pytest

from bot.services.round_correlation_service import RoundCorrelationService


def _select_round_with_strategy3_priority(rounds, target_unix):
    """Pure-Python mirror of the Strategy 3 SQL.

    Returns (id, priority, dist) of the best match or None. Mirrors:
        ORDER BY priority ASC, dist ASC LIMIT 1
    so the test fails loud if SQL semantics drift.
    """
    candidates = []
    for r in rounds:
        rsu = r["round_start_unix"]
        reu = r.get("round_end_unix")
        if rsu is None:
            continue
        end_in = reu is not None and abs(reu - target_unix) <= 90
        start_in = abs(rsu - target_unix) <= 90
        if not (end_in or start_in):
            continue
        if end_in:
            priority = 1
        elif start_in:
            priority = 2
        else:
            priority = 99
        dist = min(abs(rsu - target_unix), abs((reu or 9_999_999) - target_unix))
        candidates.append((priority, dist, r["id"]))
    if not candidates:
        return None
    candidates.sort()
    p, d, rid = candidates[0]
    return rid, p, d


class _Strategy3FakeDb:
    """Just enough fake DB to drive _find_nearby_correlation_id via Strategy 3.

    We force Strategy 1 to find nothing (no nearby correlations), Strategy 2
    is round_number-gated, and Strategy 3 queries `rounds` with the priority
    expression. We answer that query by running the equivalent Python sort
    against an in-memory rounds fixture so the test asserts the exact SQL
    semantics, not just "some row came back".
    """

    def __init__(self, rounds, correlations):
        self.rounds = rounds
        self.correlations = correlations  # round_id -> correlation_id

    async def fetch_all(self, query, params=None):
        # Strategy 1 nearby-correlation lookup → return empty so we proceed
        # to Strategy 3.
        if "FROM round_correlations" in str(query) and "ORDER BY created_at DESC" in str(query):
            return []
        return []

    async def fetch_one(self, query, params=None):
        q = re.sub(r"\s+", " ", str(query)).strip()
        # Strategy 3 rounds query — first SELECT with FROM rounds
        if q.startswith("SELECT id, CASE WHEN round_end_unix IS NOT NULL"):
            target_unix = params[0]
            map_name = params[4]
            round_number = params[5]
            filtered = [
                r for r in self.rounds
                if r["map_name"] == map_name and r["round_number"] == round_number
            ]
            picked = _select_round_with_strategy3_priority(filtered, target_unix)
            if picked is None:
                return None
            return (picked[0], picked[1], picked[2])
        # Correlation lookup by r1_round_id / r2_round_id
        if "SELECT correlation_id FROM round_correlations" in q:
            rid = params[0]
            cid = self.correlations.get(rid)
            return (cid,) if cid else None
        return None


@pytest.fixture
def svc():
    db = _Strategy3FakeDb(rounds=[], correlations={})
    s = RoundCorrelationService(
        db,
        dry_run=False,
        require_schema_check=False,
        write_error_threshold=3,
    )
    return s, db


@pytest.mark.asyncio
async def test_strategy3_picks_correct_match_in_back_to_back_session(svc):
    """Two te_escape2 R2 rounds 8 minutes apart (sequenced game day).

    Proximity event arrives with target_dt at round_end_unix of the SECOND
    match. Strategy 3 must pick round id=2002 (the second match), not 2001.
    """
    s, db = svc
    db.rounds = [
        # Match 1 R2: started 17:00:30, ended 17:05:00
        {"id": 2001, "map_name": "te_escape2", "round_number": 2,
         "round_start_unix": 1_700_000_030, "round_end_unix": 1_700_000_300},
        # Match 2 R2: started 17:13:00, ended 17:17:30 (8 min after match 1)
        {"id": 2002, "map_name": "te_escape2", "round_number": 2,
         "round_start_unix": 1_700_000_780, "round_end_unix": 1_700_001_050},
    ]
    db.correlations = {2002: "match2-cid"}

    # Proximity flushes ~2s after match 2 round end. We build match_id from
    # the SAME naive-local datetime → unix conversion as production so the
    # round-trip target_unix value matches our fixture.
    from datetime import datetime
    target_unix = 1_700_001_052
    match_id = datetime.fromtimestamp(target_unix).strftime("%Y-%m-%d-%H%M%S")
    cid = await s._find_nearby_correlation_id(match_id, "te_escape2", round_number=2)
    assert cid == "match2-cid", "Strategy 3 picked wrong match in back-to-back scenario"


@pytest.mark.asyncio
async def test_strategy3_skips_when_target_outside_90s_window(svc):
    """Target ±91s from round_start AND ±91s from round_end → no match.

    Guards against the old ±1800s window that caused false-merges.
    """
    s, db = svc
    db.rounds = [
        {"id": 3001, "map_name": "supply", "round_number": 1,
         "round_start_unix": 1_700_010_000, "round_end_unix": 1_700_010_240},
    ]
    db.correlations = {3001: "supply-cid"}

    from datetime import datetime
    # Build match_id from naive-local fromtimestamp so the production
    # round-trip (strptime → timestamp) yields target_unix exactly.
    out_of_window_target = 1_700_009_900  # round_start - 100 → outside ±90s
    match_id = datetime.fromtimestamp(out_of_window_target).strftime("%Y-%m-%d-%H%M%S")
    cid = await s._find_nearby_correlation_id(match_id, "supply", round_number=1)
    assert cid is None, "Strategy 3 false-merged outside ±90s window"


@pytest.mark.asyncio
async def test_strategy3_prefers_round_end_over_round_start(svc):
    """Target is within ±90s of A's round_start AND B's round_end.

    A: round_start_unix close (priority 2), round_end_unix far (no match).
    B: round_end_unix close (priority 1), round_start_unix far (no match).
    Strategy 3 must pick B (priority 1 beats priority 2).
    """
    s, db = svc
    target_unix = 1_700_020_000
    db.rounds = [
        # A: round_start within ±90s of target (priority 2)
        {"id": 4001, "map_name": "frostbite", "round_number": 2,
         "round_start_unix": target_unix - 30, "round_end_unix": target_unix - 500},
        # B: round_end within ±90s of target (priority 1)
        {"id": 4002, "map_name": "frostbite", "round_number": 2,
         "round_start_unix": target_unix - 500, "round_end_unix": target_unix - 10},
    ]
    db.correlations = {4001: "a-cid", 4002: "b-cid"}

    from datetime import datetime
    match_id = datetime.fromtimestamp(target_unix).strftime("%Y-%m-%d-%H%M%S")
    cid = await s._find_nearby_correlation_id(match_id, "frostbite", round_number=2)
    assert cid == "b-cid", "Strategy 3 must prefer round_end_unix match (priority 1)"
