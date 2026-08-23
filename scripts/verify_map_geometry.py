#!/usr/bin/env python3
"""Do the exported floors hold the players who walked on them? READ-ONLY.

`export_map_geometry.py` cannot check itself. Everything computable from its own
output can be satisfied by its own filters: a median triangle area looks healthy
because slivers were already discarded, the sliver rate barely moves between a
correct read and a wrong one (5.3% against 9.9% on supply), and bounding-box
coverage overlaps between the two cases. Each of those was measured and rejected
before this script was written.

⭐ THE EVIDENCE HAS TO COME FROM SOMEWHERE ELSE. `player_track.path` records
where players actually stood, sampled every 200 ms by a completely separate
pipeline that has never read a BSP. A player standing on a floor is a fact the
export cannot manufacture: if the corners of a triangle are read in the wrong
order, the floors land in the wrong places, and the players float or sink.

WHAT IS MEASURED

For each sampled position, find the exported floor triangle directly below it
(the highest one whose footprint contains the point) and record the drop from
the player's feet to that floor. A correct export puts that drop near zero for
almost every sample.

⚠️ Near a constant, not near zero. `path` samples an origin, and in ET:Legacy
the player origin sits above the feet: `playerMins = { -18, -18, -24 }`
(`src/game/g_client.c:53`), so a standing player reads 24 units above the floor.

⭐ THAT NUMBER IS THE VERIFICATION. The first run measured a median of exactly
24 on supply, te_escape2 and etl_adlernest — three maps, one number, and it is
the engine's own constant rather than anything this pipeline could have chosen.
The export and the engine agree about where the ground is, from two sources
that have never read each other.

The SPREAD is what a failure would show: a consistent height means the geometry
is right and the offset is a convention, a scattered one means it is not.

⛔ Samples with no floor beneath them are reported, never dropped. A player over
a gap is either a real hole in the export (a floor we filtered away) or a jump,
and averaging them out of existence would hide precisely the maps where the
export is worst.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.dependencies import get_db_pool, init_db_pool  # noqa: E402

#: How far below a sample a floor may be and still count as the one being stood
#: on. Generous on purpose: this is not a physics check, and a tighter window
#: would reject legitimate stairs and slopes between samples.
MAX_DROP = 512.0

#: A player's origin sits above their feet; anything further above the floor
#: than this is airborne (a jump, a ladder, a fall) rather than standing.
MAX_RISE = 96.0


def load_mesh(path: Path) -> tuple[list, list]:
    data = json.loads(path.read_text())
    return data["vertices"], data["indexes"]


def floors_below(vertices: list, indexes: list, x: float, y: float) -> list[float]:
    """Heights of every exported floor whose footprint contains (x, y)."""
    heights: list[float] = []
    for i in range(0, len(indexes) - 2, 3):
        a, b, c = (indexes[i] * 3, indexes[i + 1] * 3, indexes[i + 2] * 3)
        x1, y1, z1 = vertices[a], vertices[a + 1], vertices[a + 2]
        x2, y2, z2 = vertices[b], vertices[b + 1], vertices[b + 2]
        x3, y3, z3 = vertices[c], vertices[c + 1], vertices[c + 2]
        # Barycentric containment. Cheaper than it looks because the bounding
        # rejection below fires for almost every triangle.
        if x < min(x1, x2, x3) or x > max(x1, x2, x3):
            continue
        if y < min(y1, y2, y3) or y > max(y1, y2, y3):
            continue
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if d == 0:
            continue
        wa = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / d
        wb = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / d
        wc = 1.0 - wa - wb
        if wa < 0 or wb < 0 or wc < 0:
            continue
        heights.append(wa * z1 + wb * z2 + wc * z3)
    return heights


async def sample_positions(db, map_name: str, limit: int) -> list[tuple]:
    rows = await db.fetch_all("""
        SELECT (e->>'x')::float, (e->>'y')::float, (e->>'z')::float
        FROM player_track pt
        JOIN rounds r ON r.id = pt.round_id,
             jsonb_array_elements(pt.path) e
        WHERE r.map_name = $1
          AND jsonb_exists(e, 'x')
          AND e->>'event' IS DISTINCT FROM 'death'
        LIMIT $2
    """, (map_name, limit))
    return [(float(a), float(b), float(c)) for a, b, c in (rows or [])]


async def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--geometry", type=Path,
                    default=ROOT / "website/assets/maps/geometry")
    ap.add_argument("--maps", nargs="*")
    ap.add_argument("--samples", type=int, default=400,
                    help="player positions per map")
    args = ap.parse_args()

    manifest = json.loads((args.geometry / "manifest.json").read_text())
    wanted = args.maps or [n for n, e in manifest["maps"].items() if e.get("available")]

    await init_db_pool()
    db = get_db_pool()

    print(f"  {'mapa':<20s} {'vzorcev':>8s} {'na tleh':>9s} {'višina p50':>11s} "
          f"{'razmik p10–p90':>15s} {'brez tal':>9s}")
    failures: list[str] = []
    for name in sorted(wanted):
        mesh_path = args.geometry / f"{name}.json"
        if not mesh_path.exists():
            print(f"  {name:<20s} ⚠️ ni izvožene geometrije")
            continue
        vertices, indexes = load_mesh(mesh_path)
        positions = await sample_positions(db, name, args.samples)
        if not positions:
            print(f"  {name:<20s} ⚠️ ni zapisanih leg igralcev")
            continue

        rises: list[float] = []
        unsupported = 0
        for x, y, z in positions:
            below = [h for h in floors_below(vertices, indexes, x, y)
                     if z - h <= MAX_DROP and z - h >= -MAX_RISE]
            if not below:
                unsupported += 1
                continue
            rises.append(z - max(below))

        if not rises:
            failures.append(f"{name}: no sample found any floor")
            print(f"  {name:<20s} ⛔ noben vzorec ni našel tal")
            continue

        rises.sort()
        p10, p50, p90 = (rises[len(rises) // 10], rises[len(rises) // 2],
                         rises[(len(rises) * 9) // 10])
        spread = p90 - p10
        share_unsupported = unsupported / len(positions)
        # ⭐ The spread is the verdict, not the offset. A constant height above
        # the floor is the origin convention; a scattered one is wrong geometry.
        bad = spread > 128.0 or share_unsupported > 0.25
        if bad:
            failures.append(
                f"{name}: spread {spread:.0f}, unsupported {100*share_unsupported:.0f}%")
        print(f"  {name:<20s} {len(positions):>8d} {len(rises):>9d} {p50:>11.0f} "
              f"{spread:>15.0f} {100*share_unsupported:>8.0f}%"
              + ("  ⛔" if bad else ""))

    print()
    if failures:
        print("  ⛔ MAPE, KI NE DRŽIJO SVOJIH IGRALCEV:")
        for f in failures:
            print(f"      {f}")
    else:
        print("  ✅ vsaka preverjena mapa drži igralce, ki so po njej hodili")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
