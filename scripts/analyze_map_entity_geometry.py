#!/usr/bin/env python3
"""Publish a deterministic, read-only W3 entity-geometry inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from website.backend.map_geometry import (
    MapAssetKind,
    Pk3GeometryIndex,
    entity_catalog_manifest,
    extract_entity_catalog,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--etmain-dir",
        type=Path,
        default=Path("/home/samba/share/etmain"),
        help="ET main directory containing PK3 archives",
    )
    parser.add_argument("--output", type=Path, required=True, help="JSON evidence path")
    parser.add_argument(
        "--map",
        dest="maps",
        action="append",
        default=[],
        help="Map to include; repeat for several maps. Defaults to every indexed BSP map.",
    )
    return parser.parse_args()


def _content_hash(payload: dict) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def build_inventory(index: Pk3GeometryIndex, map_names: list[str] | None = None) -> dict:
    resolutions = index.resolve_many(map_names if map_names else index.map_names)
    maps: dict[str, dict] = {}
    status_counts = {"measured": 0, "no_geometry": 0, "ambiguous_geometry": 0}
    totals = {
        "spawn_points": 0,
        "objective_volumes": 0,
        "objective_markers": 0,
        "collision_entities": 0,
    }

    for geometry in resolutions:
        map_name = geometry.map_name
        if geometry.status != "geometry":
            status_counts[geometry.status] += 1
            maps[geometry.map_name] = {
                "map_name": geometry.map_name,
                "status": geometry.status,
                "reason": geometry.reason,
                "spawn_points": None,
                "objective_volumes": None,
                "objective_markers": None,
                "collision_entities": None,
            }
            continue

        selected = geometry.selected
        if selected is None:
            raise RuntimeError(f"geometry resolution for {geometry.map_name!r} has no selected provider")
        catalog = extract_entity_catalog(index.load_bsp(map_name), map_name)
        publication = entity_catalog_manifest(catalog)
        relative_pk3 = selected.pk3_path.relative_to(index.etmain_dir)
        stable_source = f"{relative_pk3.as_posix()}!/{selected.member}"
        publication["bsp_source"] = stable_source
        publication["bsp_sha256"] = selected.sha256
        publication["bsp_provider"] = stable_source
        maps[geometry.map_name] = publication
        status_counts["measured"] += 1
        totals["spawn_points"] += len(catalog.spawn_points)
        totals["objective_volumes"] += len(catalog.objective_volumes)
        totals["objective_markers"] += len(catalog.objective_markers)
        totals["collision_entities"] += len(catalog.collision_entities)

    payload = {
        "protocol": "map-entity-geometry-v1",
        "asset_kind": MapAssetKind.BSP.value,
        "maps": maps,
        "summary": {
            "requested_maps": len(resolutions),
            "status_counts": status_counts,
            **totals,
        },
    }
    return {
        **payload,
        "etmain_dir": str(index.etmain_dir),
        "content_manifest_sha256": _content_hash(payload),
    }


def main() -> None:
    args = _parse_args()
    index = Pk3GeometryIndex.scan(args.etmain_dir)
    inventory = build_inventory(index, args.maps or None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(inventory["summary"], indent=2, sort_keys=True))
    print(f"content_manifest_sha256={inventory['content_manifest_sha256']}")


if __name__ == "__main__":
    main()
