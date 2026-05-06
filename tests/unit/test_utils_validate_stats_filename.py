"""Tests for the canonical `validate_stats_filename` and
`normalize_player_name` helpers in bot/core/utils.py.

`validate_stats_filename` is the security gate for every webhook
trigger and SSH-discovered file. ultimate_bot.py and webhook_handler
both delegate to it. A regression silently lets a malicious filename
through to file processing OR drops legitimate rounds.

`normalize_player_name` underpins every name comparison in the parser
and aggregator. A regression in color-code stripping splits one
player across many DB rows.

`_parse_round_datetime` is the shared date+time → datetime parser used
by round_linker.

All three are pure helpers — pin every branch.
"""
from __future__ import annotations

import pytest

from bot.core.round_linker import _parse_round_datetime
from bot.core.utils import normalize_player_name, validate_stats_filename

# ---------------------------------------------------------------------------
# validate_stats_filename — security gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("good", [
    "2025-12-09-221829-etl_sp_delivery-round-1.txt",
    "2026-01-12-100000-supply-round-2.txt",
    "2020-01-01-000000-a-round-1.txt",
    "2035-12-31-235959-radar-round-10.txt",
    "2026-04-21-120000-mp_oasis-round-3.txt",
])
def test_validate_stats_accepts_canonical_format(good):
    """Pin happy-path examples so a regex tweak that breaks them is
    immediately visible in CI."""
    assert validate_stats_filename(good) is True


@pytest.mark.parametrize("bad", [
    "../etc/passwd",
    "2026-01-12-100000-../supply-round-1.txt",  # embedded ..
    "2026-01-12/100000-supply-round-1.txt",     # slash
    "2026-01-12-100000-supply-round-1.txt\0",   # null byte
    "2026-01-12-100000-supply-round-1.txt\\evil",  # backslash
])
def test_validate_stats_rejects_path_injections(bad):
    """Path-traversal + injection chars MUST be rejected before any
    file open. A regression here is a security bug."""
    assert validate_stats_filename(bad) is False


def test_validate_stats_rejects_too_long_filename():
    """>255 chars → rejected (DoS prevention)."""
    f = "a" * 256 + ".txt"
    assert validate_stats_filename(f) is False


@pytest.mark.parametrize("bad", [
    "stats.txt",                                      # no datetime
    "2026-01-12-supply-round-1.txt",                  # missing time
    "2026-01-12-100000-supply-round-1.log",           # wrong ext
    "2026-1-12-100000-supply-round-1.txt",            # 1-digit month
    "26-01-12-100000-supply-round-1.txt",             # 2-digit year
    "2026-01-12-100000-supply-round-1",               # no .txt
    "2026-01-12-100000-supply-round-1-endstats.txt",  # endstats variant
])
def test_validate_stats_rejects_pattern_violations(bad):
    """Reject everything that doesn't match the strict format."""
    assert validate_stats_filename(bad) is False


@pytest.mark.parametrize("bad", [
    "2019-01-12-100000-supply-round-1.txt",  # year < 2020
    "2036-01-12-100000-supply-round-1.txt",  # year > 2035
    "2026-00-12-100000-supply-round-1.txt",  # month=0
    "2026-13-12-100000-supply-round-1.txt",  # month=13
    "2026-01-00-100000-supply-round-1.txt",  # day=0
    "2026-01-32-100000-supply-round-1.txt",  # day=32
])
def test_validate_stats_rejects_invalid_date_components(bad):
    assert validate_stats_filename(bad) is False


@pytest.mark.parametrize("bad", [
    "2026-01-12-246060-supply-round-1.txt",  # hour=24
    "2026-01-12-126060-supply-round-1.txt",  # minute=60
    "2026-01-12-125960-supply-round-1.txt",  # 12:59:60 sec=60
])
def test_validate_stats_rejects_invalid_timestamp(bad):
    assert validate_stats_filename(bad) is False


@pytest.mark.parametrize("bad_round", ["0", "11", "99"])
def test_validate_stats_rejects_round_outside_1_to_10(bad_round):
    f = f"2026-01-12-100000-supply-round-{bad_round}.txt"
    assert validate_stats_filename(f) is False


@pytest.mark.parametrize("good_round", ["1", "2", "5", "10"])
def test_validate_stats_accepts_round_1_through_10(good_round):
    f = f"2026-01-12-100000-supply-round-{good_round}.txt"
    assert validate_stats_filename(f) is True


def test_validate_stats_rejects_map_name_too_long():
    """map_name > 50 chars → rejected."""
    long_map = "x" * 51
    f = f"2026-01-12-100000-{long_map}-round-1.txt"
    assert validate_stats_filename(f) is False


def test_validate_stats_accepts_map_name_at_50_char_boundary():
    map50 = "x" * 50
    f = f"2026-01-12-100000-{map50}-round-1.txt"
    assert validate_stats_filename(f) is True


@pytest.mark.parametrize("bad_map", ["map name", "map.name", "map'name"])
def test_validate_stats_rejects_disallowed_map_chars(bad_map):
    """map_name allowlist is alnum + hyphen + underscore only."""
    f = f"2026-01-12-100000-{bad_map}-round-1.txt"
    assert validate_stats_filename(f) is False


# ---------------------------------------------------------------------------
# normalize_player_name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("raw, expected", [
    ("^1Hello",                      "Hello"),
    ("^1H^2e^3l^4l^5o",              "Hello"),
    ("^aMixed^Bcase",                "Mixedcase"),
    ("Plain",                        "Plain"),
    ("",                             ""),
])
def test_normalize_strips_color_codes(raw, expected):
    assert normalize_player_name(raw) == expected


def test_normalize_collapses_multiple_whitespace():
    """Runs of whitespace → single space. Pinned because the parser
    output sometimes contains tab + multiple spaces and downstream
    GROUP BY player_name must match across rows."""
    assert normalize_player_name("Player\t  Name") == "Player Name"
    assert normalize_player_name("a   b   c") == "a b c"


def test_normalize_strips_leading_trailing_whitespace():
    """A regression that omitted the trailing .strip() would split one
    player across rows by leading-space variants."""
    assert normalize_player_name("  Player  ") == "Player"


def test_normalize_strips_color_codes_then_whitespace():
    """Color stripping happens BEFORE whitespace collapse — verify the
    order doesn't matter for the final result."""
    assert normalize_player_name("^1  Player  ") == "Player"


def test_normalize_handles_color_codes_with_internal_whitespace():
    """`^1Player ^2Name` → `Player Name` (single space)."""
    assert normalize_player_name("^1Player ^2Name") == "Player Name"


def test_normalize_handles_lone_caret():
    """`^` not followed by alnum is preserved (regex match contract)."""
    out = normalize_player_name("foo^^bar")
    assert "^" in out


# ---------------------------------------------------------------------------
# _parse_round_datetime — round_linker private helper
# ---------------------------------------------------------------------------


def test_parse_round_datetime_basic():
    """Date+time → datetime. Pin format: time must be 6 digits HHMMSS
    (with or without colons)."""
    out = _parse_round_datetime("2026-04-21", "120000")
    assert out is not None
    assert out.year == 2026
    assert out.month == 4
    assert out.day == 21
    assert out.hour == 12
    assert out.minute == 0
    assert out.second == 0


def test_parse_round_datetime_strips_colons():
    """`12:00:00` is converted to `120000` before parsing."""
    out = _parse_round_datetime("2026-04-21", "12:00:00")
    assert out is not None
    assert out.hour == 12


def test_parse_round_datetime_returns_none_on_missing_inputs():
    """Either date or time None/empty → None (caller handles fallback)."""
    assert _parse_round_datetime(None, "120000") is None
    assert _parse_round_datetime("2026-04-21", None) is None
    assert _parse_round_datetime("", "120000") is None
    assert _parse_round_datetime("2026-04-21", "") is None


def test_parse_round_datetime_returns_none_on_short_time():
    """Time string ≠ 6 digits after colon-strip → None.
    Pin so a 5-digit padding bug doesn't accidentally parse to wrong
    second-of-day."""
    assert _parse_round_datetime("2026-04-21", "12000") is None  # 5 digits
    assert _parse_round_datetime("2026-04-21", "1200000") is None  # 7 digits


def test_parse_round_datetime_returns_none_on_invalid_date_format():
    assert _parse_round_datetime("21-04-2026", "120000") is None  # DMY
    assert _parse_round_datetime("garbage", "120000") is None


def test_parse_round_datetime_returns_none_on_out_of_range_components():
    """strptime's strictness catches 13:00:00 month and 25:00:00 hour."""
    assert _parse_round_datetime("2026-13-21", "120000") is None  # month=13
    assert _parse_round_datetime("2026-04-21", "250000") is None  # hour=25


def test_parse_round_datetime_returns_naive_datetime():
    """The returned datetime has NO tzinfo. Pinned because the caller
    (resolve_round_id) does naive-local subtraction; a tz-aware object
    would crash with TypeError."""
    out = _parse_round_datetime("2026-04-21", "120000")
    assert out is not None
    assert out.tzinfo is None
