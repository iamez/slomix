from __future__ import annotations

import pytest

from bot.services.timing_comparison_service import TimingComparisonService


class _FakeDB:
    def __init__(self, round_row, player_rows):
        self.round_row = round_row
        self.player_rows = player_rows
        self.last_round_query = None
        self.last_round_params = None
        self.last_player_query = None
        self.last_player_params = None

    async def fetch_one(self, query, params):
        self.last_round_query = query
        self.last_round_params = params
        return self.round_row

    async def fetch_all(self, query, params):
        self.last_player_query = query
        self.last_player_params = params
        return self.player_rows


@pytest.mark.asyncio
async def test_fetch_stats_file_data_includes_team_side_payload():
    round_row = (
        9819, "2026-02-11-220205", 2, "supply", "2026-02-11", "220205",
        "9:39", "12:00", 1, 2, 579, 0, "NORMAL"
    )
    player_rows = [
        ("g_axis", "AxisPlayer", 320, 50, 15.6, 1800, 337.5, 3, 0),
        ("g_allies", "AlliesPlayer", 300, 40, 13.3, 1500, 300.0, 0, 2),
        ("g_mixed", "MixedPlayer", 280, 30, 10.7, 1200, 257.1, 1, 1),
        ("g_unknown", "UnknownPlayer", 240, 20, 8.3, 900, 225.0, 0, 0),
    ]
    db = _FakeDB(round_row, player_rows)
    service = TimingComparisonService(db_adapter=db, bot=None)

    stats = await service._fetch_stats_file_data(9819)

    assert stats is not None
    assert db.last_player_params == (9819,)
    assert "SUM(CASE WHEN team = 1 THEN 1 ELSE 0 END) as axis_rows" in db.last_player_query
    assert "SUM(CASE WHEN team = 2 THEN 1 ELSE 0 END) as allies_rows" in db.last_player_query

    players = {p["guid"]: p for p in stats["players"]}
    assert players["g_axis"]["team"] == 1
    assert players["g_axis"]["side_marker"] == "[AX]"
    assert players["g_allies"]["team"] == 2
    assert players["g_allies"]["side_marker"] == "[AL]"
    assert players["g_mixed"]["team"] == 0
    assert players["g_mixed"]["side_marker"] == "[MX]"
    assert players["g_unknown"]["team"] == 0
    assert players["g_unknown"]["side_marker"] == "[--]"


def test_build_comparison_embed_renders_side_markers():
    service = TimingComparisonService(db_adapter=None, bot=None)

    stats_data = {
        "round_id": 9819,
        "round_number": 2,
        "map_name": "supply",
        "round_date": "2026-02-11",
        "round_time": "220205",
        "actual_time": "9:39",
        "stats_duration_seconds": 579,
        "time_limit": "12:00",
        "players": [
            {
                "name": "AxisPlayer",
                "time_played_seconds": 320,
                "time_dead_seconds": 50,
                "time_dead_ratio": 15.6,
                "dpm": 337.5,
                "side_state": "axis",
                "side_marker": "[AX]",
            },
            {
                "name": "AlliesPlayer",
                "time_played_seconds": 300,
                "time_dead_seconds": 40,
                "time_dead_ratio": 13.3,
                "dpm": 300.0,
                "side_state": "allies",
                "side_marker": "[AL]",
            },
            {
                "name": "MixedPlayer",
                "time_played_seconds": 280,
                "time_dead_seconds": 30,
                "time_dead_ratio": 10.7,
                "dpm": 257.1,
                "side_state": "mixed",
                "side_marker": "[MX]",
            },
        ],
    }

    embed = service._build_comparison_embed(stats_data, lua_data=None)

    player_field = next(f for f in embed.fields if f.name.startswith("👥 Per-Player Times"))
    assert "[AX]" in player_field.value
    assert "[AL]" in player_field.value
    assert "[MX]" in player_field.value
    assert "🧭 [AX]=Axis | [AL]=Allies | [MX]/[--]=mixed or unknown" in player_field.value
