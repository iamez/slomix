"""Opt-in full bootstrap + unmocked spawned import; retain synthetic DB for audit.

This is a two-round vehicle slice, not proof of all telemetry or live cutover.
Only the guarded disposable PostgreSQL endpoint is accepted. No app credentials,
service actions, consumer processes or deletion of databases/source files.
Requires RUNTIME_PROXIMITY_RETAIN_DB=true in addition to the guarded PG target.
Use a unique retained pytest basetemp plus saved output to preserve source files
and database names; the retained database alone is not the complete proof.
"""

import asyncio
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import asyncpg
import pytest

from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_config import ProximityProcessConfig
from shared.runtime_proximity_supervisor import supervise
from shared.runtime_source_reservation import reserve_source_generation
from shared.runtime_spool import publish_proximity_file
from tests.integration.test_runtime_events_pg import connection_options
from website.backend.services.round_web_service import load_capture_policy


def publish_round(root, number):
    start = 1789794600 + (number - 1) * 600
    payload = (
        f'# PROXIMITY_TRACKER_V4\n# map=fixture\n# round={number}\n'
        f'# round_start_unix={start}\n# round_end_unix={start + 600}\n'
        '# capabilities=vehicle_tracking:1\n\n# VEHICLE_PROGRESS\n'
        f'tank;script_mover;0;0;0;{number * 100};0;0;{number * 100};1000;900;0;'
        '1000;2000;1000;2000\n'
    ).encode()
    digest = hashlib.sha256(payload).hexdigest()
    filename = f'2026-09-19-051000-fixture-round-{number}_engagements.txt'
    generation = f'{number:032x}'
    directory = reserve_source_generation(root, generation)
    completion = dict(version=1, filename=filename, bytes=len(payload), state='writer_closed')
    publish_proximity_admission(directory, source_id='fixture-server', generation=generation,
        completion=completion, expected_sha256=digest, session_date=date(2026, 9, 19))
    publish_proximity_file(directory, filename, [payload], expected_size=len(payload), expected_sha256=digest)
    record_proximity_completion_once(directory, completion, expected_sha256=digest)
    return directory, filename, payload, digest


def one_parent_turn(config):
    stop = threading.Event()
    states = []

    def report(state):
        states.append(state['status'])
        if state['status'] in ('completed', 'failed', 'timed_out'):
            stop.set()

    supervise(config, stop, reporter=report, timeout_seconds=20)
    assert states == ['starting', 'batch_running', 'completed', 'stopped']


@pytest.fixture
async def retained_full_schema_database():
    retention = os.environ.get('RUNTIME_PROXIMITY_RETAIN_DB')
    if retention is None:
        pytest.skip('Retained proof requires explicit RUNTIME_PROXIMITY_RETAIN_DB=true')
    if retention != 'true':
        raise ValueError('RUNTIME_PROXIMITY_RETAIN_DB must be exactly true when specified')
    options = connection_options()
    database = 'runtime_fullproof_' + uuid.uuid4().hex
    admin = await asyncpg.connect(**options)
    try:
        await admin.execute(f'CREATE DATABASE "{database}" TEMPLATE template0')
        # Record acknowledged ownership even if closing the admin later fails.
        print(f'Synthetic proof database retained: {database}')
    finally:
        await admin.close(timeout=5)
    options = dict(options, database=database)
    owner = await asyncpg.connect(**options)
    try:
        identity = await owner.fetchrow('SELECT current_database() AS database, current_user AS username')
        if identity['database'] != database or identity['username'] != options['user']:
            raise RuntimeError('Retained proof database/user identity mismatch')
        yield owner, options
    finally:
        await owner.close(timeout=5)


@pytest.mark.asyncio
@pytest.mark.timeout(120)
@pytest.mark.parametrize('parents_late', [False, True])
async def test_full_schema_two_round_vehicle_import_and_fresh_child_replay(
        tmp_path, parents_late, retained_full_schema_database):
    owner, options = retained_full_schema_database
    database = options['database']
    observer = None
    try:
        schema = Path(__file__).resolve().parents[2] / 'tools/schema_postgresql.sql'
        await owner.execute(schema.read_text(), timeout=60)
        parents_sql = """
            INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix)
            VALUES (10,1,20,'fixture',1789794600), (11,2,20,'fixture',1789795200)
        """
        if not parents_late:
            await owner.execute(parents_sql)
        observer = await asyncpg.connect(**options)

        class ReaderAdapter:
            async def fetch_all(self, sql, params):
                return await observer.fetch(sql, *params)

        reader = ReaderAdapter()
        root = tmp_path / 'spool'
        root.mkdir(mode=0o700)
        gametimes = tmp_path / 'gametimes'
        gametimes.mkdir(mode=0o700)
        sources = [publish_round(root, number) for number in (1, 2)]
        config = ProximityProcessConfig(
            root, 'fixture-server', gametimes, options['host'], options.get('port', 5432),
            database, await owner.fetchval('SELECT current_user'), 'public', options.get('password', ''),
        )
        if parents_late:
            one_parent_turn(config)
            for table in ('proximity_vehicle_progress', 'proximity_processed_files'):
                assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
                assert await owner.fetch(f'SELECT * FROM {table}') == []
            for directory, filename, payload, _ in sources:
                outcome = json.loads((directory / '.proximity-outcome-001.json').read_text())
                assert (outcome['action'], outcome['reason']) == ('retry', 'parent_missing')
                assert (directory / filename).read_bytes() == payload
            await owner.execute(parents_sql)
            # Real UTC backoff across a fresh child, no mocked clock or rewritten history.
            deadlines = [json.loads((s[0] / '.proximity-attempt-001.json').read_text())['retry_at']
                         for s in sources]
            assert min(deadlines) - time.time() > 5, 'Fixture missed the cooldown observation window'
            one_parent_turn(config)
            assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
            assert await owner.fetchval('SELECT count(*) FROM proximity_vehicle_progress') == 0
            assert all(len(list(s[0].glob('.proximity-attempt-*.json'))) == 1 for s in sources)
            await asyncio.sleep(max(0, max(deadlines) - time.time()) + 1)
            print('Full-schema pending proof: zero committed rows/receipts without parents; '
                  'parent arrival does not bypass durable cooldown across child restart')
        for replay in (False, True):
            one_parent_turn(config)
            rows = await observer.fetch("""
                SELECT v.round_id,r.gaming_session_id,v.round_number,v.total_distance
                FROM proximity_vehicle_progress v JOIN rounds r ON r.id=v.round_id
                ORDER BY v.round_number
            """)
            assert [tuple(row) for row in rows] == [(10, 20, 1, 100.0), (11, 20, 2, 200.0)]
            assert await owner.fetchval('SELECT count(*) FROM proximity_vehicle_progress') == 2
            assert await owner.fetchval('SELECT sum(total_distance) FROM proximity_vehicle_progress') == 300
            receipts = await observer.fetch('SELECT file_hash,aggregates_applied,runtime_parent_gate,linked_round_id FROM proximity_processed_files')
            assert sorted(tuple(row) for row in receipts) == sorted(
                (s[3], True, True, 10 + index) for index, s in enumerate(sources))
            assert await owner.fetchval('SELECT count(*) FROM proximity_processed_files') == 2
            for round_id in (10, 11):
                policy = await load_capture_policy(reader, round_id)
                assert policy.manifest_count == 1
                assert policy.capabilities['vehicle_tracking'] == 'enabled'
                # A successful import does not invent a missing clock declaration.
                assert policy.event_time_basis is None
                assert await owner.fetchval(
                    'SELECT count(*) FROM proximity_processed_files WHERE linked_round_id=$1',
                    round_id,
                ) == policy.manifest_count
            for directory, filename, payload, _ in sources:
                assert (directory / filename).read_bytes() == payload
                attempts = sorted(directory.glob('.proximity-attempt-*.json'))
                expected_attempts = 2 if parents_late else 1
                assert len(attempts) == expected_attempts
                assert [json.loads(p.read_text())['attempt'] for p in attempts] == list(range(1, expected_attempts + 1))
            assert json.loads((root / '.proximity-cursor.json').read_text())['after'] == f'{2:032x}'
            print(f'Full-schema spawned proof: replay={replay}, 2 strict receipts, '
                  f'2 vehicle rows/300 distance, session20, {expected_attempts} attempts/source; '
                  'reader sees one vehicle manifest per linked round, clock unknown')
    finally:
        if observer is not None:
            await observer.close(timeout=5)
