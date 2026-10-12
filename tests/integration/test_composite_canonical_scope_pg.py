"""Execute production composite SQL over SELECT-only statement-local fixtures.

ScopeDB captures query construction with two accepted canonical round keys;
this exercise validates metric/coverage SQL, not the resolver or live corpus.
No fixture tables are created. Normal pytest requires disposable PostgreSQL.
"""

import asyncpg

from tests.integration.test_runtime_events_pg import connection_options
from tests.unit.test_composite_canonical_scope import ScopeDB
from website.backend.routers.skill_router import get_composite_stats

PREFIX = """
WITH rounds(id,gaming_session_id,round_number,is_valid,is_bot_round,round_status) AS (
 VALUES (1,42,1,true,false,'completed'),(2,42,1,true,false,'substitution'),
 (3,42,1,true,false,'cancelled'),(4,42,1,false,false,'completed'),(5,42,1,true,true,'completed')
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
 (60,1000,'supply',1,'2026-08-13'::date,1)
), proximity_kill_outcome AS (
 SELECT *,'A'::text AS killer_guid_canonical,'gibbed'::text AS outcome FROM events
), storytelling_kill_impact AS (
 SELECT id AS kill_outcome_id,42 AS gaming_session_id,'A'::text AS killer_guid_canonical,
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
    db = ScopeDB()
    await get_composite_stats(db=db, gaming_session_id=42, session_date=None)
    query, params = next((q, p) for q, p in db.queries if "WITH session_pcs" in q)
    coverage, cparams = next(
        (q, p) for q, p in db.queries if "SELECT COUNT(*) FROM proximity_crossfire_opportunity" in q
    )
    rows = await conn.fetch(PREFIX.rstrip() + ", " + query.lstrip().removeprefix("WITH "), *params)
    counts = await conn.fetchrow(PREFIX + coverage, *cparams)
    assert tuple(counts) == (2, 2, 2, 2, 2, 2), tuple(counts)
    assert len(rows) == 1 and tuple(rows[0])[:10] == ("A", "Player", 20, 2, 2, 2, 2, 2, 2, 10.0), tuple(rows[0])
    mutant = query.replace(
        "WHERE gaming_session_id = $1 AND kill_outcome_id IN", "WHERE gaming_session_id = $1 OR kill_outcome_id IN"
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
    finally:
        await conn.close(timeout=5)
