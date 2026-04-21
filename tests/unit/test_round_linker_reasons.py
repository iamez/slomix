from __future__ import annotations

from datetime import datetime, timezone

import pytest

from bot.core.round_linker import resolve_round_id, resolve_round_id_with_reason


class _FakeDB:
    def __init__(self, rows_with_date=None, rows_without_date=None):
        self.rows_with_date = rows_with_date if rows_with_date is not None else []
        self.rows_without_date = rows_without_date if rows_without_date is not None else []

    async def fetch_all(self, query, params):
        if "AND round_date = ?" in query:
            return self.rows_with_date
        return self.rows_without_date


@pytest.mark.asyncio
async def test_resolve_round_id_with_reason_resolved():
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "220205", None)],
        rows_without_date=[(9818, "2026-02-11", "220205", None)],
    )

    target_dt = datetime.strptime("2026-02-11 220206", "%Y-%m-%d %H%M%S")
    round_id, diag = await resolve_round_id_with_reason(
        db,
        "supply",
        2,
        target_dt=target_dt,
        round_date="2026-02-11",
        round_time="220206",
        window_minutes=45,
    )

    assert round_id == 9818
    assert diag["reason_code"] == "resolved"
    assert diag["candidate_count"] == 1
    assert diag["best_diff_seconds"] == 1


@pytest.mark.asyncio
async def test_resolve_round_id_with_reason_no_rows():
    db = _FakeDB(rows_with_date=[], rows_without_date=[])

    round_id, diag = await resolve_round_id_with_reason(
        db,
        "supply",
        2,
        round_date="2026-02-11",
        round_time="220205",
    )

    assert round_id is None
    assert diag["reason_code"] == "no_rows_for_map_round"


@pytest.mark.asyncio
async def test_resolve_round_id_with_reason_date_filter_excluded_rows():
    db = _FakeDB(rows_with_date=[], rows_without_date=[(9818,)])

    round_id, diag = await resolve_round_id_with_reason(
        db,
        "supply",
        2,
        round_date="2026-02-11",
        round_time="220205",
    )

    assert round_id is None
    assert diag["reason_code"] == "date_filter_excluded_rows"


@pytest.mark.asyncio
async def test_resolve_round_id_with_reason_outside_window():
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "230000", None)],
        rows_without_date=[(9818, "2026-02-11", "230000", None)],
    )

    target_dt = datetime.strptime("2026-02-11 220205", "%Y-%m-%d %H%M%S")
    round_id, diag = await resolve_round_id_with_reason(
        db,
        "supply",
        2,
        target_dt=target_dt,
        round_date="2026-02-11",
        round_time="220205",
        window_minutes=5,
    )

    assert round_id is None
    assert diag["reason_code"] == "all_candidates_outside_window"
    assert diag["best_diff_seconds"] == 3475


@pytest.mark.asyncio
async def test_resolve_round_id_with_reason_time_parse_failed():
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "bad", None)],
        rows_without_date=[(9818, "2026-02-11", "bad", None)],
    )

    target_dt = datetime.strptime("2026-02-11 220205", "%Y-%m-%d %H%M%S")
    round_id, diag = await resolve_round_id_with_reason(
        db,
        "supply",
        2,
        target_dt=target_dt,
        round_date="2026-02-11",
        round_time="220205",
        window_minutes=45,
    )

    assert round_id is None
    assert diag["reason_code"] == "time_parse_failed"
    assert diag["parsed_candidate_count"] == 0


@pytest.mark.asyncio
async def test_resolve_round_id_compatibility_wrapper():
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "220205", None)],
        rows_without_date=[(9818, "2026-02-11", "220205", None)],
    )

    target_dt = datetime.strptime("2026-02-11 220206", "%Y-%m-%d %H%M%S")
    round_id = await resolve_round_id(
        db,
        "supply",
        2,
        target_dt=target_dt,
        round_date="2026-02-11",
        round_time="220206",
    )
    assert round_id == 9818


# ---------------------------------------------------------------------------
# Regression for Copilot review on PR #130: tz-aware target_dt must not
# raise TypeError inside the naive/aware arithmetic downstream. The
# proximity relinker started passing `datetime.now(timezone.utc)`-style
# values; round_linker normalizes on entry so legacy naive callers and
# tz-aware callers both work.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_round_id_tz_aware_target_dt_no_crash():
    """Regression: tz-aware target_dt must not raise TypeError downstream.

    Pre-fix, `abs(candidate_dt - target_dt)` inside the matcher crashed with
    `can't subtract offset-naive and offset-aware datetimes` as soon as the
    proximity relinker started passing `datetime.now(timezone.utc)`-style
    values. The normalization at entry converts tz-aware → naive-local so
    the downstream arithmetic stays consistent.

    We don't assert a specific round_id because the tz-aware → local-naive
    conversion depends on the host UTC offset (test machine may be UTC,
    UTC+1, UTC+2, …), and whether the result falls inside the 45-min
    matching window is offset-sensitive. The contract we pin here is:
    tz-aware input never raises, and the helper always returns a
    structured `diag` dict.
    """
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "220205", None)],
        rows_without_date=[(9818, "2026-02-11", "220205", None)],
    )
    tz_aware = datetime(2026, 2, 11, 22, 2, 6, tzinfo=timezone.utc)
    round_id, diag = await resolve_round_id_with_reason(
        db, "supply", 2,
        target_dt=tz_aware,
        round_date="2026-02-11",
        round_time="220206",
    )
    assert diag["reason_code"] in {
        "resolved",
        "all_candidates_outside_window",
    }
    if diag["reason_code"] == "resolved":
        assert round_id == 9818


@pytest.mark.asyncio
async def test_resolve_round_id_naive_target_dt_still_works():
    """Legacy callers that pass naive-local target_dt keep working."""
    db = _FakeDB(
        rows_with_date=[(9818, "2026-02-11", "220205", None)],
        rows_without_date=[(9818, "2026-02-11", "220205", None)],
    )
    naive = datetime.strptime("2026-02-11 220206", "%Y-%m-%d %H%M%S")
    round_id, diag = await resolve_round_id_with_reason(
        db, "supply", 2,
        target_dt=naive,
        round_date="2026-02-11",
        round_time="220206",
    )
    assert round_id == 9818
    assert diag["reason_code"] == "resolved"
