"""Filesystem verification must gate all calls into the database importer."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from shared import runtime_ingest
from shared.runtime_import import ImportStepResult
from shared.runtime_ingest import import_verified_file
from shared.runtime_spool import publish_stats_file

NAME = '2026-09-20-120000-map-round-1.txt'
DIGEST = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'


async def ingest(directory):
    """Use fixed source metadata independently of local contents."""
    return await import_verified_file(None, directory, NAME, expected_size=3, expected_sha256=DIGEST)


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
    importer.assert_awaited_once_with(None, path.absolute())


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
