"""Explicit bounded stats mapping inputs and strict admission before any DB."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.community_stats_parser import C0RNP0RN3StatsParser
from bot.runtime_completed_import import import_completed_round
from bot.runtime_round_mapping import StatsRoundBinding
from tests.unit.test_runtime_identity_contract import FIRST, SECOND
from tests.unit.test_runtime_identity_import import completed_identity_pair


def first_binding():
    return StatsRoundBinding(FIRST, '1' * 32, '2026-09-25-120000-supply-round-1.txt', 100, 'a' * 64, 'supply')


@pytest.mark.parametrize('changes', [
    {'identity': None}, {'size': True}, {'size': 0}, {'size': 8388609},
    {'sha256': 'a' * 63}, {'generation': 'g' * 32}, {'generation': None},
    {'filename': '../file'}, {'filename': '2026-09-25-120000-supply-round-2.txt'},
    {'map_name': 'oasis'}, {'map_name': 'invalid/name'}, {'first': first_binding()},
])
def test_invalid_binding_rejected(changes):
    with pytest.raises(ValueError):
        replace(first_binding(), **changes)


@pytest.mark.parametrize('first', [None, {}, replace(first_binding(), identity=replace(FIRST, match_id='f' * 32))])
def test_second_requires_matching_explicit_first(first):
    with pytest.raises(ValueError):
        StatsRoundBinding(SECOND, '2' * 32, '2026-09-25-120000-supply-round-2.txt', 100, 'b' * 64, 'supply', first)


async def test_expected_identity_rejected_before_manager_even_in_default_mode(tmp_path):
    first, _ = completed_identity_pair(tmp_path)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock())
    with pytest.raises(ValueError, match='disagrees with expected'):
        await import_completed_round(manager, first, expected_identity=replace(FIRST, match_id='f' * 32))
    manager.process_file.assert_not_awaited()


async def test_first_half_mapping_has_no_snapshot_dependency(tmp_path):
    first, _ = completed_identity_pair(tmp_path)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock(return_value=(True, 'fixture')))
    assert await import_completed_round(manager, first, expected_identity=FIRST) == (True, 'fixture')
    binding = manager.process_file.call_args.kwargs['runtime_binding']
    assert binding.identity == FIRST and binding.first is None
    assert binding.sha256 == first.sha256


@pytest.mark.parametrize('line_ending', [b'\n', b'\r\n'])
async def test_strict_mapping_delivers_exact_frozen_dependency(tmp_path, line_ending):
    first, second = completed_identity_pair(tmp_path, line_ending=line_ending)
    manager = SimpleNamespace(parser=C0RNP0RN3StatsParser(), process_file=AsyncMock(return_value=(True, 'fixture')))
    await import_completed_round(manager, second, first=first, expected_identity=SECOND)
    binding = manager.process_file.call_args.kwargs['runtime_binding']
    assert binding.identity == SECOND and binding.first.identity == FIRST
    assert (binding.sha256, binding.generation, binding.size) == (second.sha256, second.generation, second.size)
    assert (binding.first.sha256, binding.first.filename) == (first.sha256, first.filename)


@pytest.mark.parametrize('validation', [True, False])
async def test_mapping_records_actual_warning_or_success(validation):
    from unittest.mock import Mock

    from bot.runtime_round_mapping import record_round_mapping

    class Row(dict):
        def __iter__(self):
            return iter(self.values())

    binding = first_binding()
    conn = Mock()
    conn.is_in_transaction.return_value = True
    parent = dict(map_name='supply', round_number=1, gaming_session_id=7,
                  match_id=binding.filename[:17], round_date='2026-09-25', round_time='120000')
    event = Row(source_filename=binding.filename, source_payload_sha256='b' * 64,
                validation_passed=validation, round_number=1, gaming_session_id=7)
    conn.fetchrow = AsyncMock(side_effect=[parent, event])
    conn.execute = AsyncMock()
    await record_round_mapping(conn, binding, 3, 'b' * 64, validation_passed=validation)
    conn.execute.assert_awaited_once()
    assert conn.execute.await_args.args[-2:] == (3, 'b' * 64)
    conn.fetchrow = AsyncMock(side_effect=[parent, event])
    conn.execute.reset_mock()
    with pytest.raises(ValueError, match='journal missing or changed'):
        await record_round_mapping(conn, binding, 3, 'b' * 64, validation_passed=not validation)
    conn.execute.assert_not_awaited()


@pytest.mark.parametrize('deferred', [False, True])
@pytest.mark.parametrize('marked', [None, False, True])
@pytest.mark.parametrize('validation', [True, False])
@pytest.mark.parametrize('team_error', [None, 'busy', 'conflict'])
async def test_bound_replay_reconciles_only_default_team_effect(monkeypatch, deferred, marked, validation, team_error):
    from contextlib import asynccontextmanager
    from pathlib import Path
    from unittest.mock import Mock

    import postgresql_database_manager as database

    @asynccontextmanager
    async def borrow():
        yield conn

    binding = first_binding()
    conn = Mock()
    conn.transaction = borrow
    conn.fetchrow = AsyncMock(return_value=None if marked is None else dict(success=marked, file_hash='b' * 64, error_message=None))
    conn.fetchval = AsyncMock(return_value=validation)
    manager = object.__new__(database.PostgreSQLDatabaseManager)
    manager.defer_team_assignment = deferred
    manager.event_stream_enabled = True
    manager.pool = SimpleNamespace(acquire=borrow)
    monkeypatch.setattr(manager, '_compute_file_hashes', Mock(return_value=('a' * 64, 'b' * 64)))
    manager.mark_file_processed = AsyncMock()
    from shared.import_result import RetryableImportFailure
    from shared.team_identity import TeamIdentityConflict
    from shared.team_write_guard import TeamWriteBusy

    error = {'busy': TeamWriteBusy('busy'), 'conflict': TeamIdentityConflict('conflict')}.get(team_error)
    from shared import import_team_assignment

    monkeypatch.setattr(import_team_assignment, 'assign_round_teams',
                        AsyncMock(side_effect=error, return_value=import_team_assignment.TeamAssignment.ASSIGNED))
    auto_assign = AsyncMock(wraps=manager._auto_assign_teams_from_r1)  # noqa: SLF001
    manager.stats = {'files_failed': 0}
    monkeypatch.setattr(manager, '_auto_assign_teams_from_r1', auto_assign)
    monkeypatch.setattr(database, 'inspect_round_mapping', AsyncMock(return_value=3))
    monkeypatch.setattr(database, 'require_first_mapping', AsyncMock())
    result = await manager.process_file(Path(binding.filename), runtime_binding=binding,
                                        input_source=SimpleNamespace(read_bytes=lambda: b'x' * 100))
    if team_error is not None and not deferred:
        assert isinstance(result, RetryableImportFailure)
        assert result == (False, str(error))
    else:
        assert result == (True, 'Already mapped')
    if deferred:
        auto_assign.assert_not_awaited()
    else:
        auto_assign.assert_awaited_once_with(3, '2026-09-25', propagate_errors=True)
    assert manager.mark_file_processed.await_count == int(marked is not True or validation is False)
    if manager.mark_file_processed.await_count:
        warning = manager.mark_file_processed.await_args.kwargs['error_msg']
        assert (isinstance(warning, str) and warning.startswith('WARN:')) is (not validation)


@pytest.mark.parametrize('name', ['map.v2', 'map+beta', 'SW_goldrush_te', 'plain-map'])
def test_binding_accepts_transport_map_alphabet(name):
    binding = replace(first_binding(), map_name=name, filename=f'2026-09-25-120000-{name}-round-1.txt')
    assert binding.map_name == name


@pytest.mark.parametrize('strict', [False, True])
@pytest.mark.parametrize('kind', ['busy', 'conflict', 'cancelled'])
async def test_team_assignment_error_contract_preserves_strict_errors(monkeypatch, strict, kind):
    import asyncio
    from contextlib import asynccontextmanager

    import postgresql_database_manager as database
    from shared import import_team_assignment
    from shared.team_identity import TeamIdentityConflict
    from shared.team_write_guard import TeamWriteBusy

    @asynccontextmanager
    async def borrow():
        yield object()

    error = {'busy': TeamWriteBusy('held'), 'conflict': TeamIdentityConflict('unresolved'),
             'cancelled': asyncio.CancelledError()}[kind]
    monkeypatch.setattr(import_team_assignment, 'assign_round_teams', AsyncMock(side_effect=error))
    manager = object.__new__(database.PostgreSQLDatabaseManager)
    manager.pool = SimpleNamespace(acquire=borrow)
    if strict or kind == 'cancelled':
        with pytest.raises(type(error)) as caught:
            await manager._auto_assign_teams_from_r1(3, '2026-09-25', propagate_errors=strict)  # noqa: SLF001
        assert caught.value is error
    else:
        assert await manager._auto_assign_teams_from_r1(3, '2026-09-25') is False  # noqa: SLF001
