"""Arrival ordering and existing-message refresh; no Discord transport or DB."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.services.timing_comparison_service import TimingComparisonService


def service():
    message = SimpleNamespace(edit=AsyncMock())
    channel = SimpleNamespace(send=AsyncMock(return_value=message))
    bot = SimpleNamespace(get_channel=lambda _: channel)
    result = TimingComparisonService(SimpleNamespace(fetch_one=AsyncMock(return_value=None),
                                                     fetch_all=AsyncMock()), bot)
    result.fetch_stats_file_data = AsyncMock(return_value={
        'round_id': 11957, 'map_name': 'et_brewdog', 'round_number': 1,
        'round_date': '2026-11-03', 'round_time': '225141', 'actual_time': '3:02',
        'stats_duration_seconds': 182, 'time_limit': '12:00', 'players': []})
    return result, channel, message


LUA = {'lua_duration_seconds': 182, 'round_number': 1, 'round_start_unix': 1793742516,
       'round_end_unix': 1793742698, 'total_pause_seconds': 0, 'pause_count': 0,
       'winner_team': 2, 'end_reason': 'NORMAL', 'match_confidence': 'direct'}


async def test_later_store_refreshes_original_diagnostic_without_second_send():
    current, channel, message = service()
    current.fetch_lua_data = AsyncMock(return_value=None)
    assert await current.post_timing_comparison(11957, 7)
    pending = channel.send.call_args.kwargs['embed']
    assert 'PENDING' in pending.description and 'NO LUA DATA' not in pending.description
    assert not any('may not have fired' in field.value for field in pending.fields)
    current.fetch_lua_data.return_value = LUA
    assert await current.on_lua_data_stored(11957)
    assert 'ALIGNED' in message.edit.call_args.kwargs['embed'].description
    current.fetch_lua_data.assert_awaited_with(11957, 'et_brewdog', 1, '2026-11-03', '225141', linked_only=True)
    assert channel.send.await_count == message.edit.await_count == 1
    assert not await current.on_lua_data_stored(11957)


async def test_store_during_send_is_not_lost():
    current, channel, message = service()
    current.fetch_lua_data = AsyncMock(return_value=None)

    async def send(**kwargs):
        current.fetch_lua_data.return_value = LUA
        assert not await current.on_lua_data_stored(11957)
        return message

    channel.send.side_effect = send
    assert await current.post_timing_comparison(11957, 7)
    assert message.edit.await_count == 1
    assert not await current.on_lua_data_stored(11957)


async def test_unlinked_refresh_never_guesses_another_round():
    current, _, _ = service()
    assert await current.fetch_lua_data(11957, 'et_brewdog', 1, '2026-11-03', '225141', linked_only=True) is None
    current.db_adapter.fetch_all.assert_not_awaited()


async def test_failed_edit_keeps_retry_state_and_unrelated_round_cannot_edit():
    current, channel, message = service()
    current.fetch_lua_data = AsyncMock(return_value=None)
    await current.post_timing_comparison(11957, 7)
    current.fetch_lua_data.return_value = LUA
    message.edit.side_effect = RuntimeError('fixture edit unavailable')
    assert not await current.on_lua_data_stored(11957)
    assert not await current.on_lua_data_stored(11958)
    message.edit.side_effect = None
    assert await current.on_lua_data_stored(11957)
    assert channel.send.await_count == 1


async def test_duplicate_publication_during_send_does_not_leave_stale_copy():
    current, channel, message = service()
    current.fetch_lua_data = AsyncMock(return_value=None)
    entered, release = asyncio.Event(), asyncio.Event()

    async def send(**kwargs):
        entered.set()
        await release.wait()
        return message

    channel.send.side_effect = send
    first = asyncio.create_task(current.post_timing_comparison(11957, 7))
    await entered.wait()
    assert not await current.post_timing_comparison(11957, 7)
    release.set()
    assert await first
    assert channel.send.await_count == 1
    current.fetch_lua_data.return_value = LUA
    assert await current.on_lua_data_stored(11957)
    assert await current.post_timing_comparison(11957, 7)
    assert channel.send.await_count == 2


async def test_pending_edit_capacity_is_bounded():
    current, _, _ = service()
    current.fetch_lua_data = AsyncMock(return_value=None)
    for round_id in range(65):
        await current.post_timing_comparison(round_id, 7)
    current.fetch_lua_data.return_value = LUA
    assert not await current.on_lua_data_stored(0)
    assert sum([await current.on_lua_data_stored(round_id) for round_id in range(1, 65)]) == 64
