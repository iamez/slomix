"""Codex §18/L3: relinker fanout + detection query now cover the three
tables with the worst wrong-round-linkage rates.

combat_engagement, player_track, and lua_round_teams were previously
excluded from both ProximityCog._PROXIMITY_ROUND_ID_TABLES (the fanout
UPDATE list) and _relink_null_round_ids's own detection UNION query — a
NULL or wrong round_id in any of them was never found, and never fixed, by
the 5-minute cron. L2 (test_relinker_fanout_coverage's earlier revision)
locked in that gap; this revision locks in the fix.
"""
# ruff: noqa: SLF001

from __future__ import annotations

import importlib
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from bot.cogs.proximity_cog import ProximityCog

relinker = importlib.import_module("bot.cogs.proximity_mixins.relinker_mixin")

_PREVIOUSLY_MISSING_TABLES = ("combat_engagement", "player_track", "lua_round_teams")


def test_fanout_table_list_now_includes_the_worst_offenders():
    for table in _PREVIOUSLY_MISSING_TABLES:
        assert table in ProximityCog._PROXIMITY_ROUND_ID_TABLES


class _CapturingDB:
    """Captures the detection query's SQL text, then reports zero unlinked
    rows so _relink_null_round_ids returns immediately afterward."""

    def __init__(self):
        self.captured_query: str | None = None
        self.captured_params: tuple | None = None

    async def fetch_all(self, query, params=None):
        self.captured_query = " ".join(str(query).split())
        self.captured_params = params
        return []


class _FakeBot:
    def __init__(self, db):
        self.db_adapter = db


def _relinker():
    svc = relinker._ProximityRelinkerMixin.__new__(relinker._ProximityRelinkerMixin)
    svc._PROXIMITY_ROUND_ID_TABLES = ProximityCog._PROXIMITY_ROUND_ID_TABLES
    return svc


@pytest.mark.asyncio
async def test_detection_query_now_includes_combat_engagement_and_player_track():
    """Both have a session_date column, so they use the generic leg shape."""
    db = _CapturingDB()
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    assert db.captured_query is not None
    assert "FROM combat_engagement WHERE round_id IS NULL" in db.captured_query
    assert "FROM player_track WHERE round_id IS NULL" in db.captured_query


@pytest.mark.asyncio
async def test_detection_query_lua_round_teams_synthesizes_session_date():
    """lua_round_teams has no session_date column — the detection query
    must synthesize one from round_start_unix (TO_TIMESTAMP(...)::date)
    rather than reference a column that doesn't exist."""
    db = _CapturingDB()
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    assert db.captured_query is not None
    assert "FROM lua_round_teams WHERE round_id IS NULL" in db.captured_query
    assert "TO_TIMESTAMP(round_start_unix)::date" in db.captured_query
    # Never a bare reference to a session_date COLUMN on this table.
    assert "lua_round_teams WHERE round_id IS NULL" in db.captured_query


@pytest.mark.asyncio
async def test_detection_query_deduplicates_only_once_after_union_all_legs():
    db = _CapturingDB()
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    assert db.captured_query is not None
    assert db.captured_query.startswith(
        "SELECT DISTINCT map_name, round_number, round_start_unix, session_date"
    )
    assert "UNION ALL" in db.captured_query
    assert "UNION" not in db.captured_query.replace("UNION ALL", "")


@pytest.mark.asyncio
async def test_detection_query_pushes_the_permanent_orphan_cutoff_into_every_leg():
    db = _CapturingDB()
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    assert db.captured_query is not None
    assert db.captured_params is not None
    assert "round_start_unix >= $1" in db.captured_query
    assert "round_start_unix IS NULL AND session_date >= $2" in db.captured_query
    assert len(db.captured_params) == 2


class _FanoutCapturingDB:
    """Reports one unlinked row, resolves it, then captures every UPDATE
    the fanout issues so the lua_round_teams special-case SQL/params can be
    asserted directly."""

    def __init__(self, target_unix: int, round_date: str, map_name: str = "supply"):
        self.executed: list[tuple[str, tuple]] = []
        self.fetched: list[tuple[str, tuple | None]] = []
        self._target_unix = target_unix
        self._round_date = round_date
        self._map_name = map_name

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        self.fetched.append((q, params))
        if "SELECT DISTINCT map_name" in q:
            return [(self._map_name, 1, self._target_unix, self._round_date)]
        if "SELECT id FROM rounds" in q:
            return [(999,)]
        return []

    async def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def fetch_val(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))
        return None


@pytest.mark.asyncio
async def test_fanout_links_lua_round_teams_with_dedicated_template():
    # A recent timestamp — the relinker skips anything older than 6h as a
    # permanent orphan before it ever reaches resolve_round_id/the fanout.
    target_unix = int(time.time()) - 300
    round_date = time.strftime("%Y-%m-%d", time.localtime(target_unix))
    db = _FanoutCapturingDB(target_unix, round_date)
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    lua_updates = [
        (q, p) for q, p in db.executed if "UPDATE lua_round_teams l" in q
    ]
    assert len(lua_updates) == 1
    query, params = lua_updates[0]
    assert "session_date" not in query
    assert "source_state.source_count = 1" in query
    assert "target_state.target_count = 1" in query
    assert "ELSE NULL" in query
    assert "FROM lua_round_teams" in query
    assert "round_number = $2" in query
    assert "round_start_unix = $3" in query
    assert params == ("supply", 1, target_unix)
    spawn_update = next(
        (query, params)
        for query, params in db.executed
        if "UPDATE lua_spawn_stats s" in query
    )
    assert "s.match_id = l.match_id" in spawn_update[0]
    assert spawn_update[1] == ("supply", 1, target_unix)


@pytest.mark.asyncio
async def test_fanout_lua_update_cannot_use_the_fuzzy_round_id():
    target_unix = int(time.time()) - 300
    round_date = time.strftime("%Y-%m-%d", time.localtime(target_unix))
    db = _FanoutCapturingDB(target_unix, round_date)
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    lua_updates = [
        (q, p) for q, p in db.executed if "UPDATE lua_round_teams l" in q
    ]
    assert len(lua_updates) == 1
    query, params = lua_updates[0]
    assert "source_state.source_count = 1" in query
    assert "target_state.target_count = 1" in query
    assert 999 not in params
    assert params == ("supply", 1, target_unix)


@pytest.mark.asyncio
async def test_positive_start_resolves_normalized_exact_target_before_fuzzy(monkeypatch):
    target_unix = int(time.time()) - 300
    round_date = time.strftime("%Y-%m-%d", time.localtime(target_unix))
    db = _FanoutCapturingDB(target_unix, round_date, map_name=" Supply ")
    svc = _relinker()
    svc.bot = _FakeBot(db)
    fuzzy = AsyncMock(side_effect=AssertionError("fuzzy resolver must not run"))
    monkeypatch.setattr("bot.core.round_linker.resolve_round_id", fuzzy)

    await svc._relink_null_round_ids()

    assert fuzzy.await_count == 0
    exact_query, exact_params = next(
        (query, params)
        for query, params in db.fetched
        if "SELECT id FROM rounds" in query
    )
    assert "LOWER(BTRIM(map_name)) = LOWER(BTRIM($1))" in exact_query
    assert exact_params == (" Supply ", 1, target_unix)
    lua_params = next(
        params for query, params in db.executed if "UPDATE lua_round_teams l" in query
    )
    assert lua_params == (" Supply ", 1, target_unix)


@pytest.mark.asyncio
async def test_lua_exact_failure_never_falls_back_to_generic_update():
    class _FailingLuaDB(_FanoutCapturingDB):
        async def execute(self, query, params=None):
            normalized = " ".join(str(query).split())
            self.executed.append((normalized, params))
            if "UPDATE lua_round_teams l" in normalized:
                raise RuntimeError("forced exact update failure")

    target_unix = int(time.time()) - 300
    round_date = time.strftime("%Y-%m-%d", time.localtime(target_unix))
    db = _FailingLuaDB(target_unix, round_date)
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    lua_queries = [
        query
        for query, _params in db.executed
        if "UPDATE lua_round_teams l" in query
    ]
    assert len(lua_queries) == 1
    assert "UPDATE lua_round_teams l" in lua_queries[0]
