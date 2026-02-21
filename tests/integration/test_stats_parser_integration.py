"""
Integration test: Stats parser end-to-end validation.

Verifies that the production stats parser (C0RNP0RN3StatsParser) can
parse real stats fixture files and produce structurally valid output
with expected fields, types, and value ranges.

This is a critical-path test: if the parser breaks, all downstream
data (database imports, Discord embeds, leaderboards) will be wrong.
"""

import pytest
import os
from pathlib import Path

from bot.community_stats_parser import C0RNP0RN3StatsParser


FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_stats_files"
# Also check real stats files if available (local_stats has production data)
LOCAL_STATS_DIR = Path(__file__).parent.parent.parent / "bot" / "local_stats"


class TestStatsParserIntegration:
    """End-to-end parsing of real stats files through the production parser."""

    @pytest.fixture
    def parser(self):
        return C0RNP0RN3StatsParser()

    def _get_fixture_file(self, name: str) -> str:
        """Get path to a fixture stats file, skip if missing."""
        path = FIXTURE_DIR / name
        if not path.exists():
            pytest.skip(f"Fixture file not found: {path}")
        return str(path)

    def test_parse_fixture_returns_valid_structure(self, parser):
        """Parser returns well-structured output dict from fixture files."""
        filepath = self._get_fixture_file("2025-12-17-120000-goldrush-round-1.txt")
        result = parser.parse_stats_file(filepath)

        assert result is not None, "Parser returned None for valid file"
        assert isinstance(result, dict), f"Expected dict, got {type(result)}"

        # Must have required top-level keys from the parser
        required_keys = ["success", "map_name", "players"]
        for key in required_keys:
            assert key in result, f"Result missing required key '{key}': {list(result.keys())}"

        assert result["success"] is True
        assert result["map_name"] == "goldrush"
        assert isinstance(result["players"], list)

    def test_parse_real_round_1_produces_player_data(self, parser):
        """Parser extracts player data from a real production stats file."""
        if not LOCAL_STATS_DIR.exists():
            pytest.skip("local_stats directory not found")

        round1_files = sorted(LOCAL_STATS_DIR.glob("*-round-1.txt"))
        if not round1_files:
            pytest.skip("No round-1 stats files in local_stats/")

        filepath = str(round1_files[0])
        result = parser.parse_stats_file(filepath)

        assert result is not None, "Parser returned None for real file"
        assert result.get("success", False), f"Parser failed on real file: {result}"
        players = result.get("players", [])
        assert len(players) > 0, f"No players parsed from real file: {filepath}"

        for player in players:
            # Each player must have core fields
            assert "guid" in player, f"Player missing guid: {player.keys()}"
            assert "kills" in player, f"Player missing kills: {player.keys()}"
            assert "deaths" in player, f"Player missing deaths: {player.keys()}"

            # Kills and deaths must be non-negative
            assert player["kills"] >= 0, f"Negative kills: {player['kills']}"
            assert player["deaths"] >= 0, f"Negative deaths: {player['deaths']}"

    def test_parse_real_round_2_applies_differential(self, parser):
        """Parser handles Round 2 differential calculation on real files."""
        if not LOCAL_STATS_DIR.exists():
            pytest.skip("local_stats directory not found")

        round2_files = sorted(LOCAL_STATS_DIR.glob("*-round-2.txt"))
        if not round2_files:
            pytest.skip("No round-2 stats files in local_stats/")

        filepath = str(round2_files[0])
        result = parser.parse_stats_file(filepath)

        assert result is not None, "Parser returned None for R2 file"
        assert isinstance(result, dict)
        # R2 parsing should succeed if matching R1 exists
        if result.get("success", True) and "players" in result:
            for player in result["players"]:
                # After differential, kills should be non-negative
                # (negative would indicate a calculation bug)
                assert player.get("kills", 0) >= 0, \
                    f"Negative R2 differential kills for {player.get('guid')}"

    def test_parse_nonexistent_file_returns_error(self, parser):
        """Parser handles missing files gracefully without crashing."""
        result = parser.parse_stats_file("/nonexistent/path/fake-round-1.txt")

        assert result is not None, "Parser returned None for missing file"
        # Should indicate failure, not crash
        if "success" in result:
            assert not result["success"], "Parser reported success for missing file"

    def test_data_integrity_constraints_on_real_files(self, parser):
        """Verify data integrity constraints on real parsed stats."""
        if not LOCAL_STATS_DIR.exists():
            pytest.skip("local_stats directory not found")

        round1_files = sorted(LOCAL_STATS_DIR.glob("*-round-1.txt"))
        if not round1_files:
            pytest.skip("No round-1 stats files in local_stats/")

        # Test on up to 5 files for broader coverage
        for filepath in round1_files[:5]:
            result = parser.parse_stats_file(str(filepath))
            if not result or not result.get("success"):
                continue

            players = result.get("players", [])
            for player in players:
                kills = player.get("kills", 0)
                damage_given = player.get("damage_given", 0)

                # damage_given should be non-negative
                assert damage_given >= 0, \
                    f"Negative damage_given: {damage_given} in {filepath.name}"

                # kills should be non-negative
                assert kills >= 0, \
                    f"Negative kills: {kills} in {filepath.name}"

    def test_parser_strip_color_codes_consistency(self, parser):
        """Color code stripping is consistent between parser and utils module."""
        from bot.core.utils import normalize_player_name

        test_names = [
            "^1Red^7Normal",
            "^4Blue^0Black",
            "NoCodes",
            "^9Number^aLetter",
        ]

        for name in test_names:
            parser_result = parser.strip_color_codes(name)
            utils_result = normalize_player_name(name)
            # Both should remove color codes (utils also normalizes whitespace)
            assert "^" not in parser_result, f"Parser left color code in: {parser_result}"
            assert "^" not in utils_result, f"Utils left color code in: {utils_result}"

    def test_parser_detects_round_2_file_correctly(self, parser):
        """Round 2 detection works on standard filename patterns."""
        assert parser.is_round_2_file("2025-12-17-120000-goldrush-round-2.txt")
        assert parser.is_round_2_file("/some/path/2025-12-17-120000-map-round-2.txt")
        assert not parser.is_round_2_file("2025-12-17-120000-goldrush-round-1.txt")
        assert not parser.is_round_2_file("random-file.txt")

    def test_parser_time_parsing(self, parser):
        """Time string parsing converts MM:SS format correctly."""
        assert parser.parse_time_to_seconds("10:00") == 600
        assert parser.parse_time_to_seconds("1:30") == 90
        assert parser.parse_time_to_seconds("0:45") == 45
        assert parser.parse_time_to_seconds("") == 0
