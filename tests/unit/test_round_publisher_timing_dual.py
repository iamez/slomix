from __future__ import annotations

import types

import pytest

from bot.services.round_publisher_service import RoundPublisherService


class _FakeChannel:
    def __init__(self):
        self.name = "unit-test-channel"
        self.sent_embeds = []

    async def send(self, *, embed):
        self.sent_embeds.append(embed)


class _FakeBot:
    def __init__(self, channel):
        self._channel = channel

    def get_channel(self, _channel_id):
        return self._channel

    def get_all_channels(self):
        return [self._channel]


class _NoMapSummaryService(RoundPublisherService):
    async def _check_and_post_map_completion(self, round_id: int, map_name: str, current_round: int, channel):
        return None


class _TimingDualDB:
    def __init__(self, *, round_row, player_rows, lua_row=None):
        self.round_row = round_row
        self.player_rows = player_rows
        self.lua_row = lua_row
        self.fetch_one_calls = []
        self.fetch_all_calls = []

    async def fetch_one(self, query, params):
        self.fetch_one_calls.append((query, params))
        normalized = " ".join(query.split()).lower()
        if "from rounds" in normalized and "where id = ?" in normalized:
            return self.round_row
        if "from lua_round_teams" in normalized:
            return self.lua_row
        return None

    async def fetch_all(self, query, params):
        self.fetch_all_calls.append((query, params))
        return self.player_rows


def _make_player_row(name: str, team: int, kills: int):
    return (
        name, team, kills, 10, 4500, 3000, 100, 40, 2, 5,
        32.0, 0, 1, 1.2, 66.0, 2.0, 9.6, 468.8,
        0, 0, 0, 0, 0, 30,
    )


@pytest.mark.asyncio
async def test_publish_round_stats_dual_timing_shows_sw_el_and_delta():
    round_row = ("12:00", "3:54", 1, "OBJECTIVE")
    player_rows = [_make_player_row("AxisTop", 1, 20)]
    db = _TimingDualDB(round_row=round_row, player_rows=player_rows, lua_row=(266,))
    channel = _FakeChannel()
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=types.SimpleNamespace(production_channel_id=123, show_timing_dual=True),
        db_adapter=db,
    )

    await service.publish_round_stats(
        filename="2026-02-24-223229-te_escape2-round-1.txt",
        result={
            "round_id": 9955,
            "stats_data": {
                "round_num": 1,
                "map_name": "te_escape2",
                "winner_team": 1,
                "round_outcome": "OBJECTIVE",
            },
        },
    )

    assert len(channel.sent_embeds) == 1
    desc = channel.sent_embeds[0].description or ""
    assert "SW `3:54`" in desc
    assert "EL `4:26`" in desc
    assert "Δ `+0:32`" in desc


@pytest.mark.asyncio
async def test_publish_round_stats_dual_timing_shows_surrender_negative_delta():
    # Regression target: surrender-style drift where stopwatch can overstate elapsed time.
    round_row = ("20:00", "20:00", 1, "SURRENDER")
    player_rows = [_make_player_row("AxisTop", 1, 20)]
    db = _TimingDualDB(round_row=round_row, player_rows=player_rows, lua_row=(300,))
    channel = _FakeChannel()
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=types.SimpleNamespace(production_channel_id=123, show_timing_dual=True),
        db_adapter=db,
    )

    await service.publish_round_stats(
        filename="2026-02-24-230000-supply-round-2.txt",
        result={
            "round_id": 9960,
            "stats_data": {
                "round_num": 2,
                "map_name": "supply",
                "winner_team": 1,
                "round_outcome": "SURRENDER",
            },
        },
    )

    assert len(channel.sent_embeds) == 1
    desc = channel.sent_embeds[0].description or ""
    assert "SW `20:00`" in desc
    assert "EL `5:00`" in desc
    assert "Δ `-15:00`" in desc


@pytest.mark.asyncio
async def test_publish_round_stats_dual_timing_labels_lua_fallback_when_missing():
    round_row = ("12:00", "3:54", 1, "OBJECTIVE")
    player_rows = [_make_player_row("AxisTop", 1, 20)]
    db = _TimingDualDB(round_row=round_row, player_rows=player_rows, lua_row=None)
    channel = _FakeChannel()
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=types.SimpleNamespace(production_channel_id=123, show_timing_dual=True),
        db_adapter=db,
    )

    await service.publish_round_stats(
        filename="2026-02-24-223229-te_escape2-round-1.txt",
        result={
            "round_id": 9955,
            "stats_data": {
                "round_num": 1,
                "map_name": "te_escape2",
                "winner_team": 1,
                "round_outcome": "OBJECTIVE",
            },
        },
    )

    assert len(channel.sent_embeds) == 1
    desc = channel.sent_embeds[0].description or ""
    assert "SW `3:54`" in desc
    assert "EL `N/A` (fallback: no-lua-link)" in desc
