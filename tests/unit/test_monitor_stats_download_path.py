"""Polling must write into configured durable storage, not the release cwd."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.services import monitor_tasks_mixin as monitor


@pytest.mark.asyncio
@pytest.mark.parametrize('endstats', [False, True])
async def test_poll_downloads_to_configured_storage_from_readonly_release(tmp_path, monkeypatch, endstats):
    release = tmp_path / 'release'
    release.mkdir()
    release.chmod(0o500)
    destination = tmp_path / 'shared' / 'stats'
    filename = '2026-10-15-180000-supply-round-1' + ('-endstats.txt' if endstats else '.txt')
    monkeypatch.chdir(release)
    monkeypatch.setattr(monitor, 'is_dead_hour', lambda hour: False)
    monkeypatch.setattr(monitor.asyncio, 'sleep', AsyncMock())
    monkeypatch.setattr(monitor.SSHHandler, 'list_remote_files', AsyncMock(return_value=[filename]))

    # Keep the actual async downloader and its mkdir/executor path. Replace
    # only the transport, so no SSH, database or external message is possible.
    def transfer(config, name, local_dir):
        path = Path(local_dir) / name
        path.write_text('isolated transport fixture\n')
        return str(path)

    monkeypatch.setattr(monitor.SSHHandler, '_download_file_sync', transfer)
    bot = SimpleNamespace(
        monitoring=True, ssh_enabled=True, gaming_voice_channels=[], ssh_check_counter=9,
        config=SimpleNamespace(monitoring_grace_period_minutes=30, ssh_host='fixture',
                               ssh_port=22, ssh_user='fixture', ssh_key_path='fixture',
                               ssh_remote_path='/fixture', stats_directory=str(destination)),
        file_tracker=SimpleNamespace(should_process_file=AsyncMock(return_value=True)),
        _should_process_endstats_file=AsyncMock(return_value=True),
        _process_endstats_file=AsyncMock(), _pop_pending_metadata=AsyncMock(return_value=None),
        process_gamestats_file=AsyncMock(return_value={'success': False, 'error': 'fixture no import'}),
        _process_remote_gametimes_files=AsyncMock(), _reconcile_missing_round_timing=AsyncMock(),
        reset_error_tracking=AsyncMock(), track_error=AsyncMock(),
    )
    try:
        await monitor._MonitorTasksMixin.endstats_monitor.coro(bot)  # noqa: SLF001 - actual mixin entrypoint
        expected = destination / filename
        assert expected.read_text() == 'isolated transport fixture\n'
        assert not (release / 'local_stats').exists()
        if endstats:
            bot._process_endstats_file.assert_awaited_once_with(str(expected), filename)  # noqa: SLF001 - processor boundary
        else:
            bot.process_gamestats_file.assert_awaited_once_with(str(expected), filename, override_metadata=None)
        bot.track_error.assert_not_awaited()
    finally:
        release.chmod(0o700)
