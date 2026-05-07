"""Tests for replay_service pure helpers — round-replay primitives.

These helpers underpin the round-replay timeline endpoints
(/api/replay/timeline, /api/replay/positions, /api/replay/paths).
A regression silently:

- `_format_time` truncates instead of zero-padding seconds → "1:5"
  instead of "1:05" → tooltip looks broken.
- `_safe_float` raises on Decimal → endpoint 500s when asyncpg returns
  Decimal columns (very common for percentile/score columns).
- `_ensure_path_list` returns the raw JSONB string when DB stores text
  → downstream `[s.get(...)]` crashes (str doesn't have .get).
- `_find_position_at_time` linear-scans instead of bisecting → 60-fps
  paths (3000+ samples) make timeline scrubbing visibly stutter.
- `_find_position_at_time` returns the WRONG side of the boundary when
  ties happen → cursor jumps backwards on each scrub tick.

Pin every branch.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from website.backend.services.replay_service import (
    _ensure_path_list,
    _find_position_at_time,
    _format_time,
    _safe_float,
)

# ---------------------------------------------------------------------------
# _format_time — M:SS rendering
# ---------------------------------------------------------------------------


def test_format_time_zero():
    """0ms → "0:00" (NOT "0:0")."""
    assert _format_time(0) == "0:00"


def test_format_time_handles_none():
    """None → "?:??" sentinel — pin so a missing time field doesn't
    crash the timeline render."""
    assert _format_time(None) == "?:??"


@pytest.mark.parametrize("ms, expected", [
    (1_000,    "0:01"),
    (5_000,    "0:05"),
    (60_000,   "1:00"),
    (90_000,   "1:30"),
    (125_000,  "2:05"),   # zero-pad seconds
    (600_000,  "10:00"),
    (3_660_000, "61:00"),  # >60 min → keep MM:SS (no HH)
])
def test_format_time_known_values(ms, expected):
    """Pin canonical timestamps + zero-padding contract."""
    assert _format_time(ms) == expected


def test_format_time_truncates_subsecond():
    """Sub-second precision truncated (NOT rounded). Pin so a 999ms
    value renders as 0:00, not 0:01 (timeline scrub stays in sync
    with displayed time)."""
    assert _format_time(999) == "0:00"
    assert _format_time(1_999) == "0:01"


def test_format_time_handles_string_numeric():
    """Numeric strings via int() coercion — pin so a row coming from
    a JSON cast (where ms might be a string) doesn't crash."""
    assert _format_time("60000") == "1:00"


# ---------------------------------------------------------------------------
# _safe_float — Decimal coercion
# ---------------------------------------------------------------------------


def test_safe_float_none_returns_none():
    """Pin: None passes through (NOT 0.0). Caller distinguishes
    "no data" from "exactly zero"."""
    assert _safe_float(None) is None


def test_safe_float_decimal_coerces():
    """asyncpg returns NUMERIC columns as Decimal — must coerce to
    float for JSON serialization downstream. Pin so a refactor that
    drops the float() call doesn't break json.dumps."""
    out = _safe_float(Decimal("3.14"))
    assert out == 3.14
    assert isinstance(out, float)


def test_safe_float_int_coerces():
    """Int → float (preserves the magnitude)."""
    assert _safe_float(42) == 42.0
    assert isinstance(_safe_float(42), float)


def test_safe_float_zero_passes_through():
    """Zero is a valid value (NOT confused with None). Pin so a
    legitimate zero column doesn't get nulled."""
    out = _safe_float(0)
    assert out == 0.0
    assert out is not None


# ---------------------------------------------------------------------------
# _ensure_path_list — JSONB / text polymorphism
# ---------------------------------------------------------------------------


def test_ensure_path_list_none_returns_empty():
    """None → []. Pin so a player without a path field doesn't crash
    iteration."""
    assert _ensure_path_list(None) == []


def test_ensure_path_list_native_list_returned_as_is():
    """JSONB → asyncpg auto-decodes to Python list — pass through."""
    path = [{"time": 0, "x": 1}, {"time": 100, "x": 2}]
    assert _ensure_path_list(path) is path


def test_ensure_path_list_json_string_parsed():
    """Text storage (legacy) → json.loads. Pin so SQLite-backed dev
    DBs (which return text) work identically to PostgreSQL JSONB."""
    raw = '[{"time": 0}, {"time": 50}]'
    out = _ensure_path_list(raw)
    assert out == [{"time": 0}, {"time": 50}]


def test_ensure_path_list_invalid_json_string_returns_empty():
    """Malformed JSON → [] (NOT raise). Pin fail-safe so a corrupted
    row doesn't 500 the whole replay endpoint."""
    assert _ensure_path_list("not-json") == []


def test_ensure_path_list_empty_string_returns_empty():
    """Empty string → []. Pin so a NULL-coalesced empty value doesn't
    crash json.loads."""
    assert _ensure_path_list("") == []


def test_ensure_path_list_unknown_type_returns_empty():
    """Non-list/non-string/non-None → []. Pin defensive default for
    unexpected DB return shapes (e.g., dict, int)."""
    assert _ensure_path_list(42) == []
    assert _ensure_path_list({"x": 1}) == []


# ---------------------------------------------------------------------------
# _find_position_at_time — bisect-based nearest-sample search
# ---------------------------------------------------------------------------


def test_find_position_empty_path_returns_none():
    """No samples → None."""
    assert _find_position_at_time([], 1000) is None


def test_find_position_before_first_sample_returns_first():
    """Target before all samples → return first (NOT extrapolate)."""
    path = [{"time": 1000, "x": 5}, {"time": 2000, "x": 10}]
    out = _find_position_at_time(path, 500)
    assert out == {"time": 1000, "x": 5}


def test_find_position_after_last_sample_returns_last():
    """Target after all samples → return last (NOT extrapolate)."""
    path = [{"time": 1000, "x": 5}, {"time": 2000, "x": 10}]
    out = _find_position_at_time(path, 5000)
    assert out == {"time": 2000, "x": 10}


def test_find_position_exact_match():
    """Target exactly at a sample timestamp → that sample.

    bisect_left places idx AT the matching position, so the function
    enters the `idx > 0 and idx < len` branch and compares neighbors.
    For an exact match the diff to `before` (idx-1) is `target - before`
    and to `after` (the exact match) is `0` — `<=` tie-break would
    pick before. Pin observed nearest-sample semantics."""
    path = [
        {"time": 0, "x": 0},
        {"time": 1000, "x": 5},
        {"time": 2000, "x": 10},
    ]
    out = _find_position_at_time(path, 1000)
    # bisect_left → idx=1; before=path[0]@0 (diff 1000), after=path[1]@1000 (diff 0)
    # 1000 <= 0 is False → returns after = path[1]
    assert out == {"time": 1000, "x": 5}


def test_find_position_picks_nearer_neighbor_before():
    """Target closer to BEFORE neighbor → returns BEFORE."""
    path = [
        {"time": 0, "x": 0},
        {"time": 1000, "x": 5},
        {"time": 2000, "x": 10},
    ]
    # target=1100 → diff to 1000 is 100, diff to 2000 is 900 → before wins
    out = _find_position_at_time(path, 1100)
    assert out == {"time": 1000, "x": 5}


def test_find_position_picks_nearer_neighbor_after():
    """Target closer to AFTER neighbor → returns AFTER."""
    path = [
        {"time": 0, "x": 0},
        {"time": 1000, "x": 5},
        {"time": 2000, "x": 10},
    ]
    # target=1900 → diff to 1000 is 900, diff to 2000 is 100 → after wins
    out = _find_position_at_time(path, 1900)
    assert out == {"time": 2000, "x": 10}


def test_find_position_equidistant_picks_before():
    """Equidistant target → BEFORE (`<=` tie-break). Pin so scrubbing
    with smooth slider doesn't oscillate at exact midpoints."""
    path = [
        {"time": 1000, "x": 5},
        {"time": 2000, "x": 10},
    ]
    # target=1500 → equidistant → tie goes to before
    out = _find_position_at_time(path, 1500)
    assert out == {"time": 1000, "x": 5}


def test_find_position_handles_missing_time_field():
    """Sample dict without "time" key → defaults to 0 via .get(...).
    Pin so a malformed sample doesn't crash the whole replay."""
    path = [
        {"x": 1},  # no "time" key — defaults to 0
        {"time": 1000, "x": 2},
    ]
    # target=500 → diff to 0 is 500, diff to 1000 is 500 → tie → before
    out = _find_position_at_time(path, 500)
    assert out == {"x": 1}


def test_find_position_single_sample_returns_it():
    """One-sample path → that sample regardless of target."""
    path = [{"time": 5000, "x": 1}]
    assert _find_position_at_time(path, 0) == path[0]
    assert _find_position_at_time(path, 5000) == path[0]
    assert _find_position_at_time(path, 99999) == path[0]
