"""Target admission only; never connects to or changes a database."""

import logging
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from scripts import runtime_game_import as module
from scripts.runtime_game_import import proof_database


def test_private_target_and_non_fixture_refusals():
    with tempfile.TemporaryDirectory(prefix='slomix-runtime-pg-', dir='/tmp') as directory:
        path = Path(directory)
        target = proof_database(path, 'slomix_fixture_' + 'a' * 32)
        assert target.socket == directory and target.password == ''
        for name in ('etlegacy', 'postgres', 'etlegacy_test', 'slomix_fixture_x', None):
            with pytest.raises(ValueError, match='disposable'):
                proof_database(path, name)
        path.chmod(0o750)
        with pytest.raises(ValueError, match='owner-only'):
            proof_database(path, 'slomix_fixture_' + 'a' * 32)


@pytest.mark.parametrize('path', [Path('/var/run/postgresql'), Path('/tmp'),
                                Path('relative'), '/tmp/slomix-runtime-pg-example'])
def test_ambient_or_nonproof_socket_refused(path):
    with pytest.raises(ValueError, match='private proof'):
        proof_database(path, 'slomix_fixture_' + 'a' * 32)


@pytest.mark.parametrize('deferred', [False, True])
@pytest.mark.parametrize('outcomes,status', [(((True, 'private'), (True, 'warning')), 'completed'),
                                           (((True, 'private'), (False, 'private')), 'incomplete'),
                                           ((), 'incomplete')])
async def test_live_handoff_preserved_and_results_redacted(monkeypatch, outcomes, status, deferred):
    monkeypatch.setattr(module, 'preflight_import', AsyncMock())
    target, captured, lock = object(), object(), Path('/unused-lock')
    monkeypatch.setattr(module, 'proof_database', lambda *args: target)
    importer = AsyncMock(return_value=outcomes)
    monkeypatch.setattr(module, 'import_captured_match', importer)
    before = logging.root.manager.disable
    result = await module.import_live_capture(captured, socket=Path('/unused'),
                                              database='unused', lock_directory=lock, defer_team_assignment=deferred)
    importer.assert_awaited_once_with(target, captured, lock_directory=lock, attempt_timeout=60.0,
                                      defer_team_assignment=deferred)
    assert result['status'] == status and result['source_acknowledged'] is False
    assert 'private' not in str(result) and 'warning' not in str(result)
    assert logging.root.manager.disable == before


async def test_changed_target_prevents_import_and_redacts_exception(monkeypatch):
    monkeypatch.setattr(module, 'preflight_import', AsyncMock())
    def refused(*args):
        raise ValueError('PRIVATE credential detail')
    monkeypatch.setattr(module, 'proof_database', refused)
    importer = AsyncMock()
    monkeypatch.setattr(module, 'import_captured_match', importer)
    result = await module.import_live_capture(object(), socket=Path('/unused'),
                                              database='unused', lock_directory=Path('/unused'))
    importer.assert_not_awaited()
    assert result['status'] == 'outcome_unknown'
    assert 'PRIVATE' not in str(result)


@pytest.mark.parametrize('clean,unknown,accepted', [(True, [], True), (False, [], False),
                                                  (True, ['legacy.sql'], False)])
async def test_readiness_checks_ledger_with_real_private_lock(tmp_path, monkeypatch, clean, unknown, accepted):
    lock = tmp_path / 'lock'
    lock.mkdir(mode=0o700)
    inspector = AsyncMock(return_value={'clean': clean, 'unknown_checksums': unknown})
    monkeypatch.setattr(module, 'inspect_database', inspector)
    with tempfile.TemporaryDirectory(prefix='slomix-runtime-pg-', dir='/tmp') as directory:
        options = dict(socket=Path(directory), database='slomix_fixture_' + 'a' * 32,
                       lock_directory=lock)
        if accepted:
            assert (await module.preflight_import(**options))['full_schema_verified'] is False
        else:
            with pytest.raises(ValueError, match='readiness failed'):
                await module.preflight_import(**options)
    config, checksums = inspector.await_args.args
    assert config['passfile'] is None and config['password'] == ''
    assert config['server_settings']['default_transaction_read_only'] == 'on'
    assert checksums and (lock / '.import-writer.lock').is_file()
    with module.local_import_writer(lock):
        pass  # Probe releases its lock on success and refusal.


@pytest.mark.parametrize('policy', [None, 1, 'true'])
async def test_invalid_team_policy_before_preflight(monkeypatch, policy):
    preflight = AsyncMock()
    monkeypatch.setattr(module, 'preflight_import', preflight)
    before = logging.root.manager.disable
    with pytest.raises(ValueError, match='boolean team ownership'):
        await module.import_live_capture(None, socket=None, database=None, lock_directory=None,
                                         defer_team_assignment=policy)
    preflight.assert_not_awaited()
    assert logging.root.manager.disable == before
