"""Serial batch contracts and actual receipt/parser/preflight composition."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot import runtime_import_attempt
from bot import runtime_import_batch as module
from shared.import_result import RetryableImportFailure
from shared.runtime_import_pool import ImportDatabaseConfig
from shared.runtime_writer_lock import ImportWriterBusy
from tests.unit.test_runtime_completed_import import inputs as inputs
from tests.unit.test_runtime_writer_lock import child


def jobs(request):
    first, second = [item[0] for item in request.getfixturevalue('inputs')]
    return (module.ImportJob(first), module.ImportJob(second, first=first))


@pytest.mark.parametrize('failure', [(False, 'rejected'), RetryableImportFailure('later')])
async def test_stop_preserves_failure_identity(request, monkeypatch, failure):
    attempt = AsyncMock(side_effect=[failure, (True, 'must not execute')])
    monkeypatch.setattr(module, 'run_import_once', attempt)
    results = await module.run_import_batch(None, jobs(request), journal_enabled=True)
    assert len(results) == 1 and results[0] is failure
    assert attempt.await_count == 1


@pytest.mark.parametrize('failure', [RuntimeError('fixture'), asyncio.CancelledError(),
                                    runtime_import_attempt.ImportAttemptTimeout('fixture')])
async def test_exception_stops_later_jobs(request, monkeypatch, failure):
    attempt = AsyncMock(side_effect=failure)
    monkeypatch.setattr(module, 'run_import_once', attempt)
    with pytest.raises(type(failure)) as caught:
        await module.run_import_batch(None, jobs(request), journal_enabled=True)
    assert caught.value is failure and attempt.await_count == 1


@pytest.mark.parametrize('kind', ['list', 'generator', 'oversized', 'bad_late_job', 'bad_input'])
async def test_entire_envelope_validated_before_first_attempt(request, monkeypatch, kind):
    pair = jobs(request)
    bad = {'list': list(pair), 'generator': iter(pair), 'oversized': (pair[0],) * 17,
           'bad_late_job': (pair[0], None), 'bad_input': (module.ImportJob(None),)}[kind]
    attempt = AsyncMock()
    monkeypatch.setattr(module, 'run_import_once', attempt)
    with pytest.raises(ValueError):
        await module.run_import_batch(None, bad, journal_enabled=True)
    attempt.assert_not_awaited()


async def test_empty_batch_is_noop(monkeypatch):
    attempt = AsyncMock()
    monkeypatch.setattr(module, 'run_import_once', attempt)
    assert await module.run_import_batch(None, (), journal_enabled=False) == ()
    attempt.assert_not_awaited()


@pytest.mark.parametrize('policy', [False, True])
async def test_exclusive_batch_forwards_identity_policy_to_every_attempt(request, monkeypatch, tmp_path, policy):
    lock = tmp_path / 'policy-lock'
    lock.mkdir(mode=0o700)
    attempt = AsyncMock(return_value=(True, 'ok'))
    monkeypatch.setattr(module, 'run_import_once', attempt)
    await module.run_exclusive_import_batch(None, jobs(request), lock_directory=lock,
                                            journal_enabled=True, require_declared_identity=policy)
    assert attempt.await_count == 2
    assert all(call.kwargs['require_declared_identity'] is policy for call in attempt.await_args_list)


@pytest.mark.parametrize('policy', [None, 0, 1, 'true'])
async def test_invalid_policy_does_not_run_even_empty_batch(monkeypatch, policy):
    attempt = AsyncMock()
    monkeypatch.setattr(module, 'run_import_once', attempt)
    with pytest.raises(ValueError, match='boolean identity policy'):
        await module.run_import_batch(None, (), journal_enabled=True, require_declared_identity=policy)
    attempt.assert_not_awaited()


async def test_warning_success_then_failure_returns_exact_prefix(request, monkeypatch):
    pair = jobs(request)
    warning = (True, 'Imported WITH WARNINGS')
    failed = RetryableImportFailure('retry later')
    attempt = AsyncMock(side_effect=[warning, failed, (True, 'must not execute')])
    monkeypatch.setattr(module, 'run_import_once', attempt)
    result = await module.run_import_batch(None, (*pair, pair[0]), journal_enabled=True)
    assert len(result) == 2 and result[0] is warning and result[1] is failed
    assert attempt.await_count == 2


async def test_real_pair_composition_is_serial_and_retains_inputs(request, monkeypatch):
    pair = jobs(request)
    events = []
    pools = []

    async def factory(database):
        number = len(pools)
        assert all(pool.closed for pool in pools), 'Next attempt started before previous pool closed'
        events.append(('open', number))

        async def fetchval(query, *args):
            assert 'processed_files' in query and args == (pair[number].current.filename,)
            events.append(('query', number))
            await asyncio.sleep(0)
            return 1

        @asynccontextmanager
        async def acquire():
            yield SimpleNamespace(fetchval=fetchval)

        async def close():
            pool.closed = True
            events.append(('close', number))

        pool = SimpleNamespace(acquire=acquire, close=close, terminate=Mock(), closed=False)
        pools.append(pool)
        return pool

    monkeypatch.setattr(runtime_import_attempt, 'create_import_pool', factory)
    database = ImportDatabaseConfig('/tmp/fixture-socket', 'fixture_db', 'fixture_role', '')
    assert await module.run_import_batch(database, pair, journal_enabled=True) == (
        (True, 'Already processed'), (True, 'Already processed'),
    )
    assert events == [('open', 0), ('query', 0), ('close', 0), ('open', 1), ('query', 1), ('close', 1)]
    for item, raw in request.getfixturevalue('inputs'):
        source = item.root / item.generation / item.filename
        assert source.read_bytes() == raw and source.with_name(source.name + '.complete.json').exists()
    print('Serial R1/R2 batch: real receipts/parser/canonical preflight; each protocol pool closed before next')


@pytest.mark.parametrize('cancel', [False, True])
async def test_exclusive_batch_holds_lock_through_await_and_releases(request, monkeypatch, tmp_path, cancel):
    tmp_path.chmod(0o700)
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def attempt(*args, **kwargs):
        calls.append(args)
        entered.set()
        await release.wait()
        return True, 'Already processed'

    monkeypatch.setattr(module, 'run_import_once', attempt)
    pair = jobs(request)

    async def run():
        return await module.run_exclusive_import_batch(
            None, pair, lock_directory=tmp_path, journal_enabled=True,
        )

    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        with pytest.raises(ImportWriterBusy):
            await run()
        assert len(calls) == 1
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            release.set()
            assert len(await asyncio.wait_for(task, 1)) == 2
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    release.set()
    assert len(await asyncio.wait_for(run(), 1)) == 2


@pytest.mark.parametrize('cancel', [False, True])
async def test_other_process_blocked_until_real_attempt_cleanup_finishes(request, monkeypatch, tmp_path, cancel):
    """Actual receipt/parser/preflight/session composition; protocol pool only."""
    tmp_path.chmod(0o700)
    closing = asyncio.Event()
    release = asyncio.Event()
    terminated = []

    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetchval=AsyncMock(return_value=1))

    async def close():
        closing.set()
        await release.wait()

    def terminate():
        # On cancelled cleanup, exclusion must still hold during termination.
        observed = child(tmp_path)
        assert observed.returncode == 0 and observed.stdout.strip() == 'busy', observed.stderr
        terminated.append(True)

    pool = SimpleNamespace(acquire=acquire, close=close, terminate=terminate)
    monkeypatch.setattr(runtime_import_attempt, 'create_import_pool', AsyncMock(return_value=pool))
    database = ImportDatabaseConfig('/tmp/fixture-socket', 'fixture_db', 'fixture_role', '')
    selected = jobs(request)[:1]
    task = asyncio.create_task(module.run_exclusive_import_batch(
        database, selected, lock_directory=tmp_path, journal_enabled=True,
    ))
    try:
        await asyncio.wait_for(closing.wait(), 2)
        observed = child(tmp_path)
        assert observed.returncode == 0 and observed.stdout.strip() == 'busy', observed.stderr
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            release.set()
            assert await asyncio.wait_for(task, 2) == ((True, 'Already processed'),)
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert terminated == ([True] if cancel else [])
    observed = child(tmp_path)
    assert observed.returncode == 0 and observed.stdout.strip() == 'owned', observed.stderr
    print(f'Cross-process exclusion spans canonical attempt cleanup, cancel={cancel}; released only after exit')


@pytest.mark.parametrize('deferred', [False, True])
async def test_exclusive_batch_team_policy_reaches_every_attempt(tmp_path, request, monkeypatch, deferred):
    attempt = AsyncMock(return_value=(True, 'ok'))
    monkeypatch.setattr(module, 'run_import_once', attempt)
    await module.run_exclusive_import_batch(None, jobs(request), lock_directory=tmp_path,
                                            journal_enabled=True, defer_team_assignment=deferred)
    assert attempt.await_count == 2
    assert all(c.kwargs['defer_team_assignment'] is deferred for c in attempt.await_args_list)


@pytest.mark.parametrize('deferred,journal', [(None, True), (1, True), ('true', True), (True, False)])
async def test_bad_team_policy_precedes_lock_and_empty_batch(tmp_path, monkeypatch, deferred, journal):
    from unittest.mock import Mock

    lock = Mock(side_effect=AssertionError('must not acquire lock'))
    monkeypatch.setattr(module, 'local_import_writer', lock)
    with pytest.raises(ValueError):
        await module.run_exclusive_import_batch(None, (), lock_directory=tmp_path,
                                                journal_enabled=journal, defer_team_assignment=deferred)
    lock.assert_not_called()
    with pytest.raises(ValueError):
        await module.run_import_batch(None, (), journal_enabled=journal, defer_team_assignment=deferred)
