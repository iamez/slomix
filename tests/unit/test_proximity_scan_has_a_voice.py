# ruff: noqa: SLF001 — the two helpers under test are deliberately private:
# they are wiring inside the mixin, not part of any cog's public surface, and
# testing them through the 200-line scan loop would test the loop instead.
"""The proximity engagement scan can reach an admin.

⛔⛔ WHY THIS FILE EXISTS. On 2026-09-06 the SSH banner failed 22 times in a
half hour. **Nineteen of those came from this scan** and not one could reach
anybody: the handler incremented `self.error_count`, which is visible only
inside the `!proximity` admin embed, if somebody thinks to open it. The three
failures from the endstats loop went through `track_error` and paged the
owner — so the alert described the smaller half of the outage, and the larger
half was silent by construction.

The scan also runs every 2 minutes with no voice or dead-hours gating, unlike
the endstats loop, which is why it gets its own key rather than sharing one.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.cogs.proximity_mixins.ingestion_mixin import _ProximityIngestionMixin


class _Scan(_ProximityIngestionMixin):
    def __init__(self, bot):
        self.bot = bot


class _BotWithAlerts:
    def __init__(self):
        self.track_error = AsyncMock()
        self.reset_error_tracking = AsyncMock()


class _BotWithout:
    """A bot without the alert mixin — the standalone importer and the test
    harnesses look like this."""


@pytest.mark.asyncio
async def test_a_scan_failure_reaches_the_admin_alerting():
    bot = _BotWithAlerts()
    await _Scan(bot)._report_scan_error(RuntimeError("SSH list files failed: banner"))
    bot.track_error.assert_awaited_once()
    key, message = bot.track_error.await_args.args[0], bot.track_error.await_args.args[1]
    assert key == "proximity_ssh"
    assert "banner" in message


@pytest.mark.asyncio
async def test_it_has_its_own_key_not_the_endstats_one():
    """⛔ Sharing `ssh_monitor` would let a 2-minute unguarded loop drown out a
    60-second loop that skips dead hours — and would make the threshold mean
    two different things depending on which path incremented it."""
    bot = _BotWithAlerts()
    await _Scan(bot)._report_scan_error(RuntimeError("x"))
    assert bot.track_error.await_args.args[0] != "ssh_monitor"


@pytest.mark.asyncio
async def test_a_clean_scan_clears_the_streak():
    bot = _BotWithAlerts()
    await _Scan(bot)._report_scan_ok()
    bot.reset_error_tracking.assert_awaited_once_with("proximity_ssh")


@pytest.mark.asyncio
async def test_a_bot_without_alerting_is_not_a_crash():
    """⛔ THE CONTROL. This cog is loaded by bots that have no alert mixin. A
    missing alerting path must leave a logged error a logged error — turning
    it into an AttributeError would make the reporting change strictly worse
    than the silence it replaces."""
    scan = _Scan(_BotWithout())
    await scan._report_scan_error(RuntimeError("x"))   # must not raise
    await scan._report_scan_ok()                        # must not raise
