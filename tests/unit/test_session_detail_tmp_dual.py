from __future__ import annotations

import pytest

from website.backend.routers import api as api_router


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
async def test_session_detail_returns_dual_tmp_and_drift_fields(monkeypatch):
    async def _fake_build_session_scoring(*_args, **_kwargs):
        return {"available": False}, None, None

    monkeypatch.setattr(api_router, "build_session_scoring", _fake_build_session_scoring)

    # Tuple shape follows get_stats_session_detail SELECT:
    # guid,name,kills,deaths,dmg_g,dmg_r,dpm,kd,hs,total_kills,gibs,self,
    # revives_given,times_revived,time_played,time_dead_min,denied,total_hits,total_shots,
    # dead_ratio_lua_weighted_sum,dead_ratio_lua_weight,played_seconds_lua_sum
    player_rows = [
        (
            "g-alpha",
            "Alpha",
            20,
            10,
            2400,
            1800,
            240.0,
            2.0,
            8,
            20,
            3,
            1,
            4,
            2,
            600,
            2.0,  # dead minutes => computed TMP = 80.0
            0,
            120,
            240,
            10800.0,  # lua dead ratio = 18.0 => alive% = 82.0
            600.0,
            570.0,  # raw TAB[8] reconstructed play seconds across scope => 47.5%
        ),
        (
            "g-bravo",
            "Bravo",
            18,
            9,
            2200,
            1700,
            220.0,
            2.0,
            6,
            18,
            2,
            1,
            3,
            2,
            600,
            2.0,  # computed TMP = 80.0
            0,
            110,
            220,
            10740.0,  # lua dead ratio = 17.9 => alive% = 82.1
            600.0,
            585.0,  # raw TAB[8] reconstructed play seconds across scope => 48.8%
        ),
        (
            "g-charlie",
            "Charlie",
            10,
            12,
            1500,
            1900,
            150.0,
            0.83,
            4,
            10,
            1,
            2,
            1,
            3,
            600,
            1.5,  # computed TMP = 85.0
            0,
            80,
            200,
            0.0,  # no lua ratio available
            0.0,
            0.0,
        ),
    ]

    payload = await api_router.get_stats_session_detail(
        gaming_session_id=777, db=_FakeSessionDetailDB(player_rows)
    )

    players = {p["player_name"]: p for p in payload["players"]}

    alpha = players["Alpha"]
    assert alpha["tmp_pct"] == 80.0
    assert alpha["tmp_pct_computed"] == 80.0
    assert alpha["tmp_pct_lua"] == 82.0
    assert alpha["tmp_pct_diff"] == 2.0
    assert alpha["tmp_pct_drift"] is False
    assert alpha["alive_pct"] == 80.0
    assert alpha["alive_pct_lua"] == 82.0
    assert alpha["time_dead_ratio"] == 18.0
    assert alpha["played_pct"] == 50.0
    assert alpha["played_pct_lua"] == 47.5
    assert alpha["played_pct_diff"] == 2.5
    assert alpha["played_pct_drift"] is True

    bravo = players["Bravo"]
    assert bravo["tmp_pct_computed"] == 80.0
    assert bravo["tmp_pct_lua"] == 82.1
    assert bravo["tmp_pct_diff"] == 2.1
    assert bravo["tmp_pct_drift"] is True
    assert bravo["time_dead_ratio"] == 17.9
    assert bravo["played_pct"] == 50.0
    assert bravo["played_pct_lua"] == 48.8
    assert bravo["played_pct_diff"] == 1.2
    assert bravo["played_pct_drift"] is False

    charlie = players["Charlie"]
    assert charlie["tmp_pct_computed"] == 85.0
    assert charlie["tmp_pct_lua"] is None
    assert charlie["tmp_pct_diff"] is None
    assert charlie["tmp_pct_drift"] is False
    assert charlie["played_pct"] == 50.0
    assert charlie["played_pct_lua"] is None
    assert charlie["played_pct_diff"] is None
    assert charlie["played_pct_drift"] is False
