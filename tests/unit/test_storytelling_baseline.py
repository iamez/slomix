"""Unit tests for storytelling baseline helpers (S1.3)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling.baseline import (
    format_with_baseline,
    trailing_averages,
)


class TestFormatWithBaseline:
    def test_above_baseline(self):
        assert format_with_baseline(23, 17, "frags") == "23 frags — 6 above your usual"

    def test_below_baseline(self):
        assert format_with_baseline(11, 17, "frags") == "11 frags — 6 below your usual"

    def test_within_noise_band(self):
        # within max(0.5, 5%) of avg -> "around your usual"
        assert format_with_baseline(17.3, 17, "frags") == "17 frags (around your usual)"

    def test_no_history_returns_plain_value(self):
        assert format_with_baseline(23, None, "frags") == "23 frags"
        assert format_with_baseline(23, 0, "frags") == "23 frags"

    def test_precision_for_rate_metrics(self):
        out = format_with_baseline(412.5, 350.0, "DPM", precision=1)
        assert out == "412.5 DPM — 62.5 above your usual"


@pytest.mark.asyncio
async def test_trailing_averages_means_and_exclusion():
    db = AsyncMock()
    # Rows = per-session aggregates in _METRIC_EXPRS order:
    # kills, deaths, damage_given, revives_given, dpm
    db.fetch_all = AsyncMock(return_value=[
        (20, 10, 4000, 5, 400.0),
        (30, 14, 6000, 7, 500.0),
    ])
    avgs = await trailing_averages(db, "EDBB5DA9", before_session_id=123)

    assert avgs["_sessions"] == 2.0
    assert avgs["kills"] == 25.0
    assert avgs["dpm"] == 450.0
    # exclusion param reached the query
    args = db.fetch_all.call_args[0]
    assert 123 in args[1]


@pytest.mark.asyncio
async def test_trailing_averages_empty_history():
    db = AsyncMock()
    db.fetch_all = AsyncMock(return_value=[])
    assert await trailing_averages(db, "NOHISTORY") == {}
