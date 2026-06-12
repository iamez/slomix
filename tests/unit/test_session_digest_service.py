"""Unit tests for SessionDigestService (S1.1)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.services.session_digest_service import SessionDigestService


def _config(**over):
    cfg = MagicMock()
    cfg.session_digest_min_rounds = 4
    cfg.stats_channel_id = 111
    cfg.production_channel_id = 222
    cfg.website_api_base = "http://127.0.0.1:9"  # unreachable on purpose
    cfg.website_public_base = "https://www.slomix.fyi"
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _service(cfg=None):
    bot = MagicMock()
    bot.db_path = None
    return SessionDigestService(bot, AsyncMock(), cfg or _config()), bot


# Live shape (verified on dev): team_a_maps/_team1_score + maps[].map.
SCORING = {
    "team_a_name": "puran", "team_a_maps": 5, "_team1_score": 5,
    "team_b_name": "sWat", "team_b_maps": 3, "_team2_score": 3,
    "maps": [{"map": "supply", "winner": "puran"},
             {"map": "adlernest", "winner": "sWat"}],
}


def _wire_services(mock_data_cls, mock_scoring_cls, *, rounds=8):
    data = mock_data_cls.return_value
    data.get_latest_session_date = AsyncMock(return_value="2026-06-11")
    data.fetch_session_data = AsyncMock(
        return_value=([object()] * rounds, [1, 2], "1,2", 6)
    )
    data.get_hardcoded_teams = AsyncMock(return_value={
        "puran": {"guids": ["A"]}, "sWat": {"guids": ["B"]},
    })
    data.get_team_mvps = AsyncMock(return_value=(
        ("vid", 40, 410.0, 20, 5, 3), ("SuperBoyy", 38, 395.0, 22, 2, 6),
    ))
    scoring = mock_scoring_cls.return_value
    scoring.calculate_session_scores_with_teams = AsyncMock(return_value=SCORING)
    scoring.calculate_session_scores = AsyncMock(return_value=None)
    return data, scoring


@pytest.mark.asyncio
@patch("bot.services.session_digest_service.StopwatchScoringService")
@patch("bot.services.session_digest_service.SessionDataService")
async def test_digest_embed_content_and_kis_fallback(mock_data_cls, mock_scoring_cls):
    _wire_services(mock_data_cls, mock_scoring_cls)
    svc, _ = _service()

    embed = await svc._build_embed()

    assert embed is not None
    assert "puran 5 : 3 sWat" in embed.description
    assert "puran** took the night" in embed.description
    names = [f.name for f in embed.fields]
    assert "🗺️ Maps" in names and "⭐ MVPs" in names and "🔗 Deep dive" in names
    # KIS API unreachable -> no KIS field, but embed still built
    assert "💥 Highest impact (KIS)" not in names
    assert embed.url.endswith("/#/session-detail/date/2026-06-11")


@pytest.mark.asyncio
@patch("bot.services.session_digest_service.StopwatchScoringService")
@patch("bot.services.session_digest_service.SessionDataService")
async def test_digest_skips_stub_sessions(mock_data_cls, mock_scoring_cls):
    _wire_services(mock_data_cls, mock_scoring_cls, rounds=2)  # < min 4
    svc, _ = _service()
    assert await svc._build_embed() is None


@pytest.mark.asyncio
@patch("bot.services.session_digest_service.StopwatchScoringService")
@patch("bot.services.session_digest_service.SessionDataService")
async def test_post_uses_stats_channel_and_reports_success(mock_data_cls, mock_scoring_cls):
    _wire_services(mock_data_cls, mock_scoring_cls)
    svc, bot = _service()
    channel = MagicMock()
    channel.send = AsyncMock()
    bot.get_channel = MagicMock(return_value=channel)

    posted = await svc.generate_and_post()

    assert posted is True
    bot.get_channel.assert_called_once_with(111)
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
@patch("bot.services.session_digest_service.StopwatchScoringService")
@patch("bot.services.session_digest_service.SessionDataService")
async def test_build_failure_never_raises(mock_data_cls, mock_scoring_cls):
    mock_data_cls.return_value.get_latest_session_date = AsyncMock(
        side_effect=RuntimeError("db down")
    )
    svc, _ = _service()
    assert await svc.generate_and_post() is False
