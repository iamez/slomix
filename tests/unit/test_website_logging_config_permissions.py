"""Regression test for the 2026-07-13/2026-07-22 errors.log permission incidents.

The bot and web services run as different OS users sharing one group
(BOT_USER/WEB_USER/SLX_GROUP in slomix_vm_setup.sh). setup_logging() must
leave the log directory and log files group-writable (0770 / 0660), not
owner-only (0700) or group-read-only (0640) — either of those locks the
non-owning service out the next time it needs to create or rotate a file.
"""

import logging
import stat

from website.backend import logging_config


def _mode(path):
    return stat.S_IMODE(path.stat().st_mode)


def test_setup_logging_leaves_dir_and_files_group_writable(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)

    root_logger = logging.getLogger()
    saved_handlers = list(root_logger.handlers)
    try:
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
    finally:
        root_logger.handlers.clear()
        root_logger.handlers.extend(saved_handlers)
