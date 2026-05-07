"""Tests for PlayerAnalyticsService formatters + dataclass schemas.

These dataclasses + format_* methods underpin the !consistency, !mapaff,
!playstyle, and !awards Discord commands. A regression silently:

- Dataclass field default drift → callers that omit fields after a
  field rename get TypeError on init.
- `format_consistency` rounds incorrectly → tier displayed wrong.
- `format_map_affinity` sort flips → "best map" actually shows worst.
- `format_map_affinity` emoji thresholds drift → +5% map (basically
  average) shows green-best.
- `format_playstyle` preference emoji missing → embed shows raw
  preference text.
- `format_awards` empty list crashes embed with no fallback.

Pin every formatter and dataclass default.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from bot.services.player_analytics_service import (
    ConsistencyStats,
    FunAward,
    MapAffinityStats,
    PlayerAnalyticsService,
    PlaystyleStats,
    SessionFatigueStats,
)

# ---------------------------------------------------------------------------
# Dataclass schemas — pin field defaults
# ---------------------------------------------------------------------------


def test_consistency_stats_minimal_init():
    """Only player_guid + player_name required. All other fields have
    safe defaults so a partial computation can still be returned."""
    s = ConsistencyStats(player_guid="g1", player_name="alice")
    assert s.avg_dpm == 0.0
    assert s.std_dev_dpm == 0.0
    assert s.consistency_score == 0.0
    assert s.consistency_tier == "Unknown"
    assert s.rounds_analyzed == 0
    assert s.recent_variance == "stable"


def test_map_affinity_stats_minimal_init():
    """Empty map_stats dict, None best/worst. Pin so a player with
    no map data round-trips through Discord embed without crashing."""
    s = MapAffinityStats(player_guid="g1", player_name="alice")
    assert s.overall_dpm == 0.0
    assert s.map_stats == {}
    assert s.best_map is None
    assert s.worst_map is None
    assert s.best_map_delta == 0.0
    assert s.worst_map_delta == 0.0


def test_map_affinity_stats_independent_dict_per_instance():
    """`field(default_factory=dict)` — each instance gets its own dict.
    Pin so a mutable-default-class-attribute bug doesn't cause cross-
    player pollution."""
    a = MapAffinityStats(player_guid="g1", player_name="alice")
    b = MapAffinityStats(player_guid="g2", player_name="bob")
    a.map_stats["oasis"] = {"dpm": 500}
    assert b.map_stats == {}


def test_playstyle_stats_balanced_default():
    """Default preference="balanced" — never raw "Unknown". Pin so an
    embed always shows a meaningful preference badge."""
    s = PlaystyleStats(player_guid="g1", player_name="alice")
    assert s.preference == "balanced"
    assert s.preference_strength == 0.0


def test_session_fatigue_stats_zero_defaults():
    s = SessionFatigueStats(session_date="2026-05-07", gaming_session_id=42)
    assert s.early_dpm == 0.0
    assert s.mid_dpm == 0.0
    assert s.late_dpm == 0.0
    assert s.fatigue_index == 0.0
    assert s.trend == "stable"


def test_fun_award_required_fields():
    """All FunAward fields are required (no defaults). Pin schema —
    a refactor that adds `field()` default would silently break the
    "every field is set" promise that downstream embed rendering relies
    on."""
    award = FunAward(
        award_name="MVP",
        emoji="🏆",
        player_guid="g1",
        player_name="alice",
        value=42.0,
        description="Best DPM",
    )
    assert award.award_name == "MVP"
    assert award.player_name == "alice"
    assert award.value == 42.0


# ---------------------------------------------------------------------------
# format_consistency
# ---------------------------------------------------------------------------


def _service():
    """Build a service with a mock db; format methods don't touch DB."""
    return PlayerAnalyticsService(db_adapter=MagicMock())


def test_format_consistency_includes_all_required_fields():
    s = ConsistencyStats(
        player_guid="g1",
        player_name="alice",
        avg_dpm=520.5,
        std_dev_dpm=45.2,
        consistency_score=78.0,
        consistency_tier="Consistent",
        rounds_analyzed=25,
        recent_variance="improving",
    )
    out = _service().format_consistency(s)
    assert "alice" in out
    assert "78/100" in out
    assert "Consistent" in out
    assert "520.5" in out
    assert "45.2" in out
    assert "improving" in out
    assert "25" in out


def test_format_consistency_score_rounded_to_zero_decimals():
    """Score `:.0f` — pin so the displayed score is integer (NOT
    "78.000000")."""
    s = ConsistencyStats(
        player_guid="g1", player_name="alice",
        consistency_score=78.456,
        consistency_tier="Consistent",
    )
    out = _service().format_consistency(s)
    assert "78/100" in out
    assert "78.456" not in out


# ---------------------------------------------------------------------------
# format_map_affinity
# ---------------------------------------------------------------------------


def test_format_map_affinity_sorts_by_delta_descending():
    """Maps sorted by delta_percent descending — top = best map. Pin
    so a sort flip doesn't display worst-first."""
    s = MapAffinityStats(
        player_guid="g1",
        player_name="alice",
        overall_dpm=500.0,
        map_stats={
            "worst_map": {"dpm": 400.0, "delta_percent": -20.0, "rounds": 5,
                          "kills": 10, "deaths": 15, "kd": 0.67},
            "best_map":  {"dpm": 600.0, "delta_percent": 20.0,  "rounds": 5,
                          "kills": 30, "deaths": 10, "kd": 3.0},
            "neutral":   {"dpm": 510.0, "delta_percent": 2.0,   "rounds": 5,
                          "kills": 15, "deaths": 12, "kd": 1.25},
        },
    )
    out = _service().format_map_affinity(s)
    # Best appears before worst in output text
    assert out.index("best_map") < out.index("neutral") < out.index("worst_map")


def test_format_map_affinity_uses_green_emoji_for_above_10pct():
    """delta > 10 → 🟢."""
    s = MapAffinityStats(
        player_guid="g1", player_name="alice", overall_dpm=500.0,
        map_stats={"good": {"dpm": 600.0, "delta_percent": 20.0, "rounds": 5,
                            "kills": 0, "deaths": 0, "kd": 0.0}},
    )
    out = _service().format_map_affinity(s)
    assert "🟢" in out


def test_format_map_affinity_uses_red_emoji_for_below_minus_10pct():
    """delta < -10 → 🔴."""
    s = MapAffinityStats(
        player_guid="g1", player_name="alice", overall_dpm=500.0,
        map_stats={"bad": {"dpm": 400.0, "delta_percent": -20.0, "rounds": 5,
                           "kills": 0, "deaths": 0, "kd": 0.0}},
    )
    out = _service().format_map_affinity(s)
    assert "🔴" in out


def test_format_map_affinity_uses_neutral_emoji_inside_threshold():
    """-10 ≤ delta ≤ 10 → ⚪. Pin so a near-average map doesn't
    falsely look "best" or "worst"."""
    s = MapAffinityStats(
        player_guid="g1", player_name="alice", overall_dpm=500.0,
        map_stats={"neutral": {"dpm": 505.0, "delta_percent": 5.0, "rounds": 5,
                               "kills": 0, "deaths": 0, "kd": 0.0}},
    )
    out = _service().format_map_affinity(s)
    assert "⚪" in out
    assert "🟢" not in out
    assert "🔴" not in out


def test_format_map_affinity_caps_to_six_maps():
    """Top 6 maps shown. Pin so a player with 20 maps doesn't blow
    Discord's 1024-char field limit."""
    map_stats = {
        f"map{i}": {"dpm": 500 - i, "delta_percent": -i, "rounds": 5,
                    "kills": 0, "deaths": 0, "kd": 0.0}
        for i in range(20)
    }
    s = MapAffinityStats(
        player_guid="g1", player_name="alice",
        overall_dpm=500.0, map_stats=map_stats,
    )
    out = _service().format_map_affinity(s)
    # map6 onwards must NOT appear
    assert "`map5`" in out
    assert "`map6`" not in out
    assert "`map10`" not in out


def test_format_map_affinity_positive_delta_has_plus_sign():
    """Positive delta gets explicit "+" prefix; negative natural minus."""
    s = MapAffinityStats(
        player_guid="g1", player_name="alice", overall_dpm=500.0,
        map_stats={
            "up":   {"dpm": 600.0, "delta_percent": 20.0, "rounds": 5,
                     "kills": 0, "deaths": 0, "kd": 0.0},
            "down": {"dpm": 400.0, "delta_percent": -20.0, "rounds": 5,
                     "kills": 0, "deaths": 0, "kd": 0.0},
        },
    )
    out = _service().format_map_affinity(s)
    assert "+20%" in out
    assert "-20%" in out


# ---------------------------------------------------------------------------
# format_playstyle
# ---------------------------------------------------------------------------


def test_format_playstyle_attacker_emoji():
    s = PlaystyleStats(
        player_guid="g1", player_name="alice",
        attack_rounds=20, defense_rounds=5,
        preference="attacker", preference_strength=75.0,
    )
    out = _service().format_playstyle(s)
    assert "⚔️" in out
    assert "Attacker" in out  # title-cased


def test_format_playstyle_defender_emoji():
    s = PlaystyleStats(
        player_guid="g1", player_name="alice",
        preference="defender", preference_strength=80.0,
    )
    out = _service().format_playstyle(s)
    assert "🛡️" in out
    assert "Defender" in out


def test_format_playstyle_balanced_emoji():
    s = PlaystyleStats(
        player_guid="g1", player_name="alice",
        preference="balanced", preference_strength=15.0,
    )
    out = _service().format_playstyle(s)
    assert "⚖️" in out
    assert "Balanced" in out


def test_format_playstyle_unknown_preference_no_emoji_but_does_not_crash():
    """Unknown preference (typo, future value) → empty emoji string,
    NOT KeyError. Pin defensive default so a future preference
    doesn't crash the formatter."""
    s = PlaystyleStats(
        player_guid="g1", player_name="alice",
        preference="unknown_value", preference_strength=0.0,
    )
    out = _service().format_playstyle(s)  # no crash
    assert "Unknown_Value" in out  # still renders


def test_format_playstyle_includes_attack_and_defense_dpm():
    s = PlaystyleStats(
        player_guid="g1", player_name="alice",
        attack_rounds=20, defense_rounds=10,
        attack_dpm=520.5, defense_dpm=480.2,
        attack_kd=2.5, defense_kd=1.8,
        preference="attacker", preference_strength=60.0,
    )
    out = _service().format_playstyle(s)
    assert "520.5" in out
    assert "480.2" in out
    assert "2.50" in out  # KD .2f
    assert "1.80" in out


# ---------------------------------------------------------------------------
# format_awards
# ---------------------------------------------------------------------------


def test_format_awards_empty_list_returns_fallback():
    """Empty list → "No awards this session" message (NOT a blank
    embed)."""
    out = _service().format_awards([])
    assert "No awards" in out


def test_format_awards_renders_emoji_and_name_and_description():
    awards = [
        FunAward(
            award_name="MVP",
            emoji="🏆",
            player_guid="g1",
            player_name="alice",
            value=520.5,
            description="Top DPM session-wide",
        ),
        FunAward(
            award_name="Streaker",
            emoji="🔥",
            player_guid="g2",
            player_name="bob",
            value=15.0,
            description="Longest kill-streak",
        ),
    ]
    out = _service().format_awards(awards)
    assert "🏆" in out
    assert "MVP" in out
    assert "alice" in out
    assert "Top DPM" in out
    assert "🔥" in out
    assert "bob" in out


def test_format_awards_each_award_renders_two_lines():
    """Header line + indented description line per award."""
    awards = [
        FunAward(
            award_name="X", emoji="🏆", player_guid="g", player_name="alice",
            value=0, description="why",
        ),
    ]
    out = _service().format_awards(awards)
    lines = out.split("\n")
    # At least 2 non-empty lines for one award (header + description)
    nonempty = [line for line in lines if line.strip()]
    assert len(nonempty) >= 2
