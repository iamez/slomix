"""Tests for PlayerMetrics derived-metric calculation in frag_potential.py.

PlayerMetrics is a dataclass that derives FP/KD/DR/HS%/etc. in
__post_init__. The time-dead resolution path has THREE input formats
(raw seconds, raw minutes, percentage ratio) with a strict precedence
order, plus boundary clamps. A regression here would re-shape every
player's FP value for cached sessions silently.

Pin every branch.
"""
from __future__ import annotations

import pytest

from bot.core.frag_potential import (
    PlayerMetrics,
    Playstyle,
    get_playstyle_description,
)


def _metrics(**kw):
    """Build PlayerMetrics with safe defaults; override fields in tests."""
    base = {
        "player_name": "test",
        "player_guid": "abc",
        "kills": 0,
        "deaths": 0,
        "damage_given": 0,
        "damage_received": 0,
        "time_played_seconds": 0,
        "time_dead_ratio": 0.0,
    }
    base.update(kw)
    return PlayerMetrics(**base)


# ---------------------------------------------------------------------------
# time_alive resolution: three input formats with precedence order
# ---------------------------------------------------------------------------


def test_time_alive_uses_raw_seconds_when_provided():
    """time_dead_seconds wins over minutes and ratio."""
    m = _metrics(
        time_played_seconds=600,
        time_dead_seconds=120,        # primary
        time_dead_minutes=999,        # ignored
        time_dead_ratio=99.0,         # ignored
    )
    assert m.time_alive_seconds == 480  # 600 - 120


def test_time_alive_falls_back_to_minutes_when_seconds_zero():
    """When time_dead_seconds=0, minutes wins over ratio."""
    m = _metrics(
        time_played_seconds=600,
        time_dead_seconds=0,
        time_dead_minutes=2.0,        # 120 sec
        time_dead_ratio=99.0,         # ignored
    )
    assert m.time_alive_seconds == 480  # 600 - 120


def test_time_alive_falls_back_to_ratio_when_no_raw():
    """When neither seconds nor minutes are set, use ratio."""
    m = _metrics(
        time_played_seconds=600,
        time_dead_ratio=20.0,  # 20% of 600 = 120 sec dead
    )
    assert m.time_alive_seconds == 480


def test_time_alive_clamps_to_one_when_played_zero():
    """Min floor of 1 second prevents division-by-zero downstream."""
    m = _metrics(time_played_seconds=0)
    assert m.time_alive_seconds == 1


def test_time_alive_clamps_when_dead_exceeds_played():
    """Edge case: dead time > played time → clamped to played → alive=1."""
    m = _metrics(
        time_played_seconds=300,
        time_dead_seconds=500,  # impossibly large
    )
    # dead clamped to 300; alive = max(1, 300-300) = 1
    assert m.time_alive_seconds == 1


def test_time_alive_with_negative_dead_seconds_clamps_to_zero():
    """Negative time_dead_seconds (parser glitch) → 0."""
    m = _metrics(
        time_played_seconds=300,
        time_dead_seconds=-50,  # nonsense input
    )
    # Negative is the falsy branch (`> 0`), so falls through to ratio (=0).
    # time_alive ends up = max(1, 300 - 0) = 300.
    assert m.time_alive_seconds == 300


# ---------------------------------------------------------------------------
# frag_potential
# ---------------------------------------------------------------------------


def test_frag_potential_basic_calculation():
    """FP = (damage_given / time_alive_seconds) * 60."""
    m = _metrics(
        time_played_seconds=600,
        time_dead_seconds=120,        # alive=480s
        damage_given=4_800,           # 480s * 10 dmg/s
    )
    # 4800 / 480 = 10/sec * 60 = 600/min
    assert m.frag_potential == 600.0


def test_frag_potential_zero_when_no_damage():
    m = _metrics(time_played_seconds=300, damage_given=0)
    assert m.frag_potential == 0.0


def test_frag_potential_uses_clamped_time_alive():
    """FP uses the clamped time_alive (≥1 second), so a 0-played player
    with damage doesn't divide by zero."""
    m = _metrics(time_played_seconds=0, damage_given=1000)
    # time_alive=1 (clamped), FP = 1000/1 * 60 = 60000
    assert m.frag_potential == 60000.0


# ---------------------------------------------------------------------------
# kd_ratio
# ---------------------------------------------------------------------------


def test_kd_ratio_basic():
    m = _metrics(kills=15, deaths=10)
    assert m.kd_ratio == 1.5


def test_kd_ratio_handles_zero_deaths_via_max():
    """deaths=0 → divisor max(1, 0) = 1 → KD = kills."""
    m = _metrics(kills=12, deaths=0)
    assert m.kd_ratio == 12.0


def test_kd_ratio_zero_kills_zero_deaths():
    m = _metrics(kills=0, deaths=0)
    assert m.kd_ratio == 0.0


# ---------------------------------------------------------------------------
# damage_ratio
# ---------------------------------------------------------------------------


def test_damage_ratio_basic():
    m = _metrics(damage_given=1500, damage_received=500)
    assert m.damage_ratio == 3.0


def test_damage_ratio_zero_received_via_max():
    m = _metrics(damage_given=1500, damage_received=0)
    assert m.damage_ratio == 1500.0


# ---------------------------------------------------------------------------
# headshot_percentage
# ---------------------------------------------------------------------------


def test_headshot_pct_uses_hit_ratio_when_total_hits_set():
    """Real HS% is hits-on-head / total-hits, NOT kills."""
    m = _metrics(
        kills=10,
        headshot_kills=2,
        headshot_hits=18,
        total_hits=150,
    )
    # 18/150 * 100 = 12.0%
    assert m.headshot_percentage == pytest.approx(12.0)


def test_headshot_pct_falls_back_to_kill_ratio_when_no_hits():
    """Older parser output without hit-region data → kill-ratio fallback.
    Pin the precedence so a future "always use hits" change is loud."""
    m = _metrics(
        kills=10,
        headshot_kills=3,
        headshot_hits=0,
        total_hits=0,
    )
    # 3/10 * 100 = 30% (kill-ratio fallback)
    assert m.headshot_percentage == 30.0


def test_headshot_pct_zero_when_no_data():
    m = _metrics(kills=0, headshot_kills=0, total_hits=0)
    assert m.headshot_percentage == 0.0


def test_headshot_pct_total_hits_takes_precedence_over_kill_ratio():
    """When both data sources are present, hit-ratio MUST win — kill-ratio
    is the fallback for legacy data only."""
    m = _metrics(
        kills=10,
        headshot_kills=10,           # would be 100% via fallback
        headshot_hits=5,
        total_hits=100,              # hit-ratio = 5%
    )
    assert m.headshot_percentage == 5.0


# ---------------------------------------------------------------------------
# time_dead_ratio recomputation when raw seconds/minutes set
# ---------------------------------------------------------------------------


def test_time_dead_ratio_recomputed_from_raw_seconds():
    """When raw seconds are provided, ratio is recomputed for consistency."""
    m = _metrics(
        time_played_seconds=600,
        time_dead_seconds=120,
        time_dead_ratio=99.0,  # bogus input — should be overwritten
    )
    # 120/600 = 20%
    assert m.time_dead_ratio == 20.0


def test_time_dead_ratio_recomputed_from_minutes():
    m = _metrics(
        time_played_seconds=600,
        time_dead_seconds=0,
        time_dead_minutes=3.0,   # = 180 sec
        time_dead_ratio=99.0,    # overwritten
    )
    assert m.time_dead_ratio == 30.0


def test_time_dead_ratio_preserved_when_only_ratio_provided():
    """When raw fields are zero, ratio passes through unchanged."""
    m = _metrics(time_played_seconds=600, time_dead_ratio=25.0)
    assert m.time_dead_ratio == 25.0


# ---------------------------------------------------------------------------
# Playstyle enum properties
# ---------------------------------------------------------------------------


def test_playstyle_enum_exposes_emoji_name_color():
    p = Playstyle.FRAGGER
    assert p.emoji == "🔥"
    assert p.name_display == "Fragger"
    assert p.color == "#FF6B35"


def test_all_playstyles_have_three_tuple_value():
    """Every enum value is (emoji, name, color hex). Pin so future
    additions don't drop a field and break the .emoji/.color accessors."""
    for ps in Playstyle:
        emoji, name, color = ps.value
        assert isinstance(emoji, str)
        assert isinstance(name, str) and name
        assert color.startswith("#") and len(color) == 7


def test_playstyle_balanced_is_default_for_dataclass():
    m = _metrics()
    assert m.playstyle is Playstyle.BALANCED


# ---------------------------------------------------------------------------
# get_playstyle_description
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("playstyle, prefix", [
    (Playstyle.FRAGGER,   "High"),
    (Playstyle.SLAYER,    "Kill"),
    (Playstyle.TANK,      "Absorbs"),
    (Playstyle.MEDIC,     "Support"),
    (Playstyle.SNIPER,    "Precision"),
    (Playstyle.RUSHER,    "Aggressive"),
    (Playstyle.OBJECTIVE, "Mission"),
    (Playstyle.BALANCED,  "Well-rounded"),
])
def test_get_playstyle_description_each_known(playstyle, prefix):
    out = get_playstyle_description(playstyle)
    assert out.startswith(prefix), f"{playstyle.name} should start with '{prefix}'"


def test_get_playstyle_description_all_eight_covered():
    """Every Playstyle enum value has a description entry."""
    for ps in Playstyle:
        assert get_playstyle_description(ps) != "Unknown playstyle"
