"""L2 (Codex): lock in the CURRENT relinker fanout/detection table coverage,
BEFORE any change (test/linkage-writer-lock).

Codex §18 found combat_engagement, player_track, and lua_round_teams among
the proximity tables with the WORST wrong-round-linkage rates — precisely
because none of the three is in ProximityCog._PROXIMITY_ROUND_ID_TABLES
(the 5-minute relinker's fanout UPDATE list) or in
_relink_null_round_ids's own detection UNION query. A NULL or wrong
round_id in any of these three tables is never found, and never fixed, by
the periodic cron. These tests pin today's gap so L3's fanout-extension fix
has an exact, provable target — and so a future accidental removal of the
extension (once added) trips a test immediately.
"""
from __future__ import annotations

import importlib

import pytest

from bot.cogs.proximity_cog import ProximityCog

relinker = importlib.import_module("bot.cogs.proximity_mixins.relinker_mixin")

_CURRENTLY_MISSING_TABLES = ("combat_engagement", "player_track", "lua_round_teams")


def test_fanout_table_list_currently_excludes_the_worst_offenders():
    """ProximityCog._PROXIMITY_ROUND_ID_TABLES — the fanout UPDATE list —
    does not yet include the three tables Codex §18 flagged as having the
    worst wrong-round-linkage rates."""
    for table in _CURRENTLY_MISSING_TABLES:
        assert table not in ProximityCog._PROXIMITY_ROUND_ID_TABLES, (
            f"{table} now appears in the fanout list — if this is the L3 fix "
            "landing, update/remove this lock-in test rather than deleting it blind"
        )


class _CapturingDB:
    """Captures the detection query's SQL text, then reports zero unlinked
    rows so _relink_null_round_ids returns immediately afterward."""

    def __init__(self):
        self.captured_query: str | None = None

    async def fetch_all(self, query, params=None):
        self.captured_query = " ".join(str(query).split())
        return []


class _FakeBot:
    def __init__(self, db):
        self.db_adapter = db


def _relinker():
    svc = relinker._ProximityRelinkerMixin.__new__(relinker._ProximityRelinkerMixin)
    svc._PROXIMITY_ROUND_ID_TABLES = ProximityCog._PROXIMITY_ROUND_ID_TABLES
    return svc


@pytest.mark.asyncio
async def test_detection_query_currently_excludes_the_worst_offenders():
    """The NULL/mismatch detection UNION query (tables_with_round_number)
    is a SEPARATE hardcoded list from _PROXIMITY_ROUND_ID_TABLES — must be
    checked independently. A wrong/NULL round_id in these three tables is
    currently never even detected, let alone fixed."""
    db = _CapturingDB()
    svc = _relinker()
    svc.bot = _FakeBot(db)

    await svc._relink_null_round_ids()

    assert db.captured_query is not None, "detection query was never issued"
    for table in _CURRENTLY_MISSING_TABLES:
        assert f"FROM {table} " not in db.captured_query, (
            f"{table} now appears in the detection query — if this is the "
            "L3 fix landing, update/remove this lock-in test rather than "
            "deleting it blind"
        )
