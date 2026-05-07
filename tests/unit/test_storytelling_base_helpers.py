"""Tests for storytelling/base.py module-level helpers.

These are small pure utilities that get touched by every Storytelling
mixin: date normalisation, time formatting, and the bounded lock dict
that prevents per-session lock accumulation from leaking memory.

The lock dict in particular is a memory-leak guard — if its LRU
eviction regresses, locks pile up unboundedly across the website's
lifetime (every unique session_date adds an asyncio.Lock that never
gets garbage-collected). Pin the eviction contract.
"""
from __future__ import annotations

import asyncio
from datetime import date

import pytest

from website.backend.services.storytelling.base import (
    _BoundedLockDict,
    _compute_locks,
    _format_time_ms,
    _to_date,
    _to_date_str,
)


# ---------------------------------------------------------------------------
# _to_date
# ---------------------------------------------------------------------------


def test_to_date_passthroughs_date_object():
    d = date(2026, 4, 21)
    assert _to_date(d) is d


def test_to_date_parses_iso_string():
    assert _to_date("2026-04-21") == date(2026, 4, 21)


def test_to_date_rejects_bad_string():
    with pytest.raises(ValueError):
        _to_date("not-a-date")


def test_to_date_rejects_wrong_format():
    """Production uses asyncpg with DATE columns — only YYYY-MM-DD is valid."""
    with pytest.raises(ValueError):
        _to_date("21/04/2026")


# ---------------------------------------------------------------------------
# _to_date_str
# ---------------------------------------------------------------------------


def test_to_date_str_converts_date_to_iso():
    assert _to_date_str(date(2026, 4, 21)) == "2026-04-21"


def test_to_date_str_passthroughs_valid_string():
    """Valid strings pass through after format check (no re-parsing)."""
    assert _to_date_str("2026-04-21") == "2026-04-21"


def test_to_date_str_rejects_invalid_string():
    """Required because PCS columns store text — silently passing
    'not-a-date' would corrupt downstream queries."""
    with pytest.raises(ValueError):
        _to_date_str("not-a-date")


# ---------------------------------------------------------------------------
# _format_time_ms
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ms, expected", [
    (0,         "0:00"),       # boundary: zero
    (1000,      "0:01"),       # 1 second
    (59_999,    "0:59"),       # one tick before minute roll
    (60_000,    "1:00"),       # exactly 1 minute
    (75_500,    "1:15"),       # 1 min 15 sec
    (599_999,   "9:59"),       # one tick before 10 min
    (600_000,   "10:00"),      # 10 minutes — most common round duration
    (3_660_000, "61:00"),      # >60 min — no HH:MM:SS rollover
])
def test_format_time_ms_known_values(ms, expected):
    assert _format_time_ms(ms) == expected


@pytest.mark.parametrize("bad", [None, 0, -1, -100_000])
def test_format_time_ms_handles_bad_input(bad):
    """Negative or None must not crash; falls back to 0:00."""
    assert _format_time_ms(bad) == "0:00"


def test_format_time_ms_truncates_subsecond_remainder():
    """1099 ms truncates to 1 second (integer division of total_seconds)."""
    assert _format_time_ms(1099) == "0:01"


# ---------------------------------------------------------------------------
# _BoundedLockDict — memory-leak guard
# ---------------------------------------------------------------------------


def test_bounded_lock_dict_returns_same_lock_for_same_key():
    """Idempotent: same key → same Lock instance (otherwise the lock is
    useless because two callers would each own a fresh lock)."""
    d = _BoundedLockDict(maxsize=8)
    a = d.get("session-X")
    b = d.get("session-X")
    assert a is b
    assert isinstance(a, asyncio.Lock)


def test_bounded_lock_dict_returns_different_lock_for_different_keys():
    d = _BoundedLockDict(maxsize=8)
    a = d.get("session-A")
    b = d.get("session-B")
    assert a is not b


def test_bounded_lock_dict_evicts_oldest_when_full():
    """LRU-by-insertion eviction. Once we exceed maxsize, the FIRST
    inserted key is evicted; subsequent get() of that key returns a
    new (different) Lock instance."""
    d = _BoundedLockDict(maxsize=3)
    keys = ["a", "b", "c"]
    locks = {k: d.get(k) for k in keys}

    # Insert a 4th → should evict "a"
    d.get("d")

    # "a" comes back as a NEW Lock (proves eviction happened)
    a_after = d.get("a")
    assert a_after is not locks["a"]


def test_bounded_lock_dict_keeps_size_bounded():
    """Insert 100 distinct keys with maxsize=10 → internal dict never
    exceeds 10 entries. This is THE memory-leak guarantee."""
    d = _BoundedLockDict(maxsize=10)
    for i in range(100):
        d.get(f"session-{i}")
    assert len(d._locks) == 10


def test_bounded_lock_dict_recently_inserted_keys_are_kept():
    """After overflow, the NEWEST keys must still be present unchanged."""
    d = _BoundedLockDict(maxsize=3)
    a = d.get("a")
    b = d.get("b")
    c = d.get("c")
    d.get("d")  # evict a
    d.get("e")  # evict b

    # c, d, e are still in the dict; a, b are not.
    assert d.get("c") is c
    # a got re-inserted as a fresh lock (different instance from original)
    assert d.get("a") is not a
    assert d.get("b") is not b


def test_global_compute_locks_instance_is_bounded():
    """The module-level singleton must use the bounded variant — guarding
    against a future refactor that swaps it for a plain dict."""
    assert isinstance(_compute_locks, _BoundedLockDict)
    # And it has a configured maxsize > 0
    assert _compute_locks._maxsize > 0


def test_bounded_lock_dict_handles_maxsize_one():
    """Edge case: maxsize=1 means every new key evicts the previous."""
    d = _BoundedLockDict(maxsize=1)
    a = d.get("a")
    d.get("b")
    a_again = d.get("a")
    assert a_again is not a
