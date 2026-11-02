"""Owned import pool plus separate readonly observation; no ambient setup."""

import asyncio
from contextlib import asynccontextmanager
from functools import partial
from types import SimpleNamespace

import asyncpg

from bot.core.database_adapter import PostgreSQLAdapter
from bot.runtime_import_session import open_import_session
from shared.runtime_import_pool import ImportDatabaseConfig, TcpImportDatabaseConfig, create_import_pool

_IDENTITY = '''SELECT current_database(),current_schema(),current_user,pg_is_in_recovery()'''


class _BorrowedAdapter(PostgreSQLAdapter):
    """Only the enclosing import session owns the pool; never discover/reconnect."""

    async def connect(self):
        raise RuntimeError('Timing adapter requires its enclosing owned import session')

    async def close(self):
        raise RuntimeError('Only the enclosing import session may close the pool')


@asynccontextmanager
async def timing_import_resources(database, *, close_timeout=5.0):
    """One serial writer slot shared by stats/timing and one separate observer.

    The observer is NOT borrowed from the single-slot pool. It defaults to
    readonly, and each library observer opens its own fresh readonly snapshot.
    Require matching primary/database/schema/role and distinct backend PIDs;
    this is session agreement, not physical host authentication or a writer fence.
    The legacy adapter cannot parse colon-bearing hosts, including IPv6; refuse
    them before pool creation rather than silently changing the supplied target.
    No schema setup, provider, background task, discovery or source acknowledgement.
    Errors/cancellation preserve earlier commits; both resources close boundedly.
    Do not retain manager/adapter/observer beyond the context or share concurrently.
    """
    if not isinstance(database, (ImportDatabaseConfig, TcpImportDatabaseConfig)):
        raise ValueError('Explicit import target required')
    options = database.pool_options()
    if ':' in options['host']:
        raise ValueError('Timing adapter requires a Unix socket, IPv4 literal or localhost')
    # open_import_session validates close_timeout before creating anything.
    async with open_import_session(
        SimpleNamespace(database_type='postgresql'), pool_factory=partial(create_import_pool, database),
        journal_enabled=True, defer_team_assignment=True, close_timeout=close_timeout,
    ) as manager:
        adapter = _BorrowedAdapter(options['host'], database.port, database.database,
                                   database.user, database.password)
        adapter.pool = manager.pool
        observer = None
        failure = None
        try:
            observer = await asyncpg.connect(
                host=options['host'], port=database.port, database=database.database,
                user=database.user, password=database.password, ssl=False, timeout=5,
                command_timeout=10, target_session_attrs='primary',
                server_settings={'search_path': 'public', 'statement_timeout': '10000',
                                 'application_name': 'slomix-runtime-timing-observer',
                                 'default_transaction_read_only': 'on'},
            )
            observed = tuple(await observer.fetchrow(_IDENTITY))
            async with manager.pool.acquire() as writer:
                actual = tuple(await writer.fetchrow(_IDENTITY))
                if (actual != observed or actual != (database.database, 'public', database.user, False)
                        or writer.get_server_pid() == observer.get_server_pid()
                        or writer.is_in_transaction() or observer.is_in_transaction()
                        or await writer.fetchval('SHOW transaction_read_only') != 'off'
                        or await observer.fetchval('SHOW transaction_read_only') != 'on'):
                    raise RuntimeError('Writer and independent readonly observer do not agree')
            yield manager, adapter, observer
        except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as error:
            failure = error
            raise
        finally:
            adapter.pool = None
            if observer is not None:
                try:
                    await asyncio.wait_for(observer.close(timeout=close_timeout), close_timeout)
                except (Exception, asyncio.CancelledError, KeyboardInterrupt, SystemExit) as close_error:
                    observer.terminate()
                    if failure is not None:
                        raise failure from close_error
                    raise
