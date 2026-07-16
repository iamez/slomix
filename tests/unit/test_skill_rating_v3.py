"""ET Performance v3 shadow formula (audit AUD-007).

The headline v3 claim is that the median profile scores EXACTLY 0.50 (unlike
v2's ≈0.57), achieved without retuning weights: directed midrank percentiles
× absolute weights, no constant. These tests prove that property and the
directional handling of penalty metrics.
"""
from __future__ import annotations

import statistics

import pytest

from website.backend.services.skill_rating_service import WEIGHTS
from website.backend.services.skill_rating_v3 import (
    _ABS_WEIGHT_SUM,
    _PENALTY_METRICS,
    directed_midrank_percentiles,
    score_population,
)


def test_absolute_weights_sum_to_one():
    """The median-0.50 property depends on Σ|w| == 1.0."""
    assert pytest.approx(1.0, abs=1e-9) == _ABS_WEIGHT_SUM


def test_dpr_is_the_penalty_metric():
    assert "dpr" in _PENALTY_METRICS


def test_midrank_median_is_half():
    assert directed_midrank_percentiles([1, 2, 3, 4, 5])[2] == pytest.approx(0.5)
    assert directed_midrank_percentiles([7, 7, 7]) == pytest.approx([0.5, 0.5, 0.5])


def _synthetic_population(n: int = 21) -> list[dict]:
    """n players with each metric spread across a distinct rank so every
    metric column has a clean midrank distribution."""
    players = []
    for i in range(n):
        components = {}
        for j, m in enumerate(WEIGHTS):
            # Distinct value per player per metric; offset by metric so columns
            # aren't identical (avoids all-equal-everywhere degeneracy).
            components[m] = {"raw": float(i * 10 + j)}
        players.append({
            "player_guid": f"G{i:03d}",
            "display_name": f"P{i}",
            "rounds": 25,
            "components": components,
        })
    return players


def test_population_median_is_exactly_half():
    """Across a full-rank synthetic cohort, the MEDIAN v3 rating is 0.50.

    This is the core AUD-007 fix vs v2's ≈0.57.
    """
    scored = score_population(_synthetic_population(21))
    ratings = [p["et_performance_v3"] for p in scored]
    assert statistics.median(ratings) == pytest.approx(0.5, abs=1e-9)


def test_penalty_metric_direction_is_flipped():
    """Two players identical except dpr: the one with MORE deaths must score
    LOWER (penalty inverted, not rewarded)."""
    base = {m: {"raw": 1.0} for m in WEIGHTS}
    low_dpr = {"player_guid": "A", "display_name": "A", "rounds": 25,
               "components": {**base, "dpr": {"raw": 0.1}}}
    high_dpr = {"player_guid": "B", "display_name": "B", "rounds": 25,
                "components": {**base, "dpr": {"raw": 9.0}}}
    scored = {p["player_guid"]: p["et_performance_v3"]
              for p in score_population([low_dpr, high_dpr])}
    assert scored["A"] > scored["B"], "more deaths must lower the rating"


def test_no_constant_offset():
    """A single player has no cohort → every directed percentile is 0.5 →
    rating = 0.5 * Σ|w| = 0.5 (no additive constant)."""
    solo = score_population(_synthetic_population(1))
    assert solo[0]["et_performance_v3"] == pytest.approx(0.5, abs=1e-9)


def test_components_flag_unscoped_crossfire():
    scored = score_population(_synthetic_population(5))
    comps = scored[0]["components"]
    assert comps["crossfire_rate"]["epoch_scoped"] is False
    assert comps["dpm"]["epoch_scoped"] is True
    assert "abs_weight" in comps["dpm"] and comps["dpm"]["abs_weight"] >= 0
