"""Tests for PlayerBadgeService — milestone thresholds + badge stacking.

This service computes the achievement-badge string shown next to every
player name in `!last_session` and the website session detail. A
regression silently:

- KILL_MILESTONES threshold drift (e.g., 1000 → 100) → every player
  shows max badge → loses signal.
- `_get_highest_milestone` returns LOWEST instead of HIGHEST →
  player at 20K kills still shows 🎯 (1K) instead of 👑 (20K).
- `_get_highest_milestone` strict `>` instead of `>=` → player
  at exactly the milestone misses the badge.
- `_format_badges_with_stacking` doesn't dedup → embed shows 🎯🎯🎯
  instead of 🎯x3, exceeds Discord field width.
- 20-game minimum on K/D badge dropped → new player with 5 kills
  and 0 deaths shows 💯 (3.0 K/D) — meaningless.

Pin every threshold + every dedup invariant.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from bot.services.player_badge_service import PlayerBadgeService


@pytest.fixture
def db():
    a = AsyncMock()
    a.fetch_one = AsyncMock(return_value=None)
    a.fetch_all = AsyncMock(return_value=[])
    return a


@pytest.fixture
def svc(db):
    return PlayerBadgeService(db_adapter=db)


# ---------------------------------------------------------------------------
# Milestone constants — pin thresholds + emoji
# ---------------------------------------------------------------------------


def test_kill_milestones_thresholds():
    """Pin exact thresholds. A drift in either direction (e.g., 5000
    → 500) silently devalues badges for every player."""
    assert PlayerBadgeService.KILL_MILESTONES == {
        1000: "🎯",
        5000: "💀",
        10000: "☠️",
        20000: "👑",
    }


def test_game_milestones_thresholds():
    assert PlayerBadgeService.GAME_MILESTONES == {
        50: "🎮",
        500: "🕹️",
        5000: "🏆",
        10000: "⭐",
        30000: "💎",
    }


def test_kd_milestones_thresholds():
    """K/D ladder is denser than kills/games — pin every step.
    Pin 0.0 → ⚰️ as a "death/zero K/D" indicator (NOT just absent)."""
    assert PlayerBadgeService.KD_MILESTONES == {
        0.0: "⚰️",
        1.0: "⚖️",
        1.5: "📈",
        2.0: "🔥",
        2.5: "⚡",
        3.0: "💯",
    }


def test_revive_milestones_thresholds():
    assert PlayerBadgeService.REVIVE_MILESTONES == {
        100: "💉",
        500: "🏥",
        5000: "⚕️",
    }


def test_dynamite_planted_milestones():
    assert PlayerBadgeService.DYNAMITE_PLANTED_MILESTONES == {
        50: "💣",
        200: "🧨",
        1000: "💥",
    }


def test_objective_milestones_thresholds():
    assert PlayerBadgeService.OBJECTIVE_MILESTONES == {
        25: "🚩",
        250: "🎖️",
        2500: "🏅",
    }


# ---------------------------------------------------------------------------
# _get_highest_milestone — picks HIGHEST, inclusive boundary
# ---------------------------------------------------------------------------


def test_highest_milestone_below_lowest_threshold(svc):
    """Value below lowest threshold → None."""
    out = svc._get_highest_milestone(500, PlayerBadgeService.KILL_MILESTONES)
    assert out is None


def test_highest_milestone_exact_lowest_threshold(svc):
    """Value == lowest threshold → that badge (inclusive `>=`)."""
    out = svc._get_highest_milestone(1000, PlayerBadgeService.KILL_MILESTONES)
    assert out == "🎯"


def test_highest_milestone_picks_highest_qualified(svc):
    """Value above multiple thresholds → highest one wins.
    Pin so a sort-flip in the function doesn't downgrade every
    20K-kill player to a 1K badge."""
    out = svc._get_highest_milestone(25000, PlayerBadgeService.KILL_MILESTONES)
    assert out == "👑"  # the 20K threshold


def test_highest_milestone_between_thresholds(svc):
    """Between two milestones → returns the LOWER one (highest met)."""
    # 7500 is between 5000 (💀) and 10000 (☠️) → 💀
    out = svc._get_highest_milestone(7500, PlayerBadgeService.KILL_MILESTONES)
    assert out == "💀"


def test_highest_milestone_exact_top_threshold(svc):
    """Value exactly at the top milestone → that badge."""
    out = svc._get_highest_milestone(20000, PlayerBadgeService.KILL_MILESTONES)
    assert out == "👑"


def test_highest_milestone_kd_zero_returns_dead_emoji(svc):
    """K/D == 0.0 → ⚰️ (the zero-floor sentinel)."""
    out = svc._get_highest_milestone(0.0, PlayerBadgeService.KD_MILESTONES)
    assert out == "⚰️"


def test_highest_milestone_kd_intermediate(svc):
    """K/D 1.7 → 📈 (1.5 threshold), NOT 🔥 (2.0 threshold)."""
    out = svc._get_highest_milestone(1.7, PlayerBadgeService.KD_MILESTONES)
    assert out == "📈"


def test_highest_milestone_kd_at_3_returns_top(svc):
    """K/D == 3.0 → 💯 (top of ladder)."""
    out = svc._get_highest_milestone(3.0, PlayerBadgeService.KD_MILESTONES)
    assert out == "💯"


def test_highest_milestone_empty_dict(svc):
    """Empty milestone dict → None (no thresholds defined)."""
    out = svc._get_highest_milestone(100, {})
    assert out is None


def test_highest_milestone_negative_value(svc):
    """Negative value → None (below all thresholds, including 0.0)."""
    out = svc._get_highest_milestone(-1, PlayerBadgeService.KD_MILESTONES)
    # -1 < 0.0 → no milestone met
    assert out is None


# ---------------------------------------------------------------------------
# _format_badges_with_stacking — dedup + count notation
# ---------------------------------------------------------------------------


def test_format_empty_badges(svc):
    """No badges → empty string."""
    assert svc._format_badges_with_stacking([]) == ""


def test_format_single_unique_badges(svc):
    """All-unique badges → just concatenated."""
    out = svc._format_badges_with_stacking(["🎯", "💀", "🏆"])
    assert out == "🎯💀🏆"


def test_format_dedupes_with_count_notation(svc):
    """Repeated badge → "🎯x3" suffix."""
    out = svc._format_badges_with_stacking(["🎯", "🎯", "🎯"])
    assert out == "🎯x3"


def test_format_mix_of_unique_and_duplicates(svc):
    """Mixed: some unique, some duplicated."""
    out = svc._format_badges_with_stacking(["🎯", "🎯", "💀", "🏆", "🏆"])
    # 🎯x2, 💀, 🏆x2 — order preserved by first appearance
    assert "🎯x2" in out
    assert "💀" in out
    assert "🏆x2" in out


def test_format_preserves_first_appearance_order(svc):
    """Output order matches first-appearance order (Python dict
    insertion order). Pin so a refactor that sorts alphabetically
    doesn't reshuffle every player's badge string."""
    out = svc._format_badges_with_stacking(["💀", "🎯", "💀"])
    # First appearance: 💀 then 🎯 → "💀x2🎯"
    assert out.startswith("💀")
    assert out.endswith("🎯")


def test_format_single_badge_no_count_suffix(svc):
    """Count of 1 → no "x1" suffix (just the emoji)."""
    out = svc._format_badges_with_stacking(["🎯"])
    assert out == "🎯"
    assert "x" not in out


def test_format_count_of_two_uses_x2(svc):
    """Boundary: 2 of same → "x2"."""
    out = svc._format_badges_with_stacking(["🎯", "🎯"])
    assert out == "🎯x2"


# ---------------------------------------------------------------------------
# get_player_badges — orchestration with mocked DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_badges_returns_empty_when_no_data(svc, db):
    """Player not found → empty string (NOT crash on NoneType)."""
    db.fetch_one = AsyncMock(return_value=None)
    out = await svc.get_player_badges("ghost-guid")
    assert out == ""


@pytest.mark.asyncio
async def test_get_badges_returns_empty_when_zero_kills(svc, db):
    """First column is total_kills; if it's None → returns "" early.
    Pin the early-bail so a no-stats player's row is empty."""
    db.fetch_one = AsyncMock(return_value=(None, 0, 0, 0, 0, 0, 0, 0, 0))
    out = await svc.get_player_badges("guid")
    assert out == ""


@pytest.mark.asyncio
async def test_get_badges_skips_kd_below_20_games(svc, db):
    """A player with 5 kills, 0 deaths and 5 games has perfect K/D
    but FEWER than 20 games → no K/D badge.

    Pin the games >= 20 gate — protects against new players' freak
    K/D ratios (e.g., 5-0 in their first round)."""
    # 1000 kills (badge 🎯), 0 deaths, 19 games → K/D would be huge
    # but games < 20 should suppress the K/D badge
    db.fetch_one = AsyncMock(return_value=(
        1000, 0, 19, 1000.0,  # kills, deaths, games, kd
        0, 0, 0, 0, 0,        # revives, times_revived, dyns, defused, objs
    ))
    out = await svc.get_player_badges("guid")
    # Should have kill badge 🎯 but NOT a K/D badge
    assert "🎯" in out
    assert "💯" not in out
    assert "🔥" not in out


@pytest.mark.asyncio
async def test_get_badges_includes_kd_at_20_games(svc, db):
    """Exactly 20 games → K/D badge shown (inclusive boundary)."""
    db.fetch_one = AsyncMock(return_value=(
        1000, 500, 20, 2.0,
        0, 0, 0, 0, 0,
    ))
    out = await svc.get_player_badges("guid")
    # 2.0 K/D → 🔥
    assert "🔥" in out


@pytest.mark.asyncio
async def test_get_badges_combines_all_categories(svc, db):
    """Top player (kills + games + K/D + revives + objectives) →
    multiple badges concatenated (with stacking dedup)."""
    db.fetch_one = AsyncMock(return_value=(
        15000, 5000, 2000, 3.0,  # core: 💀 (10K kills), 🏆 (5K games), 💯 (3.0 KD)
        500,    # revives: 🏥
        100,    # times_revived: 🔄
        50,     # dyns_planted: 💣
        50,     # dyns_defused: 🛡️
        25,     # objectives: 🚩
    ))
    out = await svc.get_player_badges("guid")
    # 15000 kills met 10K (☠️) but not 20K (👑) → ☠️
    assert "☠️" in out
    # 2000 games met 500 (🕹️) but not 5000 (🏆)
    assert "🕹️" in out
    assert "💯" in out  # 3.0 K/D
    assert "🏥" in out  # 500 revives
    assert "🚩" in out  # 25 objectives


@pytest.mark.asyncio
async def test_get_badges_swallows_db_exception(svc, db):
    """DB raises → empty string (NOT propagate). Pin so a transient
    DB error doesn't crash every embed mid-render."""
    db.fetch_one = AsyncMock(side_effect=RuntimeError("DB down"))
    out = await svc.get_player_badges("guid")
    assert out == ""
