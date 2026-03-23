"""
Test the session graph aggression model.

get_session_graph_stats returns 31-column rows. This test verifies
the aggression scoring rewards productive pressure.
"""
from __future__ import annotations

import pytest

from website.backend.routers import sessions_router as api_router


def _make_row(
    name, guid, round_num, kills, deaths, dmg_g, dmg_r, time_secs,
    revives, kill_assists, gibs, headshots, accuracy, team_kills,
    self_kills, times_revived, dead_min, denied, useful, map_name, round_id,
    constructions=0, obj_stolen=0, dyna_planted=0, dyna_defused=0,
    useless=0, double=0, triple=0, quad=0, mega=0, bullets=100, tpp=80.0,
):
    """Build a 31-column tuple matching the get_session_graph_stats SELECT."""
    return (
        name, round_num, kills, deaths, dmg_g, dmg_r, time_secs,
        revives, kill_assists, gibs, headshots, accuracy,
        team_kills, self_kills, times_revived, dead_min, denied,
        useful, map_name, round_id, constructions, obj_stolen,
        dyna_planted, dyna_defused, useless, double, triple, quad, mega,
        bullets, tpp,
    )


class _SessionGraphAggressionDB:
    async def fetch_all(self, query: str, params=()):
        normalized = " ".join(str(query).split()).lower()
        if "from player_comprehensive_stats p" not in normalized:
            raise AssertionError(f"Unexpected query: {normalized}")
        return [
            _make_row("Alpha", "guid-a", 1, 14, 5, 2200, 1200, 600,
                       1, 2, 1, 3, 36.0, 0, 0, 1, 1.5, 150, 6, "supply", 11),
            _make_row("Alpha", "guid-a", 2, 10, 4, 1800, 1000, 600,
                       0, 1, 1, 2, 34.0, 0, 0, 1, 1.2, 120, 5, "radar", 12),
            _make_row("Bravo", "guid-b", 1, 15, 10, 2100, 2400, 600,
                       0, 1, 1, 2, 35.0, 0, 0, 1, 3.5, 30, 1, "supply", 11),
            _make_row("Bravo", "guid-b", 2, 9, 8, 1600, 2200, 600,
                       0, 0, 0, 1, 33.0, 0, 0, 1, 3.0, 20, 1, "radar", 12),
        ]


@pytest.mark.asyncio
async def test_session_graph_aggression_rewards_productive_pressure():
    payload = await api_router.get_session_graph_stats(
        "2026-03-05",
        gaming_session_id=95,
        db=_SessionGraphAggressionDB(),
    )

    players = {player["name"]: player for player in payload["players"]}
    alpha = players["Alpha"]
    bravo = players["Bravo"]

    assert alpha["combat_defense"]["useful_kills"] == 11
    assert alpha["advanced_metrics"]["useful_kills_per_round"] == 5.5
    assert alpha["advanced_metrics"]["empty_death_burden"] < bravo["advanced_metrics"]["empty_death_burden"]
    assert alpha["advanced_metrics"]["discipline_score"] > bravo["advanced_metrics"]["discipline_score"]
