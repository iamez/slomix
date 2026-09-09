#!/usr/bin/env python
"""Layer 4 of the spider web — collect the candidate dataset and run §8.

Two phases, so the numbers can be reproduced without the database:

  collect  walks every eligible round (tracks linked, valid, human, with a
           winner) at a fixed cadence through the layer-1 snapshot, layer-3
           information state and, where the map has geometry, the W6-validated
           line-of-sight tracer, and writes one row per (player, round) with
           the candidate metrics as shares of that player's alive samples.
  analyse  the §8.6 reference implementation on the saved rows: within-round
           median split, chronological 70/30 block split, block bootstrap with
           a max-T family-wise interval, a verdict per candidate, and the frozen
           family manifest with its hash.

⛔ Every candidate here is a HYPOTHESIS (spec §7.4). The controls are part of
the family: dpm must ship (a known within-round signal) and a seeded uniform
must not, or the harness — not the candidates — is what is being measured.
⛔ The oracle candidates (exposure, wave phase) consume true enemy positions
and the reconstructed enemy clock; §6.4/§7.4 say those can be reported as a
diagnostic and never shipped as a score. Their verdict is published like the
others, but `kind` names them.

Usage (dev, from the repo root, with website/.env loaded):
  python scripts/spiderweb_layer4_family.py collect --out /path/rows.jsonl [--limit N] [--cadence-ms 5000] [--skip-los]
  python scripts/spiderweb_layer4_family.py analyse --rows /path/rows.jsonl --out-md /path/table.md --out-manifest docs/spiderweb/layer4_family_manifest.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from website.backend.services import layer4_family as l4  # noqa: E402
from website.backend.services import line_of_sight as los  # noqa: E402
from website.backend.services import round_web_service as rws  # noqa: E402
from website.backend.services.layer4_family import Candidate, Row  # noqa: E402

#: Moving = faster than this, in game units per second (walking is ~130–200,
#: sprinting ~350; 100 separates "standing/strafing in place" from going somewhere).
MOVING_UPS = 100.0
#: Geometrically alone = no living teammate within this many units (straight line).
ISOLATION_UNITS = 800.0
#: "Enemy wave imminent" = the enemy's next reinforcement lands within this share of its interval.
WAVE_IMMINENT_SHARE = 0.25
DEFAULT_CADENCE_MS = 5000
SEED = 20260909
RESAMPLES = 2000

CANDIDATES: list[Candidate] = [
    Candidate("dpm", "damage given × 60 / seconds played, from player_comprehensive_stats for that round", "positive",
              {"source": "player_comprehensive_stats"}, kind="positive_control"),
    Candidate("noise", "uniform(0, 1) seeded by (round_id, guid)", "positive", {"seed": SEED}, kind="negative_control"),
    Candidate("moving_share", "share of alive samples with speed > MOVING_UPS", "positive", {"moving_ups": MOVING_UPS}),
    Candidate("isolation_share", "share of alive samples with no living teammate within ISOLATION_UNITS (straight-line, §7.4: geometric separation, not route support time)", "negative",
              {"isolation_units": ISOLATION_UNITS}, kind="oracle_diagnostic"),
    Candidate("blind_moving_share", "share of MOVING samples during which the holder held NO placeable enemy belief (subject named, region inside position_claim_max_radius, counts_as_known) — moved without knowing where any enemy was; information-consistent movement, §7.4", "negative",
              {"moving_ups": MOVING_UPS, "placeable": "subject_guid and region.radius <= position_claim_max_radius and counts_as_known"}),
    Candidate("exposure_share", "share of alive samples with ≥ 1 living enemy holding a clear eye-to-body ray to the player (W6 tracer, static geometry) — §7.4 exposure, ORACLE form", "negative",
              {"tracer": "services/line_of_sight.py", "validation": "W6 2026-08-22, 99.92 %"}, kind="oracle_diagnostic"),
    Candidate("push_into_wave_share", "share of MOVING samples while the ENEMY's validated reinforcement wave lands within WAVE_IMMINENT_SHARE of its interval (oracle clock, §5.6/§6.3: never a scoring fallback)", "negative",
              {"wave_imminent_share": WAVE_IMMINENT_SHARE, "clock": "validated only"}, kind="oracle_diagnostic"),
]

ROUNDS_SQL = """
    SELECT r.id, r.gaming_session_id, r.map_name, r.winner_team, r.round_date::text, r.round_time::text, r.round_number
    FROM rounds r
    WHERE r.round_number IN (1, 2)
      AND r.is_valid IS DISTINCT FROM FALSE
      AND r.is_bot_round IS DISTINCT FROM TRUE
      AND r.winner_team IN (1, 2)
      AND r.gaming_session_id IS NOT NULL
      AND EXISTS (SELECT 1 FROM player_track pt WHERE pt.round_id = r.id)
    ORDER BY r.round_date, r.round_time, r.id
"""
DPM_SQL = """
    SELECT player_guid, damage_given, time_played_seconds
    FROM player_comprehensive_stats WHERE round_id = $1
"""


class MemoDb:
    """The same answers the loaders would get, fetched once per round: layer 3
    and the clock issue their queries per call, and the walk calls them per tick."""

    def __init__(self, db):
        self._db = db
        self._memo: dict[tuple, list] = {}

    async def fetch_all(self, sql, params=None):
        key = (sql, tuple(params) if params else ())
        if key not in self._memo:
            self._memo[key] = await self._db.fetch_all(sql, params)
        return self._memo[key]

    async def fetch_one(self, sql, params=None):
        key = ("one", sql, tuple(params) if params else ())
        if key not in self._memo:
            self._memo[key] = await self._db.fetch_one(sql, params)
        return self._memo[key]


def _team_word(winner: int) -> str:
    return "AXIS" if winner == 1 else "ALLIES"


async def collect_round(db, rid: int, meta: dict, *, cadence_ms: int, provider: los.GeometryProvider | None) -> list[dict]:
    mdb = MemoDb(db)
    tracks = await rws.load_round_tracks(mdb, rid)
    if not tracks:
        return []
    engagements = await rws.load_round_engagements(mdb, rid)
    policy = await rws.load_capture_policy(mdb, rid)
    end_ms = await rws.load_round_end_ms(mdb, rid, tracks)
    first = max(0, min((t[4] for lives in tracks.values() for t in lives if t[4] is not None), default=0))
    if not end_ms or end_ms <= first:
        return []
    velocity_max_dt = policy.observation_interval_ms * rws.VELOCITY_MAX_DT_INTERVALS if policy.observation_interval_ms else None
    tracer = None
    if provider is not None:
        tracer, _label = await provider.tracer_for(meta["map"])
    acc: dict[str, dict[str, float]] = {}
    for t in range(first, end_ms, cadence_ms):
        snap = rws.build_snapshot(tracks, t, engagements=engagements, velocity_max_dt_ms=velocity_max_dt)
        alive = {g: p for g, p in snap.players.items() if p.alive and p.x is not None}
        if not alive:
            continue
        sep = rws.nearest_teammate_separation(snap)
        clock = await rws.load_round_clock(mdb, rid, t)
        info = await rws.load_round_information_state(mdb, rid, t, snap, clock, policy, tracks)
        holders = info.get("holders", {})
        los_by_edge = los.line_of_sight_for_edges(snap.players, snap.edges, tracer) if tracer is not None else {}
        exposed: set[str] = set()
        for (a, b), v in los_by_edge.items():
            if v["b_to_a"]["status"] == "clear":
                exposed.add(a)
            if v["a_to_b"]["status"] == "clear":
                exposed.add(b)
        for g, p in alive.items():
            a = acc.setdefault(g, {"alive": 0, "moving": 0, "isolated": 0, "blind_moving": 0, "exposed": 0, "exposed_measured": 0, "wave_measured": 0, "push_into_wave": 0, "team": p.team or ""})
            a["alive"] += 1
            moving = (p.speed or 0.0) > MOVING_UPS
            if moving:
                a["moving"] += 1
            d = sep.get(g)
            if d is None or d > ISOLATION_UNITS:
                a["isolated"] += 1
            h = holders.get(g)
            # "Blind" = no enemy the holder could PLACE: a belief that names a
            # subject, carries a region inside the published horizon and still
            # counts as known. known_enemy_count alone would not do — a public
            # obituary names an enemy without placing him, so it is rarely 0
            # (probe 2026-09-09: 0.0 for 20 of 22 rows).
            if moving and h is not None:
                horizon = h.get("position_claim_max_radius") or float("inf")
                placeable = any(
                    b.get("subject_guid") and b.get("region") and b.get("counts_as_known")
                    and b["region"].get("radius", float("inf")) <= horizon
                    for b in h.get("beliefs", [])
                )
                if not placeable:
                    a["blind_moving"] += 1
            if tracer is not None:
                a["exposed_measured"] += 1
                if g in exposed:
                    a["exposed"] += 1
            enemy = "ALLIES" if (p.team or "").upper() == "AXIS" else "AXIS"
            ec = clock.get(enemy) or {}
            if moving and ec.get("status") == "validated" and ec.get("interval_ms") and ec.get("time_to_next_wave_ms") is not None:
                a["wave_measured"] += 1
                if ec["time_to_next_wave_ms"] < WAVE_IMMINENT_SHARE * ec["interval_ms"]:
                    a["push_into_wave"] += 1
    dpm_rows = await db.fetch_all(DPM_SQL, (rid,))
    dpm = {}
    for guid, dmg, secs in dpm_rows:
        if guid and secs and secs > 0:
            dpm[str(guid)] = float(dmg or 0) * 60.0 / float(secs)
    winner = _team_word(meta["winner"])
    rows = []
    for g, a in acc.items():
        if a["alive"] < 6:  # fewer than 30 s alive at a 5 s cadence: not a measurement of anything
            continue
        rng = random.Random(f"{SEED}:{rid}:{g}")  # noqa: S311 — the negative control
        rows.append({
            "block": meta["block"], "round_id": rid, "player": g, "team": a["team"],
            "won": 1 if (a["team"] or "").upper() == winner else 0,
            "order_key": f"{meta['date']} {meta['time']}",
            "map": meta["map"],
            "metrics": {
                "dpm": dpm.get(g[:8]) or dpm.get(g),
                "noise": rng.random(),
                "moving_share": a["moving"] / a["alive"],
                "isolation_share": a["isolated"] / a["alive"],
                "blind_moving_share": (a["blind_moving"] / a["moving"]) if a["moving"] >= 6 else None,
                "exposure_share": (a["exposed"] / a["exposed_measured"]) if a["exposed_measured"] else None,
                "push_into_wave_share": (a["push_into_wave"] / a["wave_measured"]) if a["wave_measured"] >= 6 else None,
            },
            "samples": {"alive": a["alive"], "moving": a["moving"], "exposed_measured": a["exposed_measured"], "wave_measured": a["wave_measured"]},
        })
    return rows


async def collect(args) -> None:
    from website.backend import dependencies as dep
    await dep.init_db_pool()
    db = dep.get_db_pool()
    rounds = await db.fetch_all(ROUNDS_SQL)
    if args.limit:
        rounds = rounds[: args.limit]
    provider = None if args.skip_los else los.GeometryProvider()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists() and args.resume:
        with out.open() as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["round_id"])
                except (ValueError, KeyError):
                    continue
    t_start = time.perf_counter()
    n_rows = 0
    with out.open("a") as fh:
        for i, (rid, gsid, map_name, winner, rdate, rtime, rnum) in enumerate(rounds, 1):
            if rid in done:
                continue
            t0 = time.perf_counter()
            try:
                rows = await collect_round(db, int(rid), {"block": int(gsid), "map": map_name, "winner": int(winner), "date": rdate, "time": rtime}, cadence_ms=args.cadence_ms, provider=provider)
            except Exception as exc:  # noqa: BLE001 — one bad round must not end the walk; it is named
                print(f"round {rid} ({map_name}) FAILED: {type(exc).__name__}: {exc}", flush=True)
                continue
            for r in rows:
                fh.write(json.dumps(r) + "\n")
            fh.flush()
            n_rows += len(rows)
            print(f"[{i}/{len(rounds)}] round {rid} {map_name} R{rnum} gsid {gsid}: {len(rows)} rows in {time.perf_counter() - t0:.1f} s", flush=True)
    print(f"collected {n_rows} rows in {time.perf_counter() - t_start:.0f} s → {out}")


def _fmt(x: float | None, digits: int = 3) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:+.{digits}f}"


def analyse(args) -> None:
    rows: list[Row] = []
    with Path(args.rows).open() as fh:
        for line in fh:
            d = json.loads(line)
            rows.append(Row(block=d["block"], round_id=d["round_id"], player=d["player"], won=d["won"], metrics=d["metrics"], order_key=d["order_key"]))
    result = l4.analyse(rows, CANDIDATES, resamples=args.resamples, seed=SEED)
    filters = [
        "rounds: round_number in (1, 2), is_valid not false, not a bot round, winner_team in (1, 2), gaming_session_id set, ≥ 1 linked player_track",
        f"players: ≥ 6 alive samples at a {args.cadence_ms} ms cadence (30 s alive); moving-based shares need ≥ 6 moving samples; wave share needs a validated enemy clock",
        "exposure: only on maps with a BSP in the indexed etmain tree; else null",
    ]
    man = l4.manifest(CANDIDATES, cutoff=result["cutoff"], outcome="the player's team is rounds.winner_team (1 = Axis, 2 = Allies) for that round",
                      filters=filters, seed=SEED, resamples=args.resamples,
                      extra={"cadence_ms": args.cadence_ms, "rows": len(rows), "blocks": result["blocks"], "collected_from": str(Path(args.rows).name)})
    lines = [
        f"# Layer 4 family — §8 table ({time.strftime('%Y-%m-%d')})", "",
        f"manifest sha256 `{man['sha256']}` · rows {len(rows)} · blocks discovery {result['blocks']['discovery']} / confirmation {result['blocks']['confirmation']} · confirmation starts at `{result['cutoff']}` · {args.resamples} block resamples, seed {SEED}", "",
        "| candidate | kind | expected | discovery: effect (rounds) [ci95] | confirmation: effect (rounds) [ci95] [simultaneous 95] | verdict |",
        "|---|---|---|---|---|---|",
    ]
    for t in result["table"]:
        d, c = t["discovery"], t["confirmation"]
        ci = lambda x: f"[{_fmt(x[0])}, {_fmt(x[1])}]" if x else "—"  # noqa: E731
        lines.append(f"| `{t['id']}` | {t['kind']} | {t['expected']} | {_fmt(d['point'])} ({d['rounds']}) {ci(d['ci95'])} | {_fmt(c['point'])} ({c['rounds']}) {ci(c['ci95'])} {ci(c['sim95'])} | **{t['verdict']}** |")
    lines += ["", "effect = mean over rounds of (win rate of the upper median half − lower half) on that metric, within the round (§8.1); intervals from a block bootstrap over gaming_session_id (§8.2); the simultaneous interval is max-T over the whole family (§8.4). A candidate ships only with the frozen direction in both splits AND a simultaneous confirmation interval that excludes zero.", ""]
    for c in CANDIDATES:
        lines.append(f"- `{c.id}` ({c.kind}, expected {c.expected_direction}): {c.formula}; parameters `{json.dumps(c.parameters)}`")
    Path(args.out_md).write_text("\n".join(lines) + "\n")
    Path(args.out_manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_manifest).write_text(json.dumps({**man, "result": result}, indent=1, ensure_ascii=False) + "\n")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--out", required=True)
    c.add_argument("--limit", type=int, default=0)
    c.add_argument("--cadence-ms", type=int, default=DEFAULT_CADENCE_MS)
    c.add_argument("--skip-los", action="store_true")
    c.add_argument("--resume", action="store_true")
    a = sub.add_parser("analyse")
    a.add_argument("--rows", required=True)
    a.add_argument("--out-md", required=True)
    a.add_argument("--out-manifest", required=True)
    a.add_argument("--resamples", type=int, default=RESAMPLES)
    a.add_argument("--cadence-ms", type=int, default=DEFAULT_CADENCE_MS)
    args = ap.parse_args()
    if args.cmd == "collect":
        os.environ.setdefault("SSH_ENABLED", "false")
        asyncio.run(collect(args))
    else:
        analyse(args)


if __name__ == "__main__":
    main()
