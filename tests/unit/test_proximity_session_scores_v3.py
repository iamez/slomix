"""C3: !proximity_session_scores now consumes the website's v3.0 prox-scores.

The bot no longer re-computes proximity scores with the retired v1 formula; it
fetches the same v3.0 composite the website renders, so Discord and the site can
never disagree. These tests pin the HTTP contract (graceful None on any failure)
and the embed mapping (3 categories + overall, cleaned names, bot rounds hidden).
"""
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.cogs.proximity_mixins.stats_commands_mixin import _ProximityStatsCommandsMixin


class _Cog(_ProximityStatsCommandsMixin):
    def __init__(self, bot):
        self.bot = bot


def _cog(api_base="http://127.0.0.1:8000/api"):
    bot = MagicMock()
    bot.config.website_api_base = api_base
    bot.db_adapter = AsyncMock()
    return _Cog(bot)


def _ctx():
    ctx = MagicMock()
    ctx.send = AsyncMock()
    return ctx


# -- _fetch_prox_scores: the HTTP contract ---------------------------------

def _patch_session(monkeypatch, resp):
    class _Sess:
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        def get(self, *a, **k): return resp
    monkeypatch.setattr(
        "bot.cogs.proximity_mixins.stats_commands_mixin.aiohttp.ClientSession",
        lambda *a, **k: _Sess(),
    )


@pytest.mark.asyncio
async def test_fetch_returns_json_on_200(monkeypatch):
    class _Resp:
        status = 200
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def json(self): return {"status": "ok", "players": []}
    _patch_session(monkeypatch, _Resp())
    out = await _cog()._fetch_prox_scores("2026-08-11")
    assert out == {"status": "ok", "players": []}


@pytest.mark.asyncio
async def test_fetch_returns_none_on_non_200(monkeypatch):
    class _Resp:
        status = 503
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def json(self): return {}
    _patch_session(monkeypatch, _Resp())
    assert await _cog()._fetch_prox_scores("2026-08-11") is None


@pytest.mark.asyncio
async def test_fetch_returns_none_on_exception(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("web down")
    monkeypatch.setattr(
        "bot.cogs.proximity_mixins.stats_commands_mixin.aiohttp.ClientSession", _boom
    )
    assert await _cog()._fetch_prox_scores("2026-08-11") is None


# -- command: embed mapping + graceful fallbacks ---------------------------

async def _run(cog, ctx, date="2026-08-11"):
    # The decorator wraps the method in a Command; call the raw coroutine.
    await _ProximityStatsCommandsMixin.proximity_session_scores.callback(cog, ctx, date)


@pytest.mark.asyncio
async def test_command_maps_v3_and_filters_bots():
    cog = _cog()
    cog._fetch_prox_scores = AsyncMock(return_value={
        "status": "ok",
        "players": [
            {"guid": "G1", "name": "^6S^2uper^6B^2oyy", "prox_overall": 69.0,
             "prox_combat": 100.0, "prox_team": 36.4, "prox_gamesense": 65.0,
             "engagements": 221},
            {"guid": "OMNIBOT_2", "name": "^o[BOT]^7endekk", "prox_overall": 62.7,
             "prox_combat": 45.5, "prox_team": 55.8, "prox_gamesense": 100.0,
             "engagements": 159},
            {"guid": "G3", "name": "SQUUAZE", "prox_overall": 61.8,
             "prox_combat": 81.8, "prox_team": 50.7, "prox_gamesense": 45.5,
             "engagements": 239},
        ],
    })
    ctx = _ctx()
    await _run(cog, ctx)

    embed = ctx.send.call_args.kwargs["embed"]
    # Bot row dropped → only the two real players remain.
    assert len(embed.fields) == 2
    # Color codes stripped for display.
    assert "SuperBoyy" in embed.fields[0].name
    assert "^" not in embed.fields[0].name
    # v3.0 overall + all three categories present.
    assert "69.0" in embed.fields[0].name
    val = embed.fields[0].value
    assert "Combat 100" in val and "Team 36" in val and "Gamesense 65" in val
    assert "[BOT]" not in embed.fields[0].name + embed.fields[1].name
    assert "v3.0" in embed.footer.text


@pytest.mark.asyncio
async def test_command_web_unreachable_is_graceful():
    cog = _cog()
    cog._fetch_prox_scores = AsyncMock(return_value=None)
    ctx = _ctx()
    await _run(cog, ctx)
    assert "unavailable" in ctx.send.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_command_degraded_status_is_graceful():
    cog = _cog()
    cog._fetch_prox_scores = AsyncMock(return_value={"status": "degraded", "players": []})
    ctx = _ctx()
    await _run(cog, ctx)
    assert "not enough" in ctx.send.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_command_no_players_after_bot_filter():
    cog = _cog()
    cog._fetch_prox_scores = AsyncMock(return_value={
        "status": "ok",
        "players": [{"guid": "OMNIBOT_1", "name": "[BOT] x", "prox_overall": 50.0,
                     "prox_combat": 50, "prox_team": 50, "prox_gamesense": 50,
                     "engagements": 100}],
    })
    ctx = _ctx()
    await _run(cog, ctx)
    assert "no proximity data" in ctx.send.call_args.args[0].lower()
