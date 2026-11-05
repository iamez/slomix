"""Explicit timing ownership and bounded progress, no database or service."""
import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from bot import runtime_captured_timing_import as adapter
from scripts import runtime_game_import as importer
from scripts import runtime_game_supervisor as supervisor
from tests.unit.test_runtime_captured_timing_import import captured as make_handoff


@pytest.mark.parametrize('flags', [(False, False), (True, False), (False, True), (1, True)])
async def test_full_import_refuses_absent_or_ambiguous_handover(monkeypatch, flags):
    probe = AsyncMock()
    monkeypatch.setattr(importer, 'preflight_import', probe)
    with pytest.raises(ValueError):
        await importer.import_live_timing_capture(object(), socket=Path('/unused'), database='unused',
            lock_directory=Path('/unused'), defer_team_assignment=True,
            writer_handover_confirmed=flags[0], timing_writer_handover_confirmed=flags[1])
    probe.assert_not_awaited()


@pytest.mark.parametrize('outcome', ['complete', 'unobserved', 'partial', 'exception', 'cancel'])
async def test_owned_pipeline_reports_only_observed_completion(monkeypatch, tmp_path, outcome):
    monkeypatch.setattr(importer, 'preflight_import', AsyncMock())
    monkeypatch.setattr(importer, 'proof_database', lambda *args:
        SimpleNamespace(socket='/private/approved', database='approved', user='owner'))
    captured = make_handoff(tmp_path)

    async def operation(options, handoff, progress):
        assert handoff is captured
        assert options.execute and options.journal == 'enabled' and options.defer_team_assignment
        assert options.timing_writer_handover_confirmed and not options.writer_handover_confirmed
        assert options.env_file is None and options.database == 'approved'
        if outcome == 'exception':
            raise RuntimeError('PRIVATE transport detail')
        if outcome == 'cancel':
            raise asyncio.CancelledError()
        if outcome == 'complete':
            progress.update(effect_state='observed_complete', active_stage='finished')
        return outcome != 'partial'

    monkeypatch.setattr(adapter, 'import_captured_timing_match', operation)
    previous = logging.root.manager.disable
    result = await importer.import_live_timing_capture(captured, socket=Path('/private/approved'),
        database='approved', lock_directory=Path('/private/lock'), defer_team_assignment=True,
        writer_handover_confirmed=True, timing_writer_handover_confirmed=True)
    expected = dict(complete='completed', unobserved='incomplete', partial='incomplete',
                    exception='outcome_unknown', cancel='interrupted')
    assert result['status'] == expected[outcome]
    assert result['source_acknowledged'] is False and 'PRIVATE' not in str(result)
    assert logging.root.manager.disable == previous


@pytest.mark.parametrize('flags', [(True, False), (False, True), (True, True)])
def test_bad_timing_policy_refused_before_containment(monkeypatch, tmp_path, flags):
    containment = Mock()
    monkeypatch.setattr(supervisor, 'require_containment', containment)
    with pytest.raises(ValueError):
        supervisor.run(tmp_path, 'unused', 'a' * 40, writer_handover_confirmed=flags[0],
                       timing_writer_handover_confirmed=flags[1])
    containment.assert_not_called()


def test_both_handover_claims_are_in_exact_unit_argv(tmp_path):
    argv = supervisor.supervisor_argv(tmp_path, '/usr/bin/python3', tmp_path, 'unit', 'a' * 40,
        writer_handover_confirmed=True, timing_writer_handover_confirmed=True)
    assert argv.count('--writer-handover-confirmed') == 1
    assert argv.count('--timing-writer-handover-confirmed') == 1


@pytest.mark.parametrize('flags', [(True, False), (False, True)])
def test_complete_target_does_not_replace_either_handover(flags):
    with pytest.raises(ValueError, match='both handovers'):
        supervisor.validate_import_policy(True, '/private/socket', 'explicit', '/private/lock',
            writer_handover_confirmed=flags[0], timing_writer_handover_confirmed=flags[1])


@pytest.mark.parametrize('field,value', [
    ('defer_team_assignment', False), ('defer_team_assignment', 1),
    ('writer_handover_confirmed', 1), ('timing_writer_handover_confirmed', 1),
    ('socket', None), ('database', None), ('lock_directory', None),
])
async def test_timing_only_admission_requires_exact_claims_and_complete_target(monkeypatch, field, value):
    probe = AsyncMock()
    monkeypatch.setattr(importer, 'preflight_import', probe)
    options = dict(socket=Path('/unused'), database='unused', lock_directory=Path('/unused'),
                   defer_team_assignment=True, writer_handover_confirmed=True,
                   timing_writer_handover_confirmed=True)
    options[field] = value
    with pytest.raises(ValueError, match='both handovers'):
        await importer.import_live_timing_capture(object(), **options)
    probe.assert_not_awaited()


async def test_timing_admission_does_not_import_supervisor(monkeypatch):
    import builtins

    original = builtins.__import__

    def without_supervisor(name, *args, **kwargs):
        if name == 'scripts.runtime_game_supervisor':
            raise AssertionError('Timing importer must not import its supervisor')
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, '__import__', without_supervisor)
    with pytest.raises(ValueError, match='Successful live captured timing match required'):
        await importer.import_live_timing_capture(object(), socket=Path('/unused'), database='unused',
            lock_directory=Path('/unused'), defer_team_assignment=True,
            writer_handover_confirmed=True, timing_writer_handover_confirmed=True)
