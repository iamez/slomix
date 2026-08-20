"""The match-summary branch writes a rounds row, never player rows.

The round_number = 0 "match summary" was a stored copy of the parsed R2 file
(commit ee500692, 2025). Its playtime was wrong, consumers moved to
`round_number IN (1, 2)`, and nothing has read the copy since; match totals now
come from the player_match_stats view (migration 078), which sums the stored
halves and so cannot drift.

What must NOT be lost with it: the summary's `rounds` row, which carries the
match's winner/outcome metadata and IS read (scripts/repair_round_winner_outcome).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bot.services.stats_import_mixin import _StatsImportMixin  # noqa: E402


class _FakeAdapter:
    """Records every statement; answers just enough to walk the import path."""

    def __init__(self):
        self.queries: list[str] = []

    async def fetch_all(self, query, params=None):
        self.queries.append(query)
        if "information_schema.columns" in query:
            # Column introspection: claim only the columns the mixin needs.
            return [("round_date",), ("round_time",), ("match_id",), ("map_name",),
                    ("round_number",), ("time_limit",), ("actual_time",),
                    ("winner_team",), ("defender_team",), ("round_outcome",),
                    ("gaming_session_id",)]
        return []

    async def fetch_one(self, query, params=None):
        self.queries.append(query)
        return None  # no existing round, no existing summary

    async def fetch_val(self, query, params=None):
        self.queries.append(query)
        # rounds INSERT ... RETURNING id — a new id for each insert
        return 100 + sum(1 for q in self.queries if "INSERT INTO rounds" in q)

    async def execute(self, query, params=None):
        self.queries.append(query)
        return None


class _Harness(_StatsImportMixin):
    """Minimal host object: the mixin's collaborators stubbed to no-ops."""

    def __init__(self):
        self.db_adapter = _FakeAdapter()
        self.config = type("C", (), {})()
        self.file_tracker = None
        self.round_publisher = None
        self.correlation_service = None
        self.team_manager = None
        self.inserted_player_rows: list[int] = []

    async def _calculate_gaming_session_id(self, *_a, **_k):
        return 1

    async def _insert_player_stats(self, round_id, *_a, **_k):
        self.inserted_player_rows.append(round_id)

    async def _handle_team_tracking(self, *_a, **_k):
        return None

    async def _update_player_alias(self, *_a, **_k):
        return None

    async def _resolve_round_correlation_context(self, *_a, **_k):
        return {}

    def get_channel(self, *_a, **_k):
        return None


def _stats_data():
    """An R2 parse result carrying its match summary, as the parser emits it."""
    player = {"guid": "AAAA1111", "name": "vid", "kills": 5, "deaths": 3}
    return {
        "map_name": "supply",
        "round_num": 2,
        "players": [player],
        "winner_team": 1,
        "defender_team": 2,
        "actual_time": "9:12",
        "map_time": "12:00",
        "r1_filename": "2026-08-19-210000-supply-round-1.txt",
        "match_summary": {
            "map_name": "supply",
            "round_num": 0,
            "players": [player],
            "winner_team": 1,
            "defender_team": 2,
            "actual_time": "9:12",
            "map_time": "12:00",
        },
    }


@pytest.mark.asyncio
async def test_summary_gets_a_rounds_row_but_no_player_rows():
    host = _Harness()
    await host._import_stats_to_db(_stats_data(), "2026-08-19-211000-supply-round-2.txt")

    rounds_inserts = [q for q in host.db_adapter.queries if "INSERT INTO rounds" in q]
    assert len(rounds_inserts) == 2, (
        "expected two rounds rows — the R2 round and its match summary; the "
        "summary row carries winner/outcome metadata that IS read"
    )

    # Player rows land on the R2 round only. The summary round id is the second
    # one handed out, so its presence here would mean R0 player rows are back.
    assert host.inserted_player_rows, "the R2 round got no player rows at all"
    assert len(set(host.inserted_player_rows)) == 1, (
        "player rows were written for more than one round — the match summary "
        "is being duplicated into player_comprehensive_stats again"
    )
