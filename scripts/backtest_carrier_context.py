#!/usr/bin/env python3
"""Carrier context backtest — the owner's objective-carrier idea, measured.

READ-ONLY. Nothing is written; no formula, cache row or table is touched.

Owner's idea (2026-08-19): "ko nosis objektiv si top tarca, tako kot v Quake ko
imas powerup. Ce kot soigralec pomagas nosilcu — ce ga trejdas, mu zelo pomagas.
Ce delas kile medtem ko on bezi je najbolse kar je mozno. In ne samo kili, tudi
dmg, shots fired/hit se steje pod kritje. Potem pa obrnjena vloga: on kar lavfa z
docsi, zdaj gledamo skozi oci branilca — mi ga moramo ustaviti."

What this script measures, and the traps it is built to avoid:

  THE CONFOUND. A carry ITSELF predicts the round (rounds with a carry: the
  attacker wins ~74%, without: ~40%). So a raw "escort kill wins more" number is
  mostly the situation, not the kill. Every effect here is therefore reported at
  three levels: raw, within carry-rounds only, and additionally at an even man
  count. Only the third number is quotable.

  THE ENDOGENOUS OUTCOME. Escort kills during a carry that ended `secured`
  predict the round at 99.9% — the objective was secured, so the round was won.
  The carry's outcome is NEVER an input; it appears only as a diagnostic.

  ROLE. Attacker and defender have different baselines (~65% / ~41%) and several
  axes point in OPPOSITE directions by role, so every number is within role.
  `rounds.defender_team` is read, never hardcoded (etl_ice: Allies defend).

Sections:
    A  scope + coverage
    B  carry state per kill: escort / stopper / carrier-kill, with 3 controls
    C  distance to the carrier (reconstructed from player_track.path)
    D  defender's side: killed the carrier vs killed anyone else
    E  covering damage near the carrier (share of team work, tempo-controlled)
    F  damage ON the carrier — does "we nearly stopped him" predict anything?
    G  trade for the carrier: killing whoever hurt our carrier
    H  shot_fired coverage bias check (partial table — is it usable at all?)
    I  model: do the carrier axes survive next to the KIS v6 axes?
    J  verdict against thresholds set before the numbers were seen

Usage:
    PGPASSWORD=... venv/bin/python3 scripts/backtest_carrier_context.py
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import sys
from collections import defaultdict

import asyncpg
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_kis_v6 import (  # noqa: E402 - path set above
    CARRIER_TRACK_SQL,
    CARRY_SQL,
    KILLS_SQL,
    REACTION_SQL,
    REVENGE_SQL,
    V5_VERSION,
    Axes,
    CarrierIndex,
    _logit_fit,
    _man_adv,
    _pct,
    _role,
    _side,
    _won,
)

# Pre-registered thresholds (plan, 2026-08-19) — written before the numbers.
ACCEPT_MIN_N = 200            # an axis needs this many kills to be judged at all
ACCEPT_CONTROLLED_PP = 2.0    # effect must survive the even-man control by this
BOOTSTRAP_ROUNDS = 200
TRADE_FOR_CARRIER_MS = 5_000  # avenging the carrier within this counts
UNITS_TO_M = 0.0254

# Distance bands to the carrier. The prototype found the peak at 500-1200u, not
# at point blank — the useful escort clears space around the carrier rather than
# hugging him. These bands exist to test that, not to assume it.
DIST_BANDS = ((0, 500, "<500u (<13m)"),
              (500, 1200, "500-1200u (13-30m)"),
              (1200, 2500, "1200-2500u"),
              (2500, 10 ** 9, ">2500u (>63m)"))

DAMAGE_SQL = """
SELECT hr.round_id AS rid, hr.event_time, hr.attacker_guid, hr.victim_guid, hr.damage
FROM proximity_hit_region hr
JOIN rounds r ON r.id = hr.round_id AND r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
WHERE hr.damage > 0
  -- only rounds that contain a carry: the unrestricted form pulled all 376k
  -- damage rows into memory to use a fraction of them (CodeRabbit)
  AND EXISTS (SELECT 1 FROM proximity_carrier_event ce WHERE ce.round_id = hr.round_id)
"""

SHOTS_SQL = """
SELECT sf.round_id AS rid, count(*) AS shots
FROM proximity_shot_fired sf
JOIN rounds r ON r.id = sf.round_id AND r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
GROUP BY 1
"""


def _dist(a, b) -> float:
    return math.dist(a, b)


def _effect(rows, baseline: float) -> tuple[int, float]:
    if not rows:
        return 0, float("nan")
    return len(rows), (sum(_won(r) for r in rows) / len(rows) - baseline) * 100


def _even(rows):
    """Man-count-neutral subset — the dominance control, applied everywhere."""
    return [r for r in rows if abs(_man_adv(r)) <= 1]


async def main() -> int:  # noqa: PLR0915 - a report, read top to bottom
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")
    kills = await conn.fetch(KILLS_SQL, V5_VERSION)
    carries = await conn.fetch(CARRY_SQL)
    tracks = await conn.fetch(CARRIER_TRACK_SQL)
    damage = await conn.fetch(DAMAGE_SQL)
    shots = await conn.fetch(SHOTS_SQL)
    revenge_rows = await conn.fetch(REVENGE_SQL)
    reaction_rows = await conn.fetch(REACTION_SQL)
    await conn.close()

    kills = [k for k in kills if k["attacker_team"]]
    idx = CarrierIndex(carries, tracks)
    axes = Axes(kills)
    axes.add_revenge(revenge_rows)
    axes.add_reaction(reaction_rows)

    baselines = {}
    for role in ("ATT", "DEF"):
        sub = [k for k in kills if _role(k) == role]
        baselines[role] = sum(_won(k) for k in sub) / len(sub)

    # ---- A. scope -----------------------------------------------------------
    print("=" * 78)
    print("A. SCOPE  (valid, non-bot rounds; winner and defender known)")
    print("=" * 78)
    carry_rounds = set(idx.by_round)
    kill_rounds = {k["rid"] for k in kills}
    print(f"  kills .................. {len(kills)}   rounds {len(kill_rounds)}")
    print(f"  carries ................ {len(carries)}   rounds with a carry "
          f"{len(carry_rounds & kill_rounds)}")
    print(f"  carriers with a path ... {len(idx.paths)}")
    print(f"  damage events .......... {len(damage)}")
    print(f"  rounds with shot data .. {len(shots)} of {len(kill_rounds)}")
    for role in ("ATT", "DEF"):
        print(f"  baseline {role} ............ {_pct(baselines[role])}")

    outcomes = defaultdict(int)
    for c in carries:
        outcomes[c["outcome"]] += 1
    print("  carry outcomes ......... " + ", ".join(
        f"{k} {v}" for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1])))

    # ---- B. carry state per kill -------------------------------------------
    print()
    print("=" * 78)
    print("B. CARRY STATE PER KILL  (three control levels — only the third is quotable)")
    print("=" * 78)
    # THE CONFOUND, measured first: does a carry alone predict the round?
    first_of_round = {}
    for k in kills:
        first_of_round.setdefault(k["rid"], k)
    with_carry = [1 if k["winner_team"] != k["defender_team"] else 0
                  for rid, k in first_of_round.items() if rid in carry_rounds]
    without = [1 if k["winner_team"] != k["defender_team"] else 0
               for rid, k in first_of_round.items() if rid not in carry_rounds]
    print(f"  rounds WITH a carry: {len(with_carry):4d}  attacker wins "
          f"{100*sum(with_carry)/max(len(with_carry),1):.1f}%")
    print(f"  rounds without ....: {len(without):4d}  attacker wins "
          f"{100*sum(without)/max(len(without),1):.1f}%")
    print("  -> most of any raw 'escort kills win' number is THIS, not the kill.")

    cats: dict[str, list] = defaultdict(list)
    for k in kills:
        # Resolve OUR carry and THEIRS separately. active() without a team
        # returns whichever interval comes first in query order, so on a map
        # where both sides carry at once the classification was decided by row
        # order rather than by who was carrying (CodeRabbit). Re-measured after
        # the fix: every §11 figure is unchanged — the bug was latent here.
        mine = idx.active(k["rid"], k["kill_time"], _side(k))
        theirs = idx.active(k["rid"], k["kill_time"],
                            "ALLIES" if _side(k) == "AXIS" else "AXIS")
        if mine is None and theirs is None:
            cats["no carry active"].append(k)
        elif theirs is not None and k["victim_guid"] == theirs["carrier_guid"]:
            cats["killed the carrier"].append(k)
        elif mine is not None and k["killer_guid"] == mine["carrier_guid"]:
            cats["the carrier's own kill"].append(k)
        elif mine is not None:
            cats["escort kill (we carry)"].append(k)
        else:
            cats["stopper kill (they carry)"].append(k)

    # control 2: within carry-rounds only, same role, outside any own carry window
    ref = {}
    for role in ("ATT", "DEF"):
        pool = [k for k in kills if _role(k) == role and k["rid"] in carry_rounds
                and idx.active(k["rid"], k["kill_time"], _side(k)) is None]
        ref[role] = (sum(_won(k) for k in pool) / len(pool), len(pool)) if pool else (float("nan"), 0)
        pool_even = _even(pool)
        ref[role + "_even"] = ((sum(_won(k) for k in pool_even) / len(pool_even), len(pool_even))
                               if pool_even else (float("nan"), 0))
    print("\n  reference (same role, carry round, OUTSIDE our carry window):")
    for role in ("ATT", "DEF"):
        print(f"    {role}: {_pct(ref[role][0])} (n={ref[role][1]})   "
              f"even man count {_pct(ref[role + '_even'][0])} (n={ref[role + '_even'][1]})")

    print(f"\n  {'category':<26}{'n':>6}{'share':>7}   raw pp / in-carry pp / even pp")
    for name in ("no carry active", "escort kill (we carry)", "stopper kill (they carry)",
                 "killed the carrier", "the carrier's own kill"):
        v = cats[name]
        line = []
        for role in ("ATT", "DEF"):
            sel = [k for k in v if _role(k) == role]
            if len(sel) < 50:
                line.append(f"{role} n={len(sel)}")
                continue
            n_raw, pp_raw = _effect(sel, baselines[role])
            _, pp_in = _effect(sel, ref[role][0])
            sel_even = _even(sel)
            _, pp_even = _effect(sel_even, ref[role + "_even"][0])
            line.append(f"{role} {pp_raw:+5.1f} / {pp_in:+5.1f} / {pp_even:+5.1f} (n={n_raw})")
        print(f"  {name:<26}{len(v):>6}{100.0*len(v)/len(kills):>6.1f}%   " + "   ".join(line))

    # diagnostic only — NEVER an input
    print("\n  DIAGNOSTIC (never an input): escort kills by how that carry ended")
    for oc in ("secured", "dropped", "killed"):
        sel = []
        for k in cats["escort kill (we carry)"]:
            car = idx.active(k["rid"], k["kill_time"], _side(k))
            if car is not None and car["outcome"] == oc:
                sel.append(k)
        if len(sel) >= 50:
            print(f"    carry -> {oc:<9} n={len(sel):4d}  wins "
                  f"{100*sum(_won(k) for k in sel)/len(sel):.1f}%")
    print("    ^ 'secured' is ~100% by construction: the objective was secured, so")
    print("      the round was won. This is why carry OUTCOME never enters a score.")

    # ---- C. distance to the carrier ----------------------------------------
    print()
    print("=" * 78)
    print("C. DISTANCE TO THE CARRIER  (owner: 'ce si v proximity mu pomagas')")
    print("=" * 78)
    escort_d: list[tuple] = []
    missing = 0
    for k in cats["escort kill (we carry)"]:
        car = idx.active(k["rid"], k["kill_time"], _side(k))
        if car is None or k["kill_distance"] is None:
            continue
        pos = idx.position(k["rid"], car["carrier_guid"], k["kill_time"])
        if pos is None or None in (k["killer_x"], k["killer_y"], k["killer_z"]):
            missing += 1
            continue
        escort_d.append((k, _dist((k["killer_x"], k["killer_y"], k["killer_z"]), pos), car))
    total_escort = len(cats["escort kill (we carry)"])
    print(f"  escort kills with a known carrier distance: {len(escort_d)} of "
          f"{total_escort} ({100.0*len(escort_d)/max(total_escort,1):.0f}%)")
    if escort_d:
        ds = sorted(d for _, d, _ in escort_d)
        print(f"  distance: p25 {ds[len(ds)//4]:.0f}u  median {ds[len(ds)//2]:.0f}u  "
              f"p75 {ds[3*len(ds)//4]:.0f}u  ({ds[len(ds)//2]*UNITS_TO_M:.0f} m median)")
        print(f"\n  {'band':<22}{'n':>6}{'wins':>8}{'vs ref':>9}{'even n':>8}{'even':>8}{'vs ref':>9}")
        for lo, hi, nm in DIST_BANDS:
            sel = [e[0] for e in escort_d if lo <= e[1] < hi]
            if len(sel) < 40:
                print(f"  {nm:<22}{len(sel):>6}   (too few)")
                continue
            w = sum(_won(k) for k in sel) / len(sel)
            sel_even = _even(sel)
            we = (sum(_won(k) for k in sel_even) / len(sel_even)) if len(sel_even) >= 40 else float("nan")
            print(f"  {nm:<22}{len(sel):>6}{_pct(w):>8}{(w-ref['ATT'][0])*100:>+9.1f}"
                  f"{len(sel_even):>8}{_pct(we):>8}{(we-ref['ATT_even'][0])*100:>+9.1f}")
        # is the 37% without a path systematically different?
        with_path = {id(e[0]) for e in escort_d}
        no_path = [k for k in cats["escort kill (we carry)"] if id(k) not in with_path]
        if len(no_path) >= 50:
            print(f"\n  BIAS CHECK — escort kills WITHOUT a carrier path: n={len(no_path)}, "
                  f"wins {100*sum(_won(k) for k in no_path)/len(no_path):.1f}% "
                  f"vs {100*sum(_won(e[0]) for e in escort_d)/len(escort_d):.1f}% with a path")

    # ---- D. the defender's side --------------------------------------------
    print()
    print("=" * 78)
    print("D. DEFENDER: stopping the carrier vs killing anyone else")
    print("=" * 78)
    for name in ("killed the carrier", "stopper kill (they carry)"):
        sel = [k for k in cats[name] if _role(k) == "DEF"]
        sel_even = _even(sel)
        if len(sel) < 50:
            continue
        print(f"  {name:<28} n={len(sel):5d}  wins {_pct(sum(_won(k) for k in sel)/len(sel))}"
              f"  vs ref {(sum(_won(k) for k in sel)/len(sel) - ref['DEF'][0])*100:+5.1f} pp"
              f"   even: {(sum(_won(k) for k in sel_even)/len(sel_even) - ref['DEF_even'][0])*100:+5.1f} pp"
              f" (n={len(sel_even)})")
    print("  -> under the owner's 'bonuses only' rule a negative axis becomes x1.00;")
    print("     it is reported so the UI can still SAY it, without scoring it.")

    # ---- E/F/G. damage-side measurements -----------------------------------
    print()
    print("=" * 78)
    print("E/F/G. DAMAGE: covering fire, damage on the carrier, trading for him")
    print("=" * 78)
    dmg_by_round = defaultdict(list)
    for d in damage:
        dmg_by_round[d["rid"]].append(d)
    for rid in dmg_by_round:
        dmg_by_round[rid].sort(key=lambda d: d["event_time"])

    covering, on_carrier = 0, 0
    cover_dmg, carrier_dmg = 0, 0
    carrier_hitters: dict[tuple[int, str], list[tuple[int, str]]] = defaultdict(list)
    for rid, events in dmg_by_round.items():
        for d in events:
            car = idx.active(rid, d["event_time"])
            if car is None:
                continue
            if d["victim_guid"] == car["carrier_guid"]:
                on_carrier += 1
                carrier_dmg += d["damage"] or 0
                carrier_hitters[(rid, car["carrier_guid"])].append(
                    (d["event_time"], d["attacker_guid"]))
            else:
                covering += 1
                cover_dmg += d["damage"] or 0
    print(f"  E. damage events inside a carry window ... {covering} "
          f"({cover_dmg} damage)")
    print(f"  F. damage landed ON a carrier ........... {on_carrier} "
          f"({carrier_dmg} damage, {len(carrier_hitters)} carries hit)")

    # F: does hurting a carrier who then survives predict anything?
    hurt_survived, hurt_died = [], []
    for c in carries:
        key = (c["rid"], c["carrier_guid"])
        hits = [h for h in carrier_hitters.get(key, ())
                if c["pickup_time"] <= h[0] <= c["drop_time"]]
        if not hits:
            continue
        (hurt_died if c["outcome"] == "killed" else hurt_survived).append(c)
    print(f"     carries that took damage: {len(hurt_died) + len(hurt_survived)}"
          f"  -> carrier killed {len(hurt_died)}, survived the run {len(hurt_survived)}")
    print("     (a 'we nearly stopped him' axis needs the survived group to differ;")
    print("      it is scored only if section I keeps it.)")

    # G: trade for the carrier — the killer killed someone who had just hurt our carrier
    trade_for_carrier = []
    for k in kills:
        car = idx.active(k["rid"], k["kill_time"], _side(k))
        if car is None or k["killer_guid"] == car["carrier_guid"]:
            continue
        hits = carrier_hitters.get((k["rid"], car["carrier_guid"]), ())
        if any(h[1] == k["victim_guid"] and 0 <= k["kill_time"] - h[0] <= TRADE_FOR_CARRIER_MS
               for h in hits):
            trade_for_carrier.append(k)
    sel = [k for k in trade_for_carrier if _role(k) == "ATT"]
    if len(sel) >= 40:
        sel_even = _even(sel)
        print(f"  G. killed someone who hurt our carrier within "
              f"{TRADE_FOR_CARRIER_MS//1000}s: n={len(sel)}")
        print(f"     wins {_pct(sum(_won(k) for k in sel)/len(sel))}  "
              f"vs ref {(sum(_won(k) for k in sel)/len(sel) - ref['ATT'][0])*100:+5.1f} pp"
              + (f"   even {(sum(_won(k) for k in sel_even)/len(sel_even) - ref['ATT_even'][0])*100:+5.1f} pp"
                 f" (n={len(sel_even)})" if len(sel_even) >= 40 else ""))
    else:
        print(f"  G. trade-for-carrier kills: only {len(sel)} — below the "
              f"{ACCEPT_MIN_N} threshold, not judged")

    # ---- H. shots coverage bias --------------------------------------------
    print()
    print("=" * 78)
    print("H. shot_fired COVERAGE — is the partial table usable?")
    print("=" * 78)
    shot_rounds = {s["rid"] for s in shots}
    covered = [k for k in kills if k["rid"] in shot_rounds]
    uncovered = [k for k in kills if k["rid"] not in shot_rounds]
    print(f"  kills in rounds WITH shots: {len(covered)}   without: {len(uncovered)}")
    if covered and uncovered:
        by_map_cov = defaultdict(int)
        by_map_all = defaultdict(int)
        for k in kills:
            by_map_all[k["rmap"]] += 1
            if k["rid"] in shot_rounds:
                by_map_cov[k["rmap"]] += 1
        skew = sorted((by_map_cov[m] / by_map_all[m], m, by_map_all[m])
                       for m in by_map_all if by_map_all[m] >= 500)
        print("  coverage by map (>=500 kills):")
        for frac, m, n in skew:
            print(f"    {m:<20}{100*frac:5.1f}%  (n={n})")
        print("  -> if coverage is uneven per map, shot volume is NOT comparable")
        print("     across players; it stays descriptive until that is fixed.")

    # ---- I. model ----------------------------------------------------------
    print()
    print("=" * 78)
    print("I. MODEL — do the carrier axes survive next to the KIS v6 axes?")
    print("=" * 78)
    dist_of = {}
    for k, d, _c in escort_d:
        dist_of[k["id"]] = d

    def escort_any(k) -> float:
        """Our team is carrying, and this kill is neither on nor by the carrier."""
        car = idx.active(k["rid"], k["kill_time"], _side(k))
        if car is None:
            return 0.0
        cg = car["carrier_guid"]
        return 0.0 if (k["victim_guid"] == cg or k["killer_guid"] == cg) else 1.0

    def escort_band(k) -> float:
        d = dist_of.get(k["id"])
        return 1.0 if (d is not None and 500 <= d < 1200) else 0.0

    def stop_kill(k) -> float:
        car = idx.active(k["rid"], k["kill_time"])
        return 1.0 if (car is not None and k["victim_guid"] == car["carrier_guid"]) else 0.0

    def trade_carrier(k) -> float:
        return 1.0 if k["id"] in {x["id"] for x in trade_for_carrier} else 0.0

    feats = [
        ("wave_z", axes.wave_z),
        ("stood", axes.stood),
        ("isolation", axes.isolation),
        ("objective", axes.objective),
        ("crossfire", axes.crossfire),
        ("clean_pick", axes.clean_pick),
        ("escort_any", escort_any),
        ("escort_band", escort_band),
        ("stop_kill", stop_kill),
        ("trade_carrier", trade_carrier),
        ("man_adv", _man_adv),
    ]
    kept: dict[str, dict[str, float]] = {"ATT": {}, "DEF": {}}
    for role in ("ATT", "DEF"):
        sub = [k for k in kills if _role(k) == role]
        X = np.column_stack([np.ones(len(sub))] + [[f(k) for k in sub] for _, f in feats])
        y = np.array([_won(k) for k in sub])
        rids = np.array([k["rid"] for k in sub])
        beta = _logit_fit(X, y)
        uniq = sorted(set(rids.tolist()))
        by_rid = {u: np.where(rids == u)[0] for u in uniq}
        rng = random.Random(20260819)  # noqa: S311 - statistical control, not crypto
        boots = []
        for _ in range(BOOTSTRAP_ROUNDS):
            ii = np.concatenate([by_rid[uniq[rng.randrange(len(uniq))]] for _ in range(len(uniq))])
            try:
                boots.append(_logit_fit(X[ii], y[ii], iters=25))
            except np.linalg.LinAlgError:
                continue
        if not boots:
            print(f"\n  --- {role}: every bootstrap fit failed — no CIs to report")
            continue
        B = np.array(boots)
        print(f"\n  --- {role}  (n={len(sub)} kills, {len(uniq)} rounds, "
              f"baseline {_pct(y.mean())})")
        print(f"  {'axis':<15}{'coef':>8}{'95% CI':>22}{'odds':>7}  n_fires  verdict")
        for i, (name, fn) in enumerate([("intercept", None)] + feats):
            lo, hi = np.percentile(B[:, i], [2.5, 97.5])
            # count how often the axis actually FIRES. Continuous axes (wave_z,
            # man_adv) can be negative, so summing them is not a count — an
            # earlier version did exactly that and knocked out wave_z with a
            # "-22 kills" verdict. Count non-zero values instead.
            continuous = name in ("wave_z", "man_adv", "intercept")
            fires = len(sub) if continuous else int(sum(1 for k in sub if fn(k)))
            if name in ("intercept", "man_adv"):
                mark = "(control)" if name == "man_adv" else ""
            elif fires < ACCEPT_MIN_N:
                mark = f"-> 1.0 (only {fires} kills)"
            elif lo <= 0.0 <= hi:
                mark = "-> 1.0 (CI covers 0)"
            elif beta[i] <= 0:
                mark = "-> 1.0 (negative; owner: bonuses only)"
            else:
                mark = "KEEP"
                kept[role][name] = round(float(math.exp(beta[i])), 2)
            print(f"  {name:<15}{beta[i]:>8.3f}  [{lo:>7.3f},{hi:>7.3f}]"
                  f"{math.exp(beta[i]):>7.2f}{fires:>9}  {mark}")

    # ---- J. verdict --------------------------------------------------------
    print()
    print("=" * 78)
    print("J. VERDICT against thresholds set before the numbers were seen")
    print("=" * 78)
    carrier_axes = ("escort_any", "escort_band", "stop_kill", "trade_carrier")
    survivors = {r: [a for a in carrier_axes if a in kept[r]] for r in ("ATT", "DEF")}
    for role in ("ATT", "DEF"):
        got = survivors[role]
        print(f"  {role}: {len(got)} carrier axes survive -> "
              f"{', '.join(f'{a} x{kept[role][a]}' for a in got) if got else '(none)'}")
    total = sum(len(v) for v in survivors.values())
    print()
    if total:
        print(f"  => {total} carrier axis/axes earned a place in KIS. The non-kill parts")
        print("     (covering damage, damage on the carrier, shots) belong in PWC as a")
        print("     share component — that needs its own backtest before pwc-v3.")
    else:
        print("  => no carrier axis survived the model; the raw effect was the situation")
        print("     (a carry predicts the round), not the kill. Report it, do not score it.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
