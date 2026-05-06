"""Tests for _AdminAlertMixin — admin alerts + consecutive error tracking.

This mixin is the operator's alarm system. A regression silently:

- Drops admin notifications → 24/7 outages go unnoticed.
- Loses error counts → alerts spam every cycle (false positive)
  OR never fire (false negative).
- Resets counters at the wrong moment → flapping services don't
  trigger the threshold alert.

Pin the contract for `alert_admins`, `track_error`, and
`reset_error_tracking`.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from bot.services.admin_alert_mixin import _AdminAlertMixin


class _StubBot(_AdminAlertMixin):
    """Minimal harness — set the attributes the mixin reads."""
    def __init__(self, admin_channel_id=None, channel=None):
        self.admin_channel_id = admin_channel_id
        self._channel = channel
        self._consecutive_errors: dict[str, int] = {}

    def get_channel(self, channel_id):
        return self._channel


def _channel_with_send():
    """Build a discord.TextChannel-like mock with an awaitable send()."""
    ch = MagicMock()
    ch.send = AsyncMock()
    return ch


# ---------------------------------------------------------------------------
# alert_admins — main alert path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alert_admins_returns_false_when_no_channel_configured():
    """No admin_channel_id → returns False, never tries to send.
    Pin so a misconfigured deploy doesn't crash on every error."""
    bot = _StubBot(admin_channel_id=None)
    out = await bot.alert_admins("title", "desc")
    assert out is False


@pytest.mark.asyncio
async def test_alert_admins_returns_false_when_channel_not_found():
    """admin_channel_id set but get_channel returns None (channel deleted
    or bot not in guild yet) → False, no crash."""
    bot = _StubBot(admin_channel_id=123, channel=None)
    out = await bot.alert_admins("title", "desc")
    assert out is False


@pytest.mark.asyncio
async def test_alert_admins_sends_embed_on_happy_path():
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    out = await bot.alert_admins("Test Alert", "Something happened")
    assert out is True
    ch.send.assert_awaited_once()
    # Inspect the embed argument
    args, kwargs = ch.send.call_args
    embed = kwargs.get("embed") or args[0]
    assert isinstance(embed, discord.Embed)


@pytest.mark.asyncio
async def test_alert_admins_uses_severity_emoji_in_title():
    """The severity → emoji mapping is part of the alert UX. Pin so a
    future cleanup doesn't accidentally drop the prefix."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    await bot.alert_admins("Boom", "x", severity="critical")
    embed = ch.send.call_args.kwargs["embed"]
    assert "🚨" in embed.title
    assert "Boom" in embed.title


@pytest.mark.asyncio
async def test_alert_admins_unknown_severity_falls_back_to_warning():
    """Unknown severity → orange + ⚠️ (warning palette). Pin fail-safe."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    await bot.alert_admins("title", "x", severity="bogus")
    embed = ch.send.call_args.kwargs["embed"]
    assert embed.color.value == 0xF39C12  # warning orange
    assert "⚠️" in embed.title


@pytest.mark.asyncio
async def test_alert_admins_severity_color_table():
    """Pin every severity → color mapping. A regression here would
    silently flip alert urgency in the admin embed."""
    expected = {
        "info":     0x3498DB,
        "warning":  0xF39C12,
        "error":    0xE74C3C,
        "critical": 0x8B0000,
    }
    for severity, color in expected.items():
        ch = _channel_with_send()
        bot = _StubBot(admin_channel_id=42, channel=ch)
        await bot.alert_admins("t", "d", severity=severity)
        embed = ch.send.call_args.kwargs["embed"]
        assert embed.color.value == color, f"{severity} should be {color:#x}"


@pytest.mark.asyncio
async def test_alert_admins_truncates_description_to_4000_chars():
    """Discord embed limit is 4096; we cap to 4000 to leave headroom.
    A regression that lets the full string through would 400-error
    the entire send call."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    huge = "x" * 5000
    out = await bot.alert_admins("t", huge)
    assert out is True
    embed = ch.send.call_args.kwargs["embed"]
    assert len(embed.description) == 4000


@pytest.mark.asyncio
async def test_alert_admins_returns_false_on_forbidden():
    """403 Forbidden → False, no exception. Pin so a permission glitch
    doesn't bubble up and crash the calling task."""
    ch = _channel_with_send()
    ch.send = AsyncMock(
        side_effect=discord.Forbidden(MagicMock(status=403), "no perms"),
    )
    bot = _StubBot(admin_channel_id=42, channel=ch)
    out = await bot.alert_admins("t", "d")
    assert out is False


@pytest.mark.asyncio
async def test_alert_admins_returns_false_on_generic_exception():
    """Any other exception → False, swallowed. Last line of defence
    against the alert system itself crashing."""
    ch = _channel_with_send()
    ch.send = AsyncMock(side_effect=RuntimeError("network down"))
    bot = _StubBot(admin_channel_id=42, channel=ch)
    out = await bot.alert_admins("t", "d")
    assert out is False


@pytest.mark.asyncio
async def test_alert_admins_footer_includes_uppercase_severity():
    """The footer carries severity in UPPERCASE — pin for consistency."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    await bot.alert_admins("t", "d", severity="error")
    embed = ch.send.call_args.kwargs["embed"]
    assert embed.footer.text == "Severity: ERROR"


# ---------------------------------------------------------------------------
# track_error — consecutive error counter + threshold alert
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_track_error_increments_counter_on_each_call():
    bot = _StubBot(admin_channel_id=None)  # no channel → no alert sent
    assert await bot.track_error("ssh_monitor", "boom") == 1
    assert await bot.track_error("ssh_monitor", "boom") == 2
    assert await bot.track_error("ssh_monitor", "boom") == 3


@pytest.mark.asyncio
async def test_track_error_counters_independent_per_key():
    """Different error keys keep separate counts — pin so a regression
    that shared counters would alert prematurely."""
    bot = _StubBot(admin_channel_id=None)
    await bot.track_error("ssh", "x")
    await bot.track_error("ssh", "x")
    assert await bot.track_error("api", "y") == 1
    assert bot._consecutive_errors == {"ssh": 2, "api": 1}


@pytest.mark.asyncio
async def test_track_error_fires_alert_at_threshold():
    """Default threshold = 3 — exactly 3 consecutive → alert."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    await bot.track_error("ssh_monitor", "first")
    await bot.track_error("ssh_monitor", "second")
    assert ch.send.await_count == 0
    # 3rd call → fires alert
    await bot.track_error("ssh_monitor", "third")
    assert ch.send.await_count == 1


@pytest.mark.asyncio
async def test_track_error_does_not_fire_above_threshold_unless_decade():
    """Counts 4-9 → NO alert. Count 10, 20, 30 → reminder alert.
    This dampening is critical: a constantly-failing service shouldn't
    spam the admin channel every cycle."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    for _ in range(3):
        await bot.track_error("svc", "x")  # 1, 2, 3 → fires once at 3
    assert ch.send.await_count == 1

    for _ in range(6):
        await bot.track_error("svc", "x")  # 4, 5, 6, 7, 8, 9 → no fires
    assert ch.send.await_count == 1

    await bot.track_error("svc", "x")  # 10 → reminder
    assert ch.send.await_count == 2


@pytest.mark.asyncio
async def test_track_error_reminder_uses_critical_severity():
    """Decade reminders elevate severity to 'critical' (dark red) since
    a service is in sustained failure. Pin the colour."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    # Get to count=10
    for _ in range(10):
        await bot.track_error("svc", "x")
    # Last call (count=10) should fire critical alert
    last_embed = ch.send.call_args.kwargs["embed"]
    assert last_embed.color.value == 0x8B0000
    assert "Still Failing" in last_embed.title


@pytest.mark.asyncio
async def test_track_error_threshold_alert_uses_error_severity():
    """First threshold alert is 'error' (red), not critical. Pin."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    for _ in range(3):
        await bot.track_error("svc", "x")
    embed = ch.send.call_args.kwargs["embed"]
    assert embed.color.value == 0xE74C3C
    assert "Failing" in embed.title


@pytest.mark.asyncio
async def test_track_error_humanises_key_in_title():
    """`ssh_monitor` → `Ssh Monitor` (replace _ with space + Title)."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    for _ in range(3):
        await bot.track_error("ssh_monitor", "x")
    embed = ch.send.call_args.kwargs["embed"]
    assert "Ssh Monitor" in embed.title


@pytest.mark.asyncio
async def test_track_error_custom_threshold():
    """max_consecutive=5 → alert on 5th, not 3rd."""
    ch = _channel_with_send()
    bot = _StubBot(admin_channel_id=42, channel=ch)
    for _ in range(4):
        await bot.track_error("svc", "x", max_consecutive=5)
    assert ch.send.await_count == 0
    await bot.track_error("svc", "x", max_consecutive=5)
    assert ch.send.await_count == 1


# ---------------------------------------------------------------------------
# reset_error_tracking
# ---------------------------------------------------------------------------


def test_reset_error_tracking_zeroes_existing_counter():
    bot = _StubBot()
    bot._consecutive_errors["svc"] = 7
    bot.reset_error_tracking("svc")
    assert bot._consecutive_errors["svc"] == 0


def test_reset_error_tracking_no_op_for_unknown_key():
    """Reset for a key that was never tracked → no-op (does NOT add a
    zero entry). Pin so a flood of resets for non-existent keys doesn't
    bloat the dict."""
    bot = _StubBot()
    bot._consecutive_errors["other"] = 5
    bot.reset_error_tracking("nonexistent")
    assert "nonexistent" not in bot._consecutive_errors
    assert bot._consecutive_errors == {"other": 5}


@pytest.mark.asyncio
async def test_reset_then_track_starts_count_from_one():
    """After reset_error_tracking, the next track_error returns 1
    (counter genuinely cleared, not just hidden)."""
    bot = _StubBot()
    for _ in range(5):
        await bot.track_error("svc", "x")
    bot.reset_error_tracking("svc")
    assert await bot.track_error("svc", "x") == 1
