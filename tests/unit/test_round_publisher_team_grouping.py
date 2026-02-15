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


class _FakeDB:
    def __init__(self, round_row, player_rows):
        self.round_row = round_row
        self.player_rows = player_rows
        self.fetch_one_calls = []
        self.fetch_all_calls = []

    async def fetch_one(self, query, params):
        self.fetch_one_calls.append((query, params))
        return self.round_row

    async def fetch_all(self, query, params):
        self.fetch_all_calls.append((query, params))
        return self.player_rows


class _NoMapSummaryService(RoundPublisherService):
    def __init__(self, bot, config, db_adapter):
        super().__init__(bot=bot, config=config, db_adapter=db_adapter)
        self.map_completion_calls = []

    async def _check_and_post_map_completion(self, round_id: int, map_name: str, current_round: int, channel):
        self.map_completion_calls.append((round_id, map_name, current_round, channel))


def _make_player_row(name: str, team: int, kills: int):
    # player_name, team, kills, deaths, damage_given, damage_received,
    # team_damage_given, team_damage_received, gibs, headshots,
    # accuracy, revives_given, times_revived, time_dead_minutes,
    # efficiency, kd_ratio, time_played_minutes, dpm,
    # double_kills, triple_kills, quad_kills, multi_kills, mega_kills,
    # denied_playtime
    return (
        name, team, kills, 10, 4500, 3000, 100, 40, 2, 5,
        32.0, 0, 1, 1.2, 66.0, 2.0, 9.6, 468.8,
        0, 0, 0, 0, 0, 30,
    )


@pytest.mark.asyncio
async def test_publish_round_stats_groups_players_by_team_with_local_ranks():
    round_row = ("12:00", "9:39", 1, "OBJECTIVE")
    player_rows = [
        _make_player_row("AxisTop", 1, 20),
        _make_player_row("AlliesTop", 2, 15),
        _make_player_row("AxisLow", 1, 10),
        _make_player_row("UnknownSide", 0, 5),
    ]

    channel = _FakeChannel()
    db = _FakeDB(round_row=round_row, player_rows=player_rows)
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=types.SimpleNamespace(production_channel_id=123),
        db_adapter=db,
    )

    await service.publish_round_stats(
        filename="2026-02-11-220205-supply-round-2.txt",
        result={
            "round_id": 9819,
            "stats_data": {
                "round_num": 2,
                "map_name": "supply",
                "winner_team": 1,
                "round_outcome": "OBJECTIVE",
            },
        },
    )

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]

    field_map = {field.name: field.value for field in embed.fields}
    assert "⚔️ Axis" in field_map
    assert "🛡️ Allies" in field_map
    assert "❓ Unknown Side" in field_map

    axis_value = field_map["⚔️ Axis"]
    allies_value = field_map["🛡️ Allies"]
    unknown_value = field_map["❓ Unknown Side"]

    # Team-local ranking should restart per section.
    assert "🥇 **AxisTop**" in axis_value
    assert "🥈 **AxisLow**" in axis_value
    assert "🥇 **AlliesTop**" in allies_value
    assert "🥇 **UnknownSide**" in unknown_value

    # Map summary check flow is still called after posting.
    assert len(service.map_completion_calls) == 1
    assert service.map_completion_calls[0][0:3] == (9819, "supply", 2)


@pytest.mark.asyncio
async def test_publish_round_stats_keeps_discord_field_values_within_limit():
    round_row = ("12:00", "9:39", 1, "OBJECTIVE")
    player_rows = []
    for i in range(1, 18):
        player_rows.append(_make_player_row(f"AxisPlayer{i:02d}", 1, 30 - i))

    channel = _FakeChannel()
    db = _FakeDB(round_row=round_row, player_rows=player_rows)
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=types.SimpleNamespace(production_channel_id=123),
        db_adapter=db,
    )

    await service.publish_round_stats(
        filename="2026-02-11-220205-supply-round-2.txt",
        result={
            "round_id": 9819,
            "stats_data": {
                "round_num": 2,
                "map_name": "supply",
                "winner_team": 1,
                "round_outcome": "OBJECTIVE",
            },
        },
    )

    assert len(channel.sent_embeds) == 1
    embed = channel.sent_embeds[0]
    axis_fields = [f for f in embed.fields if f.name.startswith("⚔️ Axis")]
    assert len(axis_fields) >= 2
    for field in axis_fields:
        assert len(field.value) <= 1024
