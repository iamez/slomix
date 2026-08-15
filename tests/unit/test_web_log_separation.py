"""Each web log file must contain its own stream.

Until 2026-08-15 every handler hung off the root logger with no name filter,
so web.log, security.log and access.log were byte-identical — three copies of
the same records. The cost was not disk: `security.log` did not mean security
and `access.log` did not mean access, so hunting one event meant reading the
same soup three times.

These tests pin the routing AND the two things that must NOT change with it:
errors.log and debug.log stay catch-alls (errors.log is shared with the bot
process, debug.log is the firehose), so an access-layer failure is still
visible in both.
"""
from __future__ import annotations

import logging

import pytest

from website.backend.logging_config import (
    DEDICATED_STREAMS,
    ExcludeDedicatedStreamsFilter,
    OnlyStreamFilter,
)


def _record(name: str, level: int = logging.INFO) -> logging.LogRecord:
    return logging.LogRecord(name, level, __file__, 1, "msg", None, None)


@pytest.mark.parametrize("stream", DEDICATED_STREAMS)
def test_only_filter_keeps_its_own_stream(stream):
    f = OnlyStreamFilter(stream)

    assert f.filter(_record(stream)) is True
    # Child loggers belong to their parent stream: `access.middleware` is access.
    assert f.filter(_record(f"{stream}.middleware")) is True
    assert f.filter(_record("api.storytelling")) is False
    assert f.filter(_record("backend.main")) is False


def test_only_filter_does_not_match_a_prefix_lookalike():
    """`accessibility` is not `access` — split on the dot, never startswith."""
    f = OnlyStreamFilter("access")

    assert f.filter(_record("accessibility")) is False
    assert f.filter(_record("access")) is True


def test_web_log_excludes_streams_that_own_a_file():
    f = ExcludeDedicatedStreamsFilter()

    assert f.filter(_record("api.storytelling")) is True
    assert f.filter(_record("backend.main")) is True
    for stream in DEDICATED_STREAMS:
        assert f.filter(_record(stream)) is False
        assert f.filter(_record(f"{stream}.sub")) is False


def test_error_and_debug_handlers_carry_no_stream_filter(tmp_path, monkeypatch):
    """errors.log is shared with the bot and debug.log is the firehose — an
    access-layer error must still land in both, or the separation would hide
    exactly the records someone is hunting."""
    monkeypatch.setenv("WEB_LOG_DIR", str(tmp_path))
    import importlib

    import website.backend.logging_config as lc

    importlib.reload(lc)
    lc.setup_logging()

    logging.getLogger("access").error("request blew up")
    logging.getLogger("security").info("auth ok")
    logging.getLogger("api.storytelling").info("panel computed")
    for handler in logging.getLogger().handlers:
        handler.flush()

    def streams(filename: str) -> set[str]:
        path = tmp_path / filename
        if not path.exists():
            return set()
        return {
            line.split("|")[2].strip()
            for line in path.read_text().splitlines()
            if line.count("|") >= 3
        }

    assert streams("access.log") == {"access"}
    assert streams("security.log") == {"security"}
    assert "access" not in streams("web.log")
    assert "security" not in streams("web.log")
    assert "api.storytelling" in streams("web.log")
    # Catch-alls keep everything.
    assert "access" in streams("errors.log")
    assert {"access", "security", "api.storytelling"} <= streams("debug.log")
