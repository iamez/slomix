"""Tests for TeamManager pure staticmethods.

These four helpers are SQL-fragment + JSON normalisation helpers that
shape every team-detection query. They look innocuous but a regression
in any of them silently corrupts:

- session scoping (wrong session's teams returned),
- ON CONFLICT clause (failed upsert → silent data loss),
- DELETE query (cross-session deletion → ALL session teams wiped),
- JSON decode (bad input → 500 from team detection).

Pin the contract for each.
"""
from __future__ import annotations

from bot.core.team_manager import TeamManager

# ---------------------------------------------------------------------------
# _session_scope_clause: WHERE-fragment chooser
# ---------------------------------------------------------------------------


def test_session_scope_prefers_gaming_session_id_when_available():
    """When BOTH `gaming_session_id` is set AND the column exists, the
    INT id wins over the date-LIKE filter (more precise scoping)."""
    columns = {"gaming_session_id", "session_start_date"}
    clause, params = TeamManager._session_scope_clause(
        columns, session_date="2026-04-21", gaming_session_id=42,
    )
    assert clause == "gaming_session_id = ?"
    assert params == (42,)


def test_session_scope_falls_back_to_date_when_gaming_session_id_none():
    """gaming_session_id=None → use date-LIKE filter even if column exists.
    This branch supports legacy rows imported before gaming_session_id
    was introduced."""
    columns = {"gaming_session_id", "session_start_date"}
    clause, params = TeamManager._session_scope_clause(
        columns, session_date="2026-04-21", gaming_session_id=None,
    )
    assert clause == "session_start_date LIKE ?"
    assert params == ("2026-04-21%",)


def test_session_scope_falls_back_when_column_missing():
    """Old schema without gaming_session_id column → date filter."""
    columns = {"session_start_date"}  # no gaming_session_id column
    clause, params = TeamManager._session_scope_clause(
        columns, session_date="2026-04-21", gaming_session_id=42,
    )
    # gaming_session_id passed but column doesn't exist → date filter
    assert clause == "session_start_date LIKE ?"
    assert params == ("2026-04-21%",)


def test_session_scope_applies_table_alias_when_provided():
    """JOIN queries pass a table alias — must be prefixed onto column."""
    columns = {"gaming_session_id"}
    clause, params = TeamManager._session_scope_clause(
        columns, session_date="2026-04-21",
        gaming_session_id=99, table_alias="st",
    )
    assert clause == "st.gaming_session_id = ?"
    assert params == (99,)


def test_session_scope_alias_applied_to_date_branch_too():
    columns = set()
    clause, params = TeamManager._session_scope_clause(
        columns, session_date="2026-04-21",
        gaming_session_id=None, table_alias="t",
    )
    assert clause == "t.session_start_date LIKE ?"
    assert params == ("2026-04-21%",)


def test_session_scope_date_param_uses_like_wildcard():
    """The date filter must include a trailing `%` so it matches the
    full datetime in session_start_date (which may have time suffix)."""
    _, params = TeamManager._session_scope_clause(
        set(), session_date="2026-04-21", gaming_session_id=None,
    )
    assert params[0].endswith("%")


# ---------------------------------------------------------------------------
# _session_teams_conflict_clause
# ---------------------------------------------------------------------------


def test_conflict_clause_uses_named_constraint_when_session_identity_present():
    """Newer schema has a `session_teams_identity_unique` UNIQUE constraint.
    Pin so an ON CONFLICT regression doesn't silently degrade upserts to
    `WHERE` matching the wrong tuple."""
    out = TeamManager._session_teams_conflict_clause({"session_identity"})
    assert "session_teams_identity_unique" in out
    assert out.startswith("ON CONFLICT")


def test_conflict_clause_falls_back_to_legacy_columns():
    """Old schema → ON CONFLICT (date, map, team_name)."""
    out = TeamManager._session_teams_conflict_clause(set())
    assert out == "ON CONFLICT (session_start_date, map_name, team_name)"


def test_conflict_clause_legacy_when_session_identity_absent_other_cols_present():
    """Even with other cols, no session_identity → legacy fallback."""
    out = TeamManager._session_teams_conflict_clause({"gaming_session_id"})
    assert "session_teams_identity_unique" not in out
    assert out == "ON CONFLICT (session_start_date, map_name, team_name)"


# ---------------------------------------------------------------------------
# _session_delete_query
# ---------------------------------------------------------------------------


def test_delete_query_uses_gaming_session_id_when_available():
    out = TeamManager._session_delete_query(
        {"gaming_session_id"}, gaming_session_id=42, map_all_only=False,
    )
    assert "gaming_session_id = ?" in out
    assert "session_start_date" not in out


def test_delete_query_scopes_to_map_all_when_flag_set():
    """`map_all_only=True` adds `AND map_name = 'ALL'` so per-map team rows
    are preserved. Pin this — a regression that drops the AND would wipe
    all per-map teams the user explicitly named."""
    out = TeamManager._session_delete_query(
        {"gaming_session_id"}, gaming_session_id=42, map_all_only=True,
    )
    assert "map_name = 'ALL'" in out
    assert "AND" in out


def test_delete_query_no_map_filter_when_map_all_only_false():
    out = TeamManager._session_delete_query(
        {"gaming_session_id"}, gaming_session_id=42, map_all_only=False,
    )
    assert "map_name" not in out


def test_delete_query_legacy_path_when_gaming_session_id_absent():
    out = TeamManager._session_delete_query(
        {"session_start_date"}, gaming_session_id=None, map_all_only=False,
    )
    assert "session_start_date LIKE ?" in out
    assert "gaming_session_id" not in out


def test_delete_query_legacy_with_map_all_filter():
    out = TeamManager._session_delete_query(
        set(), gaming_session_id=None, map_all_only=True,
    )
    assert "session_start_date LIKE ?" in out
    assert "map_name = 'ALL'" in out


def test_delete_query_falls_back_to_date_when_gaming_session_id_none_even_if_column_present():
    """If gaming_session_id=None even with column present → date scope."""
    out = TeamManager._session_delete_query(
        {"gaming_session_id"}, gaming_session_id=None, map_all_only=False,
    )
    assert "session_start_date LIKE ?" in out


# ---------------------------------------------------------------------------
# _decode_json_array — JSONB normalisation
# ---------------------------------------------------------------------------


def test_decode_json_array_returns_empty_for_none():
    """None → [] (legacy rows with NULL roster column)."""
    assert TeamManager._decode_json_array(None) == []


def test_decode_json_array_passes_through_native_list():
    """asyncpg with JSONB native decoding returns a list directly — no
    re-decode needed."""
    src = ["guid1", "guid2"]
    out = TeamManager._decode_json_array(src)
    assert out == ["guid1", "guid2"]


def test_decode_json_array_native_list_returned_as_is():
    """The implementation returns the SAME list object when input is
    already a list (no copy). Pin so a future "always copy" change is
    visible (would break callers that mutate)."""
    src = ["a", "b"]
    out = TeamManager._decode_json_array(src)
    assert out is src


def test_decode_json_array_parses_json_string():
    """Older PostgreSQL JSON column returns a string — must be parsed."""
    out = TeamManager._decode_json_array('["alice", "bob"]')
    assert out == ["alice", "bob"]


def test_decode_json_array_parses_string_with_unicode():
    out = TeamManager._decode_json_array('["úžasen", "naložb"]')
    assert out == ["úžasen", "naložb"]


def test_decode_json_array_returns_empty_on_malformed_json():
    """Bad JSON → [] (logged warning), NOT exception. Pin fail-safe so
    a corrupt roster column doesn't crash team detection for the whole
    session."""
    out = TeamManager._decode_json_array("not valid json{")
    assert out == []


def test_decode_json_array_returns_empty_on_empty_string():
    """Empty string is invalid JSON → []."""
    out = TeamManager._decode_json_array("")
    assert out == []


def test_decode_json_array_handles_tuple_input():
    """Tuple input is converted to list (asyncpg sometimes hands back
    tuples for ARRAY columns)."""
    out = TeamManager._decode_json_array(("a", "b", "c"))
    assert out == ["a", "b", "c"]


def test_decode_json_array_returns_empty_for_unknown_type():
    """int/float/dict → falls through to the final `tuple` check which
    fails → returns []. Pin fail-safe."""
    assert TeamManager._decode_json_array(42) == []
    assert TeamManager._decode_json_array({"k": "v"}) == []
    assert TeamManager._decode_json_array(3.14) == []


def test_decode_json_array_json_string_returning_dict_normalises_to_empty():
    """A JSON string that parses to a non-list (`{"k": "v"}`) is NOT a roster.
    Pin the contract: the helper returns a list — non-list parses normalize
    to []. Callers (`get_session_teams`, etc.) immediately do `len(guids)`
    so a dict leak would crash the read path."""
    out = TeamManager._decode_json_array('{"k": "v"}')
    assert out == []


def test_decode_json_array_json_string_returning_null_normalises_to_empty():
    """JSON `null` → json.loads returns None → helper normalises to [].
    Pin the safe behaviour so a stored JSON `null` (legacy/malformed row)
    doesn't TypeError on `len(...)` downstream."""
    out = TeamManager._decode_json_array("null")
    assert out == []
