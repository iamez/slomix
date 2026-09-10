"""Failure streaks survive a restart — and stale ones do not.

⛔⛔ THE BUG THIS PINS. The streak counters lived only in RAM, so
`systemctl restart` set every one of them to zero. The owner hit this on
2026-09-06: after restarting the bot, the SSH alert counters were wiped. That
is not merely lost history. With the counter back at zero, a service that is
STILL failing must fail the full threshold again before anyone is paged — so
restarting a broken bot POSTPONES its next alert, which is the opposite of
what the person typing `systemctl restart` expects.

The other half is just as load-bearing: a bot that was down for a day must NOT
come back holding yesterday's streak, or its first healthy cycle would announce
a recovery from an outage that ended long ago. STREAK_WINDOW governs the file
exactly as it governs memory.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.admin_alert_mixin import STREAK_WINDOW, _AdminAlertMixin
from bot.services.error_streak_store import SCHEMA_VERSION, ErrorStreakStore

NOW = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)


class _StubBot(_AdminAlertMixin):
    """A bot with a real store, so a 'restart' is just a second instance."""

    def __init__(self, path, channel=None, boot_time=NOW):
        self.admin_channels = [123]
        self._channel = channel if channel is not None else _channel_with_send()
        self._consecutive_errors: dict[str, int] = {}
        self._alerted_keys: set[str] = set()
        self._error_streak_started: dict[str, datetime] = {}
        self._error_last_seen: dict[str, datetime] = {}
        self._boot_time = boot_time
        self._streak_store = ErrorStreakStore(path)
        self.load_error_streaks()

    def get_channel(self, channel_id):
        return self._channel


def _channel_with_send():
    ch = MagicMock()
    ch.send = AsyncMock()
    return ch


def _titles(channel):
    return [c.kwargs["embed"].title for c in channel.send.call_args_list]


# ---------------------------------------------------------------------------
# The owner's scenario: a restart must not reset the clock on an outage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_restart_does_not_postpone_the_alert(tmp_path):
    """Two failures, restart, one more failure → the third one alerts.

    Before persistence the third failure was the FIRST of a new streak and the
    admins heard nothing until two more arrived.
    """
    state = tmp_path / "streaks.json"

    bot = _StubBot(state)
    await bot.track_error("ssh_monitor", "boom", max_consecutive=3)
    await bot.track_error("ssh_monitor", "boom", max_consecutive=3)
    assert _titles(bot._channel) == [], "two failures must not alert yet"

    restarted = _StubBot(state)
    assert restarted._consecutive_errors["ssh_monitor"] == 2

    count = await restarted.track_error("ssh_monitor", "boom", max_consecutive=3)

    assert count == 3
    assert _titles(restarted._channel) == ["❌ Ssh Monitor Failing"]


@pytest.mark.asyncio
async def test_a_reset_survives_the_restart_too(tmp_path):
    """A cleared counter must not come back from disk.

    Persisting only failures would be worse than persisting nothing: the next
    single failure after a recovery would read as the third one.
    """
    state = tmp_path / "streaks.json"

    bot = _StubBot(state)
    await bot.track_error("ssh_monitor", "boom", max_consecutive=3)
    await bot.track_error("ssh_monitor", "boom", max_consecutive=3)
    await bot.reset_error_tracking("ssh_monitor")

    restarted = _StubBot(state)
    assert restarted._consecutive_errors.get("ssh_monitor", 0) == 0

    await restarted.track_error("ssh_monitor", "boom", max_consecutive=3)
    assert _titles(restarted._channel) == [], "one failure must not alert"


@pytest.mark.asyncio
async def test_alerted_survives_so_recovery_is_still_announced(tmp_path):
    """The key alerted before the restart, so its recovery must be reported.

    Otherwise the admins are left with an ERROR in the channel and no closing
    line — from Discord alone the outage never ended.
    """
    state = tmp_path / "streaks.json"

    bot = _StubBot(state)
    for _ in range(3):
        await bot.track_error("ssh_monitor", "boom", max_consecutive=3)
    assert "ssh_monitor" in bot._alerted_keys

    restarted = _StubBot(state)
    assert "ssh_monitor" in restarted._alerted_keys

    await restarted.reset_error_tracking("ssh_monitor")
    assert _titles(restarted._channel) == ["ℹ️ Ssh Monitor Recovered"]


@pytest.mark.asyncio
async def test_recovery_says_the_streak_crossed_a_restart(tmp_path):
    """An admin reading a duration must not assume one process watched it all."""
    state = tmp_path / "streaks.json"

    bot = _StubBot(state, boot_time=NOW - timedelta(hours=2))
    for _ in range(3):
        await bot.track_error("ssh_monitor", "boom", max_consecutive=3)

    # The new process booted after the streak began.
    restarted = _StubBot(state, boot_time=datetime.now(timezone.utc))
    await restarted.reset_error_tracking("ssh_monitor")

    body = restarted._channel.send.call_args.kwargs["embed"].description
    assert "crossed a bot restart" in body


# ---------------------------------------------------------------------------
# The window governs the file, not just memory
# ---------------------------------------------------------------------------

def test_a_streak_older_than_the_window_is_dropped_on_load(tmp_path):
    """A bot down for a day must not wake up holding yesterday's outage."""
    state = tmp_path / "streaks.json"
    stale = NOW - STREAK_WINDOW - timedelta(minutes=1)
    state.write_text(json.dumps({
        "version": SCHEMA_VERSION,
        "written_at": stale.isoformat(),
        "boot_time": stale.isoformat(),
        "streaks": {
            "ssh_monitor": {
                "count": 7,
                "streak_started_at": stale.isoformat(),
                "last_seen_at": stale.isoformat(),
                "alerted": True,
            }
        },
    }))

    loaded = ErrorStreakStore(state).load(STREAK_WINDOW, now=NOW)

    assert loaded["consecutive"] == {}
    assert loaded["alerted"] == set()
    assert loaded["expired"] == 1


def test_a_streak_inside_the_window_is_kept(tmp_path):
    """The control for the test above: the same shape, one minute younger."""
    state = tmp_path / "streaks.json"
    fresh = NOW - STREAK_WINDOW + timedelta(minutes=1)
    state.write_text(json.dumps({
        "version": SCHEMA_VERSION,
        "written_at": fresh.isoformat(),
        "boot_time": fresh.isoformat(),
        "streaks": {
            "ssh_monitor": {
                "count": 7,
                "streak_started_at": fresh.isoformat(),
                "last_seen_at": fresh.isoformat(),
                "alerted": True,
            }
        },
    }))

    loaded = ErrorStreakStore(state).load(STREAK_WINDOW, now=NOW)

    assert loaded["consecutive"] == {"ssh_monitor": 7}
    assert loaded["alerted"] == {"ssh_monitor"}
    assert loaded["expired"] == 0


# ---------------------------------------------------------------------------
# The store must never raise into the alerting path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    "{not json at all",
    "[]",
    json.dumps({"version": 999, "streaks": {"k": {"count": 2}}}),
    json.dumps({"version": SCHEMA_VERSION, "streaks": "not a dict"}),
])
def test_an_unusable_file_starts_empty_instead_of_raising(tmp_path, body):
    state = tmp_path / "streaks.json"
    state.write_text(body)

    loaded = ErrorStreakStore(state).load(STREAK_WINDOW, now=NOW)

    assert loaded["consecutive"] == {}


def test_a_missing_file_starts_empty(tmp_path):
    loaded = ErrorStreakStore(tmp_path / "nope.json").load(STREAK_WINDOW, now=NOW)
    assert loaded["consecutive"] == {}


@pytest.mark.parametrize("entry", [
    {"count": 0, "last_seen_at": NOW.isoformat()},
    {"count": -1, "last_seen_at": NOW.isoformat()},
    {"count": "3", "last_seen_at": NOW.isoformat()},
    {"count": True, "last_seen_at": NOW.isoformat()},
    {"count": 3},                                     # no last_seen: unageable
    {"count": 3, "last_seen_at": "not a timestamp"},
])
def test_an_unusable_entry_is_skipped_not_fatal(tmp_path, entry):
    state = tmp_path / "streaks.json"
    state.write_text(json.dumps({
        "version": SCHEMA_VERSION, "boot_time": NOW.isoformat(),
        "streaks": {"good": {"count": 2, "last_seen_at": NOW.isoformat()}, "bad": entry},
    }))

    loaded = ErrorStreakStore(state).load(STREAK_WINDOW, now=NOW)

    assert "bad" not in loaded["consecutive"]
    assert loaded["consecutive"]["good"] == 2, "one bad entry must not lose the good ones"


def test_a_naive_timestamp_is_made_aware(tmp_path):
    """⛔ A naive datetime would raise TypeError inside track_error's window
    comparison — in the one method that must never raise."""
    state = tmp_path / "streaks.json"
    state.write_text(json.dumps({
        "version": SCHEMA_VERSION, "boot_time": NOW.isoformat(),
        "streaks": {"k": {"count": 2, "last_seen_at": "2026-09-06T12:00:00"}},
    }))

    loaded = ErrorStreakStore(state).load(STREAK_WINDOW, now=NOW)

    assert loaded["last_seen"]["k"].tzinfo is not None


def test_an_unwritable_path_returns_false_and_does_not_raise(tmp_path):
    """A full or read-only disk must cost persistence, never alerting."""
    store = ErrorStreakStore(tmp_path / "sub" / "streaks.json")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub").chmod(0o500)
    try:
        ok = store.save(
            boot_time=NOW, consecutive={"k": 2}, started={"k": NOW},
            last_seen={"k": NOW}, alerted=set(),
        )
    finally:
        (tmp_path / "sub").chmod(0o700)

    assert ok is False


@pytest.mark.asyncio
async def test_alerting_still_works_when_the_disk_refuses(tmp_path):
    """The whole point of swallowing write errors."""
    bot = _StubBot(tmp_path / "streaks.json")
    bot._streak_store.save = MagicMock(side_effect=OSError("disk full"))

    with pytest.raises(OSError):
        bot._streak_store.save()   # control: the mock really does raise

    bot._streak_store.save = MagicMock(return_value=False)
    for _ in range(3):
        await bot.track_error("ssh_monitor", "boom", max_consecutive=3)

    assert _titles(bot._channel) == ["❌ Ssh Monitor Failing"]


# ---------------------------------------------------------------------------
# Shape of the file — the external watchdog reads it
# ---------------------------------------------------------------------------

def test_the_written_document_carries_what_a_watchdog_needs(tmp_path):
    """`written_at` + `boot_time` separate "the bot is dead" from
    "the bot is alive and a streak is old"."""
    state = tmp_path / "streaks.json"
    store = ErrorStreakStore(state)

    store.save(
        boot_time=NOW, consecutive={"ssh_monitor": 4, "quiet": 0},
        started={"ssh_monitor": NOW}, last_seen={"ssh_monitor": NOW},
        alerted={"ssh_monitor"}, now=NOW,
    )

    doc = json.loads(state.read_text())
    assert doc["version"] == SCHEMA_VERSION
    assert doc["written_at"] == NOW.isoformat()
    assert doc["boot_time"] == NOW.isoformat()
    assert doc["streaks"]["ssh_monitor"]["alerted"] is True
    assert "quiet" not in doc["streaks"], "a zeroed counter carries no information"


def test_the_write_is_atomic_and_leaves_no_temp_file(tmp_path):
    state = tmp_path / "streaks.json"
    ErrorStreakStore(state).save(
        boot_time=NOW, consecutive={"k": 1}, started={"k": NOW},
        last_seen={"k": NOW}, alerted=set(), now=NOW,
    )

    assert state.exists()
    assert list(tmp_path.glob("*.tmp")) == []
