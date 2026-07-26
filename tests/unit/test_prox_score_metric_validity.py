"""#556: the prox_score composite may only weight metrics shown to matter.

Two of the retired metrics (`dodge_ms`, `sprint_discipline`) were not merely
uninformative — they were scoring players BACKWARDS, rewarding the behaviour
associated with LOSING the round. That is the failure mode worth a permanent
test: a re-added metric should have to survive the measurement first.

The measurement itself lives in the module header of prox_scoring.py
(within-round comparison, 95% CI bootstrapped over rounds).
"""
from __future__ import annotations

import pytest

from tests.unit.test_prox_scoring_quality import SOURCE_LABELS
from website.backend.services import prox_scoring

# Measured non-predictive of round outcome at 95% confidence in #556.
# Re-adding one to METRICS means re-running the measurement and updating this
# list with the new numbers — not deleting the entry to make the test pass.
RETIRED_BY_556 = {
    "headshot_pct", "return_fire_ms", "kpr", "peak_speed", "dodge_ms",
    "crossfire_rate", "support_reaction_ms", "trades_per_session",
    "focus_survival", "sprint_discipline", "post_spawn_rush",
    "stance_variety", "timed_kills",
}
# The two that measured INVERTED — these actively mis-rank players.
INVERTED_BY_556 = {"dodge_ms", "sprint_discipline"}

DEMONSTRATED = {
    "escape_rate", "spawn_score", "revive_rate_as_victim",
    "distance_per_life", "denied_time",
}


def _scored_metrics() -> set[str]:
    return {
        m for cat in prox_scoring.METRICS.values() for m in cat["metrics"]
    }


def test_no_retired_metric_carries_score_weight():
    leaked = _scored_metrics() & RETIRED_BY_556
    assert not leaked, (
        f"{sorted(leaked)} measured non-predictive of the round outcome in "
        f"#556 but still carry weight in the composite"
    )


def test_inverted_metrics_are_not_scored():
    """The sharpest failure: these ranked players in the wrong direction."""
    leaked = _scored_metrics() & INVERTED_BY_556
    assert not leaked, (
        f"{sorted(leaked)} measured INVERTED against round outcome — scoring "
        f"them ranks players by the behaviour that loses rounds"
    )


def test_scored_set_is_exactly_what_was_demonstrated():
    assert _scored_metrics() == DEMONSTRATED


def test_retired_metrics_are_still_reported():
    """Retired from the SCORE, not deleted — the UI must keep showing them."""
    reported = {
        m for cat in prox_scoring.RETIRED_METRICS.values() for m in cat
    }
    assert reported, "retired metrics vanished instead of becoming descriptive"
    assert not (reported & _scored_metrics()), (
        "a metric cannot be both scored and descriptive"
    )


def test_retired_metrics_contribute_zero():
    """A descriptive entry must be visibly weightless, not quietly folded in."""
    percentiles = {
        m: {"G": 0.9}
        for cat in prox_scoring.RETIRED_METRICS.values() for m in cat
    }
    raw = {"__guid__": "G"}
    for cat_key, retired in prox_scoring.RETIRED_METRICS.items():
        if not retired:
            continue
        _score, breakdown = prox_scoring._compute_category_score(  # noqa: SLF001
            raw, cat_key, percentiles,
        )
        desc = breakdown.get("__descriptive__", {})
        assert set(desc) == set(retired), f"{cat_key} lost descriptive metrics"
        for key, entry in desc.items():
            assert entry["contribution"] == 0.0, f"{key} still contributes"
            assert entry["weight"] == 0.0, f"{key} still carries weight"


def test_a_retired_metric_cannot_move_the_score():
    """Behavioural, not structural: change a retired metric's percentile from
    worst to best and the category score must not budge."""
    for cat_key, retired in prox_scoring.RETIRED_METRICS.items():
        if not retired:
            continue
        worst = {m: {"G": 0.0} for m in retired}
        best = {m: {"G": 1.0} for m in retired}
        raw = {"__guid__": "G"}
        s_worst, _ = prox_scoring._compute_category_score(raw, cat_key, worst)  # noqa: SLF001
        s_best, _ = prox_scoring._compute_category_score(raw, cat_key, best)  # noqa: SLF001
        assert s_worst == s_best, (
            f"{cat_key}: retired metrics still move the score "
            f"({s_worst} vs {s_best})"
        )


def test_coverage_weights_only_count_scored_metrics():
    eff = prox_scoring._metric_effective_weights()  # noqa: SLF001
    assert set(eff) == DEMONSTRATED
    assert sum(eff.values()) == pytest.approx(
        sum(prox_scoring.CATEGORY_WEIGHTS.values())
    )


def test_version_bumped_for_the_formula_change():
    assert prox_scoring.FORMULA_VERSION == "3.0"
    assert prox_scoring.FORMULA_VERSION_QUALITY == "prox-web-v3.0"


@pytest.mark.asyncio
async def test_descriptive_metrics_get_real_percentiles(monkeypatch):
    """A retired metric is still ranked — otherwise every descriptive row
    comes back at the neutral 0.5 fill, which reads as "average" rather than
    "not computed"."""
    from website.backend.services.prox_scoring import compute_prox_scores

    async def fake_fetch(db, range_days, **kwargs):
        players = {}
        for i, guid in enumerate(("G1", "G2", "G3", "G4")):
            players[guid] = {
                "name": guid, "engagements": 40, "tracks": 10,
                "escape_rate": 0.5, "spawn_score": 0.5,
                "revive_rate_as_victim": 0.5, "distance_per_life": 100.0,
                "denied_time": 1000.0,
                # spread so a real ranking cannot land everyone on 0.5
                "headshot_pct": 0.1 * (i + 1),
            }
        sources = [{"source": s, "success": True, "row_count": 4,
                    "error_code": None, "duration_ms": 5}
                   for s in SOURCE_LABELS]
        return players, sources

    monkeypatch.setattr(prox_scoring, "_fetch_raw_metrics", fake_fetch)
    result = await compute_prox_scores(object())
    seen = set()
    for p in result["players"]:
        desc = p["breakdown"]["prox_combat"]["__descriptive__"]
        seen.add(desc["headshot_pct"]["percentile"])
    assert len(seen) > 1, (
        f"every descriptive percentile came back identical ({seen}) — the "
        f"retired metrics are not being ranked, only neutral-filled"
    )
