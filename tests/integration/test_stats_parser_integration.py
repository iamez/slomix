"""Deterministic file-to-parser contracts, plus an explicitly opted-in corpus smoke.

Synthetic rows follow c0rn's c0rnp0rn/endstats wire format, independently checked
against vps_scripts/c0rnp0rn8.lua (weapon serialization and stats[guid] writes).
This is not a live engine proof. Historical TAB-prefix fixtures stay unchanged:
other parity tests deliberately characterize their zero-player output.
"""

import errno
import os
from datetime import datetime
from pathlib import Path

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser


def write_round_pair(root):
    """Literal synthetic counters; never derive expectations with parser code."""
    paths = []
    # Weapon order: hits, shots, kills, deaths, headshot HITS.
    # TAB slots: damage 0/1, alive% 8, headshot KILLS 14, played minutes 22,
    # dead minutes 25, revives 37. Reset fields deliberately differ from deltas.
    for number, name, weapon, damage, received, played, dead, hs_kills, revives in (
        (1, "^1Before", "16 20 50 4 2 3", 900, 400, 5, 1, 2, 4),
        (2, "^4After", "16 50 100 10 5 8", 2100, 1000, 9, 0.5, 3, 7),
    ):
        fields = ["0"] * 38
        for slot, value in {0: damage, 1: received, 8: 80, 14: hs_kills,
                            22: played, 25: dead, 37: revives}.items():
            fields[slot] = str(value)
        limit, target, measured_ms = ("12:00", "5:00", 300000) if number == 1 else ("5:00", "4:00", 240000)
        header = "\\".join(("synthetic", "goldrush", "synthetic", str(number),
                            "2", "1", limit, target, str(measured_ms)))
        player = "\\".join(("12345678", name, str(number), str(number), weapon))
        path = root / f"2026-01-01-120000-goldrush-round-{number}.txt"
        path.write_text(header + "\n" + player + " \t" + "\t".join(fields) + "\n")
        paths.append(path)
    return tuple(paths)


def one_player(result, round_number):
    assert result["success"] is True
    assert result["map_name"] == "goldrush"
    assert result["round_num"] == round_number
    assert result["total_players"] == 1
    assert len(result["players"]) == 1
    player = result["players"][0]
    assert player["guid"] == "12345678"
    return player


def assert_r1(result):
    player = one_player(result, 1)
    expected = dict(name="Before", kills=4, deaths=2, headshots=3,
                    damage_given=900, damage_received=400, time_played_seconds=300,
                    dpm=180, kd_ratio=2, accuracy=40, hits_total=20, shots_total=50)
    assert {key: player[key] for key in expected} == expected
    assert player["objective_stats"]["headshot_kills"] == 2
    assert player["objective_stats"]["revives_given"] == 4


def assert_r2(result, r1_name):
    player = one_player(result, 2)
    assert result["differential_calculation"] is True
    assert result["r1_filename"] == r1_name
    expected = dict(name="After", kills=6, deaths=3, headshots=5,
                    damage_given=1200, damage_received=600, time_played_seconds=240,
                    dpm=300, kd_ratio=2, accuracy=60, hits_total=30, shots_total=50)
    assert {key: player[key] for key in expected} == expected
    assert player["r2_counter_reset_fallback"] is False
    assert player["weapon_stats"] == {
        "WS_MP40": dict(hits=30, shots=50, kills=6, deaths=3, headshots=5, accuracy=60)}
    objective = dict(time_played_minutes=4, time_dead_minutes=0.5, time_dead_ratio=12.5,
                     time_played_percent=80, headshot_kills=3, revives_given=7)
    assert {key: player["objective_stats"][key] for key in objective} == objective
    summary = result["match_summary"]
    assert summary["round_num"] == 0
    assert summary["is_match_summary"] is True
    assert len(summary["players"]) == 1
    totals = summary["players"][0]
    assert (totals["kills"], totals["headshots"]) == (10, 8)
    assert totals["objective_stats"]["headshot_kills"] == 5
    assert totals["objective_stats"]["revives_given"] == 11


class TestStatsParserIntegration:
    @pytest.fixture
    def parser(self):
        return C0RNP0RN3StatsParser(allow_legacy_r1_fallback=False)

    @pytest.fixture
    def pair(self, tmp_path):
        return write_round_pair(tmp_path)

    def test_parse_round_1_with_independent_oracle(self, parser, pair):
        assert_r1(parser.parse_stats_file(str(pair[0])))

    def test_parse_round_2_with_independent_oracle(self, parser, pair):
        # 10 cumulative kills - 4 R1 kills = 6 R2 kills; reset revives stay 7.
        # A renamed player must still match by GUID rather than name.
        assert_r2(parser.parse_stats_file(str(pair[1])), pair[0].name)

    def test_missing_file_has_explicit_error_contract(self, parser, tmp_path):
        missing = tmp_path / "2026-01-01-120000-goldrush-round-1.txt"
        result = parser.parse_stats_file(str(missing))
        error = "exception: " + str(FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), str(missing)))
        assert result["success"] is False
        assert result["error"] == error
        assert result["players"] == []
        assert result["total_players"] == 0
        assert result["map_name"] == "Unknown"
        assert result["round_num"] == 0
        assert result["mvp"] is None
        assert result["score_confidence"] == "missing"
        assert result["side_parse_diagnostics"]["reasons"] == ["parse_error:" + error]
        for key in ("round_stopwatch_state", "time_to_beat_seconds", "next_timelimit_minutes"):
            assert result[key] is None
        datetime.fromisoformat(result["timestamp"])

    @pytest.mark.parametrize("name,expected", [
        ("^1Red^7Normal", "RedNormal"), ("^4Blue^0Black", "BlueBlack"),
        ("NoCodes", "NoCodes"), ("^9Number^aLetter", "NumberLetter"),
    ])
    def test_color_codes_preserve_text(self, parser, name, expected):
        from bot.core.utils import normalize_player_name

        assert parser.strip_color_codes(name) == expected
        assert normalize_player_name(name) == expected

    def test_round_2_filename_detection(self, parser):
        assert parser.is_round_2_file("2025-12-17-120000-goldrush-round-2.txt")
        assert parser.is_round_2_file("/some/path/2025-12-17-120000-map-round-2.txt")
        assert not parser.is_round_2_file("2025-12-17-120000-goldrush-round-1.txt")
        assert not parser.is_round_2_file("random-file.txt")

    def test_time_parsing(self, parser):
        assert parser.parse_time_to_seconds("10:00") == 600
        assert parser.parse_time_to_seconds("1:30") == 90
        assert parser.parse_time_to_seconds("0:45") == 45
        assert parser.parse_time_to_seconds("") == 0


def test_explicit_local_corpus_is_not_silent_success():
    selected = os.environ.get("SLOMIX_PARSER_CORPUS")
    if selected is None:
        pytest.skip("Optional corpus not requested; deterministic parser contracts run independently")
    directory = Path(selected)
    assert directory.is_dir(), "Requested corpus directory is missing"
    files = sorted(directory.glob("*-round-1.txt"))[:5]
    assert files, "Requested corpus has no R1 files"
    parser = C0RNP0RN3StatsParser(allow_legacy_r1_fallback=False)
    evaluated = 0
    for path in files:
        result = parser.parse_stats_file(str(path))
        assert result["success"] is True, path.name
        assert result["players"], path.name
        assert result["total_players"] == len(result["players"])
        for player in result["players"]:
            assert player["guid"]
            assert player["kills"] >= 0
            assert player["deaths"] >= 0
            assert player["damage_given"] >= 0
            evaluated += 1
    assert evaluated > 0


# Preserve the published historical fixture smoke alongside the stronger oracles.
FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "sample_stats_files"

LOCAL_STATS_DIR = Path(__file__).parent.parent.parent / "bot" / "local_stats"

class TestLegacyStatsFixtureIntegration:
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
