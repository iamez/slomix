"""Tests for StorytellingService._classify_archetype.

This is the priority-based decision tree that produces every player's
archetype label on the Smart Stats page. Until now: zero tests despite
9 distinct branches and a relative-to-session threshold model that
silently changes label for every player when an upstream stat shifts.

Pin each branch's entry condition AND the priority order — the first
match wins, so re-ordering the if-blocks would silently re-label
players for already-computed sessions.
"""
from __future__ import annotations

import pytest

from website.backend.services.storytelling.service import StorytellingService


def _stats(**kw):
    """Build a stats dict with sane zeroed defaults for any field that
    `_classify_archetype` reads. Override only what the test needs."""
    base = {
        "pcs_kills": 0, "kills": 0, "deaths": 1,
        "carrier_kills": 0, "carrier_returns": 0,
        "revives_given": 0, "trade_kills": 0, "crossfire_kills": 0,
        "push_kills": 0, "headshot_pct": 0.0, "dpm": 0,
        "denied_time": 0, "time_dead_pct": 0.0,
    }
    base.update(kw)
    return base


def _avgs(**kw):
    """Session averages — leave at sane mid-range values so single
    overrides don't accidentally trip multiple branches."""
    base = {
        "avg_kills": 10, "avg_trades": 5, "avg_revives": 10,
        "avg_kd": 1.0, "avg_dpm": 100, "avg_denied": 50,
        "avg_time_dead_pct": 0.20,
    }
    base.update(kw)
    return base


def _classify(stats, avgs=None):
    return StorytellingService._classify_archetype(stats, avgs or _avgs())


# ---------------------------------------------------------------------------
# Each archetype's entry condition (most-specific first per production order)
# ---------------------------------------------------------------------------


def test_objective_specialist_via_carrier_kills_threshold():
    """3+ carrier kills → objective_specialist regardless of other stats."""
    assert _classify(_stats(carrier_kills=3)) == "objective_specialist"
    assert _classify(_stats(carrier_kills=10)) == "objective_specialist"


def test_objective_specialist_via_carrier_returns_threshold():
    """2+ carrier returns → objective_specialist (alternative trigger)."""
    assert _classify(_stats(carrier_returns=2)) == "objective_specialist"


def test_carrier_kills_below_threshold_does_not_trigger_objective():
    """2 carrier kills + 1 return → not enough → falls through."""
    result = _classify(_stats(carrier_kills=2, carrier_returns=1))
    assert result != "objective_specialist"


def test_pressure_engine_via_high_dpm_and_kills():
    """DPM ≥ 1.12x avg AND kills ≥ 1.05x avg → pressure_engine."""
    avgs = _avgs(avg_kills=10, avg_dpm=100)
    stats = _stats(pcs_kills=11, dpm=120)
    assert _classify(stats, avgs) == "pressure_engine"


def test_pressure_engine_via_high_kills_and_kd():
    """kills ≥ 1.1x avg AND kd ≥ 1.15x avg → pressure_engine (alt trigger)."""
    avgs = _avgs(avg_kills=10, avg_kd=1.0, avg_dpm=100)
    stats = _stats(pcs_kills=12, deaths=10, dpm=80)  # kd=1.2
    assert _classify(stats, avgs) == "pressure_engine"


def test_medic_anchor_requires_both_relative_and_absolute_threshold():
    """1.35x avg revives AND >= 20 absolute → medic_anchor."""
    avgs = _avgs(avg_revives=10)
    assert _classify(_stats(revives_given=20), avgs) == "medic_anchor"
    # 19 revives misses the absolute floor → falls through
    assert _classify(_stats(revives_given=19), avgs) != "medic_anchor"


def test_medic_anchor_misses_when_below_relative_threshold():
    """20 absolute is enough only when revives >= 1.35 * avg.
    avg=20 → need >=27."""
    avgs = _avgs(avg_revives=20)
    assert _classify(_stats(revives_given=20), avgs) != "medic_anchor"


def test_silent_assassin_requires_hs_pct_and_kd():
    """headshot_pct ≥ 0.12 AND kd ≥ 1.05x avg."""
    avgs = _avgs(avg_kd=1.0)
    stats = _stats(pcs_kills=11, deaths=10, headshot_pct=0.15)  # kd=1.1
    assert _classify(stats, avgs) == "silent_assassin"


def test_silent_assassin_skipped_when_hs_too_low():
    """hs_pct=0.10 below 0.12 threshold → not silent_assassin."""
    avgs = _avgs(avg_kd=1.0)
    stats = _stats(pcs_kills=12, deaths=10, headshot_pct=0.10)
    assert _classify(stats, avgs) != "silent_assassin"


def test_chaos_agent_high_dpm_low_kd():
    """DPM ≥ 0.95x avg AND kd < 0.75x avg → chaos_agent (aggressive reckless)."""
    avgs = _avgs(avg_dpm=100, avg_kd=1.0)
    stats = _stats(pcs_kills=4, deaths=10, dpm=100)  # kd=0.4
    assert _classify(stats, avgs) == "chaos_agent"


def test_wall_breaker_via_denied_time():
    """denied_time ≥ 1.2x avg AND >= 100 absolute."""
    avgs = _avgs(avg_denied=50)
    stats = _stats(denied_time=120)
    assert _classify(stats, avgs) == "wall_breaker"


def test_wall_breaker_below_absolute_floor():
    """denied=99 below absolute 100 → falls through even if relative satisfied."""
    avgs = _avgs(avg_denied=50)
    stats = _stats(denied_time=99)
    assert _classify(stats, avgs) != "wall_breaker"


def test_trade_master_via_trade_kills():
    """trades ≥ 1.25x avg AND >= 10 absolute."""
    avgs = _avgs(avg_trades=5)
    stats = _stats(trade_kills=10)
    assert _classify(stats, avgs) == "trade_master"


def test_survivor_via_high_kd_and_low_time_dead():
    """kd ≥ 1.2x avg AND time_dead_pct ≤ 0.85x avg.

    Must keep kills below the pressure_engine 1.1x threshold so we
    isolate the survivor branch (otherwise pressure_engine fires first).
    """
    avgs = _avgs(avg_kills=10, avg_kd=1.0, avg_time_dead_pct=0.20)
    # kills=10 (= avg, fails 1.1x), kd=1.25, time_dead 0.10 (< 0.20*0.85=0.17)
    stats = _stats(pcs_kills=10, deaths=8, time_dead_pct=0.10)
    assert _classify(stats, avgs) == "survivor"


def test_survivor_fallback_via_dominant_kd_alone():
    """kd ≥ 1.3x avg without low time_dead context still earns survivor.

    Again kills=avg so pressure_engine doesn't fire first.
    """
    avgs = _avgs(avg_kills=10, avg_kd=1.0, avg_time_dead_pct=0.20)
    # kills=10 (= avg), kd=1.4 (1.4 ≥ 1.3*1.0=1.3), high time_dead so the
    # AND-survivor branch fails and we fall to the fallback.
    stats = _stats(pcs_kills=10, deaths=7, time_dead_pct=0.30)
    assert _classify(stats, avgs) == "survivor"


def test_frontline_warrior_via_push_kills():
    """push_kills >= 8 → frontline_warrior."""
    stats = _stats(push_kills=8)
    assert _classify(stats) == "frontline_warrior"


def test_frontline_warrior_via_crossfire_kills():
    """crossfire >= 5 → frontline_warrior."""
    stats = _stats(crossfire_kills=5)
    assert _classify(stats) == "frontline_warrior"


def test_frontline_warrior_fallback_when_no_archetype_fits():
    """Empty stats default to frontline_warrior (catch-all)."""
    assert _classify(_stats()) == "frontline_warrior"


# ---------------------------------------------------------------------------
# Priority order: first match in the if-cascade wins
# ---------------------------------------------------------------------------


def test_objective_beats_pressure():
    """Player with both carrier_kills=3 AND high DPM+kills → objective wins."""
    avgs = _avgs(avg_kills=10, avg_dpm=100)
    stats = _stats(carrier_kills=3, pcs_kills=15, dpm=200)
    assert _classify(stats, avgs) == "objective_specialist"


def test_pressure_beats_silent_assassin():
    """High DPM + kills wins over high HS% + KD."""
    avgs = _avgs(avg_kills=10, avg_kd=1.0, avg_dpm=100)
    stats = _stats(pcs_kills=12, deaths=10, dpm=120, headshot_pct=0.15)
    assert _classify(stats, avgs) == "pressure_engine"


def test_medic_anchor_beats_survivor_even_when_kd_qualifies():
    """20+ revives @ 1.35x avg trumps later survivor branch.

    Keep kills below pressure_engine threshold so medic_anchor branch
    is isolated: avg_kills=20, kills=10 fails 1.1x.
    """
    avgs = _avgs(avg_kills=20, avg_revives=10, avg_kd=1.0, avg_time_dead_pct=0.20)
    stats = _stats(
        revives_given=20, pcs_kills=10, deaths=7, time_dead_pct=0.10,
    )
    assert _classify(stats, avgs) == "medic_anchor"


def test_session_stats_default_to_self_when_omitted():
    """If session_stats is None, the player is compared to themself —
    all relative thresholds collapse to ratio=1.0 → falls into the
    catch-all frontline_warrior. Calls the underlying classmethod
    directly so no avgs fixture interferes."""
    stats = _stats(pcs_kills=10, deaths=5, dpm=100)
    # Bypass _classify's `avgs or _avgs()` default — pass None straight through
    result = StorytellingService._classify_archetype(stats, None)
    assert result == "frontline_warrior"


def test_zero_deaths_does_not_divide_by_zero():
    """deaths=0 must use max(deaths, 1) to avoid ZeroDivisionError."""
    avgs = _avgs(avg_kd=1.0)
    stats = _stats(pcs_kills=5, deaths=0, headshot_pct=0.20)
    # Should not raise; KD = 5/1 = 5.0 (much above avg)
    label = _classify(stats, avgs)
    assert isinstance(label, str)


# ---------------------------------------------------------------------------
# Stats-source compat: pcs_kills vs kills
# ---------------------------------------------------------------------------


def test_pcs_kills_takes_precedence_over_kills():
    """pcs_kills is the authoritative count when both are provided."""
    avgs = _avgs(avg_kills=10, avg_kd=1.0)
    stats = _stats(pcs_kills=15, kills=3, deaths=10)  # PCS=15 should win
    # 15 ≥ 1.1*10 AND kd=1.5 ≥ 1.15 → pressure_engine
    assert _classify(stats, avgs) == "pressure_engine"


def test_falls_back_to_kills_when_pcs_kills_missing():
    """Older stats payloads omit pcs_kills."""
    avgs = _avgs(avg_kills=10, avg_kd=1.0)
    stats = _stats(kills=15, deaths=10)
    stats.pop("pcs_kills")  # simulate older payload
    assert _classify(stats, avgs) == "pressure_engine"
