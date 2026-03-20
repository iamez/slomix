from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


REQUIRED_COLUMNS = [
    "round_id",
    "player_guid",
    "player_name",
    "kills",
    "deaths",
    "damage_given",
    "damage_received",
    "time_played_seconds",
    "time_dead_minutes",
    "time_dead_ratio",
    "kill_assists",
    "dynamites_planted",
    "times_revived",
    "revives_given",
    "most_useful_kills",
    "useless_kills",
    "kill_steals",
    "denied_playtime",
    "constructions",
]


class _SchemaValidationDB:
    def __init__(self, columns: list[str]) -> None:
        self.columns = columns

    async def fetch_all(self, query: str):
        assert "information_schema.columns" in query
        return [(column,) for column in self.columns]


def _dummy_bot(columns: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        config=SimpleNamespace(database_type="postgresql"),
        db_adapter=_SchemaValidationDB(columns),
    )


@pytest.mark.asyncio
async def test_validate_database_schema_allows_additive_columns():
    columns = REQUIRED_COLUMNS + [f"optional_{idx}" for idx in range(38)]
    dummy = _dummy_bot(columns)

    await UltimateETLegacyBot.validate_database_schema(dummy)


@pytest.mark.asyncio
async def test_validate_database_schema_rejects_missing_required_columns():
    columns = [column for column in REQUIRED_COLUMNS if column != "denied_playtime"]
    columns.extend(f"optional_{idx}" for idx in range(40))
    dummy = _dummy_bot(columns)

    with pytest.raises(RuntimeError, match="Missing required unified-schema columns"):
        await UltimateETLegacyBot.validate_database_schema(dummy)
