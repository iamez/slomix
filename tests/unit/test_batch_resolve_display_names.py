"""Regression tests for batch_resolve_display_names ET color stripping.

Copilot review on PR #120 flagged that the helper had early-return paths
(after tier 1 / tier 2) that skipped strip_et_colors(), so callers got
raw `^N` color codes in display names depending on where the match
resolved. These tests pin every return path through the helper to
guarantee the color strip is always applied.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.routers.api_helpers import batch_resolve_display_names


def _fake_db(fetch_all_side_effects):
    """Build a DatabaseAdapter mock whose fetch_all yields each scripted batch."""
    db = AsyncMock()
    db.fetch_all = AsyncMock(side_effect=fetch_all_side_effects)
    return db


@pytest.mark.asyncio
async def test_empty_input_returns_empty_dict():
    db = _fake_db([])
    assert await batch_resolve_display_names(db, []) == {}


@pytest.mark.asyncio
async def test_tier1_early_return_strips_colors():
    """All names resolved via player_links → early return — must strip."""
    db = _fake_db([
        [("GUID1", "^1Red"), ("GUID2", "^3Yellow^7")],
    ])
    result = await batch_resolve_display_names(
        db, [("GUID1", "fallback1"), ("GUID2", "fallback2")]
    )
    assert result == {"GUID1": "Red", "GUID2": "Yellow"}


@pytest.mark.asyncio
async def test_tier2_early_return_strips_colors():
    """Half resolve via player_links, rest via player_aliases — early return after tier 2."""
    db = _fake_db([
        [("GUID1", "^2Green")],                      # tier 1: only GUID1
        [("GUID2", "^5Cyan^1!")],                    # tier 2: GUID2 via aliases
    ])
    result = await batch_resolve_display_names(
        db, [("GUID1", "f1"), ("GUID2", "f2")]
    )
    assert result == {"GUID1": "Green", "GUID2": "Cyan!"}


@pytest.mark.asyncio
async def test_tier3_fallback_strips_colors():
    """None resolve until tier 3 (player_comprehensive_stats) — final return."""
    db = _fake_db([
        [],                                          # tier 1: no matches
        [],                                          # tier 2: no matches
        [("GUID1", "^4Blue"), ("GUID2", "^0Black^7")],  # tier 3
    ])
    result = await batch_resolve_display_names(
        db, [("GUID1", "f1"), ("GUID2", "f2")]
    )
    assert result == {"GUID1": "Blue", "GUID2": "Black"}


@pytest.mark.asyncio
async def test_fallback_name_is_also_stripped():
    """Fallbacks are applied when no tier resolves — they also get stripped."""
    db = _fake_db([
        [],  # tier 1
        [],  # tier 2
        [],  # tier 3
    ])
    result = await batch_resolve_display_names(
        db, [("GUID1", "^8Orange"), ("GUID2", "^7White")]
    )
    assert result == {"GUID1": "Orange", "GUID2": "White"}


@pytest.mark.asyncio
async def test_mixed_tiers_and_fallbacks_all_stripped():
    """GUID1 via tier 1, GUID2 via tier 3, GUID3 falls back — every path stripped."""
    db = _fake_db([
        [("GUID1", "^1Alpha")],                      # tier 1
        [],                                          # tier 2 (empty)
        [("GUID2", "^2Beta")],                       # tier 3 — GUID3 misses
    ])
    result = await batch_resolve_display_names(
        db, [("GUID1", "fa"), ("GUID2", "fb"), ("GUID3", "^3Gamma")]
    )
    assert result == {"GUID1": "Alpha", "GUID2": "Beta", "GUID3": "Gamma"}


@pytest.mark.asyncio
async def test_no_color_codes_passthrough():
    """Plain names stay unchanged (sanity check — no over-stripping)."""
    db = _fake_db([
        [("GUID1", "PlainName")],
    ])
    result = await batch_resolve_display_names(db, [("GUID1", "fallback")])
    assert result == {"GUID1": "PlainName"}
