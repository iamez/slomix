"""Completion gates cannot become database import acknowledgements."""

import asyncio
import hashlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared import proximity_import
from shared.runtime_completion_manifest import record_proximity_completion_once
from shared.runtime_proximity_ingest import import_completed_proximity_file
from shared.runtime_spool import publish_proximity_file

NAME = '2026-10-05-120000-fixture-round-1_engagements.txt'
PAYLOAD = b'fixture'
HASH = hashlib.sha256(PAYLOAD).hexdigest()
RECEIPT = dict(version=1, filename=NAME, bytes=len(PAYLOAD), state='writer_closed')


@pytest.fixture
def source(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    publish_proximity_file(tmp_path, NAME, [PAYLOAD], expected_size=len(PAYLOAD), expected_sha256=HASH)
    canonical = AsyncMock(return_value=proximity_import.ProximityImportResult(True, {}))
    monkeypatch.setattr(proximity_import, 'import_proximity_file', canonical)
    options = dict(adapter=SimpleNamespace(transaction=AsyncMock()), session_date=date(2026, 10, 5),
                   gametimes_dir=tmp_path, expected_size=len(PAYLOAD), expected_sha256=HASH)
    return tmp_path, canonical, options


@pytest.mark.parametrize('state', ['missing_manifest', 'missing_content', 'content_conflict', 'receipt_conflict'])
async def test_completion_gates_before_database(source, state):
    directory, canonical, options = source
    if state != 'missing_manifest':
        record_proximity_completion_once(directory, RECEIPT, expected_sha256=HASH)
    if state == 'missing_content':
        (directory / NAME).rename(directory / 'retained-fixture')
    elif state == 'content_conflict':
        (directory / NAME).write_bytes(b'changed')
    elif state == 'receipt_conflict':
        options['expected_sha256'] = '0' * 64
    before = {p.name: (p.stat().st_ino, p.read_bytes()) for p in directory.iterdir()}
    result = await import_completed_proximity_file(directory, NAME, **options)
    assert result.manifest_status == state and result.import_result is None
    canonical.assert_not_awaited()
    assert {p.name: (p.stat().st_ino, p.read_bytes()) for p in directory.iterdir()} == before


@pytest.mark.parametrize('result', [
    proximity_import.ProximityImportResult(True, {}, round_id=10, gaming_session_id=20),
    proximity_import.ProximityImportResult(False, None),
    proximity_import.ProximityImportResult(False, None, pending_reason='parent_missing'),
    proximity_import.ProximityImportResult(False, None, pending_reason='parent_ambiguous'),
])
async def test_matching_manifest_preserves_strict_import_outcome(source, result):
    directory, canonical, options = source
    record_proximity_completion_once(directory, RECEIPT, expected_sha256=HASH)
    canonical.return_value = result
    outcome = await import_completed_proximity_file(directory, NAME, **options)
    assert outcome.manifest_status == 'match' and outcome.import_result is result
    canonical.assert_awaited_once_with(directory / NAME, **options, max_bytes=8 * 1024 * 1024,
                                       require_linked_parent=True)


@pytest.mark.parametrize('failure', [RuntimeError('database unavailable'), asyncio.CancelledError()])
async def test_failure_is_not_success_or_missing_data(source, failure):
    directory, canonical, options = source
    record_proximity_completion_once(directory, RECEIPT, expected_sha256=HASH)
    canonical.side_effect = failure
    with pytest.raises(type(failure)):
        await import_completed_proximity_file(directory, NAME, **options)
    assert len(list(directory.iterdir())) == 2


@pytest.mark.parametrize('override', [
    {'expected_size': True}, {'expected_size': 0}, {'expected_sha256': None},
    {'expected_sha256': 'invalid'}, {'max_bytes': 1}, {'session_date': None}, {'adapter': None},
])
async def test_invalid_caller_rejected_even_without_manifest(source, override):
    directory, canonical, options = source
    with pytest.raises((TypeError, ValueError)):
        await import_completed_proximity_file(directory, NAME, **(options | override))
    canonical.assert_not_awaited()


async def test_malformed_manifest_propagates_without_import(source):
    directory, canonical, options = source
    path = directory / (NAME + '.complete.json')
    path.write_text('{')
    path.chmod(0o600)
    with pytest.raises(ValueError, match='Malformed'):
        await import_completed_proximity_file(directory, NAME, **options)
    canonical.assert_not_awaited()


async def test_stats_filename_does_not_enter_proximity_import(source):
    directory, canonical, options = source
    with pytest.raises(ValueError, match='filename'):
        await import_completed_proximity_file(directory, NAME.replace('_engagements', ''), **options)
    canonical.assert_not_awaited()


@pytest.mark.parametrize('enabled', [False, True])
@pytest.mark.parametrize('complete', [False, True])
async def test_declared_policy_preserves_legacy_manifest_gated_import(source, enabled, complete):
    from shared.runtime_proximity_admission import publish_proximity_admission
    from shared.runtime_proximity_ingest import import_admitted_proximity_file
    from shared.runtime_source_reservation import reserve_source_generation

    root, canonical, options = source
    generation = '8' * 32
    directory = reserve_source_generation(root, generation)
    publish_proximity_admission(directory, source_id='fixture', generation=generation,
        completion=RECEIPT, expected_sha256=HASH, session_date=options['session_date'])
    if complete:
        publish_proximity_file(directory, NAME, [PAYLOAD], expected_size=len(PAYLOAD), expected_sha256=HASH)
        record_proximity_completion_once(directory, RECEIPT, expected_sha256=HASH)
    result = await import_admitted_proximity_file(directory, source_id='fixture',
        generation=generation, adapter=options['adapter'], gametimes_dir=root,
        allow_declared_mapping=enabled)
    assert result.manifest_status == ('match' if complete else 'missing_manifest')
    if complete:
        canonical.assert_awaited_once()
        assert canonical.call_args.kwargs['require_linked_parent'] is True
        assert 'declared_binding' not in canonical.call_args.kwargs
    else:
        canonical.assert_not_awaited()
