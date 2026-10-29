"""Offline service delivery must never mutate its verified release."""
import json

import pytest

from scripts import prepare_runtime_consumer_service as delivery
from scripts import prepare_runtime_team_service as team
from shared.release_manifest import MANIFEST, file_hash, verify_release


@pytest.fixture
def inputs(tmp_path):
    release = tmp_path / ('a' * 40)
    release.mkdir()
    names = set().union(*(s['required'] for s in delivery.COMPONENTS.values()))
    for name in names:
        p = release / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('# fixture\n')
    record = dict(version=1, source_commit=release.name,
                  files={name: file_hash(release / name) for name in names})
    (release / MANIFEST).write_text(json.dumps(record))
    interpreter = tmp_path / 'python'
    interpreter.write_text('#!/bin/sh\nexit 0\n')
    interpreter.chmod(0o755)
    environment = tmp_path / 'consumer.env'
    environment.write_text('EVENT_STREAM_ENABLED=false\n')
    environment.chmod(0o600)
    return release, interpreter, environment


@pytest.mark.parametrize('component', ['team', 'cache', 'legacy-team'])
def test_refuse_output_inside_release_without_modifying_it(inputs, component):
    release, interpreter, environment = inputs
    before = verify_release(release)
    destination = release / 'prepared'
    with pytest.raises(ValueError, match='outside'):
        if component == 'legacy-team':
            team.prepare(release, interpreter, environment, destination, release.name)
        else:
            delivery.prepare(release, interpreter, environment, destination,
                             release.name, component=component)
    assert not destination.exists()
    assert verify_release(release) == before


@pytest.mark.parametrize('component', ['team', 'cache'])
def test_prepare_separate_default_off_units(inputs, component):
    release, interpreter, environment = inputs
    before = verify_release(release)
    destination = release.parent / component
    record = delivery.prepare(release, interpreter, environment, destination,
                              release.name, component=component)
    unit = destination / f'slomix-runtime-{component}.service'
    contents = unit.read_text()
    assert f'-m shared.runtime_{component}_main' in contents
    assert 'WantedBy=default.target' in contents
    assert 'Restart=on-failure' in contents and 'TimeoutStopSec=25' in contents
    assert 'Requires=' not in contents and 'User=' not in contents
    assert record['unit_sha256'] == file_hash(unit)
    assert record['configuration_validated'] is False
    assert record['handover_required'] is (component == 'team')
    assert record['runtime_acceptance'] == 'pending'
    assert verify_release(release) == before
    with pytest.raises(ValueError, match='new output'):
        delivery.prepare(release, interpreter, environment, destination,
                         release.name, component=component)


def test_compatibility_team_entrypoint(inputs):
    assert 'canonical' in team.__all__
    assert team.canonical is delivery.canonical
    release, interpreter, environment = inputs
    output = release.parent / 'compatibility'
    assert team.prepare(release, interpreter, environment, output,
                        release.name)['component'] == 'team'


@pytest.mark.parametrize('bad', ['revision', 'permissions', 'payload', 'component'])
def test_invalid_input_never_creates_output(inputs, bad):
    release, interpreter, environment = inputs
    revision, component = release.name, 'cache'
    if bad == 'revision':
        revision = 'b' * 40
    elif bad == 'permissions':
        environment.chmod(0o644)
    elif bad == 'payload':
        (release / 'shared/runtime_cache_main.py').write_text('changed\n')
    else:
        component = 'arbitrary'
    output = release.parent / 'refused'
    with pytest.raises(ValueError):
        delivery.prepare(release, interpreter, environment, output,
                         revision, component=component)
    assert not output.exists()


@pytest.mark.parametrize('changed', ['environment', 'interpreter', 'unit', 'payload',
                                     'missing_digest', 'permissions'])
def test_prepared_verification_refuses_drift(inputs, changed):
    release, interpreter, environment = inputs
    destination = release.parent / 'prepared'
    delivery.prepare(release, interpreter, environment, destination, release.name, component='team')
    contract = destination / 'contract.json'
    if changed in ('environment', 'interpreter', 'unit', 'payload'):
        target = {'environment': environment, 'interpreter': interpreter,
                  'unit': destination / 'slomix-runtime-team.service',
                  'payload': release / 'shared/runtime_team_main.py'}[changed]
        target.write_text(target.read_text() + '# changed\n')
    elif changed == 'permissions':
        environment.chmod(0o644)
    else:
        record = json.loads(contract.read_text())
        del record['environment_sha256']
        contract.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        delivery.verify_prepared(contract)


@pytest.mark.parametrize('component', ['team', 'cache'])
def test_verification_is_read_only_and_not_activation(inputs, component, capsys):
    release, interpreter, environment = inputs
    destination = release.parent / 'prepared'
    delivery.prepare(release, interpreter, environment, destination, release.name, component=component)
    before = {p: p.read_bytes() for p in release.parent.rglob('*') if p.is_file()}
    assert delivery.main(['--verify-contract=' + str(destination / 'contract.json')]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['prepared_files_match'] is True
    assert report['configuration_validated'] is False
    assert report['handover_verified'] is False
    assert report['activation_ready'] is False
    assert report['effective_environment'] == 'unmeasured'
    assert before == {p: p.read_bytes() for p in release.parent.rglob('*') if p.is_file()}


def test_verify_failure_does_not_disclose_environment(inputs, capsys):
    release, interpreter, environment = inputs
    destination = release.parent / 'prepared'
    delivery.prepare(release, interpreter, environment, destination, release.name, component='team')
    environment.write_text('PASSWORD=secret-sentinel\n')
    assert delivery.main(['--verify-contract', str(destination / 'contract.json')]) == 1
    captured = capsys.readouterr()
    assert 'secret-sentinel' not in captured.out + captured.err


def test_verification_rejects_fifo_unit_without_opening_it(inputs, monkeypatch):
    import os

    release, interpreter, environment = inputs
    destination = release.parent / 'prepared'
    delivery.prepare(release, interpreter, environment, destination, release.name, component='team')
    unit = destination / 'slomix-runtime-team.service'
    unit.unlink()
    os.mkfifo(unit)
    actual_hash = delivery.file_hash

    def hash_regular_only(path):
        assert path != unit, 'Verification must reject a FIFO before opening it'
        return actual_hash(path)

    monkeypatch.setattr(delivery, 'file_hash', hash_regular_only)
    with pytest.raises(ValueError, match='regular file'):
        delivery.verify_prepared(destination / 'contract.json')


@pytest.mark.parametrize('component', ['team', 'cache'])
def test_consumer_units_scrub_import_environment(inputs, component):
    release, interpreter, environment = inputs
    destination = release.parent / component
    delivery.prepare(release, interpreter, environment, destination, release.name, component=component)
    unit = (destination / f'slomix-runtime-{component}.service').read_text()
    unset = next(line.split('=', 1)[1] for line in unit.splitlines() if line.startswith('UnsetEnvironment='))
    assert set(unset.split()) == {'PYTHONPATH', 'PYTHONHOME', 'LD_PRELOAD', 'LD_LIBRARY_PATH', 'LD_AUDIT'}


def test_consumer_preserves_standard_symlink_venv(inputs):
    import subprocess
    import sys

    release, _, environment = inputs
    venv = release.parent / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)],
                   check=True, capture_output=True, timeout=20)
    interpreter = venv / 'bin/python'
    assert interpreter.is_symlink()
    destination = release.parent / 'linked-consumer'
    record = delivery.prepare(release, interpreter, environment, destination, release.name, component='cache')
    assert record['interpreter'] == str(interpreter)
    assert delivery.verify_prepared(destination / 'contract.json')['prepared_files_match'] is True


@pytest.mark.parametrize("equals", [False, True])
def test_team_compatibility_cli_can_verify_prepared_contract(inputs, monkeypatch, capsys, equals):
    import sys

    from scripts import prepare_runtime_team_service as team

    release, python, environment = inputs
    destination = release.parent / "team-verify"
    team.prepare(release, python, environment, destination, release.name)
    path = str(destination / "contract.json")
    args = ["--verify-contract=" + path] if equals else ["--verify-contract", path]
    monkeypatch.setattr(sys, "argv", ["prepare_runtime_team_service.py", *args])
    assert team.main() == 0
    assert json.loads(capsys.readouterr().out)["component"] == "team"


@pytest.mark.parametrize('component', ['team', 'cache'])
@pytest.mark.parametrize('change', ['command', 'sandbox', 'guard'])
def test_rehashed_unit_cannot_change_consumer_policy(inputs, component, change):
    release, interpreter, environment = inputs
    destination = release.parent / component
    delivery.prepare(release, interpreter, environment, destination, release.name, component=component)
    unit = destination / f'slomix-runtime-{component}.service'
    original = unit.read_text()
    if change == 'command':
        altered = original.replace(f'ExecStart={interpreter} -E -B -s -u -m', 'ExecStart=/bin/false #')
    elif change == 'sandbox':
        altered = original.replace(f'ReadOnlyPaths={release}\n', '')
    else:
        altered = '\n'.join(line for line in original.splitlines() if not line.startswith('ExecStartPre=')) + '\n'
    assert altered != original
    unit.write_text(altered)
    contract = destination / 'contract.json'
    record = json.loads(contract.read_text())
    record['unit_sha256'] = file_hash(unit)
    contract.write_text(json.dumps(record))
    with pytest.raises(ValueError, match='consumer policy'):
        delivery.verify_prepared(contract)


def test_mount_guard_refuses_actual_writable_release_without_writing(inputs):
    import os
    import subprocess
    import sys

    release, _, _ = inputs
    assert not os.statvfs(release).f_flag & os.ST_RDONLY
    before = verify_release(release)
    result = subprocess.run([sys.executable, '-I', '-B', '-c', delivery.READ_ONLY_RELEASE_CHECK],
                            cwd=release, capture_output=True, timeout=10)
    assert result.returncode == 1
    assert result.stdout == result.stderr == b''
    assert verify_release(release) == before


@pytest.mark.parametrize('writable', [None, '.', 'shared', 'shared/runtime_cache_main.py'])
def test_mount_guard_checks_release_and_all_descendants(inputs, monkeypatch, writable):
    import os
    from types import SimpleNamespace

    release, _, _ = inputs
    monkeypatch.chdir(release)
    observed = set()

    def filesystem_flags(path):
        name = path.relative_to(release).as_posix()
        observed.add(name)
        return SimpleNamespace(f_flag=0 if name == writable else os.ST_RDONLY)

    monkeypatch.setattr(os, 'statvfs', filesystem_flags)
    with pytest.raises(SystemExit) as exit_info:
        exec(delivery.READ_ONLY_RELEASE_CHECK, {})  # noqa: S102 -- constant unit guard, no external code
    assert exit_info.value.code == (0 if writable is None else 1)
    assert '.' in observed
    if writable is None:
        assert observed == {'.', *(p.relative_to(release).as_posix() for p in release.rglob('*'))}
    else:
        assert writable in observed


@pytest.mark.parametrize('component', ['team', 'cache'])
def test_consumer_actual_python_flags_ignore_ambient_python_settings(inputs, component):
    import shlex
    import subprocess
    import sys

    release, _, environment = inputs
    unit = delivery.render_unit(release, sys.executable, environment, release.name, component=component)
    argv = shlex.split(next(line.split('=', 1)[1] for line in unit.splitlines()
                            if line.startswith('ExecStart=')))
    assert argv[1:5] == ['-E', '-B', '-s', '-u']
    result = subprocess.run([*argv[:5], '-c',
                             'import sys; assert sys.flags.ignore_environment; '
                             'assert sys.stdout.write_through; assert sys.flags.no_user_site; '
                             'assert sys.dont_write_bytecode; print("startup-flags-ok")'],
                            env={'PYTHONPLATLIBDIR': 'nonexistent-library'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'startup-flags-ok'
