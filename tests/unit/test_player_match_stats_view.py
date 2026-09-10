"""player_match_stats (migration 078) — the gates it must carry, and the sum it must equal.

Two layers, same split as the plausibility-audit suite:
1. the migration text itself is well-formed — pure file reading, always runs;
2. the view in a live database returns exactly what the hand-rolled per-match
   GROUP BY returned — skipped cleanly when no database is reachable.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.data_plausibility_audit import get_connection  # noqa: E402

MIGRATION = _REPO_ROOT / "migrations" / "078_player_match_stats_view.sql"

# The hand-rolled query records_awards.py ran before the view existed. It is
# the behaviour contract: the view may be tidier, never different.
LEGACY_SUM_SQL = """
    SELECT r.match_id, pcs.player_guid,
           SUM(pcs.damage_given), SUM(pcs.kills), SUM(pcs.xp),
           SUM(pcs.gibs), SUM(pcs.revives_given), SUM(pcs.headshots),
           SUM(pcs.time_played_seconds)
    FROM player_comprehensive_stats pcs
    JOIN rounds r ON r.id = pcs.round_id
    WHERE pcs.round_number IN (1, 2)
      AND pcs.time_played_seconds > 0
      AND r.is_valid IS DISTINCT FROM FALSE
      AND r.round_status IS DISTINCT FROM 'orphan_r2'
      AND r.match_id IS NOT NULL
    GROUP BY r.match_id, pcs.player_guid
"""

VIEW_SUM_SQL = """
    SELECT match_id, player_guid,
           damage_given, kills, xp, gibs, revives_given, headshots,
           time_played_seconds
    FROM player_match_stats
"""


def _migration_text() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_exists_and_is_idempotent():
    """Re-running a migration must not fail the ledger's replay."""
    sql = _migration_text()
    assert "CREATE OR REPLACE VIEW player_match_stats" in sql


def test_view_carries_the_structural_gates():
    """These four are what keep a record from being built on a doubled or
    invalid row — the same gates records_awards.py used to spell out inline."""
    sql = _migration_text()
    for gate in (
        "pcs.round_number IN (1, 2)",
        "pcs.time_played_seconds > 0",
        "r.is_valid IS DISTINCT FROM FALSE",
        "r.round_status IS DISTINCT FROM 'orphan_r2'",
    ):
        assert gate in sql, f"view lost its {gate!r} gate"


def test_view_leaves_bot_policy_to_callers():
    """Baking the [BOT]/OMNIBOT filter in would make the view useless for the
    bot-round diagnostics that need exactly those rows. Checked as PREDICATES,
    not as words — the header prose explains this policy and would otherwise
    trip the assertion."""
    sql = _migration_text()
    assert "NOT LIKE '[BOT]" not in sql
    assert "NOT LIKE 'OMNIBOT" not in sql


def test_grants_are_role_guarded():
    """A fresh CI database has etlegacy_user but not website_app; an
    unguarded GRANT would abort the whole migration there."""
    sql = _migration_text()
    assert "pg_roles" in sql and "website_app" in sql


# ── DB-dependent: the view must equal the query it replaced ────────────────


@pytest.fixture(scope="module")
def db_conn():
    try:
        conn = get_connection()
    except (Exception, SystemExit):
        pytest.skip("Database unreachable — skipping DB-dependent view tests")
    yield conn
    conn.close()


def test_view_equals_the_query_it_replaced(db_conn):
    """Row-for-row, column-for-column. A single differing row means a record
    on the site changed value the day the view went live."""
    with db_conn.cursor() as cur:
        cur.execute(LEGACY_SUM_SQL)
        legacy = {(r[0], r[1]): tuple(r[2:]) for r in cur.fetchall()}
        cur.execute(VIEW_SUM_SQL)
        view = {(r[0], r[1]): tuple(r[2:]) for r in cur.fetchall()}

    if not legacy:
        pytest.skip("No match rows in this database — nothing to compare")

    assert set(view) == set(legacy), (
        f"match/player keys differ: {len(set(view) ^ set(legacy))} unmatched"
    )
    differing = [k for k in legacy if view[k] != legacy[k]]
    assert not differing, f"{len(differing)} rows differ, e.g. {differing[:3]}"


def test_view_reports_how_many_halves_a_row_covers(db_conn):
    """`halves` is what lets a caller demand a complete match; a value outside
    1..2 would mean the grouping key is wrong (two matches folded into one)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT MIN(halves), MAX(halves) FROM player_match_stats")
        low, high = cur.fetchone()
    if low is None:
        pytest.skip("No match rows in this database")
    assert low >= 1
    assert high <= 2, "a row covers more than two halves — match_id is not unique per match"
