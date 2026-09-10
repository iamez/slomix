"""Two code paths INSERT into player_comprehensive_stats. They must not
silently disagree about which columns they write.

Why this guard exists
---------------------
`postgresql_database_manager.py` omitted `time_played_percent` from its
column list. That path is the live one (`ultimate_bot.py` ->
`PostgreSQLDatabaseManager.process_file`), so from the 2026-03-24 session
onward every row got the schema DEFAULT 0 for that column -- 100% of rows,
for five months, with nothing failing.

The damage was not the column itself. `sessions_router` computes
`survival_rate` engine-first from `time_played_percent` and falls back to
dead-time when it is missing, so the fallback silently became the only
path for `survivability`, `aggression`, `discipline_score` and `alive_pct`.
Worse, `alive_pct_drift` -- the check that compares the two sources against
each other -- can only fire when both exist, so the one guard that would
have reported this was disabled by the very bug it was meant to catch.

The omission ran in BOTH directions: the mixin does not write
`full_selfkills`, which the manager does. A difference is therefore not
automatically a bug, but it must be a *decision* someone wrote down, not an
accident nobody measured. New divergence fails this test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

TABLE = "player_comprehensive_stats"

# Columns one writer emits and the other does not, each with the reason it is
# allowed to differ. Adding an entry here is a deliberate act; leaving one out
# is what this test is for.
ACCEPTED_DIFFERENCES = {
    "full_selfkills": (
        "Only postgresql_database_manager writes it. The mixin predates the "
        "column and is not the live import path; see docs/KNOWN_ISSUES.md."
    ),
}

# The two paths that can actually write to the current schema.
#
# `tools/simple_bulk_import.py` also contains an INSERT into this table and is
# deliberately NOT listed: its column list starts `session_id, session_date`,
# and neither column exists on player_comprehensive_stats (the table has
# `round_id`, `round_date`). That INSERT cannot execute against the current
# schema at all, so comparing its columns would report noise, not a defect.
# If that file is ever revived, add it here rather than leaving it unchecked.
WRITERS = {
    "postgresql_database_manager": "postgresql_database_manager.py",
    "stats_import_mixin": "bot/services/stats_import_mixin.py",
}


def _extract_insert(source: str) -> tuple[list[str], int]:
    """Return (column names, placeholder count) for the INSERT into TABLE.

    Reads the SQL text itself rather than grepping the file, so a column name
    that only appears in a comment or docstring cannot satisfy this guard.
    """
    marker = f"INSERT INTO {TABLE}"
    start = source.index(marker)
    tail = source[start:]

    open_paren = tail.index("(")
    close = tail.index(") VALUES (")
    columns = [
        col.strip()
        for col in tail[open_paren + 1 : close].replace("\n", " ").split(",")
        if col.strip()
    ]

    values_start = close + len(") VALUES (")
    values_end = tail.index(")", values_start)
    values = tail[values_start:values_end]
    # asyncpg uses $1..$n, the adapter path uses ?
    placeholders = len(re.findall(r"\$\d+", values)) or values.count("?")

    return columns, placeholders


def _columns_for(rel_path: str) -> tuple[list[str], int]:
    return _extract_insert((REPO_ROOT / rel_path).read_text(encoding="utf-8"))


@pytest.mark.parametrize("writer,rel_path", sorted(WRITERS.items()))
def test_each_writer_lists_as_many_placeholders_as_columns(writer, rel_path):
    """A column list longer than its placeholder list is a runtime error that
    no unit test would otherwise reach -- the INSERT only runs against a live
    database."""
    columns, placeholders = _columns_for(rel_path)
    assert columns, f"{writer}: no column list parsed -- the extractor is broken"
    assert len(columns) == placeholders, (
        f"{writer} ({rel_path}) writes {len(columns)} columns but supplies "
        f"{placeholders} placeholders"
    )


def test_both_writers_agree_on_which_columns_they_write():
    manager_cols, _ = _columns_for(WRITERS["postgresql_database_manager"])
    mixin_cols, _ = _columns_for(WRITERS["stats_import_mixin"])

    difference = set(manager_cols) ^ set(mixin_cols)
    undocumented = difference - set(ACCEPTED_DIFFERENCES)

    assert not undocumented, (
        "These columns are written by one import path and not the other, with "
        "no recorded reason: " + ", ".join(sorted(undocumented)) + ". "
        "Rows created by the path that omits a column get the schema DEFAULT "
        "instead, which reads as real data. Either write the column in both "
        "paths, or add it to ACCEPTED_DIFFERENCES with the reason."
    )

    stale = set(ACCEPTED_DIFFERENCES) - difference
    assert not stale, (
        "ACCEPTED_DIFFERENCES still excuses columns that no longer differ: "
        + ", ".join(sorted(stale))
        + ". Remove them so the list keeps meaning something."
    )


def test_the_column_this_guard_was_written_for_is_present_in_both():
    """`time_played_percent` is the specific omission that went unnoticed for
    five months. Pin it by name so a future refactor cannot quietly drop it
    again and satisfy the symmetric-difference check by removing it twice."""
    for writer, rel_path in WRITERS.items():
        columns, _ = _columns_for(rel_path)
        assert "time_played_percent" in columns, (
            f"{writer} ({rel_path}) does not write time_played_percent; rows it "
            "creates will carry the schema DEFAULT 0, which disables "
            "alive_pct_engine and with it the alive_pct_drift check"
        )
