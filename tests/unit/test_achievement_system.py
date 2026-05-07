"""Tests for AchievementSystem milestone constants + ledger claim path.

This service announces "Player X reached 1000 kills!" embeds in Discord.
A regression silently:

- KILL/GAME/KD milestone threshold drift → some achievements never
  fire (or fire at wrong thresholds → embeds say "1k kills!" at 100).
- Milestone metadata schema drift (missing emoji/title/color) →
  embed render KeyError mid-broadcast.
- `_claim_achievement_ledger` returns True on conflict → duplicate
  notifications spam Discord.
- `_claim_achievement_ledger` returns False on DB outage → no
  achievements ever fire → users frustrated.
- ACTUALLY: production falls back to in-memory dedupe on DB error,
  pin observed.

Pin every milestone + ledger contract.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.core.achievement_system import AchievementSystem

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bot():
    b = MagicMock()
    b.db_adapter = MagicMock()
    b.db_adapter.fetch_one = AsyncMock(return_value=None)
    b.db_adapter.fetch_all = AsyncMock(return_value=[])
    b.db_adapter.execute = AsyncMock(return_value=None)
    b.config = MagicMock()
    return b


@pytest.fixture
def system(bot):
    return AchievementSystem(bot)


# ---------------------------------------------------------------------------
# KILL_MILESTONES — thresholds + metadata schema
# ---------------------------------------------------------------------------


def test_kill_milestone_thresholds_pinned():
    """Pin exact threshold ladder. Drift here changes when "X reached
    1000 kills!" embeds fire (which is loud/visible)."""
    assert set(AchievementSystem.KILL_MILESTONES.keys()) == {
        100, 500, 1000, 2500, 5000, 10000,
    }


def test_kill_milestone_thresholds_sorted_ascending():
    """Pin sort order so the iteration in check_player_achievements
    fires in expected order."""
    keys = list(AchievementSystem.KILL_MILESTONES.keys())
    assert keys == sorted(keys)


@pytest.mark.parametrize("threshold", list(AchievementSystem.KILL_MILESTONES.keys()))
def test_kill_milestone_metadata_schema(threshold):
    """Each entry has emoji + title + color. Pin schema so embed
    render never KeyErrors."""
    entry = AchievementSystem.KILL_MILESTONES[threshold]
    assert "emoji" in entry
    assert "title" in entry
    assert "color" in entry
    assert isinstance(entry["emoji"], str) and entry["emoji"]
    assert isinstance(entry["title"], str) and entry["title"]
    assert isinstance(entry["color"], int)


def test_kill_milestone_titles_distinct():
    """No two milestones share a title (would confuse the embed)."""
    titles = [m["title"] for m in AchievementSystem.KILL_MILESTONES.values()]
    assert len(titles) == len(set(titles))


# ---------------------------------------------------------------------------
# GAME_MILESTONES — thresholds + metadata schema
# ---------------------------------------------------------------------------


def test_game_milestone_thresholds_pinned():
    assert set(AchievementSystem.GAME_MILESTONES.keys()) == {
        10, 50, 100, 250, 500, 1000,
    }


@pytest.mark.parametrize("threshold", list(AchievementSystem.GAME_MILESTONES.keys()))
def test_game_milestone_metadata_schema(threshold):
    entry = AchievementSystem.GAME_MILESTONES[threshold]
    assert {"emoji", "title", "color"} <= set(entry.keys())


def test_game_milestone_titles_distinct():
    titles = [m["title"] for m in AchievementSystem.GAME_MILESTONES.values()]
    assert len(titles) == len(set(titles))


# ---------------------------------------------------------------------------
# KD_MILESTONES — thresholds + metadata schema
# ---------------------------------------------------------------------------


def test_kd_milestone_thresholds_pinned():
    """K/D ladder is denser than kills/games — pin every step."""
    assert set(AchievementSystem.KD_MILESTONES.keys()) == {1.0, 1.5, 2.0, 3.0}


@pytest.mark.parametrize("threshold", list(AchievementSystem.KD_MILESTONES.keys()))
def test_kd_milestone_metadata_schema(threshold):
    entry = AchievementSystem.KD_MILESTONES[threshold]
    assert {"emoji", "title", "color"} <= set(entry.keys())


def test_milestone_categories_use_distinct_top_emojis():
    """Top milestone in kills (👑), games (👑), KD (💯) — pin observed
    that kills + games share 👑 (legendary). A future PR that swaps
    these is loud."""
    top_kill = AchievementSystem.KILL_MILESTONES[10000]["emoji"]
    top_kd = AchievementSystem.KD_MILESTONES[3.0]["emoji"]
    assert top_kill != top_kd  # Different emojis between kill-top and KD-top


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_empty_notified_set(bot):
    """notified_achievements starts empty. Pin so first notification
    isn't suppressed by stale state."""
    s = AchievementSystem(bot)
    assert s.notified_achievements == set()


def test_init_persistent_ledger_enabled(bot):
    """Ledger flag starts True — pin so first DB error degrades
    gracefully (only THEN flips to in-memory)."""
    s = AchievementSystem(bot)
    assert s._persistent_ledger_enabled is True


def test_init_stores_bot_reference(bot):
    s = AchievementSystem(bot)
    assert s.bot is bot


# ---------------------------------------------------------------------------
# _claim_achievement_ledger
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_claim_returns_true_when_inserted(system, bot):
    """ON CONFLICT DO NOTHING + RETURNING → row returned only when
    INSERT succeeded (this process should announce)."""
    bot.db_adapter.fetch_one = AsyncMock(return_value=("ach_123",))
    out = await system._claim_achievement_ledger("ach_123", "g1", "kills", 1000)
    assert out is True


@pytest.mark.asyncio
async def test_claim_returns_false_on_conflict(system, bot):
    """ON CONFLICT → no row returned → False (already claimed by
    another process). Pin so duplicate processes don't double-announce."""
    bot.db_adapter.fetch_one = AsyncMock(return_value=None)
    out = await system._claim_achievement_ledger("ach_123", "g1", "kills", 1000)
    assert out is False


@pytest.mark.asyncio
async def test_claim_returns_true_on_db_error_with_fallback(system, bot):
    """DB unavailable → returns True (in-memory dedupe takes over).
    Pin observed graceful degradation: never block achievements
    on DB issues."""
    bot.db_adapter.fetch_one = AsyncMock(side_effect=RuntimeError("table missing"))
    out = await system._claim_achievement_ledger("ach_123", "g1", "kills", 1000)
    assert out is True
    # Disabled flag flipped — subsequent calls bypass DB
    assert system._persistent_ledger_enabled is False


@pytest.mark.asyncio
async def test_claim_short_circuits_when_ledger_disabled(system, bot):
    """Once disabled (after one DB error), every claim returns True
    without hitting DB again. Pin so a bot whose DB is missing the
    ledger table doesn't fire 1000s of failed queries."""
    system._persistent_ledger_enabled = False
    bot.db_adapter.fetch_one = AsyncMock(return_value=None)

    out = await system._claim_achievement_ledger("ach_X", "g1", "kills", 1000)
    assert out is True
    bot.db_adapter.fetch_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_claim_passes_threshold_as_string_to_db(system, bot):
    """The DB column accepts varchar — threshold int/float coerced to
    str. Pin so a future K/D float threshold (e.g., 1.5) doesn't
    crash on type-mismatch."""
    bot.db_adapter.fetch_one = AsyncMock(return_value=("ach",))
    await system._claim_achievement_ledger("ach", "g1", "kd", 1.5)
    args, _ = bot.db_adapter.fetch_one.await_args
    params = args[1]
    assert params[3] == "1.5"  # threshold serialised as string
    assert isinstance(params[3], str)


# ---------------------------------------------------------------------------
# check_player_achievements — early bails
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_returns_empty_when_player_has_no_data(system, bot):
    """No stats row → empty list."""
    bot.db_adapter.fetch_one = AsyncMock(return_value=None)
    out = await system.check_player_achievements("ghost-guid")
    assert out == []


@pytest.mark.asyncio
async def test_check_returns_empty_when_kills_null(system, bot):
    """First column (total_kills) NULL → empty (player has games but
    no kills tracked)."""
    bot.db_adapter.fetch_one = AsyncMock(return_value=(None, 0, 0, 0))
    out = await system.check_player_achievements("guid")
    assert out == []


# ---------------------------------------------------------------------------
# Cross-category schema invariants
# ---------------------------------------------------------------------------


def test_all_milestone_dicts_have_consistent_value_schema():
    """Across kills/games/kd, every value dict has emoji+title+color.
    Pin so a refactor that adds a new category remembers the schema."""
    all_dicts = [
        AchievementSystem.KILL_MILESTONES,
        AchievementSystem.GAME_MILESTONES,
        AchievementSystem.KD_MILESTONES,
    ]
    for d in all_dicts:
        for entry in d.values():
            assert "emoji" in entry
            assert "title" in entry
            assert "color" in entry


def test_milestone_colors_are_valid_discord_color_ints():
    """Discord embed colors are 24-bit RGB ints (0..0xFFFFFF). Pin
    bound so a typo'd color value (e.g., negative) doesn't crash
    discord.py at render time."""
    for d in [
        AchievementSystem.KILL_MILESTONES,
        AchievementSystem.GAME_MILESTONES,
        AchievementSystem.KD_MILESTONES,
    ]:
        for entry in d.values():
            assert 0 <= entry["color"] <= 0xFFFFFF
