"""Native eligibility parity on an explicit disposable database, never app data."""

import os
from datetime import date
from types import SimpleNamespace

import asyncpg
import pytest

from bot.services.monitor_tasks_mixin import _MonitorTasksMixin
from tests.disposable_database import connection_options, isolated_database
from website.backend.services.session_scope import _build_scope, _fetch_scope_rounds

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def scope_db():
    if not {"RUNTIME_EVENTS_TEST_SOCKET", "RUNTIME_EVENTS_TEST_CI"}.intersection(os.environ):
        pytest.skip("Disposable PostgreSQL not explicitly configured")
    connection_options()  # Requested invalid infrastructure is an error, not a skip.
    async with isolated_database() as config:
        options = {key: config[key] for key in ("host", "port", "database", "user", "password")}
        options.update(timeout=5, command_timeout=5, ssl=False)
        writer = await asyncpg.connect(**options)
        reader = None
        try:
            reader = await asyncpg.connect(**options)
            await writer.execute("""
                CREATE TABLE rounds (
                    id INTEGER PRIMARY KEY, gaming_session_id INTEGER,
                    round_start_unix BIGINT, map_name TEXT, round_number INTEGER,
                    round_date DATE, is_valid BOOLEAN, round_status TEXT, is_bot_round BOOLEAN
                );
                CREATE TABLE proximity_kill_outcome (
                    round_start_unix BIGINT, map_name TEXT, round_number INTEGER
                );
                CREATE TABLE storytelling_kill_impact (
                    round_start_unix BIGINT, map_name TEXT, round_number INTEGER
                )
            """)

            class Adapter:
                async def fetch_all(self, query, params=()):
                    return await reader.fetch(query, *params)

            yield writer, reader, Adapter()
        finally:
            try:
                if reader is not None:
                    await reader.close(timeout=5)
            finally:
                await writer.close(timeout=5)


# canonical and coverage are independent literal expectations. Coverage alone
# intentionally excludes bot rounds and unavailable clocks; canonical need not.
@pytest.mark.parametrize("valid,status,number,bot,clock,gsid,canonical,coverage", [
    (True, "completed", 1, False, 1794519000, 101, True, True),
    (None, "completed", 1, False, 1794519000, 101, True, True),
    (False, "completed", 1, False, 1794519000, 101, False, False),
    (True, "cancelled", 1, False, 1794519000, 101, False, False),
    (True, "restarted", 1, False, 1794519000, 101, False, False),
    (True, "unknown", 1, False, 1794519000, 101, False, False),
    (True, "substitution", 2, False, 1794519000, 101, True, True),
    (True, None, 2, False, 1794519000, 101, True, True),
    (None, None, 2, False, 1794519000, 101, True, True),
    (True, "completed", 0, False, 1794519000, 101, False, False),
    (True, "completed", 3, False, 1794519000, 101, False, False),
    (True, "completed", -1, False, 1794519000, 101, False, False),
    (True, "completed", 1, True, 1794519000, 101, True, False),
    (True, "completed", 1, None, 1794519000, 101, True, True),
    (True, "completed", 1, False, None, 101, True, False),
    (True, "", 1, False, 1794519000, 101, False, False),
    (True, "warmup", 1, False, 1794519000, 101, False, False),
    (True, "completed", None, False, 1794519000, 101, False, False),
    (True, "completed", 1, False, 1794519000, None, False, False),
], ids=["completed", "legacy-null-valid", "invalid", "cancelled", "restarted", "unknown-status",
        "substitution", "legacy-null-status", "legacy-both-null", "summary-r0", "nonstandard-r3",
        "negative-round", "bot-excluded", "legacy-null-bot", "missing-clock", "empty-status",
        "warmup", "missing-round-number", "missing-gsid"])
async def test_gap_eligibility_matches_canonical_policy(scope_db, valid, status, number, bot,
                                                       clock, gsid, canonical, coverage):
    writer, _, adapter = scope_db
    await writer.execute(
        "INSERT INTO rounds VALUES (1,$1,$2,'te_escape2',$3,'2026-11-12',$4,$5,$6)",
        gsid, clock, number, valid, status, bot,
    )
    await writer.execute("INSERT INTO proximity_kill_outcome VALUES ($1,'te_escape2',$2)", clock, number)
    scope_rows = await _fetch_scope_rounds(adapter, 101)
    expected_keys = [(clock, "te_escape2", number, "2026-11-12")] if canonical else []
    assert [tuple(row) for row in scope_rows] == expected_keys
    # A separate connection reads committed fixture rows through the actual
    # monitor method. No source regex or duplicate implementation of its SQL.
    gaps = await _MonitorTasksMixin._find_kis_coverage_gaps(SimpleNamespace(db_adapter=adapter))  # noqa: SLF001
    assert gaps == ([(101, "2026-11-12", 1, 0)] if coverage else [])


async def test_repeated_escape_halves_keep_distinct_keys_and_exact_counts(scope_db):
    writer, reader, adapter = scope_db
    keys = [(1794526500, "te_escape2", 1), (1794526800, "te_escape2", 2),
            (1794529500, "te_escape2", 1), (1794529800, "te_escape2", 2)]
    for index, (stamp, map_name, number) in enumerate(keys):
        await writer.execute(
            "INSERT INTO rounds VALUES ($1,202,$2,$3,$4,$5,TRUE,'completed',FALSE)",
            index + 1, stamp, map_name, number, date(2026, 11, 12 if index < 2 else 13),
        )
        await writer.execute("INSERT INTO proximity_kill_outcome VALUES ($1,$2,$3)", stamp, map_name, number)
    await writer.execute("INSERT INTO storytelling_kill_impact VALUES ($1,$2,$3)", *keys[0])
    # Another session shares the map/date, but its physical key is different
    # and its scores are complete. It must not alter this session's gap.
    other_key = (1794530000, "te_escape2", 1)
    await writer.execute("INSERT INTO rounds VALUES (5,303,$1,$2,$3,'2026-11-13',TRUE,'completed',FALSE)",
                         *other_key)
    await writer.execute("INSERT INTO proximity_kill_outcome VALUES ($1,$2,$3)", *other_key)
    await writer.execute("INSERT INTO storytelling_kill_impact VALUES ($1,$2,$3)", *other_key)
    assert await reader.fetchval("SELECT COUNT(*) FROM rounds") == 5
    assert await reader.fetchval("SELECT COUNT(*) FROM proximity_kill_outcome") == 5
    assert await reader.fetchval("SELECT COUNT(*) FROM storytelling_kill_impact") == 2
    assert [tuple(row[:3]) for row in await _fetch_scope_rounds(adapter, 202)] == keys
    assert [tuple(row[:3]) for row in await _fetch_scope_rounds(adapter, 303)] == [other_key]
    monitor = SimpleNamespace(db_adapter=adapter)
    assert await _MonitorTasksMixin._find_kis_coverage_gaps(monitor) == [(202, "2026-11-12", 4, 1)]  # noqa: SLF001
    await writer.executemany("INSERT INTO storytelling_kill_impact VALUES ($1,$2,$3)", keys[1:])
    assert await reader.fetchval("SELECT COUNT(*) FROM storytelling_kill_impact") == 5
    assert await _MonitorTasksMixin._find_kis_coverage_gaps(monitor) == []  # noqa: SLF001


async def test_eligible_round_without_proximity_rows_is_not_a_gap(scope_db):
    writer, reader, adapter = scope_db
    await writer.execute("INSERT INTO rounds VALUES (1,404,1794519000,'te_escape2',1,'2026-11-12',NULL,'completed',FALSE)")
    assert len(await _fetch_scope_rounds(adapter, 404)) == 1
    assert await reader.fetchval("SELECT COUNT(*) FROM proximity_kill_outcome") == 0
    assert await reader.fetchval("SELECT COUNT(*) FROM storytelling_kill_impact") == 0
    assert await _MonitorTasksMixin._find_kis_coverage_gaps(SimpleNamespace(db_adapter=adapter)) == []  # noqa: SLF001


@pytest.mark.parametrize("duplicate", ["same-session", "different-date", "cross-session"])
async def test_duplicate_scope_rows_do_not_multiply_event_counts(scope_db, duplicate):
    writer, reader, adapter = scope_db
    second_gsid = 102 if duplicate == "cross-session" else 101
    second_date = date(2026, 11, 13 if duplicate == "different-date" else 12)
    await writer.execute("""
        INSERT INTO rounds VALUES
            (1,101,1794519000,'te_escape2',1,'2026-11-12',TRUE,'completed',FALSE),
            (2,$1,1794519000,'te_escape2',1,$2,NULL,'completed',FALSE)
        """, second_gsid, second_date)
    key = (1794519000, "te_escape2", 1)
    await writer.executemany("INSERT INTO proximity_kill_outcome VALUES ($1,$2,$3)", [key] * 3)
    await writer.execute("INSERT INTO storytelling_kill_impact VALUES ($1,$2,$3)", *key)
    assert await reader.fetchval("SELECT COUNT(*) FROM proximity_kill_outcome") == 3
    assert await reader.fetchval("SELECT COUNT(*) FROM storytelling_kill_impact") == 1
    scope = _build_scope(101, await _fetch_scope_rounds(adapter, 101))
    assert scope.round_keys == (key,)
    expected = [(101, "2026-11-12", 3, 1)]
    if duplicate == "cross-session":
        # Counting parity does not resolve ownership when two session scopes
        # already claim the same physical key; that ambiguity remains separate.
        expected.insert(0, (102, "2026-11-12", 3, 1))
    monitor = SimpleNamespace(db_adapter=adapter)
    assert await _MonitorTasksMixin._find_kis_coverage_gaps(monitor) == expected  # noqa: SLF001
    await writer.executemany("INSERT INTO storytelling_kill_impact VALUES ($1,$2,$3)", [key] * 2)
    assert await reader.fetchval("SELECT COUNT(*) FROM storytelling_kill_impact") == 3
    assert await _MonitorTasksMixin._find_kis_coverage_gaps(monitor) == []  # noqa: SLF001
