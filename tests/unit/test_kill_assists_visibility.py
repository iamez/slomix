from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.services.session_stats_aggregator import SessionStatsAggregator
from bot.services.session_view_handlers import SessionViewHandlers
from website.backend.routers.api import get_session_graph_stats


class _AggDB:
    def __init__(self, columns):
        self.columns = columns
        self.last_query = None
        self.last_params = None

    async def fetch_all(self, query, params=None):
        q = " ".join(query.split())
        if q.startswith("PRAGMA table_info(player_comprehensive_stats)"):
            return [(i, col, None, None, None, None) for i, col in enumerate(self.columns)]
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


class _ObjectivesDB:
    async def fetch_all(self, query, params):
        if "SUM(revives_given)" in query:
            return [("guid-1", "Player One", 6)]

        return [
            (
                "Player One",  # clean_name
                500,           # xp
                4,             # kill_assists
                1,             # objectives_stolen
                0,             # objectives_returned
                2,             # dynamites_planted
                1,             # dynamites_defused
                3,             # times_revived
                1, 0, 0, 0, 0,  # multi-kills buckets
                30,            # denied_playtime
                5,             # most_useful_kills
                1,             # useless_kills
                2,             # gibs
                7,             # killing_spree_best
                2,             # death_spree_worst
            )
        ]


class _Ctx:
    def __init__(self):
        self.sent = []

    async def send(self, *args, **kwargs):
        self.sent.append((args, kwargs))


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
            "supply",      # map_name
            9001,          # round_id
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
    assert player["advanced_metrics"]["frag_potential"] == 24.0


@pytest.mark.asyncio
async def test_objectives_view_embed_includes_kill_assists_line():
    handler = SessionViewHandlers(_ObjectivesDB(), stats_calculator=SimpleNamespace())
    ctx = _Ctx()

    await handler.show_objectives_view(
        ctx=ctx,
        latest_date="2026-02-12",
        session_ids=[1],
        session_ids_str="?",
        player_count=1,
    )

    assert ctx.sent
    embed = ctx.sent[0][1]["embed"]
    assert embed.fields
    assert "Kill Assists" in embed.fields[0].value
    assert "`4`" in embed.fields[0].value
