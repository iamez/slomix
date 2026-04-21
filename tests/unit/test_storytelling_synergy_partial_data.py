"""Regression test for audit F9: partial_data signal.

Synergy endpoint used to return `None` silently when a session had
rows but no R1 data (typical post-surrender crash scenarios). The
frontend then rendered a degenerate single-group layout.

Fix propagates `status: "partial_data"` with a machine-readable reason
through the endpoint, so consumers can show an "Insufficient data"
badge instead.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from website.backend.services.storytelling.service import StorytellingService


@pytest.mark.asyncio
async def test_synergy_returns_partial_data_when_r1_missing():
    db = AsyncMock()
    # Rows exist but all are round_number=2 — no R1 → partial_data.
    db.fetch_all.return_value = [
        ("GUID1", "alpha", 2, 1, 1_700_000_000),
        ("GUID2", "bravo", 2, 2, 1_700_000_000),
    ]

    svc = StorytellingService(db)
    result = await svc.compute_team_synergy(date(2026, 4, 21))

    assert result["status"] == "partial_data"
    assert result["reason"] == "no_r1_data"
    assert result["groups"] == {}


@pytest.mark.asyncio
async def test_build_player_groups_returns_groups_on_r1_present():
    """Directly exercise `_build_player_groups` with R1 rows present:
    must return the full shape (with the new defaulted_players_count
    key) and NOT the partial_data sentinel."""
    db = AsyncMock()
    db.fetch_all.return_value = [
        ("GUID_A1", "alpha", 1, 1, 1_700_000_000),
        ("GUID_B1", "bravo", 1, 2, 1_700_000_000),
    ]

    svc = StorytellingService(db)
    groups = await svc._build_player_groups(date(2026, 4, 21))

    assert groups is not None
    assert "_status" not in groups  # partial_data sentinel absent
    assert "group_a_players" in groups
    assert "defaulted_players_count" in groups


@pytest.mark.asyncio
async def test_synergy_no_data_when_no_rows():
    db = AsyncMock()
    db.fetch_all.return_value = []

    svc = StorytellingService(db)
    result = await svc.compute_team_synergy(date(2026, 4, 21))

    assert result["status"] == "no_data"
    assert result["groups"] == {}
