#!/usr/bin/env python3
"""Export objective coordinate zones for web minimap overlays."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        default="proximity/objective_coords_from_etmain.json",
        help="Objective coordinates JSON source.",
    )
    parser.add_argument(
        "--output",
        default="website/assets/maps/proximity/objective_zones.json",
        help="Output path for zone config.",
    )
    parser.add_argument(
        "--radius",
        type=int,
        default=500,
        help="Default objective zone radius in world units.",
    )
    return parser.parse_args()


def normalize_name(name: str) -> str:
    out = []
    prev_us = False
    for ch in (name or "").lower():
        if ch.isalnum():
            out.append(ch)
            prev_us = False
        else:
            if not prev_us:
                out.append("_")
                prev_us = True
    return "".join(out).strip("_") or "objective"


def main() -> int:
    logger.info("Script started: %s", __file__)
    args = parse_args()
    source_path = Path(args.source)
    out_path = Path(args.output)
    if not source_path.exists():
        raise FileNotFoundError(f"Missing source: {source_path}")

    payload = json.loads(source_path.read_text(encoding="utf-8"))
    maps = payload.get("maps", {})

    zone_maps: dict[str, Any] = {}
    total = 0

    for map_name, rows in sorted(maps.items()):
        normalized = map_name.lower()
        objectives = []
        seen_ids = set()
        for row in rows:
            x = row.get("x")
            y = row.get("y")
            z = row.get("z")
            if x is None or y is None or z is None:
                continue
            base = row.get("lua_name") or normalize_name(row.get("name", "objective"))
            obj_id = f"{normalized}:{base}"
            if obj_id in seen_ids:
                continue
            seen_ids.add(obj_id)
            objectives.append(
                {
                    "id": obj_id,
                    "name": row.get("name") or base,
                    "lua_name": base,
                    "type": row.get("type") or "objective",
                    "target": row.get("target"),
                    "x": float(x),
                    "y": float(y),
                    "z": float(z),
                    "radius": int(args.radius),
                    "source_pk3": row.get("source_pk3"),
                }
            )
        if not objectives:
            continue

        entry = {
            "map_name": map_name,
            "aliases": sorted({map_name, normalized}),
            "objectives": objectives,
        }
        zone_maps[map_name] = entry
        zone_maps[normalized] = entry
        total += len(objectives)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "meta": {
            "source": str(source_path),
            "map_count": len({k for k in zone_maps.keys() if k == k.lower()}),
            "objective_count": total,
            "default_radius": int(args.radius),
        },
        "maps": zone_maps,
    }
    out_path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({out['meta']['map_count']} maps, {total} objectives)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
