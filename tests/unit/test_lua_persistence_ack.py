"""Composed ingestion must acknowledge only a persisted Lua capture."""
# ruff: noqa: SLF001
import json
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from bot.services.stats_ready_mixin import _StatsReadyMixin
from bot.services.webhook_round_metadata_service import WebhookRoundMetadataService
from bot.ultimate_bot import UltimateETLegacyBot
from tests.unit.test_lua_round_teams_param_packing import _FakeBot, _sample_round_metadata


def bot_fixture(failed, linked):
    bot = _FakeBot(has_round_id=True, resolved_round_id=42 if linked else None)
    bot.db_adapter.execute = AsyncMock(side_effect=RuntimeError('injected database outage') if failed else None)
    bot._link_late_lua_row = AsyncMock(return_value=None)
    bot._store_lua_round_teams = MethodType(UltimateETLegacyBot._store_lua_round_teams, bot)
    bot._fetch_latest_stats_file = AsyncMock(return_value=True)
    bot.track_error = AsyncMock()
    return bot


@pytest.mark.parametrize('failed,linked', [(True, True), (False, True), (False, False)])
async def test_actual_store_controls_webhook_acknowledgement(failed, linked):
    bot = bot_fixture(failed, linked)
    metadata = _sample_round_metadata()
    metadata.pop('round_start_unix')
    message = SimpleNamespace(delete=AsyncMock())
    if failed:
        with pytest.raises(RuntimeError):
            await _StatsReadyMixin._process_stats_ready_round(bot, metadata, message)
        message.delete.assert_not_awaited()
        bot.track_error.assert_awaited_once()
    else:
        await _StatsReadyMixin._process_stats_ready_round(bot, metadata, message)
        message.delete.assert_awaited_once()
        bot.track_error.assert_not_awaited()
    assert bot.db_adapter.execute.await_count == 1


@pytest.mark.parametrize('failed', [True, False])
async def test_actual_store_controls_gametime_success(tmp_path, failed):
    bot = bot_fixture(failed, False)
    bot.ssh_enabled = False
    bot.webhook_round_metadata_service = WebhookRoundMetadataService()
    bot._queue_pending_metadata = lambda *args, **kwargs: None
    document = {'meta': {}, 'payload': {'embeds': [{'fields': [
        {'name': 'Map', 'value': 'supply'}, {'name': 'Round', 'value': '2'},
        {'name': 'Lua_RoundEnd', 'value': '1770843722'},
        {'name': 'Lua_Playtime', 'value': '579 sec'}]}]}}
    path = tmp_path / 'capture.json'
    path.write_text(json.dumps(document))
    with patch('bot.ultimate_bot.retain_lua_correction_if_enabled', new=AsyncMock()):
        assert await UltimateETLegacyBot._process_gametimes_file(bot, str(path), path.name) is (not failed)
    assert bot.db_adapter.execute.await_count == 1


async def test_webhook_can_retry_after_database_recovers():
    bot = bot_fixture(True, True)
    metadata = _sample_round_metadata()
    metadata.pop('round_start_unix')
    message = SimpleNamespace(delete=AsyncMock())
    with pytest.raises(RuntimeError):
        await _StatsReadyMixin._process_stats_ready_round(bot, metadata, message)
    bot.db_adapter.execute.side_effect = None
    await _StatsReadyMixin._process_stats_ready_round(bot, metadata, message)
    assert bot.db_adapter.execute.await_count == 2
    message.delete.assert_awaited_once()


async def test_poll_keeps_failed_file_and_processes_next_capture():
    bot = SimpleNamespace(
        config=SimpleNamespace(gametimes_enabled=True, ssh_host='fixture', ssh_port=22,
                               ssh_user='fixture', ssh_key_path='fixture-key',
                               gametimes_remote_path='/fixture', gametimes_local_path='/fixture',
                               gametimes_startup_lookback_hours=0),
        ssh_enabled=True, processed_gametimes_files=set(),
        _extract_gametime_timestamp=lambda _: None,
        _process_gametimes_file=AsyncMock(side_effect=[False, True]),
    )
    bot._mark_gametime_processed = bot.processed_gametimes_files.add
    first, second = 'gametime-supply-R1-1.json', 'gametime-supply-R2-2.json'
    with patch('bot.ultimate_bot.SSHHandler.list_remote_files', new=AsyncMock(return_value=[first, second])), \
         patch('bot.ultimate_bot.SSHHandler.download_file', new=AsyncMock(return_value='/fixture/capture.json')):
        await UltimateETLegacyBot._process_remote_gametimes_files(bot)
    assert bot.processed_gametimes_files == {second}
    assert bot._process_gametimes_file.await_count == 2
