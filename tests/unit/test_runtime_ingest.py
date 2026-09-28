"""Filesystem verification must gate all calls into the database importer."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared import runtime_ingest
from shared.runtime_import import ImportStepResult
from shared.runtime_ingest import ExpectedStatsIdentity, import_verified_file
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-map-round-1.txt'
DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
MANAGER = SimpleNamespace(parser=SimpleNamespace(allow_legacy_r1_fallback=False))


async def ingest(directory):
    """Use fixed source metadata independently of local contents."""
    return await import_verified_file(MANAGER, directory, NAME, expected_size=3, expected_sha256=DIGEST)


@pytest.mark.parametrize('present', [False, True])
async def test_absence_and_conflict_never_import(tmp_path, monkeypatch, present):
    """No importer calls or markers are permitted for unverified content."""
    importer = AsyncMock()
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    if present:
        publish_stats_file(tmp_path, NAME, [b'xyz'], expected_size=3)
    result = await ingest(tmp_path)
    assert result.capture_status == ('conflict' if present else 'missing')
    assert result.import_result is None
    importer.assert_not_awaited()


@pytest.mark.parametrize('status', ['imported', 'waiting_for_r1', 'retryable_failure', 'failed'])
async def test_verified_content_preserves_import_outcome(tmp_path, monkeypatch, status):
    """Matching bytes are not automatically successful database ingestion."""
    path = publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3)
    expected = ImportStepResult(status, 'fixture outcome')
    importer = AsyncMock(return_value=expected)
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    result = await ingest(tmp_path)
    assert result.capture_status == 'match' and result.import_result is expected
    assert result.dependency_status == 'not_required'
    importer.assert_awaited_once_with(MANAGER, path.absolute())


async def test_cancellation_propagates(tmp_path, monkeypatch):
    """Cancellation is not a failed or successful acknowledged import."""
    publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3)
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', AsyncMock(side_effect=asyncio.CancelledError))
    with pytest.raises(asyncio.CancelledError):
        await ingest(tmp_path)


async def test_unavailable_spool_never_imports(tmp_path, monkeypatch):
    """Directory failure propagates rather than looking like an empty queue."""
    importer = AsyncMock()
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    with pytest.raises(FileNotFoundError):
        await ingest(tmp_path / 'absent')
    importer.assert_not_awaited()


@pytest.mark.parametrize('state', ['unverified', 'missing', 'conflict', 'match'])
async def test_selected_dependency_requires_trusted_matching_identity(tmp_path, monkeypatch, state):
    r2 = '2026-09-20-121000-map-round-2.txt'
    publish_stats_file(tmp_path, r2, [b'abc'], expected_size=3)
    if state != 'missing':
        publish_stats_file(tmp_path, NAME, [b'xyz' if state == 'conflict' else b'abc'], expected_size=3)
    manager = SimpleNamespace(parser=SimpleNamespace(
        allow_legacy_r1_fallback=False,
        find_corresponding_round_1_file=Mock(return_value=str(tmp_path / NAME)),
    ))
    importer = AsyncMock(return_value=ImportStepResult('imported', 'ok'))
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    result = await import_verified_file(
        manager, tmp_path, r2, expected_size=3, expected_sha256=DIGEST,
        expected_r1=None if state == 'unverified' else {NAME: ExpectedStatsIdentity(3, DIGEST)},
    )
    assert result.capture_status == 'match' and result.dependency_status == state
    if state == 'match':
        importer.assert_awaited_once()
    else:
        assert result.import_result is None
        importer.assert_not_awaited()


async def test_selected_dependency_outside_spool_fails_closed(tmp_path, monkeypatch):
    r2 = '2026-09-20-121000-map-round-2.txt'
    publish_stats_file(tmp_path, r2, [b'abc'], expected_size=3)
    manager = SimpleNamespace(parser=SimpleNamespace(
        allow_legacy_r1_fallback=False,
        find_corresponding_round_1_file=Mock(return_value=str(tmp_path.parent / NAME)),
    ))
    importer = AsyncMock()
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    with pytest.raises(ValueError, match='inside the verified spool'):
        await import_verified_file(manager, tmp_path, r2, expected_size=3, expected_sha256=DIGEST)
    importer.assert_not_awaited()


async def test_legacy_parser_cannot_enter_verified_import(tmp_path, monkeypatch):
    """Require explicit isolation at construction, not temporary parser mutation."""
    publish_stats_file(tmp_path, NAME, [b'abc'], expected_size=3)
    importer = AsyncMock()
    monkeypatch.setattr(runtime_ingest, 'import_ready_file', importer)
    manager = SimpleNamespace(parser=SimpleNamespace(allow_legacy_r1_fallback=True))
    with pytest.raises(ValueError, match='spool-only R1'):
        await import_verified_file(manager, tmp_path, NAME, expected_size=3, expected_sha256=DIGEST)
    importer.assert_not_awaited()
