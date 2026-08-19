#!/usr/bin/env python3
"""KIS v5 audit + KIS v6 candidate backtest (owner questions, 2026-08-19).

READ-ONLY. Nothing is written, no formula version is bumped, no cache row is
touched. Tables before surfaces (owner rule).

Owner's definition of KIS: "kill impact score bi mogu stet, koliko impakten je
bil kill ... za dober kill dobis vec tock, za filler kill pa navaden kill ...
tiste kile ki lahko jih nagradimo z bonus tockami, tiste ki pa nemoremo
tocno/zanesljivo jih pa pustimo na default value."

Owner decisions (2026-08-19), encoded below:
  1. kill DISTANCE is descriptive only — never a multiplier ("je pa fajn vedt
     kok dalec sta se strelala"). Section D reports it; nothing scores on it.
  2. BONUSES ONLY, never below 1.0. A filler kill is a normal kill, not a
     punished one — which is exactly what the owner said in the first place.
  3. gib / revive go to 1.0 and stay as descriptive columns.

Why the method changed. Round-winner prediction turned out to be too weak a
criterion for a PER-KILL score: 638 paired rounds means a weighting would have
to flip ~3.4% of rounds to reach p<0.05. So every axis now faces two tests:

  RELIABILITY  split-half over each player's kills (20 random splits,
               Spearman-Brown corrected), computed twice: raw, and on the
               residual after subtracting the (map, side) cell mean — so a
               "stable" axis cannot just be "he plays that side more".
  MODEL        role-stratified logistic regression with EVERY axis at once and
               man-advantage as a control IN the first fit (owner rule: control
               for dominance in the first query, not as an afterthought).
               Confidence intervals come from a cluster bootstrap over ROUNDS,
               because the outcome is shared by every kill in a round.

Sections:
    A  scope + role baselines
    B  double-count evidence (v5 spawn == v5 reinf)
    C  per-multiplier effect within role (v5)
    D  new proximity axes: coverage + within-role effect (incl. distance)
    E  the model: coefficients -> proposed v6 bonus table
    F  v6 scoring + distribution
    G  reliability: v5 vs v6 vs each axis        <- PRIMARY acceptance test
    H  round-level winner prediction (secondary, underpowered by construction)
    J  robustness: bootstrap CI, leave-one-map-out, defender-side stability
    K  escort sanity: does one 4.6% axis reorder the board?
    L  leave-one-map-out on the composite score
    I  acceptance verdict against the pre-registered thresholds (printed LAST,
       after J/K/L, because it reads them)

Usage:
    PGPASSWORD=... venv/bin/python3 scripts/backtest_kis_v6.py
"""
from __future__ import annotations

import asyncio
import bisect
import json
import math
import os
import random
import re
import statistics
import sys
from collections import defaultdict

import asyncpg
import numpy as np

# The formula version these scripts AUDIT. It is deliberately the old one:
# every measurement here compares a candidate against what production stores.
# ⚠️ When kis-v6 ships, change this — otherwise the audit silently keeps
# reading the superseded rows and reports them as current.
V5_VERSION = "kis-v5"

# Pre-registered acceptance thresholds (plan, 2026-08-19). Written down BEFORE
# the numbers were seen so the verdict cannot drift to fit the result.
ACCEPT_RELIABILITY_SB = 0.70        # v6 per-player reliability must reach this
ACCEPT_ROUND_TEST_TOLERANCE = 0.02  # v6 may not trail kills by more than this

TRADE_BACK_WINDOW_MS = 10_000     # killer dies within this -> the kill was answered
WAVE_Z_CAP = 2.0                  # cap the wave bonus at +2 SD, no runaway kills
MIN_KILLS_FOR_PLAYER = 200
BOOTSTRAP_ROUNDS = 200
SPLIT_HALF_REPEATS = 200
UNITS_TO_M = 0.0254               # Q3/ET convention: 1 unit ~ 1 inch

_COLOR = re.compile(r"\^.")


def _clean(s: str) -> str:
    return _COLOR.sub("", s or "")


def _pct(x: float) -> str:
    return f"{100.0 * x:6.2f}%"


def _mcnemar(b: int, c: int) -> tuple[float, float]:
    """McNemar chi-square (no continuity correction) + two-sided p."""
    if b + c == 0:
        return 0.0, 1.0
    chi2 = (b - c) ** 2 / (b + c)
    return chi2, math.erfc(math.sqrt(chi2 / 2.0))


def _pearson(xs, ys) -> float:
    n = len(xs)
    if n < 3:
        return float("nan")
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else float("nan")


def _spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(v: list[float]) -> list[float]:
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    return _pearson(ranks(xs), ranks(ys))


def _spearman_brown(r: float) -> float:
    """Correct a split-half correlation back to full test length."""
    return 2 * r / (1 + r) if r > -1 else float("nan")


# One row per kill, with everything any candidate axis needs.
# Filters, stated explicitly (owner rule: always attach the filters):
#   - rounds.is_valid, not a bot round, winner_team AND defender_team known
#   - bots excluded on both sides of the kill
#   - killer side from proximity_combat_position (best per-kill coverage); the
#     join carries victim_guid too, otherwise two kills sharing an event_time
#     would fan out into duplicate rows
#   - defender_team is READ, never hardcoded: etl_ice is the one map in the DB
#     where Allies defend (memory: kis-round-swing-2026-08-01)
KILLS_SQL = """
SELECT ko.id, ko.round_id AS rid, ko.kill_time, ko.outcome,
       ko.killer_guid, ko.victim_guid, ko.delta_ms, ko.effective_denied_ms,
       ki.killer_name, ki.total_impact, ki.victim_reinf, ki.spawn_multiplier,
       ki.reinf_multiplier, ki.carrier_multiplier, ki.crossfire_multiplier,
       ki.outcome_multiplier, ki.class_multiplier, ki.health_multiplier,
       ki.alive_multiplier, ki.is_objective_area, ki.is_carrier_kill,
       cp.attacker_team, cp.axis_alive, cp.allies_alive,
       cp.attacker_x AS killer_x, cp.attacker_y AS killer_y, cp.attacker_z AS killer_z,
       sqrt(power(cp.attacker_x - cp.victim_x, 2)
          + power(cp.attacker_y - cp.victim_y, 2)
          + power(cp.attacker_z - cp.victim_z, 2)) AS kill_distance,
       te.is_isolation_death, te.opportunity_count, te.nearest_teammate_dist,
       r.map_name AS rmap, r.defender_team, r.winner_team
FROM proximity_kill_outcome ko
JOIN rounds r ON r.id = ko.round_id
JOIN storytelling_kill_impact ki
  ON ki.kill_outcome_id = ko.id AND ki.formula_version = $1
LEFT JOIN proximity_combat_position cp
  ON cp.round_id = ko.round_id AND cp.event_type = 'kill'
 AND cp.attacker_guid = ko.killer_guid AND cp.victim_guid = ko.victim_guid
 AND cp.event_time = ko.kill_time
LEFT JOIN proximity_trade_event te
  ON te.round_id = ko.round_id AND te.victim_guid = ko.victim_guid
 AND te.death_time_ms = ko.kill_time
WHERE r.is_valid
  AND NOT COALESCE(r.is_bot_round, FALSE)
  AND r.winner_team   IN (1, 2)
  AND r.defender_team IN (1, 2)
  AND ko.killer_guid NOT LIKE 'OMNIBOT%'
  AND ko.victim_guid NOT LIKE 'OMNIBOT%'
  AND COALESCE(ki.killer_name, '') NOT LIKE '[BOT]%'
ORDER BY ko.round_id, ko.kill_time, ko.id
"""


# Two more per-kill sources, fetched separately and matched in Python: an exact
# SQL join cannot express "closest row within a tolerance" without a LATERAL
# that scans the whole table per kill.
#
# proximity_lua_trade_kill is the SERVER-SIDE (Lua checkTradeKill,
# proximity_tracker.lua:2071-2127, 3s window) record of "this kill avenged a
# team-mate". It is an INDEPENDENT path from proximity_trade_event, which the
# parser derives after the fact (parser.py:3780-3897) — so the two give the
# rule-of-two-paths check on the same concept.
REVENGE_SQL = """
SELECT round_id, trader_guid, traded_kill_time
FROM proximity_lua_trade_kill
WHERE round_id IS NOT NULL
"""

# proximity_reaction_metric is one row per CLOSED engagement (53% end in a
# kill). return_fire_ms IS NULL means the victim never landed a shot back —
# a clean pick — and duration_ms separates an instant pick from a long duel.
# Neither is inside any existing KIS multiplier.
REACTION_SQL = """
SELECT round_id, target_guid, end_time_ms, return_fire_ms, duration_ms
FROM proximity_reaction_metric
WHERE outcome = 'killed' AND round_id IS NOT NULL
"""


# Carry windows. `escort_any` — a kill while OUR team is running the objective —
# was the strongest single axis in scripts/backtest_carrier_context.py
# (odds 1.80, CI [0.336, 0.851] for the attacker, surviving the man-advantage
# control). It lives here so both scripts share one definition.
#
# GOTCHA: a carry itself predicts the round (attacker wins 73.6% of rounds with
# a carry vs 40.0% without), so this axis is only meaningful INSIDE the model,
# next to man_adv. Never quote the raw difference.
CARRY_SQL = """
SELECT ce.round_id AS rid, ce.carrier_guid, ce.carrier_team, ce.pickup_time,
       ce.drop_time, ce.duration_ms, ce.outcome, ce.carry_distance
FROM proximity_carrier_event ce
JOIN rounds r ON r.id = ce.round_id
WHERE r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
  AND ce.drop_time > ce.pickup_time
ORDER BY ce.round_id, ce.pickup_time
"""

CARRIER_TRACK_SQL = """
SELECT pt.round_id AS rid, pt.player_guid, pt.path
FROM player_track pt
JOIN rounds r ON r.id = pt.round_id AND r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
JOIN (SELECT DISTINCT round_id, carrier_guid FROM proximity_carrier_event) ce
  ON ce.round_id = pt.round_id AND ce.carrier_guid = pt.player_guid
WHERE pt.sample_count > 5
"""


class CarrierIndex:
    """Carry windows per round, and (optionally) the carrier's path over time."""

    def __init__(self, carries, tracks=()):
        self.by_round: dict[int, list] = defaultdict(list)
        for c in carries:
            self.by_round[c["rid"]].append(c)
        self.paths: dict[tuple[int, str], tuple[list[int], list[tuple]]] = {}
        raw: dict[tuple[int, str], list[tuple]] = defaultdict(list)
        for t in tracks:
            path = t["path"] if isinstance(t["path"], list) else json.loads(t["path"])
            for q in path:
                if q.get("x") is None:
                    continue
                raw[(t["rid"], t["player_guid"])].append(
                    (q.get("time", 0), (q["x"], q["y"], q.get("z", 0))))
        for key, pts in raw.items():
            pts.sort()
            self.paths[key] = ([p[0] for p in pts], [p[1] for p in pts])

    def active(self, rid: int, t: int, team: str | None = None):
        """The carry (if any) in progress at time t, optionally for one team."""
        for c in self.by_round.get(rid, ()):
            if c["pickup_time"] <= t <= c["drop_time"] and (
                    team is None or (c["carrier_team"] or "").upper() == team):
                return c
        return None

    def position(self, rid: int, guid: str, t: int, tol_ms: int = 3000):
        """Carrier position at time t, from the nearest path sample."""
        entry = self.paths.get((rid, guid))
        if not entry:
            return None
        times, points = entry
        i = bisect.bisect_left(times, t)
        best, gap = None, tol_ms
        for j in (i - 1, i, i + 1):
            if 0 <= j < len(times) and abs(times[j] - t) < gap:
                best, gap = points[j], abs(times[j] - t)
        return best



def _side(row) -> str:
    s = (row["attacker_team"] or "").upper()
    return "AXIS" if s in ("AXIS", "1") else "ALLIES"


def _role(row) -> str:
    team_num = 1 if _side(row) == "AXIS" else 2
    return "DEF" if team_num == row["defender_team"] else "ATT"


def _won(row) -> float:
    team_num = 1 if _side(row) == "AXIS" else 2
    return 1.0 if team_num == row["winner_team"] else 0.0


def _man_adv(row) -> float:
    mine = row["axis_alive"] if _side(row) == "AXIS" else row["allies_alive"]
    theirs = row["allies_alive"] if _side(row) == "AXIS" else row["axis_alive"]
    return float((mine or 0) - (theirs or 0))


def _denied_seconds(row) -> float | None:
    """Seconds the victim was actually out of play (revive-aware).

    round_end is endogenous (the round ending produced the number) and expired
    is a tracker artefact — both are excluded rather than scored.
    """
    if row["outcome"] in ("round_end", "expired"):
        return None
    ms = row["effective_denied_ms"] if (row["effective_denied_ms"] or 0) > 0 else row["delta_ms"]
    return ms / 1000.0 if ms and ms > 0 else None


def _logit_fit(X: np.ndarray, y: np.ndarray, iters: int = 40) -> np.ndarray:
    """Newton-Raphson logistic regression with a small ridge for stability."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-X @ beta))
        w = p * (1 - p) + 1e-9
        grad = X.T @ (y - p)
        hess = (X * w[:, None]).T @ X + 1e-6 * np.eye(X.shape[1])
        step = np.linalg.solve(hess, grad)
        beta += step
        if np.max(np.abs(step)) < 1e-8:
            break
    return beta


class Axes:
    """The candidate axes, and the inputs the v6 scorer is calibrated on.

    The wave axis needs the (map, side) cell statistics: the spawn interval is
    a property of the SIDE (ALLIES 20.7s / AXIS 30.0s), so an unnormalised wave
    number measures "you shot at Axis" rather than kill quality
    (memory: et-metrics-what-fails-2026-08-17).
    """

    def __init__(self, rows):
        self.cells: dict[tuple[str, str], tuple[float, float]] = {}
        buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
        for r in rows:
            if r["victim_reinf"] is not None:
                buckets[(r["rmap"], _side(r))].append(float(r["victim_reinf"]))
        for key, vals in buckets.items():
            self.cells[key] = (statistics.mean(vals), statistics.pstdev(vals) or 1.0)

        # "answered": the killer himself dies within the trade window
        deaths: dict[tuple[int, str], list[int]] = defaultdict(list)
        for r in rows:
            if _denied_seconds(r) is not None:
                deaths[(r["rid"], r["victim_guid"])].append(r["kill_time"])
        for key in deaths:
            deaths[key].sort()
        self._deaths = deaths
        self._revenge: set[tuple[int, str, int]] = set()
        self._reaction: dict[tuple[int, str], list[tuple[int, object, object]]] = defaultdict(list)
        # Per-kill flags are read hundreds of thousands of times by the
        # reliability bootstrap; compute each one once, keyed by kill id.
        self._memo: dict[tuple[str, int], float] = {}
        self._carriers: CarrierIndex | None = None

    def add_carries(self, carries) -> None:
        """Carry windows for the escort axis (no paths — distance is not scored)."""
        self._carriers = CarrierIndex(carries)

    def _cached(self, name: str, row, compute) -> float:
        key = (name, row["id"])
        val = self._memo.get(key)
        if val is None:
            val = compute(row)
            self._memo[key] = val
        return val

    def add_revenge(self, rows) -> None:
        """Server-side 'this kill avenged a team-mate' flags (Lua, 3s window)."""
        self._revenge = {(r["round_id"], r["trader_guid"], r["traded_kill_time"]) for r in rows}

    def add_reaction(self, rows) -> None:
        """Engagement records for the victim, matched by end time near the kill."""
        for r in rows:
            self._reaction[(r["round_id"], r["target_guid"])].append(
                (r["end_time_ms"], r["return_fire_ms"], r["duration_ms"]))
        for key in self._reaction:
            # sort by end time only — return_fire_ms/duration_ms may be NULL
            self._reaction[key].sort(key=lambda t: t[0] or 0)

    def _engagement(self, row):
        """The victim's engagement that ended within 1.5s of this kill."""
        key = ("_eng", row["id"])
        if key in self._memo:
            return self._memo[key]
        best, best_gap = None, 1501
        for end_ms, ret_ms, dur_ms in self._reaction.get((row["rid"], row["victim_guid"]), ()):
            gap = abs((end_ms or 0) - row["kill_time"])
            if gap < best_gap:
                best, best_gap = (ret_ms, dur_ms), gap
        self._memo[key] = best
        return best

    def revenge(self, row) -> float:
        """This kill avenged a team-mate (independent Lua path)."""
        return self._cached("revenge", row, lambda r: float(
            (r["rid"], r["killer_guid"], r["kill_time"]) in self._revenge))

    def clean_pick(self, row) -> float:
        """The victim never landed a shot back at this killer."""
        eng = self._engagement(row)
        return 1.0 if (eng is not None and eng[0] is None) else 0.0

    def long_duel(self, row) -> float:
        """The engagement that killed the victim lasted over 3 seconds."""
        eng = self._engagement(row)
        return 1.0 if (eng is not None and (eng[1] or 0) > 3000) else 0.0

    def wave_z(self, row) -> float:
        if row["victim_reinf"] is None:
            return 0.0
        mean, sd = self.cells.get((row["rmap"], _side(row)), (0.0, 1.0))
        return max(-WAVE_Z_CAP, min(WAVE_Z_CAP, (float(row["victim_reinf"]) - mean) / sd))

    def answered(self, row) -> float:
        """1.0 when the enemy answered this kill within the trade window."""
        def _compute(r):
            for t in self._deaths.get((r["rid"], r["killer_guid"]), ()):
                if r["kill_time"] < t <= r["kill_time"] + TRADE_BACK_WINDOW_MS:
                    return 1.0
            return 0.0
        return self._cached("answered", row, _compute)

    def stood(self, row) -> float:
        """Bonus-shaped mirror of `answered` — the kill they could not answer."""
        return 1.0 - self.answered(row)

    def isolation(self, row) -> float:
        return 1.0 if row["is_isolation_death"] else 0.0

    def escort(self, row) -> float:
        """Our team is carrying, and this kill is neither on nor by the carrier.

        The distance band (500-1200u) was measured and did NOT survive the model
        on top of this flag (CI [-0.035, 0.575]) — the plain flag already carries
        the information, so distance stays descriptive.
        """
        if self._carriers is None:
            return 0.0

        def _compute(r):
            car = self._carriers.active(r["rid"], r["kill_time"], _side(r))
            if car is None:
                return 0.0
            cg = car["carrier_guid"]
            return 0.0 if (r["victim_guid"] == cg or r["killer_guid"] == cg) else 1.0

        return self._cached("escort", row, _compute)

    def objective(self, row) -> float:
        return 1.0 if row["is_objective_area"] else 0.0

    def crossfire(self, row) -> float:
        return 1.0 if row["crossfire_multiplier"] != 1.0 else 0.0

    def carrier(self, row) -> float:
        return 1.0 if row["is_carrier_kill"] else 0.0

    def gibbed(self, row) -> float:
        return 1.0 if row["outcome"] == "gibbed" else 0.0

    def revived(self, row) -> float:
        return 1.0 if row["outcome"] == "revived" else 0.0

    def model_features(self):
        """Feature list for section E — man_adv LAST so it reads as the control."""
        return [
            ("wave_z", self.wave_z),
            ("stood", self.stood),
            ("revenge", self.revenge),
            ("clean_pick", self.clean_pick),
            ("long_duel", self.long_duel),
            ("isolation", self.isolation),
            ("escort", self.escort),
            ("objective", self.objective),
            ("crossfire", self.crossfire),
            ("carrier", self.carrier),
            ("gibbed", self.gibbed),
            ("revived", self.revived),
            ("man_adv", _man_adv),
        ]


def _v6_scorer(axes: Axes, weights: dict[str, dict[str, float]]):
    """Build the v6 scorer from the FITTED weights.

    weights[role][axis] is an odds ratio the model measured, already floored at
    1.0 (owner decision 2: bonuses only). An axis whose CI covered zero never
    reaches this dict and therefore contributes exactly nothing.
    """
    flags = {
        "stood": axes.stood,
        "escort": axes.escort,
        "revenge": axes.revenge,
        "clean_pick": axes.clean_pick,
        "long_duel": axes.long_duel,
        "isolation": axes.isolation,
        "objective": axes.objective,
        "crossfire": axes.crossfire,
        "carrier": axes.carrier,
        "gibbed": axes.gibbed,
        "revived": axes.revived,
    }

    def score(row) -> float:
        w = weights[_role(row)]
        # wave: a graded bonus, never a penalty — exp(beta*z) floored at 1.0
        total = max(1.0, math.exp(w.get("wave_beta", 0.0) * axes.wave_z(row)))
        for name, fn in flags.items():
            mult = w.get(name, 1.0)
            if mult != 1.0 and fn(row):
                total *= mult
        return total

    return score


def _split_halves(players, value_of, cell_mean, rng):
    """One random split of every player's kills into two halves."""
    first, second = [], []
    for _guid, kills in players:
        vals = [value_of(r) - (cell_mean(r) if cell_mean else 0.0) for r in kills]
        rng.shuffle(vals)
        half = len(vals) // 2
        first.append(sum(vals[:half]) / half)
        second.append(sum(vals[half:]) / len(vals[half:]))
    return first, second


def _reliability(players, value_of, cell_mean=None, seed=1) -> float:
    """Split-half reliability of a per-kill metric's player mean."""
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not crypto
    rs = [_pearson(*_split_halves(players, value_of, cell_mean, rng))
          for _ in range(SPLIT_HALF_REPEATS)]
    return _spearman_brown(sum(rs) / len(rs))


def _reliability_ci(players, value_of, cell_mean=None, seed=1, draws=300):
    """Reliability plus a bootstrap CI over PLAYERS.

    With ~15 players the split-half correlation is itself a noisy statistic —
    two runs of the 20-repeat version landed on 0.735 and 0.662. The point
    estimate alone is not a decision; the interval is.
    """
    rng = random.Random(seed)  # noqa: S311 - statistical resampling, not crypto
    point = _reliability(players, value_of, cell_mean, seed)
    vals = []
    for _ in range(draws):
        sample = [players[rng.randrange(len(players))] for _ in range(len(players))]
        a, b = _split_halves(sample, value_of, cell_mean, rng)
        v = _spearman_brown(_pearson(a, b))
        if not math.isnan(v):
            vals.append(v)
    lo = float(np.percentile(vals, 2.5)) if vals else float("nan")
    hi = float(np.percentile(vals, 97.5)) if vals else float("nan")
    return point, lo, hi


async def main() -> int:  # noqa: PLR0915 - a report, read top to bottom
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")
    rows = await conn.fetch(KILLS_SQL, V5_VERSION)
    total_v5 = await conn.fetchval(
        "SELECT COUNT(*) FROM storytelling_kill_impact WHERE formula_version = $1", V5_VERSION)
    revenge_rows = await conn.fetch(REVENGE_SQL)
    reaction_rows = await conn.fetch(REACTION_SQL)
    carry_rows = await conn.fetch(CARRY_SQL)
    await conn.close()

    rows = [r for r in rows if r["attacker_team"]]
    axes = Axes(rows)
    axes.add_revenge(revenge_rows)
    axes.add_reaction(reaction_rows)
    axes.add_carries(carry_rows)

    # ---- A. scope -----------------------------------------------------------
    print("=" * 78)
    print("A. SCOPE  (is_valid, not bot round, winner+defender known, no bots)")
    print("=" * 78)
    baselines = {}
    for role in ("ATT", "DEF"):
        sub = [r for r in rows if _role(r) == role]
        baselines[role] = sum(_won(r) for r in sub) / len(sub)
        print(f"  {role} kills {len(sub):>6}   baseline win {_pct(baselines[role])}")
    print(f"  kis-v5 rows in DB ............ {total_v5}")
    print(f"  kills in scope ............... {len(rows)} "
          f"({100.0*len(rows)/max(total_v5,1):.1f}% of v5 rows)")
    print(f"  rounds in scope .............. {len({r['rid'] for r in rows})}")
    print("  -> a global baseline (~51%) mixes the two roles and FLIPS signs.")

    def effect(subset, role):
        sel = [r for r in subset if _role(r) == role]
        if len(sel) < 80:
            return len(sel), float("nan")
        return len(sel), (sum(_won(r) for r in sel) / len(sel) - baselines[role]) * 100

    # ---- B. double count ----------------------------------------------------
    print()
    print("=" * 78)
    print("B. DOUBLE COUNT: v5 spawn_multiplier vs reinf_multiplier")
    print("=" * 78)
    ls = [math.log(r["spawn_multiplier"]) for r in rows if r["spawn_multiplier"] > 0]
    lr = [math.log(r["reinf_multiplier"]) for r in rows if r["reinf_multiplier"] > 0]
    print(f"  r(log spawn, log reinf) ...... {_pearson(ls, lr):.3f}  "
          "(one Lua time_to_next, stored twice)")

    def logsum(r, skip=()):
        parts = {
            "carrier": r["carrier_multiplier"], "crossfire": r["crossfire_multiplier"],
            "spawn": r["spawn_multiplier"], "outcome": r["outcome_multiplier"],
            "class": r["class_multiplier"], "health": r["health_multiplier"],
            "alive": r["alive_multiplier"], "reinf": r["reinf_multiplier"],
            "obj": 1.4 if r["is_objective_area"] else 1.0,
        }
        return sum(math.log(v) for k, v in parts.items() if k not in skip and v > 0)

    v_all = statistics.variance([logsum(r) for r in rows])
    v_no_clock = statistics.variance([logsum(r, skip=("spawn", "reinf")) for r in rows])
    print(f"  var(ln total) {v_all:.4f} -> without spawn AND reinf {v_no_clock:.4f}")
    print(f"  -> share of KIS spread owned by the enemy spawn clock: "
          f"{100*(1 - v_no_clock/v_all):.1f}%")

    # ---- C. v5 multipliers within role -------------------------------------
    print()
    print("=" * 78)
    print("C. v5 MULTIPLIERS, WITHIN ROLE  (pp vs that role's baseline)")
    print("=" * 78)
    v5_flags = {
        "carrier": lambda r: r["is_carrier_kill"],
        "crossfire": lambda r: r["crossfire_multiplier"] != 1.0,
        "objective": lambda r: r["is_objective_area"],
        "gibbed": lambda r: r["outcome"] == "gibbed",
        "revived": lambda r: r["outcome"] == "revived",
        "class(medic)": lambda r: r["class_multiplier"] >= 1.5,
        "health<30": lambda r: r["health_multiplier"] != 1.0,
        "outnumbered": lambda r: r["alive_multiplier"] != 1.0,
    }
    print(f"  {'multiplier':<14}{'ATT n':>7}{'ATT pp':>9}{'DEF n':>7}{'DEF pp':>9}")
    for name, fn in v5_flags.items():
        hit = [r for r in rows if fn(r)]
        (na, pa), (nd, pd) = effect(hit, "ATT"), effect(hit, "DEF")
        print(f"  {name:<14}{na:>7}{pa:>9.1f}{nd:>7}{pd:>9.1f}")

    # ---- D. new axes --------------------------------------------------------
    print()
    print("=" * 78)
    print("D. NEW PROXIMITY AXES  (coverage, then pp vs role baseline)")
    print("=" * 78)
    have_iso = [r for r in rows if r["is_isolation_death"] is not None]
    have_dist = [r for r in rows if r["kill_distance"] is not None]
    answered = [r for r in rows if axes.answered(r)]
    print(f"  trade_event joined ........... {len(have_iso)} "
          f"({100.0*len(have_iso)/len(rows):.1f}%)")
    print(f"  both positions (distance) .... {len(have_dist)} "
          f"({100.0*len(have_dist)/len(rows):.1f}%)")
    print(f"  answered within {TRADE_BACK_WINDOW_MS//1000}s ......... {len(answered)} "
          f"({100.0*len(answered)/len(rows):.1f}%)")
    for name, fn in (("kill was answered", axes.answered),
                     ("victim isolated", axes.isolation),
                     ("escort kill (we carry)", axes.escort),
                     ("kill was revenge", axes.revenge),
                     ("clean pick (no reply)", axes.clean_pick),
                     ("long duel (>3s)", axes.long_duel)):
        hit = [r for r in rows if fn(r)]
        (na, pa), (nd, pd) = effect(hit, "ATT"), effect(hit, "DEF")
        print(f"  {name:<20} ATT {pa:+5.1f}pp (n={na:5d})   DEF {pd:+5.1f}pp (n={nd:5d})")

    print()
    print("  kill DISTANCE — descriptive only (owner decision, never a multiplier):")
    ds = sorted(float(r["kill_distance"]) for r in have_dist)
    for label, q in (("p10", 0.10), ("median", 0.50), ("p90", 0.90), ("p99", 0.99)):
        v = ds[int(q * len(ds))]
        print(f"    {label:<7}{v:7.0f} u = {v*UNITS_TO_M:5.1f} m")
    for lo, hi, nm in ((0, 300, "<300u (<7.6m)"), (300, 900, "300-900u"),
                       (900, 10 ** 9, ">900u (>22.9m)")):
        hit = [r for r in have_dist if lo <= float(r["kill_distance"]) < hi]
        (na, pa), (nd, pd) = effect(hit, "ATT"), effect(hit, "DEF")
        print(f"    {nm:<16} ATT {pa:+5.1f}pp (n={na:5d})   DEF {pd:+5.1f}pp (n={nd:5d})")
    print("    ^ real and role-mirrored, but parked for a separate feature")
    print("      ('who kills from inside vs who chips away from range'), NOT KIS.")

    # ---- E. the model -------------------------------------------------------
    print()
    print("=" * 78)
    print("E. MODEL: role-stratified logistic, every axis at once, man_adv control")
    print("=" * 78)
    print(f"  CIs from a cluster bootstrap over ROUNDS ({BOOTSTRAP_ROUNDS}x) — the")
    print("  outcome is shared by every kill in a round, so kills are not n.")
    features = axes.model_features()
    weights: dict[str, dict[str, float]] = {"ATT": {}, "DEF": {}}
    for role in ("ATT", "DEF"):
        sub = [r for r in rows if _role(r) == role]
        X = np.column_stack([np.ones(len(sub))] + [[fn(r) for r in sub] for _, fn in features])
        y = np.array([_won(r) for r in sub])
        rids = np.array([r["rid"] for r in sub])
        beta = _logit_fit(X, y)
        uniq = sorted(set(rids.tolist()))
        idx_by = {u: np.where(rids == u)[0] for u in uniq}
        rng = random.Random(20260819)  # noqa: S311 - statistical control, not crypto
        boots = []
        for _ in range(BOOTSTRAP_ROUNDS):
            pick = [idx_by[uniq[rng.randrange(len(uniq))]] for _ in range(len(uniq))]
            ii = np.concatenate(pick)
            try:
                boots.append(_logit_fit(X[ii], y[ii], iters=25))
            except np.linalg.LinAlgError:
                continue
        B = np.array(boots)
        print(f"\n  --- {role}  (n={len(sub)} kills, {len(uniq)} rounds, "
              f"baseline {_pct(y.mean())})")
        print(f"  {'axis':<12}{'coef':>8}{'95% CI':>22}{'odds':>7}  kept?")
        for i, (name, _fn) in enumerate([("intercept", None)] + features):
            lo, hi = np.percentile(B[:, i], [2.5, 97.5])
            keeps = not (lo <= 0.0 <= hi)
            if name == "intercept":
                mark = ""
            elif name == "man_adv":
                mark = "(control)"
            elif not keeps:
                mark = "-> 1.0 (CI covers 0)"
            elif beta[i] <= 0:
                mark = "-> 1.0 (negative; owner: bonuses only)"
            else:
                mark = "KEEP"
            print(f"  {name:<12}{beta[i]:>8.3f}  [{lo:>7.3f},{hi:>7.3f}]"
                  f"{math.exp(beta[i]):>7.2f}  {mark}")
            if name in ("intercept", "man_adv") or not keeps or beta[i] <= 0:
                continue
            # Owner decision 2: bonuses only. A measured-negative axis is NOT
            # turned into a penalty; it simply earns no bonus.
            if name == "wave_z":
                weights[role]["wave_beta"] = float(beta[i])
            else:
                weights[role][name] = round(float(math.exp(beta[i])), 2)

    print()
    print("  PROPOSED v6 BONUS TABLE (model decides, table shows):")
    print(f"  {'axis':<14}{'ATT':>10}{'DEF':>10}")
    a = weights["ATT"].get("wave_beta", 0.0)
    d = weights["DEF"].get("wave_beta", 0.0)
    print(f"  {'wave (beta)':<14}{a:>10.3f}{d:>10.3f}   -> max bonus "
          f"x{math.exp(a*WAVE_Z_CAP):.2f} / x{math.exp(d*WAVE_Z_CAP):.2f}")
    for name in ("stood", "escort", "revenge", "clean_pick", "long_duel",
                 "isolation", "objective", "crossfire", "carrier", "gibbed",
                 "revived"):
        print(f"  {name:<14}{weights['ATT'].get(name, 1.0):>10.2f}"
              f"{weights['DEF'].get(name, 1.0):>10.2f}")
    print("  everything not listed: x1.00 (spawn=duplicate, class, health,")
    print("  alive/clutch, push, distance)")

    # ---- F. v6 scoring ------------------------------------------------------
    print()
    print("=" * 78)
    print("F. v6 SCORE DISTRIBUTION")
    print("=" * 78)
    score_v6 = _v6_scorer(axes, weights)
    # escort is a ROUND-CONTEXT axis: whether a carry was running while you were
    # alive is not a property of you. Section G measures what that does to a
    # per-player score, so the two composites are carried side by side.
    weights_no_escort = {role: {k: v for k, v in w.items() if k != "escort"}
                         for role, w in weights.items()}
    score_v6_ne = _v6_scorer(axes, weights_no_escort)
    v6 = [score_v6(r) for r in rows]
    v5 = [float(r["total_impact"]) for r in rows]
    for label, vals in (("v5", v5), ("v6", v6)):
        s = sorted(vals)
        print(f"  {label}: mean {statistics.mean(vals):.2f}  median {s[len(s)//2]:.2f}  "
              f"p90 {s[int(0.9*len(s))]:.2f}  max {s[-1]:.2f}")
    plain = sum(1 for v in v6 if v <= 1.001)
    print(f"  ordinary kills (v6 == 1.00) .. {plain} ({100.0*plain/len(v6):.1f}%) "
          "<- the owner's 'filler kill is a normal kill'")

    # ---- G. reliability -----------------------------------------------------
    print()
    print("=" * 78)
    print("G. RELIABILITY (split-half per player, Spearman-Brown)  [PRIMARY TEST]")
    print("=" * 78)
    by_player = defaultdict(list)
    for r in rows:
        by_player[r["killer_guid"]].append(r)
    players = [(g, v) for g, v in by_player.items() if len(v) >= MIN_KILLS_FOR_PLAYER]
    print(f"  players with >= {MIN_KILLS_FOR_PLAYER} kills: {len(players)}   "
          f"kills used: {sum(len(v) for _, v in players)}")

    def cell_mean_of(fn):
        buckets = defaultdict(list)
        for r in rows:
            buckets[(r["rmap"], _side(r))].append(fn(r))
        means = {k: sum(v) / len(v) for k, v in buckets.items()}
        return lambda r: means[(r["rmap"], _side(r))]

    def role_mean_of(fn):
        buckets = defaultdict(list)
        for r in rows:
            buckets[_role(r)].append(fn(r))
        means = {k: sum(v) / len(v) for k, v in buckets.items()}
        return lambda r: means[_role(r)]

    metrics = {
        "KIS v5 (total)": lambda r: float(r["total_impact"]),
        "KIS v6 (with escort)": score_v6,
        "KIS v6 (no escort)": score_v6_ne,
        "wave phase (reinf)": lambda r: float(r["victim_reinf"] or 0.0),
        "answered rate": axes.answered,
        "isolation rate": axes.isolation,
        "escort rate": axes.escort,
        "revenge rate": axes.revenge,
        "clean-pick rate": axes.clean_pick,
        "denied seconds": lambda r: _denied_seconds(r) or 0.0,
        "kill distance": lambda r: float(r["kill_distance"] or 0.0),
    }
    print(f"  {'metric':<22}{'raw':>7}{'role-resid (95% CI)':>26}{'(map,side)':>12}")
    reliability, reliability_cell, reliability_ci = {}, {}, {}
    for name, fn in metrics.items():
        raw = _reliability(players, fn)
        by_role, lo, hi = _reliability_ci(players, fn, cell_mean=role_mean_of(fn))
        by_cell = _reliability(players, fn, cell_mean=cell_mean_of(fn))
        reliability[name] = by_role
        reliability_cell[name] = by_cell
        reliability_ci[name] = (lo, hi)
        print(f"  {name:<22}{raw:>7.3f}{by_role:>13.3f} [{lo:>5.2f},{hi:>5.2f}]{by_cell:>12.3f}")

    # WHICH control is the right one — measured, not assumed. Every (map, side)
    # cell in this DB maps to exactly ONE role (Axis defends on every map but
    # etl_ice), so residualising a ROLE-GATED score by (map, side) subtracts the
    # role gate itself and deflates it by construction. The plan pre-registered
    # the (map,side) control before that degeneracy was known; both columns are
    # printed, and the verdict uses the role residual for role-aware scores.
    cells = defaultdict(set)
    for r in rows:
        cells[(r["rmap"], _side(r))].add(_role(r))
    degenerate = sum(1 for v in cells.values() if len(v) == 1)
    print(f"  (map,side) cells: {len(cells)}, mapping to exactly one role: {degenerate}")
    print("  -> for a role-gated score the (map,side) column is over-control;")
    print("     the role-residual column is the honest one. Both are shown.")

    # Per-role reliability: does the score separate players at all on each side?
    print()
    for role in ("ATT", "DEF"):
        pr = [(g, [r for r in v if _role(r) == role]) for g, v in players]
        pr = [(g, v) for g, v in pr if len(v) >= MIN_KILLS_FOR_PLAYER // 2]
        if len(pr) < 5:
            continue
        v5r = _reliability(pr, lambda r: float(r["total_impact"]))
        v6r = _reliability(pr, score_v6)
        v6n = _reliability(pr, score_v6_ne)
        print(f"  {role}-only kills ({len(pr)} players): v5 {v5r:6.3f}   "
              f"v6+escort {v6r:6.3f}   v6 no-escort {v6n:6.3f}")

    # ---- H. round-level prediction -----------------------------------------
    print()
    print("=" * 78)
    print("H. ROUND WINNER (secondary — underpowered by construction)")
    print("=" * 78)
    cands = {"kills": lambda r: 1.0,
             "v5": lambda r: float(r["total_impact"]),
             "v6": score_v6,
             "v6-ne": score_v6_ne}
    per_round = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    rmap, won_by = {}, {}
    for r in rows:
        side = _side(r)
        for name, fn in cands.items():
            per_round[r["rid"]][side][name] += fn(r)
        rmap[r["rid"]] = r["rmap"]
        won_by[(r["rid"], side)] = _won(r)
    diffs = []
    for rid, sides in per_round.items():
        if "AXIS" not in sides or "ALLIES" not in sides:
            continue
        d = {n: sides["AXIS"][n] - sides["ALLIES"][n] for n in cands}
        d["map"], d["won"] = rmap[rid], won_by[(rid, "AXIS")]
        diffs.append(d)
    print(f"  paired rounds ................ {len(diffs)}")
    preds, accs = {}, {}
    for name in cands:
        by_map = defaultdict(list)
        for d in diffs:
            by_map[d["map"]].append(d[name])
        means = {m: sum(v) / len(v) for m, v in by_map.items()}
        preds[name] = [1 if ((d[name] - means[d["map"]]) > 0) == (d["won"] == 1) else 0
                       for d in diffs]
        accs[name] = sum(preds[name]) / len(preds[name])
    for name in cands:
        if name == "kills":
            print(f"  {name:<6} {_pct(accs[name])}   (null model: every kill worth 1)")
            continue
        b = sum(1 for x, y in zip(preds[name], preds["kills"]) if x and not y)
        c = sum(1 for x, y in zip(preds[name], preds["kills"]) if y and not x)
        chi2, p = _mcnemar(b, c)
        print(f"  {name:<6} {_pct(accs[name])}   vs kills {b}:{c} "
              f"chi2={chi2:.2f} p={p:.3f}")
    print("  With ~640 rounds a weighting must flip ~3.4% of them to reach")
    print("  p<0.05 — so 'no difference' here is expected, not a failure.")

    # ---- J. robustness of the round-level result ----------------------------
    print()
    print("=" * 78)
    print("J. ROBUSTNESS  (a single McNemar p is not evidence on its own)")
    print("=" * 78)
    rng = random.Random(3)  # noqa: S311 - statistical resampling, not crypto

    def _acc(sample, key):
        by_map = defaultdict(list)
        for d in sample:
            by_map[d["map"]].append(d[key])
        means = {m: sum(v) / len(v) for m, v in by_map.items()}
        return sum(1 for d in sample
                   if ((d[key] - means[d["map"]]) > 0) == (d["won"] == 1)) / len(sample)

    deltas = []
    for _ in range(1000):
        sample = [diffs[rng.randrange(len(diffs))] for _ in range(len(diffs))]
        deltas.append(_acc(sample, "v6") - _acc(sample, "kills"))
    lo, hi = np.percentile(deltas, [2.5, 97.5])
    print(f"  acc(v6) - acc(kills) ......... {statistics.mean(deltas)*100:+.2f} pp   "
          f"95% CI [{lo*100:+.2f}, {hi*100:+.2f}]  "
          f"({'excludes 0' if lo > 0 else 'TOUCHES 0 — promising, not proven'})")
    print("  leave-one-map-out (v6 - kills, pp):")
    for mp in sorted({d["map"] for d in diffs}):
        sample = [d for d in diffs if d["map"] != mp]
        if len(sample) < 200:
            continue
        print(f"    without {mp:<18}n={len(sample):4d}  "
              f"{100*(_acc(sample, 'v6') - _acc(sample, 'kills')):+5.2f}")

    print()
    print("  DEF-only reliability at several minimum kill counts — the defender")
    print("  side is where BOTH versions are thin, and the estimate wanders:")
    for thr in (100, 150, 200, 300):
        pr = [(g, [r for r in v if _role(r) == "DEF"]) for g, v in by_player.items()]
        pr = [(g, v) for g, v in pr if len(v) >= thr]
        if len(pr) < 5:
            continue
        v5r = _reliability(pr, lambda r: float(r["total_impact"]))
        v6r = _reliability(pr, score_v6)
        print(f"    >= {thr:3d} kills ({len(pr):2d} players): v5 {v5r:6.3f}   v6 {v6r:6.3f}")
    print("  -> report the ATTACKER number with confidence, the DEFENDER number")
    print("     as not-yet-measurable at this sample size.")

    # ---- K. escort sanity: does one 4.6% axis move more than its weight? ----
    print()
    print("=" * 78)
    print("K. ESCORT SANITY  (a new, strong axis deserves its own suspicion)")
    print("=" * 78)
    esc = [r for r in rows if axes.escort(r)]
    print(f"  kills carrying the escort bonus .. {len(esc)} "
          f"({100.0*len(esc)/len(rows):.1f}% of kills)")
    with_esc = {g: sum(1 for r in v if axes.escort(r)) for g, v in by_player.items()}
    if players:
        shares = sorted((with_esc.get(g, 0) / len(v)) for g, v in players)
        print(f"  per-player escort share .......... {100*shares[0]:.1f}% - "
              f"{100*shares[-1]:.1f}%  (median {100*shares[len(shares)//2]:.1f}%)")
        rank_no_esc = sorted(
            players, key=lambda kv: -sum(score_v6(r) for r in kv[1] if not axes.escort(r))
            / max(sum(1 for r in kv[1] if not axes.escort(r)), 1))
        rank_all = sorted(players, key=lambda kv: -sum(score_v6(r) for r in kv[1]) / len(kv[1]))
        pos_a = {g: i for i, (g, _) in enumerate(rank_all)}
        pos_n = {g: i for i, (g, _) in enumerate(rank_no_esc)}
        movers = sum(1 for g, _ in players if abs(pos_a[g] - pos_n[g]) >= 3)
        print(f"  players moving >=3 ranks if escort kills are dropped: {movers} "
              f"of {len(players)}")
        print("  -> if a 4.6% axis reorders the board, that is a warning, not a win.")

    # ---- L. leave-one-map-out on the COMPOSITE, not just the delta ----------
    print()
    print("=" * 78)
    print("L. LEAVE-ONE-MAP-OUT on the composite score")
    print("=" * 78)
    for mp in sorted({d["map"] for d in diffs}):
        sample = [d for d in diffs if d["map"] != mp]
        if len(sample) < 200:
            continue
        accs_h = {}
        for name in ("kills", "v6"):
            by_map = defaultdict(list)
            for d in sample:
                by_map[d["map"]].append(d[name])
            means = {m: sum(v) / len(v) for m, v in by_map.items()}
            accs_h[name] = sum(1 for d in sample
                               if ((d[name] - means[d["map"]]) > 0) == (d["won"] == 1)) / len(sample)
        print(f"  without {mp:<20}n={len(sample):4d}  v6 {_pct(accs_h['v6'])}  "
              f"kills {_pct(accs_h['kills'])}  delta {100*(accs_h['v6']-accs_h['kills']):+5.2f}")

    # ---- I. verdict ---------------------------------------------------------
    print()
    print("=" * 78)
    print("I. VERDICT against thresholds set BEFORE the numbers were seen")
    print("=" * 78)
    r_v5 = reliability["KIS v5 (total)"]
    print(f"  {'variant':<22}{'reliability':>12}{'round acc':>11}{'verdict':>26}")
    admitted = []
    for label, key, cand in (("v6 with escort", "KIS v6 (with escort)", "v6"),
                             ("v6 without escort", "KIS v6 (no escort)", "v6-ne")):
        rel = reliability[key]
        lo, hi = reliability_ci[key]
        ok_r = rel >= ACCEPT_RELIABILITY_SB
        ok_a = accs[cand] >= accs["kills"] - ACCEPT_ROUND_TEST_TOLERANCE
        verdict = "ADMITTED" if (ok_r and ok_a) else (
            "rejected: reliability" if not ok_r else "rejected: round test")
        if ok_r and ok_a:
            admitted.append(label)
        print(f"  {label:<22}{rel:>12.3f}{_pct(accs[cand]):>11}{verdict:>26}")
        print(f"  {'':<22}CI [{lo:.2f}, {hi:.2f}]   vs kills {_pct(accs['kills'])}")
    r_v6 = reliability["KIS v6 (no escort)"]
    r_v6_cell = reliability_cell["KIS v6 (no escort)"]
    ci_lo, ci_hi = reliability_ci["KIS v6 (no escort)"]
    ok_rel = r_v6 >= ACCEPT_RELIABILITY_SB
    ok_round = accs["v6-ne"] >= accs["kills"] - ACCEPT_ROUND_TEST_TOLERANCE
    kept = sorted({n for role in weights for n in weights[role]})
    print(f"  1. reliability v6 >= {ACCEPT_RELIABILITY_SB:.2f} .......... "
          f"{r_v6:.3f}  {'PASS' if ok_rel else 'FAIL'}   (v5 is {r_v5:.3f})"
          "   [no-escort variant]")
    print(f"     95% CI [{ci_lo:.3f}, {ci_hi:.3f}] over players — read the interval,")
    print(f"     not the point: at {len(players)} players this statistic is noisy.")
    print("     ^ role-residual control; under the pre-registered (map,side)")
    print(f"       control v6 reads {r_v6_cell:.3f} — see the note in section G.")
    print(f"  2. every kept axis has a CI excluding 0 .. {len(kept)} kept: "
          f"{', '.join(kept) if kept else '(none)'}")
    print(f"  3. round test within {ACCEPT_ROUND_TEST_TOLERANCE:.0%} of kills ... "
          f"{_pct(accs['v6-ne'])} vs {_pct(accs['kills'])}  "
          f"{'PASS' if ok_round else 'FAIL'}")
    print()
    verdict = (f"PROCEED with: {', '.join(admitted)}" if admitted
               else "DO NOT ship — no variant met the thresholds")
    print(f"  => {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
