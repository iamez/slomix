"""Proximity Score v2 quality contract (audit AUD-008).

Before: ten independent source queries ran with return_exceptions=True; a
failed source was omitted, its metrics silently became neutral 0.5, and the
endpoint returned a normal-looking ranking. These tests pin the fix:

- ANY source failure → status=degraded, ranking_available=False, players=[]
  (never neutral substitution);
- midrank percentiles → an all-equal cohort scores 0.5, not 1.0;
- a player below the metric-weight coverage threshold is dropped from the
  leaderboard (but a single-player request still returns them, flagged);
- every player row carries metric_weight_coverage + missing_metrics.
"""
from __future__ import annotations

import pytest

from website.backend.services import prox_scoring
from website.backend.services.prox_scoring import (
    FORMULA_VERSION_QUALITY,
    _percentile_rank_midrank,
    compute_prox_scores,
)

# The 10 source labels _fetch_raw_metrics queries, in order.
SOURCE_LABELS = [
    "combat_engagement", "proximity_reaction_metric", "proximity_spawn_timing",
    "player_track", "proximity_kill_outcome_killer", "proximity_kill_outcome_victim",
    "proximity_hit_region", "proximity_crossfire_opportunity",
    "proximity_lua_trade_kill", "proximity_focus_fire",
]


# ── midrank percentile ───────────────────────────────────────────────


def test_midrank_all_equal_is_half():
    assert _percentile_rank_midrank([5.0, 5.0, 5.0]) == pytest.approx([0.5, 0.5, 0.5])


def test_midrank_unique_top_is_one_bottom_is_zero():
    out = _percentile_rank_midrank([1.0, 2.0, 3.0])
    assert out == pytest.approx([0.0, 0.5, 1.0])


def test_midrank_single_value_is_neutral():
    assert _percentile_rank_midrank([42.0]) == [0.5]


def test_midrank_preserves_input_order():
    assert _percentile_rank_midrank([3.0, 1.0, 2.0]) == pytest.approx([1.0, 0.0, 0.5])


def test_midrank_partial_ties_average():
    # [1, 2, 2, 4]: the two 2s span the middle → (1 + (2-1)/2)/(4-1) = 1.5/3 = 0.5
    out = _percentile_rank_midrank([1.0, 2.0, 2.0, 4.0])
    assert out[1] == pytest.approx(0.5)
    assert out[2] == pytest.approx(0.5)


# ── quality contract via a fake DB ───────────────────────────────────


def _full_metric_row(guid, name):
    """A player row carrying every metric so coverage is 100%."""
    return {
        "escape_rate": 0.5, "return_fire_ms": 400.0, "dodge_ms": 300.0,
        "kpr": 0.5, "peak_speed": 300.0, "headshot_pct": 0.3,
        "spawn_score": 0.5, "crossfire_rate": 0.4, "support_reaction_ms": 500.0,
        "trades_per_session": 2.0, "revive_rate_as_victim": 0.3,
        "focus_survival": 0.5, "distance_per_life": 1000.0,
        "sprint_discipline": 0.5, "post_spawn_rush": 500.0,
        "stance_variety": 0.5, "timed_kills": 3.0, "denied_time": 400.0,
    }


class FakeDB:
    """Serves canned per-source rows, or raises for a chosen failing source.

    `source_rows` (label → list of row tuples matching THAT source's real
    SELECT column order) exercises the actual SQL-merge logic — IMP-003's
    review point that injecting pre-merged dicts proves nothing about the
    merge itself.
    """

    def __init__(self, fail_source: str | None = None, players=None,
                 source_rows: dict | None = None):
        self.fail_source = fail_source
        self.players = players or {}
        self.source_rows = source_rows or {}
        self._call = 0

    async def fetch_all(self, query, params=()):
        idx = self._call
        self._call += 1
        label = SOURCE_LABELS[idx] if idx < len(SOURCE_LABELS) else "?"
        if label == self.fail_source:
            raise RuntimeError(f"{label} boom")
        if label in self.source_rows:
            return self.source_rows[label]
        # combat_engagement row: (guid, name, engagements, escape_rate,
        # sessions_played) — mirrors the production SELECT.
        if label == "combat_engagement":
            return [
                (g, p["name"], p["engagements"], p.get("escape_rate", 0.5),
                 p.get("sessions_played", 1))
                for g, p in self.players.items()
            ]
        return []


@pytest.mark.asyncio
async def test_any_source_failure_returns_degraded(monkeypatch):
    result = await compute_prox_scores(FakeDB(fail_source="proximity_hit_region"))
    assert result["status"] == "degraded"
    assert result["formula_version"] == FORMULA_VERSION_QUALITY
    assert result["quality"]["ranking_available"] is False
    assert "proximity_hit_region" in result["quality"]["failed_sources"]
    assert result["players"] == []


def test_canonical_formula_version_is_v2_1():
    """2.1 = IMP-003 semantics (trades denominator = sessions PLAYED,
    exact-round true-zero fill, single-player MIN_ENGAGEMENTS)."""
    assert prox_scoring.FORMULA_VERSION == "2.1"
    assert prox_scoring.FORMULA_VERSION_QUALITY == "prox-web-v2.1"


@pytest.mark.asyncio
async def test_healthy_sources_but_no_data_is_ok_empty():
    result = await compute_prox_scores(FakeDB(players={}))
    assert result["status"] == "ok"
    assert result["quality"]["ranking_available"] is False  # no players
    assert result["players"] == []
    assert result["quality"]["failed_sources"] == []
    # Quality shape is dataset-independent: below_coverage_dropped is always
    # present, even on an empty healthy response (Codex #512).
    assert result["quality"]["below_coverage_dropped"] == 0


@pytest.mark.asyncio
async def test_player_rows_carry_coverage_and_missing_metrics(monkeypatch):
    # Inject a fully-covered player via _fetch_raw_metrics monkeypatch so we
    # exercise the scoring/coverage path directly, not the SQL merge.
    async def fake_fetch(db, range_days, **kwargs):
        players = {
            "GUID_AAAA": {**_full_metric_row("GUID_AAAA", "Alpha"),
                          "name": "Alpha", "engagements": 40, "tracks": 10},
            "GUID_BBBB": {**_full_metric_row("GUID_BBBB", "Bravo"),
                          "name": "Bravo", "engagements": 30, "tracks": 8},
        }
        sources = [{"source": s, "success": True, "row_count": 2,
                    "error_code": None, "duration_ms": 5} for s in SOURCE_LABELS]
        return players, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object())
    assert result["status"] == "ok"
    assert result["quality"]["ranking_available"] is True
    assert len(result["players"]) == 2
    for p in result["players"]:
        assert p["metric_weight_coverage"] == pytest.approx(1.0)
        assert p["missing_metrics"] == []


@pytest.mark.asyncio
async def test_low_coverage_player_dropped_from_leaderboard(monkeypatch):
    async def fake_fetch(db, range_days, **kwargs):
        full = {**_full_metric_row("GUID_FULL", "Full"),
                "name": "Full", "engagements": 40, "tracks": 10}
        # Sparse player: only escape_rate present → coverage well below 80%.
        sparse = {"escape_rate": 0.5, "name": "Sparse",
                  "engagements": 40, "tracks": 10}
        sources = [{"source": s, "success": True, "row_count": 2,
                    "error_code": None, "duration_ms": 5} for s in SOURCE_LABELS]
        return {"GUID_FULL": full, "GUID_SPARSE": sparse}, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object())
    guids = {p["guid"] for p in result["players"]}
    assert "GUID_FULL" in guids
    assert "GUID_SPARSE" not in guids, "sub-threshold player must not be ranked"
    assert result["quality"]["below_coverage_dropped"] == 1


def test_metric_effective_weights_match_category_weighting():
    """Coverage weights must equal CATEGORY_WEIGHTS x within-category share and
    sum to the CATEGORY_WEIGHTS total, not treat each category as ~1/3 (#512)."""
    eff = prox_scoring._metric_effective_weights()  # noqa: SLF001
    assert sum(eff.values()) == pytest.approx(sum(prox_scoring.CATEGORY_WEIGHTS.values()))
    # escape_rate: Combat(0.40) x (0.20 / combat_total 1.0) = 0.08
    assert eff["escape_rate"] == pytest.approx(0.08)
    # stance_variety: Game Sense(0.25) x (0.15 / 1.0) = 0.0375
    assert eff["stance_variety"] == pytest.approx(0.0375)


@pytest.mark.asyncio
async def test_response_coverage_is_min_of_returned_players(monkeypatch):
    async def fake_fetch(db, range_days, **kwargs):
        full = {**_full_metric_row("GUID_FULL", "Full"),
                "name": "Full", "engagements": 40, "tracks": 10}
        partial = {**_full_metric_row("GUID_PART", "Part"),
                   "name": "Part", "engagements": 40, "tracks": 10}
        del partial["stance_variety"]  # drop one light metric → coverage ~0.96
        sources = [{"source": s, "success": True, "row_count": 2,
                    "error_code": None, "duration_ms": 5} for s in SOURCE_LABELS]
        return {"GUID_FULL": full, "GUID_PART": partial}, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object())
    assert len(result["players"]) == 2  # both above the 0.80 gate
    cov = result["quality"]["metric_weight_coverage"]
    assert cov < 1.0, "response coverage must reflect the least-covered player"
    assert cov == pytest.approx(min(p["metric_weight_coverage"] for p in result["players"]))


@pytest.mark.asyncio
async def test_none_valued_metric_counts_as_missing(monkeypatch):
    """A preserved NULL aggregate (None, not coalesced 0) must count as missing
    coverage, not real data (Codex #512)."""
    async def fake_fetch(db, range_days, **kwargs):
        row = {**_full_metric_row("GUID_X", "X"),
               "name": "X", "engagements": 40, "tracks": 10}
        row["denied_time"] = None  # NULL aggregate now preserved as None
        sources = [{"source": s, "success": True, "row_count": 1,
                    "error_code": None, "duration_ms": 5} for s in SOURCE_LABELS]
        return {"GUID_X": row}, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object(), player_guid="GUID_X")
    p = result["players"][0]
    assert "denied_time" in p["missing_metrics"]
    assert p["metric_weight_coverage"] < 1.0


@pytest.mark.asyncio
async def test_single_player_request_returns_low_coverage_player(monkeypatch):
    async def fake_fetch(db, range_days, **kwargs):
        sparse = {"escape_rate": 0.5, "name": "Sparse",
                  "engagements": 40, "tracks": 10}
        sources = [{"source": s, "success": True, "row_count": 1,
                    "error_code": None, "duration_ms": 5} for s in SOURCE_LABELS]
        return {"GUID_SPARSE": sparse}, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object(), player_guid="GUID_SPARSE")
    assert len(result["players"]) == 1
    p = result["players"][0]
    assert p["guid"] == "GUID_SPARSE"
    assert p["metric_weight_coverage"] < prox_scoring.MIN_METRIC_WEIGHT_COVERAGE
    assert len(p["missing_metrics"]) > 0


# ── SQL-merge level contracts (IMP-003) — real _fetch_raw_metrics rows ───────


QUAL = {"GUID_Q": {"name": "Q", "engagements": 40, "sessions_played": 3}}

EXACT_SCOPE = {"session_date": "2026-07-18", "map_name": "supply",
               "round_number": 1, "round_start_unix": 1721300000}


@pytest.mark.asyncio
async def test_trades_denominator_is_sessions_played():
    """1 trade across 3 PLAYED sessions = 1/3, not 1.0 (the old
    sessions-with-a-trade denominator) — IMP-003."""
    db = FakeDB(players=QUAL, source_rows={
        "proximity_lua_trade_kill": [("GUID_Q", "Q", 1)],
    })
    players, sources = await prox_scoring._fetch_raw_metrics(db, 30)  # noqa: SLF001
    assert all(s["success"] for s in sources)
    assert players["GUID_Q"]["trades_per_session"] == pytest.approx(1 / 3)


@pytest.mark.asyncio
async def test_trades_without_participation_denominator_stay_missing():
    """Trade rows for a player with NO engagement rows in scope have no sound
    sessions-played denominator → the metric stays missing, never guessed."""
    db = FakeDB(players=QUAL, source_rows={
        "proximity_lua_trade_kill": [("GUID_GHOST", "Ghost", 5)],
    })
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30)  # noqa: SLF001
    assert "trades_per_session" not in players["GUID_GHOST"]


@pytest.mark.asyncio
async def test_exact_round_scope_zero_fills_count_metrics():
    """Exact-round scope + ANOTHER player's event in the same round (shared
    tracker artifact captured the signal) → a qualified player absent from the
    source genuinely recorded ZERO trades / timed kills."""
    db = FakeDB(players=QUAL, source_rows={
        "proximity_lua_trade_kill": [("GUID_OTHER", "Other", 2)],
        "proximity_spawn_timing": [("GUID_OTHER", "Other", 0.5, 3)],
    })
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30, **EXACT_SCOPE)  # noqa: SLF001
    assert players["GUID_Q"]["trades_per_session"] == 0.0
    assert players["GUID_Q"]["timed_kills"] == 0.0


@pytest.mark.asyncio
async def test_broad_window_never_zero_fills():
    """A range_days window mixes pre/post-feature periods → missing stays
    MISSING (no presumed zero) until a capability manifest exists."""
    db = FakeDB(players=QUAL, source_rows={
        "proximity_lua_trade_kill": [("GUID_OTHER", "Other", 2)],
        "proximity_spawn_timing": [("GUID_OTHER", "Other", 0.5, 3)],
    })
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30)  # broad scope  # noqa: SLF001
    assert "trades_per_session" not in players["GUID_Q"]
    assert "timed_kills" not in players["GUID_Q"]


@pytest.mark.asyncio
async def test_exact_round_no_fill_without_capture_proof():
    """Exact-round scope but the source returned ZERO rows — capture is not
    proven, so nothing is zero-filled."""
    db = FakeDB(players=QUAL)  # trade + spawn sources return []
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30, **EXACT_SCOPE)  # noqa: SLF001
    assert "trades_per_session" not in players["GUID_Q"]
    assert "timed_kills" not in players["GUID_Q"]


@pytest.mark.asyncio
async def test_crossfire_is_never_zero_filled():
    """Without crossfire OPPORTUNITIES the ratio is mathematically undefined —
    absent stays missing even in exact-round scope; a true 0 (opportunities>0,
    executed=0) already comes back from the query itself."""
    db = FakeDB(players=QUAL, source_rows={
        "proximity_crossfire_opportunity": [("GUID_OTHER", 4, 0)],
        "proximity_lua_trade_kill": [("GUID_OTHER", "Other", 1)],
    })
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30, **EXACT_SCOPE)  # noqa: SLF001
    assert "crossfire_rate" not in players["GUID_Q"]
    # …while the other player's real 0/4 IS a true zero from the query:
    assert players["GUID_OTHER"]["crossfire_rate"] == 0.0


@pytest.mark.asyncio
async def test_single_player_below_min_engagements_returns_empty():
    """A sub-MIN_ENGAGEMENTS single-player request returns NO player (the
    profile falls back to its labeled CF/TR estimate) — IMP-003."""
    players = {
        "GUID_Q": {"name": "Q", "engagements": 40, "sessions_played": 3},
        "GUID_LOW": {"name": "Low", "engagements": 3, "sessions_played": 1},
    }
    result = await compute_prox_scores(FakeDB(players=players),
                                       player_guid="GUID_LOW")
    assert result["status"] == "ok"
    assert result["players"] == []


@pytest.mark.asyncio
async def test_sentinel_or_empty_scope_params_never_zero_fill():
    """round_start_unix=0 (schema default for unlinked rows) and an empty
    map_name do NOT disambiguate a single round — such a scope must not
    enable the true-zero fill (Codex/Copilot on #518)."""
    rows = {
        "proximity_lua_trade_kill": [("GUID_OTHER", "Other", 2)],
        "proximity_spawn_timing": [("GUID_OTHER", "Other", 0.5, 3)],
    }
    for bad_scope in (
        {**EXACT_SCOPE, "round_start_unix": 0},
        {**EXACT_SCOPE, "map_name": ""},
    ):
        db = FakeDB(players=QUAL, source_rows=rows)
        players, _ = await prox_scoring._fetch_raw_metrics(db, 30, **bad_scope)  # noqa: SLF001
        assert "trades_per_session" not in players["GUID_Q"], bad_scope
        assert "timed_kills" not in players["GUID_Q"], bad_scope


@pytest.mark.asyncio
async def test_trades_denominator_covers_untargeted_sessions():
    """combat_engagement is target-only: a session where the player was never
    attacked would undercount participation and re-inflate the rate. The
    denominator is the MAX of engagement-sessions and track-sessions (both
    lower bounds) — Codex repro on #518: 1 trade, tracked in 3 sessions but
    targeted in only 1 → 1/3, not 1/1."""
    # player_track row: (guid, name, tracks, avg_speed, peak_speed, sprint,
    # distance, post_spawn, standing, crouching, prone, sessions_tracked)
    db = FakeDB(
        players={"GUID_Q": {"name": "Q", "engagements": 40, "sessions_played": 1}},
        source_rows={
            "player_track": [("GUID_Q", "Q", 12, 200.0, 350.0, 40.0,
                              900.0, 300.0, 10.0, 5.0, 1.0, 3)],
            "proximity_lua_trade_kill": [("GUID_Q", "Q", 1)],
        },
    )
    players, _ = await prox_scoring._fetch_raw_metrics(db, 30)  # noqa: SLF001
    assert players["GUID_Q"]["trades_per_session"] == pytest.approx(1 / 3)
