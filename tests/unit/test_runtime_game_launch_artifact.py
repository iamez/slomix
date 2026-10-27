"""Native Git clean-filter and external immutable supervisor bootstrap controls."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import prepare_runtime_game_service as service
from scripts import runtime_game_supervisor as supervisor
from tests.unit.test_runtime_game_source_binding import git


def repository(tmp_path):
    root = tmp_path / 'source'
    root.mkdir()
    git(root, 'init', '-q')
    (root / 'source.py').write_text('approved = True\n')
    git(root, 'add', 'source.py')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'test: synthetic source')
    return root, git(root, 'rev-parse', 'HEAD')


def test_native_source_admission_never_executes_clean_filter(tmp_path):
    root, head = repository(tmp_path)
    sentinel = tmp_path / 'clean-filter-executed'
    hook = tmp_path / 'clean-filter'
    hook.write_text('#!/bin/sh\nprintf called >> ' + str(sentinel) + '\ncat\n')
    hook.chmod(0o700)
    (root / '.git/info/attributes').write_text('source.py filter=proof\n')
    git(root, 'config', 'filter.proof.clean', str(hook))
    (root / 'source.py').write_text('approved = True\n')
    git(root, 'diff', '--quiet', 'HEAD', '--')
    assert sentinel.read_text()  # This Git actually executes clean filters.
    sentinel.unlink()
    supervisor.verify_source(root, head)
    assert not sentinel.exists()


@pytest.mark.parametrize('change', ['staged', 'unstaged', 'mode', 'symlink'])
def test_raw_source_comparison_refuses_drift_without_conversion(tmp_path, change):
    root, head = repository(tmp_path)
    path = root / 'source.py'
    if change == 'mode':
        path.chmod(0o755)
    elif change == 'symlink':
        path.unlink()
        path.symlink_to(tmp_path / 'external')
    else:
        path.write_text('unapproved = True\n')
        if change == 'staged':
            git(root, 'add', 'source.py')
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        supervisor.verify_source(root, head)


def test_copied_supervisor_bytes_come_from_approved_commit(tmp_path):
    root, _ = repository(tmp_path)
    (root / 'scripts').mkdir()
    path = root / 'scripts/runtime_game_supervisor.py'
    raw = b'print("approved supervisor")\n'
    path.write_bytes(raw)
    git(root, 'add', 'scripts/runtime_game_supervisor.py')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
        '-c', 'commit.gpgsign=false', 'commit', '-qm', 'test: committed supervisor')
    head = git(root, 'rev-parse', 'HEAD')
    path.write_text('raise RuntimeError("mutable checkout")\n')
    assert service.committed_supervisor(root, head) == raw


@pytest.mark.parametrize('tamper', ['none', 'checkout', 'artifact', 'after-read', 'symlink', 'permissions'])
def test_native_bootstrap_executes_only_same_verified_private_buffer(tmp_path, tamper):
    source = tmp_path / 'mutable-supervisor.py'
    original = Path(supervisor.__file__).read_bytes()
    source.write_bytes(original)
    digest = hashlib.sha256(original).hexdigest()
    artifact = tmp_path / ('supervisor-' + digest + '.py')
    artifact.write_bytes(original)
    artifact.chmod(0o600)
    sentinel = tmp_path / 'unverified-code-executed'
    malicious = f'open({str(sentinel)!r}, "w").write("unsafe")\n'.encode()
    if tamper == 'checkout':
        source.write_bytes(malicious + original)
    elif tamper == 'artifact':
        artifact.write_bytes(malicious + original)
    elif tamper == 'symlink':
        artifact.unlink()
        artifact.symlink_to(source)
    elif tamper == 'permissions':
        artifact.chmod(0o644)
    bootstrap = supervisor.SUPERVISOR_BOOTSTRAP
    if tamper == 'after-read':
        bootstrap = '''import hashlib,pathlib
original=hashlib.sha256
class Digest:
 def __init__(self,raw): self.digest=original(raw)
 def hexdigest(self):
  pathlib.Path(__import__('sys').argv[1]).write_bytes(''' + repr(malicious + original) + ''')
  return self.digest.hexdigest()
hashlib.sha256=Digest
''' + bootstrap
    result = subprocess.run([sys.executable, '-I', '-B', '-c', bootstrap, str(artifact), digest, str(source),
        'verify-stopped', '--unit', 'slomix-et-proof-1234abcd.service', '--invocation-id', 'a' * 32,
        '--port', '27963'], env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'},
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert not sentinel.exists()
    report = json.loads(result.stderr)
    assert report['status'] == 'refused_or_failed'
    if tamper in {'artifact', 'symlink', 'permissions'}:
        assert report['reason'] == 'supervisor_artifact_refused'
    else:
        assert report['error_type'] == 'ValueError'  # Original wrong-port guard ran.


def test_direct_service_run_requires_external_bootstrap(tmp_path):
    result = subprocess.run([sys.executable, '-I', '-B', supervisor.__file__, 'run',
        '--directory', str(tmp_path), '--unit', 'slomix-et-proof-1234abcd.service', '--commit', 'a' * 40],
        capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and result.stdout == ''
    assert json.loads(result.stderr)['error_type'] == 'ValueError'


def test_main_process_provenance_guard_runs_before_containment(tmp_path, monkeypatch):
    monkeypatch.setattr(supervisor, '__name__', '__main__')
    monkeypatch.delitem(supervisor.__dict__, '_SUPERVISOR_SHA256', raising=False)
    monkeypatch.setattr(supervisor, 'require_containment', lambda *args:
                        pytest.fail('Missing artifact provenance reached service admission'))
    with pytest.raises(ValueError, match='external supervisor bootstrap'):
        supervisor.run(tmp_path, 'slomix-et-proof-1234abcd.service', 'a' * 40)
