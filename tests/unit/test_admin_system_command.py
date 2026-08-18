"""!sistem — the Discord side of the system overview.

The command exists to report state, so the cases that matter are the ugly
ones: an API that does not answer, one that answers with an error code, and a
payload where one stage is broken. None of them may raise; all of them must
say something a human can act on.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.cogs.admin_cog import AdminCog


def _cog(api_base="http://127.0.0.1:8000/api"):
    bot = MagicMock()
    bot.config.website_api_base = api_base
    return AdminCog(bot)


def _ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    return ctx


def _patch_session(monkeypatch, resp=None, *, raises=None):
    class _Sess:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def get(self, *a, **k):
            if raises is not None:
                raise raises
            return resp

    monkeypatch.setattr("bot.cogs.admin_cog.aiohttp.ClientSession", lambda *a, **k: _Sess())


def _resp(status=200, payload=None):
    class _Resp:
        def __init__(self):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def json(self):
            return payload or {}

    return _Resp()


_HEALTHY = {
    "generated_at": "2026-08-15T04:55:18+00:00",
    "overall": "ok",
    "stages": [
        {"key": "game_server", "label": "Game server", "state": "ok", "summary": "6/16 players on supply"},
        {"key": "parser", "label": "Parser", "state": "ok", "summary": "14 rounds parsed in the last 7 days"},
    ],
    "linkage": {"available": True, "breach_count": 0, "breaches": []},
}


@pytest.mark.asyncio
async def test_reports_every_stage_and_the_headline(monkeypatch):
    _patch_session(monkeypatch, _resp(200, _HEALTHY))
    ctx = _ctx()

    # @commands.command wraps the coroutine in a Command object;
    # .callback is the plain function underneath.
    await AdminCog.system_status.callback(_cog(), ctx)

    msg = ctx.send.call_args[0][0]
    assert "OK" in msg
    assert "Game server" in msg and "Parser" in msg
    assert "14 rounds parsed" in msg
    assert "nobena meja ni presežena" in msg
    assert "2026-08-15 04:55:18" in msg


@pytest.mark.asyncio
async def test_broken_stage_is_visible_in_the_message(monkeypatch):
    payload = {
        "overall": "warn",
        "stages": [
            {"key": "capture", "label": "Lua capture", "state": "warn",
             "summary": "3 captured rounds not linked in the last 48 h"},
        ],
        "linkage": {"available": True, "breaches": [
            {"metric": "unlinked_lua_ratio", "value": 0.4, "threshold": 0.1},
        ]},
    }
    _patch_session(monkeypatch, _resp(200, payload))
    ctx = _ctx()

    # @commands.command wraps the coroutine in a Command object;
    # .callback is the plain function underneath.
    await AdminCog.system_status.callback(_cog(), ctx)

    msg = ctx.send.call_args[0][0]
    assert "WARN" in msg
    assert "3 captured rounds not linked" in msg
    assert "unlinked_lua_ratio" in msg


@pytest.mark.asyncio
async def test_unreachable_api_answers_instead_of_raising(monkeypatch):
    _patch_session(monkeypatch, raises=OSError("connection refused"))
    ctx = _ctx()

    # @commands.command wraps the coroutine in a Command object;
    # .callback is the plain function underneath.
    await AdminCog.system_status.callback(_cog(), ctx)

    msg = ctx.send.call_args[0][0]
    assert "se ne odziva" in msg
    assert msg.startswith("🔴")


@pytest.mark.asyncio
async def test_http_error_status_is_reported_with_the_code(monkeypatch):
    _patch_session(monkeypatch, _resp(503, {}))
    ctx = _ctx()

    # @commands.command wraps the coroutine in a Command object;
    # .callback is the plain function underneath.
    await AdminCog.system_status.callback(_cog(), ctx)

    msg = ctx.send.call_args[0][0]
    assert "503" in msg


@pytest.mark.asyncio
async def test_linkage_absent_does_not_break_the_message(monkeypatch):
    payload = {"overall": "idle", "stages": [], "linkage": {"available": False}}
    _patch_session(monkeypatch, _resp(200, payload))
    ctx = _ctx()

    # @commands.command wraps the coroutine in a Command object;
    # .callback is the plain function underneath.
    await AdminCog.system_status.callback(_cog(), ctx)

    msg = ctx.send.call_args[0][0]
    assert "IDLE" in msg
    assert "Integriteta" not in msg
