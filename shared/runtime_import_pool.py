"""Explicit Unix or separately approved private TCP pools; no service activation."""

import ipaddress
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

import asyncpg


def _validate_connection(database, user, password, port, application_name):
    for value in (database, user):
        if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', value):
            raise ValueError('Explicit simple database and role identifiers required')
    if not isinstance(password, str):
        raise ValueError('Explicit password string required; empty permits peer authentication')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid PostgreSQL port')
    if (not isinstance(application_name, str)
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,63}', application_name)):
        raise ValueError('Invalid pool application name')


def _pool_options(host, config):
    return dict(
        host=host, port=config.port, database=config.database, user=config.user,
        password=config.password, ssl=False, target_session_attrs='read-write',
        min_size=0, max_size=1, timeout=5, command_timeout=10,
        server_settings={'search_path': 'public', 'statement_timeout': '10000',
                         'application_name': config.application_name},
    )


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
        _validate_connection(self.database, self.user, self.password, self.port, self.application_name)

    def pool_options(self):
        """One lazy connection, fixed budgets and search path; no schema changes.

        Pool acquisition still belongs to the serial caller: command/connection
        timeouts are not a queue-wait or entire-import deadline.
        """
        return _pool_options(self.socket, self)


@dataclass(frozen=True)
class TcpImportDatabaseConfig:
    """Explicit private-network TCP target; neither a DEV attestation nor TLS.

    Only localhost or a private/loopback literal IP is accepted. There is no DNS
    host list, DSN, password file or environment discovery. Caller authentication
    and exclusive legacy-writer handover remain independent prerequisites.
    """

    host: str
    database: str
    user: str
    password: str = field(repr=False)
    port: int = 5432
    application_name: str = 'slomix-runtime-import-dev'

    def __post_init__(self):
        _validate_connection(self.database, self.user, self.password, self.port, self.application_name)
        if not self.password:
            raise ValueError('Explicit TCP password required')
        if self.host != 'localhost':
            try:
                address = ipaddress.ip_address(self.host)
            except (TypeError, ValueError):
                raise ValueError('Explicit private or loopback IP, or localhost required') from None
            if (not isinstance(self.host, str) or '%' in self.host or not address.is_private
                    or address.is_unspecified or address.is_multicast or address.is_link_local):
                raise ValueError('Explicit private or loopback IP, or localhost required')

    def pool_options(self):
        return _pool_options(self.host, self)


async def create_import_pool(config: ImportDatabaseConfig | TcpImportDatabaseConfig):
    """Return an owned, initially empty pool; construction is NOT a health check."""
    return await asyncpg.create_pool(**config.pool_options())
