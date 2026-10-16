"""Shared-fixture isolation; never infer permission from an application's .env."""

import os
import pwd
import stat
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg


def connection_options(environ=None):
    """Allow only the explicit private proof socket or opted-in CI service."""
    env = os.environ if environ is None else environ
    socket = env.get("RUNTIME_EVENTS_TEST_SOCKET")
    if socket:
        path = Path(socket)
        if (not path.is_absolute() or path.parent != Path("/tmp")
                or not path.name.startswith("slomix-runtime-pg-")
                or path.is_symlink()):
            raise ValueError("Refusing non-private test socket path")
        info = path.stat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o700):
            raise ValueError("Test socket directory must be owned by this user with mode 0700")
        return dict(host=str(path), port=5432, database="postgres",
                    user=pwd.getpwuid(os.getuid()).pw_name, password="",
                    timeout=5, command_timeout=5, ssl=False)
    if (env.get("RUNTIME_EVENTS_TEST_CI") == "true"
            and env.get("GITHUB_ACTIONS") == "true"
            and env.get("POSTGRES_TEST_HOST") == "127.0.0.1"
            and env.get("POSTGRES_TEST_PORT") == "5432"
            and env.get("POSTGRES_TEST_DATABASE") == "etlegacy_test"
            and env.get("POSTGRES_TEST_USER") == "etlegacy_user"
            and env.get("POSTGRES_TEST_PASSWORD")):
        return dict(host="127.0.0.1", port=5432, database="etlegacy_test",
                    user="etlegacy_user", password=env["POSTGRES_TEST_PASSWORD"],
                    timeout=5, command_timeout=5, ssl=False)
    raise ValueError("Shared DB fixtures require a private proof socket or explicit CI isolation")


@asynccontextmanager
async def isolated_database():
    """Yield a new per-test database; only remove a database we created here.

    No transaction wrapper: tests must observe real commits, rollback and pools.
    A failed CREATE never authorizes DROP; ambiguous outcomes remain for review.
    Teardown failures propagate and do not terminate other clients forcibly.
    """
    options = connection_options()
    name = "slomix_fixture_" + uuid.uuid4().hex
    admin = await asyncpg.connect(**options)
    created = False
    try:
        await admin.execute(f'CREATE DATABASE "{name}" TEMPLATE template0')
        created = True
        yield dict(db_type="postgresql", host=options["host"], port=options["port"],
                   database=name, user=options["user"], password=options["password"],
                   min_pool_size=2, max_pool_size=5)
    finally:
        try:
            if created:
                await admin.execute(f'DROP DATABASE "{name}"')
        finally:
            await admin.close(timeout=5)
