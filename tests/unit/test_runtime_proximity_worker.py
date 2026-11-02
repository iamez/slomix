"""Caller-owned worker lifecycle, pacing and actual checkpoint smoke."""

import asyncio
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import asyncpg
import pytest

from shared import runtime_proximity_worker as module
from shared.runtime_proximity_batch import ProximityBatchItem, ProximityBatchResult, ProximityDiscovery
from shared.runtime_proximity_queue import ProximityQueueResult


def worker(root, **kwargs):
    return module.RuntimeProximityWorker(root, source_id='fixture', gametimes_dir=root, **kwargs)


@asynccontextmanager
async def resources():
    yield None, None


def batch(*actions):
    items = tuple(ProximityBatchItem(f'{i:032x}', ProximityQueueResult(action, reason))
                  for i, (action, reason) in enumerate(actions))
    return ProximityBatchResult(ProximityDiscovery(tuple(i.generation for i in items),
                                                   None, len(items), 0, len(items)), items)


async def test_disabled_is_default_and_does_not_acquire(tmp_path):
    acquire = Mock(side_effect=AssertionError('must not acquire'))
    subject = worker(tmp_path)
    await subject.run(acquire, asyncio.Event())
    assert subject.state.status == 'disabled'
    assert not list(tmp_path.iterdir())
    acquire.assert_not_called()


@pytest.mark.parametrize('kwargs', [dict(enabled=1), dict(batch_size=True), dict(batch_size=33),
                                   dict(max_entries=0), dict(poll_seconds=float('nan')),
                                   dict(attempt_timeout=float('inf')), dict(retry_seconds=0),
                                   dict(max_retry_seconds=3601), dict(poll_seconds=True),
                                   dict(retry_seconds=10, max_retry_seconds=5)])
def test_bad_configuration(tmp_path, kwargs):
    with pytest.raises(ValueError):
        worker(tmp_path, **kwargs)


async def test_backoff_caps_resets_and_releases_before_wait(tmp_path, monkeypatch, caplog):
    subject = worker(tmp_path, enabled=True, retry_seconds=2, max_retry_seconds=5, poll_seconds=7)
    stop = asyncio.Event()
    calls = 0
    opened = False
    delays = []

    @asynccontextmanager
    async def acquire():
        nonlocal opened
        assert not opened
        opened = True
        try:
            yield None, None
        finally:
            opened = False

    async def process(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls != 4:
            raise OSError('PRIVATE_SENTINEL_DO_NOT_LOG')
        return batch(('deferred', 'not_due'))

    async def wait(_stop, delay):
        assert not opened
        delays.append(delay)
        if calls == 5:
            stop.set()

    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)
    monkeypatch.setattr(subject, '_wait', wait)
    await subject.run(acquire, stop)
    assert delays == [2, 4, 5, 7, 2]
    assert subject.state.last_success_monotonic is not None
    assert 'PRIVATE_SENTINEL' not in caplog.text
    assert subject.state.status == 'stopped'


async def test_actual_local_batches_rotate_and_wait_even_when_full(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    for number in (3, 1, 2):
        (tmp_path / f'{number:032x}').mkdir(mode=0o700)
    subject = worker(tmp_path, enabled=True, batch_size=1, poll_seconds=9)
    stop = asyncio.Event()
    observed = []

    async def wait(_stop, delay):
        assert delay == 9
        observed.append(json.loads((tmp_path / '.proximity-cursor.json').read_text())['after'])
        assert subject.state.status == 'waiting'
        assert dict(subject.state.last_batch_counts)['deferred'] == 1
        if len(observed) == 4:
            stop.set()

    monkeypatch.setattr(subject, '_wait', wait)
    await subject.run(resources, stop)
    assert observed == [f'{number:032x}' for number in (1, 2, 3, 1)]
    assert len(list(tmp_path.iterdir())) == 4
    print('Worker runtime proof: actual cursor batches 1,2,3,1; four polling waits; no DB/service')


async def test_timeout_cleans_up_before_reacquiring(tmp_path, monkeypatch):
    subject = worker(tmp_path, enabled=True, attempt_timeout=0.01, retry_seconds=0.001)
    stop = asyncio.Event()
    acquired, released = [], []

    @asynccontextmanager
    async def acquire():
        acquired.append(len(acquired) + 1)
        try:
            yield None, None
        finally:
            released.append(len(released) + 1)

    async def process(*args, **kwargs):
        if len(acquired) == 1:
            await asyncio.Event().wait()
        assert released == [1]
        assert subject.state.error_type == 'TimeoutError'
        stop.set()
        return batch()

    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)
    await asyncio.wait_for(subject.run(acquire, stop), 1)
    assert acquired == released == [1, 2]


@pytest.mark.parametrize('error', [ValueError('schema'), asyncpg.UndefinedTableError('migration'),
                                 asyncpg.InterfaceError('misuse'), RuntimeError('bug')])
async def test_programming_and_schema_errors_fail_not_retry(tmp_path, monkeypatch, error):
    subject = worker(tmp_path, enabled=True)
    process = AsyncMock(side_effect=error)
    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)
    with pytest.raises(type(error)):
        await subject.run(resources, asyncio.Event())
    assert subject.state.status == 'failed'
    assert subject.state.error_type == type(error).__name__
    process.assert_awaited_once()


async def test_connection_error_is_retryable(tmp_path, monkeypatch):
    subject = worker(tmp_path, enabled=True)
    stop = asyncio.Event()
    process = AsyncMock(side_effect=asyncpg.ConnectionDoesNotExistError('closed'))
    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)

    async def wait(_stop, delay):
        assert subject.state.status == 'unavailable'
        assert delay == 5
        stop.set()

    monkeypatch.setattr(subject, '_wait', wait)
    await subject.run(resources, stop)
    process.assert_awaited_once()


@pytest.mark.parametrize('cancel_during_acquisition', [True, False])
async def test_cancel_releases_resources_and_rejects_double_run(tmp_path, monkeypatch, cancel_during_acquisition):
    subject = worker(tmp_path, enabled=True)
    active, released = asyncio.Event(), asyncio.Event()

    @asynccontextmanager
    async def acquire():
        try:
            if cancel_during_acquisition:
                active.set()
                await asyncio.Event().wait()
            yield None, None
        finally:
            released.set()

    async def process(*args, **kwargs):
        active.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', process)
    task = asyncio.create_task(subject.run(acquire, asyncio.Event()))
    try:
        await asyncio.wait_for(active.wait(), 1)
        with pytest.raises(RuntimeError, match='already running'):
            await subject.run(acquire, asyncio.Event())
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert released.is_set()
    assert subject.state.status == 'stopped'


@pytest.mark.parametrize('result, status', [(batch(), 'idle'),
    (batch(('reconcile', 'exhausted'), ('committed', 'matching_strict_receipt_visible')), 'attention'),
    (batch(('retry', 'parent_missing')), 'waiting')])
async def test_state_counts_are_last_batch_and_stop_interrupts_wait(tmp_path, monkeypatch, result, status):
    subject = worker(tmp_path, enabled=True, poll_seconds=3600)
    stop = asyncio.Event()
    monkeypatch.setattr(module, 'process_proximity_checkpointed_batch', AsyncMock(return_value=result))
    task = asyncio.create_task(subject.run(resources, stop))
    try:
        async with asyncio.timeout(1):
            while subject.state.last_success_monotonic is None:
                await asyncio.sleep(0)
        assert subject.state.status == status
        assert sum(dict(subject.state.last_batch_counts).values()) == len(result.items)
        assert subject.state.last_batch_exhausted == sum(i.result.reason == 'exhausted' for i in result.items)
    finally:
        stop.set()
        await asyncio.wait_for(task, 1)
