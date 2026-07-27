#!/usr/bin/env python3
"""Build and optionally decode a read-only ET PK3/BSP geometry inventory."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from website.backend.map_geometry import Pk3GeometryIndex, SurfaceType  # noqa: E402


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--etmain-dir",
        default="/home/samba/share/etmain",
        help="Directory tree containing ET .pk3 archives.",
    )
    parser.add_argument(
        "--played-map",
        action="append",
        default=[],
        help="Played map to resolve. Repeat for every map; omitted means all discovered BSP maps.",
    )
    parser.add_argument(
        "--parse",
        action="store_true",
        help="Strictly decode every resolved BSP and include structure counts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write JSON to this path instead of stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    index = Pk3GeometryIndex.scan(args.etmain_dir)
    requested = args.played_map or index.map_names
    manifest = index.manifest(requested)

    if args.parse:
        for map_name, record in manifest["maps"].items():
            if record["status"] != "geometry":
                continue
            bsp = index.load_bsp(map_name)
            record["parsed"] = {
                "magic": bsp.magic.decode("ascii"),
                "version": bsp.version,
                "entities": len(bsp.entities),
                "shaders": len(bsp.shaders),
                "planes": len(bsp.planes),
                "nodes": len(bsp.nodes),
                "leafs": len(bsp.leafs),
                "leaf_surfaces": len(bsp.leaf_surfaces),
                "leaf_brushes": len(bsp.leaf_brushes),
                "models": len(bsp.models),
                "brushes": len(bsp.brushes),
                "brush_sides": len(bsp.brush_sides),
                "draw_vertices": len(bsp.draw_vertices),
                "draw_indexes": len(bsp.draw_indexes),
                "surfaces": len(bsp.surfaces),
                "patch_surfaces": sum(surface.surface_type is SurfaceType.PATCH for surface in bsp.surfaces),
            }

    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
