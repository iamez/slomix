"""Regression test for PostgreSQLAdapter.pool_stats().

Surfaced via `/diagnostics` endpoint — the pool capacity / saturation
counters detect connection leaks and pool starvation. The shape and
keys must stay stable so dashboards (current and future) don't break.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from bot.core.database_adapter import PostgreSQLAdapter


def _adapter_with_pool(get_size: int, get_idle_size: int, get_min: int, get_max: int) -> PostgreSQLAdapter:
    a = PostgreSQLAdapter.__new__(PostgreSQLAdapter)
    a.pool = MagicMock()
    a.pool.get_size.return_value = get_size
    a.pool.get_idle_size.return_value = get_idle_size
    a.pool.get_min_size.return_value = get_min
    a.pool.get_max_size.return_value = get_max
    return a


def test_pool_stats_returns_dict_with_expected_keys():
    a = _adapter_with_pool(get_size=10, get_idle_size=7, get_min=5, get_max=20)
    stats = a.pool_stats()
    expected = {"connected", "size", "idle", "in_use", "min_size", "max_size", "utilisation_pct"}
    assert expected.issubset(stats.keys()), f"missing keys: {expected - stats.keys()}"


def test_pool_stats_reports_no_pool_when_unconnected():
    a = PostgreSQLAdapter.__new__(PostgreSQLAdapter)
    a.pool = None
    stats = a.pool_stats()
    assert stats == {"connected": False}


def test_pool_stats_computes_in_use_correctly():
    a = _adapter_with_pool(get_size=15, get_idle_size=4, get_min=5, get_max=20)
    stats = a.pool_stats()
    assert stats["in_use"] == 11  # 15 size - 4 idle


def test_pool_stats_utilisation_pct():
    a = _adapter_with_pool(get_size=20, get_idle_size=5, get_min=5, get_max=20)
    stats = a.pool_stats()
    # 15 in use / 20 size = 75%
    assert stats["utilisation_pct"] == 75.0


def test_pool_stats_zero_size_does_not_divide_by_zero():
    """Pool right after init can briefly have size=0; utilisation_pct
    must not raise ZeroDivisionError."""
    a = _adapter_with_pool(get_size=0, get_idle_size=0, get_min=5, get_max=20)
    stats = a.pool_stats()
    assert stats["utilisation_pct"] == 0.0


def test_pool_stats_swallows_internal_errors():
    """If asyncpg getter raises (e.g., during pool teardown), the
    diagnostics endpoint should get a structured error not a crash."""
    a = PostgreSQLAdapter.__new__(PostgreSQLAdapter)
    a.pool = MagicMock()
    a.pool.get_size.side_effect = RuntimeError("pool detached")
    stats = a.pool_stats()
    assert stats["connected"] is True
    assert "error" in stats
