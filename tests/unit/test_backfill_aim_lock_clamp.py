"""Aim-lock clamp backfill guard (audit remediation plan U3).

--apply must refuse to write unless the operator passes the exact candidate
count, phantom-ms sum, newest violation date, and candidate-id fingerprint
from a fresh dry-run. These tests cover the pure guard logic; the DB write is
exercised by the owner's guarded production run.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.backfill_aim_lock_clamp import check_expectations, fingerprint_ids  # noqa: E402


def _args(**overrides):
    defaults = {
        "expect_count": 56,
        "expect_phantom_ms": 726050,
        "expect_latest_date": "2026-06-11",
        "expect_fingerprint": fingerprint_ids([1, 2, 3]),
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def _stats(**overrides):
    stats = {
        "ids": [1, 2, 3],
        "count": 56,
        "phantom_ms": 726050,
        "latest_date": "2026-06-11",
        "fingerprint": fingerprint_ids([1, 2, 3]),
    }
    stats.update(overrides)
    return stats


def test_fingerprint_is_order_sensitive_and_stable():
    assert fingerprint_ids([1, 2, 3]) == fingerprint_ids([1, 2, 3])
    assert fingerprint_ids([1, 2, 3]) != fingerprint_ids([3, 2, 1])
    assert fingerprint_ids([]) == fingerprint_ids([])


def test_matching_expectations_pass():
    assert check_expectations(_stats(), _args()) == []


def test_each_mismatch_is_reported():
    problems = check_expectations(
        _stats(count=57, phantom_ms=1, latest_date="2026-07-01",
               fingerprint="deadbeef"),
        _args(),
    )
    assert len(problems) == 4
    assert any("count" in p for p in problems)
    assert any("phantom-ms" in p for p in problems)
    assert any("latest-date" in p for p in problems)
    assert any("fingerprint" in p for p in problems)


def test_missing_expectations_are_refused():
    problems = check_expectations(
        _stats(),
        _args(expect_count=None, expect_phantom_ms=None,
              expect_latest_date=None, expect_fingerprint=None),
    )
    assert len(problems) == 4
    assert all("required with --apply" in p for p in problems)


def test_new_rows_since_dry_run_change_fingerprint():
    """A row that appears between dry-run and apply must break the guard."""
    stats = _stats(ids=[1, 2, 3, 4], count=57,
                   fingerprint=fingerprint_ids([1, 2, 3, 4]))
    problems = check_expectations(stats, _args())
    assert problems, "guard must trip when the candidate set changed"


def test_zero_rows_with_apply_trips_guard():
    """A DB with no candidate rows (wrong target / already mutated) must fail
    the guard against a nonzero --expect-count, not silently no-op to success.
    main() now runs check_expectations even on a zero-row --apply measurement
    (Codex review on #509)."""
    stats = _stats(ids=[], count=0, phantom_ms=0, latest_date=None,
                   fingerprint=fingerprint_ids([]))
    problems = check_expectations(stats, _args())
    assert problems, "zero-row measurement must not satisfy --expect-count 56"
    assert any("count" in p for p in problems)
