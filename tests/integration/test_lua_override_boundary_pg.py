"""Characterize the legacy Lua correction boundary before opt-in atomicity.

This pins existing partial-commit behavior, not desired enabled-mode behavior.
Only isolated fixture data is written; canonical-ID/linking side effects are
stubbed so this proof concerns the actual round and player UPDATE statements.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.ultimate_bot import UltimateETLegacyBot
from tests.integration.test_runtime_events_pg import journal_db  # noqa: F401


async def test_legacy_player_failure_leaves_round_correction_committed(journal_db, monkeypatch, caplog):  # noqa: F811
    writer, reader = journal_db
    await writer.execute("""
        ALTER TABLE rounds ADD COLUMN actual_duration_seconds INTEGER;
        ALTER TABLE rounds ADD COLUMN time_limit INTEGER;
        ALTER TABLE rounds ADD COLUMN winner_team INTEGER;
        INSERT INTO rounds VALUES (42,1,7,1800,20,1);
        CREATE TABLE player_comprehensive_stats (
            round_id INTEGER, damage_given INTEGER, time_played_seconds REAL,
            time_played_minutes REAL, dpm REAL,
            CONSTRAINT fixture_reject_dpm CHECK (dpm=0)
        );
        INSERT INTO player_comprehensive_stats VALUES (42,1200,1800,30,0);
    """)

    async def fetch_one(query, params=None):
        return await writer.fetchrow(query, *(params or ()))

    async def execute(query, params=None):
        return await writer.execute(query, *(params or ()))

    canonical = AsyncMock()
    monkeypatch.setattr("bot.core.round_canonical.update_canonical_id_if_possible", canonical)
    linker = AsyncMock()
    bot = SimpleNamespace(
        db_adapter=SimpleNamespace(fetch_one=fetch_one, execute=execute),
        _resolve_round_id_for_metadata=AsyncMock(return_value=42),
        _link_lua_round_teams=linker,
    )
    result = await UltimateETLegacyBot._apply_round_metadata_override(  # noqa: SLF001
        bot, "fixture", {"actual_duration_seconds": 600, "winner_team": 2}
    )
    assert result is None  # Legacy API suppresses the player UPDATE failure.
    assert tuple(await reader.fetchrow(
        "SELECT actual_duration_seconds,winner_team FROM rounds WHERE id=42"
    )) == (600, 2)
    assert tuple(await reader.fetchrow(
        "SELECT time_played_seconds,dpm FROM player_comprehensive_stats WHERE round_id=42"
    )) == (1800, 0)
    assert "fixture_reject_dpm" in caplog.text
    canonical.assert_awaited_once()
    linker.assert_awaited_once()
    print("legacy Lua runtime: round committed at 600s; rejected player update stays 1800s; exception suppressed")
