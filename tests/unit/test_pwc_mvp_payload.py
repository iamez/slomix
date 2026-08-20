"""MVP payload transparency + public PWC formula endpoint.

The Smart Stats MVP is picked by waa_bayes while the leaderboard sorts by
total_pwc — in sessions where the two disagree the UI must be able to say
why. The mvp payload therefore carries the deciding metric (waa_bayes) and
how it was selected (selected_by). The public formula endpoint mirrors the
KIS one and must not drift from the computed weights.
"""
from __future__ import annotations

import pytest

from website.backend.routers.storytelling_router import get_pwc_formula
from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling import win_contribution
from website.backend.services.storytelling_service import StorytellingService

_SCOPE = GamingSessionScope(
    gaming_session_id=42,
    dates=("2026-07-08",),
    round_keys=((500, "te_escape2", 1), (600, "te_escape2", 2)),
    accepted_round_count=2,
    distinct_map_names=("te_escape2",),
)


class _FakeDB:
    """Two players on team 1, two rounds; team 1 wins round 1 only."""

    def __init__(self, winner_teams=(1, 2)):
        w1, w2 = winner_teams
        self.rows = [
            # guid, name, round_number, map_name, team, winner_team, kills,
            # damage, objectives, revives, time_alive, round_id, round_start_unix
            ("AAAA1111", "carry", 1, "te_escape2", 1, w1, 8, 800, 1, 0, 5.0, 1, 500),
            ("BBBB2222", "anchor", 1, "te_escape2", 1, w1, 2, 200, 0, 2, 5.0, 1, 500),
            ("AAAA1111", "carry", 2, "te_escape2", 1, w2, 6, 600, 0, 0, 5.0, 2, 600),
            ("BBBB2222", "anchor", 2, "te_escape2", 1, w2, 3, 300, 1, 1, 5.0, 2, 600),
        ]

    async def fetch_all(self, query, params=()):
        if "player_comprehensive_stats" in query:
            return self.rows
        return []


@pytest.mark.asyncio
async def test_mvp_payload_carries_deciding_metric():
    result = await StorytellingService(_FakeDB()).compute_win_contribution(_SCOPE)
    mvp = result["mvp"]
    assert mvp is not None
    assert mvp["selected_by"] == "waa_bayes"
    assert isinstance(mvp["waa_bayes"], float)
    # the deciding metric must equal that player's entry in the list
    entry = next(p for p in result["players"] if p["guid"] == mvp["guid"])
    assert mvp["waa_bayes"] == entry["waa_bayes"]


@pytest.mark.asyncio
async def test_mvp_fallback_is_labeled():
    # nobody wins a round (winner_team=0) -> no eligible candidate ->
    # fallback to leaderboard #1 by total_pwc, and the payload says so
    result = await StorytellingService(
        _FakeDB(winner_teams=(0, 0))
    ).compute_win_contribution(_SCOPE)
    mvp = result["mvp"]
    assert mvp is not None
    assert mvp["selected_by"] == "total_pwc_fallback"
    assert mvp["guid"] == result["players"][0]["guid"]


@pytest.mark.asyncio
async def test_pwc_formula_endpoint_matches_computed_weights():
    body = await get_pwc_formula()
    assert body["status"] == "ok"
    # version imported from the owning module — cannot drift
    assert body["version"] == win_contribution.FORMULA_VERSION
    weights = {k: v["value"] for k, v in body["weights"].items()}
    assert weights == StorytellingService.pwc_weights()
    assert sum(weights.values()) == pytest.approx(1.0)
