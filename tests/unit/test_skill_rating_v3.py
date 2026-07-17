"""ET Performance v3 shadow formula (audit AUD-007).

The v3 correction (vs v2's ≈0.57 centre) is that the population MEAN scores
EXACTLY 0.50 without retuning weights: directed midrank percentiles × absolute
weights (Σ|w|=1), no constant. Each metric column has mean 0.5, so the weighted
composite mean is 0.5 for ANY ranking pattern; the median lands near 0.5 but is
not forced there (Codex #513). These tests pin the mean property, the median
being centred only for rank-aligned cohorts, and the directional/neutralisation
handling.
"""
from __future__ import annotations

import statistics

import pytest

from website.backend.services.skill_rating_service import WEIGHTS
from website.backend.services.skill_rating_v3 import (
    _ABS_WEIGHT_SUM,
    _PENALTY_METRICS,
    UNSCOPED_METRICS,
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


def test_rank_aligned_population_centers_at_half():
    """The synthetic cohort ranks every metric in the SAME order, so the middle
    player sits at percentile 0.5 in each metric → both mean AND median are 0.50
    (this is the special aligned case where they coincide)."""
    scored = score_population(_synthetic_population(21))
    ratings = [p["et_performance_v3"] for p in scored]
    assert statistics.mean(ratings) == pytest.approx(0.5, abs=1e-3)
    assert statistics.median(ratings) == pytest.approx(0.5, abs=1e-9)


def _mixed_population(n: int = 23) -> list[dict]:
    """n players where each metric ranks them in a DIFFERENT order (distinct
    coprime permutations mod a prime), so rankings are not aligned and the
    median need not equal the mean."""
    players = []
    for i in range(n):
        components = {}
        for j, m in enumerate(WEIGHTS):
            components[m] = {"raw": float((i * (j + 1)) % n)}  # permutation per metric
        players.append({
            "player_guid": f"G{i:03d}", "display_name": f"P{i}",
            "rounds": 25, "components": components,
        })
    return players


def test_mixed_ranking_population_mean_is_exactly_half():
    """The corrected AUD-007 property: for ARBITRARY (mixed) metric rankings the
    population MEAN is exactly 0.50 — the median is not forced there (Codex)."""
    scored = score_population(_mixed_population(23))
    ratings = [p["et_performance_v3"] for p in scored]
    assert statistics.mean(ratings) == pytest.approx(0.5, abs=1e-3)


def test_crossfire_is_neutralized_for_all_players():
    """crossfire (epoch-unscoped) must give every player the neutral 0.5
    directed percentile so its distorted rate never affects ranking (Codex)."""
    assert "crossfire_rate" in UNSCOPED_METRICS
    scored = score_population(_mixed_population(10))
    for p in scored:
        assert p["components"]["crossfire_rate"]["directed_percentile"] == pytest.approx(0.5)


def test_observed_zero_proximity_ranks_at_bottom_not_neutral():
    """A genuinely-zero scoped proximity value must rank at the bottom (0.0), NOT
    be inflated to a neutral 0.5 — v3 no longer guesses missing-vs-zero, which
    would inflate real zeros (Codex #513). Missing/observed can't be split until
    migration 062 capability data exists."""
    base = {m: {"raw": 1.0} for m in WEIGHTS}
    hi = {"player_guid": "HI", "display_name": "HI", "rounds": 25,
          "components": {**base, "trade_rate": {"raw": 0.9}}}
    mid = {"player_guid": "MID", "display_name": "MID", "rounds": 25,
           "components": {**base, "trade_rate": {"raw": 0.4}}}
    zero = {"player_guid": "ZERO", "display_name": "ZERO", "rounds": 25,
            "components": {**base, "trade_rate": {"raw": 0.0}}}
    scored = {p["player_guid"]: p for p in score_population([hi, mid, zero])}
    assert scored["ZERO"]["components"]["trade_rate"]["directed_percentile"] == pytest.approx(0.0)
    assert scored["HI"]["components"]["trade_rate"]["directed_percentile"] == pytest.approx(1.0)


def test_score_population_uses_unrounded_raw_stats():
    """Ranking must use raw_stats (unrounded), not the 3-decimal display value
    in components["raw"], so near-equal players don't collapse into ties
    (Codex #513)."""
    def _p(guid, dpm_unrounded):
        return {
            "player_guid": guid, "display_name": guid, "rounds": 25,
            # display raw rounds both to 0.5 (a tie if used for ranking)…
            "components": {m: {"raw": 0.5} for m in WEIGHTS},
            # …but raw_stats carries the true, distinct values.
            "raw_stats": {**dict.fromkeys(WEIGHTS, 0.5), "dpm": dpm_unrounded},
        }
    scored = {p["player_guid"]: p for p in score_population([_p("A", 0.50004), _p("B", 0.49996)])}
    assert scored["A"]["components"]["dpm"]["directed_percentile"] == pytest.approx(1.0)
    assert scored["B"]["components"]["dpm"]["directed_percentile"] == pytest.approx(0.0)


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
