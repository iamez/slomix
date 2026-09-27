"""Compatibility startup for callers that do not supply importer configuration."""

import threading

_logging_lock = threading.Lock()
_logging_initialized = False


def load_legacy_config():
    """Load dotenv before selecting log paths; configure legacy logging once.

    Explicit-config callers never enter this compatibility path. Initialization
    failures propagate and leave logging eligible for retry. No database or
    Discord validation is performed here.
    """
    from bot.config import load_config

    global _logging_initialized
    with _logging_lock:
        if not _logging_initialized:
            import logging

            from bot.logging_config import setup_logging

            setup_logging(logging.INFO)
            _logging_initialized = True
    return load_config()
