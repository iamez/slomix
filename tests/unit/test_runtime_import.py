"""Explicit waiting states must never become terminal processed markers."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared.import_result import RetryableImportFailure
from shared.runtime_import import import_ready_file


def manager(dependency=None, result=(True, 'ok')):
    """Protocol fixture with no DB or presentation dependencies."""
    return SimpleNamespace(
        parser=SimpleNamespace(find_corresponding_round_1_file=Mock(return_value=dependency)),
        process_file=AsyncMock(return_value=result),
        is_file_processed=AsyncMock(return_value=False),
        find_processed_duplicate=AsyncMock(return_value=None),
    )


async def test_missing_r1_waits_then_imports_when_available():
    """A future poll can retry without any processed marker from this step."""
    subject = manager()
    path = Path('2026-09-20-121000-goldrush-round-2.txt')
    assert (await import_ready_file(subject, path)).status == 'waiting_for_r1'
    subject.process_file.assert_not_awaited()
    subject.parser.find_corresponding_round_1_file.return_value = 'matching-round-1.txt'
    assert (await import_ready_file(subject, path)).status == 'imported'
    subject.process_file.assert_awaited_once_with(path.absolute())


async def test_completed_r2_does_not_wait_for_pruned_dependency():
    """Successful processing remains successful after R1 retention expires."""
    subject = manager()
    subject.is_file_processed.return_value = True
    result = await import_ready_file(subject, Path('2026-09-20-121000-fixture-round-2.txt'))
    assert result.status == 'imported' and result.message == 'Already processed'
    subject.process_file.assert_not_awaited()


async def test_bare_relative_file_uses_same_absolute_path_for_lookup_and_import(monkeypatch, tmp_path):
    """A parser lookup must not receive an empty directory for a bare filename."""
    monkeypatch.chdir(tmp_path)
    subject = manager(dependency='fixture-round-1.txt')
    path = Path('2026-09-20-121000-fixture-round-2.txt')
    await import_ready_file(subject, path)
    subject.parser.find_corresponding_round_1_file.assert_called_once_with(str(tmp_path / path))
    subject.process_file.assert_awaited_once_with(tmp_path / path)


@pytest.mark.parametrize('result,status', [
    ((True, 'Already processed'), 'imported'),
    ((False, 'malformed'), 'failed'),
    (RetryableImportFailure('offline'), 'retryable_failure'),
])
async def test_r1_preserves_canonical_outcomes(result, status):
    """R1 bypasses dependency lookup and retains failure classification."""
    subject = manager(result=result)
    actual = await import_ready_file(subject, Path('fixture-round-1.txt'))
    assert actual.status == status and actual.message == result[1]
    subject.parser.find_corresponding_round_1_file.assert_not_called()


async def test_cancellation_propagates():
    """Stopping the caller must not turn cancellation into a successful import."""
    subject = manager()
    subject.process_file.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await import_ready_file(subject, Path('fixture-round-1.txt'))


async def test_renamed_duplicate_reaches_canonical_marker_path():
    """Content deduplication remains reachable after R1 retention expires."""
    subject = manager(result=(True, 'Duplicate payload of original'))
    subject.find_processed_duplicate.return_value = '2026-09-20-121000-original-round-2.txt'
    path = Path('2026-09-20-121000-mirror-round-2.txt')
    result = await import_ready_file(subject, path)
    assert result.status == 'imported' and result.message == 'Duplicate payload of original'
    subject.find_processed_duplicate.assert_awaited_once_with(path.absolute())
    subject.process_file.assert_awaited_once_with(path.absolute())


@pytest.mark.parametrize('duplicate', ['2026-09-20-120000-map-round-1.txt', 'invalid'])
async def test_only_confirmed_round_two_duplicate_can_bypass_waiting(duplicate):
    """Identical R1 payload is not evidence that a zero-delta R2 was imported."""
    subject = manager()
    subject.find_processed_duplicate.return_value = duplicate
    result = await import_ready_file(subject, Path('2026-09-20-121000-map-round-2.txt'))
    assert result.status == 'waiting_for_r1'
    subject.process_file.assert_not_awaited()


@pytest.mark.parametrize('name', [
    'bad-round-2.txt', '2026-13-32-999999-goldrush-round-2.txt',
    '2026-02-29-120000-goldrush-round-2.txt', '2026-04-31-120000-map-round-2.txt',
    '2026-09-20-240000-map-round-2.txt', '2026-09-20-126000-map-round-2.txt',
    '2026-09-20-120060-map-round-2.txt', '0000-01-01-120000-map-round-2.txt',
])
async def test_malformed_round_two_uses_canonical_failure(name):
    """Invalid names must not be mistaken for a temporarily missing dependency."""
    subject = manager(result=(False, 'Parse error: invalid filename'))
    path = Path(name)
    result = await import_ready_file(subject, path)
    assert result.status == 'failed'
    subject.parser.find_corresponding_round_1_file.assert_not_called()
    subject.process_file.assert_awaited_once_with(path.absolute())


@pytest.mark.parametrize('stamp', ['2024-02-29-235959', '2026-01-01-000000'])
async def test_valid_calendar_boundaries_can_wait(stamp):
    """Leap-day and midnight inputs retain the dependency-waiting contract."""
    subject = manager()
    result = await import_ready_file(subject, Path(f'{stamp}-map-round-2.txt'))
    assert result.status == 'waiting_for_r1'
    subject.process_file.assert_not_awaited()
