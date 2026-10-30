"""Persistent outcomes do not become stale permanent completion markers."""

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from shared import runtime_proximity_queue as queue
from shared.proximity_import import ProximityImportResult
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_commit import ProximityCommitObservation as Commit
from shared.runtime_proximity_ingest import CompletedProximityImportResult as Observation
from shared.runtime_source_reservation import reserve_source_generation
from tests.unit.test_runtime_proximity_admission import GENERATION, OPTIONS, SOURCE


@pytest.fixture
def setup(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    inspect = AsyncMock(return_value=Commit('not_committed', 'receipt_not_visible'))
    importer = AsyncMock(return_value=Observation('missing_manifest'))
    monkeypatch.setattr(queue, 'inspect_proximity_commit', inspect)
    monkeypatch.setattr(queue, 'import_admitted_proximity_file', importer)
    options = dict(source_id=SOURCE, generation=GENERATION, adapter=object(), observer=object(),
                   gametimes_dir=tmp_path)
    return directory, inspect, importer, options


async def test_missing_admission_never_checks_database(setup):
    directory, inspect, importer, options = setup
    assert (await queue.process_proximity_once(directory, now=1000, **options)).reason == 'missing_admission'
    inspect.assert_not_awaited()
    importer.assert_not_awaited()

    script = '''
import asyncio, json, sys
from dataclasses import asdict
from pathlib import Path
from shared.runtime_proximity_queue import process_proximity_once
value = asyncio.run(process_proximity_once(Path(sys.argv[1]), source_id=sys.argv[2],
    generation=sys.argv[3], now=9999, adapter=object(), observer=object(),
    gametimes_dir=Path(sys.argv[1])))
print(json.dumps(asdict(value)))
'''
    # Missing admission is also recoverable without a DB in a fresh process.
    completed = subprocess.run([sys.executable, '-c', script, str(directory), SOURCE, GENERATION],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, check=True, timeout=10)
    assert json.loads(completed.stdout)['reason'] == 'missing_admission'


async def test_retry_record_recovered_and_cooldown_preserved(setup):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    result = await queue.process_proximity_once(directory, now=1000, **options)
    assert (result.action, result.reason, result.attempt) == ('retry', 'missing_manifest', 1)
    record = json.loads((directory / '.proximity-outcome-001.json').read_text())
    assert record['action'] == 'retry' and record['attempt'] == 1
    assert (await queue.process_proximity_once(directory, now=1029, **options)).reason == 'not_due'
    assert importer.await_count == 1
    assert (await queue.process_proximity_once(directory, now=1030, **options)).attempt == 2


async def test_declared_identity_mapping_hold_is_explicit_persistent_and_not_retried(setup):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    reason = 'declared_identity_mapping_pending'
    importer.return_value = Observation('match', ProximityImportResult(False, None, pending_reason=reason))
    result = await queue.process_proximity_once(directory, now=1000, **options)
    assert (result.action, result.reason) == ('reconcile', reason)
    record = json.loads((directory / '.proximity-outcome-001.json').read_text())
    assert record['action'] == 'reconcile' and record['reason'] == reason
    inspect.reset_mock()
    importer.reset_mock()
    result = await queue.process_proximity_once(directory, now=9999, **options)
    assert (result.action, result.reason) == ('reconcile', reason)
    inspect.assert_not_awaited()
    importer.assert_not_awaited()


async def test_persisted_conflict_blocks_even_if_importer_later_changes(setup):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    importer.return_value = Observation('content_conflict')
    assert (await queue.process_proximity_once(directory, now=1000, **options)).action == 'reconcile'
    inspect.reset_mock()
    importer.reset_mock()
    importer.return_value = Observation('missing_manifest')
    result = await queue.process_proximity_once(directory, now=9999, **options)
    assert (result.action, result.reason) == ('reconcile', 'content_conflict')
    inspect.assert_not_awaited()
    importer.assert_not_awaited()
    script = '''
import asyncio, json, sys
from dataclasses import asdict
from pathlib import Path
from shared.runtime_proximity_queue import process_proximity_once
value = asyncio.run(process_proximity_once(Path(sys.argv[1]), source_id=sys.argv[2],
    generation=sys.argv[3], now=9999, adapter=object(), observer=object(),
    gametimes_dir=Path(sys.argv[1])))
print(json.dumps(asdict(value)))
'''
    completed = subprocess.run([sys.executable, '-c', script, str(directory), SOURCE, GENERATION],
        cwd=Path(__file__).resolve().parents[2], text=True, capture_output=True, check=True, timeout=10)
    assert json.loads(completed.stdout) == dict(action='reconcile', reason='content_conflict', attempt=1)


async def test_committed_history_rechecked_and_missing_receipt_retried(setup):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    importer.return_value = Observation('match', ProximityImportResult(True, {}, round_id=10, gaming_session_id=20))
    inspect.side_effect = [Commit('not_committed', 'receipt_not_visible'),
                          Commit('committed', 'matching_strict_receipt_visible')]
    assert (await queue.process_proximity_once(directory, now=1000, **options)).action == 'committed'
    inspect.side_effect = None
    inspect.return_value = Commit('committed', 'matching_strict_receipt_visible')
    assert (await queue.process_proximity_once(directory, now=1030, **options)).attempt is None
    assert importer.await_count == 1
    # Simulate restored DB, while the earlier committed outcome stays on disk.
    inspect.return_value = Commit('not_committed', 'receipt_not_visible')
    result = await queue.process_proximity_once(directory, now=1030, **options)
    assert (result.action, result.reason, result.attempt) == ('retry', 'receipt_not_visible', 2)
    assert importer.await_count == 2
    assert json.loads((directory / '.proximity-outcome-001.json').read_text())['action'] == 'committed'


@pytest.mark.parametrize('error', [OSError('fixture DB unavailable'), asyncio.CancelledError()])
async def test_unavailable_verification_never_uses_old_success(setup, error):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    importer.return_value = Observation('match', ProximityImportResult(True, {}, round_id=10, gaming_session_id=20))
    inspect.side_effect = [Commit('not_committed', 'receipt_not_visible'),
                          Commit('committed', 'matching_strict_receipt_visible')]
    assert (await queue.process_proximity_once(directory, now=1000, **options)).action == 'committed'
    original = {p.name: p.read_bytes() for p in directory.iterdir()}
    importer.reset_mock()
    inspect.side_effect = error
    with pytest.raises(type(error)):
        await queue.process_proximity_once(directory, now=2000, **options)
    importer.assert_not_awaited()
    assert {p.name: p.read_bytes() for p in directory.iterdir()} == original


@pytest.mark.parametrize('kind', ['identity', 'attempt', 'schema', 'reason', 'corrupt', 'permissions', 'unspent'])
async def test_bad_outcomes_cannot_be_ignored(setup, kind):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    await queue.process_proximity_once(directory, now=1000, **options)
    path = directory / '.proximity-outcome-001.json'
    data = json.loads(path.read_text())
    if kind == 'identity':
        data['identity_sha256'] = '0' * 64
    elif kind == 'attempt':
        data['attempt'] = True
    elif kind == 'schema':
        data['version'] = 2
    elif kind == 'reason':
        data['reason'] = 'unexpected secret error'
    elif kind == 'unspent':
        path = directory / '.proximity-outcome-002.json'
        data['attempt'] = 2
    path.write_text('{' if kind == 'corrupt' else json.dumps(data))
    path.chmod(0o600)
    if kind == 'permissions':
        path.chmod(0o644)
    with pytest.raises(ValueError):
        await queue.process_proximity_once(directory, now=1030, **options)
    assert importer.await_count == 1


async def test_outcome_publication_failure_does_not_report_success(setup, monkeypatch):
    directory, inspect, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)

    def failed(*args):
        raise OSError('fixture outcome fsync failed')

    monkeypatch.setattr(queue, '_publish_file', failed)
    with pytest.raises(OSError, match='outcome fsync failed'):
        await queue.process_proximity_once(directory, now=1000, **options)
    assert (directory / '.proximity-attempt-001.json').exists()
    assert not (directory / '.proximity-outcome-001.json').exists()
