"""A library that prints its own traceback must not drown the log.

⛔⛔ THE MEASUREMENT THIS PINS. On 2026-09-06 the owner ran
`journalctl -u etlegacy-bot | grep -iE "warn|error"` and saw 48 ERROR lines.
Two were events; the other 46 were `paramiko.transport` printing two
tracebacks, one ERROR record per line. A 24x inflation — and it buried the
SLOW QUERY and KIS-RECONCILE lines that actually needed a human.

⛔ The filter is attached to HANDLERS, never to the logger. Raising the level
on `paramiko.transport` would stop the record being created at all, and the
full traceback is the only thing that can diagnose `[Errno 9] Bad file
descriptor` — a socket closed under paramiko's own thread, which is read from
frames, not from a summary. bot.log therefore keeps everything; only the two
surfaces a human greps are spared the duplicate.
"""
from __future__ import annotations

import logging

import pytest

from bot.logging_config import NOISY_TRACEBACK_LOGGERS, SuppressNoisyTracebacks


def _record(name: str, level: int = logging.ERROR) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, "msg", None, None)


@pytest.mark.parametrize("name", [
    "paramiko.transport",
    # ⛔ Measured on 2026-09-06: .sftp is a SEPARATE logger and the larger half
    # by volume (1935 lines that day against 3216). A filter naming only
    # "paramiko.transport" as an exact match would have left most of the noise.
    "paramiko.transport.sftp",
])
def test_the_noisy_library_is_dropped(name):
    assert SuppressNoisyTracebacks().filter(_record(name)) is False


@pytest.mark.parametrize("name", [
    "bot.automation.ssh",       # our own one-line summary — the whole point
    "bot.cogs.proximity",
    "bot.core",
    "discord.gateway",
])
def test_everything_else_still_passes(name):
    assert SuppressNoisyTracebacks().filter(_record(name)) is True


def test_our_own_ssh_summary_survives_the_same_incident():
    """⛔ The filter must not silence the line that replaces the traceback.

    `_describe_ssh_failure` (#923) logs the unwrapped cause in one line under
    `bot.automation.ssh`. If that were filtered too, the incident would vanish
    from errors.log entirely — trading noise for blindness.
    """
    f = SuppressNoisyTracebacks()
    assert f.filter(_record("paramiko.transport")) is False
    assert f.filter(_record("bot.automation.ssh")) is True


def test_the_default_prefixes_are_the_module_constant():
    assert SuppressNoisyTracebacks().prefixes == tuple(NOISY_TRACEBACK_LOGGERS)


# ---------------------------------------------------------------------------
# Runtime: the filter is actually attached, and to the right handlers
# ---------------------------------------------------------------------------

def test_the_filter_reaches_console_and_errors_but_not_bot_log(tmp_path, monkeypatch):
    """⛔ Wiring proof. The class working in isolation says nothing about
    whether setup_logging attaches it — and attaching it to bot.log would
    destroy the forensics this design deliberately keeps."""
    import bot.logging_config as lc

    monkeypatch.setattr(lc, "LOGS_DIR", tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        lc.setup_logging()
        by_file = {}
        console = None
        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not hasattr(h, "baseFilename"):
                console = h
            elif hasattr(h, "baseFilename"):
                by_file[h.baseFilename.rsplit("/", 1)[-1]] = h

        def has_filter(handler):
            return any(isinstance(f, lc.SuppressNoisyTracebacks) for f in handler.filters)

        assert console is not None, "no console handler found"
        assert has_filter(console), "console (what journalctl shows) is unfiltered"
        assert has_filter(by_file["errors.log"]), "errors.log is unfiltered"
        assert not has_filter(by_file["bot.log"]), (
            "bot.log must keep the full traceback — it is the only forensic copy"
        )
    finally:
        for h in root.handlers:
            h.close()
        root.handlers[:] = saved


def test_a_paramiko_traceback_lands_only_in_bot_log(tmp_path, monkeypatch):
    """End to end: emit the record, then read the files."""
    import bot.logging_config as lc

    monkeypatch.setattr(lc, "LOGS_DIR", tmp_path)
    root = logging.getLogger()
    saved = list(root.handlers)
    try:
        lc.setup_logging()
        logging.getLogger("paramiko.transport").error("Error reading SSH protocol banner")
        logging.getLogger("bot.automation.ssh").error("SSH list files failed: [remote slow]")
        for h in root.handlers:
            h.flush()

        bot_log = (tmp_path / "bot.log").read_text()
        errors_log = (tmp_path / "errors.log").read_text()

        assert "Error reading SSH protocol banner" in bot_log, "forensics lost"
        assert "Error reading SSH protocol banner" not in errors_log, "noise not filtered"
        assert "SSH list files failed" in errors_log, "our own summary must survive"
    finally:
        for h in root.handlers:
            h.close()
        root.handlers[:] = saved
