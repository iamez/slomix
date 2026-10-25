"""Native Git hook refusal and preparation/launch source revision binding."""
import subprocess

import pytest

from scripts import prepare_runtime_game_service as service
from scripts import runtime_game_supervisor as supervisor


def git(root, *args):
    return subprocess.check_output(['/usr/bin/git', '-C', str(root), *args], text=True).strip()


def test_native_fsmonitor_never_executes_during_source_admission(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    git(root, 'init', '-q')
    (root / 'source.py').write_text('approved = True\n')
    git(root, 'add', 'source.py')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'test: synthetic source')
    head = git(root, 'rev-parse', 'HEAD')
    sentinel = tmp_path / 'fsmonitor-executed'
    hook = tmp_path / 'fsmonitor-hook'
    hook.write_text('#!/bin/sh\nprintf called >> ' + str(sentinel) + '\nprintf "\\0"\n')
    hook.chmod(0o700)
    git(root, 'config', 'core.fsmonitor', str(hook))
    # Positive control: this Git build actually executes configured hooks.
    git(root, 'ls-files', '-v')
    assert sentinel.read_text() == 'called'
    sentinel.unlink()
    supervisor.verify_source(root, head)
    assert not sentinel.exists()
    assert (root / 'source.py').read_text() == 'approved = True\n'


@pytest.mark.parametrize('workspace_commit', ['a' * 40, 'b' * 40])
def test_preparation_binds_workspace_before_artifact_creation(tmp_path, monkeypatch, workspace_commit):
    monkeypatch.setattr(service, 'verify_source', lambda *args: None)
    monkeypatch.setattr(service, 'startup_recipe', lambda *args, **kw:
                        {'workspace': {'source_commit': workspace_commit}})
    # Invalid interpreter marks the next independent admission check, before IO.
    kwargs = dict(source=tmp_path, interpreter=tmp_path / 'missing-python',
                  workspace=tmp_path / 'game', destination=tmp_path / 'unit', commit='a' * 40)
    with pytest.raises(ValueError, match='executable interpreter' if workspace_commit == 'a' * 40
                       else 'Workspace source commit'):
        service.prepare(**kwargs)
    assert not kwargs['destination'].exists()


@pytest.mark.parametrize('workspace_commit', ['a' * 40, 'b' * 40])
def test_launch_binds_workspace_before_process_creation(tmp_path, monkeypatch, workspace_commit):
    monkeypatch.setattr(supervisor, 'require_containment', lambda *args: {'InvocationID': 'c' * 32})
    monkeypatch.setattr(supervisor, 'validate_launch_commands', lambda *args: None)
    monkeypatch.setattr(supervisor, 'verify_source', lambda *args: None)
    monkeypatch.setattr(supervisor, 'startup_recipe', lambda *args, **kw:
                        dict(argv=[], cwd='/', env={}, workspace={'source_commit': workspace_commit}))
    calls = []
    def process(*args, **kwargs):
        calls.append('process_boundary')
        raise RuntimeError('synthetic launch boundary; no process started')
    monkeypatch.setattr(supervisor.subprocess, 'Popen', process)
    with pytest.raises(RuntimeError if workspace_commit == 'a' * 40 else ValueError,
                       match='synthetic launch boundary' if workspace_commit == 'a' * 40 else 'Workspace source commit'):
        supervisor.run(tmp_path, 'slomix-et-proof-1234abcd.service', 'a' * 40)
    assert calls == (['process_boundary'] if workspace_commit == 'a' * 40 else [])
