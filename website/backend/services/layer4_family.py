"""Layer 4 — the §8 validation protocol as code (spec §7, §8, §12 B4/B5).

Nothing in layer 4 ships on plausibility. A candidate signal is a hypothesis
until it has been measured WITHIN rounds (§8.1), on whole match blocks
(§8.2), with discovery and confirmation separated chronologically (§8.3)
and the family-wise error controlled over every candidate that was tried
(§8.4). This module is the reference implementation of §8.6, kept pure so
the rules can be pinned by tests and the numbers reproduced from a saved
dataset without the database.

Vocabulary
- row: one (player, round) with its metrics and the round's outcome for
  that player's team (1 = won, 0 = lost).
- block: the independent unit — a `gaming_session_id` (teammates share an
  outcome, R1/R2 share teams; resampling players or rounds would treat
  dependent things as independent).
- spread: within one round, split its players at the median of a metric;
  win rate of the upper half minus the lower half. The effect of a metric
  is the mean spread over rounds. A metric that only tracks round length,
  map or opponent quality has no spread, because everyone in the round
  shares those.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from dataclasses import dataclass, field
from typing import Any, Iterable

#: Fewer players than this in a round and a median split says nothing.
MIN_PLAYERS_PER_ROUND = 4
#: A verdict needs a tail to estimate: fewer confirmation blocks than this,
#: or fewer rounds than MIN_ROUNDS_PER_SPLIT in either split, is "unmeasured".
#: Seen on the first partial run (4 confirmation blocks): a bootstrap over
#: four blocks is a handful of discrete outcomes, not a distribution.
MIN_CONFIRMATION_BLOCKS = 10
MIN_ROUNDS_PER_SPLIT = 30


@dataclass(frozen=True, slots=True)
class Candidate:
    """One member of the frozen family (§8.3): id, formula in words, the
    parameters that produced it, and the direction it is EXPECTED to run —
    written down before confirmation data is opened."""
    id: str
    formula: str
    expected_direction: str  # "positive" | "negative"
    parameters: dict[str, Any] = field(default_factory=dict)
    kind: str = "candidate"  # "candidate" | "positive_control" | "negative_control" | "oracle_diagnostic"
    #: What the arithmetic cannot see — a confound the reader must weigh
    #: before believing a "passes" (§7.4.1: side and stage share the outcome).
    caveat: str | None = None


@dataclass(slots=True)
class Row:
    block: int
    round_id: int
    player: str
    won: int
    metrics: dict[str, float | None]
    order_key: str = ""  # chronological key of the block (first round time)


def round_spread(rows: list[Row], metric: str) -> float | None:
    """Median split of one round's players on `metric`; win rate of the upper
    half minus the lower half. Players AT the median are left out of both
    halves (a tie is not a side), and a round with fewer than
    MIN_PLAYERS_PER_ROUND measured players, or an empty half, answers None."""
    measured = [(r.metrics.get(metric), r.won) for r in rows if r.metrics.get(metric) is not None]
    if len(measured) < MIN_PLAYERS_PER_ROUND:
        return None
    values = sorted(v for v, _ in measured)
    n = len(values)
    median = values[n // 2] if n % 2 else (values[n // 2 - 1] + values[n // 2]) / 2
    upper = [w for v, w in measured if v > median]
    lower = [w for v, w in measured if v < median]
    if not upper or not lower:
        return None
    return sum(upper) / len(upper) - sum(lower) / len(lower)


def spreads_by_round(rows: Iterable[Row], metric: str) -> dict[int, float]:
    by_round: dict[int, list[Row]] = {}
    for r in rows:
        by_round.setdefault(r.round_id, []).append(r)
    out: dict[int, float] = {}
    for rid, rs in by_round.items():
        s = round_spread(rs, metric)
        if s is not None:
            out[rid] = s
    return out


def split_blocks(rows: list[Row], discovery_share: float = 0.7) -> tuple[set[int], set[int], str | None]:
    """Chronological split of WHOLE blocks: the earliest `discovery_share`
    for discovery, the rest untouched for confirmation. Returns the two block
    sets and the order key of the first confirmation block (the published
    cut-off)."""
    keys: dict[int, str] = {}
    for r in rows:
        keys[r.block] = min(keys.get(r.block, r.order_key), r.order_key)
    ordered = sorted(keys, key=lambda b: (keys[b], b))
    n_disc = int(math.floor(len(ordered) * discovery_share))
    discovery = set(ordered[:n_disc])
    confirmation = set(ordered[n_disc:])
    cutoff = keys[ordered[n_disc]] if n_disc < len(ordered) else None
    return discovery, confirmation, cutoff


def _block_means(rows: list[Row], metric: str) -> dict[int, tuple[float, int]]:
    """Per block: (sum of round spreads, number of rounds with a spread)."""
    by_round = spreads_by_round(rows, metric)
    block_of = {r.round_id: r.block for r in rows}
    acc: dict[int, list[float]] = {}
    for rid, s in by_round.items():
        acc.setdefault(block_of[rid], []).append(s)
    return {b: (sum(v), len(v)) for b, v in acc.items()}


def effect(rows: list[Row], metric: str) -> tuple[float | None, int]:
    """Mean round spread and the number of rounds it rests on."""
    by_round = spreads_by_round(rows, metric)
    if not by_round:
        return None, 0
    return sum(by_round.values()) / len(by_round), len(by_round)


def block_bootstrap(rows: list[Row], metrics: list[str], *, resamples: int, seed: int) -> dict[str, Any]:
    """§8.2 + §8.4: resample WHOLE blocks with replacement, recompute every
    metric's mean spread on each draw, and control the family-wise error
    with a max-T bootstrap: each draw's largest studentised deviation over
    the family sets the width of every simultaneous interval.

    Returns per metric: point, rounds, se, ci95 (percentile, individual),
    sim95 (simultaneous, max-T). Deterministic for a seed."""
    per_metric = {m: _block_means(rows, m) for m in metrics}
    blocks = sorted({b for bm in per_metric.values() for b in bm})
    if not blocks:
        return {m: {"point": None, "rounds": 0, "se": None, "ci95": None, "sim95": None} for m in metrics}
    rng = random.Random(seed)  # noqa: S311 — a bootstrap draw, not a secret
    point: dict[str, float | None] = {}
    rounds: dict[str, int] = {}
    for m in metrics:
        bm = per_metric[m]
        tot = sum(s for s, _ in bm.values())
        n = sum(c for _, c in bm.values())
        point[m] = tot / n if n else None
        rounds[m] = n
    draws: dict[str, list[float]] = {m: [] for m in metrics}
    for _ in range(resamples):
        # ONE draw of blocks for the whole family (a shared draw is what makes
        # the max-T comparable across candidates).
        sample = [blocks[rng.randrange(len(blocks))] for _ in blocks]
        for m in metrics:
            bm = per_metric[m]
            tot = sum(bm[b][0] for b in sample if b in bm)
            n = sum(bm[b][1] for b in sample if b in bm)
            if n:
                draws[m].append(tot / n)
    out: dict[str, Any] = {}
    se: dict[str, float | None] = {}
    for m in metrics:
        d = draws[m]
        if len(d) < 2 or point[m] is None:
            se[m] = None
            continue
        mean = sum(d) / len(d)
        se[m] = math.sqrt(sum((x - mean) ** 2 for x in d) / (len(d) - 1))
    # max-T: for each draw, the largest |draw - point| / se over the family.
    usable = [m for m in metrics if se.get(m) not in (None, 0.0) and point[m] is not None]
    n_draws = min((len(draws[m]) for m in usable), default=0)
    max_t: list[float] = [
        max(abs(draws[m][i] - point[m]) / se[m] for m in usable)  # type: ignore[operator]
        for i in range(n_draws)
    ]
    t_crit = _percentile(max_t, 0.95) if max_t else None
    for m in metrics:
        d = sorted(draws[m])
        ci = (_percentile(d, 0.025), _percentile(d, 0.975)) if len(d) >= 2 else None
        sim = None
        if t_crit is not None and se.get(m) not in (None, 0.0) and point[m] is not None:
            sim = (point[m] - t_crit * se[m], point[m] + t_crit * se[m])  # type: ignore[operator]
            # ⛔ Simultaneous means "at least as wide as the individual
            # interval": the studentised band is symmetric and, over a few
            # skewed blocks, came out NARROWER than the percentile interval
            # (first partial run: dpm [−0.14, +0.19] individual, [+0.03, +0.13]
            # simultaneous). The family-wise interval takes the union.
            if ci is not None:
                sim = (min(sim[0], ci[0]), max(sim[1], ci[1]))
        out[m] = {"point": point[m], "rounds": rounds[m], "se": se.get(m), "ci95": ci, "sim95": sim, "t_crit": t_crit,
                  "blocks": len(per_metric[m])}
    return out


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * q
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


def direction_of(x: float | None) -> str | None:
    if x is None:
        return None
    return "positive" if x > 0 else "negative" if x < 0 else "zero"


def verdict(candidate: Candidate, discovery: dict[str, Any], confirmation: dict[str, Any]) -> str:
    """§8.4: ships only when the effect has the frozen direction in BOTH
    splits and the simultaneous 95 % interval on confirmation excludes zero.
    Anything else is named, not ranked: a point estimate or a lone
    individual interval is insufficient."""
    d_pt = discovery.get("point")
    c_pt = confirmation.get("point")
    sim = confirmation.get("sim95")
    if d_pt is None or c_pt is None or sim is None:
        return "unmeasured"
    if confirmation.get("blocks", 0) < MIN_CONFIRMATION_BLOCKS:
        return f"unmeasured: {confirmation.get('blocks', 0)} confirmation blocks, {MIN_CONFIRMATION_BLOCKS} needed"
    if discovery.get("rounds", 0) < MIN_ROUNDS_PER_SPLIT or confirmation.get("rounds", 0) < MIN_ROUNDS_PER_SPLIT:
        return f"unmeasured: {discovery.get('rounds', 0)}/{confirmation.get('rounds', 0)} rounds, {MIN_ROUNDS_PER_SPLIT} needed in each split"
    if direction_of(d_pt) != candidate.expected_direction:
        return "fails: discovery direction"
    if direction_of(c_pt) != candidate.expected_direction:
        return "fails: confirmation direction"
    lo, hi = sim
    if lo <= 0 <= hi:
        return "fails: simultaneous interval includes zero"
    # The arithmetic passed. What that MEANS depends on what was measured:
    # a control passing is the harness working, an oracle passing is a
    # diagnostic (§6.4 / P6: it consumed positions or a clock nobody had),
    # and only a plain candidate is a signal — and even that ships to a page
    # only once its caveat is answered.
    if candidate.kind == "positive_control":
        return "control passes (the harness sees a known signal)"
    if candidate.kind == "negative_control":
        return "CONTROL PASSES — the harness is broken"
    if candidate.kind == "oracle_diagnostic":
        return "passes the arithmetic; oracle diagnostic, does not ship (§6.4, P6)"
    return "passes §8.4" + (f"; NOT shipped: {candidate.caveat}" if candidate.caveat else "; ships")


def manifest(candidates: list[Candidate], *, cutoff: str | None, outcome: str, filters: list[str], seed: int, resamples: int, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    """The frozen family (§8.3): every candidate and parameter variant, the
    split cut-off, the outcome definition, the filters, the seed. Its hash
    is what a reader checks against the published table."""
    body = {
        "protocol": "docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md §8",
        "candidates": [{"id": c.id, "kind": c.kind, "formula": c.formula, "expected_direction": c.expected_direction, "parameters": c.parameters, "caveat": c.caveat} for c in candidates],
        "split": {"rule": "earliest 70 % of gaming_session_id blocks by first round time = discovery; the rest = confirmation", "confirmation_starts_at": cutoff},
        "outcome": outcome,
        "filters": filters,
        "inference": {"unit": "gaming_session_id block", "resamples": resamples, "seed": seed, "family_wise": "max-T bootstrap, simultaneous 95 % intervals"},
        **(extra or {}),
    }
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {**body, "sha256": digest}


def analyse(rows: list[Row], candidates: list[Candidate], *, resamples: int, seed: int) -> dict[str, Any]:
    """Discovery and confirmation, one shared block draw per split, a
    verdict per candidate, and the manifest hash."""
    disc_blocks, conf_blocks, cutoff = split_blocks(rows)
    disc = [r for r in rows if r.block in disc_blocks]
    conf = [r for r in rows if r.block in conf_blocks]
    ids = [c.id for c in candidates]
    d = block_bootstrap(disc, ids, resamples=resamples, seed=seed)
    c = block_bootstrap(conf, ids, resamples=resamples, seed=seed + 1)
    table = [
        {
            "id": cand.id, "kind": cand.kind, "expected": cand.expected_direction,
            "discovery": d[cand.id], "confirmation": c[cand.id],
            "verdict": verdict(cand, d[cand.id], c[cand.id]),
        }
        for cand in candidates
    ]
    return {
        "cutoff": cutoff,
        "blocks": {"discovery": len(disc_blocks), "confirmation": len(conf_blocks)},
        "rows": {"discovery": len(disc), "confirmation": len(conf)},
        "table": table,
    }
