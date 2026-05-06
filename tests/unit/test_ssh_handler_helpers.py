"""Tests for SSHHandler pure helpers + filename security gates.

The SSH handler is the boundary between the VPS and the bot's
filesystem. A regression in `_sanitize_stats_filename` silently lets
a malicious VPS-supplied path traverse out of the download dir
(e.g., `../../etc/passwd`).

`parse_gamestats_filename` drives every R1/R2 differential calc.
A regression returns wrong round_number → R2 differential subtracts
the wrong R1 → silent stat corruption.

Both are static methods, so testable without paramiko / network.
"""
from __future__ import annotations

import pytest

from bot.automation.ssh_handler import SSHHandler

# ---------------------------------------------------------------------------
# _sanitize_stats_filename — security gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("good", [
    "2025-10-02-232818-erdenberg_t2-round-2.txt",
    "2026-01-12-100000-supply-round-1.txt",
    "2026-04-21-235959-mp_oasis-round-10.txt",
    "2026-01-12-100000-supply-round-1-endstats.txt",
    "2026-01-12-100000-supply-round-1_ws.txt",
    "2026-01-12-100000-supply-round-1_engagements.txt",
    "gametime-supply-R1-1234567890.json",  # alt pattern
])
def test_sanitize_accepts_canonical_format(good):
    """Pin the full set of accepted patterns — a regex tightening
    would silently drop legitimate _engagements/_ws/-endstats files."""
    assert SSHHandler._sanitize_stats_filename(good) == good


def test_sanitize_strips_whitespace():
    """Trailing CRLF from the VPS sender must not reject the file."""
    out = SSHHandler._sanitize_stats_filename(
        "  2026-01-12-100000-supply-round-1.txt  \n"
    )
    assert out == "2026-01-12-100000-supply-round-1.txt"


def test_sanitize_rejects_empty_filename():
    """Empty / whitespace-only → ValueError (NOT silent pass)."""
    with pytest.raises(ValueError, match="required"):
        SSHHandler._sanitize_stats_filename("")
    with pytest.raises(ValueError, match="required"):
        SSHHandler._sanitize_stats_filename("   ")


def test_sanitize_rejects_none():
    with pytest.raises(ValueError, match="required"):
        SSHHandler._sanitize_stats_filename(None)


def test_sanitize_rejects_path_with_directory():
    """Filename containing a directory component → ValueError.
    Pin so a "../" or "subdir/foo.txt" can't traverse out of the
    expected download folder."""
    with pytest.raises(ValueError, match="Unsafe filename path"):
        SSHHandler._sanitize_stats_filename(
            "subdir/2026-01-12-100000-supply-round-1.txt"
        )


def test_sanitize_rejects_backslash():
    """Windows-style backslash → ValueError (Windows path traversal)."""
    with pytest.raises(ValueError, match="Unsafe filename path"):
        SSHHandler._sanitize_stats_filename(
            "subdir\\2026-01-12-100000-supply-round-1.txt"
        )


def test_sanitize_rejects_parent_directory_reference():
    """`..` anywhere in basename → ValueError. Pin the dedicated
    error message so operator triage is easier."""
    with pytest.raises(ValueError, match="Path traversal"):
        SSHHandler._sanitize_stats_filename(
            "2026-01-12-100000-..-round-1.txt"
        )


def test_sanitize_rejects_unexpected_format():
    """Filename without datetime prefix → ValueError."""
    with pytest.raises(ValueError, match="Unexpected stats filename format"):
        SSHHandler._sanitize_stats_filename("random-file.txt")


def test_sanitize_rejects_log_extension():
    """`.log` not in allowed extensions."""
    with pytest.raises(ValueError, match="Unexpected stats filename format"):
        SSHHandler._sanitize_stats_filename(
            "2026-01-12-100000-supply-round-1.log"
        )


def test_sanitize_rejects_absolute_path():
    """Absolute path → also rejected by basename != candidate guard."""
    with pytest.raises(ValueError, match="Unsafe filename path"):
        SSHHandler._sanitize_stats_filename(
            "/etc/2026-01-12-100000-supply-round-1.txt"
        )


# ---------------------------------------------------------------------------
# parse_gamestats_filename — round-number extraction (drives R1/R2 diff)
# ---------------------------------------------------------------------------


def test_parse_extracts_round_1_metadata():
    """R1 → is_round_1=True, is_round_2=False, is_map_complete=False."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-1.txt"
    )
    assert out is not None
    assert out["round_number"] == 1
    assert out["is_round_1"] is True
    assert out["is_round_2"] is False
    assert out["is_map_complete"] is False


def test_parse_extracts_round_2_metadata():
    """R2 → is_round_1=False, is_round_2=True, is_map_complete=True.
    Pin so the differential calculator reads the correct flag."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-2.txt"
    )
    assert out["round_number"] == 2
    assert out["is_round_1"] is False
    assert out["is_round_2"] is True
    assert out["is_map_complete"] is True  # R1 + R2 = complete


def test_parse_extracts_higher_rounds_not_complete():
    """Round 3+ → is_map_complete=False (only R2 is "complete").
    Pin so a custom 3-round mode doesn't silently mark R3 as complete."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-3.txt"
    )
    assert out["round_number"] == 3
    assert out["is_round_1"] is False
    assert out["is_round_2"] is False
    assert out["is_map_complete"] is False


def test_parse_extracts_full_timestamp():
    """`100000` → `10:00:00` (HH:MM:SS format)."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-1.txt"
    )
    assert out["full_timestamp"] == "2026-01-12 10:00:00"


def test_parse_extracts_underscored_map_name():
    """Maps with underscores parse cleanly (regex uses non-greedy)."""
    out = SSHHandler.parse_gamestats_filename(
        "2025-10-02-232818-erdenberg_t2-round-2.txt"
    )
    assert out["map_name"] == "erdenberg_t2"


def test_parse_extracts_hyphenated_map_name():
    """Maps with hyphens — pin since `-round-` could otherwise eat
    too much."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-mp-oasis-round-1.txt"
    )
    assert out["map_name"] == "mp-oasis"
    assert out["round_number"] == 1


def test_parse_returns_none_for_endstats_variant():
    """The simple gamestats parser does NOT match -endstats files
    (those use a different parser). Pin the divergence."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-1-endstats.txt"
    )
    # The pattern is `-round-(\d+)\.txt$` — endstats has more after
    # round-1, so it doesn't match this strict pattern.
    assert out is None


def test_parse_returns_none_for_ws_variant():
    """`_ws.txt` suffix → not matched by gamestats pattern."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-1_ws.txt"
    )
    assert out is None


@pytest.mark.parametrize("bad", [
    "stats.txt",
    "2026-01-12-supply-round-1.txt",  # missing time
    "2026-01-12-100000-supply-round-1.log",  # wrong ext
    "2026-1-12-100000-supply-round-1.txt",  # 1-digit month
    "",
])
def test_parse_returns_none_for_garbage(bad):
    assert SSHHandler.parse_gamestats_filename(bad) is None


def test_parse_preserves_filename_in_output():
    """The original filename is included so caller can pass it to
    later steps without keeping a separate var."""
    src = "2026-01-12-100000-supply-round-1.txt"
    out = SSHHandler.parse_gamestats_filename(src)
    assert out["filename"] == src


def test_parse_round_number_is_int_not_string():
    """`round_number` parsed as int — pin so a regression to keep it
    as str doesn't break callers doing arithmetic comparisons."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-2.txt"
    )
    assert isinstance(out["round_number"], int)


def test_parse_date_and_time_are_strings():
    """Date and time fields stay as strings in the original format
    (date='YYYY-MM-DD', time='HHMMSS')."""
    out = SSHHandler.parse_gamestats_filename(
        "2026-01-12-100000-supply-round-1.txt"
    )
    assert out["date"] == "2026-01-12"
    assert out["time"] == "100000"
