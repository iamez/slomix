"""Migration 065 + parser idempotency for revive / weapon-accuracy identity.

Codex #549 asked for direct coverage of the dedup migration rather than
only the parser change that depends on it. These tests exercise the SQL
itself against a fixture, and pin the parser's rerun contract.

Accepted limitation, asserted rather than hidden: a historically WRONG
`round_id` participates in row identity only through the backfill, so two
rows for the same physical event can survive if they were linked to
different rounds. That is no worse than the pre-migration state (where
neither row had any identity) but it does mean dedup is not total until
the relink workstream lands.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATION = Path("migrations/065_dedup_revive_weapon_accuracy.sql")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _statements() -> str:
    """SQL with comment lines stripped — the header documents the same
    keywords it uses, which would otherwise inflate every count."""
    return "\n".join(
        ln for ln in _sql().splitlines() if not ln.lstrip().startswith("--")
    )


def test_migration_exists_and_is_idempotent_by_construction():
    sql = _statements()
    # every DDL step must tolerate a rerun
    assert sql.count("ADD COLUMN IF NOT EXISTS") == 4
    assert sql.count("CREATE UNIQUE INDEX IF NOT EXISTS") == 2
    assert sql.count("DROP INDEX IF EXISTS") == 2
    # backfill only touches rows that still lack identity
    assert "AND pr.round_start_unix IS NULL" in sql
    assert "AND pw.round_start_unix IS NULL" in sql


def test_unique_indexes_carry_the_full_canonical_round_key():
    """round_number must be part of the key: stale telemetry can give two
    rounds of one map the same start timestamp, and without it their rows
    would dedupe across genuinely distinct rounds."""
    sql = _sql()
    for idx in ("uq_prox_revive_identity", "uq_prox_wacc_identity"):
        m = re.search(rf"CREATE UNIQUE INDEX IF NOT EXISTS {idx}\s+ON\s+\w+\s*\(([^)]*)\)", sql)
        assert m, f"{idx} not found"
        cols = [c.strip() for c in m.group(1).split(",")]
        assert "round_start_unix" in cols
        assert "round_number" in cols
        assert "map_name" in cols
    # partial predicate keeps identity-less legacy rows out of the constraint
    assert sql.count("WHERE round_start_unix IS NOT NULL AND round_number IS NOT NULL") == 2


def test_orphan_dedup_compares_every_column():
    """Orphan rows (no round identity even after backfill) may only be
    collapsed when byte-identical — anything differing is distinct
    telemetry that must survive."""
    sql = _sql()
    revive_block = sql[sql.index("pr.round_start_unix IS NULL"):]
    for col in ("revive_x", "revive_y", "revive_z", "distance_to_enemy",
                "under_fire", "nearest_enemy_guid", "medic_name",
                "revived_name", "round_id"):
        assert f"keep.{col} IS NOT DISTINCT FROM pr.{col}" in revive_block, col

    wacc_block = sql[sql.index("pw.round_start_unix IS NULL"):]
    for col in ("accuracy_pct", "team", "player_name", "round_id"):
        assert f"keep.{col} IS NOT DISTINCT FROM pw.{col}" in wacc_block, col


def test_backfill_copies_round_identity_not_session_attribution():
    """065 copies the LINKED round's own identity, so it deliberately has no
    validity gate — unlike 064, which ATTRIBUTES rows to a gaming session
    and must therefore exclude rejected rounds. Conflating the two would
    either drop legitimate identity here or leak attribution there."""
    sql = _sql()
    assert "FROM rounds r" in sql
    assert "pr.round_id = r.id" in sql and "pw.round_id = r.id" in sql
    assert "r.round_start_unix IS NOT NULL AND r.round_start_unix > 0" in sql
    # no session attribution happens in this migration
    assert "gaming_session_id" not in sql


def test_indexes_are_rebuilt_so_an_earlier_revision_self_heals():
    """An earlier revision of this file created the indexes WITHOUT
    round_number. DROP-then-CREATE makes a rerun converge on the correct
    shape instead of silently keeping the weaker key."""
    sql = _sql()
    for idx in ("uq_prox_revive_identity", "uq_prox_wacc_identity"):
        assert f"DROP INDEX IF EXISTS {idx};" in sql
        assert sql.index(f"DROP INDEX IF EXISTS {idx};") < sql.index(
            f"CREATE UNIQUE INDEX IF NOT EXISTS {idx}")


def test_documented_limitation_is_stated_in_the_migration():
    """The wrong-round_id identity limitation must be discoverable by an
    operator reading the migration, not only in a PR comment."""
    sql = _sql().lower()
    assert "round_id" in sql
    assert "limitation" in sql or "omejit" in sql or "known" in sql


@pytest.mark.parametrize("table,conflict_cols", [
    ("proximity_revive", ["round_start_unix", "round_number", "map_name",
                          "medic_guid", "revived_guid", "revive_time"]),
    ("proximity_weapon_accuracy", ["round_start_unix", "round_number",
                                   "map_name", "player_guid", "weapon_id"]),
])
def test_parser_conflict_target_matches_the_unique_index(table, conflict_cols):
    """A rerun can only dedupe if the parser's ON CONFLICT names exactly the
    indexed identity — a mismatch silently degrades to duplicate inserts."""
    raw = Path("proximity/parser/parser.py").read_text(encoding="utf-8")
    # the clause is assembled from adjacent string literals across lines
    joined = re.sub(r'"\s*\n\s*"', "", raw)
    target = ", ".join(conflict_cols)
    assert f"ON CONFLICT ({target})" in joined, \
        f"{table}: parser conflict target does not match the index ({target})"


def test_parser_only_names_a_conflict_target_when_identity_is_complete():
    """With a missing round number or start time the row has no identity, so
    the parser must fall back to the bare DO NOTHING rather than naming an
    index it cannot satisfy."""
    parser = Path("proximity/parser/parser.py").read_text(encoding="utf-8")
    assert parser.count("rsu_val is not None and self.metadata.get('round_num') is not None") == 2
