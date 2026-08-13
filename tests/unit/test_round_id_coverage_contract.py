"""Schema-driven round_id linkage coverage contract (FIX 9).

Every repair list the relinker machinery uses — the detection UNION
(`relinker_mixin._DETECTION_TABLES`), the fanout UPDATE allowlist
(`ProximityCog._PROXIMITY_ROUND_ID_TABLES`) and the wrong-link inventory
(`LINKAGE_INVENTORY_TABLES`) — is a hand-typed constant. That is how
`proximity_shot_fired` sat in no list for three months (59k orphan rows),
and how the four v7 tables (`aim_lock`, `comm_event`, `skill_snapshot`,
`spawn_select`) sat in no list for five (measured 2026-08-11: ~2.9k orphan
rows across the four on dev, 425 from a single test session).

This contract derives the ground truth from the schema instead: every table
in `tools/schema_postgresql.sql` that carries a `round_id` column must be

  * in the generic detection/fanout/inventory lists (tables with the full
    four-column round identity: map_name, round_number, round_start_unix,
    session_date), or
  * special-cased with dedicated SQL (`_SPECIAL_CASE_TABLES` —
    lua_round_teams / lua_spawn_stats), or
  * explicitly exempted WITH A REASON (`_DETECTION_EXEMPT_TABLES`).

Adding a round_id table to the schema without deciding its coverage fails
this test. The canary test proves the failure mode actually fires.

Why the schema dump and not information_schema: this contract must run on
every CI box, DB or not. The dump IS the information_schema transitively —
tests/integration/test_fresh_bootstrap_parity.py proves on the CI PostgreSQL
that a database bootstrapped from this dump plus every committed migration
is presence-identical to the dump alone, so a round_id column that exists in
a real database but not here is already a failure of THAT contract.
"""
# ruff: noqa: SLF001

from __future__ import annotations

import re
from pathlib import Path

from bot.cogs.proximity_cog import ProximityCog
from bot.cogs.proximity_mixins.relinker_mixin import (
    _DETECTION_EXEMPT_TABLES,
    _DETECTION_TABLES,
    _SPECIAL_CASE_TABLES,
)
from bot.services.linkage_inventory_service import LINKAGE_INVENTORY_TABLES

_DUMP = Path("tools/schema_postgresql.sql")

# The four columns the generic detection legs and relink templates key on.
_IDENTITY_COLUMNS = frozenset(
    {"map_name", "round_number", "round_start_unix", "session_date"}
)

# Tokens that start a table-level constraint line, not a column definition.
_NON_COLUMN_TOKENS = frozenset(
    {"constraint", "primary", "foreign", "unique", "check", "like", "exclude"}
)

_CREATE_TABLE_RE = re.compile(
    r"^CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?(\w+) \(\n(.*?)^\);",
    re.MULTILINE | re.DOTALL,
)
# The dump re-applies migration 045/066's drops at the end so its NET effect
# matches the migrated schema — tables dropped there must not count.
_DROP_TABLE_RE = re.compile(
    r"^DROP TABLE IF EXISTS (?:public\.)?(\w+)", re.MULTILINE
)


def _parse_tables(sql: str) -> dict[str, set[str]]:
    """table name -> set of column names, net of trailing DROPs."""
    tables: dict[str, set[str]] = {}
    for name, body in _CREATE_TABLE_RE.findall(sql):
        columns: set[str] = set()
        for line in body.splitlines():
            token_match = re.match(r"\s*([a-z_][a-z0-9_]*)\b", line)
            if not token_match:
                continue
            token = token_match.group(1)
            if token in _NON_COLUMN_TOKENS:
                continue
            columns.add(token)
        tables[name] = columns
    for dropped in _DROP_TABLE_RE.findall(sql):
        tables.pop(dropped, None)
    return tables


def _uncovered_round_id_tables(tables: dict[str, set[str]]) -> set[str]:
    """The actual contract: round_id tables with no coverage decision."""
    round_id_tables = {t for t, cols in tables.items() if "round_id" in cols}
    covered = (
        set(_DETECTION_TABLES)
        | set(_SPECIAL_CASE_TABLES)
        | set(_DETECTION_EXEMPT_TABLES)
    )
    return round_id_tables - covered


def _dump_tables() -> dict[str, set[str]]:
    return _parse_tables(_DUMP.read_text(encoding="utf-8"))


def test_dump_parser_actually_sees_the_schema():
    """Guard the guard: if the dump format changes and the parser goes
    blind, every other test here would pass vacuously."""
    tables = _dump_tables()
    assert len(tables) > 80, f"parser found only {len(tables)} tables"
    assert "rounds" in tables
    assert "round_id" in tables["proximity_kill_outcome"]
    assert _IDENTITY_COLUMNS.issubset(tables["proximity_kill_outcome"])
    # 045/066 drop these at the end of the dump; net schema must not have them
    assert "voice_members" not in tables


def test_every_round_id_table_is_covered_or_explicitly_exempt():
    uncovered = _uncovered_round_id_tables(_dump_tables())
    assert not uncovered, (
        "tables with a round_id column that no relinker list covers and no "
        f"exemption explains: {sorted(uncovered)}. Add each to "
        "_DETECTION_TABLES + ProximityCog._PROXIMITY_ROUND_ID_TABLES + "
        "LINKAGE_INVENTORY_TABLES (plus a *_round_lookup_unlinked partial "
        "index in a NEW migration), or to _DETECTION_EXEMPT_TABLES with a "
        "reason."
    )


def test_canary_a_new_round_id_table_fails_the_contract():
    """Prove the contract can fail: a fictional round_id table that is in
    no list must be reported. If this stops failing for the fake table, the
    contract has gone blind and protects nothing."""
    tables = _dump_tables()
    tables["proximity_fictional_canary"] = {"id", "round_id", *_IDENTITY_COLUMNS}
    assert _uncovered_round_id_tables(tables) == {"proximity_fictional_canary"}


def test_no_phantom_names_in_any_coverage_list():
    """A typo'd or renamed table in a coverage list would silently cover
    nothing while looking covered."""
    tables = _dump_tables()
    for list_name, entries in (
        ("_DETECTION_TABLES", _DETECTION_TABLES),
        ("_SPECIAL_CASE_TABLES", _SPECIAL_CASE_TABLES),
        ("_DETECTION_EXEMPT_TABLES", tuple(_DETECTION_EXEMPT_TABLES)),
        ("LINKAGE_INVENTORY_TABLES", LINKAGE_INVENTORY_TABLES),
        (
            "ProximityCog._PROXIMITY_ROUND_ID_TABLES",
            tuple(ProximityCog._PROXIMITY_ROUND_ID_TABLES),
        ),
    ):
        phantoms = set(entries) - set(tables)
        assert not phantoms, f"{list_name} names unknown tables: {sorted(phantoms)}"


def test_full_identity_tables_are_in_every_repair_list():
    """A table with the full four-column identity has everything the
    generic legs need — leaving it out of any one list recreates the
    shot_fired hole (measured but never repaired, or repaired but never
    detected)."""
    tables = _dump_tables()
    generic = {
        t
        for t, cols in tables.items()
        if "round_id" in cols
        and _IDENTITY_COLUMNS.issubset(cols)
        and t not in _SPECIAL_CASE_TABLES
        and t not in _DETECTION_EXEMPT_TABLES
    }
    assert generic, "no generic-identity tables found — parser broken?"
    missing_detection = generic - set(_DETECTION_TABLES)
    missing_fanout = generic - set(ProximityCog._PROXIMITY_ROUND_ID_TABLES)
    missing_inventory = generic - set(LINKAGE_INVENTORY_TABLES)
    assert not missing_detection, f"detected never: {sorted(missing_detection)}"
    assert not missing_fanout, f"never updated: {sorted(missing_fanout)}"
    assert not missing_inventory, f"never measured: {sorted(missing_inventory)}"


def test_exemptions_are_earned_not_convenient():
    """A table with the full identity CAN be covered generically, so an
    exemption for one is a decision to leave repairable rows broken — that
    must not be expressible here. Exemptions are for tables the generic leg
    shape cannot serve, and each must carry a non-empty reason."""
    tables = _dump_tables()
    for table, reason in _DETECTION_EXEMPT_TABLES.items():
        assert reason and reason.strip(), f"{table} exempted without a reason"
        assert not _IDENTITY_COLUMNS.issubset(tables.get(table, set())), (
            f"{table} carries the full round identity and belongs in the "
            "generic lists, not in the exemptions"
        )


def test_every_generic_detection_table_has_an_unlinked_partial_index():
    """The discovery legs run every five minutes over every detection
    table. Migrations 014/068/069/071 gave each one a partial index WHERE
    round_id IS NULL; a table added to the detection UNION without one
    reintroduces the five-minute full-table scan that 068 removed
    (relinker went 3.1-4.4s -> 19ms). The dump must carry the index so
    fresh bootstraps get it too (bootstrap-parity contract)."""
    sql = _DUMP.read_text(encoding="utf-8")
    indexed = {
        m.group(1)
        for m in re.finditer(
            r"ON\s+(?:public\.)?(\w+)\s+(?:USING\s+btree\s*)?\([^;]*?\)\s*"
            r"WHERE\s*\(?\s*round_id\s+IS\s+NULL",
            sql,
            flags=re.IGNORECASE | re.DOTALL,
        )
    }
    unindexed = set(_DETECTION_TABLES) - indexed
    assert not unindexed, (
        f"detection tables without a round_id IS NULL partial index in the "
        f"dump: {sorted(unindexed)} — add the index via a NEW migration and "
        f"mirror it in tools/schema_postgresql.sql"
    )
