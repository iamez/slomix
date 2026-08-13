"""Regression: compute_prox_scores must exclude bot identities from the pool.

The prox-scores source queries carry no round-quality gate, so an omni-bot test
date produced an all-bot "ranking" and, on a mixed date (morning bot test +
evening real gather), bots sat inside the percentile pool distorting every real
player's rank. The filter is identity-based: OMNIBOT guid prefix (any case) or
a [BOT]-tagged name (ET colour codes stripped first, so "^o[B^7OT]" can't
sneak past).
"""
from unittest.mock import AsyncMock

import pytest

import website.backend.services.prox_scoring as prox_scoring
from website.backend.services.prox_scoring import MIN_ENGAGEMENTS, compute_prox_scores


def _player(name, **extra):
    # Carries real values for all 5 scored v3.0 metrics so the
    # MIN_METRIC_WEIGHT_COVERAGE gate keeps the player in the ranking.
    return {
        "name": name, "engagements": MIN_ENGAGEMENTS + 5, "tracks": 3,
        "escape_rate": 0.4, "spawn_score": 0.6, "revive_rate_as_victim": 0.5,
        "distance_per_life": 900.0, "denied_time": 120.0,
        **extra,
    }


def _patch_sources(monkeypatch, raw_data):
    sources = [{"source": "combat_engagement", "success": True}]
    monkeypatch.setattr(
        prox_scoring, "_fetch_raw_metrics",
        AsyncMock(return_value=(raw_data, sources)),
    )


@pytest.mark.asyncio
async def test_bots_dropped_from_pool_and_response(monkeypatch):
    _patch_sources(monkeypatch, {
        "AAAA1111": _player("SQUUAZE"),
        "BBBB2222": _player("^pvid"),
        "OMNIBOT0500000000000000000000000": _player("^o[BOT]^7endekk"),
        "omnibot0300000000000000000000000": _player("bot lowercase guid"),
        "CCCC3333": _player("^o[B^7OT] colour-split name"),
    })
    res = await compute_prox_scores(db=AsyncMock())
    names = [p["name"] for p in res["players"]]
    assert res["status"] == "ok"
    assert sorted(names) == ["SQUUAZE", "^pvid"]  # only the two real players


@pytest.mark.asyncio
async def test_pure_bot_pool_yields_empty_ok(monkeypatch):
    _patch_sources(monkeypatch, {
        "OMNIBOT0100000000000000000000000": _player("^o[BOT]^7wajs"),
        "OMNIBOT0200000000000000000000000": _player("^o[BOT]^7lagger"),
    })
    res = await compute_prox_scores(db=AsyncMock())
    assert res["status"] == "ok"
    assert res["players"] == []
