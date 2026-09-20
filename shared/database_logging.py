"""Database event logging without process-wide logging setup or bot imports."""

import logging


def _exc_info_for(error):
    """Return a value safe to pass as ``exc_info=`` to logger.error.

    Callers sometimes pass an exception instance, sometimes a pre-formatted
    error string (e.g. ``str(e)`` or a parser error message). ``logger.error``
    only treats a BaseException as a traceback source — strings fall through
    to ``sys.exc_info()``, which is ``(None, None, None)`` outside an active
    ``except``, silently dropping the traceback.
    """
    return error if isinstance(error, BaseException) else False


def log_database_operation(operation, details, duration=None, error=None):
    """
    Log database operations

    Args:
        operation: Type of operation (SELECT, INSERT, UPDATE, etc.)
        details: Description of the operation
        duration: How long it took in seconds (optional)
        error: Exception if operation failed (optional)
    """
    logger = logging.getLogger('bot.database')

    duration_str = f" [{duration:.3f}s]" if duration else ""

    if error:
        logger.error(f"❌ DB {operation} FAILED{duration_str}: {details} | Error: {error}", exc_info=_exc_info_for(error))
    else:
        logger.debug(f"✓ DB {operation}{duration_str}: {details}")


def log_stats_import(filename, round_count=0, player_count=0, weapon_count=0, duration=None, error=None):
    """
    Log stats file import

    Args:
        filename: Name of the stats file
        round_count: Number of rounds imported
        player_count: Number of player stats imported
        weapon_count: Number of weapon stats imported
        duration: How long import took (optional)
        error: Exception if import failed (optional)
    """
    logger = logging.getLogger('bot.database')

    duration_str = f" [{duration:.2f}s]" if duration else ""

    if error:
        logger.error(f"❌ IMPORT FAILED{duration_str}: {filename} | Error: {error}", exc_info=_exc_info_for(error))
    else:
        logger.info(
            f"✓ IMPORTED{duration_str}: {filename} | "
            f"Rounds: {round_count}, Players: {player_count}, Weapons: {weapon_count}"
        )


def log_performance_warning(operation, duration, threshold=1.0):
    """
    Log slow operations that exceed threshold

    Args:
        operation: Description of the operation
        duration: How long it took in seconds
        threshold: Threshold in seconds (default 1.0)
    """
    if duration > threshold:
        logger = logging.getLogger('bot.performance')
        logger.warning(f"⚠️ SLOW OPERATION [{duration:.2f}s]: {operation}")
