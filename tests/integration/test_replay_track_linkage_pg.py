"""Replay track->round linkage against real PostgreSQL.

`player_track` carries a real `round_id` FK, but the replay queries used to
join on (session_date, round_number, map_name). When the same map and round
number is played more than once on one date — routine in a long session —
that key matches EVERY repeat, so one track row was pulled into several
rounds at once. On the dev database that bound 24,428 track rows to more
than one round; round 10188 (sw_goldrush_te R2) returned 591 tracks where it
has 113, and its replay drew 14 distinct players for an 8-player round.

This is a SQL-semantics bug, so a fake connection cannot prove it fixed. The
tests below build the exact ambiguous shape in an isolated schema and run
the real `_TRACK_ROUND_JOIN` constant the service uses.
"""
import os
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

asyncpg = pytest.importorskip("asyncpg")

from website.backend.services.replay_service import (  # noqa: E402
    _TRACK_ROUND_JOIN,
)

TEST_DB = {
    "host": os.getenv("POSTGRES_TEST_HOST", "localhost"),
    "port": int(os.getenv("POSTGRES_TEST_PORT", "5432")),
    "database": os.getenv("POSTGRES_TEST_DATABASE", "etlegacy_test"),
    "user": os.getenv("POSTGRES_TEST_USER", "etlegacy_user"),
    "password": os.getenv("POSTGRES_TEST_PASSWORD", "etlegacy_test_password"),
}

# The date-key join the fix replaced. Kept here so the tests can show the
# difference on identical data rather than asserting on source text.
_LEGACY_JOIN = """
        JOIN rounds r ON r.round_date::date = pt.session_date
                     AND r.round_number = pt.round_number
                     AND r.map_name = pt.map_name
"""

_COUNT_SQL = """
    SELECT r.id AS round_id, pt.id AS track_id
    FROM player_track pt
    {join}
"""


async def _connect_or_skip():
    try:
        return await asyncpg.connect(timeout=5, **TEST_DB)
    except (TimeoutError, OSError, asyncpg.PostgresError) as e:
        pytest.skip(f"test PostgreSQL unavailable: {e}")


@pytest.fixture
async def pg():
    """Isolated schema so `rounds` / `player_track` resolve to test tables."""
    conn = await _connect_or_skip()
    ns = f"replaylink_{uuid.uuid4().hex[:8]}"
    await conn.execute(f"CREATE SCHEMA {ns}")
    await conn.execute(f"SET search_path TO {ns}")
    await conn.execute("""
        CREATE TABLE rounds (
            id SERIAL PRIMARY KEY,
            round_date TIMESTAMP,
            round_number INT,
            map_name TEXT
        )
    """)
    await conn.execute("""
        CREATE TABLE player_track (
            id SERIAL PRIMARY KEY,
            round_id INT,
            session_date DATE,
            round_number INT,
            map_name TEXT,
            player_guid TEXT
        )
    """)
    yield conn
    await conn.execute(f"DROP SCHEMA {ns} CASCADE")
    await conn.close()


async def _two_rounds_same_map_same_day(conn):
    """The shape that broke it: one map, one round number, twice in a day."""
    first = await conn.fetchval(
        "INSERT INTO rounds (round_date, round_number, map_name) "
        "VALUES ('2026-07-20 19:00', 2, 'sw_goldrush_te') RETURNING id"
    )
    second = await conn.fetchval(
        "INSERT INTO rounds (round_date, round_number, map_name) "
        "VALUES ('2026-07-20 21:30', 2, 'sw_goldrush_te') RETURNING id"
    )
    return first, second


async def _rows(conn, join):
    return await conn.fetch(_COUNT_SQL.format(join=join))


@pytest.mark.asyncio
async def test_linked_track_belongs_to_exactly_one_round(pg):
    """The core defect: a track row attributed to several rounds at once."""
    conn = pg
    first, second = await _two_rounds_same_map_same_day(conn)
    await conn.execute(
        "INSERT INTO player_track "
        "(round_id, session_date, round_number, map_name, player_guid) "
        "VALUES ($1, '2026-07-20', 2, 'sw_goldrush_te', 'PLAYER_A')",
        first,
    )

    legacy = await _rows(conn, _LEGACY_JOIN)
    assert len(legacy) == 2, (
        "precondition: the date key really is ambiguous here"
    )
    assert {r["round_id"] for r in legacy} == {first, second}

    fixed = await _rows(conn, _TRACK_ROUND_JOIN)
    assert len(fixed) == 1
    assert fixed[0]["round_id"] == first, (
        "a track with a round_id must follow its FK, not the date key"
    )


@pytest.mark.asyncio
async def test_unlinked_track_is_recovered_when_the_date_key_is_unique(pg):
    """5.1% of track rows have no round_id. Dropping them outright would
    have taken 59 rounds' replay dark, so an unambiguous date key still
    resolves them."""
    conn = pg
    only = await conn.fetchval(
        "INSERT INTO rounds (round_date, round_number, map_name) "
        "VALUES ('2026-07-21 20:00', 1, 'supply') RETURNING id"
    )
    await conn.execute(
        "INSERT INTO player_track "
        "(round_id, session_date, round_number, map_name, player_guid) "
        "VALUES (NULL, '2026-07-21', 1, 'supply', 'PLAYER_B')"
    )

    fixed = await _rows(conn, _TRACK_ROUND_JOIN)
    assert len(fixed) == 1
    assert fixed[0]["round_id"] == only


@pytest.mark.asyncio
async def test_unlinked_track_is_dropped_when_the_date_key_is_ambiguous(pg):
    """Attributing a track to the wrong round is worse than not showing it,
    so an unlinked row with an ambiguous key resolves to no round at all."""
    conn = pg
    await _two_rounds_same_map_same_day(conn)
    await conn.execute(
        "INSERT INTO player_track "
        "(round_id, session_date, round_number, map_name, player_guid) "
        "VALUES (NULL, '2026-07-20', 2, 'sw_goldrush_te', 'PLAYER_C')"
    )

    legacy = await _rows(conn, _LEGACY_JOIN)
    assert len(legacy) == 2, "the legacy join would have guessed, twice"

    fixed = await _rows(conn, _TRACK_ROUND_JOIN)
    assert fixed == [], (
        "an ambiguous unlinked track must not be attributed to any round"
    )


@pytest.mark.asyncio
async def test_a_round_played_twice_keeps_its_own_players(pg):
    """End-to-end shape of the live bug: each repeat must return only its
    own tracks, not the union of the day's same-map rounds."""
    conn = pg
    first, second = await _two_rounds_same_map_same_day(conn)
    for guid, rid in (("A", first), ("B", first), ("C", second)):
        await conn.execute(
            "INSERT INTO player_track "
            "(round_id, session_date, round_number, map_name, player_guid) "
            "VALUES ($1, '2026-07-20', 2, 'sw_goldrush_te', $2)",
            rid, guid,
        )

    rows = await conn.fetch(
        f"""
        SELECT pt.player_guid
        FROM player_track pt
        {_TRACK_ROUND_JOIN}
        WHERE r.id = $1
        """,
        first,
    )
    assert sorted(r["player_guid"] for r in rows) == ["A", "B"], (
        "the second round's player leaked into the first"
    )

    legacy_rows = await conn.fetch(
        f"""
        SELECT pt.player_guid
        FROM player_track pt
        {_LEGACY_JOIN}
        WHERE r.id = $1
        """,
        first,
    )
    assert sorted(r["player_guid"] for r in legacy_rows) == ["A", "B", "C"], (
        "precondition: the legacy join really did leak"
    )
