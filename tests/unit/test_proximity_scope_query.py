"""Codex §16/§17 PX-2: several proximity endpoints silently ignored
round_number/round_start_unix (the params didn't even exist in the
function signature, so a caller's exact-round request was dropped), and
/proximity/weapon-accuracy's per-weapon breakdown ignored map_name/
range_days entirely while the leaderboard in the SAME response respected
them. This locks in the fix: round scoping now reaches the SQL for every
affected endpoint, and weapon-accuracy's two queries share one scope.
"""
from __future__ import annotations

import pytest

from website.backend.routers.proximity_helpers import ProximityQueryBuilder

# ── ProximityQueryBuilder.with_round ────────────────────────────────────


def test_with_round_adds_both_filters_when_provided():
    where_sql, params = (
        ProximityQueryBuilder()
        .with_round(2, 1_700_000_000)
        .build()
    )
    assert "round_number = $1" in where_sql
    assert "round_start_unix = $2" in where_sql
    assert params == (2, 1_700_000_000)


def test_with_round_omits_round_start_unix_when_zero():
    """round_start_unix=0 means 'not provided' — matches
    _build_proximity_where_clause's `> 0` check."""
    where_sql, params = (
        ProximityQueryBuilder()
        .with_round(1, 0)
        .build()
    )
    assert "round_number = $1" in where_sql
    assert "round_start_unix" not in where_sql
    assert params == (1,)


def test_with_round_noop_when_neither_provided():
    where_sql, params = ProximityQueryBuilder().with_round(None, None).build()
    assert where_sql == ""
    assert params == ()


def test_with_round_rejects_negative_round_number():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        ProximityQueryBuilder().with_round(-1, None)
    assert exc_info.value.status_code == 400


def test_with_round_rejects_negative_round_start_unix():
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        ProximityQueryBuilder().with_round(None, -5)
    assert exc_info.value.status_code == 400


def test_with_round_composes_with_other_filters_renumbering_placeholders():
    where_sql, params = (
        ProximityQueryBuilder()
        .with_map_name("supply")
        .with_round(1, 1_700_000_000)
        .build()
    )
    assert "map_name = $1" in where_sql
    assert "round_number = $2" in where_sql
    assert "round_start_unix = $3" in where_sql
    assert params == ("supply", 1, 1_700_000_000)


# ── Router-level: round scoping now reaches the SQL ─────────────────────


class _CapturingDB:
    def __init__(self, all_rows=None, one_row=None):
        self.all_rows = all_rows if all_rows is not None else []
        self.one_row = one_row
        self.fetch_all_calls: list[tuple[str, tuple]] = []
        self.fetch_one_calls: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        self.fetch_all_calls.append((" ".join(str(query).split()), tuple(params or ())))
        return self.all_rows

    async def fetch_one(self, query, params=None):
        self.fetch_one_calls.append((" ".join(str(query).split()), tuple(params or ())))
        return self.one_row

    async def fetch_val(self, query, params=None):
        return True  # _table_column_exists probes


@pytest.mark.asyncio
async def test_support_summary_round_scope_reaches_sql():
    from website.backend.routers.proximity_support import get_proximity_support_summary

    db = _CapturingDB(one_row=(0, 0, 0, 0))
    await get_proximity_support_summary(
        round_number=2, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_one_calls, "no query executed"
    query, params = db.fetch_one_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query
    assert 2 in params
    assert 1_700_000_000 in params


@pytest.mark.asyncio
async def test_movement_stats_round_scope_reaches_sql():
    from website.backend.routers.proximity_support import get_proximity_movement_stats

    db = _CapturingDB()
    result = await get_proximity_movement_stats(
        round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query
    assert result["scope"]["round_number"] == 1
    assert result["scope"]["round_start_unix"] == 1_700_000_000


@pytest.mark.asyncio
async def test_movement_stats_scope_normalizes_zero_round_start_unix_to_none():
    """round_start_unix=0 applies no SQL filter (with_round() treats it as
    "not provided") — the echoed scope must say None, not 0, or it claims
    a round-scoped response the executed SQL isn't (Copilot review on #529)."""
    from website.backend.routers.proximity_support import get_proximity_movement_stats

    db = _CapturingDB()
    result = await get_proximity_movement_stats(round_start_unix=0, db=db)
    query, _ = db.fetch_all_calls[0]
    assert "round_start_unix" not in query
    assert result["scope"]["round_start_unix"] is None


@pytest.mark.asyncio
async def test_kill_outcomes_player_stats_round_scope_reaches_sql():
    from website.backend.routers.proximity_dashboard import (
        get_proximity_kill_outcomes_player_stats,
    )

    db = _CapturingDB()
    await get_proximity_kill_outcomes_player_stats(
        round_number=3, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


@pytest.mark.asyncio
async def test_hit_regions_by_weapon_round_scope_reaches_sql():
    from website.backend.routers.proximity_positions import (
        get_proximity_hit_regions_by_weapon,
    )

    db = _CapturingDB()
    await get_proximity_hit_regions_by_weapon(
        player_guid="ABC12345", round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


@pytest.mark.asyncio
async def test_hit_regions_headshot_rates_round_scope_reaches_sql():
    from website.backend.routers.proximity_positions import (
        get_proximity_hit_regions_headshot_rates,
    )

    db = _CapturingDB()
    await get_proximity_hit_regions_headshot_rates(
        round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


@pytest.mark.asyncio
async def test_combat_positions_kill_lines_round_scope_reaches_sql():
    from website.backend.routers.proximity_positions import (
        get_proximity_combat_positions_kill_lines,
    )

    db = _CapturingDB()
    await get_proximity_combat_positions_kill_lines(
        map_name="supply", round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


@pytest.mark.asyncio
async def test_combat_positions_danger_zones_round_scope_reaches_sql():
    from website.backend.routers.proximity_positions import (
        get_proximity_combat_positions_danger_zones,
    )

    db = _CapturingDB()
    await get_proximity_combat_positions_danger_zones(
        map_name="supply", round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_all_calls
    query, params = db.fetch_all_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


@pytest.mark.asyncio
async def test_combat_position_stats_round_scope_reaches_sql():
    from website.backend.routers.proximity_positions import (
        get_proximity_combat_position_stats,
    )

    db = _CapturingDB(one_row=(0, 0, 0, 0, 0))
    await get_proximity_combat_position_stats(
        round_number=1, round_start_unix=1_700_000_000, db=db,
    )
    assert db.fetch_one_calls, "no summary query executed"
    query, params = db.fetch_one_calls[0]
    assert "round_number = $" in query
    assert "round_start_unix = $" in query


# ── weapon-accuracy: unified scope between leaderboard + breakdown ──────


@pytest.mark.asyncio
async def test_weapon_accuracy_breakdown_respects_map_name_and_range_days():
    from website.backend.routers.proximity_scoring import get_proximity_weapon_accuracy

    db = _CapturingDB()
    await get_proximity_weapon_accuracy(
        range_days=7, player_guid="ABC12345", map_name="supply", db=db,
    )
    assert len(db.fetch_all_calls) == 2, "expected leaderboard + breakdown queries"
    _, leader_params = db.fetch_all_calls[0]
    breakdown_query, breakdown_params = db.fetch_all_calls[1]

    assert "map_name = $" in breakdown_query, (
        "weapon_breakdown query must filter by map_name like the leaderboard does"
    )
    assert "session_date >=" in breakdown_query or "created_at >=" in breakdown_query, (
        "weapon_breakdown query must respect range_days like the leaderboard does"
    )
    assert "supply" in breakdown_params
    assert 7 in breakdown_params
    # Leaderboard scope values must also be present (both queries share scope).
    assert "supply" in leader_params
    assert 7 in leader_params


@pytest.mark.asyncio
async def test_weapon_accuracy_breakdown_keeps_its_own_lower_shots_floor():
    """The breakdown intentionally uses shots_fired > 0 (not >= 10 like the
    leaderboard) — a lightly-used weapon for an already-selected player is
    still worth showing. Only the SCOPE (map/date) must be unified, not
    this threshold."""
    from website.backend.routers.proximity_scoring import get_proximity_weapon_accuracy

    db = _CapturingDB()
    await get_proximity_weapon_accuracy(player_guid="ABC12345", db=db)
    leader_query, _ = db.fetch_all_calls[0]
    breakdown_query, _ = db.fetch_all_calls[1]
    assert "shots_fired >= 10" in leader_query
    assert "shots_fired > 0" in breakdown_query
    assert "shots_fired >= 10" not in breakdown_query


@pytest.mark.asyncio
async def test_weapon_accuracy_no_breakdown_query_without_player_guid():
    from website.backend.routers.proximity_scoring import get_proximity_weapon_accuracy

    db = _CapturingDB()
    result = await get_proximity_weapon_accuracy(map_name="supply", db=db)
    assert len(db.fetch_all_calls) == 1, "no player_guid -> no breakdown query"
    assert result["weapon_breakdown"] == []
