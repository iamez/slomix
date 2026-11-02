"""Actual Lua retained timing -> durable link; independent visibility and faults."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from asyncpg import LockNotAvailableError

from bot.runtime_gametime_link import inspect_declared_gametime_link, link_declared_gametime
from tests.integration.test_lua_override_boundary_pg import adapter_for
from tests.integration.test_runtime_gametime_correlation_pg import (
    full_import_db as _full_import_db,
)
from tests.integration.test_runtime_gametime_correlation_pg import (
    pipeline as _pipeline,
)
from tests.integration.test_runtime_gametime_correlation_pg import (
    retain,
    snapshot,
)

full_import_db = _full_import_db
pipeline = _pipeline
pytestmark = pytest.mark.timeout(120)


async def link(p, half=0, adapter=None):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        return await link_declared_gametime(adapter or p.adapter, stream.fileno(), **options)


async def observe(p, half=0):
    path, options = p.artifacts[half]
    with path.open('rb') as stream:
        return await inspect_declared_gametime_link(p.reader, stream.fileno(), **options)


async def test_pair_rollback_replay_conflict(pipeline):
    p = pipeline
    assert (await link(p)).status == 'missing_retention'
    inputs = [await retain(p, half) for half in (0, 1)]
    initial = await snapshot(p.reader)
    assert (await observe(p)).status == 'not_linked'
    # A legacy completion cannot be silently relabelled a new declared link.
    async with p.adapter.transaction():
        await p.writer.execute('INSERT INTO lua_correction_receipts(input_id,round_id) VALUES ($1,1)', inputs[0].input_id)
        assert (await link(p)).status == 'conflict'
    assert (await observe(p)).status == 'conflict'
    await p.writer.execute('DELETE FROM lua_correction_receipts WHERE input_id=$1', inputs[0].input_id)
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_links') == 0
    outer = p.writer.transaction()
    await outer.start()
    try:
        assert (await link(p)).status == 'linked'
        assert await p.writer.fetchval('SELECT count(*) FROM runtime_gametime_links') == 1
        assert (await observe(p)).status == 'not_linked'
    finally:
        await outer.rollback()
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_links') == 0
    for half in (0, 1):
        assert (await link(p, half)).status == 'linked'
        assert (await observe(p, half)).status == 'linked'
        before = await p.reader.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation')
        assert (await link(p, half)).status == 'already_linked'
        assert await p.reader.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation') == before
    assert await snapshot(p.reader) == initial
    rows = await p.reader.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation')
    assert len(rows) == await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_links') == 2
    # Corruption is a conflict on BOTH replay and independent observation.
    await p.writer.execute("UPDATE runtime_gametime_links SET projection_sha256=repeat('f',64) WHERE generation=$1", '1' * 32)
    assert (await observe(p)).status == 'conflict'
    with pytest.raises(ValueError, match='conflicts'):
        await link(p)
    await p.writer.execute('UPDATE runtime_gametime_links SET projection_sha256=$1 WHERE generation=$2',
                           rows[0]['projection_sha256'], '1' * 32)
    # A second artifact for this canonical parent never overwrites the first.
    p.artifacts[0][1]['generation'] = 'd' * 32
    await retain(p)
    with pytest.raises(ValueError, match='conflicts'):
        await link(p)
    assert await p.reader.fetch('SELECT * FROM runtime_gametime_links ORDER BY generation') == rows
    print('DURABLE TIMING LINK: 2 actual Lua artifacts -> 2 parents; rollback invisible, replay unchanged, '
          'legacy/provenance/new-generation conflicts rejected; round/player data unchanged')


@pytest.mark.parametrize('cancel', [False, True])
async def test_failure_after_link_insert_rolls_back(pipeline, monkeypatch, cancel):
    p = pipeline
    await retain(p)
    before = await snapshot(p.reader)
    transaction = p.adapter.transaction
    reached = []

    @asynccontextmanager
    async def injected():
        async with transaction() as connection:
            async def fetchrow(query, *args):
                row = await connection.fetchrow(query, *args)
                if query.startswith('INSERT INTO runtime_gametime_links'):
                    assert await connection.fetchval('SELECT count(*) FROM runtime_gametime_links') == 1
                    reached.append(True)
                    if cancel:
                        raise asyncio.CancelledError()
                    raise RuntimeError('fixture failure after durable link insertion')
                return row
            yield SimpleNamespace(fetchrow=fetchrow, fetchval=connection.fetchval)

    monkeypatch.setattr(p.adapter, 'transaction', injected)
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await link(p)
    assert reached == [True]
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_links') == 0
    assert await snapshot(p.reader) == before


@pytest.mark.parametrize('commit', [False, True])
async def test_concurrent_exact_link_serializes_and_rechecks(pipeline, full_import_db, commit):
    p = pipeline
    await retain(p)
    manager, _ = full_import_db
    async with manager.pool.acquire() as other:
        outer = p.writer.transaction()
        await outer.start()
        task = None
        try:
            linked = await link(p)
            assert linked.status == 'linked'
            task = asyncio.create_task(link(p, adapter=adapter_for(other)))
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), .1)
            assert (await observe(p)).status == 'not_linked'
            with pytest.raises(LockNotAvailableError):
                async with p.reader.transaction():
                    await p.reader.execute("SET LOCAL lock_timeout='100ms'")
                    await p.reader.execute("UPDATE rounds SET map_name='blocked' WHERE id=$1", linked.round_id)
        finally:
            if commit:
                await outer.commit()
            else:
                await outer.rollback()
        try:
            assert (await asyncio.wait_for(task, 5)).status == ('already_linked' if commit else 'linked')
        finally:
            if task is not None and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
    assert (await observe(p)).status == 'linked'
    assert await p.reader.fetchval('SELECT count(*) FROM runtime_gametime_links') == 1
