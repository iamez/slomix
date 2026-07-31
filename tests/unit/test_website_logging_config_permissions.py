"""Regression test for the 2026-07-13/2026-07-22 errors.log permission incidents.

The bot and web services run as different OS users sharing one group
(BOT_USER/WEB_USER/SLX_GROUP in slomix_vm_setup.sh). setup_logging() must
leave the log directory and log files group-writable (0770 / 0660), not
owner-only (0700) or group-read-only (0640) — either of those locks the
non-owning service out the next time it needs to create or rotate a file.
"""

import logging
import stat
from pathlib import Path

from website.backend import logging_config

# Named loggers setup_logging() adjusts the level of, beyond the root
# logger — must be restored too so this test can't leak state into others
# that run in the same pytest process (Copilot review on #568).
_ADJUSTED_LOGGER_NAMES = (
    "uvicorn.access", "uvicorn.error", "httpx", "httpcore", "asyncpg", "multipart",
)


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def _run_isolated(fn):
    """Run fn() under setup_logging()'s global state, then restore all of it."""
    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_root_level = root_logger.level
    saved_levels = {name: logging.getLogger(name).level for name in _ADJUSTED_LOGGER_NAMES}
    try:
        fn()
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(saved_handlers)
        root_logger.setLevel(saved_root_level)
        for name, level in saved_levels.items():
            logging.getLogger(name).setLevel(level)


def test_setup_logging_leaves_dir_and_files_group_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    def check():
        logging_config.setup_logging(console_output=False)

        assert _mode(tmp_path) == 0o770, (
            "log dir must be owner+group rwx (0770) so the other service "
            "user can traverse/create files in it"
        )

        for config in logging_config.LOG_FILES.values():
            log_file = tmp_path / config["filename"]
            assert log_file.exists()
            assert _mode(log_file) == 0o660, (
                f"{config['filename']} must be owner+group rw (0660), "
                "not group-read-only (0640)"
            )

    _run_isolated(check)


def test_rollover_reapplies_group_writable_permission(tmp_path, monkeypatch):
    """Codex review on #568: the one-time startup chmod doesn't survive a
    rollover — RotatingFileHandler.doRollover() opens a brand new file using
    the process umask, silently reintroducing the exact incident this PR
    fixes the moment a log first rotates, not just on service restart.
    """
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    def check():
        logging_config.setup_logging(console_output=False)

        access_config = logging_config.LOG_FILES["access"]
        access_log = tmp_path / access_config["filename"]
        handler = next(
            h for h in logging.getLogger().handlers
            if isinstance(h, logging_config.GroupWritableRotatingFileHandler)
            and Path(h.baseFilename) == access_log
        )

        handler.doRollover()

        assert access_log.exists(), "doRollover() should recreate the active file"
        assert _mode(access_log) == 0o660, (
            "permission must survive rollover, not just the initial startup chmod"
        )

    _run_isolated(check)
