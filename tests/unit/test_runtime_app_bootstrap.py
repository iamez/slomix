"""Native startup integrity proof; synthetic entries never start applications."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.runtime_app_bootstrap import APP_BOOTSTRAP, launch_argv
from shared.release_manifest import MANIFEST

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def release(tmp_path):
    root = tmp_path / 'release'
    files = {
        'shared/release_manifest.py': (ROOT / 'shared/release_manifest.py').read_bytes(),
        'bot/ultimate_bot.py': b'import json, sys\nprint(json.dumps({"verified": _VERIFIED_RELEASE_ROOT, "args": sys.argv[1:]}))\n',
        'scripts/dev_schema_preflight.py': b'print("PREFLIGHT_REACHED")\n',
        'website/backend/main.py': b'# synthetic web entry\n',
        'shared/early_import.py': b'# imported code must also be verified\n',
    }
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    record = {'version': 1, 'source_commit': 'a' * 40,
              'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    (root / MANIFEST).write_text(json.dumps(record))
    return root


def command(root, entry='bot/ultimate_bot.py'):
    return launch_argv(sys.executable, root,
                       hashlib.sha256((root / MANIFEST).read_bytes()).hexdigest(),
                       hashlib.sha256((root / 'shared/release_manifest.py').read_bytes()).hexdigest(), entry)


def run(argv):
    return subprocess.run(argv, capture_output=True, text=True, timeout=10,
                          env={**os.environ, 'PYTHONPATH': '/unapproved/path'})


def test_native_verified_buffer_executes_without_bytecode(release):
    result = run(command(release) + ['fixture-argument'])
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {'verified': str(release), 'args': ['fixture-argument']}
    assert not list(release.rglob('*.pyc'))


@pytest.mark.parametrize('entry', ['bot/ultimate_bot.py', 'scripts/dev_schema_preflight.py', 'web'])
@pytest.mark.parametrize('damage', ['entry', 'verifier', 'manifest', 'extra', 'import', 'symlink'])
def test_native_tamper_refused_before_application_execution(release, entry, damage):
    argv = command(release, entry)
    if damage == 'manifest':
        path = release / MANIFEST
        record = json.loads(path.read_text())
        target = release / 'bot/ultimate_bot.py'
        target.write_text('print("UNAPPROVED_EXECUTION")\n')
        record['files']['bot/ultimate_bot.py'] = hashlib.sha256(target.read_bytes()).hexdigest()
        path.write_text(json.dumps(record))
    elif damage == 'symlink':
        path = release / 'shared/early_import.py'
        path.unlink()
        path.symlink_to('/dev/null')
    else:
        name = {'entry': 'bot/ultimate_bot.py', 'verifier': 'shared/release_manifest.py',
                'extra': 'unexpected.py', 'import': 'shared/early_import.py'}[damage]
        (release / name).write_text('print("UNAPPROVED_EXECUTION")\n')
    result = run(argv)
    assert result.returncode == 1
    assert result.stdout == ''
    assert json.loads(result.stderr)['reason'] == 'release_startup_integrity'
    assert not list(release.rglob('*.pyc'))


def test_native_preflight_entry_runs_after_verification(release):
    result = run(command(release, 'scripts/dev_schema_preflight.py'))
    assert result.returncode == 0
    assert result.stdout == 'PREFLIGHT_REACHED\n'


def test_bootstrap_argument_roundtrip():
    import shlex

    from scripts.dev_runtime_contract import render_argv
    argv = ['/python', '-I', '-B', '-c', APP_BOOTSTRAP, '/release']
    assert shlex.split(render_argv(argv)) == argv


def test_native_web_cli_reaches_dependency_without_starting_server(release):
    result = run(command(release, 'web') + ['--version'])
    assert result.returncode == 0, result.stderr
    assert 'Running uvicorn' in result.stdout
    assert not list(release.rglob('*.pyc'))


def test_inline_bootstrap_fits_systemd_249_argument_limit():
    assert len(APP_BOOTSTRAP.encode('utf-8')) < 4096


def test_launch_refuses_oversized_inline_code(monkeypatch):
    from scripts import runtime_app_bootstrap as bootstrap

    monkeypatch.setattr(bootstrap, 'APP_BOOTSTRAP', 'x' * 4096)
    with pytest.raises(ValueError, match='systemd argument limit'):
        bootstrap.launch_argv('/python', '/release', 'a' * 64, 'b' * 64, 'web')


def test_native_systemd_accepts_inline_startup_argument(tmp_path):
    import shutil

    from scripts.dev_runtime_contract import render_argv

    executable = shutil.which('systemd-analyze')
    if executable is None:
        pytest.skip('systemd-analyze is unavailable')
    unit = tmp_path / 'inline-proof.service'
    argv = launch_argv('/usr/bin/true', '/not-executed', 'a' * 64, 'b' * 64, 'web')
    unit.write_text('[Unit]\nDefaultDependencies=no\n[Service]\nType=oneshot\nExecStart='
                    + render_argv(argv) + '\n')
    result = subprocess.run([executable, 'verify', '--man=no', str(unit)],
                            env={'PATH': '/usr/bin:/bin', 'SYSTEMD_UNIT_PATH': str(tmp_path)},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
