"""Log-sweep remediation: STATS_READY soft-fail must NOT pollute the error
log or trip the worker circuit breaker.

Background: when the Lua webhook beats the SSH poll, the stats file isn't on
disk yet. The worker still persists the authoritative Lua team/spawn capture,
then raises to clear the dedup key so a retry can re-enter. That raise is an
EXPECTED, transient outcome — but it used to be logged at ERROR and counted
toward `track_error(max_consecutive=3)`, so a normal backlog of late stats
files (364× observed in prod logs) flooded the error log and could falsely
trip the breaker.

Pin the contract:
- a soft-fail raises `StatsFetchSoftFail` (subclass of `WebhookHandlerSoftFail`
  so the queue clears dedup), is logged at WARNING, and does NOT call
  `track_error`.
- a genuine error still logs at ERROR and DOES call `track_error`.
- both still re-raise (the queue relies on the raise to clear dedup).
"""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.stats_ready_mixin import StatsFetchSoftFail, _StatsReadyMixin
from bot.services.webhook_event_queue import WebhookHandlerSoftFail


def _make_self(*, fetched: bool, store_raises: Exception | None = None):
    """Minimal mock bound to the real `_process_stats_ready_round`."""
    s = MagicMock()
    s._fetch_latest_stats_file = AsyncMock(return_value=fetched)
    s._store_lua_round_teams = AsyncMock(
        side_effect=store_raises
    ) if store_raises else AsyncMock()
    s._store_lua_spawn_stats = AsyncMock()
    s.track_error = AsyncMock()
    return s


def _metadata() -> dict:
    return {
        "round_end_unix": 1_700_000_000,
        "map_name": "sw_goldrush_te",
        "round_number": 2,
    }


def _message() -> MagicMock:
    msg = MagicMock()
    msg.delete = AsyncMock()
    return msg


@pytest.mark.asyncio
async def test_soft_fail_raises_typed_exception_no_track_error(caplog):
    """fetch miss → StatsFetchSoftFail, logged WARNING, track_error NOT called."""
    s = _make_self(fetched=False)

    with caplog.at_level(logging.WARNING, logger="bot.webhook"), pytest.raises(StatsFetchSoftFail):
        await _StatsReadyMixin._process_stats_ready_round(s, _metadata(), _message())

    # Lua capture still persisted before the soft-fail signal.
    s._store_lua_round_teams.assert_awaited_once()
    # The circuit breaker must NOT see an expected soft-fail.
    s.track_error.assert_not_awaited()
    # Logged at WARNING (not ERROR) on the webhook logger.
    soft = [r for r in caplog.records if "soft-fail" in r.message.lower()]
    assert soft, "expected a soft-fail log record"
    assert all(r.levelno == logging.WARNING for r in soft)


@pytest.mark.asyncio
async def test_soft_fail_is_a_webhook_soft_fail_so_queue_clears_dedup():
    """StatsFetchSoftFail must be a WebhookHandlerSoftFail subclass so the
    queue worker recognises it and clears the dedup key for a retry."""
    assert issubclass(StatsFetchSoftFail, WebhookHandlerSoftFail)


@pytest.mark.asyncio
async def test_genuine_error_logs_error_and_calls_track_error(caplog):
    """A real failure (DB write blows up) stays ERROR + trips track_error."""
    s = _make_self(fetched=True, store_raises=ValueError("db exploded"))

    with caplog.at_level(logging.ERROR, logger="bot.webhook"), pytest.raises(ValueError):
        await _StatsReadyMixin._process_stats_ready_round(s, _metadata(), _message())

    s.track_error.assert_awaited_once()
    errs = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errs, "expected an ERROR log record for a genuine failure"
