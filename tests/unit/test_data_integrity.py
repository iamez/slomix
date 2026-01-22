"""
Data Integrity Tests for ET:Legacy Discord Bot

Tests for:
1. Cross-field validation (headshots <= kills, etc.)
2. File hash calculation
3. Configuration validation
4. Stats boundary conditions

Created: December 21, 2025
"""

import os
import pytest
import tempfile
import hashlib
from pathlib import Path

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCrossFieldValidation:
    """Test cross-field validation in postgresql_database_manager.py"""

    @pytest.fixture
    def db_manager(self):
        """Create a database manager instance for testing validation."""
        from postgresql_database_manager import PostgreSQLDatabaseManager
        # Note: This will fail if PostgreSQL isn't configured, which is expected in CI
        try:
            return PostgreSQLDatabaseManager()
        except Exception:
            pytest.skip("PostgreSQL not configured")

    def test_headshot_kills_cannot_exceed_kills(self, db_manager):
        """headshot_kills should be capped at kills"""
        player = {
            'kills': 10,
            'objective_stats': {'headshot_kills': 15}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['objective_stats']['headshot_kills'] == 10
        assert any('headshot_kills' in issue for issue in issues)

    def test_headshot_kills_normal_case(self, db_manager):
        """headshot_kills less than kills should pass"""
        player = {
            'kills': 10,
            'objective_stats': {'headshot_kills': 5}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['objective_stats']['headshot_kills'] == 5
        assert not any('headshot_kills' in issue for issue in issues)

    def test_team_kills_cannot_exceed_kills(self, db_manager):
        """team_kills should be capped at kills"""
        player = {
            'kills': 5,
            'objective_stats': {'team_kills': 10}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['objective_stats']['team_kills'] <= 5
        assert any('team_kills' in issue for issue in issues)

    def test_time_dead_cannot_exceed_time_played(self, db_manager):
        """time_dead_minutes should be capped at time_played_minutes"""
        player = {
            'time_played_seconds': 600,  # 10 minutes
            'objective_stats': {
                'time_dead_minutes': 15.0,  # 15 minutes (impossible!)
                'time_dead_ratio': 150.0
            }
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['objective_stats']['time_dead_minutes'] <= 10.0
        assert corrected['objective_stats']['time_dead_ratio'] <= 100.0
        assert any('time_dead' in issue for issue in issues)

    def test_accuracy_capped_at_100(self, db_manager):
        """accuracy should be 0-100"""
        player = {
            'accuracy': 150.0,
            'objective_stats': {}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['accuracy'] == 100.0
        assert any('accuracy' in issue for issue in issues)

    def test_accuracy_negative_fixed(self, db_manager):
        """negative accuracy should be fixed to 0"""
        player = {
            'accuracy': -10.0,
            'objective_stats': {}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['accuracy'] == 0.0

    def test_negative_kills_fixed(self, db_manager):
        """negative kills should be fixed to 0"""
        player = {
            'kills': -5,
            'deaths': 10,
            'damage_given': -100,
            'damage_received': 500,
            'objective_stats': {}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['kills'] == 0
        assert corrected['damage_given'] == 0
        assert any('negative' in issue for issue in issues)

    def test_high_dpm_logged_but_not_fixed(self, db_manager):
        """High DPM should be logged but not modified"""
        player = {
            'dpm': 1500.0,  # Very high
            'objective_stats': {}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        # DPM is logged but not fixed (could be legitimate in short round)
        assert corrected['dpm'] == 1500.0
        assert any('dpm' in issue for issue in issues)

    def test_valid_player_no_issues(self, db_manager):
        """Valid player stats should have no issues"""
        player = {
            'guid': 'ABC12345',
            'name': 'TestPlayer',
            'kills': 20,
            'deaths': 5,
            'damage_given': 5000,
            'damage_received': 1000,
            'accuracy': 45.5,
            'dpm': 250.0,
            'time_played_seconds': 600,
            'objective_stats': {
                'headshot_kills': 8,
                'team_kills': 2,
                'time_dead_minutes': 2.0,
                'time_dead_ratio': 20.0
            }
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert len(issues) == 0


class TestFileHashCalculation:
    """Test SHA256 file hash calculation in file_tracker.py"""

    def test_calculate_file_hash_basic(self):
        """Test basic hash calculation"""
        from bot.automation.file_tracker import calculate_file_hash

        # Create temp file with known content
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("test content for hashing")
            temp_path = f.name

        try:
            hash_result = calculate_file_hash(temp_path)

            # Verify it's a valid SHA256 hash (64 hex chars)
            assert len(hash_result) == 64
            assert all(c in '0123456789abcdef' for c in hash_result)

            # Verify it matches expected hash
            expected = hashlib.sha256(b"test content for hashing").hexdigest()
            assert hash_result == expected
        finally:
            os.unlink(temp_path)

    def test_calculate_file_hash_consistent(self):
        """Same file should always produce same hash"""
        from bot.automation.file_tracker import calculate_file_hash

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("consistent content")
            temp_path = f.name

        try:
            hash1 = calculate_file_hash(temp_path)
            hash2 = calculate_file_hash(temp_path)
            assert hash1 == hash2
        finally:
            os.unlink(temp_path)

    def test_different_files_different_hashes(self):
        """Different files should produce different hashes"""
        from bot.automation.file_tracker import calculate_file_hash

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f1:
            f1.write("content A")
            path1 = f1.name

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f2:
            f2.write("content B")
            path2 = f2.name

        try:
            hash1 = calculate_file_hash(path1)
            hash2 = calculate_file_hash(path2)
            assert hash1 != hash2
        finally:
            os.unlink(path1)
            os.unlink(path2)


class TestConfigurationValues:
    """Test configuration timing values"""

    def test_round_match_window_default(self):
        """round_match_window_minutes should default to 45"""
        from bot.config import BotConfig
        config = BotConfig()
        assert config.round_match_window_minutes == 45

    def test_monitoring_grace_period_default(self):
        """monitoring_grace_period_minutes should default to 45"""
        from bot.config import BotConfig
        config = BotConfig()
        assert config.monitoring_grace_period_minutes == 45

    def test_session_gap_default(self):
        """session_gap_minutes should default to 60"""
        from bot.config import BotConfig
        config = BotConfig()
        assert config.session_gap_minutes == 60

    def test_round_match_less_than_session_gap(self):
        """round_match_window should be less than session_gap"""
        from bot.config import BotConfig
        config = BotConfig()
        assert config.round_match_window_minutes < config.session_gap_minutes


class TestParserConfiguration:
    """Test parser uses configurable values"""

    def test_parser_accepts_custom_window(self):
        """Parser should accept custom round_match_window_minutes"""
        from bot.community_stats_parser import C0RNP0RN3StatsParser

        parser_default = C0RNP0RN3StatsParser()
        assert parser_default.round_match_window_minutes == 45

        parser_custom = C0RNP0RN3StatsParser(round_match_window_minutes=30)
        assert parser_custom.round_match_window_minutes == 30

        parser_custom2 = C0RNP0RN3StatsParser(round_match_window_minutes=60)
        assert parser_custom2.round_match_window_minutes == 60


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_kills_with_headshots(self):
        """Zero kills but headshots present should be fixed"""
        from postgresql_database_manager import PostgreSQLDatabaseManager
        try:
            db_manager = PostgreSQLDatabaseManager()
        except Exception:
            pytest.skip("PostgreSQL not configured")

        player = {
            'kills': 0,
            'objective_stats': {'headshot_kills': 5}
        }
        corrected, issues = db_manager.validate_player_stats(player)
        assert corrected['objective_stats']['headshot_kills'] == 0

    def test_zero_time_played(self):
        """Zero time played should not cause division by zero"""
        from postgresql_database_manager import PostgreSQLDatabaseManager
        try:
            db_manager = PostgreSQLDatabaseManager()
        except Exception:
            pytest.skip("PostgreSQL not configured")

        player = {
            'time_played_seconds': 0,
            'objective_stats': {
                'time_dead_minutes': 5.0,
                'time_dead_ratio': 100.0
            }
        }
        # Should not raise exception
        corrected, issues = db_manager.validate_player_stats(player)
        assert 'objective_stats' in corrected


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
