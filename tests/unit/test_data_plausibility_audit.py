"""scripts/data_plausibility_audit.py — Data Trust pillar B rulebook sanity.

Two layers:
1. The rules table itself is well-formed (unique names, valid tiers/
   severities/tables) — pure Python, always runs.
2. Every rule's SQL predicate at least PARSES against the real schema
   (LIMIT 0 query) — DB-dependent, skipped cleanly when unreachable so this
   suite doesn't become a hidden DB requirement for `pytest tests/unit`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.data_plausibility_audit import (  # noqa: E402
    RULES,
    VALID_SEVERITIES,
    VALID_TABLES,
    VALID_TIERS,
    build_count_sql,
    build_split_sql,
    build_top_rows_sql,
    get_connection,
    validate_rules,
)


def test_rules_table_is_well_formed():
    """validate_rules() must accept the real RULES list as-is."""
    validate_rules(RULES)  # raises on any structural problem


def test_rule_names_are_unique():
    names = [r.name for r in RULES]
    assert len(names) == len(set(names)), "duplicate rule names in RULES"


def test_rule_tiers_and_severities_are_valid():
    for rule in RULES:
        assert rule.tier in VALID_TIERS, rule.name
        assert rule.severity in VALID_SEVERITIES, rule.name
        assert rule.table in VALID_TABLES, rule.name


def test_rule_predicates_are_nonempty_strings():
    for rule in RULES:
        assert isinstance(rule.predicate, str)
        assert rule.predicate.strip(), f"{rule.name} has an empty predicate"


def test_rounds_table_rules_never_need_round_join():
    """needs_round_join is a pcs-only concept — the rounds table is already `r`."""
    for rule in RULES:
        if rule.table == "rounds":
            assert not rule.needs_round_join, rule.name


def test_at_least_one_rule_per_table():
    tables = {r.table for r in RULES}
    assert tables == VALID_TABLES, f"expected rules covering {VALID_TABLES}, got {tables}"


def test_validate_rules_rejects_duplicate_names():
    import dataclasses

    bad = list(RULES[:2])
    bad[1] = dataclasses.replace(bad[1], name=bad[0].name)
    with pytest.raises(ValueError, match="Duplicate rule names"):
        validate_rules(bad)


def test_validate_rules_rejects_invalid_severity():
    import dataclasses

    bad = [dataclasses.replace(RULES[0], severity="apocalyptic")]
    with pytest.raises(ValueError, match="invalid severity"):
        validate_rules(bad)


def test_sql_builders_produce_nonempty_statements():
    """Cheap, DB-free check that every builder returns a SELECT for every rule."""
    for rule in RULES:
        assert build_count_sql(rule).strip().upper().startswith("SELECT COUNT(*)")
        assert build_split_sql(rule).strip().upper().startswith("SELECT")
        sql, labels = build_top_rows_sql(rule, 3)
        assert sql.strip().upper().startswith("SELECT")
        assert labels, rule.name


# ── DB-dependent: predicates must actually PARSE against the schema ────────


def _try_connect():
    # get_connection() raises SystemExit (not an Exception subclass) when the
    # POSTGRES_* env vars are absent — exactly the CI situation — so catching
    # bare Exception is not enough for the "skip cleanly without a DB" promise.
    try:
        conn = get_connection()
    except (Exception, SystemExit):
        return None
    return conn


@pytest.fixture(scope="module")
def db_conn():
    conn = _try_connect()
    if conn is None:
        pytest.skip("Database unreachable — skipping DB-dependent plausibility-audit tests")
    yield conn
    conn.close()


@pytest.mark.parametrize("rule", RULES, ids=[r.name for r in RULES])
def test_rule_predicate_parses_against_schema(db_conn, rule):
    """Run each rule's count/split/top-rows SQL as `... LIMIT 0` (no rows read,
    still forces the planner to resolve every column/cast/regex in the
    predicate). A rule that references a renamed column or a bad cast fails
    here instead of silently reporting 0 violations forever in production.
    """
    with db_conn.cursor() as cur:
        cur.execute(build_count_sql(rule))
        cur.execute(build_split_sql(rule))
        sql, _labels = build_top_rows_sql(rule, 0)  # LIMIT 0 — plan/parse only, no rows
        cur.execute(sql)
