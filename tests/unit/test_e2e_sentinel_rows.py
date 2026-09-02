"""scripts/e2e_sentinel_rows.py — the dev-DB rows behind the e2e sentinel.

No database here: the script's two constants ARE its contract. Every insert
must be idempotent (ON CONFLICT DO NOTHING), every statement must address
the sentinel id and nothing else, and the delete order must respect the one
FK chain the sentinel has (user_points -> website_users)."""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "e2e_sentinel_rows.py"


def _load():
    spec = importlib.util.spec_from_file_location("e2e_sentinel_rows", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_sentinel_id_is_negative_and_cannot_be_a_real_account():
    mod = _load()
    assert mod.SENTINEL_ID < 0


def test_every_insert_is_idempotent_and_targets_the_sentinel():
    mod = _load()
    for table, sql, params in mod.INSERTS:
        assert "ON CONFLICT" in sql and "DO NOTHING" in sql, table
        assert sql.startswith(f"INSERT INTO {table} ")
        assert params[0] == mod.SENTINEL_ID, f"{table}: first bound value must be the sentinel id"


def test_remove_order_deletes_fk_dependents_before_website_users():
    mod = _load()
    tables = [t for t, _ in mod.SENTINEL_TABLES]
    assert tables[-1] == "website_users", "the FK target goes last"
    assert tables.index("user_points") < tables.index("website_users")
    assert tables.index("parimutuel_bets") < tables.index("website_users")
    # Each insert target is also removable.
    for table, _sql, _params in mod.INSERTS:
        assert table in tables


def test_statements_bind_the_id_never_inline_it():
    """Both the count and the delete loops bind %s; the only literal number
    in the SQL surface is the sentinel constant itself."""
    text = SCRIPT.read_text(encoding="utf-8")
    for stmt in re.findall(r'cur\.execute\((f?"[^"]+")', text):
        assert "%s" in stmt, stmt
        assert not re.search(r"= -?\d", stmt), f"inlined id in {stmt}"


def test_production_guard_present():
    text = SCRIPT.read_text(encoding="utf-8")
    assert 'os.getenv("ENVIRONMENT", "").lower() == "production"' in text
