"""Bounded read-only schema gate: no database or service is contacted here."""
import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

PATH = Path(__file__).resolve().parents[2] / "scripts/dev_schema_preflight.py"
SPEC = importlib.util.spec_from_file_location("dev_schema_preflight", PATH)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


def env_file(tmp_path, password=""):
    path = tmp_path / "explicit.env"
    path.write_text("DATABASE_TYPE=postgresql\nPOSTGRES_HOST=/tmp/private-pg\nPOSTGRES_PORT=5432\n"
                    "POSTGRES_DATABASE=proof\nPOSTGRES_USER=owner\n"
                    f"POSTGRES_PASSWORD='{password}'\n")
    return path


EXPECTED = ("/tmp/private-pg", 5432, "proof", "owner")


def good_columns():
    return [{"table_name": table, "column_name": column, "data_type": kind,
             "not_null": not_null}
            for (table, column), (kind, not_null) in gate.REQUIRED_COLUMNS.items()]


def test_explicit_config_ignores_shell_and_disables_interpolation(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTGRES_HOST", "wrong-host")
    monkeypatch.setenv("POSTGRES_PASSWORD", "process-secret")
    monkeypatch.setenv("TEST_SECRET", "interpolated-secret")
    options = gate.connection_options(env_file(tmp_path, "${TEST_SECRET}"), EXPECTED)
    assert options["password"] == "${TEST_SECRET}"  # noqa: S105 - interpolation sentinel
    assert options["host"] == EXPECTED[0]
    assert options["timeout"] == 5
    assert options["command_timeout"] == 10
    assert options["server_settings"]["default_transaction_read_only"] == "on"
    assert options["server_settings"]["lock_timeout"] == "2000"
    assert options["server_settings"]["statement_timeout"] == "8000"


def test_explicit_empty_password_allowed(tmp_path):
    assert gate.connection_options(env_file(tmp_path), EXPECTED)["password"] == ""


@pytest.mark.parametrize("engine", ["sqlite", "", "mysql"])
def test_wrong_or_missing_engine_refused(tmp_path, engine):
    path = env_file(tmp_path)
    path.write_text(path.read_text().replace("DATABASE_TYPE=postgresql", "DATABASE_TYPE=" + engine))
    with pytest.raises(gate.PreflightError, match="DATABASE_TYPE"):
        gate.connection_options(path, EXPECTED)


@pytest.mark.parametrize("source", ["env", "config"])
def test_ssl_override_not_silently_ignored(tmp_path, source):
    path = env_file(tmp_path)
    if source == "env":
        path.write_text(path.read_text() + "POSTGRES_SSL_MODE=require\n")
    else:
        (tmp_path / "bot_config.json").write_text('{"POSTGRES_SSL_MODE": "require"}')
    with pytest.raises(gate.PreflightError, match="SSL_MODE"):
        gate.connection_options(path, EXPECTED)


@pytest.mark.parametrize("index,value", [(0, "other"), (1, 55432), (2, "other"), (3, "other")])
def test_identity_mismatch_fails_before_connection(tmp_path, index, value):
    expected = list(EXPECTED)
    expected[index] = value
    with pytest.raises(gate.PreflightError, match="identity"):
        gate.connection_options(env_file(tmp_path), tuple(expected))


@pytest.mark.parametrize("key", ["HOST", "PORT", "DATABASE", "USER", "PASSWORD"])
def test_missing_explicit_key_never_uses_environment(tmp_path, monkeypatch, key):
    path = env_file(tmp_path)
    path.write_text("\n".join(line for line in path.read_text().splitlines()
                              if not line.startswith("POSTGRES_" + key + "=")))
    monkeypatch.setenv("POSTGRES_" + key, "fallback-secret")
    with pytest.raises(gate.PreflightError, match="required"):
        gate.connection_options(path, EXPECTED)


def test_ledger_clean_and_unknown_checksum_is_explicit():
    ledger = [{"filename": "001.sql", "checksum": None, "success": True}]
    report = gate.compare_contract({"001.sql": "hash"}, ledger, good_columns())
    assert report["clean"]
    assert report["unknown_checksums"] == ["001.sql"]


@pytest.mark.parametrize("ledger,checksums,key", [
    ([], {"001.sql": "hash"}, "pending"),
    ([{"filename": "001.sql", "checksum": "hash", "success": False}],
     {"001.sql": "hash"}, "failed"),
    ([{"filename": "001.sql", "checksum": "changed", "success": True}],
     {"001.sql": "hash"}, "checksum_mismatches"),
    ([{"filename": "001.sql", "checksum": "hash", "success": True}], {}, "missing"),
])
def test_ledger_drift_fails(ledger, checksums, key):
    report = gate.compare_contract(checksums, ledger, good_columns())
    assert not report["clean"]
    assert report[key] == ["001.sql"]


@pytest.mark.parametrize("index", range(3))
@pytest.mark.parametrize("damage", ["missing", "type", "nullability"])
def test_recorded_migrations_do_not_hide_bad_columns(index, damage):
    columns = good_columns()
    if damage == "missing":
        columns.pop(index)
    elif damage == "type":
        columns[index]["data_type"] = "bigint"
    else:
        columns[index]["not_null"] = not columns[index]["not_null"]
    ledger = [{"filename": "103.sql", "checksum": "hash", "success": True}]
    report = gate.compare_contract({"103.sql": "hash"}, ledger, columns)
    assert not report["clean"]
    assert len(report["invalid_columns"]) == 1


def test_empty_or_symlink_migrations_refused(tmp_path):
    with pytest.raises(gate.PreflightError):
        gate.migration_checksums(tmp_path)
    sql = tmp_path / "001.sql"
    sql.write_text("SELECT 1;")
    assert len(gate.migration_checksums(tmp_path)["001.sql"]) == 64
    (tmp_path / "002.sql").symlink_to(sql)
    with pytest.raises(gate.PreflightError):
        gate.migration_checksums(tmp_path)


class Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class Connection:
    def __init__(self):
        self.fetchrow = AsyncMock(return_value={"database": "proof", "role": "owner", "read_only": "on"})
        self.fetchval = AsyncMock(return_value="schema_migrations")
        self.fetch = AsyncMock(side_effect=[[], good_columns()])
        self.close = AsyncMock()
        self.transaction_options = None

    def transaction(self, **kwargs):
        self.transaction_options = kwargs
        return Transaction()


async def test_only_read_queries_and_repeatable_read_transaction(monkeypatch):
    conn = Connection()
    connect = AsyncMock(return_value=conn)
    monkeypatch.setattr(gate.asyncpg, "connect", connect)
    assert (await gate.inspect_database({"database": "proof", "user": "owner"}, {}))["clean"]
    assert conn.transaction_options == {"isolation": "repeatable_read", "readonly": True}
    for method in (conn.fetchrow, conn.fetchval, conn.fetch):
        assert all(call.args[0].startswith("SELECT ") for call in method.call_args_list)
    assert "public.schema_migrations" in conn.fetch.call_args_list[0].args[0]
    assert "n.nspname='public'" in conn.fetch.call_args_list[1].args[0]
    conn.close.assert_awaited_once_with(timeout=5)


async def test_missing_ledger_refuses_without_create(monkeypatch):
    conn = Connection()
    conn.fetchval.return_value = None
    monkeypatch.setattr(gate.asyncpg, "connect", AsyncMock(return_value=conn))
    with pytest.raises(gate.PreflightError, match="ledger is missing"):
        await gate.inspect_database({"database": "proof", "user": "owner"}, {})
    conn.fetch.assert_not_awaited()
    conn.close.assert_awaited_once()


@pytest.mark.parametrize("field,value", [("database", "wrong"), ("role", "wrong"), ("read_only", "off")])
async def test_actual_connection_identity_guard(monkeypatch, field, value):
    conn = Connection()
    conn.fetchrow.return_value[field] = value
    monkeypatch.setattr(gate.asyncpg, "connect", AsyncMock(return_value=conn))
    with pytest.raises(gate.PreflightError, match="identity/read-only"):
        await gate.inspect_database({"database": "proof", "user": "owner"}, {})
    conn.fetchval.assert_not_awaited()
    conn.close.assert_awaited_once()


def test_driver_error_cannot_leak_credentials(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate, "inspect_database", AsyncMock(side_effect=ValueError("secret-from-driver")))
    sql = tmp_path / "001.sql"
    sql.write_text("SELECT 1;")
    status = gate.main(["--env-file", str(env_file(tmp_path, "password-secret")),
                        "--expected-host", EXPECTED[0], "--expected-port", "5432",
                        "--expected-database", "proof", "--expected-user", "owner",
                        "--migrations-dir", str(tmp_path)])
    assert status == 1
    output = capsys.readouterr().out
    assert "secret" not in output
    assert "could not complete safely" in output
