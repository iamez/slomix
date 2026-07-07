#!/usr/bin/env python3
"""K-E backtest: target acquisition + reaction under fire + spawn readiness.

READ-ONLY (SET default_transaction_read_only = on). Owner-corrected naming:
"target acquisition" (aim_lock onset -> kill), NOT "reflex" — the number mixes
crosshair placement, pre-aim, tracking, ping, server tick, surprise, distance
and weapon, so it is only meaningful RELATIVE to the group. Reaction-under-fire
(return fire / dodge, victim-centric) and spawn readiness are reported as
SEPARATE metrics — never folded into one "reflex" aggregate.

Data constraints stated up front:
- position/track telemetry is quantized at ~200 ms — medians and group
  percentiles only, no sub-200 ms precision claims
- proximity_aim_lock is live since 2026-06-11, so target acquisition covers
  only rounds from that date; reaction/spawn metrics cover full history

Owner backtest rules honored: sample sizes printed everywhere, min-event
thresholds per metric, split-half stability check (session parity), CSV/MD
output stamped with formula_version, top/bottom tables.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import asyncpg

FORMULA_VERSION = "target-acq-v0.1"

ACQ_KILL_WINDOW_MS = 1000     # kill must land within lock window (+1s slack)
MIN_ACQ_EVENTS = 15           # linked aim_lock->kill events to be rated
MIN_REACTION_EVENTS = 30      # return-fire samples to be rated
MIN_SPAWN_LIVES = 50          # player_track lives to be rated
SANE_MS_MAX = 5000            # drop degenerate reaction values above this
AIM_LOCK_LIVE_SINCE = "2026-06-22"  # v7 probe rows before activation are
                                    # experimental — never rate them
BOT_FILTER = ("OMNIBOT%", "[BOT]%")


_COLOR_RE = re.compile(r"\^.")


def _clean(name: str) -> str:
    """Strip ET ^-color codes for table readability."""
    return _COLOR_RE.sub("", name or "")


def _median(vals: list[float]) -> float:
    return statistics.median(vals)


def _q(vals: list[float], p: float) -> float:
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
    return s[idx]


def _rank_map(items: list[tuple[str, float]]) -> dict[str, float]:
    """guid -> rank position (1 = best i.e. LOWEST ms), ties by order."""
    return {g: i + 1 for i, (g, _) in enumerate(sorted(items, key=lambda x: x[1]))}


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Tie-aware Spearman (average ranks) without scipy.

    Returns None below n=4 or when either half has no distinct values —
    with ~200ms-quantized telemetry fully-tied medians are common, and
    insertion-order ranks would report a false +1.00 "stability".
    """
    n = len(xs)
    if n < 4 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        pos = 0
        while pos < n:
            end = pos
            while end + 1 < n and v[order[end + 1]] == v[order[pos]]:
                end += 1
            avg = (pos + end) / 2 + 1.0  # average rank across the tie run
            for k in range(pos, end + 1):
                r[order[k]] = avg
            pos = end + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else None


async def load_events(conn) -> dict[str, dict]:
    """Per-metric: guid -> {name, events: [(session_key, value_ms)]}.

    session_key = rounds.gaming_session_id when the row is linked to a valid
    round, else 'd:<calendar date>' — two sessions on one day must not
    collapse into a single split-half bucket (codex, PR #458 round 2).
    """
    out: dict[str, dict] = {"acq": {}, "acq_err": {}, "return_fire": {},
                            "dodge": {}, "spawn": {}}

    # A) TARGET ACQUISITION: aim_lock onset -> linked kill on the same target.
    #    Join by round identity + canonical killer + victim guid8 (kill_outcome
    #    has no victim canonical column); kill inside lock window (+ slack).
    rows = await conn.fetch(f"""
        SELECT al.guid_canonical, MAX(al.player_name) AS name,
               COALESCE(r.gaming_session_id::text,
                        'd:' || al.session_date::text) AS session_key,
               (ko.kill_time - al.start_time) AS acq_ms,
               AVG(al.avg_err_deg) AS err_deg
        FROM proximity_aim_lock al
        JOIN proximity_kill_outcome ko
          ON ko.round_start_unix = al.round_start_unix
         AND ko.session_date = al.session_date
         AND ko.round_number = al.round_number
         AND ko.killer_guid_canonical = al.guid_canonical
         AND UPPER(SUBSTRING(ko.victim_guid, 1, 8)) =
             UPPER(SUBSTRING(al.target_guid, 1, 8))
         AND ko.kill_time BETWEEN al.start_time
                              AND al.end_time + {ACQ_KILL_WINDOW_MS}
        LEFT JOIN rounds r ON r.id = al.round_id
        LEFT JOIN rounds rk ON rk.id = ko.round_id
        WHERE (r.id IS NULL OR r.is_valid)
          AND (rk.id IS NULL OR rk.is_valid)
          -- 0 = missing round metadata; such buckets conflate unrelated
          -- rounds (see round-linker regression coverage) — never join them
          AND al.round_start_unix > 0
          AND al.session_date >= '{AIM_LOCK_LIVE_SINCE}'::date
          AND al.guid NOT LIKE $1 AND al.player_name NOT LIKE $2
          -- the TARGET must be human too: locking a bot and killing it must
          -- not feed a human-skill median (codex, PR #458 round 2)
          AND al.target_guid NOT LIKE $1
          AND COALESCE(al.target_name, '') NOT LIKE $2
          AND ko.victim_guid NOT LIKE $1
          AND COALESCE(ko.victim_name, '') NOT LIKE $2
          AND ko.kill_time > al.start_time
        GROUP BY al.id, al.guid_canonical, r.gaming_session_id,
                 al.session_date, ko.kill_time
    """, *BOT_FILTER)
    for r in rows:
        g = r["guid_canonical"].upper()
        d = out["acq"].setdefault(g, {"name": r["name"], "events": []})
        d["events"].append((r["session_key"], float(r["acq_ms"])))
        e = out["acq_err"].setdefault(g, {"name": r["name"], "events": []})
        e["events"].append((r["session_key"], float(r["err_deg"] or 0)))

    # B) REACTION UNDER FIRE (victim-centric, separate metric family)
    rows = await conn.fetch("""
        SELECT rm.target_guid, MAX(rm.target_name) AS name,
               COALESCE(r.gaming_session_id::text,
                        'd:' || rm.session_date::text) AS session_key,
               rm.return_fire_ms, rm.dodge_reaction_ms
        FROM proximity_reaction_metric rm
        LEFT JOIN rounds r ON r.id = rm.round_id
        WHERE (r.id IS NULL OR r.is_valid)
          AND rm.target_guid NOT LIKE $1 AND rm.target_name NOT LIKE $2
          AND (rm.return_fire_ms > 0 OR rm.dodge_reaction_ms > 0)
        GROUP BY rm.id, rm.target_guid, r.gaming_session_id, rm.session_date,
                 rm.return_fire_ms, rm.dodge_reaction_ms
    """, *BOT_FILTER)
    for r in rows:
        g = r["target_guid"][:8].upper()
        sd = r["session_key"]
        if r["return_fire_ms"] and 0 < r["return_fire_ms"] <= SANE_MS_MAX:
            d = out["return_fire"].setdefault(g, {"name": r["name"], "events": []})
            d["events"].append((sd, float(r["return_fire_ms"])))
        if r["dodge_reaction_ms"] and 0 < r["dodge_reaction_ms"] <= SANE_MS_MAX:
            d = out["dodge"].setdefault(g, {"name": r["name"], "events": []})
            d["events"].append((sd, float(r["dodge_reaction_ms"])))

    # C) SPAWN READINESS: time from spawn to first movement per life
    rows = await conn.fetch(f"""
        SELECT pt.player_guid, MAX(pt.player_name) AS name,
               COALESCE(r.gaming_session_id::text,
                        'd:' || pt.session_date::text) AS session_key,
               pt.time_to_first_move_ms
        FROM player_track pt
        LEFT JOIN rounds r ON r.id = pt.round_id
        WHERE (r.id IS NULL OR r.is_valid)
          AND pt.player_guid NOT LIKE $1 AND pt.player_name NOT LIKE $2
          AND pt.time_to_first_move_ms > 0
          AND pt.time_to_first_move_ms <= {SANE_MS_MAX}
        GROUP BY pt.id, pt.player_guid, r.gaming_session_id, pt.session_date,
                 pt.time_to_first_move_ms
    """, *BOT_FILTER)
    for r in rows:
        g = r["player_guid"][:8].upper()
        d = out["spawn"].setdefault(g, {"name": r["name"], "events": []})
        d["events"].append((r["session_key"], float(r["time_to_first_move_ms"])))

    return out


def summarize(metric: str, data: dict, min_events: int,
              lower_is_better: bool = True) -> list[dict]:
    rated = []
    for g, d in data.items():
        vals = [v for _, v in d["events"]]
        if len(vals) < min_events:
            continue
        rated.append({
            "guid": g, "name": d["name"], "n": len(vals),
            "median": _median(vals), "p25": _q(vals, 0.25), "p75": _q(vals, 0.75),
            "sessions": len({sd for sd, _ in d["events"]}),
        })
    rated.sort(key=lambda x: x["median"], reverse=not lower_is_better)
    n = len(rated)
    # equal medians share one percentile (tie-group average) — quantized
    # telemetry ties often, and insertion order must not fabricate rank
    i = 0
    while i < n:
        j = i
        while j + 1 < n and rated[j + 1]["median"] == rated[i]["median"]:
            j += 1
        pct = (sum(1.0 - k / (n - 1) for k in range(i, j + 1)) / (j - i + 1)
               if n > 1 else 1.0)
        for k in range(i, j + 1):
            rated[k]["pct_rank"] = round(pct, 3)
        i = j + 1
    return rated


def stability(data: dict, min_events: int,
              rated_guids: set[str]) -> tuple[float | None, int]:
    """Split-half: odd/even session parity medians, Spearman across players.

    Restricted to the SAME player set as the rated leaderboard (total
    n >= min_events), then additionally requires enough events per half.
    """
    xs, ys = [], []
    for g, d in data.items():
        if g not in rated_guids:
            continue
        by_sess: dict[str, list[float]] = defaultdict(list)
        for sd, v in d["events"]:
            by_sess[sd].append(v)
        # numeric ids sort numerically ('99' < '100'); date-fallback keys after
        sessions = sorted(by_sess, key=lambda k: (0, int(k)) if k.isdigit()
                          else (1, k))
        a = [v for s in sessions[0::2] for v in by_sess[s]]
        b = [v for s in sessions[1::2] for v in by_sess[s]]
        if len(a) >= min_events // 2 and len(b) >= min_events // 2:
            xs.append(_median(a))
            ys.append(_median(b))
    return _spearman(xs, ys), len(xs)


def print_table(title: str, rated: list[dict], unit: str = "ms") -> list[str]:
    lines = [f"\n## {title}  (rated={len(rated)})",
             f"{'#':>3} {'player':<20} {'median':>8} {'p25':>7} {'p75':>7} "
             f"{'n':>6} {'sess':>5} {'pct':>6}"]
    for i, r in enumerate(rated):
        lines.append(
            f"{i + 1:>3} {(_clean(r['name']) or r['guid'])[:20]:<20} "
            f"{r['median']:>6.0f}{unit} {r['p25']:>7.0f} {r['p75']:>7.0f} "
            f"{r['n']:>6} {r['sessions']:>5} {r['pct_rank']:>6.3f}")
    print("\n".join(lines))
    return lines


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-dir", default=".", help="where CSV/MD land")
    args = ap.parse_args()

    conn = await asyncpg.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=os.environ.get("POSTGRES_PASSWORD") or os.environ.get("PGPASSWORD", ""))
    await conn.execute("SET default_transaction_read_only = on")

    data = await load_events(conn)
    await conn.close()

    print(f"=== K-E target acquisition / reaction backtest — {FORMULA_VERSION} ===")
    print("NOTE: ~200ms telemetry quantization — medians/relative ranks only.")
    print(f"raw players: acq={len(data['acq'])} return_fire={len(data['return_fire'])} "
          f"dodge={len(data['dodge'])} spawn={len(data['spawn'])}")
    print(f"raw events:  acq={sum(len(d['events']) for d in data['acq'].values())} "
          f"return_fire={sum(len(d['events']) for d in data['return_fire'].values())} "
          f"dodge={sum(len(d['events']) for d in data['dodge'].values())} "
          f"spawn={sum(len(d['events']) for d in data['spawn'].values())}")
    print(f"thresholds:  acq>={MIN_ACQ_EVENTS} return_fire/dodge>={MIN_REACTION_EVENTS} "
          f"spawn>={MIN_SPAWN_LIVES}")

    md = [f"# K-E backtest — {FORMULA_VERSION}", ""]
    specs = [
        (f"TARGET ACQUISITION (aim-lock onset → kill; live since {AIM_LOCK_LIVE_SINCE})",
         "acq", MIN_ACQ_EVENTS),
        ("REACTION UNDER FIRE — return fire", "return_fire", MIN_REACTION_EVENTS),
        ("REACTION UNDER FIRE — dodge", "dodge", MIN_REACTION_EVENTS),
        ("SPAWN READINESS (time to first move per life)", "spawn", MIN_SPAWN_LIVES),
    ]
    csv_rows = []
    for title, key, mn in specs:
        rated = summarize(key, data[key], mn)
        md += print_table(title, rated)
        if rated:
            spread = rated[-1]["median"] - rated[0]["median"]
            disc = ("DISCRIMINATES" if spread >= 200 else
                    "DOES NOT DISCRIMINATE (spread < 200ms quantization)")
            dline = (f"   median spread best->worst: {spread:.0f}ms -> {disc}")
            print(dline)
            md.append(dline)
        corr, n_pairs = stability(data[key], mn, {r["guid"] for r in rated})
        verdict = ("n/a (too few players or fully tied medians)" if corr is None else
                   f"{corr:+.2f} ({'STABLE' if corr >= 0.5 else 'WEAK — treat as descriptive'})")
        line = f"   split-half stability (session parity, n={n_pairs} players): {verdict}"
        print(line)
        md.append(line)
        csv_rows.extend(
            {"metric": key, **{k: r[k] for k in
             ("guid", "name", "n", "sessions", "median", "p25", "p75", "pct_rank")},
             "formula_version": FORMULA_VERSION}
            for r in rated)

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "target_acq_v01.csv"
    fieldnames = ["metric", "guid", "name", "n", "sessions", "median",
                  "p25", "p75", "pct_rank", "formula_version"]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(csv_rows)  # header-only file when nothing met thresholds
    md_path = out / "target_acq_v01.md"
    md_path.write_text("\n".join(md) + "\n")
    print(f"\nwrote {csv_path} and {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
