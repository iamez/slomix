"""Tests for PredictionEngine pure helpers + weight invariants.

The prediction engine produces match-prediction probabilities used in
public Discord commands and OAuth-gated `!predict`. A regression silently:

- Weight invariants drift → predictions over/underweight history vs form.
- Confidence thresholds → "high confidence" tier on noisy predictions.
- Insight selection → wrong message displayed to users.

The pure helpers are testable without DB. Pin them:
- _calculate_confidence: weighted blend of factor confidences
- _score_to_confidence_label: ladder 0.7 / 0.5 / else
- _generate_key_insight: priority cascade
- Weight constants sum to 1.0 (probability invariant)
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.prediction_engine import PredictionEngine


@pytest.fixture
def engine():
    return PredictionEngine(db_adapter=AsyncMock())


# ---------------------------------------------------------------------------
# Weight invariants — class constants must sum to 1.0
# ---------------------------------------------------------------------------


def test_weights_sum_to_one():
    """Predictions blend H2H/Form/Map/Sub by weight. The weights MUST
    sum to 1.0 — otherwise the final probability isn't bounded
    [0,1] and the rendering breaks (>100% win rate displayed)."""
    total = (
        PredictionEngine.H2H_WEIGHT
        + PredictionEngine.FORM_WEIGHT
        + PredictionEngine.MAP_WEIGHT
        + PredictionEngine.SUB_WEIGHT
    )
    assert total == pytest.approx(1.0, abs=1e-9)


def test_h2h_weight_dominates_form():
    """Doc and design intent: H2H is the strongest signal. Pin so a
    refactor that flips H2H/FORM is loud."""
    assert PredictionEngine.H2H_WEIGHT > PredictionEngine.FORM_WEIGHT


def test_form_weight_dominates_map():
    """FORM > MAP > SUB (per the docstring). Pin priority order."""
    assert PredictionEngine.FORM_WEIGHT > PredictionEngine.MAP_WEIGHT


def test_sub_weight_is_zero_until_implemented():
    """Per the comment in source: subs weight is redistributed to 0.0
    until implementation lands. Pin the zero so an accidental
    re-enable on incomplete code doesn't ship."""
    assert PredictionEngine.SUB_WEIGHT == 0.0


def test_min_thresholds_are_sensible():
    """MIN_H2H_MATCHES + MIN_FORM_MATCHES — pin so a regression that
    drops them to 1 silently overstates accuracy."""
    assert PredictionEngine.MIN_H2H_MATCHES >= 3
    assert PredictionEngine.MIN_FORM_MATCHES >= 5


# ---------------------------------------------------------------------------
# _calculate_confidence — weighted blend
# ---------------------------------------------------------------------------


def test_calculate_confidence_all_high(engine):
    """All factors high → 1.0 * sum(weights) = 1.0."""
    out = engine._calculate_confidence(
        {"confidence": "high"},
        {"confidence": "high"},
        {"confidence": "high"},
        {"confidence": "high"},
    )
    assert out == pytest.approx(1.0, abs=1e-9)


def test_calculate_confidence_all_low(engine):
    """All factors low → 0.3 * 1.0 = 0.3."""
    out = engine._calculate_confidence(
        {"confidence": "low"},
        {"confidence": "low"},
        {"confidence": "low"},
        {"confidence": "low"},
    )
    assert out == pytest.approx(0.3, abs=1e-9)


def test_calculate_confidence_mixed_levels(engine):
    """high(H2H=0.45) + medium(Form=0.30) + low(Map=0.25) + low(Sub=0.0):
    1.0*0.45 + 0.6*0.30 + 0.3*0.25 + 0.3*0.0 = 0.45 + 0.18 + 0.075 = 0.705."""
    out = engine._calculate_confidence(
        {"confidence": "high"},
        {"confidence": "medium"},
        {"confidence": "low"},
        {"confidence": "low"},
    )
    assert out == pytest.approx(0.705, abs=1e-9)


def test_calculate_confidence_missing_keys_default_to_low(engine):
    """A factor without 'confidence' key → 'low' default. Pin so a
    new factor that forgets to set confidence doesn't crash with KeyError."""
    out = engine._calculate_confidence({}, {}, {}, {})
    # All default to 'low' → 0.3 each weighted by 1.0
    assert out == pytest.approx(0.3, abs=1e-9)


def test_calculate_confidence_unknown_level_defaults_to_low(engine):
    """Unknown confidence value (e.g. 'super-high') → 0.3 (low)."""
    out = engine._calculate_confidence(
        {"confidence": "super-high"},
        {"confidence": "low"},
        {"confidence": "low"},
        {"confidence": "low"},
    )
    # All effectively low
    assert out == pytest.approx(0.3, abs=1e-9)


# ---------------------------------------------------------------------------
# _score_to_confidence_label
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("score, expected", [
    (1.0,  "high"),
    (0.85, "high"),
    (0.7,  "high"),    # boundary inclusive
    (0.69, "medium"),  # just below
    (0.6,  "medium"),
    (0.5,  "medium"),  # boundary inclusive
    (0.49, "low"),     # just below
    (0.0,  "low"),
])
def test_score_to_label_thresholds(engine, score, expected):
    """Pin the full ladder boundaries: ≥0.7 high, ≥0.5 medium, else low.
    A regression that flips to strict-> silently downgrades borderline
    predictions."""
    assert engine._score_to_confidence_label(score) == expected


# ---------------------------------------------------------------------------
# _generate_key_insight — priority cascade
# ---------------------------------------------------------------------------


def test_insight_prefers_h2h_when_3plus_matches(engine):
    """H2H is highest priority when matches >= 3."""
    out = engine._generate_key_insight(
        {"matches": 5, "details": "Team A 4-1 H2H"},
        {"confidence": "high", "details": "Form details"},
        {},
        {},
    )
    assert out == "Team A 4-1 H2H"


def test_insight_skips_h2h_when_less_than_3_matches(engine):
    """H2H with <3 matches not enough → fall to form."""
    out = engine._generate_key_insight(
        {"matches": 2, "details": "H2H 1-1 (small sample)"},
        {"confidence": "high", "details": "Form is dominant"},
        {},
        {},
    )
    assert out == "Form is dominant"


def test_insight_form_only_when_high_confidence(engine):
    """Medium/low form confidence → not selected. Pin so noise doesn't
    bleed into the embed."""
    out = engine._generate_key_insight(
        {"matches": 0},
        {"confidence": "medium", "details": "weak form signal"},
        {},
        {},
    )
    # Should fall through to default
    assert out == "Limited historical data - prediction may be less accurate"


def test_insight_default_when_no_data(engine):
    """Empty factors → fallback message."""
    out = engine._generate_key_insight({}, {}, {}, {})
    assert "Limited historical data" in out


def test_insight_h2h_priority_beats_high_form(engine):
    """When BOTH conditions met, H2H wins (it's checked first AND the
    function returns the first insight only, not concat)."""
    out = engine._generate_key_insight(
        {"matches": 4, "details": "h2h-msg"},
        {"confidence": "high", "details": "form-msg"},
        {},
        {},
    )
    assert out == "h2h-msg"


def test_insight_uses_h2h_details_field_not_matches(engine):
    """When H2H qualifies, 'details' is what we render (not 'matches')."""
    out = engine._generate_key_insight(
        {"matches": 10, "details": "Team A dominant H2H"},
        {},
        {},
        {},
    )
    assert out == "Team A dominant H2H"
    assert "10" not in out  # match count NOT shown


def test_insight_handles_missing_details_field(engine):
    """`details` field absent → returns empty string (NOT crash)."""
    out = engine._generate_key_insight(
        {"matches": 5},
        {},
        {},
        {},
    )
    # The insight will be the empty string from .get('details', '') — pin observed
    assert out == ""
