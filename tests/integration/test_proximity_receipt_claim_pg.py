"""Independent importers must own a receipt before reading its aggregate flag."""

import asyncio
from contextlib import asynccontextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import pytest

from proximity.parser import ProximityParserV4
from proximity.parser.import_receipt import claim_import_receipt
from tests.integration.test_runtime_events_pg import connection_options, journal_db  # noqa: F401


@pytest.mark.parametrize('outcome', ['commit', 'rollback', 'cancel', 'timeout'])
async def test_same_file_waits_then_rechecks_receipt(journal_db, monkeypatch, tmp_path, outcome):  # noqa: F811
    first, observer = journal_db
    await first.execute('CREATE TABLE proof_data (id INTEGER PRIMARY KEY, applied INTEGER NOT NULL)')
    await first.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    second = await asyncpg.connect(**connection_options())
    await second.execute('SET search_path TO ' + await first.fetchval('SHOW search_path'))
    first_pid = await first.fetchval('SELECT pg_backend_pid()')
    second_pid = await second.fetchval('SELECT pg_backend_pid()')
    entered = asyncio.Event()
    release = asyncio.Event()
    second_started = asyncio.Event()
    reads = [[], []]
    tasks = []
    source = tmp_path / '2026-10-04-120000-fixture-round-1_engagements.txt'
    source.write_text('# PROXIMITY_TRACKER_V4\n# map=fixture\n# round=1\n')

    def make_parser(conn, index):
        @asynccontextmanager
        async def transaction():
            async with conn.transaction():
                if index:
                    second_started.set()
                yield conn

        async def fetch_one(query, params):
            row = await conn.fetchrow(query, *params)
            reads[index].append(None if row is None else row[0])
            return row

        async def execute(query, params=None):
            return await conn.execute(query, *(params or ()))

        async def engagement(day):
            if index == 0 and not release.is_set():
                entered.set()
                await release.wait()
                if outcome == 'rollback':
                    raise RuntimeError('injected first importer failure')

        async def aggregate():
            await conn.execute('INSERT INTO proof_data VALUES (1,1) ON CONFLICT (id) DO UPDATE SET applied=proof_data.applied+1')

        parser = ProximityParserV4(db_adapter=SimpleNamespace(transaction=transaction, fetch_one=fetch_one, execute=execute))
        monkeypatch.setattr(parser, '_resolve_round_link_context', AsyncMock())
        monkeypatch.setattr(parser, '_table_has_column', AsyncMock(side_effect=lambda t, c: c == 'filename'))
        monkeypatch.setattr(parser, '_import_engagements', engagement)
        monkeypatch.setattr(parser, '_update_player_stats', aggregate)
        for name in ('_update_crossfire_pairs', '_import_heatmaps'):
            monkeypatch.setattr(parser, name, AsyncMock())
        return parser

    first_parser, second_parser = make_parser(first, 0), make_parser(second, 1)
    async def run(parser):
        return await parser.import_file(str(source), date(2026, 10, 4))

    try:
        tasks.append(asyncio.create_task(run(first_parser)))
        await asyncio.wait_for(entered.wait(), 3)
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
        assert await observer.fetch('SELECT * FROM proof_data') == []
        tasks.append(asyncio.create_task(run(second_parser)))
        await asyncio.wait_for(second_started.wait(), 3)

        async def wait_for_claim():
            while not reads[1]:
                blockers = await observer.fetchval('SELECT pg_blocking_pids($1)', second_pid)
                if first_pid in blockers:
                    return
                if tasks[1].done():
                    break
                await asyncio.sleep(0.01)

        await asyncio.wait_for(wait_for_claim(), 3)
        assert reads[1] == [], 'Contender read the receipt before acquiring ownership'
        assert not tasks[1].done()
        if outcome == 'timeout':
            # Cancel only this wait, leaving the owner untouched; timeout recovery
            # itself is exercised below using PostgreSQL's lock_timeout setting.
            tasks[1].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[1]
            await second.execute("SET lock_timeout = '100ms'")
            assert await asyncio.wait_for(run(second_parser), 2) is False
            assert reads[1] == []
            assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
            release.set()
            assert await asyncio.wait_for(tasks[0], 3) is True
            assert await run(second_parser) is True
            assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1
            assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_data')] == [(1, 1)]
            assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
            assert [tuple(r) for r in await observer.fetch('SELECT * FROM proximity_processed_files')] == [(source.name, True)]
            return
        if outcome == 'cancel':
            tasks[0].cancel()
        else:
            release.set()
        results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
        assert results[1] is True
        if outcome == 'cancel':
            assert isinstance(results[0], asyncio.CancelledError)
        else:
            assert results[0] is (outcome == 'commit')
        release.set()
        assert await run(second_parser) is True
        assert await observer.fetchval('SELECT sum(applied) FROM proof_data') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proof_data')] == [(1, 1)]
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
        assert [tuple(r) for r in await observer.fetch('SELECT * FROM proximity_processed_files')] == [(source.name, True)]
        print(f'Receipt ownership: first={outcome}, contender blocked before read, aggregate=1, receipt=1, replay unchanged')
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await second.close(timeout=5)


def adapter_for(conn):
    async def execute(query, params=None):
        return await conn.execute(query, *(params or ()))
    return SimpleNamespace(execute=execute)


@pytest.mark.parametrize('flag', [True, False, None])
async def test_claim_preserves_existing_flag_and_metadata(journal_db, flag):  # noqa: F811
    writer, observer = journal_db
    await writer.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN, file_hash TEXT)')
    await writer.execute("INSERT INTO proximity_processed_files VALUES ('sealed', $1, 'existing-hash')", flag)
    async with writer.transaction():
        await claim_import_receipt(adapter_for(writer), 'sealed')
        assert tuple(await writer.fetchrow('SELECT * FROM proximity_processed_files')) == ('sealed', flag, 'existing-hash')
    assert tuple(await observer.fetchrow('SELECT * FROM proximity_processed_files')) == ('sealed', flag, 'existing-hash')


async def test_distinct_filenames_do_not_share_a_lock(journal_db):  # noqa: F811
    first, second = journal_db
    await first.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    async with first.transaction():
        await claim_import_receipt(adapter_for(first), 'one')
        async with second.transaction():
            await asyncio.wait_for(claim_import_receipt(adapter_for(second), 'two'), 2)
            await second.execute("UPDATE proximity_processed_files SET aggregates_applied=TRUE WHERE filename='two'")
        assert await second.fetchval("SELECT count(*) FROM proximity_processed_files WHERE filename='one'") == 0
        await first.execute("UPDATE proximity_processed_files SET aggregates_applied=TRUE WHERE filename='one'")
    assert [tuple(r) for r in await second.fetch('SELECT * FROM proximity_processed_files ORDER BY filename')] == [('one', True), ('two', True)]


@pytest.mark.parametrize('isolation', ['repeatable_read', 'serializable'])
async def test_stale_snapshot_claim_requires_whole_transaction_retry(journal_db, isolation):  # noqa: F811
    first, second = journal_db
    await first.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    with pytest.raises(asyncpg.SerializationError):
        async with second.transaction(isolation=isolation):
            assert await second.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
            async with first.transaction():
                await claim_import_receipt(adapter_for(first), 'one')
                await first.execute("UPDATE proximity_processed_files SET aggregates_applied=TRUE WHERE filename='one'")
            await claim_import_receipt(adapter_for(second), 'one')
    async with second.transaction(isolation=isolation):
        await claim_import_receipt(adapter_for(second), 'one')
        assert await second.fetchval('SELECT aggregates_applied FROM proximity_processed_files') is True


async def test_nested_claim_retained_after_cancelled_waiter(journal_db):  # noqa: F811
    first, observer = journal_db
    await first.execute('CREATE TABLE proximity_processed_files (filename TEXT PRIMARY KEY, aggregates_applied BOOLEAN)')
    second = await asyncpg.connect(**connection_options())
    await second.execute('SET search_path TO ' + await first.fetchval('SHOW search_path'))
    first_pid = await first.fetchval('SELECT pg_backend_pid()')
    second_pid = await second.fetchval('SELECT pg_backend_pid()')
    tasks = []

    async def contender():
        async with second.transaction():
            await claim_import_receipt(adapter_for(second), 'one')
            return await second.fetchval('SELECT aggregates_applied FROM proximity_processed_files')

    async def wait_blocked():
        while first_pid not in await observer.fetchval('SELECT pg_blocking_pids($1)', second_pid):
            await asyncio.sleep(0.01)

    try:
        async with first.transaction():
            async with first.transaction():
                await claim_import_receipt(adapter_for(first), 'one')
                await first.execute("UPDATE proximity_processed_files SET aggregates_applied=TRUE WHERE filename='one'")
            tasks.append(asyncio.create_task(contender()))
            await asyncio.wait_for(wait_blocked(), 2)
            tasks[-1].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[-1]
            assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 0
            tasks.append(asyncio.create_task(contender()))
            await asyncio.wait_for(wait_blocked(), 2)
            assert not tasks[-1].done()
        assert await asyncio.wait_for(tasks[-1], 2) is True
        assert await observer.fetchval('SELECT count(*) FROM proximity_processed_files') == 1
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await second.close(timeout=5)
