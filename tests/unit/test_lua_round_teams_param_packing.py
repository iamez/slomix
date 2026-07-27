"""
Test that _store_lua_round_teams produces the correct number of SQL parameters
for both with-round_id and without-round_id code paths.
"""
# ruff: noqa: SLF001

import re
from contextlib import asynccontextmanager

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _FakeDB:
    def __init__(self, *, team_exists=False, team_round_id=None):
        self.calls = []
        self.batch_calls = []
        self.team_exists = team_exists
        self.team_round_id = team_round_id

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def execute(self, query, params=None):
        self.calls.append((query, params))

    async def executemany(self, query, params):
        self.batch_calls.append((query, params))

    async def fetch_one(self, query, params=None):
        if "SELECT round_id FROM lua_round_teams" in query and self.team_exists:
            return (self.team_round_id,)
        return None


class _FakeBot:
    def __init__(
        self,
        has_round_id: bool,
        resolved_round_id,
        *,
        team_exists=False,
        team_round_id=None,
    ):
        self.db_adapter = _FakeDB(
            team_exists=team_exists,
            team_round_id=team_round_id,
        )
        self._has_round_id = has_round_id
        self._resolved_round_id = resolved_round_id
        # correlation_service is checked via hasattr
        self.correlation_service = None

    async def _resolve_lua_round_id_for_metadata(self, _round_metadata):
        return self._resolved_round_id

    async def _has_lua_round_teams_round_id(self):
        return self._has_round_id

    async def _has_lua_spawn_stats_table(self):
        return True

    async def _reconcile_lua_exact_source(self, **kwargs):
        return await UltimateETLegacyBot._reconcile_lua_exact_source(self, **kwargs)

    async def _resolve_lua_spawn_team_identity(self, **kwargs):
        return await UltimateETLegacyBot._resolve_lua_spawn_team_identity(
            self,
            **kwargs,
        )

    async def _resolve_round_correlation_context(self, round_id, fallback_match_id, fallback_map_name, fallback_round_number):
        return fallback_match_id, fallback_map_name, fallback_round_number


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

    query, params = next(
        (query, params)
        for query, params in fake_bot.db_adapter.calls
        if "INSERT INTO lua_round_teams" in query
    )
    assert len(params) == 24
    assert params[2] is None  # exact links are assigned only after locked proof
    assert "round_id" in query
    assert "WHEN EXCLUDED.round_start_unix > 0" in query
    _assert_query_placeholders_align(query, 24)
    assert any(
        "LOCK TABLE lua_round_teams" in query
        for query, _params in fake_bot.db_adapter.calls
    )
    reconcile_query = next(
        query
        for query, _params in fake_bot.db_adapter.calls
        if "WITH source_state AS" in query
    )
    assert "source_state.source_count = 1" in reconcile_query
    assert "target_state.target_count = 1" in reconcile_query


@pytest.mark.asyncio
async def test_store_lua_round_teams_param_count_without_round_id_column():
    fake_bot = _FakeBot(has_round_id=False, resolved_round_id=None)
    metadata = _sample_round_metadata()

    await UltimateETLegacyBot._store_lua_round_teams(fake_bot, metadata)

    query, params = next(
        (query, params)
        for query, params in fake_bot.db_adapter.calls
        if "INSERT INTO lua_round_teams" in query
    )
    assert len(params) == 23
    assert "round_id" not in query
    _assert_query_placeholders_align(query, 23)


@pytest.mark.asyncio
async def test_store_lua_spawn_stats_clears_stale_link_for_exact_start():
    fake_bot = _FakeBot(
        has_round_id=True,
        resolved_round_id=None,
        team_exists=True,
        team_round_id=None,
    )

    await UltimateETLegacyBot._store_lua_spawn_stats(
        fake_bot,
        _sample_round_metadata(),
        [{"guid": "A1", "name": "AxisOne", "spawns": 2, "deaths": 1}],
    )

    assert len(fake_bot.db_adapter.batch_calls) == 1
    query, params = fake_bot.db_adapter.batch_calls[0]
    assert "WHEN $13 THEN EXCLUDED.round_id" in query
    assert "COALESCE(EXCLUDED.round_id, lua_spawn_stats.round_id)" in query
    _assert_query_placeholders_align(query, 13)
    assert params[0][2] is None
    assert params[0][12] is True


@pytest.mark.asyncio
async def test_store_lua_spawn_stats_preserves_link_without_team_identity():
    fake_bot = _FakeBot(has_round_id=True, resolved_round_id=None, team_exists=False)
    metadata = _sample_round_metadata()

    await UltimateETLegacyBot._store_lua_spawn_stats(
        fake_bot,
        metadata,
        [{"guid": "A1", "name": "AxisOne", "spawns": 2, "deaths": 1}],
    )

    query, params = fake_bot.db_adapter.batch_calls[0]
    assert "WHEN $13 THEN EXCLUDED.round_id" in query
    assert "COALESCE(EXCLUDED.round_id, lua_spawn_stats.round_id)" in query
    assert params[0][2] is None
    assert params[0][12] is False


@pytest.mark.asyncio
async def test_store_lua_spawn_stats_uses_only_persisted_team_round_id():
    fake_bot = _FakeBot(
        has_round_id=True,
        resolved_round_id=111,
        team_exists=True,
        team_round_id=9825,
    )

    await UltimateETLegacyBot._store_lua_spawn_stats(
        fake_bot,
        _sample_round_metadata(),
        [{"guid": "A1", "name": "AxisOne", "spawns": 2, "deaths": 1}],
    )

    _query, params = fake_bot.db_adapter.batch_calls[0]
    assert params[0][2] == 9825
    assert params[0][12] is True
