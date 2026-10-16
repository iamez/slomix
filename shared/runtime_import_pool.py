"""Explicit Unix-socket development pool; no dotenv or service activation."""

import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import asyncpg


@dataclass(frozen=True)
class ImportDatabaseConfig:
    """Caller-approved target, not proof that a database is non-production.

    This initial adapter deliberately supports Unix sockets only. No DSN,
    inferred user/database/password or TCP fallback. Password is excluded from
    repr, but callers must still never log connection options or raw exceptions.
    """

    socket: str
    database: str
    user: str
    password: str = field(repr=False)
    port: int = 5432
    application_name: str = 'slomix-runtime-import-dev'

    def __post_init__(self):
        if (not isinstance(self.socket, str) or not self.socket.startswith('/')
                or '\x00' in self.socket or '..' in PurePosixPath(self.socket).parts):
            raise ValueError('Explicit absolute Unix socket directory required')
        for value in (self.database, self.user):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', value):
                raise ValueError('Explicit simple database and role identifiers required')
        if not isinstance(self.password, str):
            raise ValueError('Explicit password string required; empty permits peer authentication')
        if type(self.port) is not int or not 1 <= self.port <= 65535:
            raise ValueError('Invalid PostgreSQL port')
        if (not isinstance(self.application_name, str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', self.application_name)):
            raise ValueError('Invalid pool application name')

    def pool_options(self):
        """One lazy connection, fixed budgets and search path; no schema changes.

        Pool acquisition still belongs to the serial caller: command/connection
        timeouts are not a queue-wait or entire-import deadline.
        """
        return dict(
            host=self.socket, port=self.port, database=self.database, user=self.user,
            password=self.password, ssl=False, target_session_attrs='read-write',
            min_size=0, max_size=1, timeout=5, command_timeout=10,
            server_settings={'search_path': 'public', 'statement_timeout': '10000',
                             'application_name': self.application_name},
        )


async def create_import_pool(config: ImportDatabaseConfig):
    """Return an owned, initially empty pool; construction is NOT a health check."""
    return await asyncpg.create_pool(**config.pool_options())
