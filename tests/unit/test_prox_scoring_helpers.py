"""Tests for prox_scoring pure helpers — composite proximity score math.

This module is the engine behind the `/api/prox-scores` endpoint —
prox_combat / prox_team / prox_gamesense / prox_overall percentile-based
scoring. A regression silently:

- `_percentile_rank` ties handled wrong → percentiles diverge for equal
  raw values → "rank" column flickers session to session.
- `_percentile_rank` uses bisect_right → high values get rank 1.0, low
  values 1/n (NEVER 0). Pin so a swap to bisect_left silently shifts
  every player's percentile.
- `_compute_category_score` invert flag forgotten → "lower=better"
  metrics (return_fire_ms, dodge_ms) reward slowest player.
- `_compute_category_score` weight not normalised → category total
  diverges from 100 if metric weights don't sum to 1.0.
- `_sub_score` averages over only present metrics → a missing metric
  silently changes the radar denominator.
- `get_formula_config` schema drift → frontend renders empty radar.
- FORMULA_VERSION bump unannounced → frontend caches old percentiles
  against new formula → wrong score served.

Pin every branch.
"""
from __future__ import annotations

import pytest

from website.backend.services.prox_scoring import (
    CATEGORY_WEIGHTS,
    FORMULA_VERSION,
    METRICS,
    MIN_ENGAGEMENTS,
    _compute_category_score,
    _percentile_rank,
    _sub_score,
    get_formula_config,
)

# ---------------------------------------------------------------------------
# Constants — pin invariants that downstream callers rely on
# ---------------------------------------------------------------------------


def test_min_engagements_constant_pinned():
    """MIN_ENGAGEMENTS=10 — pin so a bump (e.g., 20) is a deliberate
    decision, not silent. The threshold gates who appears on the
    leaderboard."""
    assert MIN_ENGAGEMENTS == 10


def test_formula_version_pinned():
    """FORMULA_VERSION="2.1" — pin so any formula change is a deliberate bump.
    2.0 = quality-contract rework (midrank + coverage gating); 2.1 = IMP-003
    (trades denominator = sessions PLAYED, exact-round true-zero fill,
    single-player MIN_ENGAGEMENTS)."""
    assert FORMULA_VERSION == "2.1"


def test_category_weights_sum_to_one():
    """Category weights MUST sum to 1.0 — overall = weighted average,
    not weighted sum. Pin so a typo in CATEGORY_WEIGHTS that breaks
    normalisation (e.g., 0.5+0.5+0.5) is loud."""
    total = sum(CATEGORY_WEIGHTS.values())
    assert abs(total - 1.0) < 1e-9


def test_category_weights_keys_match_metrics_keys():
    """Every category in CATEGORY_WEIGHTS must have a METRICS entry,
    and vice versa. Pin so a renamed/dropped category doesn't leave
    a dangling weight that gets ignored at runtime."""
    assert set(CATEGORY_WEIGHTS.keys()) == set(METRICS.keys())


@pytest.mark.parametrize("cat_key", list(METRICS.keys()))
def test_each_category_has_metrics(cat_key):
    """Every category must have at least one metric. Pin so an empty
    `metrics: {}` dict (which would divide by zero in
    _compute_category_score's normalisation) can't ship."""
    assert len(METRICS[cat_key]["metrics"]) > 0


@pytest.mark.parametrize("cat_key", list(METRICS.keys()))
def test_metric_weights_are_positive(cat_key):
    """Every metric weight > 0 — a 0-weight metric serves no purpose
    and a negative weight inverts the contribution silently."""
    for mk, mc in METRICS[cat_key]["metrics"].items():
        assert mc["weight"] > 0, f"{cat_key}.{mk} has non-positive weight"


# ---------------------------------------------------------------------------
# _percentile_rank — bisect_right semantics, ties, edge cases
# ---------------------------------------------------------------------------


def test_percentile_rank_empty_list():
    """No players → no percentiles."""
    assert _percentile_rank([]) == []


def test_percentile_rank_single_value():
    """One value → percentile is 1/1 = 1.0 (top of pool)."""
    assert _percentile_rank([42.0]) == [1.0]


def test_percentile_rank_sorted_ascending():
    """[1, 2, 3] → percentiles [1/3, 2/3, 3/3] = [0.333, 0.667, 1.0].
    Pin bisect_right semantics: top value gets exactly 1.0, lowest
    gets 1/n (NEVER 0.0)."""
    out = _percentile_rank([1.0, 2.0, 3.0])
    assert out == pytest.approx([1 / 3, 2 / 3, 1.0])


def test_percentile_rank_preserves_input_order():
    """Returned list aligns with input order, not sorted order. Pin
    so callers can zip(guids, percentiles) safely."""
    # Input [3, 1, 2] → sorted [1,2,3]; bisect_right: 3→3/3, 1→1/3, 2→2/3
    out = _percentile_rank([3.0, 1.0, 2.0])
    assert out == pytest.approx([1.0, 1 / 3, 2 / 3])


def test_percentile_rank_handles_ties_via_bisect_right():
    """Tied values → both get the SAME percentile (bisect_right places
    them at the upper edge of the run). Pin so a swap to bisect_left
    that would split ties would be loud."""
    # [5, 5, 5] → all bisect_right at index 3 → 3/3 = 1.0
    out = _percentile_rank([5.0, 5.0, 5.0])
    assert out == pytest.approx([1.0, 1.0, 1.0])


def test_percentile_rank_lowest_never_zero():
    """Even the bottom-of-pool player gets 1/n, never 0.0. Pin so
    the score formula (pctl * weight * 100) never zeros out a
    qualified player completely."""
    out = _percentile_rank([1.0, 2.0, 3.0, 4.0, 5.0])
    assert min(out) == pytest.approx(1 / 5)
    assert min(out) > 0.0


def test_percentile_rank_negative_values_supported():
    """Returns are unitless — works on negative-valued metrics too
    (e.g., spawn timing diffs)."""
    out = _percentile_rank([-3.0, -1.0, -2.0])
    # Sorted: [-3, -2, -1]; -3→1/3, -1→3/3, -2→2/3
    assert out == pytest.approx([1 / 3, 1.0, 2 / 3])


# ---------------------------------------------------------------------------
# _compute_category_score — weighted scoring, invert handling
# ---------------------------------------------------------------------------


def _build_category_with_metrics(metrics: dict) -> dict:
    """Helper to install a temporary category for testing."""
    return {"label": "Test", "description": "Test", "metrics": metrics}


def test_compute_category_score_top_player_gets_100(monkeypatch):
    """A player with percentile 1.0 on every metric → category score = 100.
    Pin so a regression that flips a sign or scales by 50 instead of
    100 is immediately obvious."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 0.5, "invert": False, "label": "A"},
        "metric_b": {"weight": 0.5, "invert": False, "label": "B"},
    }))

    player_raw = {"__guid__": "g1", "metric_a": 10.0, "metric_b": 20.0}
    pmaps = {"metric_a": {"g1": 1.0}, "metric_b": {"g1": 1.0}}
    score, _ = _compute_category_score(player_raw, "test_cat", pmaps)
    assert score == 100.0


def test_compute_category_score_bottom_player_gets_zero(monkeypatch):
    """Percentile 0.0 on every metric → category score = 0.0.
    Pin the lower bound of the score range."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 0.5, "invert": False, "label": "A"},
        "metric_b": {"weight": 0.5, "invert": False, "label": "B"},
    }))

    player_raw = {"__guid__": "g1", "metric_a": 1.0, "metric_b": 2.0}
    pmaps = {"metric_a": {"g1": 0.0}, "metric_b": {"g1": 0.0}}
    score, _ = _compute_category_score(player_raw, "test_cat", pmaps)
    assert score == 0.0


def test_compute_category_score_invert_flips_percentile(monkeypatch):
    """invert=True flips percentile (1.0 → 0.0). Pin so "lower=better"
    metrics (return_fire_ms, dodge_ms) actually reward fast players,
    not the slowest in pool."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_inv": {"weight": 1.0, "invert": True, "label": "Inv"},
    }))

    player_raw = {"__guid__": "g1", "metric_inv": 100.0}
    # Percentile 1.0 (highest raw value) — but inverted → effective 0.0
    pmaps = {"metric_inv": {"g1": 1.0}}
    score, breakdown = _compute_category_score(player_raw, "test_cat", pmaps)
    assert score == 0.0
    assert breakdown["metric_inv"]["percentile"] == 0.0


def test_compute_category_score_normalises_weights(monkeypatch):
    """Internal weights are normalised by total — works even if metric
    weights don't sum to 1.0. Pin so a metric drop/add doesn't shift
    the score baseline."""
    # Weights sum to 0.6 (not 1.0) — but normalised internally
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 0.3, "invert": False, "label": "A"},
        "metric_b": {"weight": 0.3, "invert": False, "label": "B"},
    }))

    player_raw = {"__guid__": "g1", "metric_a": 1.0, "metric_b": 2.0}
    pmaps = {"metric_a": {"g1": 1.0}, "metric_b": {"g1": 1.0}}
    score, _ = _compute_category_score(player_raw, "test_cat", pmaps)
    # Both metrics percentile=1.0 → score should still be 100 (normalised)
    assert score == 100.0


def test_compute_category_score_neutral_default_for_missing_player(monkeypatch):
    """A player not present in the percentile map for a metric → 0.5
    (neutral). Pin so a player who lacks data for one metric doesn't
    score 0 on it (would tank the category unfairly)."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 1.0, "invert": False, "label": "A"},
    }))

    player_raw = {"__guid__": "g_missing", "metric_a": None}
    # g_missing not in percentile map
    pmaps = {"metric_a": {"other_player": 1.0}}
    _, breakdown = _compute_category_score(player_raw, "test_cat", pmaps)
    # Default 0.5 percentile applied
    assert breakdown["metric_a"]["percentile"] == 0.5


def test_compute_category_score_breakdown_has_all_required_fields(monkeypatch):
    """Breakdown dict per metric: raw, percentile, weight, contribution,
    label. Pin so frontend rendering doesn't KeyError on a stripped field."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 1.0, "invert": False, "label": "Metric A"},
    }))

    player_raw = {"__guid__": "g1", "metric_a": 7.5}
    pmaps = {"metric_a": {"g1": 0.8}}
    _, breakdown = _compute_category_score(player_raw, "test_cat", pmaps)
    entry = breakdown["metric_a"]
    assert set(entry.keys()) == {"raw", "percentile", "weight", "contribution", "label"}
    assert entry["raw"] == 7.5
    assert entry["label"] == "Metric A"


def test_compute_category_score_breakdown_raw_none_when_missing(monkeypatch):
    """When player_raw[metric_key] is None → breakdown["raw"] is None
    (not 0). Pin so frontend can show "—" vs "0" correctly."""
    monkeypatch.setitem(METRICS, "test_cat", _build_category_with_metrics({
        "metric_a": {"weight": 1.0, "invert": False, "label": "A"},
    }))

    player_raw = {"__guid__": "g1"}  # no metric_a key
    pmaps = {"metric_a": {"g1": 0.5}}
    _, breakdown = _compute_category_score(player_raw, "test_cat", pmaps)
    assert breakdown["metric_a"]["raw"] is None


# ---------------------------------------------------------------------------
# _sub_score — radar sub-axis averaging
# ---------------------------------------------------------------------------


def test_sub_score_averages_present_metrics():
    """Average percentile (× 100) of named metrics. Pin so adding a
    missing metric to the list doesn't drag the average toward 0."""
    breakdowns = {
        "prox_combat": {
            "headshot_pct":   {"percentile": 0.8},
            "return_fire_ms": {"percentile": 0.6},
        }
    }
    out = _sub_score(breakdowns, "prox_combat", ["headshot_pct", "return_fire_ms"])
    assert out == 70.0  # (80 + 60) / 2


def test_sub_score_skips_metrics_not_in_breakdown():
    """Metric requested but not in breakdown → silently skipped. Pin
    so a typo'd metric key shrinks the denominator instead of adding
    a 0 (which would lie about performance)."""
    breakdowns = {
        "prox_combat": {
            "headshot_pct": {"percentile": 1.0},
        }
    }
    # Request 2 metrics, only 1 present → average is 100, not 50
    out = _sub_score(breakdowns, "prox_combat", ["headshot_pct", "nonexistent"])
    assert out == 100.0


def test_sub_score_returns_zero_when_no_metrics_match():
    """No requested metrics found → 0.0 (no division by zero)."""
    breakdowns = {"prox_combat": {}}
    out = _sub_score(breakdowns, "prox_combat", ["a", "b", "c"])
    assert out == 0.0


def test_sub_score_returns_zero_when_category_missing():
    """Category not in breakdowns → 0.0. Pin defensive default so a
    radar render doesn't KeyError mid-page."""
    out = _sub_score({}, "missing_cat", ["any"])
    assert out == 0.0


def test_sub_score_rounds_to_two_decimals():
    """Output rounded to 2 decimals (matches scores throughout the
    module). Pin so the radar shows e.g. 73.33 instead of 73.3333..."""
    breakdowns = {
        "prox_combat": {
            "metric": {"percentile": 1 / 3},  # 33.333...
        }
    }
    out = _sub_score(breakdowns, "prox_combat", ["metric"])
    assert out == 33.33


# ---------------------------------------------------------------------------
# get_formula_config — schema contract for /prox-scores/formula
# ---------------------------------------------------------------------------


def test_get_formula_config_top_level_keys():
    """Pin top-level schema for the API consumer."""
    cfg = get_formula_config()
    assert "version" in cfg
    assert "min_engagements" in cfg
    assert "category_weights" in cfg
    assert "categories" in cfg


def test_get_formula_config_version_matches_constant():
    """Config version must match module FORMULA_VERSION constant.
    Pin so a version bump in code propagates to the API automatically."""
    cfg = get_formula_config()
    assert cfg["version"] == FORMULA_VERSION


def test_get_formula_config_min_engagements_matches_constant():
    cfg = get_formula_config()
    assert cfg["min_engagements"] == MIN_ENGAGEMENTS


def test_get_formula_config_category_weights_match_constant():
    """Category weights must round-trip exactly. Pin so a refactor
    that wraps weights in a tuple/dict doesn't silently change shape."""
    cfg = get_formula_config()
    assert cfg["category_weights"] == CATEGORY_WEIGHTS


def test_get_formula_config_each_category_has_required_fields():
    """Each category dict has: label, description, weight_in_overall,
    metrics. Pin schema for the frontend formula explainer."""
    cfg = get_formula_config()
    for cat_key, cat in cfg["categories"].items():
        assert "label" in cat, f"{cat_key} missing label"
        assert "description" in cat, f"{cat_key} missing description"
        assert "weight_in_overall" in cat, f"{cat_key} missing weight_in_overall"
        assert "metrics" in cat, f"{cat_key} missing metrics"
        assert cat["weight_in_overall"] == CATEGORY_WEIGHTS[cat_key]


def test_get_formula_config_metric_dicts_have_label_weight_invert():
    """Each metric in the config: label, weight, invert. Pin so the
    "lower=better" indicator on the frontend doesn't silently disappear."""
    cfg = get_formula_config()
    for cat in cfg["categories"].values():
        for metric in cat["metrics"].values():
            assert set(metric.keys()) == {"label", "weight", "invert"}
            assert isinstance(metric["weight"], (int, float))
            assert isinstance(metric["invert"], bool)
