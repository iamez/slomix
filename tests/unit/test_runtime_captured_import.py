"""Controller handoff validation and unchanged canonical batch failure semantics."""

import asyncio
import shutil
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from bot import runtime_import_batch as batch
from bot.runtime_captured_import import import_captured_match
from shared.runtime_captured_match import CapturedMatch
from shared.runtime_host_capture import CapturedStats
from shared.runtime_stats_dispatch import CompletedStatsReference
from shared.runtime_writer_lock import ImportWriterBusy, local_import_writer
from tests.unit.test_runtime_identity_contract import FIRST, SECOND
from tests.unit.test_runtime_identity_import import completed_identity_pair


def capture_pair(root):
    first, second = completed_identity_pair(root)

    def captured(item):
        return CapturedStats(item.root, CompletedStatsReference(
            item.generation, item.filename, item.size, item.sha256))

    info = root.stat()
    return CapturedMatch(captured(first), captured(second), FIRST, SECOND, (info.st_dev, info.st_ino))


@pytest.mark.parametrize('defect', ['none', 'wrong_root', 'copied_root', 'same_generation',
                                  'wrong_pair', 'wrong_half', 'wrong_hash', 'wrong_map'])
async def test_preflight_refuses_bad_pair_before_any_attempt(tmp_path, monkeypatch, defect):
    captured = capture_pair(tmp_path / 'capture')
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    if defect == 'none':
        captured = None
    elif defect in ('wrong_root', 'copied_root'):
        other = tmp_path / 'other'
        shutil.copytree(captured.first.root, other)
        captured = replace(captured, second=replace(captured.second, root=other))
        if defect == 'copied_root':
            captured = replace(captured, first=replace(captured.first, root=other))
    elif defect == 'same_generation':
        captured = replace(captured, second=captured.first)
    elif defect == 'wrong_pair':
        captured = replace(captured, second_identity=replace(SECOND, source_id='other'))
    else:
        ref = captured.second.reference
        changes = {'wrong_half': {'filename': ref.filename.replace('round-2', 'round-1')},
                   'wrong_hash': {'sha256': 'invalid'},
                   'wrong_map': {'filename': ref.filename.replace('supply', 'oasis')}}
        captured = replace(captured, second=replace(captured.second, reference=replace(ref, **changes[defect])))
    attempt = AsyncMock()
    monkeypatch.setattr(batch, 'run_import_once', attempt)
    with pytest.raises(ValueError):
        await import_captured_match(None, captured, lock_directory=lock)
    attempt.assert_not_awaited()


async def test_replaced_capture_root_refused_even_with_same_bytes(tmp_path, monkeypatch):
    captured = capture_pair(tmp_path / 'capture')
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    held = tmp_path / 'held'
    captured.first.root.rename(held)
    shutil.copytree(held, captured.first.root)
    attempt = AsyncMock()
    monkeypatch.setattr(batch, 'run_import_once', attempt)
    with pytest.raises(ValueError, match='root identity changed'):
        await import_captured_match(None, captured, lock_directory=lock)
    attempt.assert_not_awaited()


@pytest.mark.parametrize('failure_at', [None, 0, 1])
async def test_serial_bound_jobs_keep_warning_success_and_failure_prefix(tmp_path, monkeypatch, failure_at):
    captured = capture_pair(tmp_path / 'capture')
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    before = {p: p.read_bytes() for p in captured.first.root.rglob('*') if p.is_file()}
    outcomes = [(True, 'Imported WITH WARNINGS'), (True, 'ok')]
    if failure_at is not None:
        outcomes[failure_at] = (False, 'retryable fixture failure')
    calls = []

    async def attempt(database, current, **kwargs):
        with pytest.raises(ImportWriterBusy), local_import_writer(lock):
            pass
        calls.append((current, kwargs))
        await asyncio.sleep(0)
        return outcomes[len(calls) - 1]

    monkeypatch.setattr(batch, 'run_import_once', attempt)
    actual = await import_captured_match(None, captured, lock_directory=lock, attempt_timeout=17.0)
    count = 2 if failure_at is None else failure_at + 1
    assert actual == tuple(outcomes[:count])
    assert len(calls) == count
    for i, (current, kwargs) in enumerate(calls):
        assert kwargs['expected_identity'] == (FIRST, SECOND)[i]
        assert kwargs['journal_enabled'] is True and kwargs['require_declared_identity'] is True
        assert kwargs['timeout'] == 17.0
        assert kwargs['first'] == (calls[0][0] if i else None)
        assert current.root == captured.first.root
    assert all(p.read_bytes() == raw for p, raw in before.items())
    with local_import_writer(lock):
        pass


@pytest.mark.parametrize('exception', [RuntimeError('fixture'), asyncio.CancelledError()])
async def test_failure_releases_lock_retains_capture_and_allows_explicit_replay(tmp_path, monkeypatch, exception):
    captured = capture_pair(tmp_path / 'capture')
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    attempt = AsyncMock(side_effect=exception)
    monkeypatch.setattr(batch, 'run_import_once', attempt)
    with pytest.raises(type(exception)):
        await import_captured_match(None, captured, lock_directory=lock)
    assert attempt.await_count == 1
    with local_import_writer(lock):
        pass
    attempt.side_effect = None
    attempt.return_value = (True, 'Already mapped')
    assert await import_captured_match(None, captured, lock_directory=lock) == (
        (True, 'Already mapped'), (True, 'Already mapped'))
    assert all((item.directory / item.reference.filename).exists() for item in (captured.first, captured.second))


@pytest.mark.parametrize('deferred', [False, True])
async def test_captured_team_policy_is_explicit(tmp_path, monkeypatch, deferred):
    captured = capture_pair(tmp_path / 'capture')
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    attempt = AsyncMock(return_value=(True, 'ok'))
    monkeypatch.setattr(batch, 'run_import_once', attempt)
    await import_captured_match(None, captured, lock_directory=lock, defer_team_assignment=deferred)
    assert attempt.await_count == 2
    assert all(c.kwargs['defer_team_assignment'] is deferred for c in attempt.await_args_list)


async def test_captured_bad_team_policy_before_verifying_capture(tmp_path):
    with pytest.raises(ValueError, match='explicit boolean'):
        await import_captured_match(None, None, lock_directory=tmp_path, defer_team_assignment='true')
