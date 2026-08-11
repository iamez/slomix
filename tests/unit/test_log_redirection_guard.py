"""The test suite must never write into the repository's real ``logs/``.

Regression guard for PR #592 (FIX 6 in the 2026-08-11 audit). Before
``tests/conftest.py`` exported ``BOT_LOG_DIR``/``WEB_LOG_DIR``, any test that
touched logging wrote deliberate fixtures into the production logs: 1,100
fake ``SSHMonitor`` ERROR lines ("Missing SSH configuration" from
``test_ssh_monitor_helpers.py`` alone) and ~2,415 fixture lines ("simulated
SQL failure", "db down", ``fake_stats.txt``) accumulated in ``logs/bot.log``
and ``logs/errors.log``. That drowned real errors and broke every log-based
measurement — ``scripts/health_check.sh`` failed on errors that never
happened, and two audit findings (FIX 5 and FIX 6) were re-reported against
noise that was already fixed.

The redirect only works because conftest sets the env vars BEFORE any bot or
website module is imported: both logging configs resolve their directory at
import time. These tests pin the whole chain — if someone removes the
``os.environ.setdefault`` lines from conftest, reorders the imports above
them, or renames the env vars in either logging config, this fails instead
of the pollution silently returning.
"""
from __future__ import annotations

import os
from pathlib import Path

import bot.logging_config as bot_logging_config
import website.backend.logging_config as web_logging_config

REPO_LOGS_DIR = (
    Path(bot_logging_config.__file__).resolve().parent.parent / "logs"
).resolve()


def test_conftest_exports_log_redirect_env_vars():
    assert os.environ.get("BOT_LOG_DIR"), (
        "tests/conftest.py must set BOT_LOG_DIR before bot modules are "
        "imported, or the suite writes into the repository's real logs/."
    )
    assert os.environ.get("WEB_LOG_DIR"), (
        "tests/conftest.py must set WEB_LOG_DIR before website modules are "
        "imported, or the suite writes into the repository's real logs/."
    )


def test_bot_log_dir_is_redirected_out_of_repo():
    assert bot_logging_config.LOGS_DIR.resolve() != REPO_LOGS_DIR, (
        "bot.logging_config.LOGS_DIR points at the repository's real logs/ "
        "during a test run — the BOT_LOG_DIR redirect from tests/conftest.py "
        "(PR #592) is broken, so test fixtures will pollute production logs."
    )


def test_web_log_dir_is_redirected_out_of_repo():
    assert web_logging_config.LOG_DIR != REPO_LOGS_DIR, (
        "website.backend.logging_config.LOG_DIR points at the repository's "
        "real logs/ during a test run — the WEB_LOG_DIR redirect from "
        "tests/conftest.py (PR #592) is broken, so test fixtures will "
        "pollute production logs."
    )
