"""Execute production composite SQL over SELECT-only statement-local fixtures.

ScopeDB captures metric/coverage SQL with canonical and missing-start cases.
The second exercise runs the real resolver and ASGI handler over the same
statement-local fixture. These scenarios do not measure the live corpus.
No fixture tables are created. Normal pytest requires disposable PostgreSQL.
"""

import asyncpg

from tests.integration.test_runtime_events_pg import connection_options
from tests.unit.test_composite_canonical_scope import ScopeDB
from website.backend.routers.skill_router import get_composite_stats

PREFIX = """
WITH rounds(id,gaming_session_id,round_number,is_valid,is_bot_round,round_status,
            round_start_unix,map_name,round_date) AS (
 VALUES (1,42,1,true,false,'completed',1000::bigint,'supply','2026-08-11'::date),
 (2,42,1,true,false,'substitution',2000,'supply','2026-08-12'),
 (3,42,1,true,false,'cancelled',NULL,'radar','2026-08-11'),
 (4,42,1,false,false,'completed',NULL,'radar','2026-08-11'),
 (5,42,1,true,true,'completed',NULL,'radar','2026-08-11'),
 (7,42,1,true,false,NULL,NULL,'radar','2026-08-11'),
 (8,43,1,true,false,'completed',4000,'radar','2026-08-11'),
 (9,44,1,true,true,'completed',6000,'supply','2026-08-12')
), player_comprehensive_stats AS (
 SELECT id AS round_id, 'A'::text AS player_guid,'Player'::text AS player_name,
 10 AS kills,2 AS deaths,1 AS gibs,60 AS time_played_seconds,0 AS time_dead_minutes,
 0 AS time_dead_ratio,0 AS denied_playtime FROM rounds
), events(id,round_start_unix,map_name,round_number,session_date,round_id) AS (
 VALUES (10,1000::bigint,'supply',1,'2026-08-11'::date,999),
 (20,2000,'supply',1,'2026-08-12'::date,999),
 (30,3000,'supply',1,'2026-08-11'::date,1),
 (40,1000,'other',1,'2026-08-11'::date,1),
 (50,1000,'supply',2,'2026-08-11'::date,1),
 (60,1000,'supply',1,'2026-08-13'::date,1),
 (70,3500,'radar',1,'2026-08-11'::date,7),
 (80,4000,'radar',1,'2026-08-11'::date,7),
 (90,3500,'radar',1,'2026-08-11'::date,8),
 (100,3500,'other',1,'2026-08-11'::date,7),
 (110,3500,'radar',2,'2026-08-11'::date,7),
 (120,3500,'radar',1,'2026-08-12'::date,7),
 (130,3500,'radar',1,'2026-08-11'::date,3),
 (140,3500,'radar',1,'2026-08-11'::date,4),
 (150,3500,'radar',1,'2026-08-11'::date,5),
 (160,9999,'supply',1,'2026-08-11'::date,1)
), proximity_kill_outcome AS (
 SELECT *,'A'::text AS killer_guid_canonical,'gibbed'::text AS outcome FROM events
), storytelling_kill_impact AS (
 SELECT id AS kill_outcome_id,CASE WHEN id IN (30,70) THEN NULL ELSE 42 END AS gaming_session_id,
 'A'::text AS killer_guid_canonical,
 true AS is_crossfire FROM events
 UNION ALL SELECT 10,43,'A',true
), proximity_lua_trade_kill AS (
 SELECT *,'A'::text AS trader_guid_canonical FROM events
), proximity_combat_position AS (
 SELECT *,'A'::text AS attacker_guid_canonical,'kill'::text AS event_type,
 20 AS killer_health,'AXIS'::text AS attacker_team,1 AS axis_alive,2 AS allies_alive FROM events
), proximity_spawn_timing AS (
 SELECT *,'A'::text AS killer_guid_canonical,10.0 AS spawn_timing_score FROM events
), proximity_crossfire_opportunity AS (
 SELECT * FROM events
)
"""


async def exercise_composite_scope(conn):
    assert await conn.fetchval("SHOW transaction_read_only") == "on"
    db = ScopeDB(missing_start=True)
    await get_composite_stats(db=db, gaming_session_id=42, session_date=None)
    query, params = next((q, p) for q, p in db.queries if "WITH session_pcs" in q)
    coverage, cparams = next(
        (q, p) for q, p in db.queries if "SELECT COUNT(*) FROM proximity_crossfire_opportunity" in q
    )
    rows = await conn.fetch(PREFIX.rstrip() + ", " + query.lstrip().removeprefix("WITH "), *params)
    counts = await conn.fetchrow(PREFIX + coverage, *cparams)
    assert tuple(counts) == (3, 3, 3, 3, 3, 3), tuple(counts)
    assert len(rows) == 1 and tuple(rows[0])[:10] == ("A", "Player", 30, 3, 3, 3, 3, 3, 3, 10.0), tuple(rows[0])
    mutant = query.replace(
        "AND kill_outcome_id IN", "OR kill_outcome_id IN"
    )
    assert mutant != query
    badrows = await conn.fetch(PREFIX.rstrip() + ", " + mutant.lstrip().removeprefix("WITH "), *params)
    assert badrows[0][3] != rows[0][3], (badrows[0][3], rows[0][3])
    return {"coverage": list(counts), "crossfire": rows[0][3], "mutant_crossfire": badrows[0][3]}


async def test_native_composite_canonical_scope():
    options = connection_options()
    options["server_settings"] = {
        **options.get("server_settings", {}),
        "default_transaction_read_only": "on",
        "statement_timeout": "5000",
    }
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(readonly=True):
            await exercise_composite_scope(conn)
            await exercise_composite_resolution(conn)
    finally:
        await conn.close(timeout=5)


async def exercise_composite_resolution(conn):
    """Execute the real resolver and ASGI handler over statement-local rows."""
    import httpx
    from fastapi import FastAPI

    from website.backend.dependencies import get_db
    from website.backend.routers.skill_router import router

    class FixtureDB:
        def __init__(self, prefix=PREFIX):
            self.prefix = prefix
            self.queries = []

        async def fetch_all(self, query, params=None):
            self.queries.append((query, params))
            sql = (self.prefix.rstrip() + ', ' + query.lstrip().removeprefix('WITH ')
                   if query.lstrip().startswith('WITH ') else self.prefix + query)
            return await conn.fetch(sql, *(params or ()))

        async def fetch_one(self, query, params=None):
            rows = await self.fetch_all(query, params)
            return rows[0] if rows else None

    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    db = FixtureDB()
    app = FastAPI()
    app.include_router(router, prefix='/api')
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
        by_id = await client.get('/api/skill/composite?gaming_session_id=42')
        by_date = await client.get('/api/skill/composite?session_date=2026-08-12')
        ambiguous = await client.get('/api/skill/composite?session_date=2026-08-11')
    assert by_id.status_code == by_date.status_code == 200
    assert by_id.json() == by_date.json()  # Bot-only session44 cannot create a false409.
    assert ambiguous.status_code == 409
    assert by_id.json()['coverage']['source_rows']['kill_outcomes'] == 3
    # No round_id (including a plausible linked ID) may choose between two
    # accepted sessions owning the same full canonical key.
    anchor = "(9,44,1,true,true,'completed',6000,'supply','2026-08-12')"
    collision = "(9,44,1,true,false,'completed',1000,'supply','2026-08-11')"
    db = FixtureDB(PREFIX.replace(anchor, collision))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
        shared = await client.get('/api/skill/composite?gaming_session_id=42')
        other = await client.get('/api/skill/composite?gaming_session_id=44')
    assert shared.status_code == other.status_code == 409
    assert shared.json()['detail']['code'] == 'ambiguous_round_key'
    assert not any('WITH session_pcs' in q for q, _ in db.queries)
    # The date is part of the key. Rejected/bot/R0 neighbours do not own it.
    for neighbour in [
        collision.replace('2026-08-11', '2026-08-13'),
        collision.replace('true,false', 'true,true'),
        collision.replace('true,false', 'false,false'),
        collision.replace('completed', 'cancelled'),
        collision.replace('completed', 'orphan'),
        collision.replace('(9,44,1,', '(9,44,0,'),
        collision.replace('(9,44,1,', '(9,42,1,'),
    ]:
        db = FixtureDB(PREFIX.replace(anchor, neighbour))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://fixture') as client:
            admitted = await client.get('/api/skill/composite?gaming_session_id=42')
        assert admitted.status_code == 200, (neighbour, admitted.text)
    # Move just the timestamp-less accepted fixture to a newer date. Default
    # discovery must use the same fallback rather than silently pick old data.
    newer = PREFIX.replace("(7,42,1,true,false,NULL,NULL,'radar','2026-08-11')",
                           "(7,42,1,true,false,NULL,NULL,'radar','2026-08-14')").replace(
                               "(70,3500,'radar',1,'2026-08-11'::date,7)",
                               "(70,3500,'radar',1,'2026-08-14'::date,7)")
    db = FixtureDB(newer)
    default = await get_composite_stats(db=db, gaming_session_id=None, session_date=None)
    assert default['gaming_session_id'] == 42
    assert any(params == ('2026-08-14',) for _query, params in db.queries)
    return {'id_status': by_id.status_code, 'real_plus_bot_status': by_date.status_code,
            'two_real_status': ambiguous.status_code, 'shared_key_status': shared.status_code,
            'non_owner_controls': 7, 'kill_outcomes': 3, 'default_date': '2026-08-14'}
