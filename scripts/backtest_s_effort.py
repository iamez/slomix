#!/usr/bin/env python3
"""K-B1: s.effort backtest (READ-ONLY). formula_version = s.effort-v0.1

Initial hypothesis (SuperBoyy, name fixed by owner): s.effort = sess_rating /
pool_strength ; s.performance = s.effort / (lifetime / POOL_NEUTRAL).
pool_strength is NOT decided yet — this backtest compares 4 variants
(leave-one-out where the player would otherwise rate himself):
  A all participants (excl self)   B own team (excl self)
  C opponents only                 D opponent/team ratio (team-diff)
POOL_NEUTRAL = 0.564 (population avg of player_skill_ratings, not theoretical 1).

Owner requirements baked in: sample sizes printed; min-sessions threshold;
sanity checks PASS/FAIL (hard-pool no punish / easy-pool no boost / volume not
the main driver + session-count buckets); CSV + Markdown saved with
formula_version; top20 / bottom20 / changed-most-vs-current tables.
"""
from __future__ import annotations

import asyncio
import csv
import json
import os
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import asyncpg  # noqa: E402

from website.backend.services.skill_rating_service import (  # noqa: E402
    compute_population_percentiles,
    compute_session_ratings,
)

FORMULA_VERSION = "s.effort-v0.1"
POOL_NEUTRAL = 0.564
MIN_SESSIONS = 5
OUT = os.environ.get("S_EFFORT_OUT", "backtest_out/s_effort_v01")


def _tr(q):
    out, i = [], 0
    for ch in q:
        if ch == "?":
            i += 1
            out.append(f"${i}")
        else:
            out.append(ch)
    return "".join(out)


class Shim:
    def __init__(self, conn):
        self.conn = conn

    async def fetch_all(self, q, params=()):
        return await self.conn.fetch(_tr(q), *params)

    async def fetch_one(self, q, params=()):
        return await self.conn.fetchrow(_tr(q), *params)


def g8(guid):
    return (guid or "")[:8].upper()


def corr(xs, ys):
    if len(xs) < 3 or st.pstdev(xs) == 0 or st.pstdev(ys) == 0:
        return 0.0
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return num / den if den else 0.0


async def main():
    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")
    db = Shim(conn)

    life = {}   # g8 -> (name, lifetime_rating, full_guid)
    for r in await conn.fetch(
            "SELECT player_guid, display_name, et_rating FROM player_skill_ratings"):
        life[g8(r[0])] = (r[1] or g8(r[0]), float(r[2]), r[0])

    percentiles = await compute_population_percentiles(db)

    # DISTINCT ON: session_results has one row per (date, map, session) —
    # iterating raw rows would score the same player-session once per map
    # and inflate n_sessions_used and every table (codex, PR #463).
    # The scoring DATE comes from rounds (MIN(round_date) per gsid), NOT from
    # session_results.session_date: results can finalize across midnight and
    # compute_session_ratings scopes sessions by their START date — the same
    # derivation the production s.effort backfill uses (codex, round 4).
    sessions = await conn.fetch("""
        SELECT DISTINCT ON (sr.gaming_session_id)
               sr.gaming_session_id,
               rd.start_date AS session_date,
               sr.team_1_guids, sr.team_2_guids
        FROM session_results sr
        JOIN (
            SELECT gaming_session_id,
                   MIN(SUBSTRING(round_date, 1, 10)) AS start_date
            FROM rounds
            WHERE gaming_session_id IS NOT NULL AND is_valid
            GROUP BY gaming_session_id
        ) rd ON rd.gaming_session_id = sr.gaming_session_id
        WHERE sr.team_1_guids IS NOT NULL AND sr.team_2_guids IS NOT NULL
          -- legacy NULL-gsid rows would collapse into ONE DISTINCT group;
          -- this backtest scores gsid-scoped sessions only (codex, PR #463)
          AND sr.gaming_session_id IS NOT NULL
        ORDER BY sr.gaming_session_id""")

    # Aggregate rosters BY START DATE: compute_session_ratings (and the
    # production persist) score date-wide — every gsid whose MIN(round_date)
    # matches — so two sessions sharing a start date must be ONE scoring unit
    # here too, with unioned team rosters (codex, PR #463 rounds 5-6).
    by_date: dict = {}
    date_gsids: dict = {}
    for s in sessions:
        date = str(s["session_date"])[:10]
        ent = by_date.setdefault(date, (set(), set()))
        ent[0].update(g8(x) for x in json.loads(s["team_1_guids"]) if g8(x) in life)
        ent[1].update(g8(x) for x in json.loads(s["team_2_guids"]) if g8(x) in life)
        date_gsids.setdefault(date, set()).add(int(s["gaming_session_id"]))

    # cohort completeness: the scorer includes EVERY valid gsid starting on
    # the date — if session_results is missing rosters for one of them, the
    # rating would include rounds whose players aren't in the pool. Skip such
    # dates and say so (codex, PR #463 round 6).
    all_gsids = {}
    for r in await conn.fetch("""
            SELECT MIN(SUBSTRING(round_date, 1, 10)) AS d,
                   gaming_session_id
            FROM rounds WHERE gaming_session_id IS NOT NULL AND is_valid
            GROUP BY gaming_session_id"""):
        all_gsids.setdefault(str(r["d"])[:10], set()).add(int(r["gaming_session_id"]))
    incomplete = {d for d, g in date_gsids.items() if g != all_gsids.get(d, set())}
    if incomplete:
        print(f"skipped {len(incomplete)} date(s) with unfinalized sessions "
              f"(rosters missing for some gsids): {sorted(incomplete)[:5]}...")

    per_player = {}          # g8 -> list of dicts per session-date
    n_sessions_used = 0
    for date, (t1set, t2set) in sorted(by_date.items()):
        if date in incomplete:
            continue
        participants = sorted(t1set | t2set)
        ambiguous = t1set & t2set  # both sides across merged sessions
        t1, t2 = sorted(t1set - ambiguous), sorted(t2set - ambiguous)
        if len(participants) < 4:
            continue
        n_sessions_used += 1
        team_ok = len(t1) >= 2 and len(t2) >= 2
        for p in participants:
            try:
                sr = await compute_session_ratings(db, life[p][2], date, percentiles)
            except Exception as e:  # noqa: BLE001 - backtest: skip player-session, keep going
                print(f"  skip {life[p][0]} {date}: {e}", file=sys.stderr)
                continue
            sess = (sr or {}).get("session_rating") if isinstance(sr, dict) else None
            if sess is None:
                continue
            others = [g for g in participants if g != p]
            # variant A (the production pool) rates EVERYONE, including
            # both-side players (codex, PR #463 round 6)
            pools = {"A_all": st.mean(life[g][1] for g in others),
                     "B_team": None, "C_opp": None, "D_diff": None}
            if team_ok and p not in ambiguous:
                team, opp = (t1, t2) if p in t1set else (t2, t1)
                mates = [g for g in team if g != p]
                team_loo = st.mean(life[g][1] for g in mates) if mates else POOL_NEUTRAL
                opp_avg = st.mean(life[g][1] for g in opp)
                pools.update({
                    "B_team": team_loo,
                    "C_opp": opp_avg,
                    "D_diff": POOL_NEUTRAL * (opp_avg / team_loo) if team_loo else POOL_NEUTRAL,
                })
            rec = {"sess": float(sess), "pools": pools, "date": date}
            per_player.setdefault(p, []).append(rec)

    variants = ["A_all", "B_team", "C_opp", "D_diff"]
    rows = []
    for p, recs in per_player.items():
        if len(recs) < MIN_SESSIONS:
            continue
        name, lt, _full = life[p]
        row = {"player": name, "g8": p, "lifetime": lt, "n_sessions": len(recs)}
        for v in variants:
            vrecs = [r for r in recs if r["pools"].get(v)]
            if len(vrecs) < MIN_SESSIONS:
                row[f"eff_{v}"] = row[f"perf_{v}"] = None
                continue
            # s.effort scaled so pool==NEUTRAL leaves sess/NEUTRAL scale-free:
            efforts = [r["sess"] / r["pools"][v] for r in vrecs]
            perf = [e / (lt / POOL_NEUTRAL) for e in efforts]
            row[f"eff_{v}"] = st.mean(efforts)
            row[f"perf_{v}"] = st.mean(perf)
            row[f"stab_{v}"] = st.pstdev(perf)
            row[f"pool_{v}"] = st.mean(r["pools"][v] for r in vrecs)
        rows.append(row)

    total_players_all = len(per_player)
    # sanity tables read variant C; players without enough team-attributed
    # sessions (merged-date ambiguity) sink to the bottom instead of crashing
    rows.sort(key=lambda r: -(r["perf_C_opp"] if r["perf_C_opp"] is not None else -9))

    print(f"=== s.effort backtest  formula_version={FORMULA_VERSION} ===")
    print(f"SAMPLE SIZE: sessions_with_rosters={n_sessions_used} "
          f"players_any={total_players_all} players>=min{MIN_SESSIONS}sess={len(rows)} "
          f"player_sessions={sum(r['n_sessions'] for r in rows)}")

    hdr = (f"{'player':<14}{'n':>3}{'life':>6} | "
           + "".join(f"{'perf_' + v[:1]:>8}" for v in variants)
           + " | " + "".join(f"{'eff_' + v[:1]:>7}" for v in variants)
           + f"{'stabC':>7}")
    print(hdr)
    def _f(x, w):
        return f"{x:>{w}.3f}" if x is not None else f"{'—':>{w}}"

    for r in rows:
        print(f"{r['player'][:13]:<14}{r['n_sessions']:>3}{r['lifetime']:>6.3f} | "
              + "".join(_f(r['perf_' + v], 8) for v in variants)
              + " | " + "".join(_f(r['eff_' + v], 7) for v in variants)
              + _f(r.get('stab_C_opp'), 7))

    # ---- sanity checks
    print("\n=== SANITY CHECKS ===")
    rows_c = [r for r in rows if r["perf_C_opp"] is not None]
    perfs = [r["perf_C_opp"] for r in rows_c]
    pools = [r["pool_C_opp"] for r in rows_c]
    ns = [r["n_sessions"] for r in rows_c]
    lts = [r["lifetime"] for r in rows_c]
    c_pool = corr(perfs, pools)
    print(f"(a) hard-pool-no-punish: corr(perf_C, avg_pool_faced) = {c_pool:+.3f} "
          f"-> {'PASS' if c_pool > -0.35 else 'FAIL'} (strongly negative would punish hard pools)")
    weak_easy = [r for r in rows_c if r["lifetime"] < POOL_NEUTRAL and r["pool_C_opp"] < POOL_NEUTRAL]
    boost = max((r["perf_C_opp"] for r in weak_easy), default=0)
    print(f"(b) easy-pool-no-boost: max perf of below-avg players in below-avg pools = "
          f"{boost:.3f} -> {'PASS' if boost < 1.25 else 'CHECK'} (n={len(weak_easy)})")
    c_vol = corr(perfs, ns)
    print(f"(c) volume-not-main-driver: corr(perf_C, n_sessions) = {c_vol:+.3f} "
          f"(context: corr(lifetime, n_sessions) = {corr(lts, ns):+.3f})")
    buckets = {}
    for r in rows_c:
        b = "5-9" if r["n_sessions"] < 10 else ("10-19" if r["n_sessions"] < 20 else "20+")
        buckets.setdefault(b, []).append(r["perf_C_opp"])
    for b in ("5-9", "10-19", "20+"):
        if b in buckets:
            print(f"    bucket {b:>5} sessions: n={len(buckets[b])} avg_perf={st.mean(buckets[b]):.3f}")

    # ---- changed most vs current rating (rank by perf_C vs rank by lifetime)
    by_perf = {r["g8"]: i for i, r in enumerate(rows)}
    by_life = {r["g8"]: i for i, r in enumerate(sorted(rows, key=lambda x: -x["lifetime"]))}
    moved = sorted(rows, key=lambda r: -(abs(by_life[r["g8"]] - by_perf[r["g8"]])))
    print("\n=== CHANGED MOST vs current lifetime ranking (perf_C) ===")
    for r in moved[:8]:
        print(f"  {r['player'][:14]:<15} lifetime#{by_life[r['g8']] + 1:>2} -> perf#{by_perf[r['g8']] + 1:>2}")

    # ---- CSV + MD
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT + ".csv", "w", newline="") as f:
        if not rows:
            print("no players met MIN_SESSIONS — nothing to write")
            return
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["formula_version"])
        w.writeheader()
        for r in rows:
            w.writerow({**{k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in r.items()},
                        "formula_version": FORMULA_VERSION})
    with open(OUT + ".md", "w") as f:
        f.write(f"# s.effort {FORMULA_VERSION}\n\nsessions={n_sessions_used} "
                f"players={len(rows)} (min {MIN_SESSIONS} sessions)\n\n")
        f.write("|player|n|lifetime|" + "|".join(f"perf_{v}" for v in variants) + "|\n")
        f.write("|" + "---|" * (3 + len(variants)) + "\n")
        for r in rows:
            f.write(f"|{r['player']}|{r['n_sessions']}|{r['lifetime']:.3f}|"
                    + "|".join(f"{r['perf_' + v]:.3f}" for v in variants) + "|\n")
    print(f"\nSaved: {OUT}.csv / .md")
    await conn.close()

asyncio.run(main())
