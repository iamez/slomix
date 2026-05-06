"""Tests for bot/core/checks.py — Discord command permission decorators.

These decorators are the canonical authorisation surface for the
80+ bot commands. A regression in any of them either:
- silently locks out users (commands stop working in the right channel), or
- silently grants access (admin commands fire from public channels).

Both failure modes are bad. Pin every predicate's exact branching here.

Each decorator returns a `commands.check`. We unwrap to the predicate
via `decorator()._predicate`/`callback` (depending on discord.py
version) — for these tests we wrap in a tiny helper that pulls the
predicate coroutine out so we can call it with a fake ctx.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ext import commands

from bot.core.checks import (
    ChannelCheckFailure,
    is_admin,
    is_admin_channel,
    is_allowed_channel,
    is_moderator,
    is_owner,
    is_public_channel,
)


def _extract_predicate(check_decorator):
    """Pull the inner async predicate out of a `commands.check` instance.

    The check returned by commands.check exposes the predicate via the
    `predicate` attribute on discord.py 2.x. We invoke `commands.check(p)`
    on a no-op function to get back a Check object whose `predicate` is
    the function we passed in.
    """
    # Apply the decorator to a dummy command function to reach the inner
    # predicate
    dummy = AsyncMock()
    dummy.__qualname__ = "dummy"
    decorated = check_decorator(dummy)
    # discord.py stashes the predicate in `dummy.__commands_checks__`
    return decorated.__commands_checks__[-1]


def _ctx(*, channel_id=0, author_id=0, bot_attrs=None, db=None):
    """Build a minimal ctx with the attributes the predicates touch."""
    bot = MagicMock()
    if bot_attrs:
        for k, v in bot_attrs.items():
            setattr(bot, k, v)
    if db is not None:
        bot.db_adapter = db
    ctx = SimpleNamespace(
        bot=bot,
        channel=SimpleNamespace(id=channel_id),
        author=SimpleNamespace(id=author_id, __str__=lambda self: f"User{self.id}"),
    )
    return ctx


# ---------------------------------------------------------------------------
# is_admin_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_channel_fails_closed_when_unconfigured():
    """No `admin_channels`, no `admin_channel_id` → DENY (not allow).
    Pinning fail-closed is critical: a deploy that drops the env var
    must not silently expose admin commands."""
    pred = _extract_predicate(is_admin_channel())
    ctx = _ctx(channel_id=42, bot_attrs={"admin_channels": [], "admin_channel_id": 0})
    assert await pred(ctx) is False


@pytest.mark.asyncio
async def test_admin_channel_uses_admin_channels_list_when_set():
    pred = _extract_predicate(is_admin_channel())
    ctx = _ctx(channel_id=42, bot_attrs={"admin_channels": [42, 99]})
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_admin_channel_falls_back_to_legacy_id():
    """Backward-compat: when admin_channels is empty but
    admin_channel_id is set, treat the legacy ID as a single-element list."""
    pred = _extract_predicate(is_admin_channel())
    ctx = _ctx(channel_id=42, bot_attrs={"admin_channels": [], "admin_channel_id": 42})
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_admin_channel_silently_denies_wrong_channel():
    """Wrong channel returns False — DOES NOT raise. Silent ignore is
    the documented contract; raising would spam users."""
    pred = _extract_predicate(is_admin_channel())
    ctx = _ctx(channel_id=999, bot_attrs={"admin_channels": [42]})
    result = await pred(ctx)
    assert result is False


# ---------------------------------------------------------------------------
# is_public_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_channel_allows_when_unconfigured():
    """No `public_channels` configured → DEFAULT ALLOW. This is
    intentional fail-open for legacy deployments that haven't set
    the public list yet."""
    pred = _extract_predicate(is_public_channel())
    ctx = _ctx(channel_id=42)
    # Bot has no public_channels attr at all
    delattr(ctx.bot, "public_channels") if hasattr(ctx.bot, "public_channels") else None
    # Mock will autocreate, so set it explicitly to a falsy value
    ctx.bot.public_channels = []
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_public_channel_allows_in_listed_channel():
    pred = _extract_predicate(is_public_channel())
    ctx = _ctx(channel_id=42, bot_attrs={"public_channels": [42, 99]})
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_public_channel_silently_denies_wrong_channel():
    pred = _extract_predicate(is_public_channel())
    ctx = _ctx(channel_id=999, bot_attrs={"public_channels": [42]})
    assert await pred(ctx) is False


# ---------------------------------------------------------------------------
# is_allowed_channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_channel_accepts_listed():
    pred = _extract_predicate(is_allowed_channel([1, 2, 3]))
    ctx = _ctx(channel_id=2)
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_allowed_channel_silently_denies_unlisted():
    pred = _extract_predicate(is_allowed_channel([1, 2, 3]))
    ctx = _ctx(channel_id=99)
    assert await pred(ctx) is False


@pytest.mark.asyncio
async def test_allowed_channel_empty_list_denies_everything():
    """Empty allowed list → no channel passes — useful for explicit
    feature-flag-off behaviour."""
    pred = _extract_predicate(is_allowed_channel([]))
    ctx = _ctx(channel_id=42)
    assert await pred(ctx) is False


# ---------------------------------------------------------------------------
# is_owner (root tier)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_owner_allows_when_author_matches():
    pred = _extract_predicate(is_owner())
    ctx = _ctx(author_id=12345, bot_attrs={"owner_user_id": 12345})
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_owner_raises_when_author_mismatches():
    """is_owner DOES raise CheckFailure (unlike channel checks).
    Pin that distinction — it surfaces a user-visible error, which is
    desirable for high-tier commands so attempted unauthorised use
    shows up in audit logs."""
    pred = _extract_predicate(is_owner())
    ctx = _ctx(author_id=99999, bot_attrs={"owner_user_id": 12345})
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


@pytest.mark.asyncio
async def test_is_owner_raises_when_owner_unconfigured():
    """owner_user_id=0 (default) means nobody → all callers fail."""
    pred = _extract_predicate(is_owner())
    ctx = _ctx(author_id=12345, bot_attrs={"owner_user_id": 0})
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


# ---------------------------------------------------------------------------
# is_admin (DB tier check)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_admin_allows_root_unconditionally():
    """Root has admin access without DB lookup — no `db_adapter` access."""
    db = AsyncMock()
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=1, bot_attrs={"owner_user_id": 1}, db=db)
    assert await pred(ctx) is True
    db.fetch_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_is_admin_allows_when_db_returns_admin_tier():
    db = AsyncMock()
    db.fetch_one.return_value = ("admin",)
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_admin_allows_when_db_returns_moderator_tier():
    """Moderator tier is acceptable for is_admin (admin + moderator + root)."""
    db = AsyncMock()
    db.fetch_one.return_value = ("moderator",)
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_admin_raises_when_db_returns_no_row():
    db = AsyncMock()
    db.fetch_one.return_value = None
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


@pytest.mark.asyncio
async def test_is_admin_raises_when_db_returns_unexpected_tier():
    """A future schema typo or rogue tier value → fail-closed."""
    db = AsyncMock()
    db.fetch_one.return_value = ("unknown_tier",)
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


@pytest.mark.asyncio
async def test_is_admin_raises_on_db_error():
    """DB failure → fail-closed with CheckFailure (NOT a propagated
    DB exception that would crash the cog handler)."""
    db = AsyncMock()
    db.fetch_one.side_effect = RuntimeError("connection lost")
    pred = _extract_predicate(is_admin())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


# ---------------------------------------------------------------------------
# is_moderator (same DB lookup as is_admin)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_moderator_allows_root():
    pred = _extract_predicate(is_moderator())
    ctx = _ctx(author_id=1, bot_attrs={"owner_user_id": 1}, db=AsyncMock())
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_moderator_allows_admin_tier():
    db = AsyncMock()
    db.fetch_one.return_value = ("admin",)
    pred = _extract_predicate(is_moderator())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_moderator_allows_moderator_tier():
    db = AsyncMock()
    db.fetch_one.return_value = ("moderator",)
    pred = _extract_predicate(is_moderator())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    assert await pred(ctx) is True


@pytest.mark.asyncio
async def test_is_moderator_raises_when_no_row():
    db = AsyncMock()
    db.fetch_one.return_value = None
    pred = _extract_predicate(is_moderator())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


@pytest.mark.asyncio
async def test_is_moderator_raises_on_db_error():
    db = AsyncMock()
    db.fetch_one.side_effect = RuntimeError("DB outage")
    pred = _extract_predicate(is_moderator())
    ctx = _ctx(author_id=42, bot_attrs={"owner_user_id": 1}, db=db)
    with pytest.raises(commands.CheckFailure):
        await pred(ctx)


# ---------------------------------------------------------------------------
# Backward-compat marker
# ---------------------------------------------------------------------------


def test_channel_check_failure_class_is_subclass_of_check_failure():
    """ChannelCheckFailure must remain a subclass of commands.CheckFailure
    so legacy `except ChannelCheckFailure` blocks across the cogs still
    behave when raised. (Currently it's a kept-for-back-compat alias.)"""
    assert issubclass(ChannelCheckFailure, commands.CheckFailure)
