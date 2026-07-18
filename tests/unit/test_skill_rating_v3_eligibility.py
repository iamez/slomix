"""ET Performance v3 honest-eligibility metadata + epoch-only bot gate (IMP-004).

The post-merge audit found v3 publishing `eligible_count` as if the round
threshold established eligibility, while per-round telemetry coverage (the
other half of eligibility) is unknowable until the migration-062 capability
backfill. These tests pin the honest contract:

- eligible_count is null + eligibility_status="pending_capabilities";
  round_qualified_count carries the >=MIN_ROUNDS_V3 tally;
- per-player telemetry_coverage is null (unknown, never a guessed fraction);
- the observation window ends at the last INCLUDED valid round, not "now";
- coverage is exposed as coverage_proxy (diagnostic, gates nothing);
- the is_bot_round gate exists ONLY in the epoch (v3 shadow) path — the live
  v2 all-time query stays untouched (owner-gated change).
"""
from __future__ import annotations

import pytest

from website.backend.services import skill_rating_v3
from website.backend.services.skill_rating_service import (
    PROXIMITY_METRICS,
    WEIGHTS,
    compute_all_ratings,
)
from website.backend.services.skill_rating_v3 import (
    EPOCH_START,
    MIN_ROUNDS_V3,
    compute_et_performance_v3,
)


def _player(guid: str, rounds: int, trade_rate: float = 0.0) -> dict:
    """Population entry as compute_all_ratings returns it (neutral proximity
    raws except an optional off-neutral trade_rate)."""
    neutral = {m: (1.0 if m == "kill_quality" else 0.0) for m in PROXIMITY_METRICS}
    raws = dict.fromkeys(WEIGHTS, 0.5) | neutral | {"trade_rate": trade_rate}
    return {
        "player_guid": guid,
        "display_name": guid,
        "rounds": rounds,
        "components": {m: {"raw": raws[m]} for m in WEIGHTS},
        "raw_stats": dict(raws),
    }


class _FakeDB:
    """Serves the observation_end query; records every call."""

    def __init__(self, max_round_date="2026-07-10"):
        self.max_round_date = max_round_date
        self.fetch_one_calls = []

    async def fetch_one(self, query, params=()):
        self.fetch_one_calls.append((query, params))
        return (self.max_round_date,)


@pytest.mark.asyncio
async def test_v3_metadata_is_honest_about_eligibility(monkeypatch):
    async def fake_pop(db, *, epoch_start=None, min_rounds=1):
        return [
            _player("QUAL_A", rounds=MIN_ROUNDS_V3 + 5, trade_rate=0.2),
            _player("QUAL_B", rounds=MIN_ROUNDS_V3),
            _player("BELOW", rounds=MIN_ROUNDS_V3 - 1),
        ]

    monkeypatch.setattr(skill_rating_v3, "compute_all_ratings", fake_pop)
    db = _FakeDB(max_round_date="2026-07-10")
    result = await compute_et_performance_v3(db)

    # Honest eligibility: null until capabilities are backfilled.
    assert result["eligible_count"] is None
    assert result["eligibility_status"] == "pending_capabilities"
    assert result["round_qualified_count"] == 2
    assert result["scored_count"] == 2
    assert result["unrated_reasons"]["below_min_rounds"] == 1

    # Observation window: starts at the epoch, ends at the last INCLUDED round.
    assert result["observation_start"] == EPOCH_START
    assert result["observation_end"] == "2026-07-10"
    # The end came from a real query with the epoch bound, not a clock read.
    query, params = db.fetch_one_calls[0]
    assert "MAX(pcs.round_date)" in query
    assert "is_bot_round" in query
    assert params == (EPOCH_START,)


@pytest.mark.asyncio
async def test_v3_players_carry_null_telemetry_coverage(monkeypatch):
    async def fake_pop(db, *, epoch_start=None, min_rounds=1):
        return [_player("A", rounds=25), _player("B", rounds=30)]

    monkeypatch.setattr(skill_rating_v3, "compute_all_ratings", fake_pop)
    result = await compute_et_performance_v3(_FakeDB())
    assert len(result["players"]) == 2
    for p in result["players"]:
        assert p["telemetry_coverage"] is None


@pytest.mark.asyncio
async def test_v3_coverage_is_a_labeled_proxy(monkeypatch):
    async def fake_pop(db, *, epoch_start=None, min_rounds=1):
        return [
            _player("SIGNAL", rounds=25, trade_rate=0.3),  # off-neutral
            _player("SILENT", rounds=25),                  # all-neutral
        ]

    monkeypatch.setattr(skill_rating_v3, "compute_all_ratings", fake_pop)
    result = await compute_et_performance_v3(_FakeDB())
    assert "coverage" not in result, "raw 'coverage' key must not claim precision"
    assert result["coverage_proxy"] == pytest.approx(0.5)
    assert "DIAGNOSTIC" in result["coverage_proxy_note"]


@pytest.mark.asyncio
async def test_v3_observed_players_per_metric(monkeypatch):
    async def fake_pop(db, *, epoch_start=None, min_rounds=1):
        return [
            _player("A", rounds=25, trade_rate=0.3),
            _player("B", rounds=25),
        ]

    monkeypatch.setattr(skill_rating_v3, "compute_all_ratings", fake_pop)
    result = await compute_et_performance_v3(_FakeDB())
    obs = result["observed_players"]
    assert obs["dpm"] == 2, "PCS metrics are observed for the whole cohort"
    assert obs["trade_rate"] == 1, "off-neutral proxy lower bound"
    assert obs["crossfire_rate"] is None, "unscoped metric is never observed"


# ── epoch-only is_bot_round gate ─────────────────────────────────────


class _QueryCaptureDB:
    def __init__(self):
        self.queries = []

    async def fetch_all(self, query, params=()):
        self.queries.append((query, params))
        return []


@pytest.mark.asyncio
async def test_bot_gate_present_only_in_epoch_path():
    epoch_db = _QueryCaptureDB()
    await compute_all_ratings(epoch_db, epoch_start=EPOCH_START, min_rounds=1)
    epoch_query = epoch_db.queries[0][0]
    assert "NOT COALESCE(is_bot_round, FALSE)" in epoch_query
    assert "V3_BOT_GATE" not in epoch_query, "marker must be fully substituted"
    # Gate accompanies EVERY rounds-validity subselect (PCS + 4 proximity).
    assert epoch_query.count("NOT COALESCE(is_bot_round, FALSE)") == \
        epoch_query.count("FROM rounds WHERE is_valid")


@pytest.mark.asyncio
async def test_live_v2_query_has_no_bot_round_gate():
    """The live v2 all-time population is owner-gated: without an epoch the
    query must not mention is_bot_round at all (IMP-004)."""
    v2_db = _QueryCaptureDB()
    await compute_all_ratings(v2_db)
    v2_query = v2_db.queries[0][0]
    assert "is_bot_round" not in v2_query
    assert "V3_BOT_GATE" not in v2_query
