#!/usr/bin/env python3
"""Build the paired-fixture input for W6, one file per map. READ-ONLY on the DB.

WHAT W6 ACTUALLY ASKS. The 2026-08-20 validation measured our tracer against
recorded kills and got 90.4%. That number is bounded by things which have
nothing to do with our geometry: a bullet uses G_HistoricalTrace with MASK_SHOT
(SOLID|BODY|CORPSE) against antilag positions with entities clipped
(src/game/g_weapon.c:74), while we trace CONTENTS_SOLID through world brushes at
a position quantised to whole units. Every one of those differences pushes the
same way — the engine's bullet had MORE that could stop it — so 90.4% is an
upper bound on our error, not a measurement of it.

A paired fixture removes all of it. `et.trap_Trace(a, {0,0,0}, {0,0,0}, b, -2, 1)`
is a world-only point trace with CONTENTS_SOLID — confirmed on the running engine
2026-08-21, where entNum=-2 walked through a team_WOLF_checkpoint that entNum=-1
was blocked by. Same geometry, same question, same integer coordinates.

⭐ SO THE BAR IS ~100%, NOT 90.4%. Anything below is a bug in OUR tracer, and
this file exists to hand us the exact segment that proves it.

FOUR KINDS OF SEGMENT, and the first is the valuable one:

  blocked  every segment the kill validation called BLOCKED (3,945 across 12
           maps). A kill happened on each of these, so either our geometry is
           wrong, or it is right and the bullet got through on MASK_SHOT /
           antilag / an entity. The engine answering the SAME question settles
           which — turning the 9.6% residual from an unknown into a diagnosis.
  clear    a random sample of segments we called clear, for the headline rate.
  random   random pairs of recorded player positions. Kill segments are a
           biased sample — a kill succeeded there — so without these we would
           only ever measure the parts of a map people shoot across.
  control_down / control_tiny
           answers known before the engine is asked: DOWN (10,000 units down
           from a position a player occupied — they were standing on something,
           so it must block) and TINY (one unit sideways, inside the space they
           already filled, so it must be clear). If a control fails, the capture
           is broken and no other number in the run means anything.

Coordinates are quantised to float32 before anything is traced or written,
because `vec3_t` is `float[3]` (q_math.h:42) and the engine narrows whatever Lua
hands it. Both sides therefore start from the identical number, and a
disagreement can never be blamed on the handoff.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import psycopg2  # noqa: E402

from website.backend.map_geometry import (  # noqa: E402
    LINE_OF_SIGHT_MASK,
    BspPointTracer,
    Pk3GeometryIndex,
    PlayerStance,
    RuntimeGeometryCoverage,  # noqa: E402
    compile_bsp_patches,
    player_eye_point,
)

# The same hitscan set the kill validation used, so "blocked" here means exactly
# what it meant there.
HITSCAN_MODS = (1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 13, 14)

EYE_Z = 56.0  # standing eye height; matches PlayerStance.STANDING and getEyeHeight()


def _require_password() -> str:
    """The database password, from the environment, with no fallback.

    ⛔ There was a default here — the real dev password — put in for the
    convenience of not exporting a variable before each of the dozens of manual
    runs this script was written for. It reached a public repository on
    2026-08-22 when the file was committed without being re-read.

    Failing loudly is the point. An empty-string default would turn a missing
    variable into an authentication error several frames away from its cause,
    which is how a credential ends up back in the source as a "fix".
    """
    password = os.environ.get("POSTGRES_PASSWORD")
    if not password:
        raise SystemExit(
            "POSTGRES_PASSWORD is not set.\n"
            "Export it before running this script — there is deliberately no "
            "default, because a credential in source is a credential in the "
            "repository's history."
        )
    return password


def _connect():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "127.0.0.1"),
        user=os.environ.get("POSTGRES_USER", "etlegacy_user"),
        password=_require_password(),
        dbname=os.environ.get("POSTGRES_DATABASE", "etlegacy"),
    )


def _f32(v: float) -> float:
    """The value the engine will actually trace with.

    `vec3_t` is `float[3]` (q_math.h:42-44), so every coordinate handed to
    et.trap_Trace is narrowed to 32 bits, while our tracer computes on Python
    doubles. Quantising here means both sides start from the identical number
    and a disagreement cannot be blamed on the handoff.

    ⚠️ This exists because an earlier version of this file asserted that all
    coordinates are whole units. The kill columns are `integer`, but
    player_track.path carries one decimal (1172.8), and the claim came from
    looking at a single sample row and generalising — 5,581 non-integer values
    in the first fixture said otherwise.
    """
    return struct.unpack("f", struct.pack("f", float(v)))[0]


def _fmt(v: float) -> str:
    """Shortest text that reads back as the same float32.

    `repr` of a Python float round-trips the double exactly, and because the
    value has already been narrowed by `_f32`, reading it back and narrowing
    again is a no-op. Integral values stay short for readability.
    """
    if float(v).is_integer():
        return str(int(v))
    return repr(v)


def kill_segments(cursor, map_name: str) -> list[tuple]:
    cursor.execute(
        """
        SELECT attacker_x, attacker_y, attacker_z, victim_x, victim_y, victim_z
        FROM proximity_combat_position
        WHERE map_name = %s AND means_of_death = ANY(%s)
          AND attacker_x IS NOT NULL AND victim_x IS NOT NULL
        """,
        (map_name, list(HITSCAN_MODS)),
    )
    return cursor.fetchall()


def track_points(cursor, map_name: str, limit: int) -> list[tuple]:
    cursor.execute(
        """
        SELECT path FROM player_track
        WHERE map_name = %s AND path IS NOT NULL AND sample_count > 3
          AND player_guid NOT LIKE 'OMNIBOT%%'
        ORDER BY random() LIMIT %s
        """,
        (map_name, limit),
    )
    points: list[tuple] = []
    for (raw,) in cursor.fetchall():
        path = raw if isinstance(raw, list) else json.loads(raw)
        points.extend(
            (float(s["x"]), float(s["y"]), float(s.get("z", 0.0)))
            for s in path
            if isinstance(s, dict) and "x" in s and "y" in s
        )
    return points


class FixtureWriter:
    """Rows for ONE map, with the tracer that produced them bound alongside.

    This was a closure over the loop variables until ruff pointed out B023:
    `add()` captured `tracer`, `rows` and `counts` by reference, so it happened
    to be correct only because every call sat inside the same iteration. Binding
    them to an instance removes the footgun instead of silencing it — a deferred
    call would have quietly traced one map's segment through the next map's
    geometry, and nothing in the output would have said so.
    """

    def __init__(self, tracer: BspPointTracer) -> None:
        self.tracer = tracer
        self.rows: list[str] = []
        self.counts = {"blocked": 0, "clear": 0, "random": 0,
                       "control_down": 0, "control_tiny": 0}

    def add(self, kind: str, a: tuple, b: tuple) -> None:
        a = tuple(_f32(c) for c in a)
        b = tuple(_f32(c) for c in b)
        res = self.tracer.trace_segment(a, b, trace_mask=LINE_OF_SIGHT_MASK)
        self.rows.append(" ".join((
            str(len(self.rows)), kind,
            _fmt(a[0]), _fmt(a[1]), _fmt(a[2]),
            _fmt(b[0]), _fmt(b[1]), _fmt(b[2]),
            res.status.value,
            "1" if res.start_solid else "0",
        )))
        self.counts[kind] += 1

    def status_of(self, a: tuple, b: tuple) -> str:
        a = tuple(_f32(c) for c in a)
        b = tuple(_f32(c) for c in b)
        return self.tracer.trace_segment(a, b, trace_mask=LINE_OF_SIGHT_MASK).status.value


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--map", dest="maps", action="append", required=True,
                    help="map to build a fixture for (repeatable)")
    ap.add_argument("--etmain-dir", type=Path, default=Path("/home/samba/share/etmain"))
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--clear-sample", type=int, default=2000)
    ap.add_argument("--random-pairs", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260821)
    args = ap.parse_args()

    # Sampling segments to probe, nothing secret.
    random.seed(args.seed)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    index = Pk3GeometryIndex.scan(args.etmain_dir)
    conn = _connect()
    conn.set_session(readonly=True)
    cursor = conn.cursor()

    for map_name in args.maps:
        if map_name not in index.map_names:
            print(f"  ⚠️ {map_name}: ni geometrije, preskočeno")
            continue

        # The offline verdict is written alongside each segment so the engine's
        # answer can be joined without re-tracing, AND so a later re-trace can
        # prove the offline side is itself reproducible.
        bsp = index.load_bsp(map_name)
        tracer = BspPointTracer(
            bsp,
            patch_collisions=compile_bsp_patches(bsp),
            runtime_entity_completeness=RuntimeGeometryCoverage.VERIFIED,
            runtime_entity_state=RuntimeGeometryCoverage.VERIFIED,
        )
        provider = index.resolve(map_name).selected
        writer = FixtureWriter(tracer)

        kills = kill_segments(cursor, map_name)
        clear_pool = []
        for ax, ay, az, vx, vy, vz in kills:
            a = player_eye_point((float(ax), float(ay), float(az)), PlayerStance.STANDING)
            b = (float(vx), float(vy), float(vz))
            status = writer.status_of(a, b)
            if status == "blocked":
                writer.add("blocked", a, b)   # every one: this is the diagnosis
            elif status == "clear":
                clear_pool.append((a, b))
        for a, b in random.sample(clear_pool, min(args.clear_sample, len(clear_pool))):
            writer.add("clear", a, b)

        pts = track_points(cursor, map_name, 400)
        for _ in range(min(args.random_pairs, max(len(pts) - 1, 0))):
            # Choosing which recorded positions to probe; the seed is published
            # in the fixture header so the selection is reproducible, which is
            # the only property that matters here.
            p = random.choice(pts)  # noqa: S311
            q = random.choice(pts)  # noqa: S311
            if p == q:
                continue
            writer.add("random", (p[0], p[1], p[2] + EYE_Z), (q[0], q[1], q[2] + EYE_Z))

        # Controls last, so a truncated file loses them and the run fails loudly
        # rather than quietly skipping its own falsifier.
        for p in random.sample(pts, min(8, len(pts))):
            eye = (p[0], p[1], p[2] + EYE_Z)
            # ⭐ The expected answer is in the KIND, not in a comment. Both
            # controls used to be written as plain "control", so the comparator
            # could only check that the two sides agreed — and two sides that
            # agree DOWN is clear pass a check that was supposed to catch
            # exactly that (CodeRabbit, PR #797).
            writer.add("control_down", eye, (p[0], p[1], p[2] - 10000.0))
            writer.add("control_tiny", eye, (p[0] + 1.0, p[1], p[2] + EYE_Z))

        # ⛔ A fixture without controls has no falsifier. `track_points` can
        # return nothing (a map with no recorded tracks), and the control loop
        # then samples an empty list and writes none — leaving a file that looks
        # complete and proves nothing (CodeRabbit, #797).
        if not writer.counts["control_down"] or not writer.counts["control_tiny"]:
            raise SystemExit(
                f"{map_name}: no controls were written "
                f"(down={writer.counts['control_down']}, "
                f"tiny={writer.counts['control_tiny']}). A fixture with no "
                f"control cannot fail, so it is not written at all."
            )

        out = args.out_dir / f"{map_name}.txt"
        header = [
            f"# w6 trace fixture map={map_name}",
            f"# bsp_sha256={provider.sha256 if provider else 'unknown'}",
            f"# pk3={provider.pk3_path.name if provider else 'unknown'}",
            f"# seed={args.seed} eye_z={_fmt(EYE_Z)}",
            "# engine call: et.trap_Trace(a, {0,0,0}, {0,0,0}, b, -2, 1)",
            "# idx kind ax ay az bx by bz offline_status offline_startsolid",
        ]
        out.write_text("\n".join(header + writer.rows) + "\n")
        c = writer.counts
        print(f"  {map_name:16s} {len(writer.rows):6d} daljic  "
              f"blocked={c['blocked']} clear={c['clear']} "
              f"random={c['random']} "
              f"control={c['control_down'] + c['control_tiny']}  "
              f"-> {out.name} ({out.stat().st_size // 1024} KB)")
        print(f"                   pk3={provider.pk3_path.name if provider else '?'} "
              f"sha={provider.sha256[:12] if provider else '?'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
