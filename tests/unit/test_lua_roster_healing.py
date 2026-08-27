"""Bot-side safety net for truncated lua rosters (goldrush R2 2026-08-26).

The webhook Lua through v1.7.2 captured the team roster AT INTERMISSION, so
a player who quit mid-round fell out of axis/allies_players while their
stats row survived. v1.7.3 fixes the source; _heal_truncated_lua_rosters is
the bot-side net for older Lua and for rounds captured before the deploy.
These tests pin the append shape (jsonb list of {guid, name}), the
full-GUID reuse, and that a clean roster heals nothing.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bot.cogs.proximity_mixins.relinker_mixin import _ProximityRelinkerMixin


class _StubDb:
    def __init__(self, missing_rows, full_guid_row):
        self.missing_rows = missing_rows
        self.full_guid_row = full_guid_row
        self.executes: list[tuple[str, tuple]] = []

    async def fetch_all(self, query, params=None):
        return self.missing_rows

    async def fetch_one(self, query, params=None):
        return self.full_guid_row

    async def execute(self, query, params=None):
        self.executes.append((query, params))


class _StubBot:
    def __init__(self, db):
        self.db_adapter = db


class _Host(_ProximityRelinkerMixin):
    def __init__(self, db):
        self.bot = _StubBot(db)


def test_missing_player_is_appended_with_full_guid():
    db = _StubDb(
        missing_rows=[(11347, 2, "D8423F90", "vid")],
        full_guid_row=("D8423F90F045D9D3E2C0550811C5A899",),
    )
    healed = asyncio.run(_Host(db)._heal_truncated_lua_rosters())  # noqa: SLF001

    assert healed == 1
    assert len(db.executes) == 1
    query, params = db.executes[0]
    # team 2 -> allies side, jsonb append, round-scoped.
    assert "allies_players" in query and "axis_players" not in query
    assert "round_id = ?" in query
    payload, round_id = params
    assert round_id == 11347
    assert json.loads(payload) == [
        {"guid": "D8423F90F045D9D3E2C0550811C5A899", "name": "vid"}
    ]


def test_axis_side_and_prefix_fallback_without_full_guid():
    db = _StubDb(
        missing_rows=[(11278, 1, "1C747DF1", ".lgz")],
        full_guid_row=None,  # no other lua row knows this player
    )
    healed = asyncio.run(_Host(db)._heal_truncated_lua_rosters())  # noqa: SLF001

    assert healed == 1
    query, params = db.executes[0]
    assert "axis_players" in query and "allies_players" not in query
    # Consumers compare on the 8-char prefix, so the prefix is a valid guid.
    assert json.loads(params[0]) == [{"guid": "1C747DF1", "name": ".lgz"}]


def test_clean_rosters_heal_nothing():
    db = _StubDb(missing_rows=[], full_guid_row=None)
    healed = asyncio.run(_Host(db)._heal_truncated_lua_rosters())  # noqa: SLF001
    assert healed == 0
    assert db.executes == []
