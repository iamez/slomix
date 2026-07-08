"""Session-end KIS cache-invalidation hook (voice_session_service).

compute_session_kis() (website) caches storytelling_kill_impact permanently
on first read for a session_date and is never force-refreshed anywhere in
the codebase — a Story/Smart Stats page viewed mid-session freezes every
player's kill count at that partial snapshot. The bot must delete the
stale rows at session finalize so the next read recomputes fresh, and this
must NEVER break finalization (DB hiccup, missing table, etc.).

Covers codex review findings (PR #482):
  1. invalidate EVERY distinct session_date the session's rounds touch
     (midnight-crossing sessions), not just the start date
  2. (a delayed re-delete was tried to guard against an in-flight compute
     finishing late, then reverted — see _invalidate_kis_cache's docstring
     and the section below: it collided with SESSION_DIGEST_ENABLED's
     legitimate post-session-end recompute)
  3. (gating-on-scoring-success is covered by the finalize-hook test in
     test_s_effort_session_hook.py — this file only tests the invalidation
     methods directly)
"""
from __future__ import annotations

import datetime as dt
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# _delete_kis_rows — the atomic single-delete building block
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_deletes_by_session_date_as_a_date_object():
    svc = _svc()
    adapter = _FakeAdapter()
    svc.db_adapter = adapter

    await svc._delete_kis_rows("2026-07-07")  # noqa: SLF001

    assert len(adapter.calls) == 1
    query, params = adapter.calls[0]
    assert "DELETE FROM storytelling_kill_impact" in query
    assert "session_date" in query
    # storytelling_kill_impact.session_date is a DATE column — passing a
    # bare string here is the exact bug class PR #455 hit on
    # player_skill_history (codex, s_effort_service.py precedent).
    assert params == (dt.date(2026, 7, 7),)


@pytest.mark.asyncio
async def test_delete_never_raises_on_db_failure():
    svc = _svc()
    svc.db_adapter = _FakeAdapter(raise_exc=RuntimeError("db down"))

    await svc._delete_kis_rows("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


@pytest.mark.asyncio
async def test_delete_truncates_full_timestamp_to_date():
    svc = _svc()
    adapter = _FakeAdapter()
    svc.db_adapter = adapter

    await svc._delete_kis_rows("2026-07-07 23:59:00")  # noqa: SLF001

    _, params = adapter.calls[0]
    assert params == (dt.date(2026, 7, 7),)


# ---------------------------------------------------------------------------
# _invalidate_kis_cache — single delete, then warm
#
# An earlier version of this hook also re-ran the delete after a delay to
# catch an in-flight compute finishing late — but that unconditional
# second delete collided with SESSION_DIGEST_ENABLED (live on prod), which
# makes the morning-digest hook legitimately recompute fresh KIS rows
# shortly after every session end; the delayed delete wiped those out too
# (codex, PR #482, "Avoid deleting fresh KIS recomputes"). Reverted to a
# single delete, now followed by a proactive warm call so surfaces that
# read storytelling_kill_impact directly (no digest dependency) aren't
# left with zero KIS data (codex, "Warm direct KIS readers after deleting
# the cache") — see the method docstring for the full tradeoff, including
# the still-open race with a genuinely in-flight compute.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalidate_deletes_once_then_warms():
    svc = _svc()
    adapter = _FakeAdapter()
    svc.db_adapter = adapter
    warmed = []

    async def _warm(sd):
        warmed.append(sd)
    svc._warm_kis_cache = _warm  # noqa: SLF001

    await svc._invalidate_kis_cache("2026-07-07")  # noqa: SLF001

    assert len(adapter.calls) == 1
    assert adapter.calls[0][1] == (dt.date(2026, 7, 7),)
    assert warmed == ["2026-07-07"]


@pytest.mark.asyncio
async def test_invalidate_never_raises_on_db_failure():
    svc = _svc()
    svc.db_adapter = _FakeAdapter(raise_exc=RuntimeError("db down"))
    svc._warm_kis_cache = lambda sd: _noop()  # noqa: SLF001

    await svc._invalidate_kis_cache("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


async def _noop():
    return None


# ---------------------------------------------------------------------------
# _warm_kis_cache — proactive recompute trigger (mirrors _persist_s_effort)
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, status):
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Sess:
    def __init__(self, status=200, raise_exc=None):
        self._status = status
        self._raise = raise_exc
        self.requested = None
        self.params = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def get(self, url, params=None):
        self.requested = url
        self.params = params
        if self._raise:
            raise self._raise
        return _Resp(self._status)


def _warm_svc():
    svc = _svc()

    class Cfg:
        website_api_base = "http://127.0.0.1:8000/api"

    svc.config = Cfg()
    return svc


@pytest.mark.asyncio
async def test_warm_hits_kill_impact_with_the_date():
    sess = _Sess(status=200)
    with patch("aiohttp.ClientSession", return_value=sess):
        await _warm_svc()._warm_kis_cache("2026-07-07")  # noqa: SLF001
    assert sess.requested == "http://127.0.0.1:8000/api/storytelling/kill-impact"
    assert sess.params == {"session_date": "2026-07-07", "limit": 1}


@pytest.mark.asyncio
async def test_warm_never_raises_on_http_error_or_connect_failure():
    with patch("aiohttp.ClientSession", return_value=_Sess(status=404)):
        await _warm_svc()._warm_kis_cache("2026-07-07")  # noqa: SLF001
    with patch("aiohttp.ClientSession",
               return_value=_Sess(raise_exc=ConnectionError("web down"))):
        await _warm_svc()._warm_kis_cache("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


# ---------------------------------------------------------------------------
# _session_dates_touched — midnight-crossing session support
# ---------------------------------------------------------------------------

class _DatesAdapter:
    def __init__(self, rows):
        self._rows = rows
        self.query = None
        self.params = None

    async def fetch_all(self, query, params=()):
        self.query = query
        self.params = params
        return self._rows


@pytest.mark.asyncio
async def test_dates_touched_returns_all_distinct_dates():
    svc = _svc()
    adapter = _DatesAdapter([("2026-07-07",), ("2026-07-08",)])
    svc.db_adapter = adapter

    dates = await svc._session_dates_touched([9001, 9002, 9003])  # noqa: SLF001

    assert dates == ["2026-07-07", "2026-07-08"]
    assert "DISTINCT" in adapter.query
    assert "WHERE id IN" in adapter.query
    assert "gaming_session_id" not in adapter.query
    assert adapter.params == (9001, 9002, 9003)


@pytest.mark.asyncio
async def test_dates_touched_empty_round_ids_short_circuits():
    svc = _svc()
    svc.db_adapter = _DatesAdapter([])

    dates = await svc._session_dates_touched([])  # noqa: SLF001

    assert dates == []


@pytest.mark.asyncio
async def test_dates_touched_never_raises_on_db_failure():
    svc = _svc()

    class _Raising:
        async def fetch_all(self, *a, **kw):
            raise RuntimeError("db down")

    svc.db_adapter = _Raising()

    dates = await svc._session_dates_touched([9001])  # noqa: SLF001
    assert dates == []
