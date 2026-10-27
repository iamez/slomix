"""Safety contracts use denied/mocked transports; no PostgreSQL is contacted."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from tests import disposable_database as db


def ci_env():
    return dict(RUNTIME_EVENTS_TEST_CI="true", GITHUB_ACTIONS="true",
                POSTGRES_TEST_HOST="127.0.0.1", POSTGRES_TEST_PORT="5432",
                POSTGRES_TEST_DATABASE="etlegacy_test", POSTGRES_TEST_USER="etlegacy_user",
                POSTGRES_TEST_PASSWORD="synthetic")


@pytest.mark.parametrize("key", list(ci_env()))
def test_incomplete_ci_config_is_rejected(key):
    env = ci_env()
    env.pop(key)
    with pytest.raises(ValueError, match="explicit CI isolation"):
        db.connection_options(env)


@pytest.mark.parametrize("key,value", [
    ("POSTGRES_TEST_HOST", "192.168.64.116"), ("POSTGRES_TEST_HOST", "localhost"),
    ("POSTGRES_TEST_PORT", "6543"), ("POSTGRES_TEST_DATABASE", "etlegacy"),
    ("POSTGRES_TEST_USER", "website_app"), ("GITHUB_ACTIONS", "false"),
])
def test_wrong_ci_target_rejected(key, value):
    env = ci_env()
    env[key] = value
    with pytest.raises(ValueError):
        db.connection_options(env)


def test_application_pg_environment_is_not_a_fallback():
    with pytest.raises(ValueError):
        db.connection_options(dict(PGHOST="localhost", PGDATABASE="etlegacy",
                                   POSTGRES_DATABASE="etlegacy"))


def test_ci_options_explicitly_override_libpq_environment():
    options = db.connection_options({**ci_env(), "PGPORT": "6543", "PGUSER": "bad"})
    assert {k: options[k] for k in ("host", "port", "database", "user", "password")} == {
        "host": "127.0.0.1", "port": 5432, "database": "etlegacy_test",
        "user": "etlegacy_user", "password": "synthetic"}
    assert options["timeout"] == options["command_timeout"] == 5


@pytest.mark.parametrize("socket", ["/var/run/postgresql", "/tmp", "relative",
                                    "/tmp/other", "/tmp/slomix-runtime-pg-a/../b"])
def test_unapproved_socket_never_resolves_to_a_target(socket):
    with pytest.raises(ValueError):
        db.connection_options({"RUNTIME_EVENTS_TEST_SOCKET": socket})


def test_private_socket_has_explicit_connection_identity():
    with tempfile.TemporaryDirectory(prefix="slomix-runtime-pg-", dir="/tmp") as directory:
        options = db.connection_options({"RUNTIME_EVENTS_TEST_SOCKET": directory,
                                         "PGUSER": "wrong", "PGPORT": "6543"})
        assert options["host"] == directory
        assert options["port"] == 5432
        assert options["database"] == "postgres"
        assert options["user"] == db.pwd.getpwuid(db.os.getuid()).pw_name
        assert options["password"] == ""
        Path(directory).chmod(0o755)
        with pytest.raises(ValueError, match="mode 0700"):
            db.connection_options({"RUNTIME_EVENTS_TEST_SOCKET": directory})


def test_symlink_socket_is_rejected():
    with tempfile.TemporaryDirectory(prefix="slomix-runtime-pg-", dir="/tmp") as directory:
        link = Path(directory + "-link")
        link.symlink_to(directory, target_is_directory=True)
        try:
            with pytest.raises(ValueError):
                db.connection_options({"RUNTIME_EVENTS_TEST_SOCKET": str(link)})
        finally:
            link.unlink()


def test_other_owner_socket_is_rejected(monkeypatch):
    with tempfile.TemporaryDirectory(prefix="slomix-runtime-pg-", dir="/tmp") as directory:
        monkeypatch.setattr(db.os, "getuid", lambda: -1)
        with pytest.raises(ValueError, match="owned by this user"):
            db.connection_options({"RUNTIME_EVENTS_TEST_SOCKET": directory})


@pytest.fixture
def admin(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(db, "connection_options", lambda: db_options())
    monkeypatch.setattr(db.asyncpg, "connect", AsyncMock(return_value=conn))
    return conn


def db_options():
    return dict(host="synthetic", port=5432, database="postgres", user="synthetic",
                password="", timeout=5, command_timeout=5, ssl=False)


async def test_rejected_target_never_connects(monkeypatch):
    def deny():
        raise ValueError("target denied")
    connect = AsyncMock()
    monkeypatch.setattr(db, "connection_options", deny)
    monkeypatch.setattr(db.asyncpg, "connect", connect)
    with pytest.raises(ValueError, match="target denied"):
        async with db.isolated_database():
            pytest.fail("yielded denied database")
    connect.assert_not_awaited()


async def test_each_fixture_creates_and_removes_only_its_generated_database(admin):
    names = []
    for _ in range(2):
        async with db.isolated_database() as config:
            names.append(config["database"])
            assert config["database"].startswith("slomix_fixture_")
            assert len(config["database"]) == len("slomix_fixture_") + 32
    assert names[0] != names[1]
    assert [call.args[0] for call in admin.execute.await_args_list] == [
        query for name in names for query in
        (f'CREATE DATABASE "{name}" TEMPLATE template0', f'DROP DATABASE "{name}"')]
    assert admin.close.await_count == 2


async def test_failed_create_never_drops_existing_database(admin):
    admin.execute.side_effect = RuntimeError("create denied or collision")
    with pytest.raises(RuntimeError, match="create denied"):
        async with db.isolated_database():
            pytest.fail("yielded unowned database")
    assert admin.execute.await_count == 1
    admin.close.assert_awaited_once_with(timeout=5)


async def test_body_failure_still_cleans_up_owned_database(admin):
    with pytest.raises(RuntimeError, match="schema failure"):
        async with db.isolated_database() as config:
            raise RuntimeError("schema failure")
    assert admin.execute.await_args.args == (f'DROP DATABASE "{config["database"]}"',)
    admin.close.assert_awaited_once_with(timeout=5)


async def test_cleanup_failure_is_not_hidden(admin):
    admin.execute.side_effect = [None, RuntimeError("cleanup failure")]
    with pytest.raises(RuntimeError, match="cleanup failure"):
        async with db.isolated_database():
            pass
    admin.close.assert_awaited_once_with(timeout=5)


async def test_real_shared_schema_setup_does_not_swallow_error():
    from tests.conftest import _ensure_test_schema

    adapter = AsyncMock()
    adapter.execute.side_effect = RuntimeError("synthetic schema failure")
    with pytest.raises(RuntimeError, match="synthetic schema failure"):
        await _ensure_test_schema(adapter)
    adapter.execute.assert_awaited_once()


async def test_real_adapter_fixture_closes_pool_on_setup_failure(monkeypatch):
    from tests import conftest

    adapter = AsyncMock()
    adapter.execute.side_effect = RuntimeError("synthetic schema failure")
    monkeypatch.setattr(conftest, "PostgreSQLAdapter", lambda **kwargs: adapter)
    config = dict(host="synthetic", port=5432, database="synthetic", user="synthetic",
                  password="", min_pool_size=2, max_pool_size=5)
    generator = conftest.db_adapter.__wrapped__(config)
    with pytest.raises(RuntimeError, match="synthetic schema failure"):
        await anext(generator)
    adapter.connect.assert_awaited_once()
    adapter.close.assert_awaited_once()
