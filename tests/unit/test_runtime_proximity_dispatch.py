"""Pacing is enforced before import; classification never upgrades commit scope."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared import runtime_proximity_dispatch as dispatch
from shared.proximity_import import ProximityImportResult
from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_ingest import CompletedProximityImportResult as Observation
from shared.runtime_proximity_retry import reserve_proximity_retry
from shared.runtime_source_reservation import reserve_source_generation
from tests.unit.test_runtime_proximity_admission import GENERATION, OPTIONS, SOURCE


@pytest.fixture
def setup(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    importer = AsyncMock(return_value=Observation('missing_manifest'))
    monkeypatch.setattr(dispatch, 'import_admitted_proximity_file', importer)
    kwargs = dict(source_id=SOURCE, generation=GENERATION, adapter=object(), gametimes_dir=tmp_path)
    return directory, importer, kwargs


@pytest.mark.parametrize('state,action', [('missing_manifest', 'retry'), ('missing_content', 'retry'),
    ('content_conflict', 'reconcile'), ('receipt_conflict', 'reconcile')])
def test_manifest_classification(state, action):
    assert dispatch.classify_proximity_import(Observation(state)) == (action, state)


@pytest.mark.parametrize('pending,action,reason', [
    ('parent_missing', 'retry', 'parent_missing'), ('session_missing', 'retry', 'session_missing'),
    ('parent_ambiguous', 'reconcile', 'parent_ambiguous'),
    (None, 'reconcile', 'unclassified_import_failure'),
    ('unexpected private detail', 'reconcile', 'unclassified_import_failure'),
])
def test_only_known_absence_is_retryable(pending, action, reason):
    result = Observation('match', ProximityImportResult(False, None, pending_reason=pending))
    assert dispatch.classify_proximity_import(result) == (action, reason)


def test_success_is_not_committed():
    result = Observation('match', ProximityImportResult(True, {}, round_id=10, gaming_session_id=20))
    assert dispatch.classify_proximity_import(result) == ('verify_commit', 'transaction_scoped_success')


@pytest.mark.parametrize('override', [dict(round_id=None), dict(round_id=True), dict(round_id=0),
    dict(gaming_session_id=None), dict(gaming_session_id=-1), dict(pending_reason='parent_missing')])
def test_inconsistent_success_rejected(override):
    imported = ProximityImportResult(True, {}, round_id=10, gaming_session_id=20)
    with pytest.raises(ValueError):
        dispatch.classify_proximity_import(Observation('match', replace(imported, **override)))


@pytest.mark.parametrize('result', [None, Observation('unknown'), Observation('match'),
    Observation('missing_manifest', ProximityImportResult(True, {})),
    Observation('match', ProximityImportResult(1, {}))])
def test_unknown_or_inconsistent_observation_rejected(result):
    with pytest.raises(ValueError):
        dispatch.classify_proximity_import(result)


async def test_real_pacing_before_import_and_lock_through_await(setup):
    directory, importer, options = setup
    assert (await dispatch.dispatch_proximity_once(directory, now=1000, **options)).reason == 'missing_admission'
    importer.assert_not_awaited()
    publish_proximity_admission(directory, **OPTIONS)

    async def observe(*args, **kwargs):
        await asyncio.sleep(0)
        with reserve_proximity_retry(directory, source_id=SOURCE, generation=GENERATION, now=9000) as permit:
            assert permit.status == 'busy'
        return Observation('missing_manifest')

    importer.side_effect = observe
    first = await dispatch.dispatch_proximity_once(directory, now=1000, **options)
    assert (first.action, first.reason, first.permit.attempt) == ('retry', 'missing_manifest', 1)
    second = await dispatch.dispatch_proximity_once(directory, now=1029, **options)
    assert second.action == 'deferred' and second.reason == 'not_due'
    assert importer.await_count == 1
    await dispatch.dispatch_proximity_once(directory, now=1030, **options)
    assert importer.await_count == 2
    print('Dispatch proof: persistent permit before importer, local lock across await, '
          'cooldown excludes importer; due retry retains attempt count')


@pytest.mark.parametrize('error', [asyncio.CancelledError(), OSError('fixture unavailable'), ValueError('conflict')])
async def test_exception_propagates_and_spends_attempt(setup, error):
    directory, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    importer.side_effect = error
    with pytest.raises(type(error)):
        await dispatch.dispatch_proximity_once(directory, now=1000, **options)
    assert (await dispatch.dispatch_proximity_once(directory, now=1001, **options)).reason == 'not_due'
    assert importer.await_count == 1


async def test_exhaustion_requires_review_without_import(setup):
    directory, importer, options = setup
    publish_proximity_admission(directory, **OPTIONS)
    now = 1000
    for _ in range(64):
        with reserve_proximity_retry(directory, source_id=SOURCE, generation=GENERATION, now=now) as permit:
            now = permit.retry_at
    result = await dispatch.dispatch_proximity_once(directory, now=now, **options)
    assert (result.action, result.reason) == ('reconcile', 'exhausted')
    importer.assert_not_awaited()


async def test_real_dispatch_to_completion_gate_never_opens_database(tmp_path):
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    publish_proximity_admission(directory, **OPTIONS)

    def forbidden_transaction():
        raise AssertionError('Missing completion must not enter database')

    options = dict(source_id=SOURCE, generation=GENERATION,
                   adapter=SimpleNamespace(transaction=forbidden_transaction), gametimes_dir=tmp_path)
    before = (directory / '.proximity-admission.json').read_bytes()
    first = await dispatch.dispatch_proximity_once(directory, now=1000, **options)
    assert (first.action, first.reason) == ('retry', 'missing_manifest')
    second = await dispatch.dispatch_proximity_once(directory, now=1001, **options)
    assert (second.action, second.reason) == ('deferred', 'not_due')
    assert len(list(directory.glob('.proximity-attempt-*.json'))) == 1
    assert (directory / '.proximity-admission.json').read_bytes() == before
    print('Real dispatch proof: durable admission -> permit -> actual completion '
          'gate -> retry -> not_due; no DB access and source identity unchanged')
