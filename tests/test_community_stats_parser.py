import sys
import os
from pathlib import Path

# Put repository root on sys.path so tests can import local packages
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from bot.community_stats_parser import C0RNP0RN3StatsParser


def test_parser_parses_sample_file():
    parser = C0RNP0RN3StatsParser()
    # Use a sample stats file that exists in the repo (copied earlier)
    sample = os.path.join('local_stats', 'tmp_dry_run_1.txt')
    assert os.path.exists(sample), f"Sample file not found: {sample}"

    result = parser.parse_stats_file(sample)

    assert isinstance(result, dict)
    assert result.get('success') is True
    assert 'players' in result
    assert result['total_players'] == len(result['players'])

    # At least one player should have objective_stats keys (time_dead_ratio)
    players = result.get('players', [])
    assert len(players) > 0
    first = players[0]
    obj = first.get('objective_stats', {})
    assert 'time_dead_ratio' in obj
