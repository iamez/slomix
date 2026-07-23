"""Unit tests for skill_rating_service.py — pure functions only.

Tests _percentile, calculate_et_rating, get_tier, and edge cases.
No database required.
"""

import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.skill_rating_service import (
    _GLOBAL_SQL_COLUMNS,
    _PCS_SQL_COLUMNS,
    CONSTANT,
    PCS_METRICS,
    PROXIMITY_METRICS,
    WEIGHTS,
    _percentile,
    _row_to_stats,
    calculate_et_rating,
    get_tier,
)

# ===========================================================================
# _percentile
# ===========================================================================

class TestPercentile:
    """O(log n) percentile lookup against sorted values."""

    def test_empty_list_returns_half(self):
        assert _percentile([], 42.0) == 0.5

    def test_single_value_equal(self):
        # bisect_left=0, bisect_right=1 => (0+1)/(2*1) = 0.5
        assert _percentile([10.0], 10.0) == 0.5

    def test_single_value_below(self):
        # bisect_left=0, bisect_right=0 => 0/(2*1) = 0.0
        assert _percentile([10.0], 5.0) == 0.0

    def test_single_value_above(self):
        # bisect_left=1, bisect_right=1 => 2/(2*1) = 1.0
        assert _percentile([10.0], 15.0) == 1.0

    def test_median_of_three(self):
        # value=20, sorted=[10,20,30]: bisect_left=1, bisect_right=2 => (1+2)/(2*3) = 0.5
        assert _percentile([10.0, 20.0, 30.0], 20.0) == 0.5

    def test_bottom_of_three(self):
        # value=10, sorted=[10,20,30]: bisect_left=0, bisect_right=1 => 1/(6) ≈ 0.167
        result = _percentile([10.0, 20.0, 30.0], 10.0)
        assert result == pytest.approx(1.0 / 6.0, abs=0.001)

    def test_top_of_three(self):
        # value=30, sorted=[10,20,30]: bisect_left=2, bisect_right=3 => 5/(6) ≈ 0.833
        result = _percentile([10.0, 20.0, 30.0], 30.0)
        assert result == pytest.approx(5.0 / 6.0, abs=0.001)

    def test_duplicates(self):
        # value=10, sorted=[10,10,10]: bisect_left=0, bisect_right=3 => 3/(6) = 0.5
        assert _percentile([10.0, 10.0, 10.0], 10.0) == 0.5

    def test_value_between_entries(self):
        # value=15, sorted=[10,20,30]: bisect_left=1, bisect_right=1 => 2/(6) ≈ 0.333
        result = _percentile([10.0, 20.0, 30.0], 15.0)
        assert result == pytest.approx(2.0 / 6.0, abs=0.001)

    def test_large_sorted_list(self):
        """100 values, check top/bottom percentile."""
        values = sorted([float(i) for i in range(100)])
        assert _percentile(values, 0.0) == pytest.approx(0.005, abs=0.01)
        assert _percentile(values, 99.0) == pytest.approx(0.995, abs=0.01)

    def test_below_all_values(self):
        assert _percentile([10.0, 20.0, 30.0], -5.0) == 0.0

    def test_above_all_values(self):
        assert _percentile([10.0, 20.0, 30.0], 100.0) == 1.0


# ===========================================================================
# get_tier
# ===========================================================================

class TestGetTier:
    """Tier classification based on rating thresholds."""

    def test_elite(self):
        assert get_tier(0.85) == "elite"
        assert get_tier(0.90) == "elite"
        assert get_tier(1.15) == "elite"

    def test_veteran(self):
        assert get_tier(0.70) == "veteran"
        assert get_tier(0.84) == "veteran"

    def test_experienced(self):
        assert get_tier(0.55) == "experienced"
        assert get_tier(0.69) == "experienced"

    def test_regular(self):
        assert get_tier(0.40) == "regular"
        assert get_tier(0.54) == "regular"

    def test_newcomer(self):
        assert get_tier(0.00) == "newcomer"
        assert get_tier(0.39) == "newcomer"

    def test_negative_rating(self):
        assert get_tier(-0.1) == "newcomer"


# ===========================================================================
# calculate_et_rating
# ===========================================================================

class TestCalculateEtRating:
    """ET_Rating calculation with player stats and population percentiles."""

    def _make_stats(self, **overrides):
        """Create a default stats dict with zeros, plus overrides."""
        base = dict.fromkeys(WEIGHTS, 0.0)
        base.update(overrides)
        return base

    def _make_percentiles(self, n=10):
        """Create uniform percentile distributions for all metrics."""
        values = sorted([float(i) for i in range(n)])
        return dict.fromkeys(WEIGHTS, values)

    def test_average_player_near_constant(self):
        """All stats at exact median => each percentile ~0.5 => rating ≈ CONSTANT + sum(w*0.5)."""
        stats = self._make_stats(**dict.fromkeys(WEIGHTS, 4.5))
        percentiles = self._make_percentiles(n=10)
        rating, components = calculate_et_rating(stats, percentiles)
        # dpr is negative weight: -0.12, so contribution = -0.12 * ~0.5
        expected_approx = CONSTANT + sum(w * 0.5 for w in WEIGHTS.values())
        assert rating == pytest.approx(expected_approx, abs=0.05)

    def test_zero_stats_empty_percentiles(self):
        """Empty percentiles => all pct = 0.5 (fallback)."""
        stats = self._make_stats()
        percentiles = {}
        rating, components = calculate_et_rating(stats, percentiles)
        expected = CONSTANT + sum(w * 0.5 for w in WEIGHTS.values())
        assert rating == pytest.approx(expected, abs=0.01)

    def test_top_percentile_all_metrics(self):
        """All metrics at 100th percentile => rating near max."""
        stats = self._make_stats(**dict.fromkeys(WEIGHTS, 100.0))
        percentiles = self._make_percentiles(n=10)
        rating, components = calculate_et_rating(stats, percentiles)
        # All percentiles = 1.0, rating = CONSTANT + sum(weights * 1.0)
        # dpr has negative weight, so dpr contribution = -0.12 * 1.0
        expected = CONSTANT + sum(WEIGHTS.values())
        assert rating == pytest.approx(expected, abs=0.05)

    def test_bottom_percentile_all_metrics(self):
        """All metrics below everyone => rating near CONSTANT + negative."""
        stats = self._make_stats(**dict.fromkeys(WEIGHTS, -100.0))
        percentiles = self._make_percentiles(n=10)
        rating, components = calculate_et_rating(stats, percentiles)
        # All percentiles = 0.0
        expected = max(0.0, CONSTANT)
        assert rating == pytest.approx(expected, abs=0.01)

    def test_rating_clamped_at_zero(self):
        """Rating should never go below 0.0."""
        stats = self._make_stats(dpr=999.0)
        percentiles = {"dpr": sorted([float(i) for i in range(10)])}
        rating, _ = calculate_et_rating(stats, percentiles)
        assert rating >= 0.0

    def test_rating_clamped_at_1_5(self):
        """Rating should never exceed 1.5."""
        # Make all positive metrics at max percentile, huge values
        stats = self._make_stats(**dict.fromkeys(WEIGHTS, 999.0))
        percentiles = self._make_percentiles(n=2)
        rating, _ = calculate_et_rating(stats, percentiles)
        assert rating <= 1.5

    def test_components_returned_for_each_metric(self):
        stats = self._make_stats(dpm=50.0, kpr=3.0)
        percentiles = self._make_percentiles(n=10)
        rating, components = calculate_et_rating(stats, percentiles)
        for metric in WEIGHTS:
            assert metric in components
            c = components[metric]
            assert "raw" in c
            assert "percentile" in c
            assert "weight" in c
            assert "contribution" in c

    def test_dpr_negative_weight_lowers_rating(self):
        """High deaths per round should lower rating due to negative weight."""
        low_dpr = self._make_stats(dpr=0.0)
        high_dpr = self._make_stats(dpr=9.0)
        percentiles = self._make_percentiles(n=10)
        rating_low, _ = calculate_et_rating(low_dpr, percentiles)
        rating_high, _ = calculate_et_rating(high_dpr, percentiles)
        # Higher dpr percentile * negative weight => lower contribution
        assert rating_low > rating_high


# ===========================================================================
# _row_to_stats
# ===========================================================================

class TestRowToStats:
    """Extract PCS metrics from a DB row at a given offset (pcs_only = 8 columns).

    denied_playtime_pm moved to the proximity block on 2026-07-23, so a
    has_proximity=False row carries 8 PCS values (denied → neutral 0.0).
    """

    def test_basic_extraction(self):
        row = (0.0, 0.0, 0.0,  # padding
               50.0, 3.0, 2.0, 5.0, 1.0, 0.8, 0.4, 0.25)
        stats = _row_to_stats(row, offset=3, has_proximity=False)
        assert stats["dpm"] == 50.0
        assert stats["kpr"] == 3.0
        assert stats["dpr"] == 2.0
        assert stats["revive_rate"] == 5.0
        assert stats["objective_rate"] == 1.0
        assert stats["survival_rate"] == 0.8
        assert stats["useful_kill_rate"] == 0.4
        assert stats["accuracy"] == 0.25
        # denied is proximity-sourced now → neutral default in pcs_only rows
        assert stats["denied_playtime_pm"] == 0.0

    def test_zero_offset(self):
        row = (50.0, 3.0, 2.0, 5.0, 1.0, 0.8, 0.4, 0.25)
        stats = _row_to_stats(row, offset=0, has_proximity=False)
        assert stats["dpm"] == 50.0
        assert stats["accuracy"] == 0.25


# ===========================================================================
# denied_playtime_pm source switch (RCA 2026-07-23): PCS topshots[16] →
# proximity_kill_outcome. denied is now a proximity metric.
# ===========================================================================

class TestDeniedSourceContract:
    """Guards for the denied → proximity_kill_outcome switch."""

    def test_denied_is_proximity_metric(self):
        assert "denied_playtime_pm" in PROXIMITY_METRICS
        assert "denied_playtime_pm" not in PCS_METRICS

    def test_column_layout(self):
        # 8 PCS + 7 proximity = 15 global columns; denied leads the proximity block
        assert len(_GLOBAL_SQL_COLUMNS) == 15
        assert len(_PCS_SQL_COLUMNS) == 8
        assert "denied_playtime_pm" not in _PCS_SQL_COLUMNS
        assert _GLOBAL_SQL_COLUMNS[8] == "denied_playtime_pm"
        # global column order must match _row_to_stats offsets
        assert _GLOBAL_SQL_COLUMNS[7] == "accuracy"  # last PCS column

    def test_row_to_stats_denied_at_proximity_offset(self):
        # has_proximity=True: denied read from the proximity block (offset+8)
        row = tuple(range(15))  # values 0..14 at offsets 0..14
        stats = _row_to_stats(row, offset=0, has_proximity=True)
        assert stats["accuracy"] == 7.0          # last PCS
        assert stats["denied_playtime_pm"] == 8.0  # first proximity
        assert stats["kill_quality"] == 9.0

    def test_denied_skipped_in_pcs_only_rating(self):
        # A session-scope (pcs_only) rating must not consult denied (no proximity
        # data there); it is reported as proximity_data_unavailable, weight preserved.
        stats = dict.fromkeys(WEIGHTS, 0.5)
        percentiles = {m: sorted([0.0, 0.5, 1.0]) for m in WEIGHTS}
        _, components = calculate_et_rating(stats, percentiles, pcs_only=True)
        assert components["denied_playtime_pm"]["note"] == "proximity_data_unavailable"
        assert components["denied_playtime_pm"]["contribution"] == 0
        assert components["denied_playtime_pm"]["weight"] == WEIGHTS["denied_playtime_pm"]
