"""Real Lua timing/stats -> native retained provenance -> fresh canonical target.

Only isolated full-schema databases. No timing application, source ack or service.
"""

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from bot.runtime_completed_import import import_completed_round
from bot.runtime_gametime_correlation import inspect_declared_gametime
from bot.runtime_gametime_retention import retain_gametime_source
from bot.services.lua_correction_inbox import correction_payload_digest
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.unit.test_runtime_gametime_independence import run as run_timing
from tests.unit.test_runtime_gametime_source import NAME
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_stats_dispatch import prepare, reference, setup_pair

full_import_db = _full_import_db
pytestmark = pytest.mark.timeout(120)


@pytest.fixture
async def pipeline(full_import_db, tmp_path):
    manager, reader = full_import_db
    authority, spool, pair = setup_pair(tmp_path / 'stats')
    first = run_writer('lua5.4', spool, pair, 1, 'bound-ipc', dispatch=prepare(authority, spool, pair))
    second = run_writer('lua5.4', spool, pair, 2, 'bound-ipc-retry',
                        dispatch=prepare(authority, spool, pair, 2, reference(first)))
    for item, dependency, identity in ((first, None, pair.first), (second, first, pair.second)):
        assert (await import_completed_round(manager, item, first=dependency, expected_identity=identity))[0]
    artifacts = []
    for half, identity in enumerate((pair.first, pair.second), 1):
        directory = tmp_path / f'timing{half}'
        directory.mkdir()
        run_timing(directory, enabled=False, target=False, mode='frame', identity=identity)
        path = directory / NAME.replace('R1', f'R{half}')
        raw = path.read_bytes()
        options = dict(source_id=identity.source_id, generation=str(half) * 32,
                       filename=path.name, expected_size=len(raw), expected_sha256=hashlib.sha256(raw).hexdigest(),
                       expected_identity=identity)
        artifacts.append((path, options))
    async with manager.pool.acquire() as writer:
        yield SimpleNamespace(writer=writer, reader=reader, adapter=adapter_for(writer), artifacts=artifacts,
                              pair=pair, root=tmp_path)


async def retain(p, half=0):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        return await retain_gametime_source(p.adapter, stream.fileno(), **options)


async def inspect(p, half=0, observer=None):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        stream.seek(3)
        result = await inspect_declared_gametime(observer or p.reader, stream.fileno(), **options)
        assert stream.tell() == 3
        return result


async def snapshot(connection):
    tables = ('rounds', 'player_comprehensive_stats', 'runtime_events', 'runtime_round_mappings',
              'lua_correction_inputs', 'runtime_gametime_sources', 'runtime_gametime_identities')
    return {table: await connection.fetch(f'SELECT * FROM {table} ORDER BY 1,2') for table in tables}


async def test_actual_lua_pair_fresh_commit_rollback_and_no_timing_application(pipeline):
    p = pipeline
    before = await snapshot(p.reader)
    assert (await inspect(p)).status == 'missing_retention'
    outer = p.writer.transaction()
    await outer.start()
    try:
        await retain(p)
        assert (await inspect(p)).status == 'missing_retention'
        with pytest.raises(RuntimeError):
            await inspect(p, observer=p.writer)
    finally:
        await outer.rollback()
    assert await snapshot(p.reader) == before
    for half in (0, 1):
        retained = await retain(p, half)
        stable = await snapshot(p.reader)
        observed = await inspect(p, half)
        assert observed.status == 'canonical_target_verified', observed
        assert observed.input_id == retained.input_id
        parent = await p.reader.fetchrow('SELECT id,gaming_session_id,round_date FROM rounds WHERE round_number=$1', half + 1)
        assert (observed.round_id, observed.gaming_session_id) == (parent['id'], parent['gaming_session_id'])
        # Stats use 2026 filename keys, synthetic timing producer wall clock2023.
        # It must be identity, NOT that deliberately incompatible clock, linking.
        assert parent['round_date'] == '2026-09-25'
        assert await p.reader.fetchval('SELECT round_start_unix FROM lua_correction_inputs WHERE id=$1', retained.input_id) == 1700000000
        assert await snapshot(p.reader) == stable
    after = await snapshot(p.reader)
    for table in ('rounds', 'player_comprehensive_stats', 'runtime_events', 'runtime_round_mappings'):
        assert after[table] == before[table]
    assert len(after['runtime_gametime_identities']) == await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_identities') == 2
    print('WHOLE LUA STATS+TIMING -> PG097/098/099: 2 canonical targets, incompatible clocks ignored; '
          'uncommitted invisible, rollback empty, rounds/player statistics unchanged')


async def test_committed_corruption_and_missing_mapping_never_verify(pipeline):
    p = pipeline
    await retain(p, 0)
    await retain(p, 1)
    cases = (
        ('runtime_gametime_sources', 'generation', "UPDATE runtime_gametime_sources SET source_sha256=repeat('f',64)", 'conflict'),
        ('runtime_gametime_identities', 'generation', "UPDATE runtime_gametime_identities SET match_id=repeat('f',32)", 'conflict'),
        ('runtime_gametime_identities', None, 'DELETE FROM runtime_gametime_identities', 'conflict'),
        ('lua_correction_inputs', 'id', "UPDATE lua_correction_inputs SET payload_digest=repeat('f',64) WHERE round_number=2", 'conflict'),
        ('lua_correction_inputs', 'id', "UPDATE lua_correction_inputs SET map_name='oasis'", 'conflict'),
        ('runtime_round_mappings', None, 'DELETE FROM runtime_round_mappings', 'mapping_pending'),
        ('runtime_events', 'id', 'UPDATE runtime_events SET validation_passed=FALSE WHERE round_number=1', 'conflict'),
        ('rounds', 'id', "UPDATE rounds SET map_name='oasis' WHERE round_number=1", 'conflict'),
    )
    for table, key, statement, expected in cases:
        before = await snapshot(p.reader)
        originals = before[table]
        if table == 'runtime_round_mappings':
            originals = sorted(originals, key=lambda row: row['round_number'])
        transaction = p.writer.transaction()
        await transaction.start()
        try:
            await p.writer.execute(statement)
            assert (await inspect(p, 1)).status == 'canonical_target_verified'
        finally:
            await transaction.rollback()
        await p.writer.execute(statement)  # Native autocommit, not writer-local illusion.
        damaged = await snapshot(p.reader)
        assert (await inspect(p, 1)).status == expected, statement
        assert await snapshot(p.reader) == damaged  # Observer never repairs evidence.
        # Restore only the fixture's measured rows, preserving every stored value.
        # Names below originate from this fixed full-schema test, never user SQL.
        async with p.writer.transaction():
            for row in originals:
                columns = list(row.keys())
                if key is None:
                    values = ','.join(f'${i}' for i in range(1, len(columns) + 1))
                    query = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({values})"
                    await p.writer.execute(query, *row)
                else:
                    columns = [column for column in columns if column != key]
                    assignments = ','.join(f'{column}=${i}' for i, column in enumerate(columns, 1))
                    query = f'UPDATE {table} SET {assignments} WHERE {key}=${len(columns) + 1}'
                    await p.writer.execute(query, *(row[column] for column in columns), row[key])
        assert await snapshot(p.reader) == before
        assert (await inspect(p, 1)).status == 'canonical_target_verified'
    # A self-consistent new normalized payload/digest is STILL not the retained
    # projection of these admitted bytes. Checking its own hash is insufficient.
    row = await p.reader.fetchrow('SELECT id,payload FROM lua_correction_inputs WHERE round_number=2')
    payload = json.loads(row['payload'])
    payload['actual_duration_seconds'] -= 1
    await p.writer.execute('UPDATE lua_correction_inputs SET payload=$1::jsonb,payload_digest=$2 WHERE id=$3',
                           json.dumps(payload), correction_payload_digest(payload), row['id'])
    assert (await inspect(p, 1)).status == 'conflict'


async def test_snapshot_cannot_mix_concurrent_committed_evidence(pipeline):
    p = pipeline
    await retain(p, 1)
    phases = []

    async def fetchrow(query, *args):
        row = await p.reader.fetchrow(query, *args)
        if 'FROM runtime_gametime_sources ' in query:
            assert await p.reader.fetchval('SHOW transaction_read_only') == 'on'
            phases.append('source_snapshot')
            await p.writer.execute('UPDATE runtime_events SET validation_passed=FALSE WHERE round_number=1')
            phases.append('changed_event_committed')
        return row

    proxy = SimpleNamespace(is_in_transaction=p.reader.is_in_transaction,
                            transaction=p.reader.transaction, fetchrow=fetchrow)
    assert (await inspect(p, 1, observer=proxy)).status == 'canonical_target_verified'
    assert phases == ['source_snapshot', 'changed_event_committed']
    assert (await inspect(p, 1)).status == 'conflict'
    print('SNAPSHOT PROOF: concurrent event edit excluded from current view, detected by next fresh view')


async def test_deduplicated_input_cannot_substitute_another_declared_round(pipeline):
    p = pipeline
    first = await retain(p)
    path, options = p.artifacts[0]
    raw = json.loads(path.read_bytes())
    other = replace(p.pair.first, match_id='f' * 32, round_id='e' * 32, first_round_id='e' * 32)
    raw['meta']['runtime_identity'] = other.encode()
    new_path = p.root / 'other-declaration.json'
    payload = json.dumps(raw).encode()
    new_path.write_bytes(payload)
    other_options = {**options, 'generation': 'd' * 32, 'expected_identity': other,
                     'expected_size': len(payload), 'expected_sha256': hashlib.sha256(payload).hexdigest()}
    with new_path.open('rb') as stream:
        second = await retain_gametime_source(p.adapter, stream.fileno(), **other_options)
        assert first.input_id == second.input_id
        observed = await inspect_declared_gametime(p.reader, stream.fileno(), **other_options)
        assert observed.status == 'mapping_pending', observed
    assert (await inspect(p)).status == 'canonical_target_verified'
    assert await p.reader.fetchval('SELECT count(*) FROM lua_correction_inputs') == 1
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_sources') == 2
    print('DEDUP PROOF: 1 timing input, 2 distinct declarations; unmapped sibling never borrows canonical target')
