"""Refresh helper for the weapon_stats_mv materialized view.

Audit plan ref: A8.

The materialized view is created by ``migrations/053_add_weapon_stats_mv.sql``
and accelerates the ``/api/stats/weapons`` leaderboard endpoint. Refresh runs
out-of-band (periodic task, pg_cron, or manual) — never via a trigger.

This helper is intentionally permissive: if the migration has not been applied
yet, ``refresh_weapon_stats_mv`` becomes a no-op so the website can ship the
code path before the DBA applies the migration.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from typing import Any

from website.backend.env_utils import getenv_int
from website.backend.logging_config import get_app_logger

logger = get_app_logger("services.weapon_stats_mv")

_REFRESH_SQL_CONCURRENT = "REFRESH MATERIALIZED VIEW CONCURRENTLY weapon_stats_mv"
_REFRESH_SQL_BLOCKING = "REFRESH MATERIALIZED VIEW weapon_stats_mv"


def _looks_like_missing_relation(exc: Exception) -> bool:
    """Heuristic for asyncpg/psycopg2 ``UndefinedTableError`` without importing it."""
    msg = str(exc).lower()
    return (
        "weapon_stats_mv" in msg
        and ("does not exist" in msg or "undefinedtable" in msg)
    )


def _looks_like_needs_initial_populate(exc: Exception) -> bool:
    """REFRESH CONCURRENTLY fails until the MV has been populated once.

    PostgreSQL's actual error message is ``"... is not populated"`` (see
    src/backend/commands/matview.c). Earlier code matched the looser
    phrase ``"has not been populated"`` which never appears in the real
    message — the detector therefore never triggered the blocking
    fallback and the refresh loop kept failing indefinitely.
    """
    msg = str(exc).lower()
    return "is not populated" in msg or "has not been populated" in msg


async def refresh_weapon_stats_mv(db: Any) -> bool:
    """Refresh the ``weapon_stats_mv`` materialized view.

    Returns ``True`` if refresh ran (or initial populate ran), ``False`` if the
    MV does not exist yet (migration not applied) or refresh failed in a
    non-fatal way. Never raises — refresh is best-effort.
    """
    if db is None:
        logger.debug("weapon_stats_mv refresh skipped: db is None")
        return False

    execute = getattr(db, "execute", None)
    if execute is None:
        logger.debug("weapon_stats_mv refresh skipped: db has no execute()")
        return False

    try:
        await execute(_REFRESH_SQL_CONCURRENT)
        logger.debug("weapon_stats_mv refreshed concurrently")
        return True
    except Exception as exc:  # pragma: no cover - exact exception type varies
        if _looks_like_missing_relation(exc):
            logger.info(
                "weapon_stats_mv not found — skipping refresh "
                "(apply migrations/053_add_weapon_stats_mv.sql to enable)"
            )
            return False
        if _looks_like_needs_initial_populate(exc):
            logger.info("weapon_stats_mv needs initial populate; running non-concurrent REFRESH")
            try:
                await execute(_REFRESH_SQL_BLOCKING)
                return True
            except Exception as inner_exc:
                logger.warning("weapon_stats_mv initial populate failed: %s", inner_exc)
                return False
        logger.warning("weapon_stats_mv refresh failed: %s", exc)
        return False


async def weapon_stats_mv_refresh_loop(
    db_factory: Any,
    interval_seconds: int | None = None,
) -> None:
    """Background loop that refreshes ``weapon_stats_mv`` on an interval.

    ``db_factory`` may be either a DatabaseAdapter (used directly) or a
    zero-argument callable that returns one. Disabled when interval <= 0.
    """
    if interval_seconds is None:
        interval_seconds = getenv_int("WEAPON_STATS_MV_REFRESH_SECONDS", 0)
    if interval_seconds <= 0:
        logger.debug("weapon_stats_mv refresh loop disabled (interval=%s)", interval_seconds)
        return

    logger.info("weapon_stats_mv refresh loop starting (interval=%ss)", interval_seconds)
    try:
        while True:
            db = db_factory() if callable(db_factory) else db_factory
            with contextlib.suppress(Exception):
                await refresh_weapon_stats_mv(db)
            await asyncio.sleep(interval_seconds)
    except asyncio.CancelledError:
        logger.info("weapon_stats_mv refresh loop cancelled")
        raise


def use_weapon_stats_mv_enabled() -> bool:
    """Feature flag: query the MV instead of the live table."""
    raw = os.getenv("USE_WEAPON_STATS_MV", "false")
    return raw.strip().lower() in {"1", "true", "yes", "on"}
