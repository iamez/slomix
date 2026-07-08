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

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def get(self, url):
        self.requested = url
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


@pytest.mark.asyncio
async def test_hook_never_raises_on_http_error_or_connect_failure():
    with patch("aiohttp.ClientSession", return_value=_Sess(status=404)):
        await _svc()._persist_s_effort("2026-07-07")  # noqa: SLF001
    with patch("aiohttp.ClientSession",
               return_value=_Sess(raise_exc=ConnectionError("web down"))):
        await _svc()._persist_s_effort("2026-07-07")  # noqa: SLF001
    # reaching here without an exception IS the assertion


@pytest.mark.asyncio
async def test_finalize_calls_hook_after_results_saved():
    svc = _svc()
    svc.db_adapter = object()
    svc.bot = object()
    svc.prediction_engine = None
    svc._persist_s_effort = AsyncMock()

    class FakeScoring:
        def __init__(self, *a): ...
        async def calculate_session_scores_with_teams(self, *a):
            return {"ok": True}
        async def calculate_session_scores(self, *a):
            return {"ok": True}
        async def save_session_results(self, *_a):
            return True

    class FakeData:
        def __init__(self, *a): ...
        async def get_latest_session_date(self):
            return "2026-07-07"
        async def fetch_session_data(self, *_a):
            return ([1], [133], "133", 6)
        async def get_hardcoded_teams(self, *_a):
            return None

    with patch("bot.services.voice_session_service.StopwatchScoringService", FakeScoring), \
         patch("bot.services.voice_session_service.SessionDataService", FakeData):
        await svc._finalize_session_results()  # noqa: SLF001

    svc._persist_s_effort.assert_awaited_once_with("2026-07-07")
