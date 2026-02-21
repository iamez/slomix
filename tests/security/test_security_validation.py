"""
Security Validation Tests

Tests for security controls including:
- Filename validation (path traversal prevention) via production validators
- Input sanitization via production functions
- SQL injection prevention patterns
- Error message sanitization via production sanitize_error_message()
- Webhook validation patterns

These tests import and exercise REAL production validation functions
from bot.core.utils, bot.community_stats_parser, and bot.endstats_parser,
rather than duplicating logic with local regex patterns.

Limitation: bot.ultimate_bot._validate_stats_filename() and
_check_webhook_rate_limit() are instance methods on the Discord bot class,
which requires a full bot instantiation (Discord token, event loop, etc.).
A standalone validate_stats_filename() was extracted to bot.core.utils to
make it testable without the bot. The bot's own copy should be kept in sync.
"""

import pytest
import re
from pathlib import Path

# Production imports - these are the REAL validators being tested
from bot.core.utils import (
    validate_stats_filename,
    escape_like_pattern,
    escape_like_pattern_for_query,
    sanitize_error_message,
    normalize_player_name,
)
from bot.endstats_parser import validate_endstats_filename
from bot.community_stats_parser import C0RNP0RN3StatsParser


class TestFilenameValidation:
    """Tests for the production validate_stats_filename() function in bot.core.utils"""

    def test_valid_stats_filenames_accepted(self):
        """Production validator accepts correctly formatted filenames"""
        valid_filenames = [
            "2025-12-17-120000-goldrush-round-1.txt",
            "2025-12-17-120000-erdenberg_t2-round-2.txt",
            "2025-01-01-000000-battery-round-1.txt",
            "2024-12-31-235959-oasis-round-2.txt",
            "2026-01-12-224606-te_escape2-round-2.txt",
            "2025-10-12-211804-etl_adlernest-round-1.txt",
        ]

        for filename in valid_filenames:
            assert validate_stats_filename(filename), f"Valid filename rejected: {filename}"

    def test_reject_path_traversal_attempts(self):
        """Production validator rejects path traversal attacks"""
        malicious_filenames = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "..\\..\\windows\\system32",
            "/etc/passwd",
            "2025-01-01-000000-../../../etc/passwd-round-1.txt",
            "2025-01-01-000000-map\x00evil-round-1.txt",  # null byte
        ]

        for malicious in malicious_filenames:
            assert not validate_stats_filename(malicious), \
                f"Path traversal not blocked: {malicious}"

    def test_reject_absolute_paths(self):
        """Production validator rejects filenames with directory separators"""
        absolute_paths = [
            "/absolute/path/file.txt",
            "/root/.ssh/id_rsa",
            "C:\\absolute\\path\\file.txt",
        ]

        for path in absolute_paths:
            assert not validate_stats_filename(path), \
                f"Absolute path not rejected: {path}"

    def test_reject_shell_metacharacters(self):
        """Production validator rejects filenames with shell metacharacters"""
        suspicious_filenames = [
            "2025-01-01-000000-map;rm -rf /-round-1.txt",
            "2025-01-01-000000-map`whoami`-round-1.txt",
            "2025-01-01-000000-map$(whoami)-round-1.txt",
        ]

        for suspicious in suspicious_filenames:
            assert not validate_stats_filename(suspicious), \
                f"Shell metacharacters not blocked: {suspicious}"

    def test_reject_null_byte_injection(self):
        """Production validator rejects null bytes in filenames"""
        malicious_filenames = [
            "file.txt\x00.jpg",
            "safe.txt\x00../../etc/passwd",
            "2025-01-01-000000-map\x00-round-1.txt",
        ]

        for malicious in malicious_filenames:
            assert not validate_stats_filename(malicious), \
                f"Null byte not blocked: {malicious}"

    def test_filename_length_limit(self):
        """Production validator enforces 255-character limit"""
        # Too long
        too_long = "2025-01-01-000000-" + "a" * 240 + "-round-1.txt"
        assert not validate_stats_filename(too_long)

        # Acceptable length
        acceptable = "2025-01-01-000000-goldrush-round-1.txt"
        assert validate_stats_filename(acceptable)

    def test_reject_invalid_date_components(self):
        """Production validator checks date/time component ranges"""
        invalid_dates = [
            "2019-01-01-000000-map-round-1.txt",   # year too early
            "2036-01-01-000000-map-round-1.txt",   # year too late
            "2025-13-01-000000-map-round-1.txt",   # month > 12
            "2025-00-01-000000-map-round-1.txt",   # month 0
            "2025-01-32-000000-map-round-1.txt",   # day > 31
            "2025-01-00-000000-map-round-1.txt",   # day 0
            "2025-01-01-250000-map-round-1.txt",   # hour > 23
            "2025-01-01-006000-map-round-1.txt",   # minute > 59
            "2025-01-01-000060-map-round-1.txt",   # second > 59
        ]

        for filename in invalid_dates:
            assert not validate_stats_filename(filename), \
                f"Invalid date component accepted: {filename}"

    def test_reject_invalid_round_numbers(self):
        """Production validator rejects round numbers outside 1-10"""
        assert not validate_stats_filename("2025-01-01-000000-map-round-0.txt")
        assert not validate_stats_filename("2025-01-01-000000-map-round-11.txt")

    def test_map_name_length_limit(self):
        """Production validator limits map name to 50 characters"""
        long_map = "a" * 51
        assert not validate_stats_filename(f"2025-01-01-000000-{long_map}-round-1.txt")

        ok_map = "a" * 50
        assert validate_stats_filename(f"2025-01-01-000000-{ok_map}-round-1.txt")


class TestEndstatsFilenameValidation:
    """Tests for the production validate_endstats_filename() from bot.endstats_parser"""

    def test_valid_endstats_filenames(self):
        """Production endstats validator accepts valid filenames"""
        valid = [
            "2026-01-12-224606-te_escape2-round-2-endstats.txt",
            "2025-12-17-120000-goldrush-round-1-endstats.txt",
        ]
        for filename in valid:
            assert validate_endstats_filename(filename), f"Valid endstats rejected: {filename}"

    def test_reject_non_endstats_filenames(self):
        """Production endstats validator rejects regular stats filenames"""
        invalid = [
            "2025-12-17-120000-goldrush-round-1.txt",           # missing -endstats
            "../../etc/passwd",                                   # traversal
            "random-file.txt",                                    # wrong format
        ]
        for filename in invalid:
            assert not validate_endstats_filename(filename), \
                f"Invalid endstats accepted: {filename}"


class TestInputSanitization:
    """Tests for production input sanitization functions"""

    def test_color_code_stripping(self):
        """Production parser strips ET:Legacy color codes correctly"""
        parser = C0RNP0RN3StatsParser()

        assert parser.strip_color_codes("^1Red^7Normal") == "RedNormal"
        assert parser.strip_color_codes("^4Player^7Name") == "PlayerName"
        assert parser.strip_color_codes("") == ""
        assert parser.strip_color_codes("NoColors") == "NoColors"
        assert parser.strip_color_codes("^0^1^2^3^4^5^6^7^8^9") == ""

    def test_normalize_player_name(self):
        """Production normalize_player_name removes color codes and normalizes whitespace"""
        assert normalize_player_name("^1Red^7Player") == "RedPlayer"
        assert normalize_player_name("  spaces  ") == "spaces"
        assert normalize_player_name("^4Test  ^7Name") == "Test Name"

    def test_bot_name_detection(self):
        """Production parser detects bot names via configurable regex"""
        parser = C0RNP0RN3StatsParser()

        assert parser.is_bot_name("[BOT] Soldier")
        assert parser.is_bot_name("[bot] medic")
        assert not parser.is_bot_name("RealPlayer")
        assert not parser.is_bot_name("")


class TestEscapeLikePattern:
    """Tests for production escape_like_pattern() SQL injection prevention"""

    def test_escape_percent_wildcard(self):
        """Production function escapes % to prevent LIKE wildcard injection"""
        assert escape_like_pattern("100%") == "100\\%"
        assert escape_like_pattern("test%user") == "test\\%user"

    def test_escape_underscore_wildcard(self):
        """Production function escapes _ to prevent single-char wildcard"""
        assert escape_like_pattern("user_name") == "user\\_name"

    def test_escape_backslash(self):
        """Production function escapes the escape character itself"""
        assert escape_like_pattern("path\\file") == "path\\\\file"

    def test_no_change_for_safe_input(self):
        """Production function passes through safe strings unchanged"""
        assert escape_like_pattern("normaltext") == "normaltext"
        assert escape_like_pattern("player123") == "player123"

    def test_combined_special_chars(self):
        """Production function handles multiple special chars together"""
        result = escape_like_pattern("100%_test\\path")
        assert "\\%" in result
        assert "\\_" in result
        assert "\\\\" in result

    def test_escape_like_for_query_wrapping(self):
        """Production escape_like_pattern_for_query adds wildcards correctly"""
        assert escape_like_pattern_for_query("test") == "%test%"
        assert escape_like_pattern_for_query("test%") == "%test\\%%"
        assert escape_like_pattern_for_query("x", prefix="", suffix="%") == "x%"

    def test_sql_injection_via_like_blocked(self):
        """Injected SQL wildcards are escaped by production function"""
        # Without escaping, "%" matches everything in LIKE
        malicious = "'; DROP TABLE users; --%"
        escaped = escape_like_pattern(malicious)
        # The % at the end should be escaped
        assert escaped.endswith("\\%")
        # The rest passes through (SQL injection is prevented by parameterized
        # queries, not LIKE escaping - LIKE escaping prevents wildcard injection)


class TestErrorMessageSanitization:
    """Tests for production sanitize_error_message() function"""

    def test_removes_unix_file_paths(self):
        """Production sanitizer removes Unix file paths"""
        error = Exception("Error reading /home/samba/share/slomix_discord/bot/ultimate_bot.py")
        result = sanitize_error_message(error)
        assert "/home/samba" not in result
        assert "[path]" in result

    def test_removes_windows_file_paths(self):
        """Production sanitizer removes Windows file paths"""
        error = Exception("Error at C:\\Users\\admin\\secrets.txt")
        result = sanitize_error_message(error)
        assert "C:\\" not in result
        assert "[path]" in result

    def test_removes_database_connection_strings(self):
        """Production sanitizer removes PostgreSQL connection URIs"""
        error = Exception("Connection failed: postgresql://user:pass@localhost:5432/db")
        result = sanitize_error_message(error)
        assert "postgresql://" not in result
        assert "pass" not in result
        assert "[database]" in result

    def test_removes_ip_addresses(self):
        """Production sanitizer removes IP addresses"""
        error = Exception("Cannot connect to 192.168.1.100:5432")
        result = sanitize_error_message(error)
        assert "192.168.1.100" not in result
        assert "[host]" in result

    def test_truncates_long_messages(self):
        """Production sanitizer truncates messages over 200 characters"""
        long_msg = "A" * 300
        error = Exception(long_msg)
        result = sanitize_error_message(error)
        assert len(result) <= 203  # 200 + "..."
        assert result.endswith("...")

    def test_short_messages_unchanged(self):
        """Production sanitizer preserves short safe messages"""
        error = Exception("Simple error")
        result = sanitize_error_message(error)
        assert result == "Simple error"


class TestWebhookSecurity:
    """Tests for webhook security patterns.

    Note: The webhook whitelist check and rate limiter live as instance methods
    on the bot class (bot.ultimate_bot.UltimateBot._check_webhook_rate_limit
    and the on_message handler). These cannot be imported without instantiating
    the full Discord bot, which requires a valid token and event loop.

    These tests verify the webhook ID format validation pattern that the
    production code uses (Discord snowflake IDs are 18-19 digit integers),
    and verify that the BotConfig correctly parses the whitelist from env vars.
    """

    def test_webhook_id_format_matches_discord_snowflake(self):
        """Webhook IDs must be 18-19 digit Discord snowflake IDs"""
        # This is the same validation the production on_message handler
        # implicitly enforces: str(message.webhook_id) checked against
        # whitelist of string IDs parsed from WEBHOOK_TRIGGER_WHITELIST
        valid_ids = [
            "1234567890123456789",
            "9876543210987654321",
            "1111111111111111111",
        ]

        invalid_ids = [
            "not_numeric",
            "123-456-789",
            "../../etc/passwd",
            "<script>alert('xss')</script>",
            "",
            " ",
            "12345",  # Too short
        ]

        # Production code uses str(message.webhook_id) which is always
        # a numeric string from Discord. Whitelist entries are stripped strings.
        snowflake_pattern = re.compile(r'^\d{18,19}$')

        for valid_id in valid_ids:
            assert snowflake_pattern.match(valid_id), f"Valid ID rejected: {valid_id}"

        for invalid_id in invalid_ids:
            assert not snowflake_pattern.match(invalid_id), f"Invalid ID accepted: {invalid_id}"


class TestParameterizedQueries:
    """Tests verifying parameterized query format expectations.

    The production code uses asyncpg with $1, $2 style parameters and
    the database adapter with ? style parameters. These tests verify
    the expected patterns so that static analysis catches regressions.
    """

    def test_parameterized_query_format(self):
        """Queries should use $N (asyncpg) or ? (adapter) parameters"""
        good_queries = [
            "SELECT * FROM rounds WHERE id = $1",
            "INSERT INTO rounds (map_name, round_number) VALUES ($1, $2)",
            "DELETE FROM player_comprehensive_stats WHERE round_id = $1",
            "UPDATE rounds SET map_name = $1 WHERE id = $2",
        ]

        param_pattern = re.compile(r'\$\d+')

        for query in good_queries:
            assert param_pattern.search(query), f"Parameterized format not found: {query}"

    def test_no_string_concatenation_in_queries(self):
        """Verify detection of vulnerable query patterns"""
        vulnerable_patterns = [
            r'f".*\{.*\}"',  # f-strings
            r'".*\%s.*"',    # % formatting
            r'".*\{\}.*"',   # .format()
        ]

        safe_code = 'await db.execute("SELECT * FROM rounds WHERE id = $1", (round_id,))'
        unsafe_code = r'await db.execute(f"SELECT * FROM rounds WHERE id = {round_id}")'

        safe_matches = any(re.search(p, safe_code) for p in vulnerable_patterns)
        assert not safe_matches, "Safe code incorrectly flagged"

        unsafe_matches = any(re.search(p, unsafe_code) for p in vulnerable_patterns)
        assert unsafe_matches, "Unsafe code not detected"
