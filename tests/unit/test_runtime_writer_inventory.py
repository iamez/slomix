"""Named metadata is an observation, never handover authority."""
import argparse
import json
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


@pytest.mark.parametrize("unit", ["*", "*.service", "--help", "../x.service", "x.socket", "x.service\n", "x service", "x;stop.service"])
def test_rejects_ambiguous_names(unit):
    with pytest.raises(argparse.ArgumentTypeError):
        inventory.unit_name(unit)


@pytest.mark.parametrize("scope", ["system", "user"])
@pytest.mark.parametrize("state", ["active", "inactive"])
@pytest.mark.parametrize("suffix", ["service", "timer"])
def test_named_observation_never_authorizes(monkeypatch, scope, state, suffix):
    unit = "example." + suffix
    calls = runner(monkeypatch, metadata(unit, state))
    report = inventory.inventory([unit] if scope == "system" else [], [unit] if scope == "user" else [])
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
    result = inventory.observe("user", "example.service")
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
