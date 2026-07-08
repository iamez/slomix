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


class _ExplodingBot:
    def get_channel(self, _channel_id):
        raise AssertionError("production channel should not be resolved when autopost is disabled")

    def get_all_channels(self):
        raise AssertionError("channel list should not be read when autopost is disabled")


class _ExplodingDB:
    async def fetch_one(self, *_args, **_kwargs):
        raise AssertionError("database should not be queried when autopost is disabled")

    async def fetch_all(self, *_args, **_kwargs):
        raise AssertionError("database should not be queried when autopost is disabled")


class _RoundDB:
    def __init__(self):
        self.fetch_one_calls = []
        self.fetch_all_calls = []

    async def fetch_one(self, query, params):
        self.fetch_one_calls.append((query, params))
        normalized = " ".join(query.split()).lower()
        if "from rounds" in normalized and "where id = ?" in normalized:
            return ("12:00", "9:39", 1, "OBJECTIVE")
        return None

    async def fetch_all(self, query, params):
        self.fetch_all_calls.append((query, params))
        return [
            (
                "AxisTop", 1, 20, 10, 4500, 3000, 100, 40, 2, 5,
                32.0, 0, 1, 1.2, 66.0, 2.0, 9.6, 468.8,
                0, 0, 0, 0, 0, 30,
            )
        ]


class _NoMapSummaryService(RoundPublisherService):
    def __init__(self, bot, config, db_adapter):
        super().__init__(bot=bot, config=config, db_adapter=db_adapter)
        self.map_completion_calls = []

    async def _check_and_post_map_completion(self, round_id: int, map_name: str, current_round: int, channel):
        self.map_completion_calls.append((round_id, map_name, current_round, channel))


def _config(*, enabled: bool):
    return types.SimpleNamespace(
        production_channel_id=123,
        round_stats_autopost_enabled=enabled,
        show_timing_dual=False,
    )


def _result():
    return {
        "round_id": 9819,
        "stats_data": {
            "round_num": 2,
            "map_name": "supply",
            "winner_team": 1,
            "round_outcome": "OBJECTIVE",
        },
    }


def test_round_stats_autopost_config_defaults_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
    monkeypatch.setenv("AUTOMATION_ENABLED", "false")
    monkeypatch.setenv("SSH_ENABLED", "false")
    monkeypatch.delenv("ROUND_STATS_AUTOPOST_ENABLED", raising=False)

    from bot.config import BotConfig

    cfg = BotConfig(config_file=str(tmp_path / "missing-bot-config.json"))

    assert cfg.round_stats_autopost_enabled is True


def test_round_stats_autopost_config_false(monkeypatch, tmp_path):
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "test_token")
    monkeypatch.setenv("AUTOMATION_ENABLED", "false")
    monkeypatch.setenv("SSH_ENABLED", "false")
    monkeypatch.setenv("ROUND_STATS_AUTOPOST_ENABLED", "false")

    from bot.config import BotConfig

    cfg = BotConfig(config_file=str(tmp_path / "missing-bot-config.json"))

    assert cfg.round_stats_autopost_enabled is False


@pytest.mark.asyncio
async def test_publish_round_stats_disabled_skips_channel_db_and_map_summary():
    service = _NoMapSummaryService(
        bot=_ExplodingBot(),
        config=_config(enabled=False),
        db_adapter=_ExplodingDB(),
    )

    posted = await service.publish_round_stats(
        filename="2026-02-11-220205-supply-round-2.txt",
        result=_result(),
    )

    assert posted is False
    assert service.map_completion_calls == []


@pytest.mark.asyncio
async def test_publish_round_stats_enabled_posts_embed_and_checks_map_summary():
    channel = _FakeChannel()
    service = _NoMapSummaryService(
        bot=_FakeBot(channel),
        config=_config(enabled=True),
        db_adapter=_RoundDB(),
    )

    posted = await service.publish_round_stats(
        filename="2026-02-11-220205-supply-round-2.txt",
        result=_result(),
    )

    assert posted is True
    assert len(channel.sent_embeds) == 1
    assert len(service.map_completion_calls) == 1
    assert service.map_completion_calls[0][0:3] == (9819, "supply", 2)


@pytest.mark.asyncio
async def test_publish_endstats_disabled_returns_success_without_channel_lookup():
    service = RoundPublisherService(
        bot=_ExplodingBot(),
        config=_config(enabled=False),
        db_adapter=_ExplodingDB(),
    )

    published = await service.publish_endstats(
        filename="2026-02-11-220205-supply-round-2-endstats.txt",
        endstats_data={"awards": []},
        round_id=9819,
        map_name="supply",
        round_number=2,
    )

    assert published is True
