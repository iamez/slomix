"""Tests for bot/core/utils.py — pure helper contracts.

These helpers ship across many cogs (escape SQL LIKE, format duration,
truncate strings, sanitize error messages). They are pure functions
with well-defined contracts but had thin coverage outside the security
suite. Pin each contract here so future "convenience refactors" can't
silently change SQL escaping rules or error redaction patterns.
"""
from __future__ import annotations

import pytest

from bot.core.utils import (
    escape_like_pattern,
    escape_like_pattern_for_query,
    format_duration,
    sanitize_error_message,
    truncate_string,
)


# ---------------------------------------------------------------------------
# escape_like_pattern
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("plain",          "plain"),                  # no special chars
    ("100%",           "100\\%"),                  # one wildcard
    ("a%b",            "a\\%b"),
    ("a_b",            "a\\_b"),                   # underscore wildcard
    ("100% _test_",    "100\\% \\_test\\_"),       # mixed
    ("",               ""),
])
def test_escape_like_pattern_basic_wildcards(raw, expected):
    assert escape_like_pattern(raw) == expected


def test_escape_like_pattern_escapes_escape_char_first():
    """The escape char itself must be escaped first; otherwise the
    subsequent wildcard escapes get clobbered when the raw input
    already contains a backslash."""
    # Input has both a wildcard AND a backslash → both get doubled-escape
    raw = r"a\%b"
    out = escape_like_pattern(raw)
    # Backslash doubled → 'a\\\\%b' → 'a\\\\\\%b' after % escape
    assert out == r"a\\\%b"


def test_escape_like_pattern_with_custom_escape_char():
    """A user-supplied custom escape char (e.g. '!') must be doubled
    + then used to escape % and _."""
    out = escape_like_pattern("100% _x_", escape_char="!")
    assert out == "100!% !_x!_"


# ---------------------------------------------------------------------------
# escape_like_pattern_for_query
# ---------------------------------------------------------------------------


def test_escape_like_pattern_for_query_default_wraps_with_percent():
    """Default contains-search wraps both ends with %."""
    assert escape_like_pattern_for_query("foo") == "%foo%"


def test_escape_like_pattern_for_query_starts_with_when_no_prefix():
    """prefix='' → starts-with search."""
    assert escape_like_pattern_for_query("foo", prefix="") == "foo%"


def test_escape_like_pattern_for_query_ends_with_when_no_suffix():
    assert escape_like_pattern_for_query("foo", suffix="") == "%foo"


def test_escape_like_pattern_for_query_escapes_internal_wildcards():
    """User input with literal % gets escaped, then wrapped with the
    actual wildcard %. Pinpoint the difference between literal and wildcard."""
    out = escape_like_pattern_for_query("100%")
    assert out == "%100\\%%"  # \\% is the literal, trailing % is the wildcard


# ---------------------------------------------------------------------------
# sanitize_error_message
# ---------------------------------------------------------------------------


def test_sanitize_redacts_postgresql_url():
    err = Exception(
        "could not connect: postgresql://user:secret@host.example.com:5432/db"
    )
    out = sanitize_error_message(err)
    assert "secret" not in out
    assert "[database]" in out


def test_sanitize_redacts_postgres_url_short_form():
    err = Exception("postgres://admin:pwd@1.2.3.4/db")
    out = sanitize_error_message(err)
    assert "pwd" not in out
    assert "[database]" in out


def test_sanitize_redacts_unix_paths():
    err = Exception("file not found: /home/user/secrets.txt")
    out = sanitize_error_message(err)
    assert "/home/user/secrets.txt" not in out
    assert "[path]" in out


def test_sanitize_redacts_windows_paths():
    err = Exception(r"file not found: C:\Users\admin\creds.txt")
    out = sanitize_error_message(err)
    assert r"C:\Users\admin\creds.txt" not in out
    assert "[path]" in out


def test_sanitize_redacts_ip_addresses():
    err = Exception("connection failed to 192.168.1.42")
    out = sanitize_error_message(err)
    assert "192.168.1.42" not in out
    assert "[host]" in out


def test_sanitize_redacts_ip_with_port():
    err = Exception("connection failed to 10.0.0.5:5432")
    out = sanitize_error_message(err)
    assert "10.0.0.5" not in out
    assert "[host]" in out


def test_sanitize_truncates_long_messages():
    """Cap at 200 chars + ellipsis to prevent log/embed flooding."""
    long_msg = "x" * 500
    err = Exception(long_msg)
    out = sanitize_error_message(err)
    assert len(out) <= 203  # 200 + "..."
    assert out.endswith("...")


def test_sanitize_passes_short_safe_message_through():
    err = Exception("simple error message")
    assert sanitize_error_message(err) == "simple error message"


def test_sanitize_database_url_redacted_before_path_regex():
    """Order of regexes matters: postgresql:// must be redacted FIRST,
    otherwise the path regex would catch user/secret@host as "[path]"
    and lose the [database] label."""
    err = Exception("postgresql://u:p@host/db missing")
    out = sanitize_error_message(err)
    assert "[database]" in out
    # The path regex shouldn't have fired on what was already redacted
    assert out.count("[database]") == 1


# ---------------------------------------------------------------------------
# format_duration
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seconds, expected", [
    (0,       "0s"),
    (1,       "1s"),
    (59,      "59s"),
    (60,      "1m"),
    (61,      "1m 1s"),
    (90,      "1m 30s"),
    (3599,    "59m 59s"),
    (3600,    "1h"),
    (3660,    "1h 1m"),
    (7200,    "2h"),
    (3661,    "1h 1m"),  # seconds within remaining_minutes are dropped
    (86400,   "24h"),
])
def test_format_duration_known_values(seconds, expected):
    assert format_duration(seconds) == expected


def test_format_duration_drops_seconds_at_hour_scale():
    """3661s = 1h 1m 1s → format truncates to "1h 1m" (no seconds at hour scale).
    Pin that explicitly so a future "show seconds always" change is loud."""
    assert format_duration(3661) == "1h 1m"


# ---------------------------------------------------------------------------
# truncate_string
# ---------------------------------------------------------------------------


def test_truncate_below_limit_passes_through():
    assert truncate_string("short", max_length=10) == "short"


def test_truncate_at_exact_limit_passes_through():
    assert truncate_string("exactlyten", max_length=10) == "exactlyten"


def test_truncate_above_limit_adds_ellipsis():
    """Truncates to max_length total — ellipsis + content sums to limit."""
    out = truncate_string("a very long sentence", max_length=10)
    assert len(out) == 10
    assert out.endswith("...")


def test_truncate_default_limit_is_100():
    s = "x" * 200
    out = truncate_string(s)
    assert len(out) == 100


def test_truncate_empty_string():
    assert truncate_string("") == ""
