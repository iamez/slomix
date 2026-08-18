"""The box scorer must never trust a roster the session didn't produce.

Session 144 (2026-08-11): a morning OMNIBOT test held the gsid, its detected
bot roster stayed in session_teams, and the humans who inherited the gsid
that evening were box-scored 0:0 with "roster changed" on every map. Three
layers let that happen and each gets a guard here:

1. detect_session_teams could seed rosters from bot/invalid rounds;
2. the scorer read session_teams with no staleness check (the sibling
   reader in session_data_service has carried one since the #682 fix);
3. save_session_results' ON CONFLICT did not overwrite the roster columns,
   so even a corrected re-score kept the stale bot GUIDs.
"""
from __future__ import annotations

import inspect

from bot.core.team_manager import TeamManager
from bot.services.stopwatch_scoring_service import StopwatchScoringService


def test_roster_detection_excludes_bot_and_invalid_rounds():
    src = inspect.getsource(TeamManager.detect_session_teams)
    assert src.count("r.is_valid IS DISTINCT FROM FALSE") >= 2, (
        "both detection queries (by gsid and by date) must gate on is_valid"
    )
    assert src.count("OMNIBOT") >= 2 and src.count("[BOT]") >= 2, (
        "identity defence must cover rounds predating the is_bot_round flag"
    )


def test_scorer_verifies_roster_overlap_before_scoring():
    src = inspect.getsource(StopwatchScoringService.calculate_session_scores)
    assert "roster_guids & participants" in src, (
        "the box scorer lost its stale-roster guard — a session_teams row "
        "that shares no GUID with the actual players would be trusted again"
    )
    assert "detect_session_teams" in src, (
        "on a stale roster the scorer must fall back to fresh detection"
    )


def test_rescore_overwrites_the_roster_columns():
    src = inspect.getsource(StopwatchScoringService.save_session_results)
    for col in ("team_1_guids = EXCLUDED.team_1_guids",
                "team_2_guids = EXCLUDED.team_2_guids",
                "team_1_names = EXCLUDED.team_1_names",
                "team_2_names = EXCLUDED.team_2_names"):
        assert col in src, f"ON CONFLICT no longer overwrites {col.split(' =')[0]}"
