"""Recognized transient import failures; bounded scheduling owns retry policy."""

import asyncpg

TRANSIENT_PROXIMITY_ERRORS = (
    OSError, TimeoutError, asyncpg.PostgresConnectionError, asyncpg.QueryCanceledError,
    asyncpg.CannotConnectNowError, asyncpg.SerializationError, asyncpg.DeadlockDetectedError,
    asyncpg.TooManyConnectionsError,
)
