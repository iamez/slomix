"""⛔ A QUERY THAT ALWAYS RAISES LOOKS EXACTLY LIKE A QUERY WITH NO DATA.

`/api/seasons/current/leaders` returned `longest_session: null` for as long as
the defect existed. Not an error, not a 500 — a 200 with a null field, which the
page renders as "nothing to show". The cause: the per-player bot/validity guard
(`player_name NOT LIKE '[BOT]%'`, `player_guid NOT LIKE 'OMNIBOT%'`, and a
subquery correlating on `player_comprehensive_stats.round_id`) had been copied
onto a query that reads `FROM rounds`. `rounds` has none of those columns, so
asyncpg raised UndefinedColumnError on every call, and the caller's
`except Exception: return None` turned that into "no data".

Found by reading the log after a restart, not by a test — because no test asked
whether the value was ever non-null.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROUTER = (Path(__file__).resolve().parents[2]
          / "website" / "backend" / "routers" / "records_seasons.py")

#: Columns that live on `player_comprehensive_stats` and NOT on `rounds`.
PLAYER_ONLY_COLUMNS = ("player_name", "player_guid")


def _session_query() -> str:
    match = re.search(r'session_query = """(.*?)"""', ROUTER.read_text(), re.S)
    assert match, "session_query no longer exists under that name"
    return match.group(1)


def test_the_longest_session_query_reads_rounds():
    assert re.search(r"FROM\s+rounds", _session_query())


@pytest.mark.parametrize("column", PLAYER_ONLY_COLUMNS)
def test_it_does_not_filter_on_columns_rounds_does_not_have(column):
    """The exact defect: a per-player guard on a per-round query."""
    query = _session_query()
    assert not re.search(rf"\b{column}\b(?!s)", query), (
        f"`{column}` is a player_comprehensive_stats column and this query "
        f"reads FROM rounds — asyncpg raises, the caller swallows it, and the "
        f"endpoint answers 200 with a null field")


def test_it_does_not_correlate_on_a_table_it_never_selects():
    query = _session_query()
    if "player_comprehensive_stats." in query:
        assert re.search(r"(FROM|JOIN)\s+player_comprehensive_stats", query), (
            "the query correlates on player_comprehensive_stats without "
            "selecting from it")


def test_the_validity_guard_is_still_present():
    """Removing the broken filter must not remove the filtering.

    The old copy did carry a real intent — exclude invalid and orphaned rounds.
    Expressed against `rounds` it is `is_valid` / `round_status`; dropping it
    would trade a silent null for a silently wrong winner.
    """
    query = _session_query()
    assert "is_valid" in query, "validity guard lost"
    assert "orphan_r2" in query, "orphan guard lost"
    assert "is_bot_round" in query, "bot rounds are no longer excluded"


def test_the_session_is_grouped_and_bounded():
    query = _session_query()
    assert "GROUP BY gaming_session_id" in query
    assert "gaming_session_id IS NOT NULL" in query, (
        "NULL sessions would group into one phantom row")
