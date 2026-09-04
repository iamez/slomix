#!/usr/bin/env python3
"""Route distinctiveness — do real players move differently on the same map?
(docs/design/22 slice 1: the question to answer BEFORE building a bot twin.)

Read-only over `player_track.path` (200 ms position samples per life). For
every map and every human player with at least `--min-sessions` sessions on
it, the path points are binned on the backend's 512-unit grid
(proximity_positions.py: FLOOR(x/512)) into a visit distribution, and:

  self-split   Jensen–Shannon divergence between the player's own two halves
               (sessions split odd/even by date) — how consistent one player is;
  cross        JS divergence between two different players — how different
               two players are;
  distinct     median(cross) − median(self): > 0 means routes carry a
               personality beyond the map's geometry; ≈ 0 means everyone walks
               the same chokepoints and "his route" would be the map's route.

A second, independent path to the same conclusion: the mean distance from a
player's points to the nearest point of the other player (`nearest`), which
does not depend on the grid at all. Both must agree in direction.

Control that must fail: with the sessions randomly reassigned among the
players (`--seed`), self-split and cross must collapse together (distinct
≈ 0). If the control does not fail, the metric or the pipeline is broken.

Also reported, as food for slice 2: dwell share (points with speed <
`--dwell-speed`), which must VARY between players to be a player trait.

Usage:
  scripts/backtest_route_distinctiveness.py                 # rotation maps
  scripts/backtest_route_distinctiveness.py --maps supply --json out.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

DEFAULT_MAPS = ("etl_adlernest", "supply", "sw_goldrush_te", "etl_sp_delivery", "te_escape2", "etl_frostbite", "et_brewdog")
GRID = 512
Cell = tuple[int, int]
Point = tuple[float, float, float]  # x, y, speed


# ── pure functions (tested without a database) ────────────────────────────

def cell(x: float, y: float, grid: int = GRID) -> Cell:
    """The backend's heatmap cell: FLOOR(x/grid), FLOOR(y/grid)."""
    return (int(math.floor(x / grid)), int(math.floor(y / grid)))


def histogram(points: list[Point], grid: int = GRID) -> Counter:
    return Counter(cell(x, y, grid) for x, y, _ in points)


def normalize(h: Counter) -> dict[Cell, float]:
    total = sum(h.values())
    return {k: v / total for k, v in h.items()} if total else {}


def js_divergence(p: dict[Cell, float], q: dict[Cell, float]) -> float:
    """Jensen–Shannon divergence, base 2: 0 for identical, 1 for disjoint."""
    if not p or not q:
        return float("nan")
    keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in keys}

    def kl(a: dict[Cell, float]) -> float:
        return sum(a[k] * math.log2(a[k] / m[k]) for k in a if a[k] > 0)

    return 0.5 * kl(p) + 0.5 * kl(q)


def nearest_point_distance(a: list[Point], b: list[Point], step: int = 5, grid: int = GRID) -> float:
    """Mean distance from every `step`-th point of `a` to the nearest point of
    `b` (units). Bucketed by grid cell so it is O(n) not O(n²); the search
    covers the 3×3 cells around the point, so a nearest point further than
    one cell away reads as `grid` (a floor, said in the report)."""
    if not a or not b:
        return float("nan")
    buckets: dict[Cell, list[tuple[float, float]]] = defaultdict(list)
    for x, y, _ in b:
        buckets[cell(x, y, grid)].append((x, y))
    total = 0.0
    n = 0
    for x, y, _ in a[::step]:
        cx, cy = cell(x, y, grid)
        best = float("inf")
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for bx, by in buckets.get((cx + dx, cy + dy), ()):
                    d = math.hypot(bx - x, by - y)
                    if d < best:
                        best = d
        total += min(best, float(grid))
        n += 1
    return total / n if n else float("nan")


def dwell_share(points: list[Point], speed_lt: float = 10.0) -> float:
    if not points:
        return float("nan")
    return sum(1 for _, _, s in points if s < speed_lt) / len(points)


def dwell_by_cell(points: list[Point], speed_lt: float = 10.0, grid: int = GRID, top: int = 3) -> list[tuple[Cell, int]]:
    c = Counter(cell(x, y, grid) for x, y, s in points if s < speed_lt)
    return c.most_common(top)


def split_sessions(sessions: list[str]) -> tuple[set[str], set[str]]:
    """Two halves by date order: odd and even sessions — not first/last half,
    which would confound a player's change over time with the split."""
    ordered = sorted(set(sessions))
    return set(ordered[0::2]), set(ordered[1::2])


def shuffle_labels(rows: list[tuple[str, str, list[Point]]], seed: int) -> list[tuple[str, str, list[Point]]]:
    """The control: keep every (session, points) pair, reassign the PLAYER
    label at random among the players present — the same session counts,
    the personality removed."""
    rng = random.Random(seed)  # noqa: S311 — a reproducible shuffle for a control, not a secret
    players = [p for p, _, _ in rows]
    rng.shuffle(players)
    return [(players[i], s, pts) for i, (_, s, pts) in enumerate(rows)]


def measure_map(rows: list[tuple[str, str, list[Point]]], grid: int = GRID, dwell_speed: float = 10.0) -> dict:
    """rows: (player, session_date, points) per life. Returns the per-map
    figures: self-split, cross (both by JS), nearest-point (units), dwell."""
    by_player: dict[str, dict[str, list[Point]]] = defaultdict(lambda: defaultdict(list))
    for player, session, pts in rows:
        by_player[player][session].extend(pts)
    players = sorted(by_player)
    hist = {p: normalize(histogram([pt for s in by_player[p].values() for pt in s], grid)) for p in players}
    allpts = {p: [pt for s in by_player[p].values() for pt in s] for p in players}

    self_js: dict[str, float] = {}
    for p in players:
        a, b = split_sessions(list(by_player[p]))
        pa = [pt for s in a for pt in by_player[p][s]]
        pb = [pt for s in b for pt in by_player[p][s]]
        self_js[p] = js_divergence(normalize(histogram(pa, grid)), normalize(histogram(pb, grid)))

    cross_js: dict[tuple[str, str], float] = {}
    cross_np: dict[tuple[str, str], float] = {}
    for i, p in enumerate(players):
        for q in players[i + 1:]:
            cross_js[(p, q)] = js_divergence(hist[p], hist[q])
            cross_np[(p, q)] = 0.5 * (nearest_point_distance(allpts[p], allpts[q], grid=grid)
                                      + nearest_point_distance(allpts[q], allpts[p], grid=grid))
    self_np = {}
    for p in players:
        a, b = split_sessions(list(by_player[p]))
        pa = [pt for s in a for pt in by_player[p][s]]
        pb = [pt for s in b for pt in by_player[p][s]]
        self_np[p] = 0.5 * (nearest_point_distance(pa, pb, grid=grid) + nearest_point_distance(pb, pa, grid=grid))

    nearest_other = {}
    for p in players:
        cands = [(cross_js[(min(p, q), max(p, q))], q) for q in players if q != p]
        nearest_other[p] = min(cands) if cands else (float("nan"), None)

    def med(vals):
        vals = [v for v in vals if not math.isnan(v)]
        return statistics.median(vals) if vals else float("nan")

    return {
        "players": players,
        "sessions": {p: len(by_player[p]) for p in players},
        "self_js": self_js,
        "cross_js_median": med(cross_js.values()),
        "self_js_median": med(self_js.values()),
        "distinct_js": med(cross_js.values()) - med(self_js.values()),
        "self_np_median": med(self_np.values()),
        "cross_np_median": med(cross_np.values()),
        "distinct_np": med(cross_np.values()) - med(self_np.values()),
        "nearest_other": nearest_other,
        "dwell": {p: dwell_share(allpts[p], dwell_speed) for p in players},
        "dwell_cells": {p: dwell_by_cell(allpts[p], dwell_speed, grid) for p in players},
    }


# ── the corpus run ────────────────────────────────────────────────────────

async def load_rows(db, map_name: str, min_sessions: int) -> list[tuple[str, str, list[Point]]]:
    rows = await db.fetch_all(
        """
        SELECT pt.player_guid, pt.player_name, pt.session_date::text, pt.path
        FROM player_track pt
        WHERE pt.map_name = $1
          AND pt.player_name NOT LIKE '%[BOT]%'
          AND UPPER(pt.player_guid) NOT LIKE 'OMNIBOT%'
          AND pt.player_guid IN (
            SELECT player_guid FROM player_track
            WHERE map_name = $1 AND player_name NOT LIKE '%[BOT]%'
            GROUP BY player_guid HAVING COUNT(DISTINCT session_date) >= $2)
        """,
        (map_name, min_sessions),
    )
    out: list[tuple[str, str, list[Point]]] = []
    names: dict[str, str] = {}
    for guid, name, session, path in rows or []:
        pts = json.loads(path) if isinstance(path, str) else (path or [])
        # Every 5th sample: 200 ms → 1 s. The positional-knowledge horizon is
        # ~1 s anyway (memory 2026-08-23), and te_escape2 alone holds ~2.6 M
        # raw points — the nearest-point path is O(points), the JS path is
        # unaffected in shape. Dwell is measured on the same 1 s samples.
        points = [(float(p["x"]), float(p["y"]), float(p.get("speed") or 0.0)) for p in pts[::5] if "x" in p and "y" in p]
        key = str(guid)[:8].upper()
        names.setdefault(key, name)
        out.append((key, session, points))
    return out


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--maps", nargs="*", default=list(DEFAULT_MAPS))
    ap.add_argument("--min-sessions", type=int, default=10)
    ap.add_argument("--grid", type=int, default=GRID)
    ap.add_argument("--dwell-speed", type=float, default=10.0)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args(argv)

    import asyncpg  # noqa: PLC0415
    from audit_session_basics import Shim, _dsn  # noqa: PLC0415

    conn = await asyncpg.connect(_dsn())
    await conn.execute("SET default_transaction_read_only = on")
    db = Shim(conn)
    report: dict[str, dict] = {}
    print(f"route distinctiveness · grid {args.grid} u · players with >= {args.min_sessions} sessions · humans only")
    print(f"{'map':16} {'n':>3} {'self JS':>8} {'cross JS':>9} {'distinct':>9} | {'self np':>8} {'cross np':>9} {'distinct':>9} | {'control':>8}")
    for m in args.maps:
        rows = await load_rows(db, m, args.min_sessions)
        if not rows:
            print(f"{m:16}   0  (no player clears the session floor)")
            continue
        real = measure_map(rows, args.grid, args.dwell_speed)
        ctrl = measure_map(shuffle_labels(rows, args.seed), args.grid, args.dwell_speed)
        report[m] = {"real": real, "control_distinct_js": ctrl["distinct_js"], "control_distinct_np": ctrl["distinct_np"]}
        print(f"{m:16} {len(real['players']):>3} {real['self_js_median']:8.3f} {real['cross_js_median']:9.3f} {real['distinct_js']:9.3f} | "
              f"{real['self_np_median']:8.0f} {real['cross_np_median']:9.0f} {real['distinct_np']:9.0f} | {ctrl['distinct_js']:8.3f}")
    print()
    print(f"per player (dwell = share of samples with speed < {args.dwell_speed:.0f}; nearest other = smallest cross JS):")
    for m, r in report.items():
        real = r["real"]
        for p in real["players"]:
            no = real["nearest_other"][p]
            print(f"  {m:16} {p:8} sessions={real['sessions'][p]:>2} self={real['self_js'][p]:.3f} nearest={no[0]:.3f} ({no[1]}) dwell={real['dwell'][p]*100:5.1f} % top={real['dwell_cells'][p][:2]}")
    await conn.close()
    if args.json:
        args.json.write_text(json.dumps(report, default=str, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
