"""Prediction shadow program v2 (audit AUD-006; remediation plan §5).

Pins the shadow-program contracts:
- deterministic, order-invariant prediction_event_key (dedup);
- factor queries gate on valid/human rounds and the as-of temporal cutoff
  (no leakage of rounds completed after prediction time);
- factors report available/sample_size instead of passing neutral 0.5 off
  as evidence;
- store_prediction dedups on event-key conflict and records shadow state.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from bot.services.prediction_engine import (
    MODEL_VERSION,
    PredictionEngine,
    compute_event_key,
)

A = ["AAAA1111", "BBBB2222", "CCCC3333"]
B = ["DDDD4444", "EEEE5555", "FFFF6666"]
AS_OF = datetime(2026, 7, 14, 21, 30, 0)  # noqa: DTZ001 naive datetime intentional — project convention


class QueryCapturingDB:
    """Returns canned rows and records every query for gate assertions."""

    def __init__(self, fetch_one_results=None):
        self.queries: list[tuple[str, tuple]] = []
        self.fetch_one_results = list(fetch_one_results or [])

    async def fetch_all(self, query, params=()):
        self.queries.append((query, params))
        return []

    async def fetch_one(self, query, params=()):
        self.queries.append((query, params))
        if self.fetch_one_results:
            return self.fetch_one_results.pop(0)
        return None

    async def execute(self, query, params=()):
        self.queries.append((query, params))


# ── event key ────────────────────────────────────────────────────────


def test_event_key_is_deterministic():
    k1 = compute_event_key("2026-07-14", "3v3", A, B, "supply")
    k2 = compute_event_key("2026-07-14", "3v3", A, B, "supply")
    assert k1 == k2 and len(k1) == 64


def test_event_key_is_team_order_invariant():
    assert compute_event_key("2026-07-14", "3v3", A, B) == \
        compute_event_key("2026-07-14", "3v3", B, A)


def test_event_key_is_roster_order_invariant():
    assert compute_event_key("2026-07-14", "3v3", A, B) == \
        compute_event_key("2026-07-14", "3v3", list(reversed(A)), B)


def test_event_key_changes_with_roster_date_format_map():
    base = compute_event_key("2026-07-14", "3v3", A, B, "supply")
    assert compute_event_key("2026-07-15", "3v3", A, B, "supply") != base
    assert compute_event_key("2026-07-14", "4v4", A, B, "supply") != base
    assert compute_event_key("2026-07-14", "3v3", A[:2] + ["XXXX9999"], B, "supply") != base
    assert compute_event_key("2026-07-14", "3v3", A, B, "radar") != base


# ── factor query gates ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_factor_queries_gate_on_valid_human_rounds_and_as_of():
    db = QueryCapturingDB()
    engine = PredictionEngine(db)
    await engine.predict_match(A, B, map_name="supply", as_of=AS_OF)

    factor_queries = [q for q, _ in db.queries
                      if "player_comprehensive_stats" in q]
    assert factor_queries, "expected factor queries to run"
    for q in factor_queries:
        assert "JOIN rounds r ON r.id = pcs.round_id" in q, (
            "factor query must join rounds for validity gates"
        )
        assert "r.is_valid = TRUE" in q
        assert "COALESCE(r.is_bot_round, FALSE) = FALSE" in q
        assert "round_end_unix" in q, (
            "temporal cutoff must use round completion timestamps"
        )

    # The as_of unix timestamp must appear in the factor query params.
    as_of_unix = int(AS_OF.timestamp())
    factor_params = [p for q, p in db.queries
                     if "player_comprehensive_stats" in q]
    assert all(as_of_unix in p for p in factor_params)


@pytest.mark.asyncio
async def test_prediction_reports_model_version_coverage_and_reasons():
    db = QueryCapturingDB()
    engine = PredictionEngine(db)
    pred = await engine.predict_match(A, B, as_of=AS_OF)

    assert pred["model_version"] == MODEL_VERSION
    assert pred["as_of"] == AS_OF.isoformat()
    assert set(pred["coverage"]) == {"h2h", "form", "map", "subs"}
    for cov in pred["coverage"].values():
        assert set(cov) >= {"available", "sample_size"}
    # Empty DB → nothing is available; the neutral 0.5s are placeholders,
    # not evidence, and every factor lands in eligibility_reasons.
    assert not any(c["available"] for c in pred["coverage"].values())
    assert "h2h_unavailable" in pred["eligibility_reasons"]
    assert "form_unavailable" in pred["eligibility_reasons"]


# ── store dedup + shadow state ───────────────────────────────────────


def _split_data():
    return {
        "format": "3v3",
        "team_a_channel_id": 1,
        "team_b_channel_id": 2,
        "team_a_guids": A,
        "team_b_guids": B,
        "team_a_discord_ids": [11, 12, 13],
        "team_b_discord_ids": [21, 22, 23],
        "guid_coverage": 1.0,
    }


def _prediction():
    return {
        "team_a_win_probability": 0.6,
        "team_b_win_probability": 0.4,
        "confidence": "low",
        "confidence_score": 0.3,
        "weighted_score": 0.55,
        "key_insight": "test",
        "factors": {
            "h2h": {"score": 0.5},
            "form": {"score": 0.6},
            "map": {"score": 0.5},
            "subs": {"score": 0.5},
        },
        "coverage": {"h2h": {"available": False, "sample_size": 0}},
        "eligibility_reasons": ["h2h_unavailable"],
        "model_version": MODEL_VERSION,
    }


@pytest.mark.asyncio
async def test_store_prediction_records_shadow_state_and_event_key():
    db = QueryCapturingDB(fetch_one_results=[(42,)])
    engine = PredictionEngine(db)
    pid = await engine.store_prediction(_prediction(), _split_data(), "2026-07-14")
    assert pid == 42

    insert_q, insert_p = next(
        (q, p) for q, p in db.queries if "INSERT INTO match_predictions" in q
    )
    assert "ON CONFLICT (prediction_event_key)" in insert_q
    assert "publish_state" in insert_q and "feature_snapshot" in insert_q
    assert "shadow" in insert_p
    expected_key = compute_event_key("2026-07-14", "3v3", A, B)
    assert expected_key in insert_p


@pytest.mark.asyncio
async def test_store_prediction_dedups_on_conflict():
    """Conflict (RETURNING id → None) must return the EXISTING row's id."""
    db = QueryCapturingDB(fetch_one_results=[None, (7,)])
    engine = PredictionEngine(db)
    pid = await engine.store_prediction(_prediction(), _split_data(), "2026-07-14")
    assert pid == 7
    lookup = [q for q, _ in db.queries
              if "WHERE prediction_event_key" in q and "SELECT id" in q]
    assert lookup, "dedup path must fetch the existing row"


@pytest.mark.asyncio
async def test_store_prediction_published_state_passthrough():
    db = QueryCapturingDB(fetch_one_results=[(1,)])
    engine = PredictionEngine(db)
    await engine.store_prediction(
        _prediction(), _split_data(), "2026-07-14", publish_state="published"
    )
    _, insert_p = next(
        (q, p) for q, p in db.queries if "INSERT INTO match_predictions" in q
    )
    assert "published" in insert_p


# ── outcome brier ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outcome_stores_raw_brier_and_null_for_draw():
    db = QueryCapturingDB(fetch_one_results=[(0.7, 0.3)])
    engine = PredictionEngine(db)
    await engine.update_prediction_outcome(5, actual_winner=1,
                                           team_a_score=3, team_b_score=1)
    update_p = next(p for q, p in db.queries if "UPDATE match_predictions" in q)
    # (actual, a, b, correct, accuracy, brier, id)
    assert update_p[5] == pytest.approx((1.0 - 0.7) ** 2)

    db2 = QueryCapturingDB(fetch_one_results=[(0.7, 0.3)])
    engine2 = PredictionEngine(db2)
    await engine2.update_prediction_outcome(5, actual_winner=0,
                                            team_a_score=1, team_b_score=1)
    update_p2 = next(p for q, p in db2.queries if "UPDATE match_predictions" in q)
    assert update_p2[5] is None, "draw must not enter binary calibration"
