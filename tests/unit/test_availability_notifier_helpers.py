"""Tests for UnifiedAvailabilityNotifier static + pure helpers.

This service drives multi-channel (Discord/Telegram/Signal) delivery
with ledger-based idempotency. A regression silently:

- `build_event_key` separator drift → ledger duplicate-key collisions
  (two different events hash to the same key) or split-keys (same event
  re-sent because the qualifier formatting changed).
- `_token_hash` swapped from sha256 → another algo → existing tokens
  in DB no longer match → all in-flight link flows break.
- `_bump_result` mis-routing (sent vs failed) → metrics misreport delivery.
- `__init__` default config drift → discord DMs silently disabled or
  retry budget shrinks below the reasonable floor.
- `send_via_channel` raises wrong error for unknown channel → silent
  swallow upstream → message dropped without log.
- `_subscription_map` discord-default missing → unlinked Discord user
  doesn't get DM (regression on the "default-enabled" promise).

Pin every static + every pure branch.
"""
from __future__ import annotations

import hashlib
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.services.availability_notifier_service import (
    EVENT_DAILY_REMINDER,
    EVENT_FRIENDS_LOOKING,
    EVENT_SESSION_READY,
    DeliveryResult,
    UnifiedAvailabilityNotifier,
)

# ---------------------------------------------------------------------------
# Module constants — pin event-type names (used as DB ledger keys)
# ---------------------------------------------------------------------------


def test_event_constants_pinned():
    """Event-type strings flow into DB ledger and webhook payloads.
    Pin so a typo'd rename silently splits old vs new ledger entries."""
    assert EVENT_DAILY_REMINDER == "DAILY_REMINDER"
    assert EVENT_SESSION_READY == "SESSION_READY"
    assert EVENT_FRIENDS_LOOKING == "FRIENDS_LOOKING"


# ---------------------------------------------------------------------------
# DeliveryResult dataclass
# ---------------------------------------------------------------------------


def test_delivery_result_defaults_zero():
    """All counters start at 0. Pin so a regression that adds a missing
    default makes the dataclass non-instantiable."""
    r = DeliveryResult()
    assert r.sent == 0
    assert r.skipped == 0
    assert r.failed == 0


def test_delivery_result_fields_independent():
    """Mutating one counter doesn't affect siblings (pin field-by-field
    semantics — guards against a mutable-default class attribute bug)."""
    a = DeliveryResult()
    b = DeliveryResult()
    a.sent = 5
    assert b.sent == 0


# ---------------------------------------------------------------------------
# build_event_key — ledger-collision invariant
# ---------------------------------------------------------------------------


def test_build_event_key_no_qualifier():
    """`{event_type}:{iso_date}` — pin separator and ISO format."""
    out = UnifiedAvailabilityNotifier.build_event_key(
        "DAILY_REMINDER", date(2026, 5, 7)
    )
    assert out == "DAILY_REMINDER:2026-05-07"


def test_build_event_key_with_qualifier():
    """Qualifier appended with a `:` separator. Pin so a swap to `_`
    or `/` would split old ledger entries from new."""
    out = UnifiedAvailabilityNotifier.build_event_key(
        "SESSION_READY", date(2026, 5, 7), "match-12"
    )
    assert out == "SESSION_READY:2026-05-07:match-12"


def test_build_event_key_empty_qualifier_omits_separator():
    """Empty/None qualifier → no trailing colon. Pin so '' and None
    produce the same key (otherwise duplicate ledger rows for the
    same logical event)."""
    out_none = UnifiedAvailabilityNotifier.build_event_key(
        "DAILY_REMINDER", date(2026, 5, 7), None
    )
    out_empty = UnifiedAvailabilityNotifier.build_event_key(
        "DAILY_REMINDER", date(2026, 5, 7), ""
    )
    assert out_none == "DAILY_REMINDER:2026-05-07"
    assert out_empty == "DAILY_REMINDER:2026-05-07"
    assert out_none == out_empty


def test_build_event_key_qualifier_preserves_special_chars():
    """Qualifier passed through verbatim (no escaping). Pin so a
    qualifier containing `:` doesn't silently merge with the date."""
    out = UnifiedAvailabilityNotifier.build_event_key(
        "X", date(2026, 5, 7), "a:b:c"
    )
    assert out == "X:2026-05-07:a:b:c"


def test_build_event_key_iso_format_zero_padded():
    """Single-digit month/day must be zero-padded (ISO 8601). Pin so
    a manual `f"{m}-{d}"` swap would produce non-sortable keys."""
    out = UnifiedAvailabilityNotifier.build_event_key(
        "X", date(2026, 1, 5)
    )
    assert out == "X:2026-01-05"


# ---------------------------------------------------------------------------
# _token_hash — sha256 invariant for link tokens
# ---------------------------------------------------------------------------


def test_token_hash_is_sha256_hex():
    """Output is sha256 hex digest of UTF-8-encoded token. Pin the
    algorithm so a refactor (e.g., to blake2b) doesn't invalidate
    every active link token in the DB."""
    raw = "tok-abc-123"
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert UnifiedAvailabilityNotifier._token_hash(raw) == expected


def test_token_hash_deterministic():
    """Same input → same hash. Pin so token verification works after
    a process restart."""
    a = UnifiedAvailabilityNotifier._token_hash("xyz")
    b = UnifiedAvailabilityNotifier._token_hash("xyz")
    assert a == b


def test_token_hash_different_inputs_different_outputs():
    a = UnifiedAvailabilityNotifier._token_hash("token-A")
    b = UnifiedAvailabilityNotifier._token_hash("token-B")
    assert a != b


def test_token_hash_handles_non_string_via_str_coercion():
    """Non-string inputs coerced via str() — pin so a numeric token
    isn't silently rejected on the verify path."""
    out = UnifiedAvailabilityNotifier._token_hash(12345)
    expected = hashlib.sha256(b"12345").hexdigest()
    assert out == expected


# ---------------------------------------------------------------------------
# _bump_result — status routing
# ---------------------------------------------------------------------------


def test_bump_result_sent():
    r = DeliveryResult()
    UnifiedAvailabilityNotifier._bump_result(r, "sent")
    assert (r.sent, r.failed, r.skipped) == (1, 0, 0)


def test_bump_result_failed():
    r = DeliveryResult()
    UnifiedAvailabilityNotifier._bump_result(r, "failed")
    assert (r.sent, r.failed, r.skipped) == (0, 1, 0)


def test_bump_result_skipped_explicit():
    r = DeliveryResult()
    UnifiedAvailabilityNotifier._bump_result(r, "skipped")
    assert (r.sent, r.failed, r.skipped) == (0, 0, 1)


def test_bump_result_unknown_status_falls_to_skipped():
    """Any non-sent/non-failed status (typo, "queued", "pending") →
    skipped. Pin so an unhandled status doesn't increment the wrong
    counter (would skew delivery metrics)."""
    r = DeliveryResult()
    UnifiedAvailabilityNotifier._bump_result(r, "queued")
    assert r.skipped == 1
    UnifiedAvailabilityNotifier._bump_result(r, "")
    assert r.skipped == 2


def test_bump_result_accumulates():
    """Multiple calls accumulate across categories independently."""
    r = DeliveryResult()
    UnifiedAvailabilityNotifier._bump_result(r, "sent")
    UnifiedAvailabilityNotifier._bump_result(r, "sent")
    UnifiedAvailabilityNotifier._bump_result(r, "failed")
    UnifiedAvailabilityNotifier._bump_result(r, "skipped")
    assert (r.sent, r.failed, r.skipped) == (2, 1, 1)


# ---------------------------------------------------------------------------
# __init__ — config defaults that downstream services rely on
# ---------------------------------------------------------------------------


def _build_notifier(**overrides):
    """Build a notifier with a minimal config; overrides set specific keys."""
    cfg = SimpleNamespace(**overrides)
    bot = MagicMock()
    db = MagicMock()
    return UnifiedAvailabilityNotifier(bot, db, cfg)


def test_init_defaults_max_attempts_5():
    """Default retry budget = 5. Pin so a config-less deploy doesn't
    silently shrink to 1 (would mean a single transient failure burns
    the message)."""
    n = _build_notifier()
    assert n.max_attempts == 5


def test_init_clamps_max_attempts_minimum_1():
    """max(1, ...) floor — pin so a bad config of 0 doesn't disable
    sends entirely."""
    n = _build_notifier(availability_notification_max_attempts=0)
    assert n.max_attempts == 1


def test_init_discord_dm_default_enabled():
    """Discord DM is default ON. Pin the "no config = sane defaults"
    promise — Discord is the primary channel."""
    n = _build_notifier()
    assert n.discord_dm_enabled is True


def test_init_discord_channel_announce_default_disabled():
    """Public channel announces are default OFF (loud feature, opt-in).
    Pin so a missing config doesn't suddenly broadcast to a server."""
    n = _build_notifier()
    assert n.discord_channel_announce_enabled is False


def test_init_telegram_default_disabled():
    """Telegram is default OFF (requires bot token). Pin so a missing
    token doesn't enable a connector that would 401-spin."""
    n = _build_notifier()
    assert n.telegram_connector.enabled is False


def test_init_signal_default_disabled():
    n = _build_notifier()
    assert n.signal_connector.enabled is False


def test_init_telegram_token_falls_back_to_legacy_key():
    """`availability_telegram_bot_token` missing → fall back to legacy
    `telegram_bot_token`. Pin so a half-migrated config still works."""
    n = _build_notifier(telegram_bot_token="legacy-token-xyz")  # noqa: S106
    assert n.telegram_connector.bot_token == "legacy-token-xyz"  # noqa: S105


def test_init_tables_ensured_starts_false():
    """Tables-ensured flag starts False — pin so the first call
    actually runs `ensure_tables()` (idempotency hinges on this flag)."""
    n = _build_notifier()
    assert n.tables_ensured is False


# ---------------------------------------------------------------------------
# send_via_channel — pure routing dispatch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_via_channel_routes_discord():
    n = _build_notifier()
    n.send_discord = AsyncMock(return_value="msg-id-123")
    out = await n.send_via_channel(
        channel_type="discord", target="42", message="hi"
    )
    assert out == "msg-id-123"
    n.send_discord.assert_awaited_once_with("42", "hi")


@pytest.mark.asyncio
async def test_send_via_channel_routes_telegram():
    n = _build_notifier()
    n.send_telegram = AsyncMock(return_value="tg-id")
    out = await n.send_via_channel(
        channel_type="telegram", target="@user", message="hi"
    )
    assert out == "tg-id"
    n.send_telegram.assert_awaited_once_with("@user", "hi")


@pytest.mark.asyncio
async def test_send_via_channel_routes_signal():
    n = _build_notifier()
    n.send_signal = AsyncMock(return_value="sig-id")
    out = await n.send_via_channel(
        channel_type="signal", target="+12025550100", message="hi"
    )
    assert out == "sig-id"
    n.send_signal.assert_awaited_once_with("+12025550100", "hi")


@pytest.mark.asyncio
async def test_send_via_channel_normalises_case_and_whitespace():
    """`  Discord  ` → routes to discord. Pin so a cog that passes
    `"DISCORD"` doesn't fall through to RuntimeError."""
    n = _build_notifier()
    n.send_discord = AsyncMock(return_value="ok")
    out = await n.send_via_channel(
        channel_type="  Discord  ", target="t", message="m"
    )
    assert out == "ok"


@pytest.mark.asyncio
async def test_send_via_channel_raises_for_unknown():
    """Unknown channel → RuntimeError (loud). Pin so a typo'd channel
    name surfaces immediately instead of silently dropping the message."""
    n = _build_notifier()
    with pytest.raises(RuntimeError, match="Unsupported channel_type"):
        await n.send_via_channel(
            channel_type="email", target="x@y", message="m"
        )


@pytest.mark.asyncio
async def test_send_via_channel_raises_for_empty():
    """Empty channel_type → RuntimeError (NOT silent skip)."""
    n = _build_notifier()
    with pytest.raises(RuntimeError):
        await n.send_via_channel(channel_type="", target="t", message="m")


# ---------------------------------------------------------------------------
# _subscription_map — discord-default fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_map_adds_discord_default_when_missing():
    """No subscriptions row → auto-add discord with enabled=True and
    user_id as channel_address. Pin the "Discord-default" promise so
    a brand-new linked user still receives DMs without explicit subscribe."""
    n = _build_notifier()
    n.db_adapter.fetch_all = AsyncMock(return_value=[])
    out = await n._subscription_map(42)
    assert "discord" in out
    assert out["discord"]["enabled"] is True
    assert out["discord"]["channel_address"] == "42"


@pytest.mark.asyncio
async def test_subscription_map_does_not_overwrite_explicit_discord_row():
    """If discord row exists in DB → use it, do NOT replace with default.
    Pin so a user who explicitly disabled Discord stays disabled."""
    n = _build_notifier()
    n.db_adapter.fetch_all = AsyncMock(return_value=[
        ("discord", False, "explicit-id"),
    ])
    out = await n._subscription_map(42)
    assert out["discord"]["enabled"] is False
    assert out["discord"]["channel_address"] == "explicit-id"


@pytest.mark.asyncio
async def test_subscription_map_lowercases_channel_keys():
    """Channel type lowercased — pin so DB row "DISCORD" / "Telegram"
    still routes correctly downstream (which lowercases its lookups)."""
    n = _build_notifier()
    n.db_adapter.fetch_all = AsyncMock(return_value=[
        ("TELEGRAM", True, "@user"),
    ])
    out = await n._subscription_map(42)
    assert "telegram" in out
    assert "TELEGRAM" not in out


@pytest.mark.asyncio
async def test_subscription_map_handles_none_rows():
    """fetch_all returns None (some adapters do for empty result) →
    handled as empty list. Pin so a None doesn't crash with `not iterable`."""
    n = _build_notifier()
    n.db_adapter.fetch_all = AsyncMock(return_value=None)
    out = await n._subscription_map(42)
    # Discord default still added
    assert "discord" in out
    assert out["discord"]["channel_address"] == "42"
