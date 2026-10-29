"""Uncommitted writer state and permissive receipts cannot authorize completion."""

import hashlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from shared.runtime_proximity_admission import publish_proximity_admission
from shared.runtime_proximity_commit import inspect_proximity_commit
from shared.runtime_source_reservation import reserve_source_generation
from tests.unit.test_runtime_proximity_admission import GENERATION, NAME, SOURCE
from tests.unit.test_runtime_proximity_admission import OPTIONS as ADMISSION_OPTIONS

PAYLOAD = b'# map=fixture\n# round=1\n'
HASH = hashlib.sha256(PAYLOAD).hexdigest()
OPTIONS = {**ADMISSION_OPTIONS, 'expected_sha256': HASH,
           'completion': {**ADMISSION_OPTIONS['completion'], 'bytes': len(PAYLOAD)}}


@pytest.fixture
def setup(tmp_path):
    tmp_path.chmod(0o700)
    directory = reserve_source_generation(tmp_path, GENERATION)
    source = directory / NAME
    source.write_bytes(PAYLOAD)
    source.chmod(0o600)
    phases = []

    @asynccontextmanager
    async def transaction(**options):
        assert options == dict(isolation='read_committed', readonly=True)
        phases.append('open')
        yield
        phases.append('close')

    observer = SimpleNamespace(is_in_transaction=Mock(return_value=False),
        transaction=transaction, fetchrow=AsyncMock(return_value=dict(
            file_hash=HASH, runtime_parent_gate=True, aggregates_applied=True, linked_round_id=10)))
    return directory, observer, phases


async def inspect(directory, observer):
    return await inspect_proximity_commit(directory, source_id=SOURCE, generation=GENERATION, observer=observer)


async def test_admission_required_before_database_access(setup):
    directory, observer, phases = setup
    assert (await inspect(directory, observer)).status == 'missing_admission'
    assert phases == []
    observer.fetchrow.assert_not_awaited()


async def test_matching_receipt_in_fresh_readonly_transaction(setup):
    directory, observer, phases = setup
    path = publish_proximity_admission(directory, **OPTIONS)
    before = path.read_bytes()
    assert (await inspect(directory, observer)).status == 'committed'
    assert phases == ['open', 'close']
    assert observer.fetchrow.call_args.args[1] == NAME
    assert '$1' in observer.fetchrow.call_args.args[0]
    assert path.read_bytes() == before
    assert set(directory.iterdir()) == {path, directory / NAME}


@pytest.mark.parametrize('value', [True, None, 0, 'false'])
async def test_existing_or_unknown_transaction_refused(setup, value):
    directory, observer, phases = setup
    publish_proximity_admission(directory, **OPTIONS)
    observer.is_in_transaction.return_value = value
    with pytest.raises(RuntimeError, match='outside any transaction'):
        await inspect(directory, observer)
    observer.fetchrow.assert_not_awaited()
    assert phases == []


@pytest.mark.parametrize('row,status,reason', [
    (None, 'not_committed', 'receipt_not_visible'),
    (dict(file_hash='0' * 64, runtime_parent_gate=True, aggregates_applied=True), 'conflict', 'source_identity_conflict'),
    (dict(file_hash=None, runtime_parent_gate=True, aggregates_applied=True), 'conflict', 'source_identity_conflict'),
    (dict(file_hash=HASH, runtime_parent_gate=False, aggregates_applied=True), 'conflict', 'strict_provenance_missing'),
    (dict(file_hash=HASH, runtime_parent_gate=1, aggregates_applied=True), 'conflict', 'strict_provenance_missing'),
    (dict(file_hash=HASH, runtime_parent_gate=True, aggregates_applied=False), 'conflict', 'aggregates_not_confirmed'),
    (dict(file_hash=HASH, runtime_parent_gate=True, aggregates_applied=None), 'conflict', 'aggregates_not_confirmed'),
    (dict(file_hash=HASH, runtime_parent_gate=True, aggregates_applied=True, linked_round_id=None), 'conflict', 'strict_provenance_missing'),
])
async def test_missing_or_conflicting_receipts_never_confirm(setup, row, status, reason):
    directory, observer, phases = setup
    publish_proximity_admission(directory, **OPTIONS)
    observer.fetchrow.return_value = row
    result = await inspect(directory, observer)
    assert (result.status, result.reason) == (status, reason)


async def test_database_failure_propagates(setup):
    directory, observer, phases = setup
    publish_proximity_admission(directory, **OPTIONS)
    observer.fetchrow.side_effect = OSError('fixture connection unavailable')
    with pytest.raises(OSError, match='fixture connection unavailable'):
        await inspect(directory, observer)
