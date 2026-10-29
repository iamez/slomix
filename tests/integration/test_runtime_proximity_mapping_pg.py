"""Actual declared Lua artifacts, canonical children and independent commit proof."""

import asyncio
import hashlib
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest
from asyncpg import LockNotAvailableError

from bot.runtime_completed_import import import_completed_round
from proximity.parser.parser import ProximityParserV4
from shared import runtime_proximity_mapping as mapping
from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_commit import inspect_proximity_commit
from shared.runtime_proximity_cursor import process_proximity_checkpointed_batch
from shared.runtime_proximity_ingest import import_admitted_proximity_file
from shared.runtime_proximity_queue import process_proximity_once
from shared.runtime_source_reservation import reserve_source_generation
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_full_import_pg import full_import_db as _full_import_db
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_proximity_identity import name
from tests.unit.test_runtime_proximity_identity import run as run_proximity
from tests.unit.test_runtime_stats_dispatch import prepare, reference, setup_pair

full_import_db = _full_import_db
pytestmark = pytest.mark.timeout(120)
DAY = date(2026, 10, 8)


@pytest.mark.parametrize('enabled', [False, True])
async def test_checkpointed_batch_declared_policy_reaches_canonical_import(pipeline, enabled):
    p = pipeline
    before = await snapshot(p.reader)
    result = await process_proximity_checkpointed_batch(
        p.root, source_id=p.bindings[0].source_id, now=1000,
        adapter=p.adapter, observer=p.reader, gametimes_dir=p.root,
        batch_size=2, allow_declared_mapping=enabled,
    )
    assert len(result.items) == 2
    if enabled:
        assert [item.result.action for item in result.items] == ['committed', 'committed']
        assert await p.reader.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 2
        assert await p.reader.fetchval('SELECT count(*) FROM player_track') == 2
        links = await p.reader.fetch(
            'SELECT m.canonical_round_id,f.linked_round_id FROM runtime_proximity_mappings m '
            'JOIN proximity_processed_files f USING(filename) ORDER BY m.canonical_round_id')
        parents = await p.reader.fetch(
            'SELECT canonical_round_id FROM runtime_round_mappings ORDER BY canonical_round_id')
        assert [tuple(row) for row in links] == [(row[0], row[0]) for row in parents]
    else:
        assert [item.result.action for item in result.items] == ['reconcile', 'reconcile']
        assert await snapshot(p.reader) == before
    assert all(path.is_file() for path in p.paths)



@pytest.mark.parametrize("entrypoint", ["worker", "spawned_batch"])
@pytest.mark.parametrize("enabled", [False, True])
async def test_configured_entrypoint_declared_policy_commits_only_when_enabled(
    pipeline, monkeypatch, entrypoint, enabled,
):
    """Actual DEV config, owned native resources and independently visible children."""
    from shared.runtime_proximity_config import ProximityProcessConfig
    from shared.runtime_proximity_isolation import run_bounded_proximity_batch
    from shared.runtime_proximity_worker import RuntimeProximityWorker
    from tests.integration.test_runtime_events_pg import connection_options

    p = pipeline
    options = connection_options()
    env = {
        "BOT_ENVIRONMENT": "dev", "RUNTIME_PROXIMITY_DEV_HANDOVER_CONFIRMED": "true",
        "RUNTIME_PROXIMITY_ROOT": str(p.root), "RUNTIME_PROXIMITY_GAMETIMES_DIR": str(p.root),
        "RUNTIME_PROXIMITY_SOURCE_ID": p.bindings[0].source_id,
        "POSTGRES_HOST": options["host"], "POSTGRES_PORT": str(options.get("port", 5432)),
        "POSTGRES_DATABASE": await p.reader.fetchval("SELECT current_database()"),
        "POSTGRES_USER": await p.reader.fetchval("SELECT current_user"),
        "POSTGRES_PASSWORD": options.get("password", ""),
        "RUNTIME_PROXIMITY_DB_SCHEMA": await p.reader.fetchval("SELECT current_schema()"),
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("RUNTIME_PROXIMITY_DECLARED_MAPPING_ENABLED", raising=False)
    if enabled:
        monkeypatch.setenv("RUNTIME_PROXIMITY_DECLARED_MAPPING_ENABLED", "true")
    config = ProximityProcessConfig.from_environment()
    assert config.allow_declared_mapping is enabled
    before = await snapshot(p.reader)
    if entrypoint == "spawned_batch":
        result = run_bounded_proximity_batch(config, timeout_seconds=30)
        assert result.status == "completed" and result.exit_code == 0, result
    else:
        pool = await mapping_test_pool(config)
        try:
            worker = RuntimeProximityWorker(
                config.root, source_id=config.source_id, gametimes_dir=config.gametimes_dir,
                enabled=True, allow_declared_mapping=config.allow_declared_mapping,
            )
            stop = asyncio.Event()

            async def finish_after_one_batch(_stop, _delay):
                stop.set()

            monkeypatch.setattr(worker, "_wait", finish_after_one_batch)
            await worker.run(config.resource_factory(pool), stop)
            counts = dict(worker.state.last_batch_counts)
            assert counts["committed" if enabled else "reconcile"] == 2
        finally:
            await asyncio.wait_for(pool.close(), 5)
    if enabled:
        tracks = await p.reader.fetch("SELECT round_id FROM player_track ORDER BY round_id")
        parents = await p.reader.fetch("SELECT canonical_round_id FROM runtime_round_mappings ORDER BY canonical_round_id")
        assert [row[0] for row in tracks] == [row[0] for row in parents]
        assert len(tracks) == await p.reader.fetchval("SELECT count(*) FROM runtime_proximity_mappings") == 2
        links = await p.reader.fetch("SELECT linked_round_id FROM proximity_processed_files ORDER BY linked_round_id")
        assert [row[0] for row in links] == [row[0] for row in parents]
    else:
        assert await snapshot(p.reader) == before
    assert all(path.is_file() for path in p.paths)
    print(f"CONFIGURED {entrypoint}: declared_policy={enabled}, exact canonical children={2 if enabled else 0}; sources retained")


async def mapping_test_pool(config):
    import asyncpg

    return await asyncpg.create_pool(**config.pool_options())

def adapter_for(connection):
    @asynccontextmanager
    async def transaction():
        async with connection.transaction():
            yield connection

    async def fetch_one(query, params=()):
        return await connection.fetchrow(pg_query(query), *(params or ()))

    async def fetch_all(query, params=()):
        return await connection.fetch(pg_query(query), *(params or ()))

    async def execute(query, params=()):
        return await connection.execute(pg_query(query), *(params or ()))

    return SimpleNamespace(transaction=transaction, fetch_one=fetch_one, fetch_all=fetch_all, execute=execute)


@pytest.fixture
async def pipeline(full_import_db, tmp_path):
    manager, reader = full_import_db
    authority, spool, pair = setup_pair(tmp_path / 'stats')
    first = run_writer('lua5.4', spool, pair, 1, 'bound-ipc', dispatch=prepare(authority, spool, pair))
    second = run_writer('lua5.4', spool, pair, 2, 'bound-ipc-retry',
                        dispatch=prepare(authority, spool, pair, 2, reference(first)))
    for item, dependency, identity in ((first, None, pair.first), (second, first, pair.second)):
        result = await import_completed_round(manager, item, first=dependency, expected_identity=identity)
        assert result[0], result
    paths, bindings, payloads = [], [], []
    for half, identity in enumerate((pair.first, pair.second), 1):
        generation = str(half + 2) * 32
        directory = reserve_source_generation(tmp_path, generation)
        run_proximity(directory, half, declared=identity)
        path = directory / name(half)
        path.chmod(0o600)
        payload = path.read_bytes()
        binding = mapping.DeclaredProximityBinding(identity.source_id, generation, path.name,
            len(payload), hashlib.sha256(payload).hexdigest(), DAY)
        completion = dict(version=1, filename=path.name, bytes=binding.size, state='writer_closed')
        publish_proximity_admission(directory, source_id=binding.source_id, generation=generation,
            completion=completion, expected_sha256=binding.sha256, session_date=DAY)
        record_proximity_completion_once(directory, completion, expected_sha256=binding.sha256)
        paths.append(path)
        bindings.append(binding)
        payloads.append(payload)
    async with manager.pool.acquire() as writer:
        yield SimpleNamespace(writer=writer, reader=reader, pool=manager.pool, adapter=adapter_for(writer), pair=pair,
                              paths=paths, bindings=bindings, payloads=payloads, root=tmp_path)


async def run(p, half=0, adapter=None):
    binding = p.bindings[half]
    return await import_admitted_proximity_file(p.paths[half].parent,
        source_id=binding.source_id, generation=binding.generation, adapter=adapter or p.adapter,
        gametimes_dir=p.root, allow_declared_mapping=True)


async def observe(p, half=0):
    binding = p.bindings[half]
    return await inspect_proximity_commit(p.paths[half].parent, source_id=binding.source_id,
        generation=binding.generation, observer=p.reader, allow_declared_mapping=True)


async def snapshot(reader):
    tables = (*mapping.ROUND_TABLES, 'player_teamplay_stats', 'crossfire_pairs', 'map_kill_heatmap',
              'map_movement_heatmap', 'proximity_processed_files', 'runtime_proximity_mappings')
    return {table: await reader.fetch(f'SELECT * FROM {table} ORDER BY 1') for table in tables}


async def test_actual_lua_pair_atomic_children_and_independent_visibility(pipeline):
    p = pipeline
    empty = await snapshot(p.reader)
    assert (await observe(p)).status == 'not_committed'
    outer = p.writer.transaction()
    await outer.start()
    try:
        assert (await run(p)).import_result.success
        assert await p.writer.fetchval('SELECT count(*) FROM player_track') == 1
        assert (await observe(p)).status == 'not_committed'
        assert await snapshot(p.reader) == empty
    finally:
        await outer.rollback()
    assert await snapshot(p.reader) == empty
    for half in (0, 1):
        result = await run(p, half)
        assert result.import_result.success, result
        assert (await observe(p, half)).status == 'committed'
        before = await snapshot(p.reader)
        assert (await run(p, half)).import_result.success
        assert await snapshot(p.reader) == before
    tracks = await p.reader.fetch('SELECT round_number,round_id,round_link_source FROM player_track ORDER BY round_number')
    assert len(tracks) == await p.reader.fetchval('SELECT count(*) FROM player_track') == 2
    parents = await p.reader.fetch('SELECT round_number,canonical_round_id FROM runtime_round_mappings ORDER BY round_number')
    assert [tuple(row) for row in tracks] == [(r[0], r[1], 'runtime_round_mapping') for r in parents]
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 2
    print('ACTUAL STATS+PROXIMITY LUA -> CANONICAL PG: 2 linked tracks, atomic proof, '
          'uncommitted invisible, rollback absent, exact replay unchanged; no clock parent lookup')


async def test_direct_parser_requires_binding_and_resets_context(pipeline):
    p = pipeline
    parser = ProximityParserV4(db_adapter=p.adapter, gametimes_dir=str(p.root))
    parser._schema_cache[('player_track', 'round_id')] = False  # noqa: SLF001 -- stale negative schema proof
    assert await parser.import_file(str(p.paths[0]), DAY, source_bytes=p.payloads[0], declared_binding=p.bindings[0])
    expected = await p.reader.fetchval('SELECT canonical_round_id FROM runtime_round_mappings WHERE round_number=1')
    assert await p.reader.fetchval('SELECT round_id FROM player_track') == expected
    before = await snapshot(p.reader)
    assert not await parser.import_file(str(p.paths[1]), DAY, source_bytes=p.payloads[1])
    assert parser._round_link_context['round_id'] is None  # noqa: SLF001 -- explicit reuse guard proof
    assert await snapshot(p.reader) == before
    assert not await parser.import_file(str(p.paths[1]), DAY, source_bytes=p.payloads[1],
                                        declared_binding=replace(p.bindings[1], source_id='wrong'))
    assert await snapshot(p.reader) == before


async def test_queue_opt_in_imports_and_observes_independent_commit(pipeline):
    p = pipeline
    binding = p.bindings[0]
    options = dict(source_id=binding.source_id, generation=binding.generation, adapter=p.adapter,
                   observer=p.reader, gametimes_dir=p.root, allow_declared_mapping=True)
    result = await process_proximity_once(p.paths[0].parent, now=1000, **options)
    assert result.action == 'committed', result
    before = await snapshot(p.reader)
    assert len(before['player_track']) == len(before['runtime_proximity_mappings']) == 1
    replay = await process_proximity_once(p.paths[0].parent, now=1001, **options)
    assert replay.action == 'committed'
    assert await snapshot(p.reader) == before


async def test_nonempty_lua_aggregates_rollback_commit_and_exact_replay(pipeline):
    p = pipeline
    directory = reserve_source_generation(p.root, '5' * 32)
    run_proximity(directory, declared=p.pair.first, scenario='aggregates')
    path = directory / name()
    path.chmod(0o600)
    payload = path.read_bytes()
    binding = replace(p.bindings[0], generation=directory.name, size=len(payload),
                      sha256=hashlib.sha256(payload).hexdigest())
    completion = dict(version=1, filename=path.name, bytes=len(payload), state='writer_closed')
    publish_proximity_admission(directory, source_id=binding.source_id, generation=binding.generation,
        completion=completion, expected_sha256=binding.sha256, session_date=DAY)
    record_proximity_completion_once(directory, completion, expected_sha256=binding.sha256)
    p.paths[0], p.bindings[0], p.payloads[0] = path, binding, payload
    empty = await snapshot(p.reader)
    outer = p.writer.transaction()
    await outer.start()
    try:
        assert (await run(p)).import_result.success
        assert await p.writer.fetchval('SELECT sum(total_kills) FROM map_kill_heatmap') == 5
        assert await p.writer.fetchval('SELECT sum(traversal_count) FROM map_movement_heatmap') == 7
        assert await snapshot(p.reader) == empty
    finally:
        await outer.rollback()
    assert await snapshot(p.reader) == empty
    assert (await run(p)).import_result.success
    rows = await p.reader.fetch('SELECT axis_kills,allies_kills,total_kills FROM map_kill_heatmap')
    assert [tuple(row) for row in rows] == [(3, 2, 5)]
    assert sum(row[0] + row[1] for row in rows) == await p.reader.fetchval('SELECT sum(total_kills) FROM map_kill_heatmap')
    assert tuple(await p.reader.fetchrow('SELECT traversal_count,combat_count,escape_count FROM map_movement_heatmap')) == (7, 4, 1)
    before = await snapshot(p.reader)
    assert (await run(p)).import_result.success
    assert await snapshot(p.reader) == before
    assert (await observe(p)).status == 'committed'
    print('NONEMPTY LUA AGGREGATES -> PG: kills=5, traversal=7; rollback empty, replay unchanged')


async def test_no_legacy_receipt_adoption_even_unfinished(pipeline):
    p = pipeline
    parent = await p.reader.fetchval('SELECT canonical_round_id FROM runtime_round_mappings WHERE round_number=1')
    for flag in (True, False, None):
        outer = p.writer.transaction()
        await outer.start()
        try:
            await p.writer.execute('INSERT INTO proximity_processed_files '
                '(filename,file_hash,runtime_parent_gate,aggregates_applied,linked_round_id) VALUES ($1,$2,TRUE,$3,$4)',
                p.bindings[0].filename, p.bindings[0].sha256, flag, parent if flag is True else None)
            before = await snapshot(p.writer)
            assert not (await run(p)).import_result.success
            assert await snapshot(p.writer) == before
        finally:
            await outer.rollback()


async def test_existing_legacy_children_are_not_skipped_or_reassigned(pipeline):
    p = pipeline
    raw = p.payloads[0].replace(('# runtime_identity=' + p.pair.first.encode() + '\n').encode(), b'')
    parser = ProximityParserV4(db_adapter=p.adapter, gametimes_dir=str(p.root))
    old_name = str(p.paths[0]).replace('120000-', '115959-')
    assert await parser.import_file(old_name, DAY, source_bytes=raw)
    assert await p.reader.fetchval('SELECT count(*) FROM player_track') == 1
    before = await snapshot(p.reader)
    assert not (await run(p)).import_result.success
    assert await snapshot(p.reader) == before


@pytest.mark.parametrize('cancel', [False, True])
@pytest.mark.parametrize('after_proof', [False, True])
async def test_failure_after_children_rolls_back_everything(pipeline, monkeypatch, cancel, after_proof):
    p = pipeline
    before = await snapshot(p.reader)
    target = 'validate_declared_receipt' if after_proof else 'record_receipt_parent'
    original = getattr(mapping, target)
    reached = []

    async def fail(*args):
        await original(*args)
        assert await p.writer.fetchval('SELECT count(*) FROM player_track') == 1
        assert await p.writer.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == int(after_proof)
        reached.append(True)
        if cancel:
            raise asyncio.CancelledError()
        raise RuntimeError('fixture failure after children and receipt/proof write')

    monkeypatch.setattr(mapping, target, fail)
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await run(p)
    else:
        assert not (await run(p)).import_result.success
    assert reached == [True]
    assert await snapshot(p.reader) == before
    assert (await observe(p)).status == 'not_committed'


@pytest.mark.parametrize('missing_parent', [False, True])
async def test_mapping_pending_hold_survives_policy_and_parent_arrival(pipeline, missing_parent):
    p = pipeline
    binding = p.bindings[0]
    options = dict(source_id=binding.source_id, generation=binding.generation, adapter=p.adapter,
                   observer=p.reader, gametimes_dir=p.root)
    # Both default-off refusal and genuinely absent mapping remain sticky after
    # enablement/parent arrival. The temporary deletion affects this fixture only.
    outer = p.writer.transaction()
    await outer.start()
    try:
        if missing_parent:
            await p.writer.execute('DELETE FROM runtime_round_mappings')
        first = await process_proximity_once(p.paths[0].parent, now=1000, **options,
                                             allow_declared_mapping=missing_parent)
    finally:
        await outer.rollback()
    assert first.reason == 'declared_identity_mapping_pending'
    second = await process_proximity_once(p.paths[0].parent, now=9999, **options, allow_declared_mapping=True)
    assert second == first
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 0


async def test_observer_rejects_changed_event_and_proof(pipeline):
    p = pipeline
    assert (await run(p)).import_result.success
    assert (await observe(p)).status == 'committed'
    async with p.writer.transaction():
        await p.writer.execute('UPDATE runtime_events SET validation_passed=FALSE WHERE round_number=1')
        # Use same writer only to simulate a COMMITTED subsequent metadata change
        # below; observer must still see the previous committed consistent state.
        assert (await observe(p)).status == 'committed'
    assert (await observe(p)).status == 'conflict'


async def test_default_observer_and_queue_never_adopt_declared_legacy_receipt(pipeline):
    p = pipeline
    binding = p.bindings[0]
    parent = await p.reader.fetchval('SELECT canonical_round_id FROM runtime_round_mappings WHERE round_number=1')
    await p.writer.execute('INSERT INTO proximity_processed_files '
        '(filename,file_hash,runtime_parent_gate,aggregates_applied,linked_round_id) VALUES ($1,$2,TRUE,TRUE,$3)',
        binding.filename, binding.sha256, parent)
    options = dict(source_id=binding.source_id, generation=binding.generation, observer=p.reader)
    before = await snapshot(p.reader)
    observed = await inspect_proximity_commit(p.paths[0].parent, **options)
    assert observed.status == 'conflict' and observed.reason == 'declared_identity_mapping_pending'
    queued = await process_proximity_once(p.paths[0].parent, now=1000, **options,
                                          adapter=p.adapter, gametimes_dir=p.root)
    assert queued.action == 'reconcile'
    assert (await observe(p)).status == 'conflict'
    assert await snapshot(p.reader) == before


async def test_065_collision_on_other_date_preserves_old_parent(pipeline):
    p = pipeline
    parser = ProximityParserV4(gametimes_dir=str(p.root))
    assert parser.parse_file(str(p.paths[0]), source_bytes=p.payloads[0])
    start = parser.metadata['round_start_unix']
    other = await p.reader.fetchval('SELECT canonical_round_id FROM runtime_round_mappings WHERE round_number=2')
    await p.writer.execute('INSERT INTO proximity_weapon_accuracy '
        '(round_id,map_name,player_guid,weapon_id,round_number,round_start_unix,session_date) '
        "VALUES ($1,'supply','fixture-player',1,1,$2,'2026-10-01')", other, start)
    before = await snapshot(p.reader)
    assert not (await run(p)).import_result.success
    assert await snapshot(p.reader) == before
    assert await p.reader.fetchval('SELECT round_id FROM proximity_weapon_accuracy') == other


async def test_concurrent_exact_import_and_parent_lock_lifetime(pipeline):
    p = pipeline
    outer = p.writer.transaction()
    await outer.start()
    committed = False
    task = None
    try:
        assert (await run(p)).import_result.success
        async with p.pool.acquire() as second_writer:
            task = asyncio.create_task(run(p, adapter=adapter_for(second_writer)))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), .15)
            assert (await observe(p)).status == 'not_committed'
            with pytest.raises(LockNotAvailableError):
                async with p.reader.transaction():
                    await p.reader.execute("SET LOCAL lock_timeout='100ms'")
                    await p.reader.execute("UPDATE rounds SET map_name='changed' WHERE round_number=1")
            await outer.commit()
            committed = True
            assert (await asyncio.wait_for(task, 5)).import_result.success
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if not committed:
            await outer.rollback()
    assert await p.reader.fetchval('SELECT count(*) FROM player_track') == 1
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_proximity_mappings') == 1
    assert (await observe(p)).status == 'committed'
