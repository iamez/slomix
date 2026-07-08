"""Session-end KIS cache-invalidation hook (voice_session_service).

compute_session_kis() (website) caches storytelling_kill_impact permanently
on first read for a session_date and is never force-refreshed anywhere in
the codebase — a Story/Smart Stats page viewed mid-session freezes every
player's kill count at that partial snapshot. The bot must delete the
stale rows at session finalize so the next read recomputes fresh, and this
must NEVER break finalization (DB hiccup, missing table, etc.).
"""
from __future__ import annotations

import datetime as dt

import pytest

from bot.services.voice_session_service import VoiceSessionService


def _svc():
    return VoiceSessionService.__new__(VoiceSessionService)


class _FakeAdapter:
    def __init__(self, raise_exc=None):
        self._raise = raise_exc
        self.calls = []

    async def execute(self, query, params=()):
        self.calls.append((query, params))
        if self._raise:
            raise self._raise


@pytest.mark.asyncio
async def test_invalidate_deletes_by_session_date_as_a_date_object():
    svc = _svc()
    adapter = _FakeAdapter()
    svc.db_adapter = adapter

    await svc._invalidate_kis_cache("2026-07-07")  # noqa: SLF001

    assert len(adapter.calls) == 1
    query, params = adapter.calls[0]
    assert "DELETE FROM storytelling_kill_impact" in query
    assert "session_date" in query
    # storytelling_kill_impact.session_date is a DATE column — passing a
    # bare string here is the exact bug class PR #455 hit on
    # player_skill_history (codex, s_effort_service.py precedent).
    assert params == (dt.date(2026, 7, 7),)


@pytest.mark.asyncio
async def test_invalidate_never_raises_on_db_failure():
    svc = _svc()
    svc.db_adapter = _FakeAdapter(raise_exc=RuntimeError("db down"))

    await svc._invalidate_kis_cache("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


@pytest.mark.asyncio
async def test_invalidate_truncates_full_timestamp_to_date():
    svc = _svc()
    adapter = _FakeAdapter()
    svc.db_adapter = adapter

    await svc._invalidate_kis_cache("2026-07-07 23:59:00")  # noqa: SLF001

    _, params = adapter.calls[0]
    assert params == (dt.date(2026, 7, 7),)
