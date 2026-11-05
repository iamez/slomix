"""Timing-debug must not borrow neighbours or lose edits during delivery."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.services.timing_debug_service import TimingDebugService

LUA_ROW = (2849, '2026-11-03-225138', 1, 'et_brewdog', 1793742516,
           1793742698, 182, 0, 0, 'NORMAL', 2, 1, 10, 0, None, None,
           0, None, 0, 1, None)
ROUND = (11957, '2026-11-03-225141', 1, 'et_brewdog', '2026-11-03',
         '225141', '10:00', '3:02')


def fixture():
    state = SimpleNamespace(lua=None)
    async def fetch_one(query, params):
        return state.lua if 'FROM lua_round_teams' in query else ROUND
    db = SimpleNamespace(fetch_one=AsyncMock(side_effect=fetch_one),
                         fetch_all=AsyncMock(return_value=[LUA_ROW]))
    message = SimpleNamespace(edit=AsyncMock())
    channel = SimpleNamespace(send=AsyncMock(return_value=message))
    bot = SimpleNamespace(get_channel=lambda _: channel)
    config = SimpleNamespace(timing_debug_enabled=True, timing_debug_channel_id=7)
    return TimingDebugService(bot, db, config), state, channel, message


async def test_debug_known_round_requires_direct_link():
    current, _, _, _ = fixture()
    assert await current.fetch_lua_data(11957, 'et_brewdog', 1, '2026-11-03', '225141') is None
    current.db_adapter.fetch_all.assert_not_awaited()


async def test_debug_arrival_during_send_refreshes_same_message():
    current, state, channel, message = fixture()
    # No candidate capture exists until send yields.
    current.db_adapter.fetch_all.return_value = []
    async def send(**kwargs):
        state.lua = LUA_ROW
        await current.on_lua_data_stored(ROUND[1], 1)
        return message
    channel.send.side_effect = send
    await current.post_round_timing_comparison(11957, _attempt=1)
    assert message.edit.await_count == 1
    assert channel.send.await_count == 1
    assert any('182 sec' in field.value for field in message.edit.call_args.kwargs['embed'].fields)


async def test_debug_failed_edit_remains_retryable_and_needs_linked_data():
    current, state, channel, message = fixture()
    current.db_adapter.fetch_all.return_value = []
    await current.post_round_timing_comparison(11957, _attempt=1)
    await current.on_lua_data_stored(ROUND[1], 1)
    message.edit.assert_not_awaited()
    state.lua = LUA_ROW
    message.edit.side_effect = RuntimeError('fixture edit unavailable')
    await current.on_lua_data_stored(ROUND[1], 1)
    message.edit.side_effect = None
    await current.on_lua_data_stored(ROUND[1], 1)
    assert message.edit.await_count == 2
    await current.on_lua_data_stored(ROUND[1], 1)
    assert message.edit.await_count == 2
    assert channel.send.await_count == 1
