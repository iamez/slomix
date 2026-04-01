from __future__ import annotations

import pytest

from website.backend.routers import sessions_router as api_router


class _FakeSessionDetailDB:
    def __init__(self, player_rows):
        self._player_rows = player_rows

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split()).lower()
        if "from information_schema.columns" in q and "player_comprehensive_stats" in q:
            return [
                ("time_played_percent",),
                ("time_dead_ratio",),
                ("time_dead_minutes",),
            ]
        if "from rounds r" in q and "where r.gaming_session_id = $1" in q:
            return [
                (11, "supply", 1, 1, "2026-03-01", "12:00", "10:00", 1770000000),
                (12, "supply", 2, 2, "2026-03-01", "12:15", "10:00", 1770000900),
            ]
        if "from lua_round_teams" in q:
            return [
                (11, 1, 0, 0, 600, 1, "supply"),
                (12, 2, 0, 0, 600, 2, "supply"),
            ]
        if "from player_comprehensive_stats p" in q and "group by p.player_guid" in q:
            return self._player_rows
        return []


@pytest.mark.asyncio
async def test_session_detail_returns_dual_alive_pct_fields(monkeypatch):
    async def _fake_build_session_scoring(*_args, **_kwargs):
        return {"available": False}, None, None

    monkeypatch.setattr(api_router, "build_session_scoring", _fake_build_session_scoring)

    # Tuple shape follows get_stats_session_detail SELECT order (23 columns):
    # 0:guid, 1:name, 2:kills, 3:deaths, 4:dmg_g, 5:dmg_r, 6:dpm, 7:kd,
    # 0:player_guid, 1:player_name, 2:kills, 3:deaths, 4:damage_given,
    # 5:damage_received, 6:dpm, 7:kd, 8:headshot_kills, 9:total_kills_for_hs,
    # 10:gibs, 11:self_kills, 12:useful_kills, 13:full_selfkills,
    # 14:revives_given, 15:times_revived, 16:time_played_seconds, 17:kill_assists,
    # 18:time_dead_minutes, 19:denied_playtime, 20:total_hits, 21:total_shots,
    # 22:weapon_headshots, 23:tpp_weighted_sum, 24:tpp_weight
    player_rows = [
        (
            "g-alpha", "Alpha",
            20, 10, 2400, 1800, 240.0, 2.0, 8, 20, 3, 1,
            6,       # useful_kills
            0,       # full_selfkills
            4, 2,
            600,     # time_played_seconds (= 10 min)
            5,       # kill_assists
            2.0,     # time_dead_minutes => computed alive% = 100-(2/10*100) = 80.0
            0,       # denied_playtime
            120, 240,
            15,       # weapon_headshots
            49200.0,  # tpp_weighted_sum = 82.0 * 600 => engine alive% = 82.0
            600.0,    # tpp_weight
        ),
        (
            "g-bravo", "Bravo",
            18, 9, 2200, 1700, 220.0, 2.0, 6, 18, 2, 1,
            5,       # useful_kills
            0,       # full_selfkills
            3, 2,
            600,
            4,
            2.0,     # computed alive% = 80.0
            0,
            110, 220,
            12,       # weapon_headshots
            49260.0,  # tpp_weighted_sum = 82.1 * 600 => engine alive% = 82.1
            600.0,
        ),
        (
            "g-charlie", "Charlie",
            10, 12, 1500, 1900, 150.0, 0.83, 4, 10, 1, 2,
            3,       # useful_kills
            0,       # full_selfkills
            1, 3,
            600,
            3,
            1.5,     # computed alive% = 100-(1.5/10*100) = 85.0
            0,
            80, 200,
            8,        # weapon_headshots
            0.0,     # no engine data available
            0.0,
        ),
    ]

    payload = await api_router.get_stats_session_detail(
        gaming_session_id=777, db=_FakeSessionDetailDB(player_rows)
    )

    players = {p["player_name"]: p for p in payload["players"]}

    # Alpha: has engine data, so alive_pct = engine value
    alpha = players["Alpha"]
    assert alpha["alive_pct"] == 82.0       # engine value (primary)
    assert alpha["alive_pct_lua"] == 82.0   # engine value
    assert alpha["alive_pct_diff"] == 2.0   # |82.0 - 80.0|
    assert alpha["alive_pct_drift"] is False  # 2.0 not > 2.0
    assert alpha["played_pct"] == 50.0      # 600/1200

    # Bravo: engine alive% differs by 2.1% from computed
    bravo = players["Bravo"]
    assert bravo["alive_pct"] == 82.1       # engine value (primary)
    assert bravo["alive_pct_lua"] == 82.1
    assert bravo["alive_pct_diff"] == 2.1
    assert bravo["alive_pct_drift"] is True  # 2.1 > 2.0
    assert bravo["played_pct"] == 50.0

    # Charlie: no engine data, falls back to computed
    charlie = players["Charlie"]
    assert charlie["alive_pct"] == 85.0       # computed fallback
    assert charlie["alive_pct_lua"] is None   # no engine data
    assert charlie["alive_pct_diff"] is None
    assert charlie["alive_pct_drift"] is False
    assert charlie["played_pct"] == 50.0
