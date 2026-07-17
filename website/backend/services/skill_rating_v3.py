"""ET Performance v3 — shadow rating (audit AUD-007).

Why v3 exists (the v2 bugs it fixes):
  1. The v2 `CONSTANT = 0.15` was documented as "centers the average player
     near 0.50", but the signed-weight sum makes the median profile ≈ 0.57.
  2. v2 mixes coverage epochs: it divides all-time proximity counts by
     PCS totals with no shared observation window, so players with more/less
     telemetry move for coverage reasons rather than play.

v3 fixes both WITHOUT retuning weights (isolate the correction):
  - shared telemetry epoch (EPOCH_START) for PCS and the date-scoped proximity
    counters (via compute_all_ratings(epoch_start=...));
  - directed midrank percentiles + absolute weights, no constant:
        score = Σ |w_i| · directed_midrank_percentile_i
    where directed flips "lower/penalty is better" metrics. Each metric column
    has mean exactly 0.5 and the absolute v2 weights sum to 1.0, so the
    population MEAN is mathematically 0.50 — provable, not asserted. (The v2
    bug was that its constant only *claimed* to centre the average; the MEDIAN
    is reported empirically and lands near, but is not forced to, 0.50.)

Status: SHADOW. Computed and exposed under an explicit v3 endpoint for
review; v2 stays the public rating. Promotion gates (≥20 eligible players,
split-half Spearman ≥ 0.70, |corr(score, coverage)| ≤ 0.15, leave-one-family
-out median rank shift ≤ 3) are owner-reviewed over ≥30 days / 8 sessions
before v3 becomes user-visible (remediation plan §6).
"""

from __future__ import annotations

import bisect
import logging
import statistics

from website.backend.services.skill_rating_service import (
    PROXIMITY_METRICS,
    WEIGHTS,
    compute_all_ratings,
)

logger = logging.getLogger(__name__)

FORMULA_VERSION = "et-perf-v3.0-shadow"

# Common telemetry epoch: kill-outcome + combat-position data is reliably
# present from this date (audit evidence). Both PCS and the date-scoped
# proximity counters observe this same window.
EPOCH_START = "2026-03-24"

# Eligibility: enough valid rounds in the epoch to rate at all.
MIN_ROUNDS_V3 = 20

# crossfire_rate is sourced from player_teamplay_stats, which has no
# session_date column. In the epoch path its all-time numerator is divided by
# an epoch-scoped kill denominator, which produces distorted (even >1) rates
# (Codex #513). Rather than mix epochs, v3 gives EVERY player the neutral
# directed percentile (0.5) for these metrics: the weight stays in the sum (so
# the composite mean stays centered) but the unreliable signal never affects
# ranking. They are flagged epoch_scoped=False in the component breakdown.
UNSCOPED_METRICS = frozenset({"crossfire_rate"})

# Neutral raw value each proximity metric collapses to when there is NO
# telemetry: compute_all_ratings COALESCEs kill_quality to 1.0 and every other
# proximity rate to 0.0. A raw sitting exactly on its neutral is treated as
# "missing" (not observed) so absent telemetry can't shape the percentile
# columns (Codex #513); this is the pre-capabilities-backfill proxy.
_PROXIMITY_NEUTRAL = {m: (1.0 if m == "kill_quality" else 0.0) for m in PROXIMITY_METRICS}

# Metrics where a higher raw value is WORSE. v2 encodes dpr as a negative
# weight; v3 makes the direction explicit and takes |weight|.
_PENALTY_METRICS = frozenset({m for m, w in WEIGHTS.items() if w < 0})

_ABS_WEIGHT_SUM = sum(abs(w) for w in WEIGHTS.values())


def directed_midrank_percentiles(values: list[float]) -> list[float]:
    """Fractional midrank percentile in [0,1] preserving input order.

    (n_less + (n_equal-1)/2) / (n-1): unique top → 1.0, unique bottom → 0.0,
    all-equal → 0.5, lone value → 0.5. The per-metric median is 0.5, which is
    what makes the composite median exactly 0.5.
    """
    if not values:
        return []
    n = len(values)
    if n == 1:
        return [0.5]
    sorted_vals = sorted(values)
    out = []
    for v in values:
        n_less = bisect.bisect_left(sorted_vals, v)
        n_equal = bisect.bisect_right(sorted_vals, v) - n_less
        out.append((n_less + (n_equal - 1) / 2) / (n - 1))
    return out


def score_population(players: list[dict]) -> list[dict]:
    """Re-score a v2 population with the v3 directed-midrank formula.

    `players` is the output of compute_all_ratings(): each has
    `components[metric]["raw"]`. Percentiles are recomputed here across the
    supplied cohort (the cohort IS the population). Each metric column has mean
    exactly 0.5 and the absolute weights sum to 1.0, so the composite MEAN is
    exactly 0.50 (the AUD-007 centering the v2 constant only claimed). The
    median lands near 0.50 but is not forced there — it is reported empirically.

    Missing telemetry is handled honestly: a proximity metric sitting on its
    neutral default is excluded from that metric's percentile column and given
    the neutral 0.5 directed percentile, and the epoch-unscoped metrics
    (crossfire) are neutralized for everyone (Codex #513). Because the excluded
    players still receive 0.5, the column mean stays 0.5 and the centering holds.
    """
    if not players:
        return []

    metrics = list(WEIGHTS.keys())

    directed: dict[str, list[float]] = {}
    for m in metrics:
        raws = [p["components"].get(m, {}).get("raw") for p in players]

        if m in UNSCOPED_METRICS:
            # Unreliable in the epoch path → uniform neutral (no ranking effect).
            directed[m] = [0.5] * len(players)
            continue

        if m in PROXIMITY_METRICS:
            neutral = _PROXIMITY_NEUTRAL[m]
            # Only players with REAL telemetry (raw present and off its neutral)
            # rank against each other; the rest get the neutral 0.5.
            real_idx = [
                i for i, v in enumerate(raws)
                if v is not None and float(v) != neutral
            ]
            real_vals = [float(raws[i]) for i in real_idx]
            real_pctls = directed_midrank_percentiles(real_vals)
            pctls = [0.5] * len(players)
            for j, i in enumerate(real_idx):
                pctls[i] = real_pctls[j]
        else:
            # PCS metrics are always observed.
            pctls = directed_midrank_percentiles([float(v or 0.0) for v in raws])

        if m in _PENALTY_METRICS:
            pctls = [1.0 - p for p in pctls]
        directed[m] = pctls

    scored = []
    for i, p in enumerate(players):
        components = {}
        score = 0.0
        for m in metrics:
            w = abs(WEIGHTS[m])
            dp = directed[m][i]
            contribution = w * dp
            score += contribution
            components[m] = {
                "raw": p["components"].get(m, {}).get("raw"),
                "directed_percentile": round(dp, 4),
                "abs_weight": round(w, 4),
                "contribution": round(contribution, 4),
                "epoch_scoped": m not in UNSCOPED_METRICS,
            }
        scored.append({
            "player_guid": p["player_guid"],
            "display_name": p["display_name"],
            "rounds": p["rounds"],
            "et_performance_v3": round(score, 4),
            "components": components,
        })
    scored.sort(key=lambda x: x["et_performance_v3"], reverse=True)
    return scored


def _population_coverage(players: list[dict]) -> float:
    """Fraction of players that have any real proximity signal (telemetry).

    A player whose every proximity metric sits at its neutral default has no
    telemetry coverage. This is the population-level proxy until
    proximity_processed_files.capabilities (migration 062) is backfilled to
    give a precise per-round coverage.
    """
    if not players:
        return 0.0
    covered = 0
    for p in players:
        comps = p["components"]
        # A metric counts as real telemetry when its raw is present and OFF its
        # own neutral default. The previous `not in (0.0, 1.0)` test wrongly
        # treated a legitimate crossfire/trade rate of exactly 1.0 as "no
        # telemetry" — only kill_quality is neutral at 1.0 (Copilot #513).
        has_prox = any(
            (raw := comps.get(m, {}).get("raw")) is not None
            and float(raw) != _PROXIMITY_NEUTRAL[m]
            for m in PROXIMITY_METRICS
        )
        if has_prox:
            covered += 1
    return covered / len(players)


async def compute_et_performance_v3(db) -> dict:
    """Compute the ET Performance v3 shadow rating with metadata.

    Returns:
        {
          "formula_version", "epoch_start", "min_rounds",
          "eligible_count", "scored_count", "unrated_reasons",
          "mean_rating", "median_rating", "coverage", "unscoped_metrics",
          "players": [ ... ]   # eligible players, ranked
        }
    """
    population = await compute_all_ratings(db, epoch_start=EPOCH_START, min_rounds=1)

    # Score ONLY the eligible cohort: players below MIN_ROUNDS_V3 must not shape
    # the percentile columns of the players we publish (Codex #513). Below-
    # threshold players are counted separately.
    eligible_pop = [p for p in population if p["rounds"] >= MIN_ROUNDS_V3]
    scored = score_population(eligible_pop)
    unrated = {
        "below_min_rounds": len(population) - len(eligible_pop),
    }

    ratings = sorted(p["et_performance_v3"] for p in scored)
    # Mean is the mathematically-centered statistic (0.50 by construction);
    # median is reported empirically, computed correctly for even cohorts
    # (average of the two middle values, not the upper-middle — Codex/Copilot).
    mean_rating = sum(ratings) / len(ratings) if ratings else None
    median = statistics.median(ratings) if ratings else None

    return {
        "formula_version": FORMULA_VERSION,
        "epoch_start": EPOCH_START,
        "min_rounds": MIN_ROUNDS_V3,
        "eligible_count": len(scored),
        "scored_count": len(scored),
        "unrated_reasons": unrated,
        "mean_rating": round(mean_rating, 4) if mean_rating is not None else None,
        "median_rating": round(median, 4) if median is not None else None,
        "coverage": round(_population_coverage(scored), 3),
        "unscoped_metrics": sorted(UNSCOPED_METRICS),
        "abs_weight_sum": round(_ABS_WEIGHT_SUM, 4),
        "players": scored,
    }
