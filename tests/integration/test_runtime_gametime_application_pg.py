"""Actual Lua pair -> isolated PostgreSQL atomic timing fill, never live services."""

import asyncio
import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from bot.runtime_gametime_application import apply_declared_gametime, inspect_declared_gametime_application
from bot.runtime_gametime_preview import TIMING_FILL_FIELDS
from shared.runtime_cache_consumer import consume_http_cache_events
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_gametime_correlation_pg import (
    full_import_db as _full_import_db,
)
from tests.integration.test_runtime_gametime_correlation_pg import pipeline as _pipeline
from tests.integration.test_runtime_gametime_correlation_pg import retain, snapshot
from tests.integration.test_runtime_gametime_link_pg import link

full_import_db = _full_import_db
pipeline = _pipeline
pytestmark = pytest.mark.timeout(120)


async def apply(p, half=0, adapter=None):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        stream.seek(3)
        try:
            return await apply_declared_gametime(adapter or p.adapter, stream.fileno(), **options)
        finally:
            assert stream.tell() == 3


async def observe(p, half=0, observer=None):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        return await inspect_declared_gametime_application(observer or p.reader, stream.fileno(), **options)


async def all_state(connection):
    values = await snapshot(connection)
    for table in ('runtime_gametime_links', 'runtime_gametime_applications'):
        values[table] = await connection.fetch(f'SELECT * FROM {table} ORDER BY generation')
    return values


async def ready(p, half=0):
    await retain(p, half)
    assert (await link(p, half)).status == 'linked'


async def test_actual_pair_atomic_visibility_replay_and_exact_write_scope(pipeline, monkeypatch):
    p = pipeline
    assert (await apply(p)).status == 'missing_retention'
    await retain(p)
    assert (await apply(p)).status == 'not_linked'
    assert (await link(p)).status == 'linked'
    await ready(p, 1)
    initial = await all_state(p.reader)
    for isolation in ('repeatable_read', 'serializable'):
        async with p.writer.transaction(isolation=isolation):
            with pytest.raises(ValueError, match='read committed'):
                await apply(p)
    assert await all_state(p.reader) == initial
    preimages = {row['id']: json.loads(row['snapshot']) for row in await p.reader.fetch(
        'SELECT id,to_jsonb(r) AS snapshot FROM rounds r')}
    outer = p.writer.transaction()
    await outer.start()
    try:
        result = await apply(p)
        assert result.status == 'applied', result
        assert await p.writer.fetchval('SELECT count(*) FROM runtime_gametime_applications') == 1
        assert (await observe(p)).status == 'not_applied'
        with pytest.raises(RuntimeError, match='outside any transaction'):
            await observe(p, observer=p.writer)
    finally:
        await outer.rollback()
    assert await all_state(p.reader) == initial
    for half in (0, 1):
        result = await apply(p, half)
        assert result.status == 'applied', result
        observed = await observe(p, half)
        assert (observed.status, observed.round_id, observed.event_id) == ('applied', result.round_id, result.event_id)
        stable = await all_state(p.reader)
        assert (await apply(p, half)).status == 'already_applied'
        assert await all_state(p.reader) == stable
    final = await all_state(p.reader)
    for table in initial:
        if table not in ('rounds', 'runtime_events', 'runtime_gametime_applications'):
            assert final[table] == initial[table], table
    original_rows = {row['id']: dict(row) for row in initial['rounds']}
    for row in final['rounds']:
        original = original_rows[row['id']]
        if row['round_number'] in (1, 2):
            assert tuple(row[key] for key in TIMING_FILL_FIELDS) == (600, 10, 1)
            assert row['actual_duration_seconds'] == 610 - row['total_pause_seconds']
            original.update(dict(zip(TIMING_FILL_FIELDS, (600, 10, 1), strict=True)))
        assert dict(row) == original
    receipts = final['runtime_gametime_applications']
    assert len(receipts) == await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_applications') == 2
    for row in receipts:
        assert json.loads(row['before_round']) == preimages[row['canonical_round_id']]
    assert len(final['runtime_events']) == len(initial['runtime_events']) + 2
    assert final['runtime_events'][:len(initial['runtime_events'])] == initial['runtime_events']
    monkeypatch.setenv('EVENT_STREAM_ENABLED', 'true')
    monkeypatch.setenv('RUNTIME_HTTP_CACHE_EVENTS_ENABLED', 'true')
    consumed = await consume_http_cache_events(p.reader)
    assert consumed.processed == len(final['runtime_events'])
    assert consumed.unsupported_pending == 0
    assert (await consume_http_cache_events(p.reader)).processed == 0
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_consumer_receipts WHERE '
        "consumer_name='http-cache-generation-v1' AND event_id IN "
        '(SELECT event_id FROM runtime_gametime_applications)') == 2
    print('ACTUAL LUA R1/R2 -> PG102: exactly 3 timing columns per half, two receipts/events; '
          'preimages exact; initial stats/player rows/clock keys/provenance unchanged; '
          'uncommitted invisible, rollback exact, replay no writes; existing cache consumer consumes once')


@pytest.mark.parametrize('point,cancel', [('update', False), ('update', True),
                                        ('receipt', False), ('receipt', True), ('notify', False)])
async def test_post_write_failure_or_cancellation_is_atomic(pipeline, monkeypatch, point, cancel):
    p = pipeline
    await ready(p)
    initial = await all_state(p.reader)
    transaction = p.adapter.transaction
    reached = []

    @asynccontextmanager
    async def injected():
        async with transaction() as connection:
            async def execute(query, *args):
                value = await connection.execute(query, *args)
                matches = ((point == 'update' and query.startswith('UPDATE rounds SET actual_duration'))
                    or (point == 'receipt' and query.startswith('INSERT INTO runtime_gametime_applications'))
                    or (point == 'notify' and 'pg_notify' in query))
                if matches:
                    assert await connection.fetchval('SELECT actual_duration_seconds FROM rounds WHERE round_number=1') == 600
                    if point != 'update':
                        assert await connection.fetchval('SELECT count(*) FROM runtime_gametime_applications') == 1
                    reached.append(point)
                    if cancel:
                        raise asyncio.CancelledError()
                    raise RuntimeError('fixture failure after ' + point)
                return value
            yield SimpleNamespace(fetchrow=connection.fetchrow, fetchval=connection.fetchval, execute=execute)

    monkeypatch.setattr(p.adapter, 'transaction', injected)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await apply(p)
    assert reached == [point]
    assert await all_state(p.reader) == initial
    assert (await observe(p)).status == 'not_applied'


@pytest.mark.parametrize('commit', [False, True])
async def test_concurrent_application_rechecks_after_first_outcome(pipeline, full_import_db, commit):
    p = pipeline
    await ready(p)
    manager, _ = full_import_db
    async with manager.pool.acquire() as other:
        outer = p.writer.transaction()
        await outer.start()
        task = None
        try:
            assert (await apply(p)).status == 'applied'
            task = asyncio.create_task(apply(p, adapter=adapter_for(other)))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), .1)
            assert (await observe(p)).status == 'not_applied'
        finally:
            if commit:
                await outer.commit()
            else:
                await outer.rollback()
        try:
            result = await asyncio.wait_for(task, 5)
            assert result.status == ('already_applied' if commit else 'applied')
        finally:
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert (await observe(p)).status == 'applied'
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_applications') == 1


async def test_existing_values_legacy_and_corrupted_evidence_are_not_adopted(pipeline):
    p = pipeline
    await ready(p)
    rid = await p.reader.fetchval('SELECT id FROM rounds WHERE round_number=1')
    before = await p.reader.fetchrow('SELECT actual_duration_seconds,total_pause_seconds,pause_count FROM rounds WHERE id=$1', rid)
    await p.writer.execute('UPDATE rounds SET actual_duration_seconds=600,total_pause_seconds=10,pause_count=1 WHERE id=$1', rid)
    stable = await all_state(p.reader)
    assert (await apply(p)).status == 'existing_values_unproven'
    assert (await observe(p)).status == 'not_applied'
    assert await all_state(p.reader) == stable
    await p.writer.execute('UPDATE rounds SET actual_duration_seconds=$1,total_pause_seconds=$2,pause_count=$3 WHERE id=$4', *before, rid)
    input_id = await p.reader.fetchval('SELECT input_id FROM runtime_gametime_links')
    await p.writer.execute('INSERT INTO lua_correction_receipts(input_id,round_id) VALUES ($1,$2)', input_id, rid)
    assert (await apply(p)).reason == 'legacy_correction_receipt_present'
    assert (await observe(p)).reason == 'legacy_correction_receipt_present'
    await p.writer.execute('DELETE FROM lua_correction_receipts WHERE input_id=$1', input_id)
    legacy_event = await p.writer.fetchval("INSERT INTO runtime_events "
        "(event_type,schema_version,round_id,round_number,event_details) "
        "VALUES ('round_lua_corrected',1,$1,1,'{}') RETURNING id", rid)
    assert (await apply(p)).reason == 'unreceipted_timing_event_present'
    assert (await observe(p)).reason == 'unreceipted_timing_event_present'
    await p.writer.execute('DELETE FROM runtime_events WHERE id=$1', legacy_event)
    result = await apply(p)
    assert result.status == 'applied'
    cases = [
        ('UPDATE rounds SET actual_duration_seconds=601 WHERE id=$1', (rid,),
         'UPDATE rounds SET actual_duration_seconds=600 WHERE id=$1', (rid,)),
        ("UPDATE runtime_gametime_applications SET link_snapshot=jsonb_set(link_snapshot,'{source_sha256}', '\"bad\"')", (),
         'UPDATE runtime_gametime_applications SET link_snapshot=$1::jsonb', None),
        ("UPDATE runtime_events SET event_details='{}' WHERE id=$1", (result.event_id,),
         'UPDATE runtime_events SET event_details=$1::jsonb WHERE id=$2', None),
        ("UPDATE runtime_gametime_applications SET before_round=jsonb_set(before_round,'{actual_time}', '\"corrupt\"')", (),
         'UPDATE runtime_gametime_applications SET before_round=$1::jsonb', None),
    ]
    receipt = await p.reader.fetchrow('SELECT * FROM runtime_gametime_applications')
    details = await p.reader.fetchval('SELECT event_details FROM runtime_events WHERE id=$1', result.event_id)
    stable = await all_state(p.reader)
    for index, (damage, args, restore, restore_args) in enumerate(cases):
        await p.writer.execute(damage, *args)
        damaged = await all_state(p.reader)
        assert (await apply(p)).status == 'conflict'
        assert (await observe(p)).status == 'conflict'
        assert await all_state(p.reader) == damaged
        if restore_args is None:
            restore_args = {1: (receipt['link_snapshot'],), 2: (details, result.event_id),
                            3: (receipt['before_round'],)}[index]
        await p.writer.execute(restore, *restore_args)
        assert await all_state(p.reader) == stable
        assert (await observe(p)).status == 'applied'


async def test_observer_snapshot_is_not_mixed_with_concurrent_event_edit(pipeline):
    p = pipeline
    await ready(p)
    result = await apply(p)
    assert result.status == 'applied'
    original = await p.reader.fetchval('SELECT event_details FROM runtime_events WHERE id=$1', result.event_id)
    phases = []

    async def fetchrow(query, *args):
        row = await p.reader.fetchrow(query, *args)
        if 'FROM runtime_gametime_sources ' in query:
            assert await p.reader.fetchval('SHOW transaction_read_only') == 'on'
            phases.append('source_snapshot')
            await p.writer.execute("UPDATE runtime_events SET event_details='{}' WHERE id=$1", result.event_id)
            phases.append('concurrent_edit_committed')
        return row

    proxy = SimpleNamespace(is_in_transaction=p.reader.is_in_transaction,
                            transaction=p.reader.transaction, fetchrow=fetchrow, fetchval=p.reader.fetchval)
    assert (await observe(p, observer=proxy)).status == 'applied'
    assert phases == ['source_snapshot', 'concurrent_edit_committed']
    assert (await observe(p)).reason == 'application_event_conflict'
    await p.writer.execute('UPDATE runtime_events SET event_details=$1::jsonb WHERE id=$2', original, result.event_id)
    assert (await observe(p)).status == 'applied'
