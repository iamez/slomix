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
  -- The R1/R2 window admits MORE than one partner: the same map is often
  -- replayed inside a session, so a 45-minute window can see two or three R2s
  -- after one R1. Measured on this database: 189 rounds match several pairs.
  -- Left-joining that directly duplicates every player row in those rounds,
  -- which silently double-counts them in the within-round comparison.
  SELECT r1.id AS r1id, r2.id AS r2id, r1.defender_team AS r2_attacker,
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
    AND r1.defender_team IN (1, 2)
    AND r1.actual_duration_seconds IS NOT NULL
    AND r2.actual_duration_seconds IS NOT NULL
), pair_margin AS (
  -- One partner per round, the nearest in time, from EITHER side of the pair.
  -- DISTINCT ON over the round id keeps the join one-to-one; the ordering is
  -- deterministic (gap, then id) so the published table is reproducible.
  SELECT DISTINCT ON (rid) rid, r1id, r2id, r2_attacker, margin
  FROM (
    SELECT r1id AS rid, r1id, r2id, r2_attacker, margin, gap FROM candidate_pairs
    UNION ALL
    SELECT r2id AS rid, r1id, r2id, r2_attacker, margin, gap FROM candidate_pairs
  ) both_sides
  ORDER BY rid, gap, r2id
)
SELECT pcs.round_id                      AS rid,
       r.gaming_session_id               AS block,
       r.created_at                      AS at,
       pcs.player_guid                   AS guid,
       pcs.team                          AS team,
       r.winner_team                     AS winner,
       pcs.kills                         AS kills,
       pcs.deaths                        AS deaths,
       pcs.damage_given                  AS dg,
       pcs.time_played_seconds           AS secs,
       pm.margin                         AS margin,
       pm.r2_attacker                    AS r2_attacker
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

    def manifest_entry(self) -> dict:
        return {"id": self.cid, "description": self.description,
                "direction": self.direction}


@dataclass
class Family:
    """§8.3: every candidate and variant tried, including abandoned ones."""
    name: str
    candidates: list[Candidate]
    filters: str
    outcome: str = "win"          # §8.3: the outcome definition is frozen too
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

    None when the match pair could not be resolved — the round is then dropped,
    not scored as a zero margin. A missing measurement and a dead heat have the
    same shape here and must not be confused.
    """
    if p.get("margin") is None or p.get("r2_attacker") is None:
        return None
    return float(p["margin"]) * (1.0 if p["team"] == p["r2_attacker"] else -1.0)


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


def block_bootstrap(blocks: dict, metric: Callable, resamples: int, seed: int,
                    estimator: Callable = None,
                    outcome: Callable = outcome_win) -> list[float]:
    """Resample WHOLE blocks with replacement (§8.2).

    Teammates share an outcome, and R1/R2 plus several maps in one session share
    teams and stopwatch state. Resampling players or rounds independently would
    treat those as independent evidence and shrink every interval by a factor
    nobody earned.
    """
    keys = sorted(blocks)
    rng = _Rng(seed)
    out = []
    for _ in range(resamples):
        merged: dict = {}
        for _ in range(len(keys)):
            k = keys[rng.next_below(len(keys))]
            for rid, players in blocks[k].items():
                # a round drawn twice counts twice: give it a fresh key
                merged[(k, rid, len(merged))] = players
        s = (estimator or within_round_spread)(merged, metric, outcome)
        if s is not None:
            out.append(s)
    return out


# --- §8.3: chronological split, whole blocks ----------------------------------
def chronological_split(block_times: dict, fraction: float):
    """Earliest `fraction` of blocks discover; the latest stay untouched.

    Splitting on whole blocks is what keeps a gaming session from straddling the
    cutoff — a session on both sides would leak the confirmation half into
    discovery through shared teams and stopwatch state.
    """
    ordered = sorted(block_times, key=lambda b: (block_times[b], str(b)))
    cut = int(len(ordered) * fraction)
    return set(ordered[:cut]), set(ordered[cut:]), ordered, cut


# --- §8.4: family-wise error ---------------------------------------------------
def max_t_intervals(boot: dict, point: dict, alpha: float):
    """Block-level max-T: one critical value for the WHOLE family (§8.4).

    Each candidate is standardised by its own bootstrap SD, the maximum |t| per
    resample is collected, and its (1-alpha) quantile becomes the critical value
    every member must clear. This is what stops "the best-looking member of a
    parameter sweep" from being read as a result.
    """
    ids = sorted(boot)
    sds = {}
    for cid in ids:
        vals = boot[cid]
        sds[cid] = statistics.stdev(vals) if len(vals) > 1 else float("nan")

    n = min((len(boot[c]) for c in ids), default=0)
    maxts = []
    for i in range(n):
        t = 0.0
        for cid in ids:
            sd = sds[cid]
            if sd and not math.isnan(sd) and sd > 0:
                t = max(t, abs(boot[cid][i] - point[cid]) / sd)
        if t > 0:
            maxts.append(t)
    if not maxts:
        return {}, float("nan"), sds
    maxts.sort()
    crit = maxts[min(int((1 - alpha) * len(maxts)), len(maxts) - 1)]
    return ({cid: (point[cid] - crit * sds[cid], point[cid] + crit * sds[cid])
             for cid in ids if sds[cid] and not math.isnan(sds[cid])}, crit, sds)


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
    Candidate("dmg_ratio", "damage given / max(received,1)", "higher_is_better",
              lambda p: float(p["dg"] or 0) / max(float(p["deaths"] or 0) * 100.0, 1.0)),
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
    point, boot = {}, {}
    for i, c in enumerate(family.candidates):
        oc = OUTCOMES[family.outcome]
        p = within_round_spread(flat, c.fn, oc)
        if p is None:
            continue
        point[c.cid] = p
        # a per-candidate seed offset keeps members from sharing one draw
        boot[c.cid] = block_bootstrap(sub, c.fn, family.resamples,
                                      family.seed + i * 7919, outcome=oc)
    return {"point": point, "boot": boot, "rounds": len(flat)}


def report(family: Family, disc: dict, conf: dict,
           d_counts: tuple, c_counts: tuple, cutoff: str) -> list[dict]:
    """§8.5: EVERY candidate, with both halves. The table is the deliverable."""
    intervals, crit, sds = max_t_intervals(conf["boot"], conf["point"], family.alpha)
    pvals = {cid: boot_p_value(conf["boot"][cid], conf["point"][cid])
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
        lo, hi = intervals.get(cid, (float("nan"), float("nan")))
        want_pos = c.direction == "higher_is_better"
        dir_ok = (d > 0 and k > 0) if want_pos else (d < 0 and k < 0)
        excl_zero = not (lo <= 0 <= hi)
        passed = dir_ok and excl_zero
        verdict = "SHIPS" if passed else "FAILS"
        why = ""
        if not passed:
            why = ("direction flipped" if not dir_ok else "interval contains zero")
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
    ap.add_argument("--outcome", choices=sorted(OUTCOMES), default="win",
                    help="win = §8.6 reference; seconds = stopwatch margin")
    ap.add_argument("--seed", type=int, default=SEED,
                    help="published seed; changing it changes the manifest hash")
    args = ap.parse_args()

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
    )

    disc_b, conf_b, ordered, cut = chronological_split(times, family.split_fraction)
    cutoff = str(times[ordered[cut]]) if cut < len(ordered) else "n/a"

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
    by_id = {r["id"]: r["verdict"] for r in results}
    controls = ["null"] + (["kpr"] if family.outcome == "win" else [])
    print("\nINSTRUMENT CHECK — these controls must FAIL:")
    broken = False
    for cid in ("kpr", "null"):
        got = by_id.get(cid, "MISSING")
        enforced = cid in controls
        ok = got == "FAILS"
        if enforced:
            broken = broken or not ok
            note = "ok" if ok else "INSTRUMENT IS BROKEN"
        else:
            note = (f"not a control under outcome '{family.outcome}' "
                    f"— #556 retired it against 'win' only")
        print(f"  {cid:<6} {got:<9} {note}")
    if broken:
        print("\nRefusing to report this run as valid: a control passed. Do not "
              "use these verdicts.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
