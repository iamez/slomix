"""Lua metadata overrides must resolve source-native identity before writes."""

# ruff: noqa: SLF001

from unittest.mock import AsyncMock, patch

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _DB:
    def __init__(self):
        self.executed: list[tuple[str, tuple]] = []

    async def fetch_one(self, query, params=None):
        if "FROM rounds WHERE id" in query:
            return (600, 20, 1)
        if "information_schema.columns" in query:
            return ("actual_duration_seconds",)
        return None

    async def execute(self, query, params=None):
        self.executed.append((query, params))


class _Bot:
    def __init__(self, *, exact_round_id=None, fuzzy_round_id=None):
        self.db_adapter = _DB()
        self.exact_round_id = exact_round_id
        self.fuzzy_round_id = fuzzy_round_id
        self.exact_calls = 0
        self.fuzzy_calls = 0
        self.link_calls: list[tuple[int, dict]] = []

    async def _resolve_lua_round_id_for_metadata(self, _metadata):
        self.exact_calls += 1
        return self.exact_round_id

    async def _resolve_round_id_for_metadata(self, _filename, _metadata):
        self.fuzzy_calls += 1
        return self.fuzzy_round_id

    async def _link_lua_round_teams(self, round_id, metadata):
        self.link_calls.append((round_id, metadata))


def _metadata(start_unix):
    return {
        "map_name": "supply",
        "round_number": 1,
        "round_start_unix": start_unix,
        "round_end_unix": 1_776_800_900,
        "winner_team": 2,
    }


@pytest.mark.asyncio
async def test_positive_lua_start_cannot_overwrite_fuzzy_neighbour():
    bot = _Bot(exact_round_id=None, fuzzy_round_id=41)

    await UltimateETLegacyBot._apply_round_metadata_override(
        bot,
        "2026-01-01-supply-round-1.txt",
        _metadata(1_776_800_000),
    )

    assert bot.exact_calls == 1
    assert bot.fuzzy_calls == 0
    assert bot.db_adapter.executed == []


@pytest.mark.asyncio
async def test_positive_lua_start_updates_only_pre_resolved_exact_round():
    bot = _Bot(exact_round_id=42, fuzzy_round_id=41)

    with patch(
        "bot.core.round_canonical.update_canonical_id_if_possible",
        new=AsyncMock(),
    ):
        await UltimateETLegacyBot._apply_round_metadata_override(
            bot,
            "2026-01-01-supply-round-1.txt",
            _metadata(1_776_800_000),
        )

    assert bot.exact_calls == 1
    assert bot.fuzzy_calls == 0
    update_query, update_params = next(
        (query, params)
        for query, params in bot.db_adapter.executed
        if "UPDATE rounds" in query
    )
    assert "WHERE id = $" in update_query
    assert update_params[-1] == 42
    assert bot.link_calls[0][0] == 42


@pytest.mark.asyncio
async def test_legacy_zero_start_keeps_compatibility_resolver():
    bot = _Bot(exact_round_id=None, fuzzy_round_id=None)

    await UltimateETLegacyBot._apply_round_metadata_override(
        bot,
        "2026-01-01-supply-round-1.txt",
        _metadata(0),
    )

    assert bot.exact_calls == 0
    assert bot.fuzzy_calls == 1
    assert bot.db_adapter.executed == []


@pytest.mark.asyncio
async def test_malformed_present_start_fails_closed_without_fuzzy_lookup():
    bot = _Bot(exact_round_id=None, fuzzy_round_id=41)

    await UltimateETLegacyBot._apply_round_metadata_override(
        bot,
        "2026-01-01-supply-round-1.txt",
        _metadata("not-a-timestamp"),
    )

    assert bot.exact_calls == 1
    assert bot.fuzzy_calls == 0
    assert bot.db_adapter.executed == []
