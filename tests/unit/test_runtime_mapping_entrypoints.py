"""Trusted expectations survive all opt-in entrypoints; late metadata fails early."""

from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import runtime_import_attempt as attempt
from bot import runtime_import_batch as batch
from bot import runtime_import_cli as cli
from bot.community_stats_parser import C0RNP0RN3StatsParser
from tests.unit.test_runtime_identity_import import completed_identity_pair
from tests.unit.test_runtime_import_attempt import database
from tests.unit.test_runtime_import_cli import arguments
from tests.unit.test_runtime_round_identity import FIRST, SECOND


@pytest.mark.parametrize('identity,journal', [('bad', True), (SECOND, True), (FIRST, False), (FIRST, 1)])
async def test_bad_expected_envelope_never_opens_pool(tmp_path, monkeypatch, identity, journal):
    first, _ = completed_identity_pair(tmp_path)
    factory = AsyncMock()
    monkeypatch.setattr(attempt, 'create_import_pool', factory)
    with pytest.raises(ValueError):
        await attempt.run_import_once(database(), first, journal_enabled=journal, expected_identity=identity)
    factory.assert_not_awaited()


@pytest.mark.parametrize('map_name', ['supply', 'supply+', 'map.with-dot_1'])
async def test_owned_attempt_reaches_actual_sealed_binding(tmp_path, monkeypatch, map_name):
    first, second = completed_identity_pair(tmp_path, map_name=map_name)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock(return_value=(True, 'ok')))
    closed = []

    @asynccontextmanager
    async def session(*args, **kwargs):
        try:
            yield manager
        finally:
            closed.append(True)

    monkeypatch.setattr(attempt, 'open_import_session', session)
    result = await attempt.run_import_once(database(), second, first=first, journal_enabled=True,
                                         expected_identity=SECOND)
    assert result == (True, 'ok') and closed == [True]
    binding = manager.process_file.await_args.kwargs['runtime_binding']
    assert binding.identity == SECOND and binding.first.identity == FIRST
    assert binding.map_name == binding.first.map_name == map_name
    assert binding.generation == second.generation and binding.sha256 == second.sha256


@pytest.mark.parametrize('changes', [
    {'root': Path('relative')}, {'root': '/absolute-but-not-path'}, {'generation': 'X' * 32},
    {'filename': '../bad.txt'}, {'size': True}, {'size': 0}, {'size': 8 * 1024 * 1024 + 1},
    {'sha256': None}, {'sha256': 'A' * 64},
    {'filename': '2026-09-25-120000-supply+-round-2.txt'},
    {'filename': '2026-02-30-120000-supply-round-2.txt'},
    {'filename': '2026-09-25-250000-supply-round-2.txt'},
    {'filename': '2026-09-25-120000-oasis-round-2.txt'},
    {'filename': '2026-09-25-124501-supply-round-2.txt'},
    {'filename': '2026-09-25-115959-supply-round-2.txt'},
])
async def test_bad_late_artifact_prevents_all_attempts(tmp_path, monkeypatch, changes):
    first, second = completed_identity_pair(tmp_path)
    jobs = (batch.ImportJob(first, expected_identity=FIRST),
            batch.ImportJob(replace(second, **changes), first, SECOND))
    run = AsyncMock()
    monkeypatch.setattr(batch, 'run_import_once', run)
    with pytest.raises(ValueError):
        await batch.run_import_batch(None, jobs, journal_enabled=True)
    run.assert_not_awaited()


@pytest.mark.parametrize('map_name', ['x' * 65])
async def test_bound_map_contract_before_pool(tmp_path, monkeypatch, map_name):
    # Keep the receipt/content valid so this reaches the map alphabet guard.
    first, _ = completed_identity_pair(tmp_path, map_name=map_name)
    factory = AsyncMock()
    monkeypatch.setattr(attempt, 'create_import_pool', factory)
    with pytest.raises(ValueError, match='Invalid mapped map'):
        await attempt.run_import_once(database(), first, journal_enabled=True, expected_identity=FIRST)
    factory.assert_not_awaited()


@pytest.mark.parametrize('kind', ['missing_first', 'wrong_first_half', 'wrong_identity_half',
    'mixed', 'wrong_source', 'wrong_match', 'wrong_first_id', 'conflicting_first_artifact', 'journal_off'])
async def test_entire_bound_pair_preflight(tmp_path, monkeypatch, kind):
    first, second = completed_identity_pair(tmp_path)
    one, two = batch.ImportJob(first, expected_identity=FIRST), batch.ImportJob(second, first, SECOND)
    if kind == 'missing_first':
        two = replace(two, first=None)
    elif kind == 'wrong_first_half':
        two = replace(two, first=second)
    elif kind == 'wrong_identity_half':
        two = replace(two, expected_identity=FIRST)
    elif kind == 'mixed':
        two = replace(two, expected_identity=None)
    elif kind == 'conflicting_first_artifact':
        two = replace(two, first=replace(first, sha256='e' * 64))
    elif kind.startswith('wrong_'):
        field = {'wrong_source': 'source_id', 'wrong_match': 'match_id', 'wrong_first_id': 'first_round_id'}[kind]
        two = replace(two, expected_identity=replace(SECOND, **{field: 'e' * 32}))
    run = AsyncMock()
    monkeypatch.setattr(batch, 'run_import_once', run)
    with pytest.raises(ValueError):
        await batch.run_import_batch(None, (one, two), journal_enabled=kind != 'journal_off')
    run.assert_not_awaited()


async def test_bound_batch_forwards_identities_and_keeps_partial_outcome(tmp_path, monkeypatch):
    first, second = completed_identity_pair(tmp_path)
    jobs = (batch.ImportJob(first, expected_identity=FIRST), batch.ImportJob(second, first, SECOND))
    failure = (False, 'DB failure after first commit')
    run = AsyncMock(side_effect=[(True, 'ok'), failure])
    monkeypatch.setattr(batch, 'run_import_once', run)
    assert await batch.run_import_batch(None, jobs, journal_enabled=True) == ((True, 'ok'), failure)
    assert [call.kwargs['expected_identity'] for call in run.await_args_list] == [FIRST, SECOND]
    assert run.await_args_list[1].kwargs['first'] == first


async def test_r2_only_batch_accepts_external_first_mapping(tmp_path, monkeypatch):
    first, second = completed_identity_pair(tmp_path)
    run = AsyncMock(return_value=(True, 'ok'))
    monkeypatch.setattr(batch, 'run_import_once', run)
    assert await batch.run_import_batch(None, (batch.ImportJob(second, first, SECOND),),
                                        journal_enabled=True) == ((True, 'ok'),)


@pytest.mark.parametrize('kind', ['one_wire', 'malformed', 'swapped', 'cross_match', 'journal_off'])
def test_bad_cli_expected_pair_is_argument_error_before_batch(tmp_path, monkeypatch, kind):
    args = arguments(tmp_path) + ['--expected-round-identities', FIRST.encode(), SECOND.encode()]
    if kind == 'one_wire':
        args.pop()
    elif kind == 'malformed':
        args[-1] = 'invalid'
    elif kind == 'swapped':
        args[-2:] = [SECOND.encode(), FIRST.encode()]
    elif kind == 'cross_match':
        args[-1] = replace(SECOND, match_id='e' * 32).encode()
    else:
        args[args.index('--journal') + 1] = 'disabled'
    run = AsyncMock()
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    with pytest.raises(SystemExit) as error:
        cli.main(args)
    assert error.value.code == 2
    run.assert_not_awaited()


@pytest.mark.parametrize('bound', [True, False])
def test_cli_transmits_independently_supplied_pair(tmp_path, monkeypatch, bound):
    args = arguments(tmp_path)
    if bound:
        args += ['--expected-round-identities', FIRST.encode(), SECOND.encode()]
    run = AsyncMock(return_value=((True, 'ok'), (True, 'ok')))
    monkeypatch.setattr(cli, 'run_exclusive_import_batch', run)
    assert cli.main(args) == 0
    _, jobs = run.await_args.args
    assert [job.expected_identity for job in jobs] == ([FIRST, SECOND] if bound else [None, None])
