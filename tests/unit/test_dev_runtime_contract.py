"""Offline unit preparation and drift guards; never starts services or databases."""
import json
import secrets
import shlex
from pathlib import Path

import pytest

from scripts import dev_runtime_contract as contract
from scripts import dev_schema_preflight as schema
from scripts import dev_verify_health as health
from shared.release_manifest import MANIFEST, file_hash
from shared.runtime_environment import load_environment, read_external_environment, refuse_config_overrides

_FIXTURE_PASSWORD = secrets.token_urlsafe()


@pytest.fixture
def inputs(tmp_path):
    home = tmp_path / "runtime"
    release = home / "releases" / ("a" * 40)
    state = home / "shared"
    release.mkdir(parents=True)
    (state / "config").mkdir(parents=True)
    files = {}
    for name in ("scripts/dev_runtime_contract.py", "scripts/dev_schema_preflight.py",
                 "bot/ultimate_bot.py", "website/backend/main.py"):
        path = release / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# synthetic; never executed\n")
        files[name] = file_hash(path)
    (release / MANIFEST).write_text(json.dumps({"version": 1, "source_commit": "a" * 40, "files": files}))
    result = dict(release=release, state=state)
    for role in ("bot", "web"):
        python = home / "envs" / ("a" * 40) / role / "bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("# fake interpreter; never executed\n")
        python.chmod(0o700)
        (python.parent.parent / "pyvenv.cfg").write_text("home = /synthetic\n")
        env = state / "config" / f"{role}.env"
        values = dict(zip(("POSTGRES_" + key for key in ("HOST", "PORT", "DATABASE", "USER")),
                          contract.IDENTITIES[role]))
        values.update(BOT_ENVIRONMENT="dev", DATABASE_TYPE="postgresql", POSTGRES_SSL_MODE="disable",
                      POSTGRES_PASSWORD=_FIXTURE_PASSWORD, MAINTENANCE_RETENTION_ENABLED="false")
        for key, path in contract.state_paths(state, role).items():
            values[key] = str(path)
            (path.parent if key == "METRICS_DB_PATH" else path).mkdir(parents=True, exist_ok=True)
        env.write_text("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
        env.chmod(0o600)
        result[f"{role}_python"] = python
        result[f"{role}_env"] = env
    return result


def test_preparation_has_no_secrets_and_never_overwrites(inputs, tmp_path):
    output = tmp_path / "prepared"
    result = contract.prepare(output, **inputs)
    assert result["status"] == "prepared_not_installed"
    record = contract.load_contract(output / "contract.json")
    assert record["revision"] == "a" * 40
    for path in output.iterdir():
        assert _FIXTURE_PASSWORD not in path.read_text()
    unit = (output / "etlegacy-bot.service").read_text()
    assert "ExecStartPre=" in unit and "--release-mode" in unit
    assert "ProtectSystem=strict" in unit and "PYTHONDONTWRITEBYTECODE=1" in unit
    assert "EnvironmentFile=" not in unit
    with pytest.raises(ValueError, match="NEW"):
        contract.prepare(output, **inputs)


@pytest.mark.parametrize("failure", ["config", "interpreter", "venv", "payload", "record"])
def test_saved_contract_refuses_drift(inputs, tmp_path, failure):
    output = tmp_path / "prepared"
    contract.prepare(output, **inputs)
    if failure == "config":
        with inputs["bot_env"].open("a") as stream:
            stream.write("LOG_LEVEL=DEBUG\n")
    elif failure == "interpreter":
        inputs["bot_python"].write_text("different executable")
    elif failure == "venv":
        (inputs["bot_python"].parent.parent / "pyvenv.cfg").write_text("changed")
    elif failure == "payload":
        (inputs["release"] / "extra.py").write_text("wrong")
    else:
        path = output / "contract.json"
        record = json.loads(path.read_text())
        record["services"]["etlegacy-bot"]["argv"] += ["--extra"]
        path.write_text(json.dumps(record))
    with pytest.raises(ValueError):
        contract.load_contract(output / "contract.json")


@pytest.mark.parametrize("line", ["BOT_ENVIRONMENT=production", "POSTGRES_HOST=remote",
                                  "BOT_LOG_DIR=/", "MAINTENANCE_RETENTION_ENABLED=true",
                                  "PYTHONPATH=/unsafe", "SLOMIX_ENV_FILE=/shadow"])
def test_unsafe_configuration_is_refused_without_echo(inputs, line):
    with inputs["bot_env"].open("a") as stream:
        stream.write(line + "\n")
    with pytest.raises(ValueError) as error:
        contract.build_contract(**inputs)
    assert _FIXTURE_PASSWORD not in str(error.value)


@pytest.mark.parametrize("key", ["POSTGRES_PASSWORD", "PGSERVICE", "DATABASE_URL", "PYTHONPATH", "SSH_ENABLED"])
def test_prestart_rejects_inherited_overrides(key):
    with pytest.raises(ValueError, match="Inherited environment") as error:
        refuse_config_overrides({"SSH_ENABLED": "false"}, {key: "secret-no-echo"})
    assert "secret-no-echo" not in str(error.value)


def test_application_rejects_config_changed_after_prestart(inputs, monkeypatch):
    env = inputs["bot_env"]
    monkeypatch.setenv("SLOMIX_ENV_FILE", str(env))
    monkeypatch.setenv("SLOMIX_ENV_SHA256", file_hash(env))
    with env.open("a") as stream:
        stream.write("NEW_PROOF_KEY=must-not-be-applied\n")
    with pytest.raises(ValueError, match="approved startup digest"):
        load_environment(root=inputs["release"])


def test_prepared_hash_accepts_exact_file_snapshot(inputs):
    env = inputs["bot_env"]
    assert read_external_environment(env, root=inputs["release"], expected_digest=file_hash(env))["BOT_ENVIRONMENT"] == "dev"


def test_connection_options_recheck_approved_snapshot(inputs):
    env = inputs["bot_env"]
    approved = file_hash(env)
    with env.open("a") as stream:
        stream.write("POSTGRES_PASSWORD=changed-synthetic-value\n")
    with pytest.raises(ValueError, match="approved startup digest"):
        schema.connection_options(env, ("192.168.64.116", 5432, "etlegacy", "etlegacy_user"),
                                  release_root=inputs["release"], expected_digest=approved)


@pytest.mark.parametrize("damage", [None, "digest", "inherited", "payload", "migration_path"])
def test_release_prestart_cli_refuses_before_database(inputs, monkeypatch, capsys, damage):
    from unittest.mock import AsyncMock

    record = contract.build_contract(**inputs)
    spec = record["services"]["etlegacy-bot"]
    root = inputs["release"]
    sql = root / "migrations/001.sql"
    sql.parent.mkdir()
    sql.write_text("SELECT 1;\n")
    manifest = json.loads((root / MANIFEST).read_text())
    manifest["files"]["migrations/001.sql"] = file_hash(sql)
    (root / MANIFEST).write_text(json.dumps(manifest))
    monkeypatch.setattr(schema, "__file__", str(root / "scripts/dev_schema_preflight.py"))
    monkeypatch.setattr(schema.os, "environ", dict(spec["environment"]))
    inspect = AsyncMock(return_value={"clean": True})
    monkeypatch.setattr(schema, "inspect_database", inspect)
    args = list(spec["pre_argv"][2:])
    if damage == "digest":
        with inputs["bot_env"].open("a") as stream:
            stream.write("OTHER=value\n")
    elif damage == "inherited":
        schema.os.environ["PGSERVICE"] = "wrong"
    elif damage == "payload":
        sql.write_text("SELECT 2;\n")
    elif damage == "migration_path":
        args[-1] = str(root)
    assert schema.main(args) == (1 if damage else 0)
    output = json.loads(capsys.readouterr().out)
    assert output["clean"] is (damage is None)
    if damage:
        inspect.assert_not_called()
    else:
        inspect.assert_awaited_once()
        assert inspect.call_args.args[0]["host"] == "192.168.64.116"
        assert inspect.call_args.args[0]["server_settings"]["default_transaction_read_only"] == "on"


def properties(spec, pid):
    def command(argv):
        return f"{{ path={argv[0]} ; argv[]={' '.join(argv)} ; ignore_errors=no ; pid=0 }}"
    return dict(LoadState="loaded", ActiveState="active", MainPID=str(pid),
                WorkingDirectory=spec["cwd"], User="samba", Group="samba",
                ExecStart=command(spec["argv"]), ExecStartPre=command(spec["pre_argv"]),
                Environment=" ".join(shlex.quote(f"{k}={v}") for k, v in spec["environment"].items()),
                EnvironmentFiles="", PassEnvironment="", UnsetEnvironment="", ProtectSystem="strict",
                NoNewPrivileges="yes", PrivateTmp="yes", ReadOnlyPaths=" ".join(spec["read_only"]),
                ReadWritePaths=" ".join(spec["read_write"]),
                MemoryMax={"1G": "1073741824", "512M": "536870912"}[spec["memory_max"]],
                CPUQuotaPerSecUSec={"200%": "2s", "100%": "1s"}[spec["cpu_quota"]])


@pytest.mark.parametrize("damage", [None, "Environment", "ProtectSystem", "ReadWritePaths", "ExecStartPre", "UnsetEnvironment"])
def test_resolved_unit_matches_exact_contract(inputs, monkeypatch, damage):
    record = contract.build_contract(**inputs)
    def output(argv, **kwargs):
        name = argv[2]
        values = properties(record["services"][name], 101 if name == "etlegacy-bot" else 102)
        if damage:
            values[damage] = "wrong"
        return "\n".join(f"{k}={v}" for k, v in values.items())
    monkeypatch.setattr(health.subprocess, "check_output", output)
    if damage:
        with pytest.raises(ValueError):
            health.units(inputs["release"], record)
    else:
        assert health.units(inputs["release"], record)["etlegacy-bot"]["pid"] == 101


@pytest.mark.parametrize("damage", [None, "exe", "argv", "bootstrap", "inherited", "revision"])
def test_release_readiness_checks_actual_process(inputs, monkeypatch, damage):
    record = contract.build_contract(**inputs)
    state = {name: {"pid": pid, "active": "active", "cwd": spec["cwd"]}
             for pid, (name, spec) in enumerate(record["services"].items(), 101)}
    by_pid = {str(state[name]["pid"]): spec for name, spec in record["services"].items()}
    monkeypatch.setattr(health, "units", lambda *args: state)
    monkeypatch.setattr(health.os, "readlink", lambda path: by_pid[path.split('/')[2]]["cwd"])
    monkeypatch.setattr(health, "file_hash", lambda path: "wrong" if damage == "exe" else by_pid[path.parts[2]]["python_sha256"])
    original_read = Path.read_bytes
    def read_bytes(path):
        if not str(path).startswith('/proc/'):
            return original_read(path)
        spec = by_pid[path.parts[2]]
        if path.name == "cmdline":
            argv = ["wrong"] if damage == "argv" else spec["argv"]
            return ("\0".join(argv) + "\0").encode()
        env = dict(spec["environment"])
        if damage == "bootstrap":
            env["SLOMIX_ENV_FILE"] = "/wrong"
        if damage == "inherited":
            env["POSTGRES_PASSWORD"] = "secret-no-echo"  # noqa: S105 - synthetic override sentinel
        return ("\0".join(f"{k}={v}" for k, v in env.items()) + "\0").encode()
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    monkeypatch.setattr(health, "read_json", lambda path: (
        {"status": "ok", "database": "ok"} if path == "/health" else
        {"revision": "a" * 40, "started_at": "2026-01-01T00:00:00+00:00"}))
    previous = {"_captured_at": 0, "etlegacy-bot": {"pid": 1}, "etlegacy-web": {"pid": 2}}
    target = "b" * 40 if damage == "revision" else "a" * 40
    if damage:
        with pytest.raises(ValueError) as error:
            health.check(inputs["release"], target, previous, record)
        assert "secret-no-echo" not in str(error.value)
    else:
        assert health.check(inputs["release"], target, previous, record) == state


@pytest.mark.asyncio
async def test_disabled_retention_preserves_old_files_and_backups(inputs, monkeypatch):
    import os
    from types import SimpleNamespace

    from bot.services.automation.database_maintenance import DatabaseMaintenance

    monkeypatch.setenv("BOT_LOG_DIR", str(inputs["state"] / "logs/bot"))
    monkeypatch.setenv("MAINTENANCE_RETENTION_ENABLED", "false")
    maintenance = DatabaseMaintenance(SimpleNamespace(), None, 0)
    paths = [Path(maintenance.log_dir) / "archive.txt"]
    paths += [Path(maintenance.backup_dir) / f"backup_{i}.dump" for i in range(10)]
    for path in paths:
        path.write_bytes(b"synthetic historical content")
        os.utime(path, (1, 1))
    before = {path: file_hash(path) for path in paths}
    assert await maintenance.cleanup_old_logs() == 0
    await maintenance._cleanup_old_backups()  # noqa: SLF001 - guard entrypoint
    assert before == {path: file_hash(path) for path in paths}


def test_standard_symlink_venv_keeps_lexical_executable_and_prefix(inputs):
    import subprocess
    import sys

    venv = inputs['release'].parent.parent / 'envs' / 'symlink-proof' / 'bot'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(venv)],
                   check=True, capture_output=True, timeout=20)
    python = venv / 'bin/python'
    assert python.is_symlink()
    values = inputs | {'bot_python': python}
    record = contract.build_contract(**values)
    assert record['services']['etlegacy-bot']['argv'][0] == str(python)
    observed = subprocess.check_output([str(python), '-I', '-c',
                                       'import json,sys; print(json.dumps([sys.executable,sys.prefix]))'],
                                      text=True, timeout=10)
    assert json.loads(observed) == [str(python), str(venv)]


@pytest.mark.parametrize('property_name,value', [('MemoryMax', 'infinity'), ('MemoryMax', ''),
                                               ('CPUQuotaPerSecUSec', 'infinity'),
                                               ('CPUQuotaPerSecUSec', '')])
def test_resolved_resource_overrides_refuse_readiness(inputs, property_name, value):
    record = contract.build_contract(**inputs)
    spec = record['services']['etlegacy-bot']
    values = properties(spec, 123)
    health.release_unit_matches('etlegacy-bot', values, spec)
    values[property_name] = value
    with pytest.raises(ValueError, match='configuration differs'):
        health.release_unit_matches('etlegacy-bot', values, spec)


@pytest.mark.parametrize('alias', ['venv', 'config'])
def test_venv_link_support_does_not_allow_parent_or_config_aliases(inputs, alias):
    if alias == 'venv':
        original = inputs['bot_python'].parent.parent
        linked = original.parent.parent / 'alias' / 'bot'
        linked.parent.mkdir()
        linked.symlink_to(original, target_is_directory=True)
        inputs['bot_python'] = linked / 'bin/python'
    else:
        config = inputs['bot_python'].parent.parent / 'pyvenv.cfg'
        held = config.with_name('retained-venv-config')
        config.rename(held)
        config.symlink_to(held)
    with pytest.raises(ValueError, match='canonical'):
        contract.build_contract(**inputs)
