"""Single-attempt composition with real receipts/parser and a protocol DB pool."""

import asyncio
import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot import runtime_import_attempt as module
from shared.runtime_import_pool import ImportDatabaseConfig
from tests.unit.test_runtime_completed_import import inputs as inputs


def database():
    return ImportDatabaseConfig('/tmp/fixture-socket', 'fixture_db', 'fixture_role', '')


@pytest.mark.parametrize('mode', ['duplicate', 'deadline', 'cancel', 'query_timeout'])
async def test_actual_composition_retains_sources_and_cleans_up(request, monkeypatch, mode):
    reached = asyncio.Event()
    released = asyncio.Event()

    async def fetchval(query, *args):
        assert 'processed_files' in query
        reached.set()
        if mode == 'query_timeout':
            raise TimeoutError('fixture query timeout')
        if mode != 'duplicate':
            await asyncio.Event().wait()
        return 1

    @asynccontextmanager
    async def acquire():
        try:
            yield SimpleNamespace(fetchval=fetchval)
        finally:
            released.set()

    pool = SimpleNamespace(acquire=acquire, close=AsyncMock(), terminate=Mock())
    factory = AsyncMock(return_value=pool)
    monkeypatch.setattr(module, 'create_import_pool', factory)
    current, raw = request.getfixturevalue('inputs')[0]
    before = set(os.listdir('/proc/self/fd'))
    task = asyncio.create_task(module.run_import_once(
        database(), current, journal_enabled=True, timeout=0.05 if mode == 'deadline' else 2,
    ))
    try:
        if mode == 'cancel':
            await asyncio.wait_for(reached.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif mode == 'deadline':
            with pytest.raises(module.ImportAttemptTimeout):
                await asyncio.wait_for(task, 0.5)
        else:
            result = await asyncio.wait_for(task, 1)
            if mode == 'duplicate':
                assert result == (True, 'Already processed')
            else:
                assert result.retryable and result == (False, 'fixture query timeout')
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert reached.is_set() and released.is_set()
    pool.close.assert_awaited_once_with()
    pool.terminate.assert_not_called()
    assert set(os.listdir('/proc/self/fd')) == before
    source = current.root / current.generation / current.filename
    assert source.read_bytes() == raw and source.with_name(source.name + '.complete.json').exists()
    print(f'Attempt {mode}: canonical preflight reached, lease/pool/FDs released, source retained')


@pytest.mark.parametrize('timeout', [True, None, '60', 0, -1, 301, float('nan'), float('inf')])
async def test_invalid_budget_never_creates_pool(monkeypatch, timeout):
    factory = AsyncMock()
    monkeypatch.setattr(module, 'create_import_pool', factory)
    with pytest.raises(ValueError):
        await module.run_import_once(database(), None, journal_enabled=True, timeout=timeout)
    factory.assert_not_awaited()


@pytest.mark.parametrize('policy', [None, 0, 1, 'true'])
async def test_invalid_identity_policy_never_creates_pool(monkeypatch, policy):
    factory = AsyncMock()
    monkeypatch.setattr(module, 'create_import_pool', factory)
    with pytest.raises(ValueError, match='boolean identity policy'):
        await module.run_import_once(database(), None, journal_enabled=True, require_declared_identity=policy)
    factory.assert_not_awaited()


async def test_strict_legacy_rejection_precedes_canonical_preflight(request, monkeypatch):
    query = AsyncMock(return_value=1)
    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetchval=query)
    pool = SimpleNamespace(acquire=acquire, close=AsyncMock(), terminate=Mock())
    monkeypatch.setattr(module, 'create_import_pool', AsyncMock(return_value=pool))
    current, _ = request.getfixturevalue('inputs')[0]
    with pytest.raises(ValueError, match='identity'):
        await module.run_import_once(database(), current, journal_enabled=True, require_declared_identity=True)
    query.assert_not_awaited()
    pool.close.assert_awaited_once_with()


@pytest.mark.parametrize('deferred,journal', [(1, True), ('true', True), (None, True), (True, False)])
async def test_invalid_team_policy_precedes_resources(monkeypatch, deferred, journal):
    factory = AsyncMock()
    monkeypatch.setattr(module, 'create_import_pool', factory)
    with pytest.raises(ValueError, match='team_assignment|enabled journal'):
        await module.run_import_once(database(), None, journal_enabled=journal,
                                     defer_team_assignment=deferred)
    factory.assert_not_awaited()


@pytest.mark.parametrize('deferred', [False, True])
async def test_attempt_forwards_team_policy_and_closes_pool(request, monkeypatch, deferred):
    supplied = request.getfixturevalue("inputs")
    owned = SimpleNamespace(close=AsyncMock(), terminate=Mock())
    monkeypatch.setattr(module, 'create_import_pool', AsyncMock(return_value=owned))
    seen = []

    async def import_source(manager, *args, **kwargs):
        seen.append(manager.defer_team_assignment)
        assert manager.pool is owned
        return True, 'fixture'

    monkeypatch.setattr(module, 'import_completed_round', import_source)
    assert (await module.run_import_once(database(), supplied[0][0], journal_enabled=True,
                                         defer_team_assignment=deferred))[0] is True
    assert seen == [deferred]
    owned.close.assert_awaited_once()
