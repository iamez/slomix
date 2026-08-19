#!/usr/bin/env python3
"""What can our numbers actually measure? — the foundations under KIS/PWC.

READ-ONLY. No formula, cache row or table is touched.

WHY THIS EXISTS. The KIS v6 acceptance run found that one axis (`escort`) makes
the score BETTER at describing the round (71.00% vs 69.75% winner accuracy) and
WORSE at describing the player (reliability 0.755 -> 0.151). That is not a
detail: it means we were measuring two different things with one number. Before
any formula ships, five questions need answers.

  A  THE INSTRUMENT. Split-half reliability on 15 players gives intervals like
     [-3.61, 0.75] — a guess with three decimals. Replaced here by a variance
     decomposition: observed spread of player means minus the sampling noise
     that must be in it. Same idea, far less noise, and it yields a detectable-
     difference threshold as a by-product.

  B  THE CEILING. We only ever compared candidates to each other. Nobody asked
     how much ANY kill-level score could be worth. Fit the best model the sample
     allows, evaluate with cross-validation GROUPED BY ROUND, and compare with
     plain kill counting. The gap is the entire prize for context work.

  C  THE MATRIX. Every axis gets two coordinates: is it stable within a player,
     and does it predict the round? Stable+predictive belongs in a PLAYER score;
     unstable+predictive belongs in a ROUND score. Architecture from measurement
     instead of argument.

  D  WOWY. The only honest test of a player number: does the team win more when
     this player is in it, adjusted for who else is in it (ridge APM)? Then —
     does KIS track that better than plain kill count does?

  E  THE FLOOR. What effect size is even detectable at 638 rounds / 15 players.
     Written down so the next idea gets checked against it before we spend a
     night on it.

Usage:
    PGPASSWORD=... venv/bin/python3 scripts/backtest_metric_foundations.py
"""
from __future__ import annotations

import asyncio
import math
import os
import random
import statistics
import sys
from collections import defaultdict

import asyncpg
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backtest_kis_v6 import (  # noqa: E402 - path set above
    CARRY_SQL,
    KILLS_SQL,
    REACTION_SQL,
    REVENGE_SQL,
    V5_VERSION,
    Axes,
    _logit_fit,
    _man_adv,
    _pct,
    _role,
    _side,
    _won,
)

MIN_KILLS_FOR_PLAYER = 200
CV_FOLDS = 5
BOOTSTRAP = 300
PERMUTATIONS = 20
RIDGE_LAMBDA = 25.0        # APM-style shrink; 36 players over ~2900 rounds
MIN_ROUNDS_FOR_WOWY = 100

# Rosters for WOWY — one row per (round, player, team). round_number IN (1,2)
# because R0 rows are the importer's summary copy and are NOT a data source
# (contract in docs/CLAUDE.md).
ROSTER_SQL = """
SELECT pcs.round_id AS rid, pcs.player_guid AS guid, pcs.team AS team,
       r.winner_team, r.map_name
FROM player_comprehensive_stats pcs
JOIN rounds r ON r.id = pcs.round_id
WHERE r.is_valid AND NOT COALESCE(r.is_bot_round, FALSE)
  AND r.winner_team IN (1, 2) AND r.defender_team IN (1, 2)
  AND pcs.round_number IN (1, 2)
  AND pcs.time_played_seconds > 0
  AND pcs.player_guid NOT LIKE 'OMNIBOT%'
ORDER BY pcs.round_id, pcs.player_guid
"""


def _reliability_vc(groups: list[list[float]]) -> tuple[float, float, float]:
    """Reliability of player means by variance decomposition.

    groups[i] = one player's per-kill values.

        observed spread of the means already CONTAINS sampling noise:
            var(means) = between + mean(within_i / n_i)
        so:
            between   = var(means) - mean(within_i / n_i)
            reliability = between / var(means)

    Returns (reliability, between_sd, typical_standard_error). Reliability is
    clamped to [0, 1]: a negative estimate means "no measurable between-player
    signal", not "anti-signal" — that distinction cost us a whole reading of the
    escort axis.
    """
    means, noises = [], []
    for vals in groups:
        n = len(vals)
        if n < 2:
            continue
        means.append(statistics.mean(vals))
        noises.append(statistics.variance(vals) / n)
    if len(means) < 3:
        return float("nan"), float("nan"), float("nan")
    observed = statistics.variance(means)
    noise = statistics.mean(noises)
    between = max(observed - noise, 0.0)
    rel = between / observed if observed > 0 else 0.0
    return min(max(rel, 0.0), 1.0), math.sqrt(between), math.sqrt(noise)


def _grouped_folds(round_ids: np.ndarray, folds: int, seed: int = 7):
    """Fold assignment by ROUND — kills of one round never straddle the split."""
    uniq = sorted(set(round_ids.tolist()))
    rng = random.Random(seed)  # noqa: S311 - fold assignment, not crypto
    rng.shuffle(uniq)
    of = {r: i % folds for i, r in enumerate(uniq)}
    return np.array([of[r] for r in round_ids])


def _round_accuracy(rows, scores: dict, side_of, won_of, map_of) -> float:
    """Map-centred paired sign test — the same yardstick used all day."""
    per = defaultdict(lambda: defaultdict(float))
    won, rmap = {}, {}
    for r in rows:
        per[r["rid"]][side_of(r)] += scores[r["id"]]
        won[(r["rid"], side_of(r))] = won_of(r)
        rmap[r["rid"]] = map_of(r)
    diffs = []
    for rid, sides in per.items():
        if "AXIS" not in sides or "ALLIES" not in sides:
            continue
        diffs.append((rmap[rid], sides["AXIS"] - sides["ALLIES"], won[(rid, "AXIS")]))
    if not diffs:
        return float("nan")
    by_map = defaultdict(list)
    for m, d, _w in diffs:
        by_map[m].append(d)
    means = {m: sum(v) / len(v) for m, v in by_map.items()}
    return sum(1 for m, d, w in diffs if ((d - means[m]) > 0) == (w == 1)) / len(diffs)


async def main() -> int:  # noqa: PLR0915 - a report, read top to bottom
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")
    kills = await conn.fetch(KILLS_SQL, V5_VERSION)
    revenge_rows = await conn.fetch(REVENGE_SQL)
    reaction_rows = await conn.fetch(REACTION_SQL)
    carry_rows = await conn.fetch(CARRY_SQL)
    roster = await conn.fetch(ROSTER_SQL)
    await conn.close()

    kills = [k for k in kills if k["attacker_team"]]
    axes = Axes(kills)
    axes.add_revenge(revenge_rows)
    axes.add_reaction(reaction_rows)
    axes.add_carries(carry_rows)

    by_player = defaultdict(list)
    for k in kills:
        by_player[k["killer_guid"]].append(k)
    players = [(g, v) for g, v in by_player.items() if len(v) >= MIN_KILLS_FOR_PLAYER]

    AXES = {
        "wave_z": axes.wave_z,
        "stood": axes.stood,
        "escort": axes.escort,
        "isolation": axes.isolation,
        "objective": axes.objective,
        "crossfire": axes.crossfire,
        "clean_pick": axes.clean_pick,
        "revenge": axes.revenge,
        "gibbed": axes.gibbed,
        "revived": axes.revived,
    }

    # ---- A. the instrument --------------------------------------------------
    print("=" * 78)
    print("A. THE INSTRUMENT — reliability by variance decomposition")
    print("=" * 78)
    print(f"  players with >= {MIN_KILLS_FOR_PLAYER} kills: {len(players)}   "
          f"kills {sum(len(v) for _, v in players)}   rounds {len({k['rid'] for k in kills})}")
    print("  residual = value minus its (map, side) cell mean. That cell IS the")
    print("  role here (Axis defends on every map but etl_ice), so neither the")
    print("  side's spawn clock nor the role can fake stability.")

    def residualiser(fn):
        """Centre each value on its (map, side) cell.

        The cell subtraction ALREADY removes the role: every (map, side) cell in
        this database belongs to exactly one role (Axis defends everywhere but
        etl_ice). An earlier version subtracted the role mean as well, which
        only added a per-role constant back in — measured effect on the
        reliabilities: wave_z 0.000, escort 0.000, clean_pick -0.001,
        stood +0.008, objective -0.013, isolation +0.053. Real but immaterial;
        removed for correctness of the description, not to change a verdict.
        """
        cell = defaultdict(list)
        for k in kills:
            cell[(k["rmap"], _side(k))].append(fn(k))
        cm = {a: sum(b) / len(b) for a, b in cell.items()}
        return lambda k: fn(k) - cm[(k["rmap"], _side(k))]

    print()
    print(f"  {'axis':<14}{'reliability':>12}{'95% CI':>18}{'between sd':>12}"
          f"{'noise sd':>10}{'min detectable':>16}")
    reliab: dict[str, float] = {}
    for name, fn in AXES.items():
        res = residualiser(fn)
        groups = [[res(k) for k in v] for _, v in players]
        rel, bsd, nsd = _reliability_vc(groups)
        reliab[name] = rel
        # bootstrap over players AND rounds: resample rounds, then rebuild
        by_round = defaultdict(list)
        for _g, v in players:
            for k in v:
                by_round[k["rid"]].append((k["killer_guid"], res(k)))
        uniq_r = sorted(by_round)
        rng = random.Random(11)  # noqa: S311 - resampling, not crypto
        boots = []
        for _ in range(BOOTSTRAP):
            picked = defaultdict(list)
            for _ in range(len(uniq_r)):
                for g, val in by_round[uniq_r[rng.randrange(len(uniq_r))]]:
                    picked[g].append(val)
            gs = [vv for vv in picked.values() if len(vv) >= 30]
            if len(gs) >= 5:
                boots.append(_reliability_vc(gs)[0])
        lo, hi = (float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))) \
            if boots else (float("nan"), float("nan"))
        # smallest per-kill mean gap two players can be told apart by (p<0.05)
        mdd = 2.77 * nsd if not math.isnan(nsd) else float("nan")
        print(f"  {name:<14}{rel:>12.3f}   [{lo:>5.2f},{hi:>5.2f}]{bsd:>12.3f}"
              f"{nsd:>10.3f}{mdd:>16.3f}")
    print("  'min detectable' = the per-kill mean difference two players must")
    print("  have before we may claim they differ (2.77 x the noise sd).")

    # ---- B. the ceiling -----------------------------------------------------
    print()
    print("=" * 78)
    print("B. THE CEILING — how much is ANY kill-derived score worth?")
    print("=" * 78)
    print("  Evaluated at ROUND level: aggregate each side's kills into features,")
    print("  take the AXIS-ALLIES difference, add map dummies, and predict the")
    print("  winner with k-fold CV over rounds. A per-kill log-odds sum cannot be")
    print("  used here — its intercept and role terms turn the team sum into a")
    print("  kill count with extra steps (that is exactly what the first version")
    print("  of this section did, and it scored below the permutation null).")
    feats = list(AXES.items()) + [("man_adv", _man_adv)]
    maps = sorted({k["rmap"] for k in kills})
    map_idx = {m: i for i, m in enumerate(maps)}

    per_side: dict[tuple[int, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    round_info: dict[int, dict] = {}
    for k in kills:
        cell = per_side[(k["rid"], _side(k))]
        cell["kills"] += 1.0
        cell["v5"] += float(k["total_impact"])
        for name, fn in feats:
            cell[name] += fn(k)
        round_info[k["rid"]] = {"map": k["rmap"], "won_axis": None}
    for k in kills:
        if _side(k) == "AXIS":
            round_info[k["rid"]]["won_axis"] = _won(k)

    rounds_ok = [rid for rid in round_info
                 if (rid, "AXIS") in per_side and (rid, "ALLIES") in per_side
                 and round_info[rid]["won_axis"] is not None]
    feat_names = ["kills", "v5"] + [n for n, _ in feats]
    Xr, yr, mr = [], [], []
    for rid in sorted(rounds_ok):
        a, b = per_side[(rid, "AXIS")], per_side[(rid, "ALLIES")]
        Xr.append([a[n] - b[n] for n in feat_names])
        yr.append(round_info[rid]["won_axis"])
        mr.append(map_idx[round_info[rid]["map"]])
    Xr = np.array(Xr)
    yr = np.array(yr, dtype=float)
    dummies = np.column_stack([(np.array(mr) == i).astype(float)
                               for i in range(len(maps) - 1)])
    n_paired_rounds = len(yr)   # captured HERE: section C rebinds `yr` to the
    # kill-level outcome array, so reading len(yr) in section E would report
    # 20,252 "rounds". Same shape as every other bug today: the name stopped
    # pointing at the set I meant.
    print(f"  rounds usable .................. {n_paired_rounds}   "
          f"features {len(feat_names)}")

    def cv_accuracy(cols, y=yr, seed=7):
        """k-fold accuracy over ROUNDS for a model built from `cols`."""
        X = np.column_stack([np.ones(len(y))] + [Xr[:, feat_names.index(c)] for c in cols]
                            + [dummies])
        order = list(range(len(y)))
        random.Random(seed).shuffle(order)  # noqa: S311 - fold assignment
        fold = {r: i % CV_FOLDS for i, r in enumerate(order)}
        folds = np.array([fold[i] for i in range(len(y))])
        hits = 0
        for f in range(CV_FOLDS):
            tr, te = folds != f, folds == f
            beta = _logit_fit(X[tr], y[tr])
            pred = (X[te] @ beta) > 0
            hits += int(np.sum(pred == (y[te] > 0.5)))
        return hits / len(y)

    models = {
        "kill count only": ["kills"],
        "KIS v5 sum": ["v5"] if "v5" in feat_names else ["kills"],
        "wave + stood (player axes)": ["wave_z", "stood"],
        "every axis (the CEILING)": feat_names,
    }
    accs_b = {}
    for label, cols in models.items():
        cols = [c for c in cols if c in feat_names]
        accs_b[label] = cv_accuracy(cols)
        print(f"  {label:<30}{_pct(accs_b[label])}")
    rng = random.Random(3)  # noqa: S311 - permutation null, not crypto
    perms = [cv_accuracy(feat_names, y=np.array(rng.sample(list(yr), len(yr))), seed=100 + i)
             for i in range(PERMUTATIONS)]
    print(f"  {'permutation null':<30}{_pct(statistics.mean(perms))}  "
          f"(sd {100*statistics.stdev(perms):.2f} pp, {PERMUTATIONS} runs)")
    headroom = accs_b["every axis (the CEILING)"] - accs_b["kill count only"]
    print(f"\n  => the ENTIRE prize for context work is {100*headroom:+.2f} pp")
    print("     (every kill-derived feature we have, minus counting kills)")

    # ---- C. the matrix ------------------------------------------------------
    print()
    print("=" * 78)
    print("C. THE MATRIX — player property or round property?")
    print("=" * 78)
    print("  round-predictiveness = |coef| in the role-stratified model (section E")
    print("  of backtest_kis_v6 has the CIs); stability = section A above.")
    coef_abs: dict[str, float] = {}
    for role in ("ATT", "DEF"):
        sub = [k for k in kills if _role(k) == role]
        Xr = np.column_stack([np.ones(len(sub))] + [[fn(k) for k in sub] for _, fn in feats])
        yr = np.array([_won(k) for k in sub])
        b = _logit_fit(Xr, yr)
        for i, (name, _fn) in enumerate(feats):
            coef_abs[name] = max(coef_abs.get(name, 0.0), abs(b[i + 1]))
    print(f"\n  {'axis':<14}{'stability':>11}{'|coef|':>9}   verdict")
    for name in AXES:
        rel, c = reliab[name], coef_abs.get(name, 0.0)
        if c < 0.05:
            v = "drop (predicts nothing)"
        elif rel >= 0.5:
            v = "PLAYER score (KIS)"
        else:
            v = "ROUND score (PWC)"
        print(f"  {name:<14}{rel:>11.3f}{c:>9.3f}   {v}")

    # ---- D. WOWY ------------------------------------------------------------
    print()
    print("=" * 78)
    print("D. WOWY — does the team win more with this player in it?")
    print("=" * 78)
    by_round_roster = defaultdict(lambda: defaultdict(list))
    winner, rmap_r = {}, {}
    for r in roster:
        by_round_roster[r["rid"]][str(r["team"])].append(r["guid"])
        winner[r["rid"]] = r["winner_team"]
        rmap_r[r["rid"]] = r["map_name"]
    guids = sorted({r["guid"] for r in roster})
    gidx = {g: i for i, g in enumerate(guids)}
    rows_x, rows_y = [], []
    for rid, teams in by_round_roster.items():
        if len(teams) != 2:
            continue
        (ta, la), (tb, lb) = sorted(teams.items())
        x = np.zeros(len(guids))
        for g in la:
            x[gidx[g]] += 1.0
        for g in lb:
            x[gidx[g]] -= 1.0
        rows_x.append(x)
        rows_y.append(1.0 if str(winner[rid]) == ta else 0.0)
    X = np.array(rows_x)
    y = np.array(rows_y)
    print(f"  rounds usable: {len(y)}   players: {len(guids)}")
    beta = np.linalg.solve(X.T @ X + RIDGE_LAMBDA * np.eye(X.shape[1]), X.T @ (y - 0.5))
    played = defaultdict(int)
    for r in roster:
        played[r["guid"]] += 1
    apm = {g: float(beta[gidx[g]]) for g in guids if played[g] >= MIN_ROUNDS_FOR_WOWY}
    # raw WOWY as the second path (rule: measure the important number twice)
    raw = {}
    for g in apm:
        with_g = [1.0 if (str(winner[rid]) == t) else 0.0
                  for rid, teams in by_round_roster.items()
                  for t, lst in teams.items() if g in lst]
        if len(with_g) >= MIN_ROUNDS_FOR_WOWY:
            raw[g] = sum(with_g) / len(with_g)
    print(f"  players with >= {MIN_ROUNDS_FOR_WOWY} rounds: {len(apm)}")
    print(f"\n  {'player':<12}{'rounds':>8}{'ridge APM':>11}{'raw win%':>10}"
          f"{'KIS/kill':>10}{'kills/rnd':>10}")
    # player_comprehensive_stats stores the SHORT guid (8 chars) while
    # storytelling_kill_impact stores the full 32-char one — joining them
    # without this fold silently produced an all-NaN column.
    kis_mean, kpr = {}, {}
    for g, v in by_player.items():
        g8 = g[:8].upper()
        kis_mean[g8] = sum(float(k["total_impact"]) for k in v) / len(v)
        kpr[g8] = len(v) / max(len({k["rid"] for k in v}), 1)
    shown = sorted(apm, key=lambda g: -apm[g])
    for g in shown:
        print(f"  {g[:8]:<12}{played[g]:>8}{apm[g]:>11.4f}{100*raw.get(g, float('nan')):>9.1f}%"
              f"{kis_mean.get(g, float('nan')):>10.2f}{kpr.get(g, float('nan')):>10.2f}")
    common = [g for g in shown if g in kis_mean]
    if len(common) >= 5:
        def corr(a, b):
            ma, mb = sum(a) / len(a), sum(b) / len(b)
            num = sum((x - ma) * (yv - mb) for x, yv in zip(a, b))
            den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((yv - mb) ** 2 for yv in b))
            return num / den if den else float("nan")
        ap = [apm[g] for g in common]
        print(f"\n  r(ridge APM, KIS per kill) .... {corr(ap, [kis_mean[g] for g in common]):+.3f}")
        print(f"  r(ridge APM, kills per round) . {corr(ap, [kpr[g] for g in common]):+.3f}")
        print(f"  r(ridge APM, raw win%) ........ "
              f"{corr(ap, [raw[g] for g in common]):+.3f}   (the two WOWY paths agree?)")
        print(f"  n = {len(common)} players — with this many, only a very large")
        print("  correlation is distinguishable from zero. Read the sign, not the digit.")

    # ---- E. the floor -------------------------------------------------------
    print()
    print("=" * 78)
    print("E. THE FLOOR — what this sample can and cannot show")
    print("=" * 78)
    # The McNemar threshold below describes the PAIRED round test, so it must
    # use that test's population (rounds with both sides and a known winner,
    # built in section B), not every round that happens to contain a kill.
    # They coincide today; they would not after a filter change (CodeRabbit).
    n_rounds = n_paired_rounds
    print(f"  paired rounds .................. {n_rounds}"
          f"   (rounds with any kill: {len({k['rid'] for k in kills})})")
    print(f"  players with >= {MIN_KILLS_FOR_PLAYER} kills ....... {len(players)}")
    print(f"  players with >= {MIN_ROUNDS_FOR_WOWY} rounds ...... {len(apm)}")
    disc = 0.19  # observed share of discordant pairs in today's McNemar tests
    need = 1.96 * math.sqrt(disc * n_rounds) / n_rounds
    print(f"  round-winner test: a weighting must flip ~{100*need:.1f}% of rounds")
    print("    net before it reaches p<0.05 (McNemar, ~19% discordant pairs)")
    print("  player reliability: see the 'min detectable' column in section A —")
    print("    per-axis, that is the gap two players need before we may rank them")
    print(f"  ceiling headroom: {100*headroom:+.2f} pp is the total budget for")
    print("    every context idea combined; a new axis has to fit inside it")
    print("\n  => Before proposing a metric, check it against these three numbers.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
