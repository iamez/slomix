"""SELECT-only execution of both real aggregates over statement-local fixtures.

No tables or rows are created. Normal pytest requires the explicit disposable
PostgreSQL target; exercise_status_gate can also use a caller-owned read-only
connection. This proves query semantics, not current corpus totals.
"""

from types import SimpleNamespace

import asyncpg

from tests.integration.test_runtime_events_pg import connection_options
from website.backend.services.storytelling.kill_matrix import _KillMatrixMixin
from website.backend.services.storytelling.movement import _MovementMixin


class FixtureDB:
    def __init__(self, conn, status):
        self.conn = conn
        self.status = status

    async def fetch_all(self, query, params):
        prefix = """
            WITH rounds AS (
                SELECT 1 AS id, 144 AS gaming_session_id, 1 AS round_number,
                       FALSE AS is_bot_round, TRUE AS is_valid, $2::text AS round_status
            ), proximity_kill_outcome AS (
                SELECT 1 AS round_id, 'AAAAAAAA'::text AS killer_guid,
                       'BBBBBBBB'::text AS victim_guid, 'Killer'::text AS killer_name,
                       'Victim'::text AS victim_name, 'gibbed'::text AS outcome
            ), player_track AS (
                SELECT 1 AS round_id, 'AAAAAAAA'::text AS player_guid,
                       'Runner'::text AS player_name, 120.0 AS total_distance,
                       20.0 AS avg_speed, 30.0 AS peak_speed, 1.0 AS sprint_sec,
                       10.0 AS post_spawn_distance, 6000 AS duration_ms
            )
        """
        return await self.conn.fetch(prefix + query, *params, self.status)


class Service(_KillMatrixMixin, _MovementMixin):
    def __init__(self, db):
        self.db = db


async def exercise_status_gate(conn):
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    results = []
    for status, accepted in [('completed', True), ('substitution', True), (None, True),
                             ('cancelled', False), ('orphan_r2', False), ('unknown', False)]:
        service = Service(FixtureDB(conn, status))
        scope = SimpleNamespace(gaming_session_id=144)
        kills = await service.compute_kill_matrix(scope)
        movement = await service.compute_movement(scope)
        assert kills['available'] is accepted, ('kill_matrix', status, kills)
        assert movement['available'] is accepted, ('movement', status, movement)
        if accepted:
            assert kills['total_kills'] == 1
            assert movement['players'][0]['total_distance'] == 120.0
        else:
            assert kills['players'] == movement['players'] == []
        results.append({'status': status, 'accepted': accepted})
    assert await conn.fetchval('SHOW transaction_read_only') == 'on'
    return {'queries': 12, 'cases': results, 'read_only': True}


async def test_native_round_status_gate():
    options = connection_options()
    options['server_settings'] = {**options.get('server_settings', {}),
                                  'default_transaction_read_only': 'on',
                                  'statement_timeout': '5000'}
    conn = await asyncpg.connect(**options)
    try:
        async with conn.transaction(readonly=True):
            await exercise_status_gate(conn)
    finally:
        await conn.close(timeout=5)
