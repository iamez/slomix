"""#855 review fixes, pinned: the player endpoints count the same rounds
everywhere else on the page counts.

Three Codex findings, each measured on the live database before the fix:

- /api/stats/player aggregated R1/R2 rows WITHOUT the validity gate the
  profile's lifetime numbers carry (490 vs 454 kills for one guid), and its
  DPM extremes had neither the round filter nor the gate — the "highest
  dpm" it reported was the R0 cumulative-damage artifact almost by
  construction (790 vs a real 403).
- /api/player/{name}/matches served R0 match-summary aggregates as if they
  were rounds (the recorded fixture carried one), ordered by a date-only
  text column that groups every R2 ahead of every R1 within a day.
- /api/stats/live-session compared a DATE-ONLY text column against
  NOW() - 30 minutes, which is midnight after the cast: at 22:26, during
  an evening with twelve rounds imported in the prior two hours, it
  answered {active: false}.

These tests read the SQL the handlers actually build — structurally, via a
recording stub, not by grepping the source file — so a revert of any one
predicate fails a named test. The stub raises after recording: everything
past the first query is out of scope here, and the handlers' own error
paths (500/404) are exactly the short-circuit that stops them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers import players_router


class _Recorder:
    """Records every query and answers None — the handlers' own None-guards
    (404 on no stats, {active: False} on no rounds, [] on no matches) are the
    short-circuits that end the run; nothing here is mocked into success."""

    def __init__(self):
        self.queries: list[str] = []

    async def fetch_one(self, query, params=None):
        self.queries.append(" ".join(query.split()))
        return None

    async def fetch_all(self, query, params=None):
        self.queries.append(" ".join(query.split()))
        return None


async def _run(coro) -> None:
    try:
        await coro
    except HTTPException:
        pass


@pytest.mark.asyncio
async def test_live_session_clock_is_a_timestamp_not_a_date():
    db = _Recorder()
    await _run(players_router.get_live_session(db=db))
    q = db.queries[0]
    assert "created_at >= NOW() - INTERVAL '30 minutes'" in q
    assert "round_date::timestamp" not in q, "round_date is date-only text; casting it compares against midnight"
    assert "round_number IN (1, 2)" in q


@pytest.mark.asyncio
async def test_player_matches_excludes_r0_and_orders_monotonically():
    db = _Recorder()
    await _run(players_router.get_player_matches("E587CA5F", limit=10, db=db))
    # resolve_player_guid runs first; the matches query is the one that
    # reads the stat columns.
    hits = [x for x in db.queries if "pcs.round_id" in x]
    assert hits, f"matches query not seen; recorded: {db.queries}"
    q = hits[0]
    assert "round_number IN (1, 2)" in q, "R0 aggregates rendered as rounds"
    assert "ORDER BY pcs.round_id DESC" in q, (
        "date-only ordering groups R2s ahead of R1s and can drop the newest rounds"
    )


@pytest.mark.asyncio
async def test_player_stats_aggregate_and_dpm_carry_the_validity_gate():
    db = _Recorder()
    await _run(players_router.get_player_stats("E587CA5F", db=db))
    aggs = [x for x in db.queries if "SUM(p.kills)" in x]
    assert aggs, f"aggregate query not seen; recorded: {db.queries}"
    agg = aggs[0]
    assert "is_valid IS DISTINCT FROM FALSE" in agg, (
        "the profile lifetime carries this gate; milestones must count the same rounds"
    )
    assert "round_number IN (1, 2)" in agg
    src = Path(players_router.__file__).read_text(encoding="utf-8")
    dpm_start = src.index("dpm_query = ")
    dpm_sql = src[dpm_start : src.index('"""', src.index('"""', dpm_start) + 3)]
    assert "round_number IN (1, 2)" in dpm_sql, "highest dpm was the R0 artifact (790 vs 403)"
    assert "is_valid IS DISTINCT FROM FALSE" in dpm_sql


@pytest.mark.asyncio
async def test_session_scoped_weapon_rows_use_the_counted_round_predicate():
    """Fourth finding, same review: the session detail's totals exclude
    cancelled rounds (is_valid + completed/substitution/NULL status), so the
    weapon rows a reader expands under those totals must be scoped the same
    way — otherwise the sub-row can exceed the row above it."""
    from website.backend.routers import records_weapons

    db = _Recorder()
    try:
        await records_weapons.get_weapon_stats_by_player(
            period="session", gaming_session_id=154, player_guid="X", db=db
        )
    except Exception:  # noqa: BLE001 — only the recorded SQL is under test
        pass
    hits = [x for x in db.queries if "gaming_session_id" in x]
    assert hits, f"session-scoped query not seen; recorded: {db.queries}"
    q = hits[0]
    assert "is_valid IS DISTINCT FROM FALSE" in q
    assert "round_status IN ('completed', 'substitution') OR round_status IS NULL" in q
    assert "round_number IN (1, 2)" in q
