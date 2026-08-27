#!/usr/bin/env python3
"""§8 validation protocol, executable.

READ-ONLY. No formula, cache row or table is touched.

WHY THIS EXISTS. `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` §8 is the protocol
that retired 13 of 18 `prox_score` metrics in #556 — two of which ranked players
BACKWARDS. It is written in full and nothing executes it. Until something does,
no new metric (Layer 3, Layer 4, or any future idea) can honestly pass or fail:
the closest existing tool, `scripts/backtest_metric_foundations.py`, groups by
ROUND, while §8.2 requires grouping by MATCH BLOCK, and it has no frozen family,
no chronological split and no family-wise correction.

WHAT §8 DEMANDS, and where each demand lives here:

  §8.1  measure WITHIN round, never between      -> within_round_spread()
  §8.2  bootstrap over match blocks              -> block_bootstrap()
  §8.3  discovery/confirmation, frozen family    -> chronological_split(), Family
  §8.4  family-wise error over blocks            -> max_t_intervals(), holm()
  §8.5  publish EVERY candidate, not the winners -> report()
  §8.6  reference implementation (#556)          -> within_round_spread()

THE ACCEPTANCE TEST. A measuring instrument proves itself on a known result
before it judges an unknown one. Two candidates in the default family must FAIL:

  `kpr`   kills per round. In #556 it showed a spread of +0.028 and would have
          passed a naive threshold; its interval was [-0.009, +0.064].
  `null`  a deterministic pseudo-random number. It has no signal by
          construction. If it ever ships, the harness is broken, not lucky.

⛔ WHAT THIS HARNESS RETIRED, INCLUDING ONE OF ITS OWN CLAIMS.

`--outcome seconds` was added on the theory that win/loss is one bit per round
while a stopwatch match is decided by a margin in seconds, and it appeared to
clear the family floor by 2.4-8.7 SD where win/loss cleared by 0.18. That
conclusion is WITHDRAWN. The quantity it used, `r1.actual_duration_seconds -
r2.actual_duration_seconds`, agrees with who actually won the round 48.5% of the
time — chance. A real stopwatch margin is not a correlate of the result, it IS
the result, so agreement should be near total. `actual_duration_seconds` is wall
clock, and an R1 fullhold runs to the timelimit rather than to an objective, so
the difference is not "how much faster the second attack was".

The outcome is kept, gated, and refuses to run below MARGIN_AGREEMENT_FLOOR, so
the next person meets the measurement instead of the idea. `time_to_beat_seconds`
is the real quantity and is populated on 33 of 2,007 eligible rounds; making it
available is capture-side work, not analysis work.

Usage:
    PGPASSWORD=... venv/bin/python3 scripts/validation_family.py
    PGPASSWORD=... venv/bin/python3 scripts/validation_family.py --spatial
    (--spatial restricts to rounds carrying position tracks: the Layer 4 universe)
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import random
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable

import asyncpg

# --- §8.3/§8.4 knobs. Changing any of these changes the manifest hash. -------
DISCOVERY_FRACTION = 0.70
RESAMPLES = 2000          # §8.4: "1,000 is exploratory, not a final result"
SEED = 20260826
ALPHA = 0.05
MIN_PLAYERS_PER_ROUND = 4   # a median split needs two sides to compare
POWER_TARGET = 0.80

_Z_ALPHA = 1.959963985      # two-sided 95%
_Z_POWER = 0.841621234      # one-sided 80%


# --- the data -----------------------------------------------------------------
# round_number IN (1,2): R0 rows are the importer's summary copy and are NOT a
# data source (contract in docs/CLAUDE.md). Bot rounds and unresolved winners
# cannot answer "did this side win", so they are excluded rather than assumed.
ROWS_SQL = """
WITH candidate_pairs AS (
  -- The R1/R2 window is many-to-many: the same map replayed inside a session
  -- gives one R1 several candidate R2s, and an abandoned R1 followed by a real
  -- one leaves two R1s pointing at the same R2.
  SELECT r1.id AS r1id, r2.id AS r2id,
         (r1.actual_duration_seconds - r2.actual_duration_seconds)::float AS margin,
         r2.created_at - r1.created_at AS gap
  FROM rounds r1
  JOIN rounds r2
    ON r2.gaming_session_id = r1.gaming_session_id
   AND r2.map_name = r1.map_name
   AND r1.round_number = 1 AND r2.round_number = 2
   AND r2.created_at > r1.created_at
   AND r2.created_at < r1.created_at + interval '45 minutes'
  WHERE r1.is_valid AND r2.is_valid
    AND r1.actual_duration_seconds IS NOT NULL
    AND r2.actual_duration_seconds IS NOT NULL
), r1_choice AS (
  SELECT DISTINCT ON (r1id) r1id, r2id, margin FROM candidate_pairs
  ORDER BY r1id, gap, r2id
), r2_choice AS (
  SELECT DISTINCT ON (r2id) r2id, r1id FROM candidate_pairs
  ORDER BY r2id, gap, r1id
), matched AS (
  -- MUTUAL choice only. Picking the nearest partner per round independently is
  -- not a matching: an abandoned R1 keeps a margin to an R2 that chose the
  -- other R1, fabricating an outcome for a round that never had one.
  SELECT a.r1id, a.r2id, a.margin
  FROM r1_choice a JOIN r2_choice b ON b.r2id = a.r2id AND b.r1id = a.r1id
), pair_margin AS (
  SELECT r1id AS rid, margin, 1 AS half FROM matched
  UNION ALL
  SELECT r2id AS rid, margin, 2 AS half FROM matched
)
SELECT pcs.round_id                      AS rid,
       r.gaming_session_id               AS block,
       r.created_at                      AS at,
       pcs.player_guid                   AS guid,
       pcs.team                          AS team,
       r.winner_team                     AS winner,
       r.defender_team                   AS defender,
       pcs.kills                         AS kills,
       pcs.deaths                        AS deaths,
       pcs.damage_given                  AS dg,
       pcs.damage_received               AS dr,
       pcs.time_played_seconds           AS secs,
       pm.margin                         AS margin,
       pm.half                           AS half
FROM player_comprehensive_stats pcs
JOIN rounds r ON r.id = pcs.round_id
LEFT JOIN pair_margin pm ON pm.rid = r.id
WHERE r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
  AND r.winner_team IN (1, 2)
  AND r.gaming_session_id IS NOT NULL
  AND pcs.round_number IN (1, 2)
  AND pcs.team IN (1, 2)
  AND pcs.time_played_seconds > 0
  AND pcs.player_guid NOT LIKE 'OMNIBOT%'
  -- $1 restricts to rounds carrying position tracks (the Layer 4 universe).
  -- A bound parameter rather than string concatenation: the query text is one
  -- constant, which is both what the SQL-injection scanners want to see and
  -- what stops a future filter from being pasted in by hand.
  AND (NOT $1::boolean
       OR EXISTS (SELECT 1 FROM player_track t WHERE t.round_id = r.id))
"""


@dataclass(frozen=True)
class Candidate:
    """One frozen hypothesis. Everything here goes into the manifest hash."""
    cid: str
    description: str
    direction: str                 # "higher_is_better" | "lower_is_better"
    fn: Callable[[dict], float | None] = field(compare=False, repr=False)

    def formula_fingerprint(self) -> str:
        """Hash of the EXECUTABLE formula, not its prose.

        §8.3 freezes the exact formula, and hashing only id/description/direction
        would let a lambda, a normalisation constant or a missing-value rule
        change while the manifest still claims the same frozen family. The
        source text of the callable is the closest honest stand-in; when it
        cannot be read (a C-level or dynamically built callable), the code
        object's constants and names are used instead, and the entry says which
        so nobody reads a weaker fingerprint as a strong one.
        """
        try:
            import inspect
            src = inspect.getsource(self.fn).strip()
            kind = "source"
            # A lambda's text names its helpers but does not contain them:
            # `dpm` reads `_minutes(p)`, so changing that helper's `/ 60.0` or
            # its missing-time rule would change the experiment while leaving
            # the manifest hash alone. Pull in the source of every module-level
            # helper the formula actually calls, sorted for stability.
            module = sys.modules.get(self.fn.__module__)
            code = getattr(self.fn, "__code__", None)
            for name in sorted(set(code.co_names if code else ())):
                helper = getattr(module, name, None)
                if callable(helper) and getattr(helper, "__module__", None) == \
                        self.fn.__module__:
                    try:
                        src += "\n" + inspect.getsource(helper).strip()
                    except (OSError, TypeError):
                        src += f"\n<unreadable helper {name}>"
                        kind = "source+partial-helpers"
        except (OSError, TypeError):
            code = getattr(self.fn, "__code__", None)
            src = (repr((code.co_names, code.co_consts, code.co_argcount))
                   if code else repr(self.fn))
            kind = "bytecode-shape"
        return f"{kind}:{hashlib.sha256(src.encode()).hexdigest()[:16]}"

    def manifest_entry(self) -> dict:
        return {"id": self.cid, "description": self.description,
                "direction": self.direction,
                "formula": self.formula_fingerprint()}


@dataclass
class Family:
    """§8.3: every candidate and variant tried, including abandoned ones."""
    name: str
    candidates: list[Candidate]
    filters: str
    outcome: str = "win"          # §8.3: the outcome definition is frozen too
    frozen_cutoff: str | None = None   # absolute; set once, never recomputed
    split_fraction: float = DISCOVERY_FRACTION
    resamples: int = RESAMPLES
    seed: int = SEED
    alpha: float = ALPHA

    def frozen(self) -> dict:
        return {
            "family": self.name,
            "candidates": [c.manifest_entry() for c in self.candidates],
            "filters": self.filters,
            "outcome": self.outcome,
            "frozen_cutoff": self.frozen_cutoff,
            "split_fraction": self.split_fraction,
            "resamples": self.resamples,
            "seed": self.seed,
            "alpha": self.alpha,
            "protocol": "SPIDER_WEB_SPEC_2026-07 §8",
        }

    def manifest_hash(self) -> str:
        blob = json.dumps(self.frozen(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()


# --- §8.1 + §8.6: the measurement --------------------------------------------
def outcome_win(p: dict) -> float | None:
    """§8.6 reference outcome: did this player's side win the round."""
    return 1.0 if p["team"] == p["winner"] else 0.0


def outcome_seconds(p: dict) -> float | None:
    """Signed stopwatch margin in seconds for this player's side.

    ⛔ THE SIDE SWAPS BETWEEN THE HALVES. `player_comprehensive_stats.team` is
    the side a player occupied in THAT round, and stopwatch teams change ends
    between R1 and R2 — measured here: 1,130 of 1,383 paired player rows sit on
    a different `team` in R2 than in R1. Deriving the sign from R1's defender
    for both halves therefore labels the real R2 attackers negative and their
    opponents positive, so the two halves of one match carry contradictory
    labels. The sign is taken per round instead: within any round the attacker
    is the side that is not `rounds.defender_team`, and the margin favours the
    R2 attacker.

    None when the pair could not be resolved — the round is dropped, not scored
    as a zero margin. A missing measurement and a dead heat have the same shape
    here and must not be confused.
    """
    if p.get("margin") is None or p.get("half") is None:
        return None
    if p.get("defender") not in (1, 2):
        return None
    attacks_this_round = p["team"] != p["defender"]
    # margin > 0 means the R2 attack was faster, which is a win for whoever
    # attacks in R2. In R1 the same persistent team is the one DEFENDING.
    favours_r2_attacker = float(p["margin"])
    if p["half"] == 2:
        return favours_r2_attacker if attacks_this_round else -favours_r2_attacker
    return -favours_r2_attacker if attacks_this_round else favours_r2_attacker


def margin_agreement(rows_by_round: dict) -> tuple[int, int]:
    """How often the margin's sign agrees with who actually won the round.

    A real stopwatch margin is not a correlate of the result — it IS the result,
    so agreement should be near total. Anything else means the quantity is not
    what its name says, and every verdict computed from it is measuring
    something nobody has identified.
    """
    agree = total = 0
    for players in rows_by_round.values():
        for p in players:
            v = outcome_seconds(p)
            if v is None or v == 0:
                continue
            total += 1
            won = p["team"] == p["winner"]
            if (v > 0) == won:
                agree += 1
    return agree, total


OUTCOMES = {"win": outcome_win, "seconds": outcome_seconds}


def within_round_spread(rows_by_round: dict, metric: Callable,
                        outcome: Callable = outcome_win) -> float | None:
    """§8.6 reference implementation, kept within round (§8.1).

    Per round: rank that round's players by the metric, split at the median,
    and take (win rate of the upper half) - (win rate of the lower half).
    Average over rounds. A metric that identifies winners scores positive.

    Comparing only inside a round is the whole point: between rounds, anything
    that accumulates with round length looks strong for that reason alone. That
    is exactly how `distance_per_life` and `denied_time` fooled the #556 pass.
    """
    diffs = []
    for players in rows_by_round.values():
        vals = [(metric(p), p) for p in players]
        vals = [(v, p) for v, p in vals if v is not None]
        if len(vals) < MIN_PLAYERS_PER_ROUND:
            continue
        # a player whose outcome is unmeasurable takes the whole round with it:
        # a half-measured round would compare two different populations
        outs = [outcome(p) for _, p in vals]
        if any(o is None for o in outs):
            continue
        vals.sort(key=lambda vp: vp[0])
        half = len(vals) // 2
        lo, hi = vals[:half], vals[-half:]
        # ⛔ TIES MUST NOT BE SPLIT. Kills and deaths are small integers, so the
        # value at the median is routinely shared. Slicing a sorted list puts
        # equal-valued players on opposite sides according to the order the
        # database happened to return them — and rows arrive grouped by round
        # and guid, which correlates with team. A CONSTANT metric could then
        # score +1 or -1 instead of carrying no signal at all. Players holding
        # the boundary value are dropped from both halves; if that empties
        # either half, the round has no median to split on and is skipped.
        boundary_lo, boundary_hi = lo[-1][0], hi[0][0]
        if boundary_lo == boundary_hi:
            tied = boundary_lo
            lo = [vp for vp in lo if vp[0] != tied]
            hi = [vp for vp in hi if vp[0] != tied]
        if not lo or not hi:
            continue
        lo_mean = sum(outcome(p) for _, p in lo) / len(lo)
        hi_mean = sum(outcome(p) for _, p in hi) / len(hi)
        diffs.append(hi_mean - lo_mean)
    if len(diffs) < 2:
        return None
    return statistics.mean(diffs)


def within_round_point_biserial(rows_by_round: dict, metric: Callable,
                                outcome: Callable = outcome_win) -> float | None:
    """Same question as §8.6, without throwing the magnitudes away.

    §8.6's median split reduces each player to above/below and each round to a
    difference of two proportions. That is a deliberately blunt instrument, and
    bluntness costs power: the floor a sample can reach is a property of the
    ESTIMATOR as much as of the sample size. This is the continuous form —
    standardise the metric within the round (§8.1 still holds: the comparison
    never leaves the round) and correlate it with who won.

    Reported as a within-round point-biserial correlation, so it is NOT on the
    win-rate-difference scale of within_round_spread(). Compare the two by their
    t = effect / bootstrap SD, never by their raw size.

    ⚠️ MEASURED 2026-08-26, AND THE HYPOTHESIS LOST. The idea above — that the
    median split wastes power and a continuous estimator would lower the floor —
    is wrong on this data. Ratio of t (continuous / median split), 600 block
    resamples on the confirmation half:

        all rounds       kpr 0.94x   kd_ratio 0.57x   dpm 0.67x   dmg_ratio 0.65x
        rounds w/tracks  kpr 1.75x   kd_ratio 0.77x   dpm 0.70x   dmg_ratio 1.02x

    Rounds hold 4-12 players, so the per-round standard deviations this estimator
    divides by are themselves noisy; that noise costs more than the magnitudes
    buy back. The median split is the more robust statistic at this roster size.

    Kept — not deleted — so the next person reads a measurement instead of
    re-running the idea. It is not the lever; the denominator is.
    """
    rs = []
    for players in rows_by_round.values():
        pairs = [(metric(p), outcome(p)) for p in players]
        pairs = [(v, w) for v, w in pairs if v is not None and w is not None]
        if len(pairs) < MIN_PLAYERS_PER_ROUND:
            continue
        vs = [v for v, _ in pairs]
        ws = [w for _, w in pairs]
        # a round where everyone shares an outcome carries no within-round
        # information about winning — it is skipped, not scored as zero
        if len(set(ws)) < 2:
            continue
        mv, mw = statistics.mean(vs), statistics.mean(ws)
        sv = statistics.pstdev(vs)
        sw = statistics.pstdev(ws)
        if sv == 0 or sw == 0:
            continue
        cov = sum((v - mv) * (w - mw) for v, w in pairs) / len(pairs)
        rs.append(cov / (sv * sw))
    if len(rs) < 2:
        return None
    return statistics.mean(rs)


ESTIMATORS = {
    "median_split": within_round_spread,          # §8.6 reference
    "point_biserial": within_round_point_biserial,
}


# --- §8.2: the resampling unit is the match block -----------------------------
class _Rng:
    """Deterministic draws. Reproducibility is the requirement, not secrecy.

    This was a hand-rolled LCG (`s = 1103515245*s + 12345 mod 2^31`, then `% n`)
    until the `null`/`kpr` controls caught what it did: with 16 confirmation
    blocks the low four bits of that generator have period 16, so every single
    bootstrap resample drew the SAME permutation of all 16 blocks. Variance
    collapsed to zero, every interval came back [nan, nan], and every candidate
    — including the two that exist to fail — "shipped".

    Mersenne Twister has no such low-bit structure, is reproducible from a
    published seed, and is what `backtest_metric_foundations.py` already uses.
    """

    def __init__(self, seed: int):
        # Statistical resampling, not cryptography: a PUBLISHED seed must
        # reproduce the published table, which is the opposite of what a
        # cryptographic generator provides. Suppressions must sit on the
        # flagged line itself — a comment block above it is not read.
        self._r = random.Random(seed)  # noqa: S311  # nosec B311

    def next_below(self, n: int) -> int:
        return self._r.randrange(n)


def block_draws(blocks: dict, resamples: int, seed: int) -> list[list]:
    """The shared sequence of block draws for the WHOLE family (§8.4).

    Every candidate must be evaluated on the SAME resamples. max_t_intervals()
    treats element j of every candidate as one joint replicate, so if each
    candidate drew its own blocks, the covariance between correlated metrics
    would be destroyed and the maximum would not come from the joint family
    distribution — the interval would still be printed, and it would no longer
    be the family-wise interval it claims to be. Drawing once, here, is what
    makes the claim true.
    """
    keys = sorted(blocks)
    rng = _Rng(seed)
    return [[keys[rng.next_below(len(keys))] for _ in range(len(keys))]
            for _ in range(resamples)]


def block_bootstrap(blocks: dict, metric: Callable, draws: list[list],
                    estimator: Callable = None,
                    outcome: Callable = outcome_win) -> list[float]:
    """Evaluate one candidate on the shared draws (§8.2).

    Teammates share an outcome, and R1/R2 plus several maps in one session share
    teams and stopwatch state. Resampling players or rounds independently would
    treat those as independent evidence and shrink every interval by a factor
    nobody earned.

    Returns one value per draw, with None where a draw could not be measured —
    positions must line up across candidates for the joint maximum to mean
    anything.
    """
    out = []
    for draw in draws:
        merged: dict = {}
        for k in draw:
            for rid, players in blocks[k].items():
                # a round drawn twice counts twice: give it a fresh key
                merged[(k, rid, len(merged))] = players
        out.append((estimator or within_round_spread)(merged, metric, outcome))
    return out


# --- §8.3: chronological split, whole blocks ----------------------------------
def chronological_split(block_times: dict, fraction: float,
                        frozen_cutoff: str | None = None):
    """Earliest blocks discover; the latest stay untouched.

    Splitting on whole blocks is what keeps a gaming session from straddling the
    cutoff — a session on both sides would leak the confirmation half into
    discovery through shared teams and stopwatch state.

    ⛔ THE CUTOFF IS AN ABSOLUTE TIMESTAMP, NOT A PERCENTILE OF TODAY'S DATA.
    Deriving it from `fraction` on every run means it MOVES as new blocks
    arrive: blocks already inspected during confirmation slide into discovery,
    a fresh confirmation set is analysed, and the manifest hash stays the same
    while the untouched-holdout guarantee is gone. Retuning after seeing
    confirmation is a new hypothesis (§8.3) and must be visible as one.

    So `fraction` is only used to PROPOSE a cutoff on a first run; once the
    family carries `frozen_cutoff`, that timestamp decides the split and the
    fraction is ignored.
    """
    ordered = sorted(block_times, key=lambda b: (block_times[b], str(b)))
    if frozen_cutoff:
        disc = [b for b in ordered if str(block_times[b]) < frozen_cutoff]
        conf = [b for b in ordered if str(block_times[b]) >= frozen_cutoff]
        return set(disc), set(conf), ordered, len(disc)
    cut = int(len(ordered) * fraction)
    return set(ordered[:cut]), set(ordered[cut:]), ordered, cut


# --- §8.4: family-wise error ---------------------------------------------------
MIN_USABLE_REPLICATES = 100
MARGIN_AGREEMENT_FLOOR = 90.0  # percent; below this an outcome is not itself
# #556 measured kpr's within-round spread near +0.028. Calibration asks whether
# this implementation reproduces that MAGNITUDE, not whether it repeats that
# sample's verdict.
KPR_EXPECTED_RANGE = (0.0, 0.10)


def max_t_intervals(boot: dict, point: dict, alpha: float):
    """Block-level max-T: one critical value for the WHOLE family (§8.4).

    `boot[cid]` is one value per SHARED draw, with None where that draw could
    not be measured. Each candidate is standardised by its own bootstrap SD, the
    maximum |t| per replicate is collected across the family, and its (1-alpha)
    quantile becomes the critical value every member must clear. This is what
    stops "the best-looking member of a parameter sweep" from being read as a
    result.

    A candidate whose bootstrap cannot produce a usable spread gets NO interval
    at all rather than a (nan, nan) one. That distinction is load-bearing: `nan`
    compares false against everything, so a nan interval read as "excludes zero"
    would ship a candidate that was never measured — an absence of evidence
    wearing the shape of evidence.
    """
    ids = sorted(boot)
    sds, usable = {}, {}
    for cid in ids:
        vals = [v for v in boot[cid] if v is not None]
        usable[cid] = len(vals)
        sds[cid] = (statistics.stdev(vals)
                    if len(vals) >= MIN_USABLE_REPLICATES else float("nan"))

    measurable = [c for c in ids
                  if sds[c] and not math.isnan(sds[c]) and sds[c] > 0]

    n = min((len(boot[c]) for c in ids), default=0)
    maxts = []
    for i in range(n):
        t, ok = 0.0, False
        for cid in measurable:
            v = boot[cid][i]
            if v is None:
                continue
            t = max(t, abs(v - point[cid]) / sds[cid])
            ok = True
        if ok:
            maxts.append(t)
    if len(maxts) < MIN_USABLE_REPLICATES:
        return {}, float("nan"), sds
    maxts.sort()
    crit = maxts[min(int((1 - alpha) * len(maxts)), len(maxts) - 1)]
    return ({cid: (point[cid] - crit * sds[cid], point[cid] + crit * sds[cid])
             for cid in measurable}, crit, sds)


def boot_p_value(vals: list[float], point: float) -> float:
    """Two-sided bootstrap p: how often the resampled effect crosses zero."""
    if not vals:
        return float("nan")
    # count resamples that land on the far side of zero from the point estimate
    side = (sum(1 for v in vals if v <= 0) if point > 0
            else sum(1 for v in vals if v >= 0))
    return min(1.0, 2.0 * (side + 1) / (len(vals) + 1))


def holm(pvals: dict, alpha: float) -> dict:
    """Holm step-down — the acceptable fallback in §8.4."""
    ordered = sorted(pvals, key=lambda c: pvals[c])
    m = len(ordered)
    out, running = {}, 0.0
    for i, cid in enumerate(ordered):
        adj = min(1.0, (m - i) * pvals[cid])
        running = max(running, adj)   # monotone step-down
        out[cid] = running
    return out


# --- §8.4 by-product: what can this sample even see ---------------------------
def detectable_effect(sd: float) -> float:
    """Smallest effect an honest test could still find, at this sample size.

    Written down BEFORE the next idea is built, so it gets checked against the
    floor instead of costing a night. Family-wise correction makes the real
    floor higher than this single-candidate figure.
    """
    if not sd or math.isnan(sd):
        return float("nan")
    return (_Z_ALPHA + _Z_POWER) * sd


# --- the default family -------------------------------------------------------
# §8.3: freeze BEFORE looking at confirmation. Two members exist to test the
# instrument, not to ship: `kpr` (retired in #556) and `null` (no signal by
# construction). If either passes, the harness is wrong.
def _minutes(p: dict) -> float:
    return max(p["secs"], 1) / 60.0


def _null_value(p: dict) -> float:
    """Deterministic noise: same input, same number, on any machine."""
    h = hashlib.sha256(f"{p['guid']}|{p['rid']}|null-control".encode()).digest()
    return int.from_bytes(h[:4], "big") / 0xFFFFFFFF


DEFAULT_FAMILY = [
    Candidate("kpr", "kills per round — retired in #556, must fail again",
              "higher_is_better", lambda p: float(p["kills"] or 0)),
    Candidate("null", "deterministic pseudo-random control — must fail",
              "higher_is_better", _null_value),
    Candidate("kd_ratio", "kills / max(deaths,1)", "higher_is_better",
              lambda p: float(p["kills"] or 0) / max(float(p["deaths"] or 0), 1.0)),
    Candidate("dpm", "damage given per minute played", "higher_is_better",
              lambda p: float(p["dg"] or 0) / _minutes(p)),
    # ⛔ This used to divide by `deaths * 100` while calling itself a damage
    # RATIO, and `damage_received` was not even loaded. The manifest hashed the
    # prose, so a different statistic shipped under this name. Fixed at the
    # source rather than by renaming: the ratio people mean is the real one.
    Candidate("dmg_ratio", "damage given / max(damage received, 1)",
              "higher_is_better",
              lambda p: float(p["dg"] or 0) / max(float(p["dr"] or 0), 1.0)),
]


async def load(spatial: bool) -> tuple[dict, dict]:
    """Returns (blocks -> rid -> [player rows], block -> earliest timestamp)."""
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    try:
        rows = await conn.fetch(ROWS_SQL, spatial)
    finally:
        await conn.close()

    blocks: dict = defaultdict(lambda: defaultdict(list))
    times: dict = {}
    for r in rows:
        d = dict(r)
        blocks[d["block"]][d["rid"]].append(d)
        t = d["at"]
        if d["block"] not in times or t < times[d["block"]]:
            times[d["block"]] = t
    return {k: dict(v) for k, v in blocks.items()}, times


def _flatten(blocks: dict, keep: set) -> dict:
    out = {}
    for b in keep:
        for rid, players in blocks.get(b, {}).items():
            out[rid] = players
    return out


def _counts(blocks: dict, keep: set) -> tuple[int, int]:
    rounds = sum(len(blocks.get(b, {})) for b in keep)
    return len(keep), rounds


def analyse(blocks: dict, keep: set, family: Family) -> dict:
    """Point estimates + block bootstrap for every family member."""
    flat = _flatten(blocks, keep)
    sub = {b: blocks[b] for b in keep if b in blocks}
    oc = OUTCOMES[family.outcome]
    # ⛔ ONE sequence of draws for the whole family (§8.4). Per-candidate seeds
    # would give each member its own resamples, and the joint maximum would then
    # be taken across replicates that never shared a sample — destroying exactly
    # the covariance that makes the interval family-wise.
    draws = block_draws(sub, family.resamples, family.seed)
    point, boot = {}, {}
    for c in family.candidates:
        pt = within_round_spread(flat, c.fn, oc)
        if pt is None:
            continue
        point[c.cid] = pt
        boot[c.cid] = block_bootstrap(sub, c.fn, draws, outcome=oc)
    return {"point": point, "boot": boot, "rounds": len(flat)}


def report(family: Family, disc: dict, conf: dict,
           d_counts: tuple, c_counts: tuple, cutoff: str) -> list[dict]:
    """§8.5: EVERY candidate, with both halves. The table is the deliverable."""
    intervals, crit, sds = max_t_intervals(conf["boot"], conf["point"], family.alpha)
    # only the usable replicates: max_t_intervals() explicitly supports a
    # candidate whose bootstrap has gaps, so the p-value must not crash on the
    # first None and must not count the gaps in its denominator either
    pvals = {cid: boot_p_value([v for v in conf["boot"][cid] if v is not None],
                               conf["point"][cid])
             for cid in conf["point"]}
    hp = holm(pvals, family.alpha)

    print("=" * 108)
    print(f"§8 VALIDATION — family '{family.name}'")
    print(f"manifest sha256 : {family.manifest_hash()}")
    print("protocol        : docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md §8")
    print(f"outcome         : {family.outcome}"
          + ("  (win-rate difference)" if family.outcome == "win"
             else "  (signed stopwatch margin, seconds)"))
    print(f"resamples       : {family.resamples} block resamples, seed {family.seed}")
    print(f"split           : {d_counts[0]} discovery blocks / {c_counts[0]} confirmation blocks")
    print(f"                  {d_counts[1]} rounds / {c_counts[1]} rounds")
    print(f"cutoff          : {cutoff}")
    print(f"max-T crit      : {crit:.3f}  (family-wise {int((1-family.alpha)*100)}%)")
    print("=" * 108)
    hdr = (f"{'candidate':<12}{'disc':>9}{'conf':>9}{'sd':>8}"
           f"{'simultaneous 95%':>22}{'margin':>8}{'holm p':>9}{'dir':>5}  verdict")
    print(hdr)
    print("-" * 108)

    results = []
    for c in family.candidates:
        cid = c.cid
        if cid not in conf["point"]:
            print(f"{cid:<12}{'—':>9}{'—':>9}  excluded: not enough rounds to measure")
            results.append({"id": cid, "verdict": "EXCLUDED"})
            continue
        d = disc["point"].get(cid, float("nan"))
        k = conf["point"][cid]
        want_pos = c.direction == "higher_is_better"
        dir_ok = (d > 0 and k > 0) if want_pos else (d < 0 and k < 0)
        if cid not in intervals:
            # no usable bootstrap spread: unmeasured, which is not the same as
            # measured-and-clear. Fail closed and say which one it was.
            lo = hi = float("nan")
            excl_zero = False
            passed = False
            why = "no usable bootstrap interval — unmeasured, not clear"
        else:
            lo, hi = intervals[cid]
            excl_zero = not (lo <= 0 <= hi)
            passed = dir_ok and excl_zero
            why = ("" if passed else
                   "direction flipped" if not dir_ok else "interval contains zero")
        verdict = "SHIPS" if passed else "FAILS"
        # How far the interval bound nearest zero sits from zero, in SD units.
        # A bound of +0.001 and a bound of +0.040 are both "excludes zero"; only
        # this column tells them apart, and only one of them survives a reread.
        sd = sds.get(cid, float("nan"))
        near = min(abs(lo), abs(hi)) if excl_zero else 0.0
        margin = near / sd if sd and not math.isnan(sd) and sd > 0 else float("nan")
        if passed and margin < 0.25:
            verdict = "SHIPS?"
            why = "bound is a hair from zero — reread before believing it"
        print(f"{cid:<12}{d:>+9.3f}{k:>+9.3f}{sd:>8.3f}"
              f"{f'[{lo:+.3f}, {hi:+.3f}]':>22}{margin:>8.2f}{hp[cid]:>9.3f}"
              f"{'+' if want_pos else '-':>5}  {verdict}"
              + (f" — {why}" if why else ""))
        results.append({"id": cid, "discovery": d, "confirmation": k,
                        "interval": [lo, hi], "margin_sd": margin,
                        "holm_p": hp[cid], "verdict": verdict})
    print("-" * 108)

    floors = [detectable_effect(sds[c]) for c in sds
              if sds[c] and not math.isnan(sds[c])]
    if floors:
        print(f"\nFLOOR (§8.4 by-product). At {c_counts[0]} confirmation blocks / "
              f"{c_counts[1]} rounds, a single candidate needs an effect of about "
              f"{statistics.median(floors):+.3f}\nto be found {int(POWER_TARGET*100)}% "
              f"of the time. Family-wise correction raises this further: the max-T "
              f"critical value is\n{crit:.3f} rather than {_Z_ALPHA:.3f}, so the real "
              f"family floor is roughly {statistics.median(floors)*crit/_Z_ALPHA:+.3f}. "
              f"Anything smaller\nthan that cannot be distinguished from chance with "
              f"the data we have — check the next idea against this\nnumber BEFORE "
              f"building it.")
    return results


async def main() -> int:
    ap = argparse.ArgumentParser(description="Execute the §8 validation protocol.")
    ap.add_argument("--spatial", action="store_true",
                    help="restrict to rounds carrying position tracks (Layer 4 universe)")
    ap.add_argument("--resamples", type=int, default=RESAMPLES)
    ap.add_argument("--cutoff", default=None,
                    help="frozen absolute cutoff (e.g. '2026-07-13 21:35:13'); "
                         "without it the split is only PROPOSED, never frozen")
    ap.add_argument("--outcome", choices=sorted(OUTCOMES), default="win",
                    help="win = §8.6 reference; seconds = stopwatch margin")
    ap.add_argument("--seed", type=int, default=SEED,
                    help="published seed; changing it changes the manifest hash")
    args = ap.parse_args()

    if args.resamples < MIN_USABLE_REPLICATES:
        print(f"⛔ --resamples {args.resamples} is below the {MIN_USABLE_REPLICATES} "
              f"needed for any usable interval.\n"
              f"   Such a run produces no inference at all, yet every candidate "
              f"would read FAILS and\n   both controls would look correct — a "
              f"family retired by an instrument that never measured it.")
        return 5

    blocks, times = await load(args.spatial)
    if not blocks:
        print("no eligible rounds — nothing to validate")
        return 1

    family = Family(
        name=("foundations-2026-08" + ("-spatial" if args.spatial else "")
              + ("" if args.outcome == "win" else f"-{args.outcome}")),
        candidates=DEFAULT_FAMILY,
        filters=ROWS_SQL.strip() + f"\n-- bound $1 (spatial) = {args.spatial}",
        resamples=args.resamples,
        seed=args.seed,
        outcome=args.outcome,
        frozen_cutoff=args.cutoff,
    )

    disc_b, conf_b, ordered, cut = chronological_split(
        times, family.split_fraction, family.frozen_cutoff)
    cutoff = family.frozen_cutoff or (
        str(times[ordered[cut]]) if cut < len(ordered) else "n/a")
    if not family.frozen_cutoff:
        # ⛔ STOP. Warning and continuing would expose the latest 30% and issue
        # verdicts on it; re-running later with the printed flag cannot make
        # that holdout untouched again. The proposal is the whole output.
        print(f"⛔ NO FROZEN CUTOFF. This run proposes {cutoff} and stops there.\n"
              f"   Confirmation data stays unopened until the boundary is fixed,\n"
              f"   because a holdout that has been looked at is not a holdout:\n\n"
              f"     --cutoff '{cutoff}'\n")
        return 4

    # ⛔ AN OUTCOME MUST BE VALIDATED BEFORE IT IS BELIEVED.
    # A stopwatch margin is not a correlate of the match result — it IS the
    # result, so its sign must agree with who won. Measured here it agrees 48.5%
    # of the time, which is chance: the quantity derived from
    # `actual_duration_seconds` is NOT a stopwatch margin, and every verdict
    # computed from it was measuring something nobody had identified.
    if family.outcome == "seconds":
        flat_all = {rid: pl for rd in blocks.values() for rid, pl in rd.items()}
        agree, total = margin_agreement(flat_all)
        pct = 100.0 * agree / total if total else 0.0
        print(f"OUTCOME CHECK — margin sign vs actual winner: "
              f"{agree}/{total} = {pct:.1f}%")
        if pct < MARGIN_AGREEMENT_FLOOR:
            print(
                f"\n⛔ REFUSING TO RUN. A stopwatch margin that agrees with the\n"
                f"   result only {pct:.1f}% of the time is not a stopwatch margin.\n"
                f"   `rounds.actual_duration_seconds` measures wall clock, and R1\n"
                f"   fullholds run to the timelimit rather than to an objective,\n"
                f"   so T1 - T2 is not 'how much faster the second attack was'.\n"
                f"   Fix the quantity — `time_to_beat_seconds` is the real one and\n"
                f"   is populated on 33 of 2,007 eligible rounds — before using\n"
                f"   this outcome for anything.\n")
            return 3

    disc = analyse(blocks, disc_b, family)
    conf = analyse(blocks, conf_b, family)
    results = report(family, disc, conf,
                     _counts(blocks, disc_b), _counts(blocks, conf_b), cutoff)

    # The instrument must fail its own controls before anyone trusts its verdict
    # on an unknown metric.
    #
    # `null` is pure noise by construction: it must fail under EVERY outcome
    # definition. If noise ships, the harness is broken, full stop.
    #
    # `kpr` is a calibration point, not a universal control, and conflating the
    # two was a design error here. #556 retired it against the WIN outcome; it
    # says nothing about whether kill count tracks a stopwatch MARGIN. Enforcing
    # it under --outcome seconds would be asserting a result nobody measured, so
    # it is checked only for the outcome it was retired under and reported as
    # information otherwise.
    by_id = {r["id"]: r for r in results}
    print("\nINSTRUMENT CHECK")
    broken = False

    # `null` is the only STRUCTURAL control: pure noise by construction, so it
    # must fail under every outcome. If noise ships, the harness is broken.
    nullr = by_id.get("null", {}).get("verdict", "MISSING")
    if nullr != "FAILS":
        broken = True
    print(f"  null  {nullr:<9} {'ok' if nullr == 'FAILS' else 'NOISE SHIPPED — BROKEN'}")

    # `kpr` is CALIBRATION, not a control. #556 measured a spread near +0.028;
    # reproducing that number is what says the instrument measures the same
    # thing. Demanding that it stay NON-SIGNIFICANT would be wrong: that was a
    # property of #556's sample, not of the metric, and with more confirmation
    # blocks its interval may legitimately exclude zero. Enforcing the old
    # verdict would then discard a valid family for being better powered.
    kpr = by_id.get("kpr")
    if kpr and family.outcome == "win" and kpr.get("confirmation") is not None:
        k = kpr["confirmation"]
        in_range = KPR_EXPECTED_RANGE[0] <= k <= KPR_EXPECTED_RANGE[1]
        broken = broken or not in_range
        print(f"  kpr   {k:+.3f}    "
              + (f"ok — within the #556 range {KPR_EXPECTED_RANGE}"
                 if in_range else
                 f"OUTSIDE the #556 range {KPR_EXPECTED_RANGE} — the instrument "
                 f"is not measuring what #556 measured"))
        print(f"        verdict {kpr['verdict']} is reported, not enforced: "
              f"significance is a property of this sample, not of the metric")
    elif kpr:
        print(f"  kpr   {kpr['verdict']:<9} not calibrated under outcome "
              f"'{family.outcome}' — #556 measured 'win' only")

    if broken:
        print("\nRefusing to report this run as valid: the instrument failed its "
              "own checks. Do not use these verdicts.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
