"""Tests for guid_utils + correlation_context — small core helpers.

These tiny helpers are imported across ~15 sites: every render path
that has to fall back to a short GUID display, every async log line
that wants to embed the request correlation id. A regression silently:

- `short_guid` length drift (8 → 6) → display rows misalign across
  the whole site (different short forms in different spots).
- `short_guid` returns "" for None instead of "?" → embed rows
  collapse to invisible.
- `name_or_short_guid` returns "" for falsy name → frontend shows
  empty player name when the player has only a GUID.
- `get_correlation_id` returns a different id on each call within
  the same async context → distributed-trace correlation broken
  (every log line gets a fresh id).
- `set_correlation_id` doesn't actually update the contextvar →
  caller's "set this CID for the request" silently no-ops.

Pin every branch.
"""
from __future__ import annotations

import asyncio

import pytest

from bot.core.correlation_context import (
    get_correlation_id,
    set_correlation_id,
)
from bot.core.guid_utils import (
    GUID_MISSING_PLACEHOLDER,
    GUID_SHORT_LEN,
    name_or_short_guid,
    short_guid,
)

# ---------------------------------------------------------------------------
# Constants — pin display-form invariants
# ---------------------------------------------------------------------------


def test_short_guid_length_pinned_at_8():
    """Short-guid length is 8 chars (matches every LEFT(guid, 8) join
    in legacy SQL). Pin so a refactor doesn't desync display from DB."""
    assert GUID_SHORT_LEN == 8


def test_missing_placeholder_is_question_mark():
    """Missing-guid placeholder = "?". Pin so embed rows render
    consistently across the site."""
    assert GUID_MISSING_PLACEHOLDER == "?"


# ---------------------------------------------------------------------------
# short_guid — main display helper
# ---------------------------------------------------------------------------


def test_short_guid_truncates_full_guid_to_8_chars():
    """Standard 32-char hex GUID → first 8 chars."""
    assert short_guid("abcdef0123456789abcdef0123456789") == "abcdef01"


def test_short_guid_returns_placeholder_for_none():
    """None → "?" (NOT empty string — placeholder is visible in embeds)."""
    assert short_guid(None) == "?"


def test_short_guid_returns_placeholder_for_empty():
    assert short_guid("") == "?"


def test_short_guid_passes_through_short_input_unchanged():
    """If input is already shorter than 8 → returned as-is.
    Pin so OMNIBOT0 short prefixes don't get padded with junk."""
    assert short_guid("short") == "short"
    assert short_guid("a") == "a"


def test_short_guid_handles_exactly_8_chars():
    """Exactly 8 chars → identity."""
    assert short_guid("12345678") == "12345678"


def test_short_guid_handles_unicode_input():
    """Pin so non-ASCII characters in a guid don't crash slice."""
    assert short_guid("éàüñæ123456789") == "éàüñæ123"


def test_short_guid_does_not_strip_whitespace():
    """Whitespace passes through. Pin observed semantics — caller
    is responsible for trimming. A future refactor that strips
    whitespace here would change the function contract."""
    assert short_guid("  abcdef  ") == "  abcdef"


# ---------------------------------------------------------------------------
# name_or_short_guid — name-first fallback
# ---------------------------------------------------------------------------


def test_name_or_short_guid_prefers_name():
    """Non-empty name → returned (NOT the GUID)."""
    assert name_or_short_guid("Dmon", "abcdef0123456789") == "Dmon"


def test_name_or_short_guid_falls_back_when_name_empty():
    """Empty name → short_guid form."""
    assert name_or_short_guid("", "abcdef0123456789") == "abcdef01"


def test_name_or_short_guid_falls_back_when_name_none():
    """None name → short_guid form."""
    assert name_or_short_guid(None, "abcdef0123456789") == "abcdef01"


def test_name_or_short_guid_returns_placeholder_when_both_missing():
    """Both None → "?". Pin so a totally-missing player still has
    a visible row marker (not blank)."""
    assert name_or_short_guid(None, None) == "?"
    assert name_or_short_guid("", "") == "?"


def test_name_or_short_guid_short_name_passes_through():
    """A 1-char name still wins (no minimum length validation here)."""
    assert name_or_short_guid("X", "abcdef0123456789") == "X"


def test_name_or_short_guid_returns_name_with_spaces():
    """Whitespace-only name is FALSY for the helper but observed:
    `bool("   ")` is True → returned as-is. Pin observed.
    Caller is responsible for trimming."""
    assert name_or_short_guid("   ", "abcdef0123456789") == "   "


# ---------------------------------------------------------------------------
# get_correlation_id — async context-local ID
# ---------------------------------------------------------------------------


def test_get_correlation_id_creates_one_on_first_call():
    """First call in a fresh context → generates a new 8-char hex id.
    Pin the format (length 8, hex)."""
    async def _run():
        cid = get_correlation_id()
        assert isinstance(cid, str)
        assert len(cid) == 8
        # All hex chars
        int(cid, 16)
        return cid

    out = asyncio.run(_run())
    assert out is not None


def test_get_correlation_id_idempotent_within_context():
    """Two calls in the same async context → same id. Pin distributed-
    trace correlation: every log line in a request gets the same cid."""
    async def _run():
        a = get_correlation_id()
        b = get_correlation_id()
        c = get_correlation_id()
        assert a == b == c

    asyncio.run(_run())


def test_get_correlation_id_different_contexts_get_different_ids():
    """Two separate event loops / fresh contexts → different ids.
    Pin so two concurrent requests don't share a cid by accident."""
    async def _run_and_return():
        return get_correlation_id()

    a = asyncio.run(_run_and_return())
    b = asyncio.run(_run_and_return())
    assert a != b  # different contextvar instances


# ---------------------------------------------------------------------------
# set_correlation_id — explicit override (e.g., from inbound header)
# ---------------------------------------------------------------------------


def test_set_correlation_id_overrides_generated():
    """An explicit set → subsequent get returns that exact id. Pin so
    a request handler can adopt the X-Correlation-Id from upstream."""
    async def _run():
        set_correlation_id("INHERITED-1234")
        assert get_correlation_id() == "INHERITED-1234"

    asyncio.run(_run())


def test_set_correlation_id_does_not_persist_across_contexts():
    """Setting a CID in one async context shouldn't leak into a
    fresh context. Pin contextvar semantics."""
    async def _set_and_check():
        set_correlation_id("CONTEXT-A")
        assert get_correlation_id() == "CONTEXT-A"

    async def _check_fresh():
        # No set → fresh CID generated; should NOT be "CONTEXT-A"
        cid = get_correlation_id()
        assert cid != "CONTEXT-A"

    asyncio.run(_set_and_check())
    asyncio.run(_check_fresh())


def test_set_correlation_id_accepts_any_string_form():
    """No format validation — caller can pass any string. Pin observed
    semantics so an UUID inherited from upstream isn't rejected."""
    async def _run():
        set_correlation_id("very-long-uuid-1234-5678-90ab-cdef")
        assert get_correlation_id() == "very-long-uuid-1234-5678-90ab-cdef"

    asyncio.run(_run())


@pytest.mark.asyncio
async def test_correlation_id_persists_across_awaits():
    """Within the same async task, awaiting other coroutines preserves
    the cid. Pin so a multi-step async request retains its trace."""
    set_correlation_id("ACROSS-AWAIT")
    cid_before = get_correlation_id()
    await asyncio.sleep(0)  # yield to event loop
    cid_after = get_correlation_id()
    assert cid_before == cid_after == "ACROSS-AWAIT"
