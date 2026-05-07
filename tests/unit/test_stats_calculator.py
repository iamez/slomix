"""Tests for StatsCalculator — centralised stat formulas.

This module is the single source of truth for DPM/KD/ACC/EFF/HS%/ADR/
KPR/DPR + safe-divide primitives. Every parser, cog, and DB aggregation
imports it. A regression in any formula silently corrupts the headline
numbers shown on the leaderboard, player profile, and round embeds.

Pin every formula + every NULL/zero-safe edge.
"""
from __future__ import annotations

import pytest

from bot.stats.calculator import StatsCalculator

# ---------------------------------------------------------------------------
# calculate_dpm
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("damage, time_seconds, expected", [
    (1200, 300,  240.0),   # 1200 * 60 / 300 = 240
    (3000, 600,  300.0),
    (60,   60,   60.0),
    (0,    300,  0.0),     # zero damage
])
def test_dpm_basic(damage, time_seconds, expected):
    assert StatsCalculator.calculate_dpm(damage, time_seconds) == expected


def test_dpm_zero_time_returns_default():
    """Zero time → default (avoid ZeroDivisionError)."""
    assert StatsCalculator.calculate_dpm(1200, 0) == 0.0


def test_dpm_none_inputs_return_default():
    assert StatsCalculator.calculate_dpm(None, 100) == 0.0
    assert StatsCalculator.calculate_dpm(100, None) == 0.0
    assert StatsCalculator.calculate_dpm(None, None) == 0.0


def test_dpm_custom_default():
    """Default arg is configurable for callers that need NaN sentinel."""
    assert StatsCalculator.calculate_dpm(None, 100, default=-1.0) == -1.0


def test_dpm_handles_string_input_gracefully():
    """TypeError on non-numeric → default. Pinned so a parser glitch
    doesn't crash the entire round import."""
    assert StatsCalculator.calculate_dpm("abc", 100) == 0.0


# ---------------------------------------------------------------------------
# calculate_kd
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kills, deaths, expected", [
    (20, 10,  2.0),
    (15, 5,   3.0),
    (10, 10,  1.0),
    (0,  10,  0.0),
])
def test_kd_basic(kills, deaths, expected):
    assert StatsCalculator.calculate_kd(kills, deaths) == expected


def test_kd_zero_deaths_returns_kills_as_float():
    """Special: deaths=0 → return kills as float (perfect K/D).
    Pinned because a "return inf" or "return 999" choice is also
    plausible — we explicitly return kills, not a sentinel."""
    out = StatsCalculator.calculate_kd(15, 0)
    assert out == 15.0
    assert isinstance(out, float)


def test_kd_none_kills_returns_default():
    assert StatsCalculator.calculate_kd(None, 10) == 0.0


def test_kd_none_deaths_treated_as_zero():
    """deaths=None handled like deaths=0 → returns kills."""
    assert StatsCalculator.calculate_kd(15, None) == 15.0


def test_kd_zero_kills_zero_deaths_returns_zero():
    """0/0 → 0 (because deaths==0 path returns float(kills)=0.0)."""
    assert StatsCalculator.calculate_kd(0, 0) == 0.0


# ---------------------------------------------------------------------------
# calculate_accuracy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("hits, shots, expected", [
    (50, 100, 50.0),
    (25, 100, 25.0),
    (100, 100, 100.0),
    (0, 100, 0.0),
])
def test_accuracy_percentage(hits, shots, expected):
    assert StatsCalculator.calculate_accuracy(hits, shots) == expected


def test_accuracy_as_ratio_when_flag_false():
    """as_percentage=False → returns 0.0-1.0 ratio."""
    assert StatsCalculator.calculate_accuracy(50, 100, as_percentage=False) == 0.5


def test_accuracy_zero_shots_returns_default():
    """Avoid divide-by-zero (no shots fired)."""
    assert StatsCalculator.calculate_accuracy(0, 0) == 0.0


def test_accuracy_none_inputs_return_default():
    assert StatsCalculator.calculate_accuracy(None, 100) == 0.0
    assert StatsCalculator.calculate_accuracy(50, None) == 0.0


# ---------------------------------------------------------------------------
# calculate_efficiency
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kills, deaths, expected", [
    (15, 5,   75.0),     # 15/(15+5) = 0.75
    (10, 0,   100.0),    # perfect
    (0,  10,  0.0),
    (20, 20,  50.0),
])
def test_efficiency_percentage(kills, deaths, expected):
    assert StatsCalculator.calculate_efficiency(kills, deaths) == expected


def test_efficiency_returns_default_when_total_engagements_zero():
    """0 kills + 0 deaths → 0/0 → default."""
    assert StatsCalculator.calculate_efficiency(0, 0) == 0.0


def test_efficiency_none_kills_treated_as_zero():
    """None inputs are coerced to 0 in this method (NOT default like others).
    Pin observed behaviour — a regression that early-returns on None
    would silently zero the metric for unrelated rows."""
    # None kills + 10 deaths → 0/(0+10) = 0%
    assert StatsCalculator.calculate_efficiency(None, 10) == 0.0


def test_efficiency_none_deaths_treated_as_zero():
    """None deaths + 10 kills → 10/(10+0) = 100%."""
    assert StatsCalculator.calculate_efficiency(10, None) == 100.0


def test_efficiency_as_ratio():
    assert StatsCalculator.calculate_efficiency(15, 5, as_percentage=False) == 0.75


# ---------------------------------------------------------------------------
# calculate_headshot_accuracy
# ---------------------------------------------------------------------------


def test_headshot_accuracy_basic():
    """50/200 = 25.0%."""
    assert StatsCalculator.calculate_headshot_accuracy(50, 200) == 25.0


def test_headshot_accuracy_zero_total_hits_returns_default():
    """No hits → no accuracy. Avoid divide-by-zero."""
    assert StatsCalculator.calculate_headshot_accuracy(0, 0) == 0.0


def test_headshot_accuracy_none_inputs_return_default():
    assert StatsCalculator.calculate_headshot_accuracy(None, 100) == 0.0
    assert StatsCalculator.calculate_headshot_accuracy(50, None) == 0.0


def test_headshot_accuracy_alias_calculate_headshot_percentage():
    """calculate_headshot_percentage is a deprecated alias for accuracy.
    Pin so a future cleanup doesn't accidentally remove the alias and
    break legacy callers."""
    assert (
        StatsCalculator.calculate_headshot_percentage(50, 200)
        == StatsCalculator.calculate_headshot_accuracy(50, 200)
    )


# ---------------------------------------------------------------------------
# calculate_headshot_kill_rate
# ---------------------------------------------------------------------------


def test_headshot_kill_rate_basic():
    """5/20 = 25%."""
    assert StatsCalculator.calculate_headshot_kill_rate(5, 20) == 25.0


def test_headshot_kill_rate_zero_total_kills():
    assert StatsCalculator.calculate_headshot_kill_rate(0, 0) == 0.0


def test_headshot_kill_rate_distinct_from_accuracy():
    """Pin that kill_rate and accuracy are SEPARATE formulas with the
    same shape — a refactor that merged them would lose the named
    distinction in the API."""
    # Same numerator/denominator different semantics
    accuracy = StatsCalculator.calculate_headshot_accuracy(10, 50)
    kill_rate = StatsCalculator.calculate_headshot_kill_rate(10, 50)
    assert accuracy == kill_rate == 20.0


# ---------------------------------------------------------------------------
# calculate_adr / calculate_kpr / calculate_dpr
# ---------------------------------------------------------------------------


def test_adr_basic():
    assert StatsCalculator.calculate_adr(3000, 4) == 750.0


def test_adr_rounds_played_zero_returns_default():
    """rounds_played=0 → default (no division)."""
    assert StatsCalculator.calculate_adr(3000, 0) == 0.0


def test_adr_negative_rounds_returns_default():
    """rounds_played < 0 (corrupt data) → default. Pin fail-safe."""
    assert StatsCalculator.calculate_adr(3000, -1) == 0.0


def test_adr_none_inputs_return_default():
    assert StatsCalculator.calculate_adr(None, 4) == 0.0
    assert StatsCalculator.calculate_adr(3000, None) == 0.0


def test_kpr_rounds_to_two_decimals():
    """7/3 = 2.333… → rounded to 2.33. Pin so a future "no rounding"
    change is loud (would break leaderboard sort tie-breakers)."""
    assert StatsCalculator.calculate_kpr(7, 3) == 2.33


def test_kpr_clean_division_returns_unrounded_int_value():
    """20/4 = 5.0 — no rounding needed."""
    assert StatsCalculator.calculate_kpr(20, 4) == 5.0


def test_kpr_zero_rounds_returns_default():
    assert StatsCalculator.calculate_kpr(20, 0) == 0.0


def test_dpr_rounds_to_two_decimals():
    """5/3 = 1.666… → 1.67."""
    assert StatsCalculator.calculate_dpr(5, 3) == 1.67


def test_dpr_clean_division():
    assert StatsCalculator.calculate_dpr(12, 4) == 3.0


def test_dpr_zero_rounds_returns_default():
    assert StatsCalculator.calculate_dpr(12, 0) == 0.0


def test_dpr_none_returns_default():
    assert StatsCalculator.calculate_dpr(None, 4) == 0.0
    assert StatsCalculator.calculate_dpr(12, None) == 0.0


# ---------------------------------------------------------------------------
# safe_divide / safe_percentage
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("num, denom, expected", [
    (100, 4,  25.0),
    (10, 4,   2.5),
    (0,  10,  0.0),
])
def test_safe_divide_basic(num, denom, expected):
    assert StatsCalculator.safe_divide(num, denom) == expected


def test_safe_divide_zero_denom_returns_default():
    assert StatsCalculator.safe_divide(10, 0) == 0.0


def test_safe_divide_none_returns_default():
    assert StatsCalculator.safe_divide(None, 5) == 0.0
    assert StatsCalculator.safe_divide(5, None) == 0.0


def test_safe_divide_custom_default():
    assert StatsCalculator.safe_divide(10, 0, default=-1.0) == -1.0


def test_safe_divide_handles_floats():
    """The signature accepts float inputs too."""
    assert StatsCalculator.safe_divide(10.5, 2.0) == 5.25


def test_safe_percentage_basic():
    assert StatsCalculator.safe_percentage(25, 100) == 25.0
    assert StatsCalculator.safe_percentage(3, 4) == 75.0


def test_safe_percentage_zero_total_returns_default():
    """5/0 → division returns default (0.0); * 100 stays 0."""
    assert StatsCalculator.safe_percentage(5, 0) == 0.0


def test_safe_percentage_none_returns_default():
    assert StatsCalculator.safe_percentage(None, 100) == 0.0
    assert StatsCalculator.safe_percentage(50, None) == 0.0
