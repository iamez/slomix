from __future__ import annotations

import pytest

from bot.services.timing_debug_service import TimingDebugService


class _FakeChannel:
    def __init__(self):
        self.sent_embeds = []

    async def send(self, *, embed):
        self.sent_embeds.append(embed)


class _FakeBot:
    def __init__(self, channel):
        self._channel = channel

    def get_channel(self, _channel_id):
        return self._channel


class _FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.last_query = None
        self.last_params = None

    async def fetch_all(self, query, params):
        self.last_query = query
        self.last_params = params
        return self.rows


class _Cfg:
    timing_debug_enabled = True
    timing_debug_channel_id = 123


@pytest.mark.asyncio
async def test_post_session_timing_comparison_joins_lua_by_round_id():
    # Row shape:
    # round_id, match_id, round_num, map_name, time_limit, actual_time,
    # lua_duration, lua_pauses, lua_end_reason, surrender_team, surrender_caller_name
    rows = [
        (9818, "2026-02-11-215052", 1, "supply", "12:00", "9:22", 563, 0, "objective", 0, ""),
        (9819, "2026-02-11-220205", 2, "supply", "12:00", "9:39", None, None, None, None, None),
    ]

    channel = _FakeChannel()
    service = TimingDebugService(_FakeBot(channel), _FakeDB(rows), _Cfg())

    await service.post_session_timing_comparison([9818, 9819])

    assert service.db_adapter.last_query is not None
    assert "lrt.round_id = r.id" in service.db_adapter.last_query
    assert "r.match_id = l.match_id" not in service.db_adapter.last_query
    assert service.db_adapter.last_params == (9818, 9819)

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    summary = embed.fields[1].value
    assert "Rounds with Lua data" in summary
    assert "1/2" in summary
    assert "Missing Lua data" in summary
