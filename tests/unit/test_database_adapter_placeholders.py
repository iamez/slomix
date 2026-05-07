"""Tests for PostgreSQLAdapter._translate_placeholders pure helper.

Every cog/service in the codebase writes SQL with `?` placeholders for
portability — the adapter rewrites them to PostgreSQL `$1, $2, …` form
before sending to asyncpg. A regression here:

- Mis-numbered placeholders → asyncpg binds wrong params → silent data
  corruption (e.g., user A's stats shown to user B).
- Off-by-one → "bind value count mismatch" runtime error.
- Quoted-string `?` accidentally rewritten → corrupt query.

Pin the contract: numbering is sequential, all `?` (even inside
strings — pin observed behaviour) get rewritten, and `?`-free queries
are returned unchanged.
"""
from __future__ import annotations

import pytest

from bot.core.database_adapter import PostgreSQLAdapter


@pytest.fixture
def adapter():
    """Build a PostgreSQLAdapter without connecting (init() doesn't open a
    pool — connect() does, and we never call it)."""
    return PostgreSQLAdapter(
        host="localhost", port=5432, database="x",
        user="y", password="z",
    )


# ---------------------------------------------------------------------------
# _translate_placeholders — pure rewrite logic
# ---------------------------------------------------------------------------


def test_no_placeholder_returns_query_unchanged(adapter):
    """Static query with no `?` → identical string returned (not a copy)."""
    q = "SELECT 1"
    assert adapter._translate_placeholders(q) == q


def test_single_placeholder_becomes_dollar_one(adapter):
    out = adapter._translate_placeholders("SELECT * FROM users WHERE id = ?")
    assert out == "SELECT * FROM users WHERE id = $1"


def test_multiple_placeholders_numbered_sequentially(adapter):
    out = adapter._translate_placeholders(
        "INSERT INTO t(a, b, c) VALUES (?, ?, ?)"
    )
    assert out == "INSERT INTO t(a, b, c) VALUES ($1, $2, $3)"


def test_placeholder_count_grows_past_nine(adapter):
    """Adapter must handle more than 9 params (some bulk-insert queries
    use 12+ columns). Pin so a regression that uses single-digit format
    is loud."""
    q = ", ".join(["?"] * 12)
    out = adapter._translate_placeholders(q)
    expected = ", ".join(f"${i}" for i in range(1, 13))
    assert out == expected
    # Sanity: $10, $11, $12 are present
    assert "$10" in out
    assert "$11" in out
    assert "$12" in out


def test_placeholders_in_complex_query(adapter):
    """Real-world-ish query with mixed clauses."""
    q = (
        "SELECT id FROM rounds "
        "WHERE map_name = ? "
        "AND round_date BETWEEN ? AND ? "
        "ORDER BY id LIMIT ?"
    )
    out = adapter._translate_placeholders(q)
    assert "map_name = $1" in out
    assert "BETWEEN $2 AND $3" in out
    assert "LIMIT $4" in out


def test_placeholders_are_distinct_per_position(adapter):
    """Same param used twice must get DIFFERENT $N — asyncpg binds by
    position, not name. A regression that reused $1 would silently
    reuse the first param value for both slots."""
    out = adapter._translate_placeholders(
        "SELECT * FROM t WHERE a = ? OR b = ?"
    )
    assert "$1" in out
    assert "$2" in out
    assert out.count("$1") == 1
    assert out.count("$2") == 1


def test_placeholder_inside_quoted_string_is_also_rewritten(adapter):
    """Pin OBSERVED behaviour: the adapter does NOT parse SQL strings,
    so `?` inside a literal is rewritten too. Callers must avoid `?`
    in string literals.

    A future hardening pass that adds quote-aware parsing would need
    to invert this test — leaving the assertion loud is the point."""
    q = "SELECT * FROM t WHERE comment = 'is this ok?' AND id = ?"
    out = adapter._translate_placeholders(q)
    # Both `?` get rewritten, ordered left-to-right
    assert "is this ok$1" in out
    assert "id = $2" in out


def test_translate_query_delegates_to_translate_placeholders(adapter):
    """Public `translate_query` is a thin wrapper. Pinned so a future
    "translate also CAST and SUBSTR" expansion doesn't accidentally
    skip the placeholder pass."""
    same_input = "SELECT ? FROM t WHERE ? = ?"
    assert adapter.translate_query(same_input) == adapter._translate_placeholders(same_input)


# ---------------------------------------------------------------------------
# _normalize_params — passthrough contract
# ---------------------------------------------------------------------------


def test_normalize_params_returns_input_unchanged(adapter):
    """Current implementation is identity — preserves date/datetime objects
    so asyncpg can bind native types. Pin so a regression that converts
    everything to str silently breaks date binding."""
    p = (1, "x", 3.14)
    assert adapter._normalize_params(p) is p


def test_normalize_params_handles_none(adapter):
    """Queries with no params pass None — must round-trip."""
    assert adapter._normalize_params(None) is None


def test_normalize_params_preserves_empty_tuple(adapter):
    out = adapter._normalize_params(())
    assert out == ()


# ---------------------------------------------------------------------------
# host:port unpacking in __init__
# ---------------------------------------------------------------------------


def test_init_splits_host_port_when_combined():
    """Some legacy configs pass `host=localhost:5432, port=5432` — the
    adapter unpacks `host:port` and re-assigns. Pin so the env-driven
    config path works for both styles."""
    a = PostgreSQLAdapter(
        host="db.internal:7777", port=5432, database="x",
        user="y", password="z",
    )
    assert a.host == "db.internal"
    assert a.port == 7777


def test_init_keeps_explicit_port_when_no_colon():
    a = PostgreSQLAdapter(
        host="db.internal", port=5432, database="x",
        user="y", password="z",
    )
    assert a.host == "db.internal"
    assert a.port == 5432


def test_init_keeps_pool_size_defaults():
    """Pool size defaults are tuned for 14 cogs + tasks — a regression
    that drops them to 1/1 would deadlock under load."""
    a = PostgreSQLAdapter(
        host="x", port=5432, database="x", user="x", password="x",
    )
    assert a.min_pool_size == 5
    assert a.max_pool_size == 20


def test_init_ssl_mode_default_disable():
    """Default SSL is disabled (matches local dev). A regression to
    'require' would break dev setups without certs."""
    a = PostgreSQLAdapter(
        host="x", port=5432, database="x", user="x", password="x",
    )
    assert a.ssl_mode == "disable"


def test_init_pool_starts_uninitialised():
    """Pool stays None until connect() — pin so a future eager-init
    refactor doesn't silently change construction-time behaviour."""
    a = PostgreSQLAdapter(
        host="x", port=5432, database="x", user="x", password="x",
    )
    assert a.pool is None
    assert a.is_connected() is False
