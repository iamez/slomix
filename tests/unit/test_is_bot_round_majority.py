"""is_bot_dominated_round majority rule (housekeeping 2026-07).

The 2026-06-21 functional test showed 1-human + N-bot test rounds slipping
through the old human_count==0 rule with is_bot_round=FALSE.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.community_stats_parser import is_bot_dominated_round


def test_pure_bot_round_is_flagged():
    assert is_bot_dominated_round(bot_player_count=6, human_player_count=0) is True


def test_no_bots_is_not_flagged():
    assert is_bot_dominated_round(bot_player_count=0, human_player_count=8) is False


def test_empty_round_is_not_flagged():
    assert is_bot_dominated_round(bot_player_count=0, human_player_count=0) is False


def test_owner_testing_with_bot_majority_is_flagged():
    # The 2026-06-21 case: 1 human owner + 5 omni-bots
    assert is_bot_dominated_round(bot_player_count=5, human_player_count=1) is True


def test_filler_bot_minority_is_not_flagged():
    # A real evening with a couple of filler bots must stay a human round
    assert is_bot_dominated_round(bot_player_count=2, human_player_count=6) is False


def test_even_split_is_not_flagged():
    # Strict majority required — 3v3 humans/bots stays a human round
    assert is_bot_dominated_round(bot_player_count=3, human_player_count=3) is False
