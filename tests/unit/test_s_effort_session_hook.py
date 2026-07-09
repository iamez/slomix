"""Session-end s.effort persist hook (voice_session_service).

The bot must fire a best-effort GET to /skill/s-effort at session finalize —
and NEVER let that call break finalization (old website builds without the
endpoint return 404; the web may be down entirely).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from bot.services.voice_session_service import VoiceSessionService


def _svc():
    svc = VoiceSessionService.__new__(VoiceSessionService)

    class Cfg:
        website_api_base = "http://127.0.0.1:8000/api"
        internal_api_secret = "test-internal-secret"  # noqa: S105 - test-only shared secret

    svc.config = Cfg()
    return svc


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
        self.headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def get(self, url, headers=None):
        self.requested = url
        self.headers = headers
        if self._raise:
            raise self._raise
        return _Resp(self._status)


@pytest.mark.asyncio
async def test_hook_hits_the_endpoint_with_the_date():
    sess = _Sess(status=200)
    with patch("aiohttp.ClientSession", return_value=sess):
        await _svc()._persist_s_effort("2026-07-07")  # noqa: SLF001
    assert sess.requested == (
        "http://127.0.0.1:8000/api/skill/s-effort?session_date=2026-07-07")
    assert sess.headers == {"X-Internal-Token": "test-internal-secret"}


@pytest.mark.asyncio
async def test_hook_never_raises_on_http_error_or_connect_failure():
    with patch("aiohttp.ClientSession", return_value=_Sess(status=404)):
        await _svc()._persist_s_effort("2026-07-07")  # noqa: SLF001
    with patch("aiohttp.ClientSession",
               return_value=_Sess(raise_exc=ConnectionError("web down"))):
        await _svc()._persist_s_effort("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


class _FakeAdapter:
    """fetch_one for the session start-date lookup (midnight-safe scope).

    session_ids are rounds.id values, so the lookup must filter by
    `id IN (...)`, never `gaming_session_id IN (...)` (which would silently
    match nothing since round ids and gaming_session_id are unrelated).
    """

    async def fetch_one(self, query, params=()):
        assert "MIN(SUBSTRING(round_date" in query
        assert "WHERE id IN" in query
        assert "gaming_session_id" not in query
        return ("2026-07-07",)

    async def fetch_all(self, query, params=()):
        # session_dates_touched lookup for KIS invalidation — return the
        # single test date so the background task has something to no-op
        # against (test_kis_cache_invalidation_hook.py covers its own
        # behavior directly).
        assert "DISTINCT SUBSTRING(round_date" in query
        assert "WHERE id IN" in query
        return [("2026-07-07",)]

    async def execute(self, query, params=()):
        return None


def _fakes(save_ok=True, order=None):
    order = order if order is not None else []

    class FakeScoring:
        def __init__(self, *a): ...
        async def calculate_session_scores_with_teams(self, *a):
            return {"ok": True}
        async def calculate_session_scores(self, *a):
            return {"ok": True}
        async def save_session_results(self, *_a):
            order.append("saved")
            return save_ok

    class FakeData:
        def __init__(self, *a): ...
        async def get_latest_session_date(self):
            return "2026-07-08"  # LAST round crossed midnight
        async def fetch_session_data(self, *_a):
            # session_ids are rounds.id values (real semantics — not a
            # gaming_session_id) so use plausible round primary keys here.
            # session_ids_str follows SessionDataService's actual contract:
            # SQL placeholders ("?,?"), not a literal comma-joined id list.
            round_ids = [9001, 9002]
            return ([1], round_ids, ",".join("?" * len(round_ids)), 6)
        async def get_hardcoded_teams(self, *_a):
            return None

    return FakeScoring, FakeData, order


async def _run_finalize(svc):
    import asyncio
    await svc._finalize_session_results()  # noqa: SLF001
    # the persist + KIS-invalidate calls run as background tasks — let them
    # get scheduled and complete (both are a single fast DB call, no delay).
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_finalize_persists_start_date_after_results_saved():
    svc = _svc()
    svc.db_adapter = _FakeAdapter()
    svc.bot = object()
    svc.prediction_engine = None
    order = []

    async def _persist(date):
        order.append(("persist", date))
    svc._persist_s_effort = _persist  # noqa: SLF001

    FakeScoring, FakeData, order = _fakes(save_ok=True, order=order)
    with patch("bot.services.voice_session_service.StopwatchScoringService", FakeScoring), \
         patch("bot.services.voice_session_service.SessionDataService", FakeData):
        await _run_finalize(svc)

    # explicit ORDER: results saved first, then the persist — and the persist
    # carries the session START date, not the midnight-crossed last date
    assert order == ["saved", ("persist", "2026-07-07")]


@pytest.mark.asyncio
async def test_finalize_persists_even_when_scoring_save_fails():
    svc = _svc()
    svc.db_adapter = _FakeAdapter()
    svc.bot = object()
    svc.prediction_engine = None
    svc._persist_s_effort = AsyncMock()  # noqa: SLF001

    FakeScoring, FakeData, _ = _fakes(save_ok=False)
    with patch("bot.services.voice_session_service.StopwatchScoringService", FakeScoring), \
         patch("bot.services.voice_session_service.SessionDataService", FakeData):
        await _run_finalize(svc)

    svc._persist_s_effort.assert_awaited_once_with("2026-07-07")  # noqa: SLF001
