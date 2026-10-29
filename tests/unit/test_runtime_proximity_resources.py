"""Real adapter acquisition lifecycle with controlled native connection doubles."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.core.database_adapter import PostgreSQLAdapter
from shared.runtime_proximity_resources import proximity_database_resources


def setup_resources():
    identity = dict(database='proof', schema='test', recovery=False, read_only='off')
    connections = [SimpleNamespace(
        get_server_pid=lambda pid=pid: pid, is_in_transaction=lambda: False,
        fetchrow=AsyncMock(return_value=dict(identity)),
    ) for pid in (100, 200)]
    borrowed, released = [], []

    class Pool:
        def get_max_size(self):
            return 2

        async def acquire(self):
            conn = connections[len(borrowed)]
            borrowed.append(conn)
            return conn

        async def release(self, conn):
            released.append(conn)

    # Native pool acquire supports BOTH await and async-with. Keep both paths
    # here so the actual PostgreSQLAdapter.connection() remains under test.
    pool = Pool()
    acquire = pool.acquire

    class Acquisition:
        def __await__(self):
            return acquire().__await__()

        async def __aenter__(self):
            self.conn = await acquire()
            return self.conn

        async def __aexit__(self, *args):
            await pool.release(self.conn)

    pool.acquire = Acquisition
    adapter = PostgreSQLAdapter('127.0.0.1', 5432, 'proof', 'fixture', '')
    adapter.pool = pool
    return adapter, connections, borrowed, released


async def test_separate_connections_writer_probe_released_before_body():
    adapter, connections, borrowed, released = setup_resources()
    async with proximity_database_resources(adapter) as (writer, observer):
        assert writer is adapter
        assert observer is connections[0]
        assert borrowed == connections
        assert released == [connections[1]]
    assert released == [connections[1], connections[0]]


@pytest.mark.parametrize('size', [0, 1])
async def test_insufficient_pool_capacity_refuses_before_acquire(size):
    adapter, _, borrowed, _ = setup_resources()
    adapter.pool.get_max_size = lambda: size
    with pytest.raises(ValueError, match='two pool slots'):
        async with proximity_database_resources(adapter):
            pytest.fail('must not yield')
    assert borrowed == []


@pytest.mark.parametrize('bad', [None, object(), PostgreSQLAdapter('127.0.0.1', 5432, 'x', 'x', '')])
async def test_no_implicit_connect(bad):
    with pytest.raises(TypeError, match='explicitly connected'):
        async with proximity_database_resources(bad):
            pytest.fail('must not yield')


@pytest.mark.parametrize('index', [0, 1])
@pytest.mark.parametrize('field,value', [('recovery', True), ('read_only', 'on'), ('schema', None)])
async def test_primary_guards_release_every_acquired_connection(index, field, value):
    adapter, conns, borrowed, released = setup_resources()
    conns[index].fetchrow.return_value[field] = value
    with pytest.raises(RuntimeError, match='writable primary'):
        async with proximity_database_resources(adapter):
            pytest.fail('must not yield')
    assert released == list(reversed(borrowed))


@pytest.mark.parametrize('field', ['database', 'schema'])
async def test_identity_mismatch_fails_closed(field):
    adapter, conns, borrowed, released = setup_resources()
    conns[1].fetchrow.return_value[field] = 'other'
    with pytest.raises(RuntimeError, match='differ'):
        async with proximity_database_resources(adapter):
            pytest.fail('must not yield')
    assert released == list(reversed(borrowed))


async def test_same_backend_refused():
    adapter, conns, _, released = setup_resources()
    conns[1].get_server_pid = conns[0].get_server_pid
    with pytest.raises(RuntimeError, match='separate backends'):
        async with proximity_database_resources(adapter):
            pytest.fail('must not yield')
    assert released == list(reversed(conns))


async def test_inherited_transaction_refused_without_releasing_owners_connection():
    adapter, conns, borrowed, released = setup_resources()
    conns[1].is_in_transaction = lambda: True
    token = adapter._active_tx_conn.set(conns[1])  # noqa: SLF001 -- inherited context proof.
    try:
        with pytest.raises(RuntimeError, match='outside transactions'):
            async with proximity_database_resources(adapter):
                pytest.fail('must not yield')
    finally:
        adapter._active_tx_conn.reset(token)  # noqa: SLF001
    assert borrowed == released == [conns[0]]


@pytest.mark.parametrize('phase', ['observer', 'writer', 'body'])
async def test_cancellation_unwinds_all_owned_resources(phase):
    adapter, conns, borrowed, released = setup_resources()
    active = asyncio.Event()

    async def block(*args):
        active.set()
        await asyncio.Event().wait()

    if phase != 'body':
        conns[0 if phase == 'observer' else 1].fetchrow = block

    async def run():
        async with proximity_database_resources(adapter):
            await block()

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(active.wait(), 1)
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert released == list(reversed(borrowed))
