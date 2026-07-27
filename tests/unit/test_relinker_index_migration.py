"""Schema contract for the relinker's round_id IS NULL discovery legs."""

import re
from pathlib import Path

_MISSING_INDEX_TABLES = {
    "proximity_carrier_event",
    "proximity_carrier_kill",
    "proximity_carrier_return",
    "proximity_combat_position",
    "proximity_construction_event",
    "proximity_escort_credit",
    "proximity_focus_fire",
    "proximity_hit_region",
    "proximity_kill_outcome",
    "proximity_objective_run",
    "proximity_revive",
    "proximity_vehicle_progress",
    "proximity_weapon_accuracy",
}


def _indexed_tables(sql: str) -> set[str]:
    return set(re.findall(
        r"ON\s+(proximity_[a-z_]+)\s*\([^;]+?\)\s*WHERE\s+round_id\s+IS\s+NULL",
        sql,
        flags=re.IGNORECASE | re.DOTALL,
    ))


def test_migration_adds_every_missing_partial_index():
    sql = Path("migrations/068_add_relinker_unlinked_indexes.sql").read_text()
    assert _indexed_tables(sql) == _MISSING_INDEX_TABLES


def test_bootstrap_schema_carries_every_new_partial_index():
    sql = Path("tools/schema_postgresql.sql").read_text()
    assert _indexed_tables(sql) >= _MISSING_INDEX_TABLES
