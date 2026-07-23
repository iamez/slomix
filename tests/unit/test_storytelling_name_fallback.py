"""Regression guards for the KIS-independent name fallback (E2E finding F5).

``compute_space_created`` / ``compute_enabler`` resolved player names ONLY
from ``storytelling_kill_impact`` — a cache table populated lazily by the
first KIS request for a session. Until that happened, both endpoints
returned ``#GUID8`` placeholders for every player (reproduced live on
2026-06-10, session 2026-06-09).

The fix adds ``_fallback_canonical_names`` (sourced from combat_engagement,
the same always-present source compute_gravity uses) merged UNDER the KIS
names. These tests pin that behaviour with an empty KIS table.

Also covers the lurker-profile ``coverage`` meta added in the same sweep.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.session_scope import GamingSessionScope
from website.backend.services.storytelling_service import StorytellingService

GUID32 = "EDBB5DA97C9F52151865C5F223F9B951"
KILLER32 = "FDA127DF5246F28D7355490F749DD894"
SD = date(2026, 5, 1)
SCOPE = GamingSessionScope(
    gaming_session_id=99,
    dates=("2026-05-01",),
    round_keys=((1781000000, "supply", 1),),
    accepted_round_count=1,
    distinct_map_names=("supply",),
)


def _svc_with_groups() -> StorytellingService:
    """Service with a pre-seeded player-groups cache (skips the PCS query)."""
    svc = StorytellingService(db=AsyncMock())
    svc._groups_cache[SCOPE.gaming_session_id] = {  # noqa: SLF001 — seed the memo (gsid key), skip the PCS query
        "guid_to_group": {GUID32[:8]: "A", KILLER32[:8]: "B"},
    }
    return svc


@pytest.mark.asyncio
async def test_fallback_canonical_names_strips_colors_and_skips_null() -> None:
    svc = StorytellingService(db=AsyncMock())
    svc.db.fetch_all = AsyncMock(return_value=[
        (GUID32[:8], "^6S^2uper^6B^2oyy"),
        (None, "ghost"),
    ])

    names = await svc._fallback_canonical_names(SCOPE)  # noqa: SLF001 — unit under test

    assert names == {GUID32[:8]: "SuperBoyy"}


@pytest.mark.asyncio
async def test_space_created_resolves_names_without_kis_rows() -> None:
    svc = _svc_with_groups()
    svc.db.fetch_all = AsyncMock(side_effect=[
        # kill_outcome rows: victim GUID32 dies, killer KILLER32, t=1000
        [(GUID32, KILLER32, 1000, 1, 1781000000)],
        [],  # storytelling_kill_impact canonical mapping — KIS EMPTY
        [],  # storytelling_kill_impact names — KIS EMPTY
        [(GUID32[:8], "^6S^2uper^6B^2oyy")],  # combat_engagement fallback
    ])

    result = await svc.compute_space_created(SCOPE)

    by_guid = {p["guid_short"]: p["name"] for p in result["players"]}
    assert by_guid[GUID32[:8]] == "SuperBoyy", (
        "names must resolve via the combat_engagement fallback when "
        "storytelling_kill_impact has not been populated yet (F5)"
    )


@pytest.mark.asyncio
async def test_enabler_resolves_names_without_kis_rows() -> None:
    svc = _svc_with_groups()
    svc.db.fetch_all = AsyncMock(side_effect=[
        # combat_engagement kill rows: killer KILLER32 kills GUID32
        [(GUID32, KILLER32, 10.0, 20.0, 1000, 1781000000, 1)],
        [],  # kill_impact canonical mapping — KIS EMPTY
        [],  # crossfire rows — KIS EMPTY
        [],  # trade rows
        [],  # kill_impact names — KIS EMPTY
        [(KILLER32[:8], "^3w^7ise^3B^7oy")],  # combat_engagement fallback
        [(KILLER32, 60000)],  # player_track alive time
    ])

    result = await svc.compute_enabler(SCOPE)

    by_guid = {p["guid_short"]: p["name"] for p in result["players"]}
    assert by_guid[KILLER32[:8]] == "wiseBoy", (
        "names must resolve via the combat_engagement fallback when "
        "storytelling_kill_impact has not been populated yet (F5)"
    )


@pytest.mark.asyncio
async def test_kis_names_win_over_fallback() -> None:
    """When KIS rows exist their names take precedence over the fallback."""
    svc = _svc_with_groups()
    svc.db.fetch_all = AsyncMock(side_effect=[
        [(GUID32, KILLER32, 1000, 1, 1781000000)],
        [(GUID32, GUID32[:8])],                      # canonical mapping
        [(GUID32[:8], "^6KIS-Name")],                # KIS names present
        [(GUID32[:8], "^6Fallback-Name")],           # fallback also present
    ])

    result = await svc.compute_space_created(SCOPE)

    by_guid = {p["guid_short"]: p["name"] for p in result["players"]}
    assert by_guid[GUID32[:8]] == "KIS-Name"


@pytest.mark.asyncio
async def test_lurker_profile_reports_coverage() -> None:
    svc = StorytellingService(db=AsyncMock())
    path = '[{"time": 0, "x": 0, "y": 0}, {"time": 1000, "x": 10, "y": 10}]'
    # The SQL already filters `path IS NOT NULL`, so the realistic skip cases
    # the worker sees are an empty array and unparseable JSON — use those.
    svc.db.fetch_all = AsyncMock(return_value=[
        (GUID32, "^6S^2uper^6B^2oyy", "AXIS", 1781000000, 0, 5000, 5000, path),
        (KILLER32, "^3w^7ise^3B^7oy", "AXIS", 1781000000, 0, 5000, 5000, "[]"),
        (KILLER32, "^3w^7ise^3B^7oy", "AXIS", 1781000000, 0, 5000, 5000, "{corrupt"),
    ])

    result = await svc.compute_lurker_profile(SD)

    assert result["coverage"] == {
        "tracks_fetched": 3,
        "tracks_used": 1,
        "tracks_skipped": 2,
    }, "empty/unparseable-path tracks must be counted as skipped, not silently dropped"
