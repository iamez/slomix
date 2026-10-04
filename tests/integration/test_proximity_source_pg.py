"""Verified runtime bytes and receipt digest commit or roll back together."""
# ruff: noqa: SLF001 -- inject canonical parser linkage faults before commit

import asyncio
import hashlib
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from asyncpg import LockNotAvailableError, UndefinedColumnError

from proximity.parser import ProximityParserV4
from shared import proximity_import
from shared.runtime_spool import publish_proximity_file
from tests.integration.proximity_adapter_helpers import pg_query
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


@pytest.fixture
async def source_import(journal_db, monkeypatch, tmp_path):  # noqa: F811
    writer, observer = journal_db
    await writer.execute('CREATE TABLE proof_data (id INTEGER PRIMARY KEY, applied INTEGER NOT NULL)')
    await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN, file_hash TEXT)')
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    payload = b'# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n'
    digest = hashlib.sha256(payload).hexdigest()
    publish_proximity_file(tmp_path, source.name, [payload],
                           expected_size=len(payload), expected_sha256=digest)
    controls = {'failure': None, 'replace_path': False}
    seen = []

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield writer

    async def execute(query, params=None):
        return await writer.execute(pg_query(query), *(params or ()))

    async def fetch_one(query, params=None):
        return await writer.fetchrow(pg_query(query), *(params or ()))

    adapter = SimpleNamespace(transaction=transaction, execute=execute, fetch_one=fetch_one)

    def factory(**kwargs):
        # The boundary has already captured verified bytes. This path mutation
        # must not change the bytes parsed or their recorded digest.
        if controls['replace_path']:
            source.write_bytes(b'# map=changed\n# round=1\n')
        parser = ProximityParserV4(**kwargs)
        monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
        monkeypatch.setattr(parser, '_table_has_column', AsyncMock(side_effect=lambda t, c: c == 'filename'))

        async def engagement(day):
            seen.append(parser.metadata['map_name'])
            assert await writer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
            if controls['failure'] == 'cancel':
                raise asyncio.CancelledError()
            if controls['failure'] == 'python':
                raise RuntimeError('injected canonical import failure after digest binding')

        async def aggregate():
            await writer.execute('INSERT INTO proof_data VALUES (1,1) ON CONFLICT (id) DO UPDATE SET applied=proof_data.applied+1')

        monkeypatch.setattr(parser, '_import_engagements', engagement)
        monkeypatch.setattr(parser, '_update_player_stats', aggregate)
        for method in ('_update_crossfire_pairs', '_import_heatmaps'):
            monkeypatch.setattr(parser, method, AsyncMock())
        return parser

    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)
    async def run(expected_payload=payload):
        return await proximity_import.import_proximity_file(
            source, adapter=adapter, session_date=date(2026, 10, 4), gametimes_dir=tmp_path,
            expected_size=len(expected_payload), expected_sha256=hashlib.sha256(expected_payload).hexdigest(),
        )
    return writer, observer, source, payload, digest, controls, seen, run


async def test_verified_repeat_and_different_content_conflict(source_import):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    for _ in range(2):
        assert (await run()).success
        assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_data')] == [(1, 1)]
        assert tuple(await observer.fetchrow('SELECT * FROM proximity_processed_files')) == (source.name, True, digest)
    changed = payload.replace(b'fixture', b'changed')
    source.write_bytes(changed)
    with pytest.raises(ValueError, match='conflicts with recorded'):
        await run(changed)
    assert seen == ['fixture', 'fixture']
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1


@pytest.mark.parametrize('flag', [True, False, None])
async def test_unverified_existing_receipt_not_adopted(source_import, flag):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    await writer.execute('INSERT INTO proximity_processed_files VALUES ($1,$2,NULL)', source.name, flag)
    with pytest.raises(ValueError, match='unverified source identity'):
        await run()
    assert seen == []
    assert tuple(await observer.fetchrow('SELECT * FROM proximity_processed_files')) == (source.name, flag, None)
    assert await observer.fetchval('SELECT count(*) FROM proof_data') == 0


@pytest.mark.parametrize('failure', ['python', 'cancel'])
async def test_failed_import_rolls_back_digest_and_claim(source_import, failure):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    controls['failure'] = failure
    if failure == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await run()
    else:
        result = await run()
        assert not result.success and result.parsed_stats is None
    assert seen == ['fixture']
    for table in ('proof_data', 'proximity_processed_files'):
        assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
        assert await observer.fetch(f'SELECT * FROM {table}') == []
    controls['failure'] = None
    assert (await run()).success
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest


async def test_runtime_parses_captured_bytes_not_reopened_path(source_import):
    writer, observer, source, payload, digest, controls, seen, run = source_import
    controls['replace_path'] = True
    assert (await run()).success
    assert source.read_bytes() != payload
    assert seen == ['fixture']
    assert await observer.fetchval('SELECT file_hash FROM proximity_processed_files') == digest
    assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1


@pytest.fixture
async def linked_import(journal_db, monkeypatch, tmp_path):  # noqa: F811
    """Real parser identity and receipt flow; minimal child replaces wide schema."""
    writer, observer = journal_db
    await writer.execute('ALTER TABLE rounds ADD COLUMN map_name TEXT, ADD COLUMN round_start_unix BIGINT')
    await writer.execute('ALTER TABLE rounds ADD COLUMN round_date TEXT, ADD COLUMN round_time TEXT, ADD COLUMN created_at TIMESTAMP, ADD COLUMN round_canonical_id TEXT')
    await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN, file_hash TEXT)')
    await writer.execute('CREATE TABLE proof_child (id INTEGER PRIMARY KEY, round_id INTEGER REFERENCES rounds(id))')
    payload = b'# map=fixture\n# round=1\n# round_start_unix=1789794600\n# round_end_unix=1789795200\n'
    digest = hashlib.sha256(payload).hexdigest()
    source = publish_proximity_file(tmp_path, '2026-09-19-051000-fixture-round-1_engagements.txt',
        [payload], expected_size=len(payload), expected_sha256=digest)
    controls = {'failure': None, 'context_override': False}
    entered, release = asyncio.Event(), asyncio.Event()

    @asynccontextmanager
    async def transaction():
        async with writer.transaction():
            yield

    async def execute(query, params=None):
        return await writer.execute(pg_query(query), *(params or ()))

    async def fetch_one(query, params=None):
        return await writer.fetchrow(pg_query(query), *(params or ()))

    async def fetch_all(query, params=None):
        return await writer.fetch(pg_query(query), *(params or ()))

    adapter = SimpleNamespace(transaction=transaction, execute=execute,
                              fetch_one=fetch_one, fetch_all=fetch_all)

    def factory(**kwargs):
        parser = ProximityParserV4(**kwargs)
        monkeypatch.setattr(parser, '_table_has_column', AsyncMock(side_effect=lambda t, c: c == 'filename'))

        async def child(day):
            if controls['context_override']:
                parser._round_link_context['round_id'] = None
            await writer.execute('INSERT INTO proof_child VALUES (1,$1) ON CONFLICT DO NOTHING',
                                 parser._round_link_context['round_id'])
            if controls['failure'] == 'cancel':
                raise asyncio.CancelledError()
            if controls['failure'] == 'duplicate':
                await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (11,1,21,'fixture',1789794600)")
            if controls['failure'] == 'pause':
                entered.set()
                await release.wait()

        monkeypatch.setattr(parser, '_import_engagements', child)
        for method in ('_update_player_stats', '_update_crossfire_pairs', '_import_heatmaps'):
            monkeypatch.setattr(parser, method, AsyncMock())
        return parser

    monkeypatch.setattr(proximity_import, 'ProximityParserV4', factory)

    async def run():
        return await proximity_import.import_proximity_file(
            source, adapter=adapter, session_date=date(2026, 9, 19), gametimes_dir=tmp_path,
            expected_size=len(payload), expected_sha256=digest, require_linked_parent=True,
        )

    return writer, observer, controls, entered, release, run


async def assert_no_linked_import(observer):
    for table in ('proof_child', 'proximity_processed_files'):
        assert await observer.fetchval(f'SELECT count(*) FROM {table}') == 0
        assert await observer.fetch(f'SELECT * FROM {table}') == []


async def test_late_parent_then_session_then_retry(linked_import):
    writer, observer, controls, entered, release, run = linked_import
    result = await run()
    assert not result.success and result.pending_reason == 'parent_missing'
    assert result.parsed_stats is None and result.round_id is None
    await assert_no_linked_import(observer)
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,NULL,'fixture',1789794600)")
    result = await run()
    assert not result.success and result.pending_reason == 'session_missing'
    await assert_no_linked_import(observer)
    await writer.execute('UPDATE rounds SET gaming_session_id=20 WHERE id=10')
    for _ in range(2):
        result = await run()
        assert result.success and result.pending_reason is None
        assert (result.round_id, result.gaming_session_id) == (10, 20)
        assert await observer.fetchval('SELECT count(*) FROM proof_child') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_child')] == [(1, 10)]
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
        assert await observer.fetchval('SELECT aggregates_applied FROM proximity_processed_files') is True


@pytest.mark.parametrize('during_import', [False, True])
async def test_strict_duplicate_identity_rolls_back(linked_import, during_import):
    writer, observer, controls, entered, release, run = linked_import
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    if during_import:
        controls['failure'] = 'duplicate'
    else:
        await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (11,1,21,'fixture',1789794600)")
    result = await run()
    assert not result.success and result.pending_reason == 'parent_ambiguous'
    await assert_no_linked_import(observer)
    assert await observer.fetchval('SELECT count(*) FROM rounds') == (1 if during_import else 2)


@pytest.mark.parametrize('failure', ['cancel', 'wrong_context'])
async def test_strict_failure_after_child_write_is_atomic(linked_import, failure):
    writer, observer, controls, entered, release, run = linked_import
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    if failure == 'cancel':
        controls['failure'] = failure
        with pytest.raises(asyncio.CancelledError):
            await run()
    else:
        controls['context_override'] = True
        with pytest.raises(RuntimeError, match='identity changed'):
            await run()
    await assert_no_linked_import(observer)


async def test_strict_parent_is_locked_through_import(linked_import):
    writer, observer, controls, entered, release, run = linked_import
    await writer.execute("INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix) VALUES (10,1,20,'fixture',1789794600)")
    controls['failure'] = 'pause'
    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await assert_no_linked_import(observer)
        await observer.execute("SET lock_timeout='100ms'")
        with pytest.raises(LockNotAvailableError, match='lock timeout'):
            await observer.execute('UPDATE rounds SET gaming_session_id=21 WHERE id=10')
        release.set()
        assert (await asyncio.wait_for(task, 5)).success
        assert await observer.fetchval('SELECT gaming_session_id FROM rounds WHERE id=10') == 20
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_strict_identity_ignores_date_but_not_map_round_or_clock(linked_import):
    writer, observer, controls, entered, release, run = linked_import
    await writer.execute("""
        INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix)
        VALUES (10,2,20,'fixture',1789794600), (11,1,21,'different',1789794600),
               (12,1,22,'fixture',1789795200)
    """)
    assert (await run()).pending_reason == 'parent_missing'
    await assert_no_linked_import(observer)
    # Physical identity survives midnight/date labels; it does not select a
    # different round merely because its START equals the source END.
    await writer.execute("""
        INSERT INTO rounds (id,round_number,gaming_session_id,map_name,round_start_unix,round_date)
        VALUES (13,1,23,'fixture',1789794600,'2026-09-20')
    """)
    result = await run()
    assert result.success and (result.round_id, result.gaming_session_id) == (13, 23)
    assert await observer.fetchval('SELECT round_id FROM proof_child') == 13


async def test_parent_query_failure_rolls_back_receipt_reservation(linked_import):
    writer, observer, controls, entered, release, run = linked_import
    await writer.execute('ALTER TABLE rounds RENAME COLUMN gaming_session_id TO unavailable_session_id')
    with pytest.raises(UndefinedColumnError):
        await run()
    await assert_no_linked_import(observer)
