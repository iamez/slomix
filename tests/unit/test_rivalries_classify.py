"""Tests for rivalries_service._classify — H2H relationship classifier.

This module classifies player vs player encounters into NEMESIS / PREY
/ RIVAL / CONTENDER / INSUFFICIENT_DATA buckets. The result drives the
"Your Rivals" page on the website. A regression silently:

- Threshold drift (PREY at 60% instead of 70%) → easy fights labeled
  as dominance.
- Classify INSUFFICIENT_DATA tier wrong → skews the rivalries list
  with one-off matches.
- 30-40% gap returns CONTENDER (not NEMESIS/RIVAL) — pin the
  intentional gap so a refactor that closes it is loud.

Pin every threshold + boundary case.
"""
from __future__ import annotations

import pytest

from website.backend.services.rivalries_service import (
    MIN_ENCOUNTERS,
    _classify,
)

# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA — sample size guard
# ---------------------------------------------------------------------------


def test_insufficient_data_when_total_below_threshold():
    """<5 encounters → INSUFFICIENT_DATA regardless of win rate.
    Pin so a 1-encounter matchup doesn't get tagged as NEMESIS
    based on a single ambush."""
    assert _classify(win_rate=1.0, total=4) == "INSUFFICIENT_DATA"
    assert _classify(win_rate=0.0, total=4) == "INSUFFICIENT_DATA"
    assert _classify(win_rate=0.5, total=4) == "INSUFFICIENT_DATA"


def test_insufficient_data_at_zero_total():
    assert _classify(win_rate=0.0, total=0) == "INSUFFICIENT_DATA"


def test_min_encounters_constant_pinned():
    """The MIN_ENCOUNTERS constant is exposed; pin its value so a
    bump (e.g., 10) is a deliberate decision, not silent."""
    assert MIN_ENCOUNTERS == 5


def test_threshold_at_5_encounters_no_longer_insufficient():
    """5 encounters is the minimum — at this threshold, classification
    proceeds. Pin the strict-< boundary."""
    out = _classify(win_rate=0.5, total=5)
    assert out != "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# PREY — you kill them ≥70% of the time
# ---------------------------------------------------------------------------


def test_prey_at_exactly_70pct():
    """≥0.70 → PREY. Pin inclusive boundary."""
    assert _classify(win_rate=0.70, total=10) == "PREY"


def test_prey_above_70pct():
    assert _classify(win_rate=0.85, total=10) == "PREY"


def test_prey_at_100pct():
    assert _classify(win_rate=1.0, total=10) == "PREY"


def test_prey_just_below_70pct_is_contender():
    """0.69 → CONTENDER (NOT PREY). Pin strict ≥ at 0.70."""
    assert _classify(win_rate=0.69, total=10) == "CONTENDER"


# ---------------------------------------------------------------------------
# NEMESIS — they kill you ≥70% of the time (win_rate ≤30%)
# ---------------------------------------------------------------------------


def test_nemesis_at_exactly_30pct():
    """≤0.30 → NEMESIS. Pin inclusive boundary."""
    assert _classify(win_rate=0.30, total=10) == "NEMESIS"


def test_nemesis_below_30pct():
    assert _classify(win_rate=0.15, total=10) == "NEMESIS"


def test_nemesis_at_zero_pct():
    """0% wins → NEMESIS (clean dominance)."""
    assert _classify(win_rate=0.0, total=10) == "NEMESIS"


def test_nemesis_just_above_30pct_is_contender():
    """0.31 → CONTENDER (NOT NEMESIS). Pin strict ≤ at 0.30."""
    assert _classify(win_rate=0.31, total=10) == "CONTENDER"


# ---------------------------------------------------------------------------
# RIVAL — balanced (40-60%)
# ---------------------------------------------------------------------------


def test_rival_at_exactly_50pct():
    """50/50 → RIVAL (the canonical balanced matchup)."""
    assert _classify(win_rate=0.50, total=10) == "RIVAL"


def test_rival_at_40pct_lower_boundary():
    """0.40 → RIVAL (inclusive lower bound)."""
    assert _classify(win_rate=0.40, total=10) == "RIVAL"


def test_rival_at_60pct_upper_boundary():
    """0.60 → RIVAL (inclusive upper bound). Pin so a regression
    that flips to <0.60 silently kicks 60% matchups into CONTENDER."""
    assert _classify(win_rate=0.60, total=10) == "RIVAL"


@pytest.mark.parametrize("rate", [0.45, 0.50, 0.55])
def test_rival_in_middle_of_range(rate):
    assert _classify(win_rate=rate, total=10) == "RIVAL"


# ---------------------------------------------------------------------------
# CONTENDER — the 30-40% and 60-70% gaps
# ---------------------------------------------------------------------------


def test_contender_in_lower_gap():
    """30% < win_rate < 40% → CONTENDER (gap between NEMESIS and RIVAL).
    Pin the intentional gap — a refactor that closes it would re-label
    every losing-edge matchup as RIVAL."""
    assert _classify(win_rate=0.31, total=10) == "CONTENDER"
    assert _classify(win_rate=0.35, total=10) == "CONTENDER"
    assert _classify(win_rate=0.39, total=10) == "CONTENDER"


def test_contender_in_upper_gap():
    """60% < win_rate < 70% → CONTENDER (gap between RIVAL and PREY)."""
    assert _classify(win_rate=0.61, total=10) == "CONTENDER"
    assert _classify(win_rate=0.65, total=10) == "CONTENDER"
    assert _classify(win_rate=0.69, total=10) == "CONTENDER"


# ---------------------------------------------------------------------------
# Full ladder — exhaustive boundary table
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("win_rate, expected", [
    # NEMESIS regime
    (0.00, "NEMESIS"),
    (0.15, "NEMESIS"),
    (0.30, "NEMESIS"),  # boundary inclusive
    # CONTENDER lower gap
    (0.31, "CONTENDER"),
    (0.39, "CONTENDER"),
    # RIVAL regime
    (0.40, "RIVAL"),    # boundary inclusive
    (0.50, "RIVAL"),
    (0.60, "RIVAL"),    # boundary inclusive
    # CONTENDER upper gap
    (0.61, "CONTENDER"),
    (0.69, "CONTENDER"),
    # PREY regime
    (0.70, "PREY"),     # boundary inclusive
    (0.85, "PREY"),
    (1.00, "PREY"),
])
def test_full_classification_ladder(win_rate, expected):
    """Pin the entire table at once — a threshold tweak in any tier
    fails immediately."""
    assert _classify(win_rate=win_rate, total=10) == expected


# ---------------------------------------------------------------------------
# Sample-size guard takes precedence over win rate
# ---------------------------------------------------------------------------


def test_insufficient_data_takes_precedence_over_extreme_win_rate():
    """100% win rate but only 3 encounters → INSUFFICIENT_DATA, NOT
    PREY. Pin the precedence so a 3-game streak doesn't masquerade
    as dominance."""
    assert _classify(win_rate=1.0, total=3) == "INSUFFICIENT_DATA"
    assert _classify(win_rate=0.0, total=3) == "INSUFFICIENT_DATA"
