"""Late-arriving Lua rows must still find their round.

Until now a Lua capture that landed AFTER its round was imported could never
be linked: the exact path needs `rounds.round_start_unix`, which is only ever
filled from an already-linked Lua row (circular), and the fuzzy path runs when
a ROUND is imported, so it never looks at rows that arrive later. Measured on
the live database on 2026-08-15: 2026-08-12 had 13 captures and 0 links, and
the timing comparison reported "NO LUA DATA" for those rounds.

These tests pin the new path AND its refusals — the tolerance is deliberately
tight because every orphan whose nearest round was further than 30 s away
belonged to a neighbouring replay that already had its own Lua row.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from bot.services.lua_round_storage_mixin import (
    _LATE_LINK_TOLERANCE_SECONDS,
    _LuaRoundStorageMixin,
)


class FakeDB:
    def __init__(self, rounds_rows):
        self.rounds_rows = rounds_rows
        self.queries: list[tuple[str, tuple]] = []
        self.updates: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        self.queries.append((" ".join(query.split()), params or ()))
        return self.rounds_rows

    async def execute(self, query, params=None):
        self.updates.append((" ".join(query.split()), params or ()))
        return "UPDATE 1"


class _Bot(_LuaRoundStorageMixin):
    def __init__(self, db):
        self.db_adapter = db


def _unix(date_str: str, time_str: str) -> int:
    """Same local-naive convention the filename parser uses."""
    return int(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H%M%S").timestamp())  # noqa: DTZ007


ROUND_DATE = "2026-08-12"
ROUND_TIME = "222037"
ROUND_UNIX = _unix(ROUND_DATE, ROUND_TIME)


@pytest.mark.asyncio
async def test_links_a_round_within_tolerance():
    db = FakeDB([(11218, ROUND_DATE, ROUND_TIME)])
    bot = _Bot(db)

    linked = await bot._link_late_lua_row(
        map_name="sw_goldrush_te", round_number=1, lua_unix=ROUND_UNIX - 3
    )

    assert linked == 11218
    assert len(db.updates) == 1
    update_sql, params = db.updates[0]
    assert update_sql.startswith("UPDATE lua_round_teams SET round_id =")
    # Only ever claims a row that is still unlinked.
    assert "round_id IS NULL" in update_sql
    assert params[0] == 11218


@pytest.mark.asyncio
async def test_refuses_a_round_outside_tolerance():
    """A neighbouring replay of the same map is minutes away, not seconds."""
    db = FakeDB([(11218, ROUND_DATE, ROUND_TIME)])
    bot = _Bot(db)

    linked = await bot._link_late_lua_row(
        map_name="sw_goldrush_te",
        round_number=1,
        lua_unix=ROUND_UNIX - (_LATE_LINK_TOLERANCE_SECONDS + 1),
    )

    assert linked is None
    assert db.updates == []


@pytest.mark.asyncio
async def test_refuses_to_guess_on_a_tie():
    """Two rounds equally close: leave both alone rather than pick one."""
    before = datetime.fromtimestamp(ROUND_UNIX - 10).strftime("%H%M%S")  # noqa: DTZ006
    after = datetime.fromtimestamp(ROUND_UNIX + 10).strftime("%H%M%S")  # noqa: DTZ006
    db = FakeDB([(1, ROUND_DATE, before), (2, ROUND_DATE, after)])
    bot = _Bot(db)

    linked = await bot._link_late_lua_row(
        map_name="sw_goldrush_te", round_number=1, lua_unix=ROUND_UNIX
    )

    assert linked is None
    assert db.updates == []


@pytest.mark.asyncio
async def test_picks_the_closest_when_there_is_no_tie():
    closer = datetime.fromtimestamp(ROUND_UNIX - 2).strftime("%H%M%S")  # noqa: DTZ006
    further = datetime.fromtimestamp(ROUND_UNIX - 20).strftime("%H%M%S")  # noqa: DTZ006
    db = FakeDB([(99, ROUND_DATE, further), (42, ROUND_DATE, closer)])
    bot = _Bot(db)

    linked = await bot._link_late_lua_row(
        map_name="sw_goldrush_te", round_number=1, lua_unix=ROUND_UNIX
    )

    assert linked == 42


@pytest.mark.asyncio
async def test_candidate_query_excludes_rounds_that_already_have_lua_data():
    """The 'do not steal an occupied round' rule lives in SQL — pin it."""
    db = FakeDB([])
    bot = _Bot(db)

    await bot._link_late_lua_row(map_name="supply", round_number=2, lua_unix=ROUND_UNIX)

    sql, params = db.queries[0]
    assert "NOT EXISTS" in sql and "FROM lua_round_teams l WHERE l.round_id = r.id" in sql
    assert params[0] == "supply"
    assert params[1] == 2
    # Neighbouring calendar dates are searched too (a round can cross midnight).
    assert len(params[2]) == 3 and ROUND_DATE in params[2]


@pytest.mark.asyncio
async def test_missing_inputs_are_a_no_op():
    db = FakeDB([(1, ROUND_DATE, ROUND_TIME)])
    bot = _Bot(db)

    assert await bot._link_late_lua_row(map_name="", round_number=1, lua_unix=ROUND_UNIX) is None
    assert await bot._link_late_lua_row(map_name="supply", round_number=1, lua_unix=0) is None
    assert db.queries == [] and db.updates == []


@pytest.mark.asyncio
async def test_unparseable_round_time_is_skipped_not_crashed():
    db = FakeDB([(1, ROUND_DATE, "nonsense"), (2, ROUND_DATE, ROUND_TIME)])
    bot = _Bot(db)

    linked = await bot._link_late_lua_row(
        map_name="sw_goldrush_te", round_number=1, lua_unix=ROUND_UNIX
    )

    assert linked == 2
