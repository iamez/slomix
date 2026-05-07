"""Tests for StatsWebSocketClient pure helpers + init validation.

This client receives push notifications from the VPS for new stats
files. A regression silently:

- _is_valid_stats_filename: lets a malicious filename ("../../etc/
  passwd") through to file processing — security bug.
- ws_scheme normalisation: ships with ws:// (insecure) when
  config has trailing whitespace.
- get_status reports stale data → admin sees wrong connection state.

DB/Discord-bound `_handle_message` is harder to test, but
`_is_valid_stats_filename` is the inner security gate.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.automation.ws_client import StatsWebSocketClient


def _make_client(ws_scheme="wss", ws_host="vps.example.com", ws_port=8080,
                 ws_auth_token="dummy-test-token", ws_enabled=True):  # noqa: S107
    """Build a client with a fake config + AsyncMock callback."""
    config = MagicMock()
    config.ws_scheme = ws_scheme
    config.ws_host = ws_host
    config.ws_port = ws_port
    config.ws_auth_token = ws_auth_token
    config.ws_enabled = ws_enabled
    config.ws_reconnect_delay = 5
    return StatsWebSocketClient(config=config, on_new_file=AsyncMock())


# ---------------------------------------------------------------------------
# _is_valid_stats_filename — security gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("good", [
    "2026-01-12-100000-supply-round-1.txt",
    "2025-12-09-221829-etl_sp_delivery-round-2.txt",
    "2026-04-21-235959-mp_oasis-round-10.txt",
    "2026-01-01-000000-supply-round-1-endstats.txt",
    "2026-01-12-100000-supply-round-1_ws.txt",  # _ws suffix variant
    "2026-01-12-100000-radar2-round-3.txt",  # digit in map name
    "2026-01-12-100000-map.with.dots-round-1.txt",  # dot in map (allowed by regex)
])
def test_validate_accepts_good_filenames(good):
    assert StatsWebSocketClient._is_valid_stats_filename(good) is True


@pytest.mark.parametrize("bad", [
    "../etc/passwd",
    "2026-01-12-100000-../supply-round-1.txt",  # embedded ..
    "2026-01-12/100000-supply-round-1.txt",     # slash
    "2026-01-12\\100000-supply-round-1.txt",    # backslash
    "stats.txt",                                 # no datetime
    "2026-01-12-supply-round-1.txt",             # missing time
    "2026-1-12-100000-supply-round-1.txt",       # 1-digit month
    "26-01-12-100000-supply-round-1.txt",        # 2-digit year
    "2026-01-12-100000-supply-round-1.log",      # wrong ext
    "",                                          # empty
])
def test_validate_rejects_bad_filenames(bad):
    assert StatsWebSocketClient._is_valid_stats_filename(bad) is False


def test_validate_rejects_too_long_filename():
    f = "2026-01-12-100000-" + ("x" * 250) + "-round-1.txt"
    # >255 chars → rejected up front
    assert len(f) > 255
    assert StatsWebSocketClient._is_valid_stats_filename(f) is False


def test_validate_handles_none():
    """None → False (str(None or '') = '' which fails)."""
    assert StatsWebSocketClient._is_valid_stats_filename(None) is False


def test_validate_strips_whitespace():
    """Leading/trailing whitespace stripped before validation. Pin so
    the VPS sender's CRLF doesn't reject legitimate filenames."""
    out = StatsWebSocketClient._is_valid_stats_filename(
        "  2026-01-12-100000-supply-round-1.txt  \n",
    )
    assert out is True


def test_validate_rejects_dotdot_anywhere():
    """`..` anywhere in the name (not just at start) → reject."""
    assert StatsWebSocketClient._is_valid_stats_filename(
        "2026-01-12-100000-supply..-round-1.txt",
    ) is False


# ---------------------------------------------------------------------------
# __init__ — URI building + scheme validation
# ---------------------------------------------------------------------------


def test_init_builds_wss_uri():
    c = _make_client(ws_scheme="wss", ws_host="example.com", ws_port=443)
    assert c.uri == "wss://example.com:443"


def test_init_builds_ws_uri_when_explicitly_set():
    """Insecure ws:// must be honoured (operator override)."""
    c = _make_client(ws_scheme="ws", ws_host="local.dev", ws_port=8080)
    assert c.uri == "ws://local.dev:8080"


def test_init_unknown_scheme_falls_back_to_wss():
    """Garbage scheme → safe default wss. Pin so a typo in env doesn't
    silently disable encryption."""
    c = _make_client(ws_scheme="garbage")
    assert c.uri.startswith("wss://")


def test_init_empty_scheme_falls_back_to_wss():
    """Empty / None scheme → wss default."""
    c = _make_client(ws_scheme="")
    assert c.uri.startswith("wss://")


def test_init_normalises_scheme_case():
    """`WSS` → `wss` (lowercased)."""
    c = _make_client(ws_scheme="WSS")
    assert c.uri.startswith("wss://")


def test_init_strips_scheme_whitespace():
    """`  wss  ` → `wss`."""
    c = _make_client(ws_scheme="  wss  ")
    assert c.uri.startswith("wss://")


# ---------------------------------------------------------------------------
# __init__ — initial state
# ---------------------------------------------------------------------------


def test_init_starts_disconnected():
    c = _make_client()
    assert c._connected is False
    assert c._ws is None
    assert c._task is None
    assert c._running is False


def test_init_zeros_stats_counters():
    """files_received and reconnect_count start at 0;
    last_notification is None."""
    c = _make_client()
    assert c.files_received == 0
    assert c.reconnect_count == 0
    assert c.last_notification is None


def test_init_stores_callback():
    cb = AsyncMock()
    config = MagicMock()
    config.ws_scheme = "wss"
    config.ws_host = "x"
    config.ws_port = 1
    config.ws_auth_token = ""
    client = StatsWebSocketClient(config=config, on_new_file=cb)
    assert client.on_new_file is cb


# ---------------------------------------------------------------------------
# is_connected — combined state check
# ---------------------------------------------------------------------------


def test_is_connected_false_when_no_websocket():
    c = _make_client()
    c._connected = True  # flag set
    c._ws = None  # but no ws → not connected
    assert c.is_connected is False


def test_is_connected_false_when_flag_false():
    c = _make_client()
    c._connected = False
    c._ws = MagicMock()  # ws set but flag false
    assert c.is_connected is False


def test_is_connected_true_when_both_set():
    c = _make_client()
    c._connected = True
    c._ws = MagicMock()
    assert c.is_connected is True


# ---------------------------------------------------------------------------
# stop() — task cancellation
# ---------------------------------------------------------------------------


def test_stop_sets_running_false():
    c = _make_client()
    c._running = True
    c.stop()
    assert c._running is False


def test_stop_cancels_active_task():
    """Active task → cancelled."""
    c = _make_client()
    task = MagicMock()
    task.done.return_value = False
    c._task = task
    c.stop()
    task.cancel.assert_called_once()


def test_stop_does_not_cancel_done_task():
    """Already-done task → NOT re-cancelled."""
    c = _make_client()
    task = MagicMock()
    task.done.return_value = True
    c._task = task
    c.stop()
    task.cancel.assert_not_called()


def test_stop_handles_no_task():
    """No task → no crash."""
    c = _make_client()
    c._task = None
    c.stop()  # no exception


# ---------------------------------------------------------------------------
# get_status — admin command snapshot
# ---------------------------------------------------------------------------


def test_status_includes_all_required_fields():
    """Schema invariant — pin keys so admin embed template doesn't break."""
    c = _make_client()
    out = c.get_status()
    assert set(out.keys()) == {
        "enabled", "connected", "uri", "files_received",
        "last_notification", "reconnect_count", "running",
    }


def test_status_reports_disconnected_initially():
    c = _make_client()
    out = c.get_status()
    assert out["connected"] is False
    assert out["files_received"] == 0
    assert out["last_notification"] is None
    assert out["reconnect_count"] == 0
    assert out["running"] is False


def test_status_includes_uri():
    c = _make_client(ws_scheme="wss", ws_host="vps.io", ws_port=9999)
    out = c.get_status()
    assert out["uri"] == "wss://vps.io:9999"


def test_status_last_notification_is_iso_when_set():
    """When set, last_notification is rendered as ISO string."""
    from datetime import datetime
    c = _make_client()
    c.last_notification = datetime(2026, 4, 21, 12, 0, 0)
    out = c.get_status()
    assert out["last_notification"] == "2026-04-21T12:00:00"


def test_status_pulls_enabled_flag_from_config():
    c = _make_client(ws_enabled=False)
    out = c.get_status()
    assert out["enabled"] is False
