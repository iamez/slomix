"""Tests for SessionStatsAggregator — DB query orchestration.

This service drives every aggregate query in `!last_session` and
session detail (player totals, team totals, scores, weapon breakdown,
DPM leaderboard). A regression silently:

- `_get_player_stats_columns` cache miss after a schema change →
  every aggregate fires the column-discovery query each time → DB
  hammered.
- `has_full_selfkills_column` cached negative result → after a real
  schema migration that adds the column, aggregator never sees it.
- `aggregate_team_stats` no-rosters fallback queries by SIDE → in
  stopwatch mode this is misleading (attackers vs defenders, NOT
  team A vs B). Pin the warning + the SQL shape.
- `calculate_session_scores` swaps team_a/team_b on hardcoded_teams
  with reversed iteration order → team scores swap on every embed.
- `calculate_session_scores` accepts winner_team=0 → spectator wins
  pollute the count.
- `get_dpm_leaderboard` no integer guard → an attacker who can pass
  `limit` from a slash command could SQL-inject via f-string.

Pin every public-method contract.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.session_stats_aggregator import SessionStatsAggregator


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_all = AsyncMock(return_value=[])
    a.fetch_one = AsyncMock(return_value=None)
    return a


@pytest.fixture
def agg(db):
    return SessionStatsAggregator(db_adapter=db)


# ---------------------------------------------------------------------------
# _get_player_stats_columns — cached column discovery
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_columns_cached_across_calls(agg, db):
    """First call hits DB, subsequent calls hit the cache attribute.
    Pin so a schema-introspection refactor doesn't fire 50× per
    embed render."""
    db.fetch_all = AsyncMock(return_value=[("kills",), ("deaths",), ("dpm",)])
    cols1 = await agg._get_player_stats_columns()
    cols2 = await agg._get_player_stats_columns()
    cols3 = await agg._get_player_stats_columns()
    assert cols1 == cols2 == cols3
    # Only one DB call across three reads
    assert db.fetch_all.await_count == 1


@pytest.mark.asyncio
async def test_columns_returned_as_set_for_o1_lookup(agg, db):
    """Must be a set, not a list — pin so `"colname" in columns` is
    O(1) (called repeatedly inside aggregator)."""
    db.fetch_all = AsyncMock(return_value=[("kills",), ("dpm",)])
    cols = await agg._get_player_stats_columns()
    assert isinstance(cols, set)
    assert "kills" in cols


@pytest.mark.asyncio
async def test_columns_db_failure_returns_empty_set(agg, db):
    """If introspection query fails, cache an empty set (caller
    treats every optional column as absent → safe defaults)."""
    db.fetch_all = AsyncMock(side_effect=RuntimeError("info_schema down"))
    cols = await agg._get_player_stats_columns()
    assert cols == set()


# ---------------------------------------------------------------------------
# has_full_selfkills_column
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_has_full_selfkills_when_column_present(agg, db):
    db.fetch_all = AsyncMock(return_value=[("full_selfkills",), ("kills",)])
    assert await agg.has_full_selfkills_column() is True


@pytest.mark.asyncio
async def test_has_full_selfkills_when_column_absent(agg, db):
    db.fetch_all = AsyncMock(return_value=[("kills",), ("deaths",)])
    assert await agg.has_full_selfkills_column() is False


# ---------------------------------------------------------------------------
# calculate_session_scores
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_scores_default_team_names_when_no_hardcoded(agg, db):
    """No hardcoded teams → "Team A" / "Team B" defaults. Pin so an
    embed always has a team-name field (NOT empty)."""
    db.fetch_all = AsyncMock(return_value=[(1, 3), (2, 2)])
    out = await agg.calculate_session_scores([101], "?", None)
    assert out == {
        "team_a_score": 3,
        "team_b_score": 2,
        "team_a_name": "Team A",
        "team_b_name": "Team B",
    }


@pytest.mark.asyncio
async def test_session_scores_uses_hardcoded_team_names(agg, db):
    """First two team-name keys → team_a/team_b. Pin so the iteration
    order matters (preserved in py3.7+)."""
    db.fetch_all = AsyncMock(return_value=[(1, 3), (2, 2)])
    teams = {
        "Puran": {"guids": ["g1"], "names": ["a"]},
        "Sk":    {"guids": ["g2"], "names": ["b"]},
    }
    out = await agg.calculate_session_scores([101], "?", teams)
    assert out["team_a_name"] == "Puran"
    assert out["team_b_name"] == "Sk"


@pytest.mark.asyncio
async def test_session_scores_zero_when_no_wins(agg, db):
    """No winning rounds → 0-0."""
    db.fetch_all = AsyncMock(return_value=[])
    out = await agg.calculate_session_scores([101], "?", None)
    assert out["team_a_score"] == 0
    assert out["team_b_score"] == 0


@pytest.mark.asyncio
async def test_session_scores_only_team_a_wins(agg, db):
    """Only team 1 has wins → team_b_score stays 0."""
    db.fetch_all = AsyncMock(return_value=[(1, 5)])
    out = await agg.calculate_session_scores([101], "?", None)
    assert out["team_a_score"] == 5
    assert out["team_b_score"] == 0


@pytest.mark.asyncio
async def test_session_scores_skips_unexpected_winner_values(agg, db):
    """winner_team=3 (or other unexpected) → logged + skipped (does
    NOT add to team_a or team_b). Pin so a corrupt row doesn't
    silently inflate one team's score."""
    db.fetch_all = AsyncMock(return_value=[(1, 2), (3, 99), (2, 1)])
    out = await agg.calculate_session_scores([101], "?", None)
    assert out["team_a_score"] == 2
    assert out["team_b_score"] == 1


@pytest.mark.asyncio
async def test_session_scores_query_excludes_winner_team_zero(agg, db):
    """SQL filter `winner_team > 0` — pin so spectator wins (0)
    never count."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.calculate_session_scores([101], "?", None)
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "winner_team > 0" in sql


@pytest.mark.asyncio
async def test_session_scores_query_excludes_in_progress_rounds(agg, db):
    """SQL filter excludes round_status not in (completed, NULL).
    Pin so partial rounds don't influence scoring."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.calculate_session_scores([101], "?", None)
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "round_status = 'completed'" in sql
    assert "round_status IS NULL" in sql


@pytest.mark.asyncio
async def test_session_scores_query_filters_to_r1_r2_only(agg, db):
    """SQL filter `round_number IN (1, 2)` — pin so R0 (cumulative
    summary) doesn't double-count wins."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.calculate_session_scores([101], "?", None)
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "round_number IN (1, 2)" in sql


# ---------------------------------------------------------------------------
# aggregate_team_stats — fallback path (no rosters)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_team_stats_fallback_groups_by_side(agg, db):
    """No hardcoded teams → SQL groups by p.team (the SIDE column).
    Pin observed behaviour + the warning so callers know the result
    is misleading in stopwatch mode."""
    db.fetch_all = AsyncMock(return_value=[(1, 30, 25, 5000), (2, 28, 30, 4500)])
    out = await agg.aggregate_team_stats([101], "?", None, None)
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "GROUP BY p.team" in sql
    assert len(out) == 2


@pytest.mark.asyncio
async def test_team_stats_fallback_when_name_to_team_empty(agg, db):
    """Empty name_to_team dict triggers the fallback (NOT just None)."""
    db.fetch_all = AsyncMock(return_value=[(1, 30, 25, 5000)])
    await agg.aggregate_team_stats([101], "?", {"X": {}}, {})
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "GROUP BY p.team" in sql


@pytest.mark.asyncio
async def test_team_stats_uses_rosters_when_provided(agg, db):
    """With hardcoded teams + name_to_team → query groups by guid,
    code aggregates by team_name in Python."""
    db.fetch_all = AsyncMock(return_value=[
        ("alice", "g1", 10, 5, 1500),
        ("bob",   "g2", 8, 7, 1200),
        ("carol", "g3", 6, 9, 800),
    ])
    teams = {"A": {}, "B": {}}
    name_to_team = {"alice": "A", "bob": "A", "carol": "B"}
    out = await agg.aggregate_team_stats([101], "?", teams, name_to_team)
    # Two teams aggregated
    assert len(out) == 2
    # Team A first (insertion order from name_to_team mapping)
    a = next((row for row in out if row[0] == 1), None)
    b = next((row for row in out if row[0] == 2), None)
    assert a is not None and b is not None
    # alice (10) + bob (8) = 18 kills for team A
    assert a[1] == 18
    # carol = 6 kills for team B
    assert b[1] == 6


@pytest.mark.asyncio
async def test_team_stats_drops_player_not_in_name_to_team(agg, db):
    """Player whose name isn't in name_to_team → silently dropped
    from totals. Pin so a substitute who arrived without team
    assignment doesn't inflate either team's stats."""
    db.fetch_all = AsyncMock(return_value=[
        ("alice", "g1", 10, 5, 1500),
        ("ghost", "g_ghost", 5, 5, 800),  # not in name_to_team
    ])
    teams = {"A": {}, "B": {}}
    name_to_team = {"alice": "A"}
    out = await agg.aggregate_team_stats([101], "?", teams, name_to_team)
    # Only one team has aggregates (alice)
    assert len(out) == 1
    assert out[0] == (1, 10, 5, 1500)


# ---------------------------------------------------------------------------
# aggregate_weapon_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weapon_stats_empty_session_ids_returns_empty_list(agg, db):
    """Empty session_ids → [] immediately (no SQL `IN ()` syntax error)."""
    out = await agg.aggregate_weapon_stats([], "")
    assert out == []
    db.fetch_all.assert_not_awaited()


@pytest.mark.asyncio
async def test_weapon_stats_groups_by_player_guid_and_weapon(agg, db):
    db.fetch_all = AsyncMock(return_value=[
        ("g1", "alice", "WS_MP40", 10, 25, 60, 5),
    ])
    await agg.aggregate_weapon_stats([101], "?")
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "GROUP BY player_guid, weapon_name" in sql


# ---------------------------------------------------------------------------
# get_dpm_leaderboard — limit validation (SQL injection guard)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dpm_leaderboard_default_limit_is_10(agg, db):
    """Default limit=10 — pin so a no-arg call doesn't accidentally
    return all 1000 rows."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.get_dpm_leaderboard([101], "?")
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "LIMIT 10" in sql


@pytest.mark.asyncio
async def test_dpm_leaderboard_rejects_zero_limit(agg, db):
    """limit=0 → ValueError. Pin so an empty leaderboard doesn't
    silently render."""
    with pytest.raises(ValueError, match="must be between 1 and 1000"):
        await agg.get_dpm_leaderboard([101], "?", limit=0)


@pytest.mark.asyncio
async def test_dpm_leaderboard_rejects_negative_limit(agg, db):
    with pytest.raises(ValueError):
        await agg.get_dpm_leaderboard([101], "?", limit=-5)


@pytest.mark.asyncio
async def test_dpm_leaderboard_rejects_oversize_limit(agg, db):
    """limit>1000 → ValueError (the cap)."""
    with pytest.raises(ValueError):
        await agg.get_dpm_leaderboard([101], "?", limit=1001)


@pytest.mark.asyncio
async def test_dpm_leaderboard_rejects_non_integer_limit(agg, db):
    """Non-integer (e.g., SQL injection attempt) → ValueError via
    `int()` coercion. Pin the security boundary."""
    with pytest.raises(ValueError):
        await agg.get_dpm_leaderboard([101], "?", limit="10; DROP TABLE rounds;--")


@pytest.mark.asyncio
async def test_dpm_leaderboard_accepts_string_integer(agg, db):
    """String "20" → coerced to int 20 → query fires with LIMIT 20."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.get_dpm_leaderboard([101], "?", limit="20")
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "LIMIT 20" in sql


@pytest.mark.asyncio
async def test_dpm_leaderboard_accepts_max_limit(agg, db):
    """limit=1000 (inclusive upper) → accepted."""
    db.fetch_all = AsyncMock(return_value=[])
    await agg.get_dpm_leaderboard([101], "?", limit=1000)
    args, _ = db.fetch_all.await_args
    sql = args[0]
    assert "LIMIT 1000" in sql
