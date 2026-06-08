"""Unit tests for the DB-free player-profile metrics.

Covers the three new gibhub.gg-parity formulas (UTRO, bait_score, streaks)
plus the weapon_t name map. These are pure functions feeding the composite
``/api/players/{id}/profile`` endpoint, so a regression here silently corrupts
every profile's advanced/aim numbers.
"""
from __future__ import annotations

import math

import pytest

from website.backend.services.player_profile_metrics import (
    REINF_MULT_TIERS,
    bait_score,
    compute_streaks,
    locale_to_flag,
    reinf_multiplier,
    utro_from_waits,
    weapon_t_name,
)

# ── reinf_multiplier / UTRO ──────────────────────────────────────────────────

@pytest.mark.parametrize(
    "wait,expected",
    [
        (0.0, 0.70),    # fresh spawn → lowest tier
        (2.0, 0.70),    # inclusive ceiling of first tier
        (2.1, 0.85),
        (5.0, 0.85),
        (10.0, 1.00),
        (15.0, 1.10),
        (20.0, 1.20),
        (25.0, 1.30),
        (26.0, 1.40),   # beyond last finite tier → inf tier
        (999.0, 1.40),
    ],
)
def test_reinf_multiplier_tiers(wait, expected):
    assert reinf_multiplier(wait) == expected


def test_reinf_multiplier_matches_tier_table():
    # Lookup must agree with the shared REINF_MULT_TIERS (kis.py contract).
    for upper, mult in REINF_MULT_TIERS:
        probe = upper if math.isfinite(upper) else 100.0
        assert reinf_multiplier(probe) == mult


def test_reinf_multiplier_handles_garbage():
    assert reinf_multiplier(None) == REINF_MULT_TIERS[0][1]
    assert reinf_multiplier(float("nan")) == REINF_MULT_TIERS[0][1]
    assert reinf_multiplier(-5.0) == REINF_MULT_TIERS[0][1]  # clamped to 0


def test_utro_empty():
    out = utro_from_waits([])
    assert out["utro"] == 0.0
    assert out["weighted_kills"] == 0
    assert out["utro_per_kill"] == 0.0


def test_utro_skips_none():
    # Two valid waits (1.0→0.70, 12.0→1.10) plus a None that must be ignored.
    out = utro_from_waits([1.0, None, 12.0])
    assert out["weighted_kills"] == 2
    assert out["utro"] == pytest.approx(0.70 + 1.10)
    assert out["utro_per_kill"] == pytest.approx((0.70 + 1.10) / 2)


# ── bait_score ───────────────────────────────────────────────────────────────

def test_bait_score_no_situations():
    out = bait_score(0, 0)
    assert out["available"] is False
    assert out["score"] == 0.0


def test_bait_score_basic():
    out = bait_score(3, 1)
    assert out["available"] is True
    assert out["score"] == pytest.approx(75.0)
    assert out["trades_made"] == 3
    assert out["untraded_deaths"] == 1


def test_bait_score_clamps_negatives():
    out = bait_score(-5, -2)
    assert out["available"] is False  # both clamp to 0 → no situations


# ── streaks ──────────────────────────────────────────────────────────────────

def test_streaks_empty():
    out = compute_streaks([])
    assert out["current_streak"] == 0
    assert out["current_type"] == ""
    assert out["longest_win"] == 0
    assert out["longest_loss"] == 0


def test_streaks_all_wins():
    out = compute_streaks(["W", "W", "W", "W"])
    assert out["current_type"] == "W"
    assert out["current_streak"] == 4
    assert out["longest_win"] == 4
    assert out["longest_loss"] == 0


def test_streaks_mixed_current_loss():
    # oldest → newest: longest win run is 3, ends on a 2-loss streak
    out = compute_streaks(["L", "W", "W", "W", "L", "L"])
    assert out["longest_win"] == 3
    assert out["longest_loss"] == 2
    assert out["current_type"] == "L"
    assert out["current_streak"] == 2


def test_streaks_draw_breaks_run():
    out = compute_streaks(["W", "W", "D", "W"])
    assert out["longest_win"] == 2
    assert out["current_type"] == "W"
    assert out["current_streak"] == 1


# ── weapon_t name map ────────────────────────────────────────────────────────

def test_weapon_t_known():
    assert weapon_t_name(3) == "MP40"
    assert weapon_t_name(8) == "Thompson"
    assert weapon_t_name(54) == "MP34"


def test_weapon_t_rifle_disambiguation():
    # ids 23 (WP_KAR98) and 31 (WP_K43) are distinct rifles — must not collide.
    # Ground truth: proximity_tracker.lua MOD→WP map (MOD_KAR98→23, MOD_K43→31).
    assert weapon_t_name(23) == "Kar98"
    assert weapon_t_name(31) == "K43"
    assert weapon_t_name(23) != weapon_t_name(31)
    assert weapon_t_name(24) == "M1 Garand (Carbine)"
    assert weapon_t_name(25) == "Garand"


def test_weapon_t_unknown_and_none():
    assert weapon_t_name(None) == "Unknown"
    assert weapon_t_name(9999) == "Weapon 9999"


# ── locale → flag ─────────────────────────────────────────────────────────────

def test_locale_to_flag_known():
    assert locale_to_flag("sl") == {"flag": "🇸🇮", "country": "SI", "locale": "sl"}
    assert locale_to_flag("en-US")["country"] == "US"
    assert locale_to_flag("pt-BR")["country"] == "BR"


def test_locale_to_flag_region_subtag_fallback():
    # Unknown language but a 2-letter region subtag → use the region.
    assert locale_to_flag("xx-NL")["country"] == "NL"


def test_locale_to_flag_invalid():
    assert locale_to_flag(None) is None
    assert locale_to_flag("") is None
    assert locale_to_flag("xx") is None  # no mapping, no region subtag
