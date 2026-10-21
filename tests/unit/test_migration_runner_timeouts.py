"""The actual migration connection, not its test replacement, owns budgets."""

from unittest.mock import AsyncMock

import pytest

from tests.integration import test_apply_migrations_pg as migration_fixtures

migration_runner = migration_fixtures.migration_runner


@pytest.fixture(autouse=True)
def clean_timeout_env(monkeypatch):
    for name in ("CONNECT", "COMMAND", "STATEMENT", "LOCK"):
        monkeypatch.delenv(f"MIGRATION_{name}_TIMEOUT_SECONDS", raising=False)


async def test_real_connection_supplies_finite_defaults(monkeypatch, migration_runner):
    connect = AsyncMock()
    monkeypatch.setattr(migration_runner.asyncpg, "connect", connect)
    conn = await migration_runner.get_connection()
    assert conn is connect.return_value
    connect.assert_awaited_once_with(
        **migration_runner.get_connection_kwargs(), timeout=10, command_timeout=600,
        server_settings={"application_name": "slomix-migrations",
                         "lock_timeout": "5s", "statement_timeout": "300s"},
    )


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1.5", "", "3601", "secret-value"])
async def test_invalid_budget_refuses_before_connect(monkeypatch, migration_runner, value):
    monkeypatch.setenv("MIGRATION_CONNECT_TIMEOUT_SECONDS", value)
    connect = AsyncMock()
    monkeypatch.setattr(migration_runner.asyncpg, "connect", connect)
    with pytest.raises(ValueError, match="MIGRATION_CONNECT_TIMEOUT_SECONDS must be") as error:
        await migration_runner.get_connection()
    assert str(error.value) == "MIGRATION_CONNECT_TIMEOUT_SECONDS must be an integer between 1 and 3600 seconds"
    connect.assert_not_awaited()


@pytest.mark.parametrize("name,value", [("LOCK", "301"), ("COMMAND", "300")])
def test_incoherent_budgets_refuse(monkeypatch, migration_runner, name, value):
    monkeypatch.setenv(f"MIGRATION_{name}_TIMEOUT_SECONDS", value)
    with pytest.raises(ValueError, match="LOCK <= STATEMENT < COMMAND"):
        migration_runner.get_timeout_kwargs()


def test_explicit_finite_budgets(monkeypatch, migration_runner):
    for name, value in (("CONNECT", "2"), ("COMMAND", "5"), ("STATEMENT", "3"), ("LOCK", "1")):
        monkeypatch.setenv(f"MIGRATION_{name}_TIMEOUT_SECONDS", value)
    assert migration_runner.get_timeout_kwargs() == {
        "timeout": 2, "command_timeout": 5,
        "server_settings": {"application_name": "slomix-migrations",
                            "lock_timeout": "1s", "statement_timeout": "3s"},
    }


async def test_close_is_bounded(monkeypatch, migration_runner):
    conn = AsyncMock()
    seen = []

    async def wait_for(awaitable, *, timeout):
        seen.append(timeout)
        await awaitable

    monkeypatch.setattr(migration_runner.asyncio, "wait_for", wait_for)
    await migration_runner.close_connection(conn)
    assert seen == [10]
    conn.close.assert_awaited_once_with()
