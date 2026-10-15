"""Pending binding must not turn old endstats into perpetual new activity."""
# ruff: noqa: SLF001 -- actual mixin boundaries and process-local state
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services import monitor_tasks_mixin as monitor
from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin
from bot.services.webhook_handler_mixin import _WebhookHandlerMixin
from shared import endstats_retry as retry


class Bot(_EndstatsPipelineMixin, _WebhookHandlerMixin, monitor._MonitorTasksMixin):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('early', [False, True])
async def test_actual_monitor_cooldown_grace_and_late_binding(monkeypatch, enabled, early):
    monkeypatch.setenv('ENDSTATS_RETRY_ENABLED', str(enabled).lower())
    clock = [0.0]
    start = datetime(2026, 10, 15, 12)  # noqa: DTZ001 - production local-naive clock contract
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (start + timedelta(seconds=clock[0])).replace(tzinfo=tz)
    monkeypatch.setattr(monitor, 'datetime', Clock)
    monkeypatch.setattr(monitor, 'is_dead_hour', lambda hour: False)
    monkeypatch.setattr(retry.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(monitor.asyncio, 'sleep', AsyncMock())
    filename = '2026-10-15-120000-supply-round-1-endstats.txt'
    listing = AsyncMock(return_value=[filename])
    download = AsyncMock(return_value='/fixture/endstats')
    monkeypatch.setattr(monitor.SSHHandler, 'list_remote_files', listing)
    monkeypatch.setattr(monitor.SSHHandler, 'download_file', download)
    data = {'metadata': {'date': '2026-10-15', 'time': '120000', 'map_name': 'supply', 'round_number': 1},
            'awards': [], 'vs_stats': []}
    monkeypatch.setattr('bot.endstats_parser.parse_endstats_file', lambda path: data)
    bot = Bot()
    bot.monitoring = bot.ssh_enabled = True
    bot.gaming_voice_channels = []
    bot.ssh_check_counter = 9
    bot.bot_startup_time = start
    bot.config = SimpleNamespace(monitoring_grace_period_minutes=30, ssh_host='fixture',
        ssh_port=22, ssh_user='fixture', ssh_key_path='fixture', ssh_remote_path='/fixture',
        stats_directory='/durable', STARTUP_LOOKBACK_HOURS=168)
    bot.processed_endstats_files = set()
    bot.endstats_retry_counts = {}
    bot.endstats_retry_max_attempts = 2
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=None),
        fetch_all=AsyncMock(return_value=[]), execute=AsyncMock())
    bot._select_richest_endstats = lambda d, p, f, *args: (d, p, f)
    bot._is_endstats_round_already_processed = AsyncMock(return_value=False)
    bot._is_endstats_round_ready = AsyncMock(return_value=True)
    bot._store_endstats_and_publish = AsyncMock(return_value=True)
    bot._process_remote_gametimes_files = AsyncMock()
    bot._reconcile_missing_round_timing = AsyncMock()
    bot.reset_error_tracking = AsyncMock()
    bot.track_error = AsyncMock()
    await bot.endstats_monitor.coro(bot)
    assert download.await_count == 1
    assert bot.last_file_download_time == start
    assert bot._endstats_poll_backoff[filename] == (1, 0)
    if early:
        bot.db_adapter.fetch_all.return_value = [(42, '2026-10-15', '120000')]
        clock[0] = 60
        await bot.endstats_monitor.coro(bot)
        assert download.await_count == 2
        assert bot._store_endstats_and_publish.await_args.args[2] == 42
        assert bot.last_file_download_time == start
        assert not retry.endstats_poll_pending(bot, filename)
        return
    for tick in (60, 120):
        clock[0] = tick
        await bot.endstats_monitor.coro(bot)
    assert download.await_count == 3
    assert bot._endstats_poll_backoff[filename] == (3, 720)
    for tick in (180, 719):
        clock[0] = tick
        await bot.endstats_monitor.coro(bot)
    assert download.await_count == 3
    clock[0] = 720
    await bot.endstats_monitor.coro(bot)
    assert download.await_count == 4
    assert bot.last_file_download_time == start
    assert bot._endstats_poll_backoff[filename] == (4, 1920)
    clock[0] = 1800
    before = listing.await_count
    for _ in range(9):
        await bot.endstats_monitor.coro(bot)
    assert listing.await_count == before
    await bot.endstats_monitor.coro(bot)
    assert download.await_count == 4
    clock[0] = 1920
    bot.ssh_check_counter = 9
    await bot.endstats_monitor.coro(bot)
    assert download.await_count == 5
    assert bot.last_file_download_time == start
    assert bot._endstats_poll_backoff[filename] == (5, 4320)
    bot.db_adapter.fetch_all.return_value = [(42, '2026-10-15', '120000')]
    clock[0] = 4320
    bot.ssh_check_counter = 9
    await bot.endstats_monitor.coro(bot)
    assert download.await_count == 6
    assert bot._store_endstats_and_publish.await_args.args[2] == 42
    assert not retry.endstats_poll_pending(bot, filename)
    bot.db_adapter.execute.assert_not_awaited()
    bot.track_error.assert_not_awaited()
    listing.return_value = ['2026-10-15-131100-supply-round-2.txt']
    bot.file_tracker = SimpleNamespace(should_process_file=AsyncMock(return_value=True))
    bot._pop_pending_metadata = AsyncMock(return_value=None)
    bot.process_gamestats_file = AsyncMock(return_value={'success': False})
    clock[0] = 4380
    bot.ssh_check_counter = 9
    await bot.endstats_monitor.coro(bot)
    assert bot.last_file_download_time == start + timedelta(seconds=4380)
    # The pre-existing startup lookback still rejects an old remote file.
    old = '2026-10-01-120000-supply-round-1-endstats.txt'
    retry.defer_endstats_poll(bot, old)
    assert not await bot._should_process_endstats_file(old)
    assert not retry.endstats_poll_pending(bot, old)



def test_backoff_cap_alias_cleanup_stale_and_restart(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(retry.time, 'monotonic', lambda: clock[0])
    bot = SimpleNamespace(endstats_retry_max_attempts=0)
    for expected in (600, 1200, 2400, 3600, 3600):
        retry.defer_endstats_poll(bot, 'original', 'selected')
        assert bot._endstats_poll_backoff['original'][1] == clock[0] + expected
        assert not retry.endstats_poll_due(bot, 'original')
        clock[0] += expected
        assert retry.endstats_poll_due(bot, 'original')
    retry.clear_endstats_poll(bot, 'original', 'selected')
    assert not bot._endstats_poll_backoff
    retry.defer_endstats_poll(bot, 'gone')
    clock[0] += 600 + 7 * 86400 + 1
    assert retry.endstats_poll_due(bot, 'other')
    assert not bot._endstats_poll_backoff
    assert retry.endstats_poll_due(SimpleNamespace(), 'gone')
