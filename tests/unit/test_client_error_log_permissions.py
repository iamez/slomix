"""Regression test: client_errors.log stays 0600 across rollover (Codex P2 on #578).

Unlike the other five log files (which need 0660 for cross-process bot/web
group access, see website/backend/logging_config.py's main setup loop),
client_errors.log is written solely by the web process, so 0600 is the
correct permission — but a chmod applied once at setup time doesn't survive
RotatingFileHandler.doRollover() opening a fresh file under the process
umask, same class of bug the #568 fix addressed for the group-writable case.
"""

import logging
import stat
from pathlib import Path

from website.backend import logging_config


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_client_errors_log_permission_survives_rollover(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    saved_level = root_logger.level
    try:
        logging_config.setup_logging(console_output=False)

        # Nested under client/ so the VM's `logs/*.log` logrotate glob (which
        # doesn't recurse) can't recreate it 0640/bot-owned — see LOG_FILES
        # in logging_config.py.
        client_error_log = tmp_path / "client" / "client_errors.log"
        assert _mode(client_error_log) == 0o600

        client_error_logger = logging.getLogger("client_error")
        handler = next(
            h for h in client_error_logger.handlers
            if isinstance(h, logging_config.OwnerOnlyRotatingFileHandler)
        )
        handler.doRollover()

        assert client_error_log.exists(), "doRollover() should recreate the active file"
        assert _mode(client_error_log) == 0o600, "permission must survive rollover"
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(saved_handlers)
        root_logger.setLevel(saved_level)
        logging.getLogger("client_error").handlers.clear()
        logging.getLogger("client_error").propagate = True
