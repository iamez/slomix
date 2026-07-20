"""Codex §18/L3: relinker fanout + detection query now cover the three
tables with the worst wrong-round-linkage rates.

combat_engagement, player_track, and lua_round_teams were previously
excluded from both ProximityCog._PROXIMITY_ROUND_ID_TABLES (the fanout
UPDATE list) and _relink_null_round_ids's own detection UNION query — a
NULL or wrong round_id in any of them was never found, and never fixed, by
the 5-minute cron. L2 (test_relinker_fanout_coverage's earlier revision)
locked in that gap; this revision locks in the fix.
"""
from __future__ import annotations

import importlib
import time

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

    async def fetch_all(self, query, params=None):
        self.captured_query = " ".join(str(query).split())
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


class _FanoutCapturingDB:
    """Reports one unlinked row, resolves it, then captures every UPDATE
    the fanout issues so the lua_round_teams special-case SQL/params can be
    asserted directly."""

    def __init__(self, target_unix: int, round_date: str):
        self.executed: list[tuple[str, tuple]] = []
        self._target_unix = target_unix
        self._round_date = round_date

    async def fetch_all(self, query, params=None):
        q = " ".join(str(query).split())
        if "SELECT DISTINCT map_name" in q:
            return [("supply", 1, self._target_unix, self._round_date)]
        # rounds candidate lookup inside resolve_round_id_with_reason
        if "FROM rounds" in q:
            return [(999, self._round_date, "000000", None, self._target_unix)]
        return []

    async def execute(self, query, params=None):
        self.executed.append((" ".join(str(query).split()), params))


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
        (q, p) for q, p in db.executed if "UPDATE lua_round_teams" in q
    ]
    assert len(lua_updates) == 1
    query, params = lua_updates[0]
    assert "session_date" not in query
    assert "round_number = $3" in query
    assert "round_start_unix = $4" in query
    assert params == (999, "supply", 1, target_unix)
