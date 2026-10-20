"""Named metadata is an observation, never handover authority."""
import argparse
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import runtime_writer_inventory as inventory


def metadata(unit="example.service", state="inactive"):
    values = dict.fromkeys(inventory.PROPERTIES, "")
    values.update(Id=unit, ActiveState=state, SubState="dead", FragmentPath="/etc/systemd/system/" + unit)
    if unit.endswith(".service"):
        values.update(MainPID="0", Restart="always")
    return values


def runner(monkeypatch, values=None, code=0):
    calls = []
    def run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=code, stdout="\n".join(f"{k}={v}" for k, v in values.items()),
                               stderr="SECRET RAW ERROR")
    monkeypatch.setattr(inventory.subprocess, "run", run)
    return calls


@pytest.mark.parametrize("unit", ["*", "*.service", "--help", "../x.service", "x.socket", "x.service\n", "x service", "x;stop.service", "worker@.service", "worker@.timer", "worker@@one.service"])
def test_rejects_ambiguous_names(unit):
    with pytest.raises(argparse.ArgumentTypeError):
        inventory.unit_name(unit)


@pytest.mark.parametrize("scope", ["system", "user"])
@pytest.mark.parametrize("state", ["active", "inactive"])
@pytest.mark.parametrize("suffix", ["service", "timer"])
def test_named_observation_never_authorizes(monkeypatch, scope, state, suffix):
    unit = "example." + suffix
    calls = runner(monkeypatch, metadata(unit, state))
    report = inventory.inventory([unit] if scope == "system" else [], [unit] if scope == "user" else [], expected_user_uid=os.getuid())
    assert report["observations"][0]["observation"] == state
    assert report["handover_verified"] is False
    assert report["activation_ready"] is False
    assert report["all_writers_absent"] is None
    assert report["manual_writer_review"] == "pending"
    assert report["schema_evidence"] == "unmeasured"
    command, kwargs = calls[0]
    assert command[:3] == ["systemctl", "--" + scope, "show"]
    assert command[-2:] == ["--", unit]
    assert kwargs["timeout"] == 5
    assert "shell" not in kwargs
    assert "Environment" not in " ".join(command)
    assert "ExecStart" not in " ".join(command)


@pytest.mark.parametrize("missing", inventory.PROPERTIES + ("MainPID", "Restart"))
def test_missing_property_is_unknown(monkeypatch, missing):
    values = metadata()
    del values[missing]
    runner(monkeypatch, values)
    assert inventory.observe("system", "example.service")["observation"] == "unknown"


@pytest.mark.parametrize("changes", [dict(FragmentPath=""), dict(Id="other.service"), dict(MainPID="broken"), dict(MainPID="12"), dict(Restart=""), dict(ActiveState="activating"), dict(ActiveState="failed"), dict(Environment="SECRET")])
def test_bad_or_unsettled_metadata_is_unknown(monkeypatch, changes):
    values = metadata()
    values.update(changes)
    runner(monkeypatch, values)
    result = inventory.observe("system", "example.service")
    assert result["observation"] == "unknown"
    assert "SECRET" not in json.dumps(result)


def test_nonzero_discards_even_successful_looking_output(monkeypatch):
    runner(monkeypatch, metadata(), code=1)
    result = inventory.observe("system", "example.service")
    assert result["observation"] == "unknown"
    assert result["properties"] == {}
    assert "SECRET" not in json.dumps(result)


@pytest.mark.parametrize("error", [subprocess.TimeoutExpired("SECRET", 5), OSError("SECRET")])
def test_probe_errors_are_unknown(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(inventory.subprocess, "run", fail)
    result = inventory.observe("user", "example.service", expected_user_uid=os.getuid())
    assert result["observation"] == "unknown"
    assert "SECRET" not in json.dumps(result)


def test_external_report_exclusive_and_private(tmp_path, monkeypatch):
    # The host sandbox has a /tmp/.git sentinel; model an external directory.
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: False if path == Path("/tmp/.git") else original_exists(path))
    path = tmp_path / "report.json"
    inventory.write_report(path, "{}\n")
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        inventory.write_report(path, "changed")
    assert path.read_text() == "{}\n"


def test_refuses_git_output(tmp_path):
    (tmp_path / ".git").write_text("gitdir: elsewhere")
    with pytest.raises(ValueError):
        inventory.write_report(tmp_path / "report.json", "{}")


def test_cli_unknown_has_nonzero_exit_and_json(monkeypatch, capsys):
    runner(monkeypatch, metadata(), code=1)
    assert inventory.main(["--system-unit", "example.service"]) == 1
    assert json.loads(capsys.readouterr().out)["activation_ready"] is False


def test_cli_requires_explicit_scope_input():
    with pytest.raises(SystemExit) as error:
        inventory.main([])
    assert error.value.code == 2


@pytest.mark.parametrize("nested", [False, True])
def test_refuses_immutable_release_output(tmp_path, monkeypatch, nested):
    # Model an external Git-free release despite this host's /tmp/.git sentinel.
    original_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda path: False if path == Path("/tmp/.git") else original_exists(path))
    (tmp_path / ".slomix-release.json").write_text("{}")
    parent = tmp_path / "nested" if nested else tmp_path
    parent.mkdir(exist_ok=True)
    output = parent / "report.json"
    with pytest.raises(ValueError, match="immutable release"):
        inventory.write_report(output, "{}")
    assert not output.exists()


@pytest.mark.parametrize('name', ['.git', '.slomix-release.json'])
def test_report_refuses_even_a_dangling_boundary_marker(tmp_path, name):
    (tmp_path / name).symlink_to(tmp_path / 'missing-marker-target')
    output = tmp_path / 'report.json'
    with pytest.raises(ValueError, match='outside'):
        inventory.write_report(output, '{}')
    assert not output.exists()


@pytest.mark.parametrize('name', ['.git', '.slomix-release.json'])
def test_writer_report_cannot_create_reserved_marker(tmp_path, name):
    before = set(tmp_path.iterdir())
    with pytest.raises(ValueError, match='reserved'):
        inventory.write_report(tmp_path / name, '{}')
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize('name', ['worker@one.service', 'worker@one.timer', 'worker.service'])
def test_concrete_instances_remain_supported(name):
    assert inventory.unit_name(name) == name


@pytest.mark.parametrize('expected', [None, -1, True, '1000'])
def test_user_identity_required_before_probe(monkeypatch, expected):
    calls = runner(monkeypatch, metadata())
    result = inventory.observe('user', 'example.service', expected_user_uid=expected)
    assert result['observation'] == 'unknown'
    assert result['error'] == 'expected_user_identity_required'
    assert calls == []


@pytest.mark.parametrize('changed', ['real', 'effective', 'expected'])
def test_wrong_user_identity_never_probes_another_manager(monkeypatch, changed):
    uid = os.getuid()
    calls = runner(monkeypatch, metadata())
    monkeypatch.setattr(inventory.os, 'getuid', lambda: uid + (changed == 'real'))
    monkeypatch.setattr(inventory.os, 'geteuid', lambda: uid + (changed == 'effective'))
    expected = uid + (changed == 'expected')
    result = inventory.observe('user', 'example.service', expected_user_uid=expected)
    assert result['observation'] == 'unknown' and result['error'] == 'user_identity_mismatch'
    assert result['user_identity']['expected_uid'] == expected
    assert calls == []


def test_user_observation_records_uid_and_pins_manager_bus(monkeypatch):
    uid = os.getuid()
    calls = runner(monkeypatch, metadata())
    monkeypatch.setenv('XDG_RUNTIME_DIR', '/synthetic/wrong-user')
    monkeypatch.setenv('DBUS_SESSION_BUS_ADDRESS', 'unix:path=/synthetic/wrong-bus')
    monkeypatch.setenv('SYSTEMD_BUS_ADDRESS', 'unix:path=/synthetic/wrong-bus')
    result = inventory.observe('user', 'example.service', expected_user_uid=uid)
    assert result['user_identity'] == {'expected_uid': uid, 'real_uid': uid, 'effective_uid': uid}
    assert result['observation'] == 'inactive'
    environment = calls[0][1]['env']
    assert environment['XDG_RUNTIME_DIR'] == f'/run/user/{uid}'
    assert environment['DBUS_SESSION_BUS_ADDRESS'] == f'unix:path=/run/user/{uid}/bus'
    assert 'SYSTEMD_BUS_ADDRESS' not in environment


def test_cli_user_scope_requires_expected_uid():
    with pytest.raises(SystemExit) as error:
        inventory.main(['--user-unit', 'example.service'])
    assert error.value.code == 2


@pytest.mark.parametrize('case', ['matched', 'wrong-user', 'template'])
def test_native_cli_binds_user_identity_before_systemctl(tmp_path, case):
    import sys

    trace = tmp_path / 'probe.json'
    command = tmp_path / 'systemctl'
    command.write_text('#!/usr/bin/python3 -B\nimport json,os\n'
                       f'open({str(trace)!r}, "w").write(json.dumps({{"bus": os.environ.get("DBUS_SESSION_BUS_ADDRESS")}}))\n'
                       f'print({chr(10).join(k+"="+v for k,v in metadata().items())!r})\n')
    command.chmod(0o700)
    uid = os.getuid()
    unit = 'worker@.service' if case == 'template' else 'example.service'
    result = subprocess.run([sys.executable, '-B', inventory.__file__, '--user-unit', unit,
                             '--expected-user-uid', str(uid + (case == 'wrong-user'))],
                            env={'PATH': str(tmp_path) + os.pathsep + os.defpath,
                                 'DBUS_SESSION_BUS_ADDRESS': 'unix:path=/synthetic/wrong-bus'},
                            capture_output=True, text=True, timeout=5)
    if case == 'template':
        assert result.returncode == 2 and not trace.exists()
        return
    report = json.loads(result.stdout)
    row = report['observations'][0]
    assert row['user_identity']['expected_uid'] == uid + (case == 'wrong-user')
    assert report['activation_ready'] is False and report['all_writers_absent'] is None
    if case == 'wrong-user':
        assert result.returncode == 1 and row['observation'] == 'unknown' and not trace.exists()
    else:
        assert result.returncode == 0 and row['observation'] == 'inactive'
        assert json.loads(trace.read_text())['bus'] == f'unix:path=/run/user/{uid}/bus'


def test_native_writer_report_refuses_bare_git_ancestor(tmp_path):
    import sys

    bare = tmp_path / 'bare-repository'
    subprocess.run(['git', 'init', '--bare', '--template=', str(bare)],
                   check=True, capture_output=True)
    target = bare / 'report.json'
    # No user units means no manager/DB access; explicit invalid-name refusal is separate.
    result = subprocess.run([sys.executable, '-B', '-c',
                             'import sys;sys.path.insert(0,sys.argv[1]);'
                             'from scripts.runtime_writer_inventory import write_report;'
                             'from pathlib import Path;write_report(Path(sys.argv[2]),"{}")',
                             str(Path(inventory.__file__).parents[1]), str(target)],
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0 and not target.exists()
    assert 'outside a Git checkout' in result.stderr
