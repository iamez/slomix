"""Tests for pure helper functions in storytelling_service."""

import asyncio
from datetime import date

import pytest

from website.backend.services.storytelling_service import (
    _BoundedLockDict,
    _format_time_ms,
    _to_date,
    _to_date_str,
)


# ── _to_date ─────────────────────────────────────────────────────

class TestToDate:
    def test_string_to_date(self):
        assert _to_date("2026-03-28") == date(2026, 3, 28)

    def test_date_passthrough(self):
        d = date(2026, 3, 28)
        assert _to_date(d) is d

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            _to_date("not-a-date")

    def test_wrong_format_raises(self):
        with pytest.raises(ValueError):
            _to_date("28/03/2026")


# ── _to_date_str ─────────────────────────────────────────────────

class TestToDateStr:
    def test_date_to_string(self):
        assert _to_date_str(date(2026, 3, 28)) == "2026-03-28"

    def test_valid_string_passthrough(self):
        assert _to_date_str("2026-03-28") == "2026-03-28"

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError):
            _to_date_str("nope")

    def test_wrong_format_raises(self):
        with pytest.raises(ValueError):
            _to_date_str("03-28-2026")


# ── _format_time_ms ─────────────────────────────────────────────

class TestFormatTimeMs:
    def test_zero(self):
        assert _format_time_ms(0) == "0:00"

    def test_one_minute_five_seconds(self):
        assert _format_time_ms(65000) == "1:05"

    def test_exact_minute(self):
        assert _format_time_ms(120000) == "2:00"

    def test_negative(self):
        assert _format_time_ms(-5000) == "0:00"

    def test_none(self):
        assert _format_time_ms(None) == "0:00"

    def test_sub_second(self):
        assert _format_time_ms(999) == "0:00"

    def test_large_value(self):
        assert _format_time_ms(600000) == "10:00"


# ── _BoundedLockDict ────────────────────────────────────────────

class TestBoundedLockDict:
    def test_get_returns_lock(self):
        bld = _BoundedLockDict(maxsize=4)
        lock = bld.get("session-1")
        assert isinstance(lock, asyncio.Lock)

    def test_same_key_returns_same_lock(self):
        bld = _BoundedLockDict(maxsize=4)
        lock1 = bld.get("session-1")
        lock2 = bld.get("session-1")
        assert lock1 is lock2

    def test_different_keys_return_different_locks(self):
        bld = _BoundedLockDict(maxsize=4)
        lock1 = bld.get("session-1")
        lock2 = bld.get("session-2")
        assert lock1 is not lock2

    def test_evicts_oldest_when_full(self):
        bld = _BoundedLockDict(maxsize=3)
        lock_a = bld.get("a")
        bld.get("b")
        bld.get("c")
        # Adding a 4th key should evict "a"
        bld.get("d")
        lock_a_new = bld.get("a")
        assert lock_a is not lock_a_new  # "a" was evicted and recreated

    def test_size_stays_bounded(self):
        bld = _BoundedLockDict(maxsize=3)
        for i in range(10):
            bld.get(f"key-{i}")
        assert len(bld._locks) <= 3
