"""A warm attempt requires a verified completed response in the requested scope."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from bot.services.voice_session_service import VoiceSessionService

pytestmark = pytest.mark.asyncio


def payload(status="computed"):
    return {"status": "ok", "compute": {"status": status, "kills_scored": 0 if status == "no_data" else 92},
            "scope": {"gaming_session_id": 184, "dates": ["2026-11-12", "2026-11-13"]}}


def service():
    result = VoiceSessionService.__new__(VoiceSessionService)
    result.config = SimpleNamespace(internal_api_secret="warm-fixture-only",  # noqa: S106 - synthetic fixture
                                    website_api_base="http://fixture.invalid/api")
    return result


def transport(monkeypatch, body, status=200, error=None):
    response = SimpleNamespace(status=status, json=AsyncMock(return_value=body, side_effect=error))
    request = MagicMock()
    request.__aenter__ = AsyncMock(return_value=response)
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.get.return_value = request
    monkeypatch.setattr(aiohttp, "ClientSession", MagicMock(return_value=session))
    return response, session


async def test_matching_computed_response_confirms_attempt(monkeypatch, caplog):
    response, session = transport(monkeypatch, payload())
    with caplog.at_level("INFO"):
        assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is True
    response.json.assert_awaited_once_with()
    assert session.get.call_args.kwargs["params"] == {"gaming_session_id": 184, "limit": 1}
    assert "cache warmed" in caplog.text


@pytest.mark.parametrize("status", ["read_only", "error", "unknown"])
async def test_unconfirmed_200_does_not_consume_attempt(monkeypatch, caplog, status):
    transport(monkeypatch, payload(status))
    with caplog.at_level("INFO"):
        assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False
    assert "cache warmed" not in caplog.text


@pytest.mark.parametrize("status", ["cached", "no_data"])
async def test_completed_noncompute_attempt_is_counted_without_claiming_calculation(monkeypatch, caplog, status):
    transport(monkeypatch, payload(status))
    with caplog.at_level("INFO"):
        assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is True
    assert "cache warmed" not in caplog.text
    assert f"returned {status}; no compute performed" in caplog.text


async def test_inconsistent_empty_result_is_not_confirmed(monkeypatch):
    body = payload("no_data")
    body["compute"]["kills_scored"] = 92
    transport(monkeypatch, body)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


@pytest.mark.parametrize("field,value", [
    ("status", "error"), ("compute", None), ("compute", []), ("scope", None), ("scope", []),
])
async def test_invalid_envelope_is_not_success(monkeypatch, field, value):
    body = payload()
    body[field] = value
    transport(monkeypatch, body)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


@pytest.mark.parametrize("body", [None, [], "not-an-envelope", {}])
async def test_malformed_payload_is_not_success(monkeypatch, body):
    transport(monkeypatch, body)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


@pytest.mark.parametrize("gsid", [185, "184", True, None, 0])
async def test_wrong_or_unverified_session_is_not_success(monkeypatch, gsid):
    body = payload()
    body["scope"]["gaming_session_id"] = gsid
    transport(monkeypatch, body)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


@pytest.mark.parametrize("count", [None, True, "92", -1, 1.5])
async def test_unverified_scored_count_is_not_success(monkeypatch, count):
    body = payload()
    body["compute"]["kills_scored"] = count
    transport(monkeypatch, body)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


@pytest.mark.parametrize("date,expected", [("2026-11-12", True), ("2026-11-13", True), ("2026-11-14", False)])
async def test_date_fallback_checks_resolved_scope_dates(monkeypatch, date, expected):
    _, session = transport(monkeypatch, payload())
    assert await service().warm_kis_cache(date) is expected
    assert session.get.call_args.kwargs["params"] == {"session_date": date, "limit": 1}


@pytest.mark.parametrize("status", [401, 404, 503])
async def test_http_errors_do_not_read_or_accept_json(monkeypatch, status):
    response, _ = transport(monkeypatch, payload(), status=status)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False
    response.json.assert_not_awaited()


@pytest.mark.parametrize("error", [ValueError("Invalid JSON fixture"), TimeoutError("Fixture timeout")])
async def test_json_or_transport_failure_is_best_effort(monkeypatch, error):
    transport(monkeypatch, None, error=error)
    assert await service().warm_kis_cache("2026-11-12", gaming_session_id=184) is False


async def test_missing_secret_never_requests_http(monkeypatch):
    transport(monkeypatch, payload())
    owner = service()
    owner.config.internal_api_secret = ""
    assert await owner.warm_kis_cache("2026-11-12", gaming_session_id=184) is False
    aiohttp.ClientSession.assert_not_called()


@pytest.mark.parametrize("enabled", [False, True], ids=["generation-off", "generation-on"])
async def test_warm_receipt_through_actual_cache_and_auth(monkeypatch, enabled):
    from tests.unit.test_http_cache_internal_requests import PATH, SECRET, client_for
    from website.backend.services.http_cache_backend import MemoryCacheBackend

    for flag in ("EVENT_STREAM_ENABLED", "RUNTIME_HTTP_CACHE_EVENTS_ENABLED",
                 "RUNTIME_HTTP_CACHE_NAMESPACE_ENABLED"):
        monkeypatch.setenv(flag, str(enabled).lower())
    monkeypatch.setenv("INTERNAL_API_SECRET", SECRET)
    client, calls = client_for(MemoryCacheBackend(), AsyncMock(return_value=1))
    statuses = []

    class Request:
        def __init__(self, params, headers):
            self.params, self.headers = params, headers

        async def __aenter__(self):
            response = await client.get(PATH, params=self.params, headers=self.headers)
            statuses.append(response.status_code)
            return SimpleNamespace(status=response.status_code,
                                   json=AsyncMock(return_value=response.json()))

        async def __aexit__(self, *args):
            return False

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def get(self, url, *, params, headers):
            assert url == "http://fixture.invalid/api/storytelling/kill-impact"
            return Request(params, headers)

    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: Session())
    owner = service()
    owner.config.internal_api_secret = SECRET
    params = {"gaming_session_id": 184, "limit": 1}
    async with client:
        assert (await client.get(PATH, params=params)).headers["X-Cache"] == "MISS"
        assert (await client.get(PATH, params=params)).headers["X-Cache"] == "HIT"
        assert await owner.warm_kis_cache("2026-11-12", gaming_session_id=184) is True
        owner.config.internal_api_secret = "invalid-fixture"  # noqa: S105 - deliberately invalid fixture
        assert await owner.warm_kis_cache("2026-11-12", gaming_session_id=184) is False
        public = await client.get(PATH, params=params)
        assert public.headers["X-Cache"] == "HIT"
        assert public.json()["compute"]["status"] == "read_only"
    assert statuses == [200, 401]
    assert calls == [(184, False), (184, True)]


@pytest.mark.parametrize("status", ["cached", "no_data"])
async def test_confirmed_noncompute_attempt_cannot_starve_older_gap(monkeypatch, status):
    from bot.services.monitor_tasks_mixin import _MonitorTasksMixin
    from tests.unit.test_kis_coverage_reconcile import Bot

    owner = service()
    bot = Bot([(gsid, "2026-11-12", 100, 0) for gsid in (200, 199, 198, 197)])
    bot.voice_session_service = owner
    _, session = transport(monkeypatch, None)
    calls = []

    def request(url, *, params, headers):
        gsid = params["gaming_session_id"]
        calls.append(gsid)
        body = payload("computed" if gsid == 197 else status)
        body["scope"]["gaming_session_id"] = gsid
        response = SimpleNamespace(status=200, json=AsyncMock(return_value=body))
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        return context

    session.get.side_effect = request
    attempt_limit = _MonitorTasksMixin._KIS_RECONCILE_MAX_ATTEMPTS  # noqa: SLF001 - actual scheduler budget
    for _ in range(attempt_limit + 1):
        await _MonitorTasksMixin.kis_coverage_reconcile.coro(bot)
    assert 197 in calls
    for gsid in (200, 199, 198):
        assert calls.count(gsid) == attempt_limit
