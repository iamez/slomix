"""Tests for round_linkage_anomaly_service helper functions.

The existing test_round_linkage_anomaly_service.py covers two
end-to-end happy/breach paths but the four pure helpers (`_safe_int`,
`_row_get`, `_normalize_thresholds`, `_build_breach`) were untested.
They are the load-bearing layer that decides whether an anomaly is
flagged — a regression in `_normalize_thresholds` that silently
clamps a threshold to 0 (or skips it) would either swamp operators
with false positives or hide real linkage drift.
"""
from __future__ import annotations

from collections import namedtuple

import pytest

from bot.services.round_linkage_anomaly_service import (
    DEFAULT_THRESHOLDS,
    _build_breach,
    _normalize_thresholds,
    _row_get,
    _safe_int,
)


# ---------------------------------------------------------------------------
# _safe_int
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value, expected", [
    (5,         5),
    ("5",       5),
    (5.7,       5),         # truncation
    (-3,        -3),
    (0,         0),
    (None,      0),         # None → 0 via `value or 0`
    ("",        0),         # falsy string → 0
    ("garbage", 0),         # ValueError → 0
    ("0",       0),
    (True,      1),         # bool inherits int → 1
    (False,     0),
])
def test_safe_int_known_values(value, expected):
    assert _safe_int(value) == expected


def test_safe_int_handles_object_without_int_conversion():
    """Arbitrary object → falls into except clause, returns 0."""
    assert _safe_int(object()) == 0


# ---------------------------------------------------------------------------
# _row_get
# ---------------------------------------------------------------------------


def test_row_get_returns_default_for_none():
    assert _row_get(None, 0, "key", default="X") == "X"
    assert _row_get(None, 0, "key") is None


def test_row_get_dict_lookup_by_key():
    row = {"key": "value", "other": 42}
    assert _row_get(row, 0, "key") == "value"
    assert _row_get(row, 0, "other") == 42


def test_row_get_dict_falls_back_to_default_when_missing():
    row = {"a": 1}
    assert _row_get(row, 0, "missing", default="default-value") == "default-value"


def test_row_get_tuple_lookup_by_index():
    """Tuple/list rows use index access only (asyncpg.Record-like rows
    use mapping access first, then index — but plain tuples lack
    string keys so the index branch wins)."""
    row = ("v0", "v1", "v2")
    assert _row_get(row, 1, "ignored_key") == "v1"


def test_row_get_list_lookup_by_index():
    row = ["v0", "v1", "v2"]
    assert _row_get(row, 2, "ignored") == "v2"


def test_row_get_falls_back_to_default_for_out_of_range():
    row = ("a", "b")
    assert _row_get(row, 5, "ignored", default="default") == "default"


def test_row_get_record_like_namedtuple():
    """asyncpg.Record acts like a mapping; namedtuples expose __getitem__
    for both keys and indices, so the mapping branch wins on first try."""
    Row = namedtuple("Row", ["key", "other"])
    row = Row(key="value", other="x")
    # namedtuple doesn't support row["key"] — it raises TypeError, falls
    # through to row[index]. Index 0 → "value".
    assert _row_get(row, 0, "key") == "value"


# ---------------------------------------------------------------------------
# _normalize_thresholds
# ---------------------------------------------------------------------------


def test_normalize_thresholds_returns_defaults_when_none():
    out = _normalize_thresholds(None)
    assert out == DEFAULT_THRESHOLDS


def test_normalize_thresholds_returns_defaults_when_empty():
    out = _normalize_thresholds({})
    assert out == DEFAULT_THRESHOLDS


def test_normalize_thresholds_merges_overrides():
    """User-supplied overrides replace defaults; unknown keys ignored."""
    out = _normalize_thresholds({
        "max_wrong_start_lua_rows": 5,
        "max_unlinked_lua_ratio": 0.5,
        "alien_field_should_be_ignored": 999,
    })
    assert out["max_wrong_start_lua_rows"] == 5
    assert out["max_unlinked_lua_ratio"] == 0.5
    assert "alien_field_should_be_ignored" not in out


def test_normalize_thresholds_skips_none_values():
    """None override → keep default. This protects against partial
    config payloads that don't want to override every key."""
    out = _normalize_thresholds({
        "max_wrong_start_lua_rows": None,
        "max_unlinked_lua_ratio": None,
    })
    assert out["max_wrong_start_lua_rows"] == DEFAULT_THRESHOLDS["max_wrong_start_lua_rows"]
    assert out["max_unlinked_lua_ratio"] == DEFAULT_THRESHOLDS["max_unlinked_lua_ratio"]


def test_normalize_thresholds_clamps_negative_int_thresholds_to_zero():
    """A negative threshold makes no sense (count of bad rows can't be
    negative). Defensive: clamp to 0."""
    out = _normalize_thresholds({"max_wrong_start_lua_rows": -5})
    assert out["max_wrong_start_lua_rows"] == 0


def test_normalize_thresholds_coerces_string_int_thresholds():
    """env-var or YAML config may supply strings."""
    out = _normalize_thresholds({"max_wrong_start_lua_rows": "10"})
    assert out["max_wrong_start_lua_rows"] == 10


def test_normalize_thresholds_coerces_garbage_int_to_zero():
    """Bad string → safe_int returns 0 → clamped to 0."""
    out = _normalize_thresholds({"max_wrong_start_lua_rows": "garbage"})
    assert out["max_wrong_start_lua_rows"] == 0


def test_normalize_thresholds_returns_float_for_ratio():
    """max_unlinked_lua_ratio must be float (used in float comparisons)."""
    out = _normalize_thresholds({"max_unlinked_lua_ratio": 1})
    assert isinstance(out["max_unlinked_lua_ratio"], float)
    assert out["max_unlinked_lua_ratio"] == 1.0


def test_normalize_thresholds_zero_ratio_is_preserved():
    """0.0 (strictest possible) must survive — protects against the
    `value or 0.0` fall-through. With value=0.0 the `or` evaluates
    the right side, so the fallback path runs."""
    out = _normalize_thresholds({"max_unlinked_lua_ratio": 0.0})
    assert out["max_unlinked_lua_ratio"] == 0.0


def test_normalize_thresholds_handles_none_ratio():
    """None ratio → falls through `merged[key] = value` (skipped),
    then `float(merged["max_unlinked_lua_ratio"] or 0.0)` lands on
    the default value, NOT zero."""
    out = _normalize_thresholds({"max_unlinked_lua_ratio": None})
    # Default is 0.20 → preserved as float
    assert out["max_unlinked_lua_ratio"] == DEFAULT_THRESHOLDS["max_unlinked_lua_ratio"]


def test_normalize_thresholds_default_keys_match_breach_sites():
    """Pin the canonical set of threshold keys so a future addition of
    a new metric requires updating both this list AND DEFAULT_THRESHOLDS."""
    expected = {
        "max_unlinked_lua_ratio",
        "max_wrong_start_lua_rows",
        "max_map_name_mismatch_rows",
        "max_round_number_mismatch_rows",
        "max_duplicate_lua_round_links",
        "max_correlation_map_mismatch_rows",
        "max_complete_missing_core_rows",
    }
    assert set(DEFAULT_THRESHOLDS.keys()) == expected


# ---------------------------------------------------------------------------
# _build_breach
# ---------------------------------------------------------------------------


def test_build_breach_returns_canonical_shape():
    out = _build_breach("max_wrong_start_lua_rows", 5, 0)
    assert out == {
        "metric": "max_wrong_start_lua_rows",
        "value": 5,
        "threshold": 0,
    }


def test_build_breach_passes_through_value_types():
    """Floats, strings, None all propagate as-is to the dashboard."""
    assert _build_breach("ratio", 0.42, 0.20)["value"] == 0.42
    assert _build_breach("ratio", "n/a", 0.0)["value"] == "n/a"
    assert _build_breach("ratio", None, 0.0)["value"] is None


def test_build_breach_keys_are_stable():
    """The dashboard depends on these exact keys — pin so a refactor
    can't quietly rename `metric` → `name` or `threshold` → `limit`."""
    out = _build_breach("x", 1, 0)
    assert set(out.keys()) == {"metric", "value", "threshold"}
