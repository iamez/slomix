"""
Tests for kill_assists visibility in session stats aggregator and session graph stats API.
"""
from __future__ import annotations

import pytest

from bot.services.session_stats_aggregator import SessionStatsAggregator
from website.backend.routers.sessions_router import get_session_graph_stats


class _AggDB:
    """Fake DB that returns column info via information_schema (PostgreSQL style)."""
    def __init__(self, columns):
        self.columns = columns
        self.last_query = None
        self.last_params = None

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        if "information_schema.columns" in q and "player_comprehensive_stats" in q:
            return [(col,) for col in self.columns]
        self.last_query = query
        self.last_params = params
        return []


class _GraphDB:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None
        self.last_params = None

    async def fetch_all(self, query, params):
        self.last_query = query
        self.last_params = params
        return self.rows


@pytest.mark.asyncio
async def test_aggregator_selects_kill_assists_when_column_exists():
    db = _AggDB(
        columns=[
            "player_name",
            "player_guid",
            "kills",
            "deaths",
            "kill_assists",
            "self_kills",
            "full_selfkills",
        ]
    )
    service = SessionStatsAggregator(db)

    await service.aggregate_all_player_stats([101, 102], "?,?")

    assert db.last_query is not None
    assert "SUM(p.kill_assists) as total_kill_assists" in db.last_query
    assert db.last_params == (101, 102)


@pytest.mark.asyncio
async def test_aggregator_defaults_kill_assists_when_column_missing():
    db = _AggDB(columns=["player_name", "player_guid", "kills", "deaths", "self_kills"])
    service = SessionStatsAggregator(db)

    await service.aggregate_all_player_stats([201], "?")

    assert db.last_query is not None
    assert "0 as total_kill_assists" in db.last_query
    assert db.last_params == (201,)


@pytest.mark.asyncio
async def test_session_graph_stats_exposes_kill_assists_and_updated_frag_formula():
    """Test that the session graph stats query includes kill_assists."""
    # Build a row matching the FULL query column order (31 columns):
    # player_name, round_number, kills, deaths, damage_given, damage_received,
    # time_played_seconds, revives_given, kill_assists, gibs, headshots, accuracy,
    # team_kills, self_kills, times_revived, time_dead_minutes, denied_playtime,
    # most_useful_kills, map_name, round_id, constructions, objectives_stolen,
    # dynamites_planted, dynamites_defused, useless_kills, double_kills,
    # triple_kills, quad_kills, mega_kills, bullets_fired, time_played_percent
    rows = [
        (
            "Player One",  # player_name
            1,             # round_number
            20,            # kills
            10,            # deaths
            3000,          # damage_given
            2000,          # damage_received
            600,           # time_played_seconds
            4,             # revives_given
            8,             # kill_assists
            5,             # gibs
            7,             # headshots
            35.0,          # accuracy
            0,             # team_kills
            0,             # self_kills
            3,             # times_revived
            2.5,           # time_dead_minutes
            120,           # denied_playtime
            6,             # most_useful_kills
            "supply",      # map_name
            9001,          # round_id
            0,             # constructions
            0,             # objectives_stolen
            0,             # dynamites_planted
            0,             # dynamites_defused
            1,             # useless_kills
            0,             # double_kills
            0,             # triple_kills
            0,             # quad_kills
            0,             # mega_kills
            100,           # bullets_fired
            85.0,          # time_played_percent
        )
    ]
    db = _GraphDB(rows)

    payload = await get_session_graph_stats("2026-02-12", db=db)

    assert db.last_query is not None
    assert "p.kill_assists" in db.last_query
    assert "r.round_number IN (1, 2)" in db.last_query
    assert payload["player_count"] == 1
    player = payload["players"][0]
    assert player["combat_defense"]["kill_assists"] == 8
