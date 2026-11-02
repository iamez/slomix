"""Actual Lua inputs, guarded composition and truthful partial/cancel outcomes."""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot import runtime_timing_import_cli as cli
from shared.runtime_writer_lock import ImportWriterBusy, local_import_writer
from tests.unit.test_runtime_gametime_independence import run as run_timing
from tests.unit.test_runtime_gametime_source import NAME
from tests.unit.test_runtime_identity_writer_path import run_writer
from tests.unit.test_runtime_stats_dispatch import prepare, reference, setup_pair


def pipeline_inputs(root):
    root = root.resolve()
    authority, spool, pair = setup_pair(root / 'stats')
    first = run_writer('lua5.4', spool, pair, 1, 'bound-ipc', dispatch=prepare(authority, spool, pair))
    second = run_writer('lua5.4', spool, pair, 2, 'bound-ipc-retry',
                        dispatch=prepare(authority, spool, pair, 2, reference(first)))
    timing = root / 'timing'
    timing.mkdir(mode=0o700)
    lock = root / 'lock'
    lock.mkdir(mode=0o700)
    args = ['--execute', '--socket', str(root / 'absent-socket'), '--database', 'fixture_db',
            '--user', 'fixture_role', '--spool', str(spool), '--lock-directory', str(lock),
            '--journal', 'enabled', '--defer-team-assignment', '--expected-round-identities',
            pair.first.encode(), pair.second.encode(), '--timing-directory', str(timing),
            '--timing-writer-handover-confirmed']
    sources = []
    for half, item, identity in ((1, first, pair.first), (2, second, pair.second)):
        args.extend([f'--r{half}', item.generation, item.filename, str(item.size), item.sha256])
        run_timing(timing, enabled=False, target=False, mode='frame', identity=identity)
        path = timing / NAME.replace('R1', f'R{half}')
        raw = path.read_bytes()
        args.extend([f'--timing-r{half}', str(half) * 32, path.name, str(len(raw)), hashlib.sha256(raw).hexdigest()])
        sources.extend([path, item.root / item.generation / item.filename])
    return SimpleNamespace(args=args, pair=pair, first=first, second=second, lock=lock,
                           timing=timing, sources=sources, original={path: path.read_bytes() for path in sources})


@pytest.fixture
def source(tmp_path):
    return pipeline_inputs(tmp_path)


def successful_stages(monkeypatch, *, visible='applied'):
    """Only composition is stubbed; input producer/FD/hash validation is real."""
    closed, calls, fds = [], [], []

    @asynccontextmanager
    async def resources(database):
        with pytest.raises(ImportWriterBusy), local_import_writer(source_lock[0]):
            pytest.fail('Pipeline released the cooperative writer lease early')
        try:
            yield object(), object(), object()
        finally:
            closed.append(True)

    source_lock = [None]
    monkeypatch.setattr(cli, 'timing_import_resources', resources)
    for function, status in [('retain_gametime_source', None),
                             ('inspect_declared_gametime', 'canonical_target_verified'),
                             ('link_declared_gametime', 'linked'), ('apply_declared_gametime', 'applied'),
                             ('inspect_declared_gametime_application', visible)]:
        def make(name, value):
            async def operation(adapter, fd, **binding):
                fds.append(fd)
                calls.append((name, binding['expected_identity'].round_number))
                assert os.fstat(fd).st_size == binding['expected_size']
                return SimpleNamespace(status=value)
            return operation
        monkeypatch.setattr(cli, function, make(function, status))

    async def stats(manager, current, **options):
        calls.append(('stats', options['expected_identity'].round_number))
        return True, 'canonical result; not a database proof'

    monkeypatch.setattr(cli, 'import_completed_round', stats)
    return source_lock, closed, calls, fds


@pytest.mark.parametrize('visible', ['applied', 'not_applied', 'conflict'])
def test_only_fresh_receipt_observation_completes(source, monkeypatch, capsys, visible):
    lock, closed, calls, fds = successful_stages(monkeypatch, visible=visible)
    lock[0] = source.lock
    assert cli.main(source.args) == (0 if visible == 'applied' else 1)
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == ('completed' if visible == 'applied' else 'incomplete')
    assert report['source_acknowledged'] is False and closed == [True]
    assert report['timing'][0]['observation'] == visible
    assert calls[:4] == [('retain_gametime_source', 1), ('retain_gametime_source', 2), ('stats', 1), ('stats', 2)]
    for path, raw in source.original.items():
        assert path.read_bytes() == raw
    for fd in set(fds):
        with pytest.raises(OSError):
            os.fstat(fd)
    with local_import_writer(source.lock):
        pass  # Lease must be available after complete, pending and conflict outcomes.


@pytest.mark.parametrize('failure', [OSError('synthetic-secret'), asyncio.CancelledError()])
def test_partial_progress_survives_failure_and_cancellation(source, monkeypatch, capsys, failure):
    lock, closed, calls, _ = successful_stages(monkeypatch)
    lock[0] = source.lock

    async def stats(manager, current, **options):
        half = options['expected_identity'].round_number
        calls.append(('stats', half))
        if half == 2:
            raise failure
        return True, 'first stage accepted'

    monkeypatch.setattr(cli, 'import_completed_round', stats)
    before = logging.root.manager.disable
    assert cli.main(source.args) == (130 if isinstance(failure, asyncio.CancelledError) else 1)
    captured = capsys.readouterr()
    assert 'synthetic-secret' not in captured.out + captured.err
    report = json.loads(captured.out)
    assert report['effect_state'] == 'possibly_partial' and report['active_stage'] == 'stats_r2'
    assert report['stats'][0]['status'] == 'accepted' and report['stats'][1]['status'] == 'unknown'
    assert [row['retention'] for row in report['timing']] == ['retained', 'retained']
    assert not any(name == 'apply_declared_gametime' for name, _ in calls)
    assert closed == [True] and logging.root.manager.disable == before


@pytest.mark.parametrize('fault', ['digest', 'symlink', 'hardlink', 'directory', 'world-write', 'map', 'identity'])
def test_bad_timing_refuses_before_resource_creation(source, monkeypatch, capsys, fault):
    path = source.sources[0]
    if fault == 'digest':
        path.write_bytes(path.read_bytes() + b'changed')
    elif fault in {'symlink', 'hardlink'}:
        saved = path.with_suffix('.saved')
        path.rename(saved)
        if fault == 'symlink':
            path.symlink_to(saved)
        else:
            os.link(saved, path)
    elif fault == 'directory':
        source.timing.chmod(0o755)
    elif fault == 'world-write':
        path.chmod(0o666)
    else:
        document = json.loads(path.read_bytes())
        if fault == 'map':
            document['meta']['map'] = 'oasis'
        else:
            document['meta']['runtime_identity'] = source.pair.second.encode()
        raw = json.dumps(document).encode()
        path.write_bytes(raw)
        offset = source.args.index('--timing-r1')
        source.args[offset + 3:offset + 5] = [str(len(raw)), hashlib.sha256(raw).hexdigest()]
    resources = AsyncMock(side_effect=AssertionError('Must not create DB resources'))
    monkeypatch.setattr(cli, 'timing_import_resources', resources)
    assert cli.main(source.args) == 1
    resources.assert_not_called()
    assert json.loads(capsys.readouterr().out)['effect_state'] == 'not_started'


@pytest.mark.parametrize('missing', ['--defer-team-assignment', '--expected-round-identities',
                                   '--timing-writer-handover-confirmed'])
def test_pipeline_has_no_legacy_or_implicit_policy_fallback(source, missing):
    index = source.args.index(missing)
    del source.args[index:index + (3 if missing == '--expected-round-identities' else 1)]
    with pytest.raises(SystemExit) as error:
        cli.main(source.args)
    assert error.value.code == 2


def test_new_cli_process_admits_real_files_without_discord_web_or_dotenv(source):
    script = '''
import importlib.abc, runpy, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'discord', 'website', 'dotenv'} or fullname in {
            'bot.config', 'bot.logging_config', 'bot.ultimate_bot', 'shared.importer_startup',
        }:
            raise AssertionError('Forbidden service/configuration dependency')
sys.meta_path.insert(0, Block())
sys.argv = ['runtime-timing-import'] + sys.argv[1:]
runpy.run_module('bot.runtime_timing_import_cli', run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', script, *source.args],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and result.stderr == ''
    report = json.loads(result.stdout)
    assert report['active_stage'] == 'resources' and report['effect_state'] == 'not_started'
    assert report['source_acknowledged'] is False
    for path, raw in source.original.items():
        assert path.read_bytes() == raw
    print('Actual CLI process admits all four actual Lua files without Discord/web/dotenv; '
          'explicit absent socket refuses before writes; sources unchanged')
