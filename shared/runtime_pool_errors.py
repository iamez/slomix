"""Recognize the pinned asyncpg closed-connection release race only."""

import asyncpg


def closed_pool_release(error, connection):
    """A disconnect can release a holder before its shielded release runs.

    asyncpg0.31 then reports a free holder even though disconnect cleanup has
    already detached the borrowed proxy. Other internal errors, non-pool
    resources and usable connections must remain fatal.
    """
    if (not isinstance(error, asyncpg.InternalClientError)
            or str(error) != 'PoolConnectionHolder.release() called on a free connection holder'
            or type(connection) is not asyncpg.pool.PoolConnectionProxy):
        return False
    try:
        return connection.is_closed()
    except asyncpg.InterfaceError:
        # The native proxy refuses methods after disconnect has detached it.
        return True
