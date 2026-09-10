#!/usr/bin/env python3
"""Export walkable floor polygons per map, for the Spider Web view. READ-ONLY.

The proximity overlay draws players on a levelshot — a photograph of the map
from above, with no height in it at all. Two players thirty metres apart
vertically land on the same pixel, and a round on a map like `te_escape2`
(z from -1090 to 1056) reads as a flat plane. The Spider Web needs the shape of
the place, not a picture of it.

WHAT IS EXPORTED, AND WHY ONLY THIS

The BSP carries the whole level: 5,587 surfaces on supply, 12,573 on
etl_adlernest, roughly 100,000 vertices each. Almost all of it is walls,
trim, decoration and sky — detail that a tactical view does not want and a
browser should not download. What a reader needs is the FLOOR: the surfaces a
player can stand on, at their true height.

So a surface is kept when all of these hold:
  * it is PLANAR (patches and triangle soups are curves and clutter);
  * its normal points up (`normal[2] >= FLOOR_NORMAL_Z`) — a floor, not a wall
    or a ceiling;
  * its shader is drawn and solid — no SURF_SKY, SURF_NODRAW, SURF_SKIP, and
    no SURF_NONSOLID, whose values are read from the engine's own
    `src/game/surfaceflags.h` rather than remembered.

That leaves 961 polygons on supply and 2,219 on etl_adlernest: about 20-50 kB
gzipped per map, which is a page asset rather than a download.

⛔ THE MANIFEST NAMES WHAT IT COULD NOT EXPORT. A map missing from the output
is indistinguishable from a map with no floors, and the consumer would draw an
empty stage either way. Every map asked for appears in the manifest, with a
reason when it produced nothing.

⚠️ Precomputed on purpose. Parsing one BSP costs 335-885 ms, so doing it per
request would put a second of CPU behind every scrub of the time slider.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.map_geometry import SurfaceType  # noqa: E402
from website.backend.map_geometry.pk3_index import Pk3GeometryIndex  # noqa: E402

#: From `src/game/surfaceflags.h` (ET:Legacy, commit 732518ef). Copied with
#: their names so a reader can grep the engine for them.
SURF_SKY = 0x00000004
SURF_NODRAW = 0x00000080
SURF_SKIP = 0x00000200
SURF_NONSOLID = 0x00004000
SURF_EXCLUDED = SURF_SKY | SURF_NODRAW | SURF_SKIP | SURF_NONSOLID

#: How steep a surface may be and still count as floor. cos(45°) is 0.707, so
#: this keeps anything a player can walk up and drops walls and ceilings.
#: ⚠️ A named model parameter, not a measurement — it decides what "floor"
#: means and there is nothing in the engine that defines it for us.
FLOOR_NORMAL_Z = 0.7

#: Coordinates are rounded to whole game units before writing. A player is
#: about 40 units wide, so a tenth of a unit is noise that costs bytes.
COORD_DECIMALS = 0


#: Triangles below this XY area are dropped, in square game units. A player
#: stands on a 36x36 footprint, so a four-unit sliver is a tessellation
#: artefact rather than floor — invisible at map scale and pure bytes.
MIN_TRIANGLE_AREA = 16.0


def floor_triangles(bsp) -> tuple[list, dict]:
    """Every upward-facing planar floor, as triangles of (x, y, z).

    ⛔ TRIANGLES FROM `draw_indexes`, NEVER THE VERTEX ORDER. The stored
    vertex run for a surface is not the polygon's boundary: taking
    `draw_vertices[first : first + count]` as a ring turns an ordinary
    56x56 quad into a bow-tie. Measured before anything was drawn — the median
    XY area of "polygons" read that way was **zero**, which is impossible for a
    surface whose normal points up, while the same quad through its indexes
    measures 3,136 units. Rendering the vertex order would have drawn every
    floor in the game as shattered glass.

    Returns the triangles and a rejection tally, because "3,518 triangles"
    alone cannot say whether the filter is working or eating the map.
    """
    triangles: list[list[list[float]]] = []
    rejected = {"not_planar": 0, "degenerate": 0, "not_floor": 0,
                "shader": 0, "sliver": 0}

    # ⛔ MODEL 0 ONLY — the world. Models 1..n are brush entities: doors, lifts,
    # movers, breakables. They sit in the BSP at their EDITOR position, which
    # for a lift is one end of a journey it spends the round away from, so
    # drawing them as static floor puts ground where there is none. 537 of
    # etl_sp_delivery's 14,317 surfaces belong to its 53 brush entities, and
    # including them scattered the standing height there (spread 154 units
    # against 16-50 elsewhere). Their real positions need entity state we do
    # not reconstruct (spec §9).
    world = bsp.models[0]
    for surface in bsp.surfaces[world.first_surface:
                                world.first_surface + world.num_surfaces]:
        if surface.surface_type != SurfaceType.PLANAR:
            rejected["not_planar"] += 1
            continue
        if surface.num_vertices < 3 or surface.num_indexes < 3:
            rejected["degenerate"] += 1
            continue

        shader = bsp.shaders[surface.shader_index]
        if shader.surface_flags & SURF_EXCLUDED:
            rejected["shader"] += 1
            continue

        # The surface normal, taken from its first vertex. For a PLANAR surface
        # every vertex carries the same normal by construction, so this is the
        # plane's normal and not one corner's idea of it.
        if bsp.draw_vertices[surface.first_vertex].normal[2] < FLOOR_NORMAL_Z:
            rejected["not_floor"] += 1
            continue

        indexes = bsp.draw_indexes[
            surface.first_index:surface.first_index + surface.num_indexes
        ]
        for i in range(0, len(indexes) - 2, 3):
            corners = [
                bsp.draw_vertices[surface.first_vertex + indexes[i + k]].position
                for k in range(3)
            ]
            if triangle_area_xy(corners) < MIN_TRIANGLE_AREA:
                rejected["sliver"] += 1
                continue
            triangles.append([
                [round(c[0], COORD_DECIMALS), round(c[1], COORD_DECIMALS),
                 round(c[2], COORD_DECIMALS)]
                for c in corners
            ])

    return triangles, rejected


def median_triangle_area(triangles: list) -> float:
    """Typical footprint of an exported triangle. REPORTED, NOT A GATE.

    ⚠️ It was written as a gate and it could not fail. The corner-order bug
    produces degenerate triangles, and `MIN_TRIANGLE_AREA` discards those
    before this median is taken — so the survivors always look healthy while
    more than half the map has silently vanished (3,332 triangles against
    1,424). A filter upstream of a check guarantees the check passes.

    Two other intrinsic statistics were measured and rejected for the same job:
    the sliver rejection rate barely moves (5.3% correct against 9.9% wrong on
    supply), and bounding-box coverage overlaps between the two cases (a
    correct supply reads 60.3%, a wrong decay_sw reads 60.9%). No cheap number
    computed from the export alone separates them.

    ⭐ The check that does is EXTERNAL: players must stand on the floor. That
    lives in `scripts/verify_map_geometry.py`, which compares exported floors
    against recorded player positions — evidence the export cannot fake.
    """
    if not triangles:
        return 0.0
    areas = sorted(triangle_area_xy(t) for t in triangles)
    return areas[len(areas) // 2]


def triangle_area_xy(corners: list) -> float:
    """Footprint area seen from above — the only area that matters here."""
    (x1, y1, _), (x2, y2, _), (x3, y3, _) = corners
    return abs((x2 - x1) * (y3 - y1) - (x3 - x1) * (y2 - y1)) / 2.0


def to_indexed_mesh(triangles: list) -> dict:
    """A deduplicated vertex pool plus index triples.

    ⭐ Measured on the three largest maps: the pool holds about 38% of the
    corners the triangles reference (4,022 of 10,554 on supply), because floors
    share their corners heavily. Writing each corner out in full costs 144 kB
    on supply against 101 kB indexed, and the indexed form is also what a
    renderer wants — one flat run of numbers to walk.
    """
    pool: dict[tuple, int] = {}
    vertices: list[int] = []
    indexes: list[int] = []
    for triangle in triangles:
        for corner in triangle:
            key = (corner[0], corner[1], corner[2])
            position = pool.get(key)
            if position is None:
                position = pool[key] = len(pool)
                vertices.extend(int(c) for c in key)
            indexes.append(position)
    return {"vertices": vertices, "indexes": indexes}


def bounds_of(triangles: list) -> dict | None:
    """The extent the renderer has to fit on screen.

    Computed here rather than in the browser: the client would have to walk
    every vertex to find it, and the answer never changes.
    """
    if not triangles:
        return None
    xs = [p[0] for tri in triangles for p in tri]
    ys = [p[1] for tri in triangles for p in tri]
    zs = [p[2] for tri in triangles for p in tri]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--etmain", type=Path, default=Path("/home/samba/share/etmain"))
    ap.add_argument("--out", type=Path,
                    default=ROOT / "website/assets/maps/geometry")
    ap.add_argument("--maps", nargs="*",
                    help="map names to export; default is every map in the index")
    ap.add_argument("--publish", nargs="*",
                    help="write files only for these maps; the rest are still "
                         "measured and named in the manifest as unpublished")
    ap.add_argument("--dry-run", action="store_true",
                    help="measure and report, write nothing")
    args = ap.parse_args()

    index = Pk3GeometryIndex.scan(args.etmain)
    available = set(index.map_names)
    wanted = list(args.maps) if args.maps else sorted(available)

    entries: dict[str, dict] = {}
    failures: list[str] = []
    print(f"  {'mapa':<22s} {'trikotnikov':>12s} {'vertexov':>9s} {'kB':>7s}  opomba")
    for name in wanted:
        if name not in available:
            # ⛔ Named, not dropped. A map that has no BSP in etmain is a fact
            # the page needs, so it can say "no geometry" instead of drawing an
            # empty stage that looks like an empty round.
            entries[name] = {"available": False,
                             "reason": "no BSP for this map in the indexed etmain tree"}
            print(f"  {name:<22s} {'—':>12s} {'—':>9s} {'—':>7s}  ⚠️ ni BSP")
            continue

        bsp = index.load_bsp(name)
        polygons, rejected = floor_triangles(bsp)
        payload = {
            "map_name": name,
            **to_indexed_mesh(polygons),
            "bounds": bounds_of(polygons),
            "floor_normal_z": FLOOR_NORMAL_Z,
            "source": bsp.source,
        }
        blob = json.dumps(payload, separators=(",", ":"))
        vertices = len(payload["vertices"]) // 3
        median_area = median_triangle_area(polygons)

        # ⛔ A map we chose not to ship is NAMED as unpublished, not dropped from
        # the manifest. Dropping it would make "we did not publish this" and
        # "this map has no floors" the same fact to a reader, and the page
        # would have no way to say which one it is looking at.
        published = args.publish is None or name in args.publish

        note = ""
        if not polygons:
            note = "⚠️ nobene talne ploskve"
        elif not published:
            note = "· ni objavljena (redko igrana)"

        entries[name] = {
            "available": bool(polygons) and published,
            "published": published,
            "triangles": len(polygons),
            "vertices": vertices,
            "bytes": len(blob),
            "median_triangle_area": round(median_area, 1),
            "rejected": rejected,
            "file": f"{name}.json",
            **({"reason": "no upward-facing planar surfaces survived the filter"}
               if not polygons else {}),
            **({"reason": "measured but not published: too few rounds to justify "
                          "the bytes in a public repository"}
               if polygons and not published else {}),
        }
        print(f"  {name:<22s} {len(polygons):>12d} {vertices:>9d} "
              f"{len(blob)/1024:>7.0f}  {note}")

        if not args.dry_run and polygons and published:
            args.out.mkdir(parents=True, exist_ok=True)
            (args.out / f"{name}.json").write_text(blob)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "script": "scripts/export_map_geometry.py",
        "etmain": str(args.etmain),
        "floor_normal_z": FLOOR_NORMAL_Z,
        "min_triangle_area": MIN_TRIANGLE_AREA,
        "surface_flags_excluded": {
            "SURF_SKY": SURF_SKY, "SURF_NODRAW": SURF_NODRAW,
            "SURF_SKIP": SURF_SKIP, "SURF_NONSOLID": SURF_NONSOLID,
        },
        "maps": entries,
    }
    if not args.dry_run:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "manifest.json").write_text(json.dumps(manifest, indent=1))
        print(f"\n  zapisano v {args.out}")
    else:
        print("\n  (dry-run: nič zapisano)")

    if failures:
        print("\n  ⛔ MAPE, KI NISO PRESTALE PREVERBE PLOŠČINE:")
        for f in failures:
            print(f"      {f}")

    missing = [n for n, e in entries.items() if not e.get("available")]
    print(f"  map: {len(entries)}   brez geometrije: {len(missing)}"
          + (f" → {', '.join(missing)}" if missing else ""))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
