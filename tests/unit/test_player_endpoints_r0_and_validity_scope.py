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
    assert "is_bot_round IS DISTINCT FROM TRUE" in q, (
        "the totals row above excludes bot rounds; the expanded weapons must too"
    )
    assert "round_status IN ('completed', 'substitution') OR round_status IS NULL" in q
    assert "round_number IN (1, 2)" in q


class _Dispatch(_Recorder):
    """Answers by query content; everything unmatched stays None."""

    def __init__(self, rules):
        super().__init__()
        self._rules = rules

    async def fetch_one(self, query, params=None):
        await super().fetch_one(query, params)
        for needle, row in self._rules:
            if needle in query:
                return row
        return None


@pytest.mark.asyncio
async def test_session_leaderboard_ids_carry_validity_and_bot_gates():
    """Round two of the same review: the aggregator sums every id this
    select hands it, so an invalid or bot round changed the top three."""
    from website.backend.routers import sessions_router

    db = _Recorder()
    try:
        await sessions_router.get_session_leaderboard(limit=5, session_id=154, db=db)
    except Exception:  # noqa: BLE001 — only the recorded SQL is under test
        pass
    hits = [x for x in db.queries if "SELECT id FROM rounds" in x]
    assert hits, f"id select not seen; recorded: {db.queries}"
    q = hits[0]
    assert "is_valid IS DISTINCT FROM FALSE" in q
    assert "is_bot_round IS DISTINCT FROM TRUE" in q
    assert "round_status IN ('completed', 'substitution') OR round_status IS NULL" in q


@pytest.mark.asyncio
async def test_composite_session_scope_excludes_cancelled_rounds():
    """The story endpoints around the composite panel exclude cancelled
    rounds; a composite computed with one disagreed with the same story's
    scoreboard (sessions 153, 84, 83, 80 carry rounds that pass the
    validity+bot gates and fail the status gate)."""
    from website.backend.routers import skill_router

    db = _Recorder()
    try:
        await skill_router.get_composite_stats(gaming_session_id=154, db=db)
    except Exception:  # noqa: BLE001 — only the recorded SQL is under test
        pass
    scoped = [x for x in db.queries if "gaming_session_id = $1" in x]
    assert scoped, f"session-scoped queries not seen; recorded: {db.queries}"
    # ⛔ Counted, not searched: the big CTE query repeats the round_set
    # fragment several times AND carries pcs_where — a membership check
    # found the pcs gate and declared the whole query gated, so a mutation
    # that stripped the round_set gate SURVIVED. Every id-subselect must
    # bring its own gate, plus exactly one on the pcs scope.
    big = next(q for q in scoped if "round_id IN (SELECT id FROM rounds" in q)
    subselects = big.count("IN (SELECT id FROM rounds")
    gates = big.count("round_status IN ('completed', 'substitution')")
    assert subselects > 0
    assert gates == subselects + 1, (
        f"{subselects} id-subselects but {gates} status gates (want one per subselect plus one on the pcs scope)"
    )


@pytest.mark.asyncio
async def test_zero_kill_player_with_rounds_is_not_a_404():
    agg_row = (0, 0, 0, 0, 3, 0, 0, "2026-08-31")  # kills..wins, last_seen
    db = _Dispatch([("SUM(p.kills)", agg_row), ("max_dpm", (0.0, 0.0))])
    out = await players_router.get_player_stats("supportonly", db=db)
    assert out["stats"]["kills"] == 0
    assert out["stats"]["games"] == 3
    # And the zero DPM extreme is a VALUE, not "no qualifying round".
    assert out["stats"]["highest_dpm"] == 0
    assert out["stats"]["lowest_dpm"] == 0
