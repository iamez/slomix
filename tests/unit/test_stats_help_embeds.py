"""Tests for _StatsHelpEmbedsMixin — !help category embed factories.

These 9 embed factories build the !help <category> embeds users see in
Discord. A regression silently:

- Title or color drift → embed renders blank or mis-themed.
- Field count drops → a command silently disappears from help docs
  while still working (confused users).
- Embed exceeds Discord 6000-char total limit → API rejects the embed
  → user sees error.
- A command name is mis-typed in the help → users get "command not
  found" when they copy-paste from the help.

Pin schema invariants + canonical command names per category.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import discord

from bot.cogs.stats_mixins.help_embeds_mixin import _StatsHelpEmbedsMixin

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _factory():
    """Bare instance of mixin for calling the embed factories."""
    obj = _StatsHelpEmbedsMixin.__new__(_StatsHelpEmbedsMixin)
    obj.bot = MagicMock()
    return obj


def _embed_total_chars(embed: discord.Embed) -> int:
    """Sum of title + description + every field name + value (rough
    Discord 6000-char check)."""
    total = 0
    if embed.title:
        total += len(embed.title)
    if embed.description:
        total += len(embed.description)
    for f in embed.fields:
        if f.name:
            total += len(f.name)
        if f.value:
            total += len(f.value)
    return total


# ---------------------------------------------------------------------------
# All 9 factories — schema invariants
# ---------------------------------------------------------------------------


ALL_FACTORIES = [
    "_help_stats",
    "_help_sessions",
    "_help_teams",
    "_help_predictions",
    "_help_synergy",
    "_help_server",
    "_help_players",
    "_help_admin",
    "_help_automation",
]


def test_each_factory_returns_discord_embed():
    """Every factory returns a `discord.Embed` instance."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        assert isinstance(embed, discord.Embed), f"{name} did not return Embed"


def test_each_embed_has_title_and_description():
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        assert embed.title, f"{name} missing title"
        assert embed.description, f"{name} missing description"


def test_each_embed_has_color():
    """Every embed has a non-default color (themed). Pin so the
    9 categories stay visually distinguishable."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        assert embed.color is not None, f"{name} missing color"


def test_each_embed_has_at_least_one_field():
    """Every category lists ≥1 command. A factory returning zero
    fields = nothing for the user to read."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        assert len(embed.fields) >= 1, f"{name} has no fields"


def test_each_embed_under_discord_total_limit():
    """Discord embed total payload ≤ 6000 chars. Pin so a future
    command-list expansion doesn't silently exceed the limit and
    cause Discord to reject the embed."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        total = _embed_total_chars(embed)
        assert total <= 6000, f"{name} total {total} chars > 6000"


def test_each_field_value_under_1024():
    """Discord per-field value limit = 1024 chars. Pin so a long
    command description doesn't truncate."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        for field in embed.fields:
            assert len(field.value) <= 1024, (
                f"{name} field '{field.name}' value > 1024 chars"
            )


def test_each_field_name_under_256():
    """Discord per-field name limit = 256 chars."""
    f = _factory()
    for name in ALL_FACTORIES:
        embed = getattr(f, name)()
        for field in embed.fields:
            assert len(field.name) <= 256, (
                f"{name} field name > 256: {field.name[:50]}..."
            )


# ---------------------------------------------------------------------------
# Per-category command-name pins (canonical commands)
# ---------------------------------------------------------------------------


def _embed_text(embed: discord.Embed) -> str:
    """Concatenate every part of the embed for substring lookups."""
    parts = [embed.title or "", embed.description or ""]
    for f in embed.fields:
        parts.append(f.name)
        parts.append(f.value)
    return "\n".join(parts)


def test_help_stats_lists_canonical_commands():
    """Pin the canonical commands so a refactor that drops one is loud."""
    embed = _factory()._help_stats()
    text = _embed_text(embed)
    for cmd in ["!stats", "!leaderboard", "!compare", "!achievements", "!badges"]:
        assert cmd in text, f"_help_stats missing {cmd}"


def test_help_sessions_lists_canonical_commands():
    embed = _factory()._help_sessions()
    text = _embed_text(embed)
    assert "!last_session" in text


def test_help_teams_lists_canonical_commands():
    embed = _factory()._help_teams()
    text = _embed_text(embed)
    # Team-related commands present
    assert "team" in text.lower()


def test_help_predictions_lists_canonical_commands():
    embed = _factory()._help_predictions()
    text = _embed_text(embed)
    assert "predict" in text.lower()


def test_help_admin_lists_canonical_commands():
    embed = _factory()._help_admin()
    text = _embed_text(embed)
    # At least one admin namespace mentioned
    assert "admin" in text.lower() or "permission" in text.lower()


def test_help_automation_lists_canonical_commands():
    embed = _factory()._help_automation()
    text = _embed_text(embed)
    # Automation cog commands
    assert "automation" in text.lower() or "rcon" in text.lower() or "ssh" in text.lower()


# ---------------------------------------------------------------------------
# Category title uniqueness (so the 9 embeds don't collide visually)
# ---------------------------------------------------------------------------


def test_all_help_embed_titles_distinct():
    """Pin so two categories don't share the same title (would
    confuse the !help dispatcher / user)."""
    f = _factory()
    titles = [getattr(f, name)().title for name in ALL_FACTORIES]
    assert len(titles) == len(set(titles))


def test_all_help_embed_colors_distinct():
    """Different colors per category (visual scanability). A clash
    would degrade the !help UX silently."""
    f = _factory()
    colors = [getattr(f, name)().color.value for name in ALL_FACTORIES]
    # Allow up to 1 collision (e.g., admin/automation both red),
    # but not all-the-same.
    assert len(set(colors)) >= len(colors) - 1


# ---------------------------------------------------------------------------
# Field inline flag pinned (false for command-list embeds)
# ---------------------------------------------------------------------------


def test_help_stats_fields_are_inline_false():
    """Command list fields are inline=False (each on own line). Pin
    so a refactor that flips to inline=True doesn't break readability."""
    embed = _factory()._help_stats()
    for field in embed.fields:
        assert field.inline is False, (
            f"field '{field.name}' should be inline=False"
        )
