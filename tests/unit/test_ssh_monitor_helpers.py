"""Tests for SSHMonitor pure helpers (legacy DISABLED service).

Although the SSH monitor is disabled in production (replaced by the
endstats_monitor task loop), the pure helpers in this module — config
validation, voice-count detection, match-type detection, filename
parsing, sanitisation, and get_stats — are still loaded and exposed
on the bot. A regression silently:

- _validate_config: misses an empty config field → SSH starts with
  half-a-config, fails opaquely.
- _parse_file_timestamp: silently returns None on legitimate files →
  every file looks "old".
- _sanitize_stats_filename: lets a malicious basename through.
- _detect_match_type: 3v3 misclassified as "regular" → wrong embed
  template.

DB-bound `_load_processed_files` is NOT covered (requires async DB).
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import discord
import pytest

from bot.services.automation.ssh_monitor import SSHMonitor


def _make_bot(host="vps", user="et", key="/home/x/.ssh/key", remote="/stats",
              gaming_voice_channels=None, channel_members=None):
    """Build a fake bot with the attributes SSHMonitor reads in __init__."""
    bot = MagicMock()
    bot.config.ssh_enabled = True
    bot.config.ssh_host = host
    bot.config.ssh_port = 22
    bot.config.ssh_user = user
    bot.config.ssh_key_path = key
    bot.config.ssh_remote_path = remote
    bot.config.ssh_check_interval = 60
    bot.config.ssh_startup_lookback_hours = 24
    bot.config.ssh_voice_conditional = False
    bot.config.ssh_grace_period_minutes = 30
    bot.production_channel_id = 0
    bot.admin_channel_id = 0
    bot.gaming_voice_channels = gaming_voice_channels or []

    if channel_members:
        # bot.get_channel returns a VoiceChannel-like with .members
        def _get_channel(cid):
            count = channel_members.get(cid, None)
            if count is None:
                return None
            ch = MagicMock(spec=discord.VoiceChannel)
            ch.members = [MagicMock() for _ in range(count)]
            return ch
        bot.get_channel.side_effect = _get_channel
    else:
        bot.get_channel.return_value = None

    return bot


@pytest.fixture
def monitor():
    """Build a minimal SSHMonitor with valid config."""
    return SSHMonitor(_make_bot())


# ---------------------------------------------------------------------------
# _validate_config — config completeness check
# ---------------------------------------------------------------------------


def test_validate_config_returns_true_when_all_set():
    m = SSHMonitor(_make_bot())
    assert m._validate_config() is True


@pytest.mark.parametrize("missing_field", ["host", "user", "key", "remote"])
def test_validate_config_returns_false_when_field_missing(missing_field):
    """Each required field individually empty → False. Pin so a deploy
    that drops one env var (e.g., SSH_KEY_PATH) is caught at startup."""
    fields = {"host": "h", "user": "u", "key": "k", "remote": "r"}
    fields[missing_field] = ""
    bot = _make_bot(**fields)
    m = SSHMonitor(bot)
    assert m._validate_config() is False


def test_validate_config_handles_none_values():
    """None config values (legacy) → False, no crash."""
    bot = _make_bot()
    bot.config.ssh_host = None
    m = SSHMonitor(bot)
    assert m._validate_config() is False


# ---------------------------------------------------------------------------
# _get_voice_player_count — voice channel aggregation
# ---------------------------------------------------------------------------


def test_voice_count_returns_minus_one_when_no_channels_configured():
    """No gaming_voice_channels attr or empty → -1 (sentinel for
    'voice monitoring disabled'). Pin the sentinel so callers can
    distinguish "disabled" from "0 players"."""
    bot = _make_bot(gaming_voice_channels=[])
    m = SSHMonitor(bot)
    assert m._get_voice_player_count() == -1


def test_voice_count_returns_minus_one_when_attr_missing():
    bot = _make_bot()
    delattr(bot, "gaming_voice_channels")
    m = SSHMonitor(bot)
    assert m._get_voice_player_count() == -1


def test_voice_count_sums_across_channels():
    """Multiple channels → sum of all members."""
    bot = _make_bot(
        gaming_voice_channels=[100, 200],
        channel_members={100: 3, 200: 4},
    )
    m = SSHMonitor(bot)
    assert m._get_voice_player_count() == 7


def test_voice_count_zero_when_channels_empty():
    """Channels exist but no members → 0 (NOT -1)."""
    bot = _make_bot(
        gaming_voice_channels=[100],
        channel_members={100: 0},
    )
    m = SSHMonitor(bot)
    assert m._get_voice_player_count() == 0


def test_voice_count_returns_minus_one_on_exception():
    """Any error → -1 (fail-open: assume voice monitoring broken,
    keep checking SSH)."""
    bot = _make_bot(gaming_voice_channels=[100])
    bot.get_channel.side_effect = RuntimeError("oops")
    m = SSHMonitor(bot)
    assert m._get_voice_player_count() == -1


# ---------------------------------------------------------------------------
# _detect_match_type — 3v3 / 6v6 / regular
# ---------------------------------------------------------------------------


def test_detect_match_type_3v3():
    """Two channels with 3 players each → "3v3"."""
    bot = _make_bot(
        gaming_voice_channels=[100, 200],
        channel_members={100: 3, 200: 3},
    )
    m = SSHMonitor(bot)
    assert m._detect_match_type() == "3v3"


def test_detect_match_type_6v6():
    bot = _make_bot(
        gaming_voice_channels=[100, 200],
        channel_members={100: 6, 200: 6},
    )
    m = SSHMonitor(bot)
    assert m._detect_match_type() == "6v6"


def test_detect_match_type_regular_when_uneven():
    """3 vs 4 → "regular" (NOT 3v3 — pin so a substituted-mid-match
    state doesn't get the wrong embed)."""
    bot = _make_bot(
        gaming_voice_channels=[100, 200],
        channel_members={100: 3, 200: 4},
    )
    m = SSHMonitor(bot)
    assert m._detect_match_type() == "regular"


def test_detect_match_type_regular_when_no_channels():
    bot = _make_bot(gaming_voice_channels=[])
    m = SSHMonitor(bot)
    assert m._detect_match_type() == "regular"


def test_detect_match_type_skips_empty_channels():
    """Channels with 0 players are filtered out — pin so a leftover
    voice channel doesn't pollute the count list."""
    bot = _make_bot(
        gaming_voice_channels=[100, 200, 300],
        channel_members={100: 3, 200: 0, 300: 3},
    )
    m = SSHMonitor(bot)
    # Filter empty (200) → [3, 3] → 3v3
    assert m._detect_match_type() == "3v3"


def test_detect_match_type_regular_for_single_team():
    """Only one populated channel → "regular" (no opposing team)."""
    bot = _make_bot(
        gaming_voice_channels=[100],
        channel_members={100: 6},
    )
    m = SSHMonitor(bot)
    assert m._detect_match_type() == "regular"


# ---------------------------------------------------------------------------
# _parse_file_timestamp — filename → datetime
# ---------------------------------------------------------------------------


def test_parse_timestamp_success(monitor):
    out = monitor._parse_file_timestamp(
        "2025-11-16-142030-supply-round-1.txt"
    )
    assert out == datetime(2025, 11, 16, 14, 20, 30)


def test_parse_timestamp_handles_underscored_map(monitor):
    """Map name with extra hyphens (e.g., et_ice) — the parser only
    cares about the first 4 dash-separated chunks."""
    out = monitor._parse_file_timestamp(
        "2025-11-16-142030-et_ice-round-1.txt"
    )
    assert out == datetime(2025, 11, 16, 14, 20, 30)


def test_parse_timestamp_returns_none_for_short_filename(monitor):
    """<5 dash-separated parts → None (NOT crash)."""
    assert monitor._parse_file_timestamp("foo-bar.txt") is None


def test_parse_timestamp_returns_none_for_garbage(monitor):
    assert monitor._parse_file_timestamp("garbage") is None
    assert monitor._parse_file_timestamp("") is None


def test_parse_timestamp_returns_none_for_5_digit_time(monitor):
    """Time must be exactly 6 digits (HHMMSS); 5 → None."""
    out = monitor._parse_file_timestamp(
        "2025-11-16-14203-supply-round-1.txt"
    )
    assert out is None


def test_parse_timestamp_returns_none_for_invalid_date(monitor):
    """Non-numeric or out-of-range date → None (caught by ValueError)."""
    out = monitor._parse_file_timestamp(
        "2025-13-99-142030-supply-round-1.txt"  # month=13
    )
    assert out is None


def test_parse_timestamp_returns_none_for_invalid_time(monitor):
    """Out-of-range time component → None."""
    out = monitor._parse_file_timestamp(
        "2025-11-16-256099-supply-round-1.txt"  # hour=25, minute=60, sec=99
    )
    assert out is None


# ---------------------------------------------------------------------------
# _sanitize_stats_filename — security gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("good", [
    "2025-11-16-142030-supply-round-1.txt",
    "stats_file.log",
    "round-1.txt",
    "a.b.c-d_e.txt",
])
def test_sanitize_accepts_safe_filenames(good):
    """Allowed charset: alnum + . _ -. Pin so a regression that adds
    `/` or `\\` to allowlist is loud."""
    assert SSHMonitor._sanitize_stats_filename(good) == good


def test_sanitize_strips_whitespace():
    """Leading/trailing whitespace stripped."""
    out = SSHMonitor._sanitize_stats_filename("  file.txt  ")
    assert out == "file.txt"


@pytest.mark.parametrize("bad", [
    "",
    None,
    ".",
    "..",
    "subdir/file.txt",      # path separator
    "../../etc/passwd",     # traversal
    "file with spaces.txt", # space NOT in allowlist
    "file%20.txt",          # % not allowed
    "file'.txt",            # quote not allowed
])
def test_sanitize_rejects_unsafe(bad):
    assert SSHMonitor._sanitize_stats_filename(bad) is None


def test_sanitize_rejects_too_long():
    """>255 chars → None."""
    assert SSHMonitor._sanitize_stats_filename("a" * 256) is None


def test_sanitize_accepts_at_255_boundary():
    """Exactly 255 chars → OK (boundary inclusive)."""
    f = "a" * 255
    assert SSHMonitor._sanitize_stats_filename(f) == f


# ---------------------------------------------------------------------------
# get_stats — admin status payload
# ---------------------------------------------------------------------------


def test_get_stats_includes_required_keys(monitor):
    out = monitor.get_stats()
    expected = {
        "is_monitoring", "files_processed", "files_tracked",
        "errors_count", "last_error", "last_check",
        "avg_check_time_ms", "avg_download_time_ms", "check_interval",
    }
    assert expected.issubset(set(out.keys()))


def test_get_stats_zero_avg_when_no_check_times(monitor):
    """Empty history → avg=0 (NOT crash on division)."""
    monitor.check_times = []
    monitor.download_times = []
    out = monitor.get_stats()
    assert out["avg_check_time_ms"] == 0
    assert out["avg_download_time_ms"] == 0


def test_get_stats_computes_avg_in_milliseconds(monitor):
    """Stored as seconds, returned in ms."""
    monitor.check_times = [0.5, 1.0]  # 500ms, 1000ms → avg 750ms
    out = monitor.get_stats()
    assert out["avg_check_time_ms"] == 750.0


def test_get_stats_files_tracked_is_set_size(monitor):
    """files_tracked = len(processed_files set)."""
    monitor.processed_files = {"a.txt", "b.txt", "c.txt"}
    out = monitor.get_stats()
    assert out["files_tracked"] == 3
