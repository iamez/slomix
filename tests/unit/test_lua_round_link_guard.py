"""
Tests for round ID resolution via _resolve_round_id_for_metadata.

The current implementation does NOT have a max_diff_seconds parameter.
It delegates entirely to resolve_round_id_with_reason which uses
the window_minutes config to find candidates.
"""
from __future__ import annotations

import pytest

from bot.ultimate_bot import UltimateETLegacyBot


class _Cfg:
    round_match_window_minutes = 45


class _FakeBot:
    _resolve_round_id_for_metadata = UltimateETLegacyBot._resolve_round_id_for_metadata

    def __init__(self):
        self.config = _Cfg()
        self.db_adapter = object()


@pytest.mark.asyncio
async def test_resolve_round_id_for_metadata_rejects_large_live_diff(monkeypatch):
    """When resolve_round_id_with_reason returns no match, result is None."""
    async def _fake_resolve(*_args, **_kwargs):
        return None, {
            "reason_code": "no_candidates",
            "candidate_count": 0,
            "parsed_candidate_count": 0,
            "best_diff_seconds": None,
            "round_date": "2026-03-05",
        }

    monkeypatch.setattr(
        "bot.core.round_linker.resolve_round_id_with_reason",
        _fake_resolve,
    )

    bot = _FakeBot()
    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746382,
    }

    round_id = await bot._resolve_round_id_for_metadata(None, metadata)
    assert round_id is None


@pytest.mark.asyncio
async def test_resolve_round_id_for_metadata_accepts_close_live_diff(monkeypatch):
    """When resolve_round_id_with_reason finds a match, return the round_id."""
    async def _fake_resolve(*_args, **_kwargs):
        return 10033, {
            "reason_code": "resolved",
            "candidate_count": 2,
            "parsed_candidate_count": 2,
            "best_diff_seconds": 3,
            "round_date": "2026-03-05",
        }

    monkeypatch.setattr(
        "bot.core.round_linker.resolve_round_id_with_reason",
        _fake_resolve,
    )

    bot = _FakeBot()
    metadata = {
        "map_name": "te_escape2",
        "round_number": 1,
        "round_end_unix": 1772746382,
    }

    round_id = await bot._resolve_round_id_for_metadata(None, metadata)
    assert round_id == 10033
