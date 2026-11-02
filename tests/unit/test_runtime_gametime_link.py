"""Durable link policy gates, exact receipt comparison and owned transaction seams."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot import runtime_gametime_link as link
from bot.runtime_gametime_correlation import GametimeCorrelationObservation, verified_timing_binding
from tests.unit.test_runtime_gametime_correlation import setup


@pytest.fixture
def case(tmp_path, monkeypatch):
    source = setup(tmp_path)
    state = SimpleNamespace(legacy=False, isolation='read committed', existing=None, create=True, phases=[])
    observed = GametimeCorrelationObservation('canonical_target_verified', 'fixture', 11, 20, 7)
    check = AsyncMock(return_value=observed)
    monkeypatch.setattr(link, 'inspect_timing_snapshot', check)
    lock = AsyncMock()
    monkeypatch.setattr(link, 'lock_correction_identity', lock)

    async def fetchval(sql, *args):
        if sql == 'SHOW transaction_isolation':
            return state.isolation
        assert sql.startswith('SELECT 1 FROM lua_correction_receipts')
        return 1 if state.legacy else None

    async def fetchrow(sql, *args):
        if sql.startswith('INSERT INTO'):
            assert lock.await_count > 0
            return args if state.create else None
        assert 'FROM runtime_gametime_links' in sql
        return state.existing

    @asynccontextmanager
    async def transaction(**options):
        assert options in ({}, dict(isolation='repeatable_read', readonly=True))
        state.phases.append('open')
        try:
            yield connection
        finally:
            state.phases.append('close')

    connection = SimpleNamespace(fetchval=AsyncMock(side_effect=fetchval), fetchrow=AsyncMock(side_effect=fetchrow),
        transaction=transaction, is_in_transaction=Mock(return_value=False))
    with source.path.open('rb') as stream:
        timing, projection = verified_timing_binding(stream.fileno(), **source.args)
    state.expected = link._values(timing, source.args['expected_identity'], projection, observed)  # noqa: SLF001
    return SimpleNamespace(source=source, state=state, connection=connection, check=check, lock=lock,
                           adapter=SimpleNamespace(transaction=transaction))


async def run(case, *, observe=False):
    with case.source.path.open('rb') as stream:
        fn = link.inspect_declared_gametime_link if observe else link.link_declared_gametime
        return await fn(case.connection if observe else case.adapter, stream.fileno(), **case.source.args)


@pytest.mark.parametrize('observe', [False, True])
async def test_legacy_correction_receipt_never_adopted(case, observe):
    case.state.legacy = True
    assert (await run(case, observe=observe)).status == 'conflict'
    case.connection.fetchrow.assert_not_awaited()


@pytest.mark.parametrize('isolation', ['repeatable read', 'serializable', None])
async def test_writer_requires_explicit_isolation(case, isolation):
    case.state.isolation = isolation
    with pytest.raises(ValueError, match='read committed'):
        await run(case)
    case.check.assert_not_awaited()


async def test_new_and_exact_replay_and_independent_observer(case):
    assert (await run(case)).status == 'linked'
    assert case.check.await_args.kwargs == {'lock': True}
    case.state.create = False
    case.state.existing = case.state.expected
    assert (await run(case)).status == 'already_linked'
    assert (await run(case, observe=True)).status == 'linked'
    assert case.check.await_args.kwargs == {'lock': False}
    assert case.state.phases == ['open', 'close'] * 3


@pytest.mark.parametrize('index', range(9))
@pytest.mark.parametrize('observe', [False, True])
async def test_every_durable_field_must_match(case, index, observe):
    case.state.create = False
    fields = list(case.state.expected)
    fields[index] = 'wrong'
    case.state.existing = fields
    if observe:
        assert (await run(case, observe=True)).status == 'conflict'
    else:
        with pytest.raises(ValueError, match='conflicts'):
            await run(case)


@pytest.mark.parametrize('status', ['missing_retention', 'mapping_pending', 'conflict'])
@pytest.mark.parametrize('observe', [False, True])
async def test_unverified_chain_never_reads_or_writes_link(case, status, observe):
    case.check.return_value = GametimeCorrelationObservation(status, 'fixture')
    assert (await run(case, observe=observe)).status == status
    case.connection.fetchrow.assert_not_awaited()


async def test_absent_link_is_not_committed(case):
    assert (await run(case, observe=True)).status == 'not_linked'
    case.state.create = False
    with pytest.raises(ValueError, match='conflicts'):
        await run(case)


async def test_observer_rejects_owned_transaction(case):
    case.connection.is_in_transaction.return_value = True
    with pytest.raises(RuntimeError, match='outside'):
        await run(case, observe=True)
    case.check.assert_not_awaited()
