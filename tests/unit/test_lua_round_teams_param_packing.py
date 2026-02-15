import re

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _FakeDB:
    def __init__(self):
        self.calls = []

    async def execute(self, query, params):
        self.calls.append((query, params))


class _FakeBot:
    def __init__(self, has_round_id: bool, resolved_round_id):
        self.db_adapter = _FakeDB()
        self._has_round_id = has_round_id
        self._resolved_round_id = resolved_round_id

    async def _resolve_round_id_for_metadata(self, _unused, _round_metadata):
        return self._resolved_round_id

    async def _has_lua_round_teams_round_id(self):
        return self._has_round_id


def _sample_round_metadata():
    return {
        "round_end_unix": 1770843722,
        "round_start_unix": 1770843050,
        "map_name": "supply",
        "round_number": 2,
        "actual_duration_seconds": 579,
        "total_pause_seconds": 12,
        "pause_count": 1,
        "end_reason": "timelimit",
        "winner_team": "allies",
        "defender_team": "axis",
        "time_limit_minutes": 12,
        "lua_warmup_seconds": 5,
        "lua_warmup_start_unix": 1770843045,
        "lua_pause_events": [{"start": 1770843200, "end": 1770843212}],
        "surrender_team": 0,
        "surrender_caller_guid": "",
        "surrender_caller_name": "",
        "axis_score": 0,
        "allies_score": 1,
        "axis_players": [{"guid": "A1", "name": "AxisOne"}],
        "allies_players": [{"guid": "B1", "name": "AlliesOne"}],
        "lua_version": "1.6.0",
    }


def _assert_query_placeholders_align(query: str, param_count: int):
    placeholders = [int(n) for n in re.findall(r"\$(\d+)", query)]
    assert placeholders
    assert max(placeholders) == param_count
    assert set(placeholders) >= set(range(1, param_count + 1))


@pytest.mark.asyncio
async def test_store_lua_round_teams_param_count_with_round_id_column():
    fake_bot = _FakeBot(has_round_id=True, resolved_round_id=9825)
    metadata = _sample_round_metadata()

    await UltimateETLegacyBot._store_lua_round_teams(fake_bot, metadata)

    assert len(fake_bot.db_adapter.calls) == 1
    query, params = fake_bot.db_adapter.calls[0]
    assert len(params) == 24
    assert params[2] == 9825
    assert "round_id" in query
    _assert_query_placeholders_align(query, 24)


@pytest.mark.asyncio
async def test_store_lua_round_teams_param_count_without_round_id_column():
    fake_bot = _FakeBot(has_round_id=False, resolved_round_id=None)
    metadata = _sample_round_metadata()

    await UltimateETLegacyBot._store_lua_round_teams(fake_bot, metadata)

    assert len(fake_bot.db_adapter.calls) == 1
    query, params = fake_bot.db_adapter.calls[0]
    assert len(params) == 23
    assert "round_id" not in query
    _assert_query_placeholders_align(query, 23)

