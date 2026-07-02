"""Guard: the inline bootstrap DDL in postgresql_database_manager must not drift
from the canonical tools/schema_postgresql.sql.

`_create_schema_if_missing` inline-creates ~24 core tables so an empty dev DB can
be bootstrapped without the full .sql. tools/schema_postgresql.sql (regenerated
from the live DB) is the single source of truth. When a migration adds a column to
one of those tables, the .sql picks it up on the next regen — but the inline DDL is
easy to forget, so a fresh bootstrap silently ends up missing columns.

This test parses both and asserts that, for every table the inline DDL defines, its
column set matches the .sql exactly — so the two can't diverge unnoticed.
"""
import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SCHEMA_SQL = _REPO / "tools" / "schema_postgresql.sql"
_MANAGER = _REPO / "postgresql_database_manager.py"

_CREATE_RE = re.compile(
    r"CREATE TABLE (?:IF NOT EXISTS )?(?:public\.)?(\w+)\s*\((.*?)\n\s*\)[;\s]",
    re.DOTALL | re.IGNORECASE,
)
_CONSTRAINT_RE = re.compile(
    r"(PRIMARY KEY|FOREIGN KEY|UNIQUE|CONSTRAINT|CHECK)\b", re.IGNORECASE
)


def _create_schema_block(manager_text: str) -> str:
    """Slice out just the _create_schema_if_missing method body, so migration-time
    CREATE TABLE DDL elsewhere in the file (e.g. a second achievement_notification_
    ledger inside _migrate_schema_if_needed) can't shadow or mask the bootstrap defs."""
    start = manager_text.index("async def _create_schema_if_missing")
    # end at the next method definition at the same (4-space) indentation
    nxt = re.search(r"\n    async def (?!_create_schema_if_missing)\w", manager_text[start + 1:])
    end = start + 1 + nxt.start() if nxt else len(manager_text)
    return manager_text[start:end]


def _tables_with_columns(text: str) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    for m in _CREATE_RE.finditer(text):
        name = m.group(1).lower()
        cols: set[str] = set()
        for raw in m.group(2).split("\n"):
            line = raw.strip().rstrip(",")
            if not line or line.startswith("--"):
                continue
            if _CONSTRAINT_RE.match(line):
                continue
            col = re.match(r'"?(\w+)"?\s', line)
            if col:
                cols.add(col.group(1).lower())
        tables[name] = cols
    return tables


def test_inline_ddl_matches_canonical_schema():
    schema = _tables_with_columns(_SCHEMA_SQL.read_text())
    inline = _tables_with_columns(_create_schema_block(_MANAGER.read_text()))

    # Sanity: a known core table must be parsed on both sides with its columns
    # (guards against a parser/format regression without a brittle count threshold).
    for side, tables in (("schema.sql", schema), ("inline DDL", inline)):
        assert "rounds" in tables and "round_canonical_id" in tables["rounds"], (
            f"{side} parse looks wrong: 'rounds' not parsed with expected columns"
        )

    problems: list[str] = []
    for table, inline_cols in sorted(inline.items()):
        if table not in schema:
            problems.append(f"{table}: defined inline but missing from schema_postgresql.sql")
            continue
        schema_cols = schema[table]
        missing = schema_cols - inline_cols  # in canonical, not in bootstrap
        extra = inline_cols - schema_cols    # in bootstrap, not in canonical
        if missing:
            problems.append(
                f"{table}: inline DDL missing columns present in schema.sql "
                f"(add them to _create_schema_if_missing): {sorted(missing)}"
            )
        if extra:
            problems.append(
                f"{table}: inline DDL has columns not in schema.sql "
                f"(stale bootstrap or missing schema regen): {sorted(extra)}"
            )

    assert not problems, "Inline bootstrap DDL drifted from schema_postgresql.sql:\n" + "\n".join(problems)
