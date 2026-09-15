"""Identity-based cleanup must not release another attempt's marker."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shared.endstats_retry import alias_endstats_marker, claim_endstats_marker, release_endstats_marker


@pytest.mark.parametrize("delete_fails", [False, True])
async def test_webhook_lost_claim_cleans_trigger_without_releasing_owner(monkeypatch, delete_fails):
    import discord

    from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin

    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "true")
    bot = object.__new__(_EndstatsPipelineMixin)
    bot.processed_endstats_files = set()
    claims = []

    async def preflight(*args):
        claims.append(claim_endstats_marker(bot, "original"))
        return None

    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(side_effect=preflight))
    bot.track_error = AsyncMock()
    trigger = SimpleNamespace(delete=AsyncMock(
        side_effect=discord.DiscordException("fixture deletion failure") if delete_fails else None
    ))
    await bot._process_webhook_triggered_endstats("original", trigger)  # noqa: SLF001
    trigger.delete.assert_awaited_once_with()
    assert len(trigger.delete.await_args_list) == 1
    bot.track_error.assert_not_awaited()
    assert bot.processed_endstats_files == {"original"}
    assert bot._endstats_marker_owners["original"] is claims[0]  # noqa: SLF001
    print(f"lost-claim runtime: delete awaits=1, owner retained, delete_fails={delete_fails}")


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "true")
    return SimpleNamespace(processed_endstats_files=set())


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("failure", ["download", "parse", "exception", "replacement"])
async def test_webhook_unscheduled_failure_releases_only_own_claim(monkeypatch, enabled, failure):
    from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin

    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", str(enabled).lower())
    bot = object.__new__(_EndstatsPipelineMixin)
    bot.processed_endstats_files = set()
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=None))
    bot.config = SimpleNamespace(ssh_host="fixture", ssh_port=22, ssh_user="fixture",
                                 ssh_key_path="unused", ssh_remote_path="unused",
                                 stats_directory="unused")
    bot.track_error = AsyncMock()
    trigger = SimpleNamespace(add_reaction=AsyncMock(), reply=AsyncMock())

    async def download(*args):
        if failure == "replacement":
            bot.processed_endstats_files.discard("original")
            claim_endstats_marker(bot, "original")
            raise RuntimeError("fixture replacement")
        if failure == "exception":
            raise RuntimeError("fixture download failure")
        return None if failure == "download" else "unused"

    monkeypatch.setattr("bot.automation.ssh_handler.SSHHandler.download_file", download)
    monkeypatch.setattr("bot.services.endstats_pipeline_mixin.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("bot.endstats_parser.parse_endstats_file", lambda path: None)
    await bot._process_webhook_triggered_endstats("original", trigger)  # noqa: SLF001
    retained = not enabled or failure == "replacement"
    assert ("original" in bot.processed_endstats_files) == retained
    assert bot.track_error.await_count == int(failure in {"exception", "replacement"})
    print(f"webhook failure runtime: enabled={enabled}, failure={failure}, retained={retained}")


def test_claim_is_exclusive_and_own_alias_is_released(bot):
    claim = claim_endstats_marker(bot, "original")
    assert claim_endstats_marker(bot, "original") is None
    alias_endstats_marker(bot, "original", "richer")
    release_endstats_marker(bot, claim)
    assert bot.processed_endstats_files == set()


def test_foreign_alias_survives_cleanup(bot):
    foreign = claim_endstats_marker(bot, "richer")
    own = claim_endstats_marker(bot, "original")
    alias_endstats_marker(bot, "original", "richer")
    release_endstats_marker(bot, own)
    assert bot.processed_endstats_files == {"richer"}
    release_endstats_marker(bot, foreign)
    assert bot.processed_endstats_files == set()


def test_later_replacement_survives_old_attempt_cleanup(bot):
    old = claim_endstats_marker(bot, "original")
    bot.processed_endstats_files.discard("original")  # Existing retry scheduler releases set entries.
    replacement = claim_endstats_marker(bot, "original")
    release_endstats_marker(bot, old)
    assert bot.processed_endstats_files == {"original"}
    release_endstats_marker(bot, replacement)
    assert bot.processed_endstats_files == set()


def test_unowned_alias_is_not_claimed(bot):
    alias_endstats_marker(bot, "missing", "richer")
    release_endstats_marker(bot, None)
    assert bot.processed_endstats_files == {"richer"}


def test_off_preserves_legacy_markers(bot, monkeypatch):
    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "false")
    claim = claim_endstats_marker(bot, "original")
    assert claim_endstats_marker(bot, "original") is True
    alias_endstats_marker(bot, "original", "richer")
    release_endstats_marker(bot, claim)
    assert bot.processed_endstats_files == {"original", "richer"}


@pytest.mark.parametrize("failure", ["not_ready", "unresolved", "publish_failed"])
async def test_polling_soft_failure_preserves_foreign_richer_marker(monkeypatch, failure):
    from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin

    monkeypatch.setenv("ENDSTATS_RETRY_ENABLED", "true")
    bot = object.__new__(_EndstatsPipelineMixin)
    bot.processed_endstats_files = set()
    foreign = claim_endstats_marker(bot, "richer")
    data = {"metadata": {"date": "2026-09-15", "time": "120000", "map_name": "fixture", "round_number": 1},
            "awards": [], "vs_stats": []}
    monkeypatch.setattr("bot.endstats_parser.parse_endstats_file", lambda path: data)
    bot.db_adapter = SimpleNamespace(fetch_one=AsyncMock(return_value=None))
    bot.endstats_retry_counts = {}
    bot.endstats_retry_max_attempts = 5
    bot._resolve_endstats_round_id = AsyncMock(return_value=(None if failure == "unresolved" else 1, "fixture"))  # noqa: SLF001
    bot._is_endstats_round_already_processed = AsyncMock(return_value=False)  # noqa: SLF001
    bot._is_endstats_round_ready = AsyncMock(return_value=failure != "not_ready")  # noqa: SLF001
    bot._store_endstats_and_publish = AsyncMock(return_value=False)  # noqa: SLF001
    bot.track_error = AsyncMock()

    def select(data, path, original, *args):
        alias_endstats_marker(bot, original, "richer")
        return data, "richer", "richer"

    bot._select_richest_endstats = select  # noqa: SLF001
    await bot._process_endstats_file("original", "original")  # noqa: SLF001
    bot.track_error.assert_not_awaited()
    assert bot.processed_endstats_files == {"richer"}
    release_endstats_marker(bot, foreign)
    assert bot.processed_endstats_files == set()
