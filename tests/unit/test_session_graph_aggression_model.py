from __future__ import annotations

import pytest

from website.backend.routers import api as api_router


class _SessionGraphAggressionDB:
    async def fetch_all(self, query: str, params=()):
        normalized = " ".join(str(query).split()).lower()
        if "from player_comprehensive_stats p" not in normalized:
            raise AssertionError(f"Unexpected query: {normalized}")
        return [
            (
                "Alpha",
                "guid-a",
                1,
                14,
                5,
                2200,
                1200,
                600,
                1,
                2,
                1,
                3,
                36.0,
                0,
                0,
                1,
                1.5,
                150,
                6,
                "supply",
                11,
            ),
            (
                "Alpha",
                "guid-a",
                2,
                10,
                4,
                1800,
                1000,
                600,
                0,
                1,
                1,
                2,
                34.0,
                0,
                0,
                1,
                1.2,
                120,
                5,
                "radar",
                12,
            ),
            (
                "Bravo",
                "guid-b",
                1,
                15,
                10,
                2100,
                2400,
                600,
                0,
                1,
                1,
                2,
                35.0,
                0,
                0,
                1,
                3.5,
                30,
                1,
                "supply",
                11,
            ),
            (
                "Bravo",
                "guid-b",
                2,
                9,
                8,
                1600,
                2200,
                600,
                0,
                0,
                0,
                1,
                33.0,
                0,
                0,
                1,
                3.0,
                20,
                1,
                "radar",
                12,
            ),
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
    assert alpha["playstyle"]["aggression"] > bravo["playstyle"]["aggression"]
    assert alpha["advanced_metrics"]["empty_death_burden"] < bravo["advanced_metrics"]["empty_death_burden"]
    assert alpha["advanced_metrics"]["discipline_score"] > bravo["advanced_metrics"]["discipline_score"]
