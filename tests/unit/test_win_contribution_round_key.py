"""compute_win_contribution proximity add-on keys (crossfire/trade/clutch).

The base PWC query already groups correctly by round_id, but the
crossfire/trade/clutch proximity add-ons were looked up by
(guid, round_start_unix) only — round_start_unix is not guaranteed unique
repo-wide, so two rounds in the same session sharing a start time would
bleed proximity counts into each other. Regression test for the fix
(codex, PR #478 follow-up audit finding #12).
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling_service import StorytellingService


class _FakeDB:
    """Two rounds (round_id 1 and 2) that share round_start_unix=500 but
    have different round_number — the crossfire data is tagged
    round_number=1 only, so round_number=2 must see ZERO crossfire."""

    def __init__(self):
        self.rows = [
            # guid, name, round_number, map_name, team, winner_team, kills,
            # damage, objectives, revives, time_alive, round_id, round_start_unix
            ("AAAA1111", "p1", 1, "te_escape2", 1, 1, 5, 500, 0, 0, 5.0, 1, 500),
            ("AAAA1111", "p1", 2, "te_escape2", 1, 1, 3, 300, 0, 0, 5.0, 2, 500),
        ]
        # crossfire tagged to round_number=1 only
        self.xf_rows = [("AAAA1111", 500, 1, 2)]
        self.tr_rows = []
        self.cl_rows = []

    async def fetch_all(self, query, params=()):
        if "player_comprehensive_stats" in query:
            return self.rows
        if "storytelling_kill_impact" in query and "is_crossfire" in query:
            return self.xf_rows
        if "proximity_lua_trade_kill" in query:
            return self.tr_rows
        if "proximity_combat_position" in query:
            return self.cl_rows
        return []


@pytest.mark.asyncio
async def test_crossfire_does_not_bleed_across_rounds_sharing_start_unix():
    result = await StorytellingService(_FakeDB()).compute_win_contribution("2026-07-08")
    player = next(p for p in result["players"] if p["guid"] == "AAAA1111")

    # round 1 (round_number=1): solo team, crossfire_share = 2/2 = 1.0,
    # weight 0.13 (0.10 + 0.03 all-objectives-zero bump) -> +0.13
    # round 2 (round_number=2): must see ZERO crossfire (not round 1's
    # count leaking in via a round_start_unix-only key) -> +0.0
    assert player["components"]["crossfire"] == pytest.approx(0.13, abs=1e-6)
