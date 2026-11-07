"""Source-grounded counter contracts; actual validator, no DB/config setup.

ET:Legacy v2.85.0 (489f1c4f) G_addStats in src/game/g_match.c increments
sess.team_kills then returns before weapon kills in normal non-debug builds.
c0rnp0rn8.lua writes that independent counter in TAB[6]. It is not a subset
of the weapon kills summed by our parser. Live binary/data impact is unmeasured.
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import postgresql_database_manager as module


@pytest.fixture
def manager(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Validation must not load application config or access DB")
    monkeypatch.setattr(module, "load_config", forbidden)
    monkeypatch.setattr(module.asyncpg, "connect", forbidden)
    monkeypatch.setattr(module.asyncpg, "create_pool", forbidden)
    return module.PostgreSQLDatabaseManager(
        config=SimpleNamespace(database_type="postgresql"), allow_legacy_r1_fallback=False)


@pytest.mark.parametrize("kills,team_kills", [(0, 3), (5, 10), (10, 3)])
def test_team_kills_are_independent_of_enemy_kills(manager, kills, team_kills):
    player = {"kills": kills, "objective_stats": {"team_kills": team_kills}}
    expected = deepcopy(player)
    corrected, issues = manager.validate_player_stats(player)
    assert corrected == expected
    assert not issues


def test_negative_kills_cannot_manufacture_negative_nested_counters(manager):
    corrected, issues = manager.validate_player_stats({
        "kills": -5, "deaths": 2, "damage_given": -10,
        "objective_stats": {"headshot_kills": 2, "team_kills": 7},
    })
    assert corrected == {"kills": 0, "deaths": 2, "damage_given": 0,
                         "objective_stats": {"headshot_kills": 0, "team_kills": 7}}
    assert "kills (-5) is negative" in issues
    assert "damage_given (-10) is negative" in issues
    assert not any("team_kills" in issue for issue in issues)


async def test_parser_to_validator_and_writer_retains_independent_team_kills(manager, tmp_path):
    fields = ["0"] * 38
    fields[6] = "3"  # Independent teamkill counter.
    fields[22] = "1"  # One minute played.
    path = tmp_path / "2026-01-01-120000-supply-round-1.txt"
    path.write_text("x\\supply\\x\\1\\2\\1\\20:00\\1:00\\60000\n"
                    "12345678\\Synthetic\\1\\1\\16 1 1 0 0 0 \t" + "\t".join(fields) + "\n")
    result = manager.parser.parse_stats_file(str(path))
    assert result["success"] is True
    assert result["total_players"] == len(result["players"]) == 1
    parsed = result["players"][0]
    assert parsed["kills"] == 0
    assert parsed["objective_stats"]["team_kills"] == 3
    corrected, issues = manager.validate_player_stats(deepcopy(parsed))
    assert corrected == parsed
    assert issues == []
    # Execute the real writer but record its SQL boundary; this is NOT a DB proof.
    connection = SimpleNamespace(
        fetchval=AsyncMock(side_effect=[1, None]),
        execute=AsyncMock(return_value="INSERT 0 1"),
    )
    # Exercise the canonical insertion boundary without creating a database.
    inserted = await manager._insert_player_stats(  # noqa: SLF001
        connection, 42, "2026-01-01", result)
    assert inserted == 1
    assert connection.fetchval.await_count == 2
    sql, *arguments = connection.fetchval.await_args_list[0].args
    assert "INSERT INTO player_comprehensive_stats" in sql
    columns = [name.strip() for name in sql.split("(", 1)[1].split(")", 1)[0].split(",")]
    sent = dict(zip(columns, arguments, strict=True))
    assert sent["round_id"] == 42
    assert sent["player_guid"] == "12345678"
    assert sent["kills"] == 0
    assert sent["team_kills"] == 3
    assert sent["headshot_kills"] == 0
    connection.execute.assert_awaited_once()
    assert manager.pool is None
