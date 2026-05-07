"""Tests for _EndstatsPipelineMixin pure helpers.

These statics + non-DB helpers underpin endstats matching, supersede
guards, and retry pacing. A regression silently:

- `_summarize_endstats_quality` returns wrong tuple → quality
  comparison flips → richer file gets dropped, sparser kept.
- `_parse_endstats_filename_timestamp` ValueError leaks → caller
  crashes mid-supersede check.
- `_are_endstats_from_same_match` returns False on parse failure →
  legitimate same-match supersede silently blocked.
  ACTUAL: returns True (safe default) — pin observed.
- `_is_endstats_quality_better` strict `>` instead of `>=` → an
  incoming file with same quality would still trigger expensive
  supersede path.
  ACTUAL: strict `>` (must be strictly better) — pin observed.
- `_is_endstats_round_unique_violation` matches wrong text → a
  benign error gets retried forever.
- `_hhmmss_to_seconds` length check off by one → "1:23:45" with
  colons doesn't fit, returns None.
- `_get_endstats_retry_delay` overflows: 2 ** 100 → silent astronomical
  delays.

Pin every static.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from bot.services.endstats_pipeline_mixin import _EndstatsPipelineMixin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _instance(retry_base_delay=10, retry_max_delay=300):
    """Bare instance for invoking helpers; sets retry-config attrs."""
    obj = _EndstatsPipelineMixin.__new__(_EndstatsPipelineMixin)
    obj.endstats_retry_base_delay = retry_base_delay
    obj.endstats_retry_max_delay = retry_max_delay
    obj.endstats_retry_counts = {}
    obj.endstats_retry_tasks = {}
    obj.processed_endstats_files = set()
    return obj


# ---------------------------------------------------------------------------
# _summarize_endstats_quality
# ---------------------------------------------------------------------------


def test_summarize_quality_none_input():
    """None input → (0, 0)."""
    assert _instance()._summarize_endstats_quality(None) == (0, 0)


def test_summarize_quality_non_dict_input():
    """Non-dict (e.g., list, string) → (0, 0)."""
    assert _instance()._summarize_endstats_quality([1, 2, 3]) == (0, 0)
    assert _instance()._summarize_endstats_quality("garbage") == (0, 0)


def test_summarize_quality_counts_awards_and_vs_stats():
    """Pin tuple shape (awards_count, vs_count)."""
    out = _instance()._summarize_endstats_quality({
        "awards": [1, 2, 3, 4, 5],
        "vs_stats": [{"a": 1}, {"b": 2}],
    })
    assert out == (5, 2)


def test_summarize_quality_handles_missing_keys():
    """Empty dict → (0, 0)."""
    assert _instance()._summarize_endstats_quality({}) == (0, 0)


def test_summarize_quality_ignores_non_list_values():
    """awards as a dict (NOT list) → 0 (defensive)."""
    out = _instance()._summarize_endstats_quality({
        "awards": {"a": "b"},
        "vs_stats": "not a list",
    })
    assert out == (0, 0)


# ---------------------------------------------------------------------------
# _parse_endstats_filename_timestamp
# ---------------------------------------------------------------------------


def test_parse_filename_ts_extracts_canonical_format():
    """`YYYY-MM-DD-HHMMSS-...` → datetime."""
    out = _EndstatsPipelineMixin._parse_endstats_filename_timestamp(
        "2026-05-07-123045-oasis-round-1-endstats.txt"
    )
    assert out == datetime(2026, 5, 7, 12, 30, 45)


def test_parse_filename_ts_returns_none_for_invalid():
    """Garbage → None (NOT raise)."""
    assert _EndstatsPipelineMixin._parse_endstats_filename_timestamp(
        "garbage_filename.txt"
    ) is None


def test_parse_filename_ts_returns_none_for_short():
    """Filename shorter than 17 chars → None."""
    assert _EndstatsPipelineMixin._parse_endstats_filename_timestamp("short") is None


def test_parse_filename_ts_returns_none_for_empty():
    assert _EndstatsPipelineMixin._parse_endstats_filename_timestamp("") is None


# ---------------------------------------------------------------------------
# _are_endstats_from_same_match
# ---------------------------------------------------------------------------


def test_same_match_when_timestamps_close():
    """Within 45 min → same match."""
    inst = _instance()
    out = inst._are_endstats_from_same_match(
        "2026-05-07-120000-oasis-round-1-endstats.txt",
        "2026-05-07-120030-oasis-round-1-endstats.txt",  # 30s apart
    )
    assert out is True


def test_not_same_match_when_timestamps_far_apart():
    """>45 min apart → different matches."""
    inst = _instance()
    out = inst._are_endstats_from_same_match(
        "2026-05-07-120000-oasis-round-1-endstats.txt",
        "2026-05-07-130100-oasis-round-1-endstats.txt",  # 61 min apart
    )
    assert out is False


def test_same_match_at_exact_boundary():
    """Exactly 45 min → still same match (`<=` boundary)."""
    inst = _instance()
    out = inst._are_endstats_from_same_match(
        "2026-05-07-120000-oasis-round-1-endstats.txt",
        "2026-05-07-124500-oasis-round-1-endstats.txt",  # 45 min
    )
    assert out is True


def test_same_match_safe_default_when_unparseable():
    """Either filename unparseable → True (assume same match — safer
    to allow supersede than block legitimate one)."""
    inst = _instance()
    assert inst._are_endstats_from_same_match("garbage1", "garbage2") is True
    assert inst._are_endstats_from_same_match(
        "garbage", "2026-05-07-120000-x.txt"
    ) is True


def test_same_match_custom_window():
    """Custom max_minutes argument respected."""
    inst = _instance()
    # 30s apart is still "same match" with 1-min window
    out = inst._are_endstats_from_same_match(
        "2026-05-07-120000-oasis-round-1-endstats.txt",
        "2026-05-07-120030-oasis-round-1-endstats.txt",
        max_minutes=1,
    )
    assert out is True
    # But not with 0-min window (boundary at 0)
    out = inst._are_endstats_from_same_match(
        "2026-05-07-120000-oasis-round-1-endstats.txt",
        "2026-05-07-120030-oasis-round-1-endstats.txt",
        max_minutes=0,
    )
    assert out is False


# ---------------------------------------------------------------------------
# _is_endstats_quality_better
# ---------------------------------------------------------------------------


def test_quality_better_strict_greater_than():
    """Strict `>` — equal quality → NOT better. Pin so an equal-quality
    file doesn't trigger expensive supersede path."""
    inst = _instance()
    assert inst._is_endstats_quality_better((5, 3), (4, 3)) is True
    assert inst._is_endstats_quality_better((5, 3), (5, 3)) is False
    assert inst._is_endstats_quality_better((4, 3), (5, 3)) is False


def test_quality_better_compares_lexicographically():
    """Tuple comparison: awards count first, then vs_stats. Pin so
    a file with more awards but fewer vs_stats wins."""
    inst = _instance()
    # (5, 1) > (4, 100) because 5 > 4
    assert inst._is_endstats_quality_better((5, 1), (4, 100)) is True
    # (5, 2) > (5, 1) because awards equal, vs_count tiebreak
    assert inst._is_endstats_quality_better((5, 2), (5, 1)) is True


# ---------------------------------------------------------------------------
# _is_endstats_round_unique_violation
# ---------------------------------------------------------------------------


def test_unique_violation_matches_pg_error():
    """Both substrings present → True."""
    inst = _instance()
    err = Exception(
        'duplicate key value violates unique constraint "uq_processed_endstats_round_id"'
    )
    assert inst._is_endstats_round_unique_violation(err) is True


def test_unique_violation_requires_both_substrings():
    """Only one substring present → False (defensive — prevents false
    positive on unrelated unique-constraint errors)."""
    inst = _instance()
    err1 = Exception("uq_processed_endstats_round_id but no duplicate text")
    err2 = Exception("duplicate key value violates unique constraint other")
    assert inst._is_endstats_round_unique_violation(err1) is False
    assert inst._is_endstats_round_unique_violation(err2) is False


def test_unique_violation_returns_false_for_unrelated():
    """Connection errors / generic errors → False."""
    inst = _instance()
    assert inst._is_endstats_round_unique_violation(Exception("connection refused")) is False
    assert inst._is_endstats_round_unique_violation(ValueError("bad")) is False


# ---------------------------------------------------------------------------
# _hhmmss_to_seconds
# ---------------------------------------------------------------------------


def test_hhmmss_canonical():
    """Pin canonical conversions."""
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("000000") == 0
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("000130") == 90  # 1m30s
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("010000") == 3600  # 1h
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("123045") == 12 * 3600 + 30 * 60 + 45


def test_hhmmss_handles_longer_strings():
    """Trailing chars ignored — only first 6 used. Pin so a row with
    extra suffix data doesn't break parsing."""
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("123045xyz") == 12 * 3600 + 30 * 60 + 45


def test_hhmmss_too_short_returns_none():
    """<6 chars → None."""
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("12345") is None
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("") is None


def test_hhmmss_none_input_returns_none():
    assert _EndstatsPipelineMixin._hhmmss_to_seconds(None) is None


def test_hhmmss_non_numeric_returns_none():
    """Non-digit chars → None (try/except guard)."""
    assert _EndstatsPipelineMixin._hhmmss_to_seconds("abcdef") is None


# ---------------------------------------------------------------------------
# _get_endstats_retry_delay — exponential backoff
# ---------------------------------------------------------------------------


def test_retry_delay_first_attempt_is_base():
    """attempt=1 → base * 2^0 = base."""
    inst = _instance(retry_base_delay=10, retry_max_delay=300)
    assert inst._get_endstats_retry_delay(1) == 10


def test_retry_delay_grows_exponentially():
    """attempt N → base * 2^(N-1)."""
    inst = _instance(retry_base_delay=10, retry_max_delay=10000)
    assert inst._get_endstats_retry_delay(2) == 20
    assert inst._get_endstats_retry_delay(3) == 40
    assert inst._get_endstats_retry_delay(4) == 80


def test_retry_delay_capped_at_max():
    """Delay capped at endstats_retry_max_delay. Pin so attempt=10
    doesn't request a 5120s sleep."""
    inst = _instance(retry_base_delay=10, retry_max_delay=300)
    assert inst._get_endstats_retry_delay(10) == 300
    assert inst._get_endstats_retry_delay(100) == 300


def test_retry_delay_max_clamps_even_first_attempt():
    """If max < base → first attempt clamped to max."""
    inst = _instance(retry_base_delay=100, retry_max_delay=50)
    assert inst._get_endstats_retry_delay(1) == 50


# ---------------------------------------------------------------------------
# _clear_endstats_retry_state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clear_retry_state_removes_count_and_task():
    """Clear pops both counter + task entries.

    Must run in async context — production code calls
    `asyncio.current_task()` unconditionally."""
    inst = _instance()
    inst.endstats_retry_counts["foo.txt"] = 5
    fake_task = MagicMock()
    fake_task.done.return_value = True
    inst.endstats_retry_tasks["foo.txt"] = fake_task

    inst._clear_endstats_retry_state("foo.txt")

    assert "foo.txt" not in inst.endstats_retry_counts
    assert "foo.txt" not in inst.endstats_retry_tasks


@pytest.mark.asyncio
async def test_clear_retry_state_no_op_when_filename_unknown():
    """Unknown filename → no crash."""
    inst = _instance()
    inst._clear_endstats_retry_state("nonexistent.txt")
    # No raise


@pytest.mark.asyncio
async def test_clear_retry_state_does_not_cancel_done_task():
    """If task is already done → don't cancel (pointless + noisy)."""
    inst = _instance()
    fake_task = MagicMock()
    fake_task.done.return_value = True
    inst.endstats_retry_tasks["foo.txt"] = fake_task
    inst._clear_endstats_retry_state("foo.txt")
    fake_task.cancel.assert_not_called()
