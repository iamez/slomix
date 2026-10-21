"""Offline unit preparation and drift guards; never starts services or databases."""
import json
import os
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
def inputs(tmp_path, monkeypatch):
    # CI runs as runner; permission checks still use real effective access.
    monkeypatch.setattr(contract, "service_uid", os.geteuid)
    home = tmp_path / "runtime"
    release = home / "releases" / ("a" * 40)
    state = home / "shared"
    release.mkdir(parents=True)
    (state / "config").mkdir(parents=True)
    files = {}
    for name in ("scripts/dev_runtime_contract.py", "scripts/dev_schema_preflight.py",
                 "bot/ultimate_bot.py", "website/backend/main.py", "shared/release_manifest.py"):
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
    assert 'UnsetEnvironment=' + ' '.join(contract.UNSET_ENVIRONMENT) in unit
    assert "ProtectSystem=strict" in unit and "PYTHONDONTWRITEBYTECODE=1" in unit
    assert "EnvironmentFile=" not in unit
    assert "Requires=postgresql.service\n" in unit
    assert "Wants=network-online.target\n" in unit
    assert "After=network-online.target postgresql.service\n" in unit
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


@pytest.mark.parametrize("key", ["POSTGRES_PASSWORD", "PGSERVICE", "DATABASE_URL", "PYTHONPATH", "LD_AUDIT", "SSH_ENABLED"])
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
    assert spec["pre_argv"][1:3] == ["-I", "-B"]
    args = list(spec["pre_argv"][9:])
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
        return f"{{ path={argv[0]} ; argv[]={shlex.join(argv)} ; ignore_errors=no ; pid=0 }}"
    return dict(Requires=" ".join(spec["requires"]), Wants=" ".join(spec["wants"]),
                After=" ".join(spec["after"]), LoadState="loaded", ActiveState="active", MainPID=str(pid),
                WorkingDirectory=spec["cwd"], User="samba", Group="samba",
                ExecStart=command(spec["argv"]), ExecStartPre=command(spec["pre_argv"]),
                Environment=" ".join(shlex.quote(f"{k}={v}") for k, v in spec["environment"].items()),
                EnvironmentFiles="", PassEnvironment="", UnsetEnvironment=" ".join(spec['unset_environment']), ProtectSystem="strict",
                Restart=spec['restart'], RestartUSec=spec['restart_usec'], InvocationID='a' * 32,
                NoNewPrivileges="yes", PrivateTmp="yes", ReadOnlyPaths=" ".join(spec["read_only"]),
                ReadWritePaths=" ".join(spec["read_write"]),
                MemoryMax={"1G": "1073741824", "512M": "536870912"}[spec["memory_max"]],
                CPUQuotaPerSecUSec={"200%": "2s", "100%": "1s"}[spec["cpu_quota"]])


@pytest.mark.parametrize("damage", [None, "Environment", "ProtectSystem", "ReadWritePaths", "ExecStartPre", "UnsetEnvironment", "Restart", "RestartUSec", "InvocationID", "Requires", "Wants", "After"])
def test_resolved_unit_matches_exact_contract(inputs, monkeypatch, damage):
    record = contract.build_contract(**inputs)
    def output(argv, **kwargs):
        for prop in ("Requires", "Wants", "After"):
            assert any(argv[i:i + 2] == ["-p", prop] for i in range(len(argv) - 1))
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


@pytest.mark.parametrize("damage", [None, "loaded", "exe", "argv", "bootstrap", "inherited", "extra_db", "extra_app", "extra_unknown", "loader", "python_setting", "revision", "not_ready"])
def test_release_readiness_checks_actual_process(inputs, monkeypatch, damage):
    record = contract.build_contract(**inputs)
    state = {name: {"pid": pid, "active": "active", "cwd": spec["cwd"], "invocation_id": 'a' * 32}
             for pid, (name, spec) in enumerate(record["services"].items(), 101)}
    by_pid = {str(state[name]["pid"]): spec for name, spec in record["services"].items()}
    monkeypatch.setattr(health, "units", lambda *args: state)
    def readiness(*args):
        if damage == 'not_ready':
            raise ValueError('Current bot has not completed startup')
    monkeypatch.setattr(health, "bot_ready", readiness)
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
        if damage == "loaded":
            env.update(read_external_environment(Path(spec["environment"]["SLOMIX_ENV_FILE"]), root=inputs["release"]))
        if damage == "extra_db":
            env["PGSERVICE"] = "unexpected"
        if damage == "extra_app":
            env["BETS_LIFECYCLE_SECONDS"] = "1"
        if damage == "extra_unknown":
            env["UNAPPROVED_CUSTOM_OPTION"] = "1"
        if damage == "python_setting":
            env["PYTHONPLATLIBDIR"] = "unexpected"
        if damage == "loader":
            env["LD_AUDIT"] = "/unsafe"
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
    if damage not in (None, "loaded"):
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


@pytest.mark.parametrize("kind", ["directory", "ancestor", "metrics", "user"])
def test_state_permissions_are_checked_as_service_account(inputs, monkeypatch, kind):
    path = inputs["state"] / "data/stats"
    mode = None
    if kind == "metrics":
        path = inputs["state"] / "logs/bot/metrics/metrics.db"
        path.write_text("synthetic state")
    elif kind == "ancestor":
        path = inputs["state"] / "data"
    elif kind == "user":
        monkeypatch.setattr(contract, "service_uid", lambda: os.geteuid() + 1)
    if kind != "user":
        mode = path.stat().st_mode
        path.chmod(0o600 if kind == "ancestor" else 0o500 if kind == "directory" else 0o400)
    try:
        with pytest.raises((ValueError, PermissionError)):
            contract.build_contract(**inputs)
    finally:
        if mode is not None:
            path.chmod(mode)
    if kind != "user":
        assert contract.build_contract(**inputs)["revision"] == "a" * 40


@pytest.mark.parametrize('role', ['bot', 'web'])
def test_actual_application_python_flags_ignore_ambient_settings(inputs, role):
    import subprocess
    import sys

    spec = contract.build_contract(**inputs)['services']['etlegacy-' + role]
    assert spec['argv'][1:4] == ['-I', '-B', '-c']
    result = subprocess.run([sys.executable, *spec['argv'][1:3], '-c',
                             'import sys; assert sys.flags.ignore_environment; '
                             'assert sys.flags.no_user_site; assert sys.dont_write_bytecode; print("startup-flags-ok")'],
                            env={'PYTHONPLATLIBDIR': 'nonexistent-library'},
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'startup-flags-ok'


@pytest.mark.parametrize('property_name,missing', [('Requires', 'postgresql.service'),
                                                 ('Wants', 'network-online.target'),
                                                 ('After', 'network-online.target'),
                                                 ('After', 'postgresql.service')])
def test_dependencies_allow_implicit_units_but_require_each_contract_member(inputs, property_name, missing):
    spec = contract.build_contract(**inputs)['services']['etlegacy-bot']
    values = properties(spec, 123)
    for name in ('Requires', 'Wants', 'After'):
        values[name] += ' sysinit.target basic.target'
    health.release_unit_matches('etlegacy-bot', values, spec)
    values[property_name] = ' '.join(value for value in values[property_name].split() if value != missing)
    with pytest.raises(ValueError, match='dependencies differ'):
        health.release_unit_matches('etlegacy-bot', values, spec)


@pytest.mark.parametrize('extra', [None, 'BETS_LIFECYCLE_SECONDS', 'PYTHONPLATLIBDIR',
                                  'UNKNOWN_APP_OPTION', 'LD_AUDIT', 'LC_UNKNOWN',
                                  'LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE',
                                  'LC_MEASUREMENT', 'LC_IDENTIFICATION'])
def test_native_child_preflight_checks_environment_before_database(inputs, extra):
    import subprocess
    import sys

    record = contract.build_contract(**inputs)
    spec = record['services']['etlegacy-bot']
    root = inputs['release']
    sql = root / 'migrations/001.sql'
    sql.parent.mkdir()
    sql.write_text('SELECT 1;\n')
    manifest = json.loads((root / MANIFEST).read_text())
    manifest['files']['migrations/001.sql'] = file_hash(sql)
    (root / MANIFEST).write_text(json.dumps(manifest))
    code = '''
import json, sys
sys.path.insert(0, sys.argv[1])
from scripts import dev_schema_preflight as schema
schema.__file__ = sys.argv[2]
calls = []
async def inspect(*args):
    calls.append("database-double")
    return {"clean": True}
schema.inspect_database = inspect
status = schema.main(json.loads(sys.argv[3]))
print(json.dumps({"exit": status, "database_calls": len(calls)}))
'''
    env = dict(spec['environment'], MEMORY_PRESSURE_WATCH='/dev/null')
    if extra:
        # Empty LD_AUDIT prevents the OS loader opening anything before the guard.
        env[extra] = '' if extra == 'LD_AUDIT' else 'C' if extra.startswith('LC_') else '1'
    result = subprocess.run([sys.executable, *spec['pre_argv'][1:3], '-c', code,
                             str(Path(__file__).resolve().parents[2]),
                             str(root / 'scripts/dev_schema_preflight.py'),
                             json.dumps(spec['pre_argv'][9:])], env=env,
                            capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    reports = [json.loads(line) for line in result.stdout.splitlines()]
    refused = extra is not None and extra not in {
        'LC_PAPER', 'LC_NAME', 'LC_ADDRESS', 'LC_TELEPHONE',
        'LC_MEASUREMENT', 'LC_IDENTIFICATION',
    }
    assert reports[-1] == {'exit': 1 if refused else 0, 'database_calls': 0 if refused else 1}
    assert reports[0]['clean'] is (not refused)


def test_unmarked_preflight_override_policy_keeps_legacy_compatibility():
    refuse_config_overrides({}, {'LEGACY_OPERATOR_OPTION': 'value'})
    with pytest.raises(ValueError, match='Unapproved'):
        refuse_config_overrides({}, {'LEGACY_OPERATOR_OPTION': 'value'}, strict=True)
