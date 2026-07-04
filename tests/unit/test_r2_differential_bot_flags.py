"""R2 differential must propagate bot-round classification (codex P2, PR #434).

calculate_round_2_differential builds a fresh result dict; before the fix it
dropped bot_player_count/human_player_count/is_bot_round, so the round_number=2
row of a bot-majority test match was stored with the default is_bot_round=FALSE.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser


def _round_data(is_bot_round: bool) -> dict:
    return {
        'map_name': 'supply',
        'defender_team': 1,
        'winner_team': 2,
        'map_time': '10:00',
        'actual_time': '7:30',
        'round_outcome': 'objective',
        'players': [],
        'bot_player_count': 5,
        'human_player_count': 1,
        'is_bot_round': is_bot_round,
    }


def test_differential_propagates_bot_round_flags():
    parser = C0RNP0RN3StatsParser()
    result = parser.calculate_round_2_differential(_round_data(False), _round_data(True))
    assert result['success'] is True
    assert result['is_bot_round'] is True
    assert result['bot_player_count'] == 5
    assert result['human_player_count'] == 1


def test_differential_defaults_when_flags_absent():
    parser = C0RNP0RN3StatsParser()
    r2 = _round_data(False)
    for key in ('bot_player_count', 'human_player_count', 'is_bot_round'):
        r2.pop(key)
    result = parser.calculate_round_2_differential(_round_data(False), r2)
    assert result['is_bot_round'] is False
    assert result['bot_player_count'] == 0
