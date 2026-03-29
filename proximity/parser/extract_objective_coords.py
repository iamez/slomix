#!/usr/bin/env python3
"""Extract ET objective coordinates from BSP entities inside PK3 archives.

This script scans an ET:Legacy etmain directory, loads maps/*.bsp from each
PK3, reads the entity lump, and resolves objective markers from
trigger_objective_info entities.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

KV_RE = re.compile(r'"([^"]*)"\s+"([^"]*)"')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--etmain-dir",
        default="/home/samba/share/etmain",
        help="Path to etmain directory containing .pk3 files.",
    )
    parser.add_argument(
        "--map-template",
        default="proximity/objective_coords_template.json",
        help="JSON file used to filter map names (set empty string to disable filter).",
    )
    parser.add_argument(
        "--output",
        default="proximity/objective_coords_from_etmain.json",
        help="Output JSON path.",
    )
    parser.add_argument(
        "--include-unfiltered",
        action="store_true",
        help="Include all maps found in PK3 files (ignore template filtering).",
    )
    return parser.parse_args()


def parse_entities(entity_blob: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    current: dict[str, str] | None = None

    for raw_line in entity_blob.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "{":
            current = {}
            continue
        if line == "}":
            if current is not None:
                entities.append(current)
            current = None
            continue
        if current is None:
            continue

        match = KV_RE.search(line)
        if match:
            current[match.group(1)] = match.group(2)

    return entities


def entities_from_bsp_bytes(bsp_bytes: bytes) -> list[dict[str, str]]:
    if len(bsp_bytes) < 16:
        return []

    # Lump 0 (entities) starts at byte offset 8 in ET BSP header.
    ent_offset, ent_length = struct.unpack_from("<ii", bsp_bytes, 8)
    if ent_offset < 0 or ent_length <= 0 or ent_offset + ent_length > len(bsp_bytes):
        return []

    chunk = bsp_bytes[ent_offset : ent_offset + ent_length]
    return parse_entities(chunk.decode("latin1", errors="ignore"))


def load_map_filter(map_template: str) -> set[str]:
    if not map_template:
        return set()

    template_path = Path(map_template)
    if not template_path.exists():
        return set()

    with template_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    maps = payload.get("maps", {})
    return {str(name).lower() for name in maps}


def parse_origin(origin: str) -> tuple[float, float, float] | None:
    parts = origin.strip().split()
    if len(parts) != 3:
        return None
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]))
    except ValueError:
        return None


def to_lua_name(name: str) -> str:
    sanitized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return sanitized or "objective"


def resolve_origin(start_target: str, by_targetname: dict[str, list[dict[str, str]]]) -> str | None:
    if not start_target:
        return None

    queue: deque[str] = deque([start_target])
    seen: set[str] = set()

    while queue:
        target = queue.popleft()
        if target in seen:
            continue
        seen.add(target)

        for ent in by_targetname.get(target, []):
            origin = ent.get("origin")
            if origin:
                return origin
            next_target = ent.get("target")
            if next_target and next_target not in seen:
                queue.append(next_target)

    return None


def classify_type(name: str) -> str:
    lower = name.lower()
    if "command post" in lower or lower.endswith("cp"):
        return "command_post"
    if "truck" in lower or "tank" in lower or "escort" in lower:
        return "escort"
    return "objective"


def scan_etmain(etmain_dir: str, allowed_maps: set[str], include_unfiltered: bool) -> dict[str, Any]:
    etmain_path = Path(etmain_dir)
    if not etmain_path.exists():
        raise FileNotFoundError(f"etmain directory not found: {etmain_dir}")

    output_maps: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for entry in sorted(etmain_path.iterdir()):
        if entry.suffix.lower() != ".pk3":
            continue

        try:
            archive = zipfile.ZipFile(entry)
        except zipfile.BadZipFile:
            continue

        with archive:
            bsp_names = [
                name
                for name in archive.namelist()
                if name.lower().startswith("maps/") and name.lower().endswith(".bsp")
            ]

            for bsp_name in bsp_names:
                map_name = Path(bsp_name).stem
                map_key = map_name.lower()
                if not include_unfiltered and allowed_maps and map_key not in allowed_maps:
                    continue

                try:
                    bsp_bytes = archive.read(bsp_name)
                except KeyError:
                    continue

                entities = entities_from_bsp_bytes(bsp_bytes)
                if not entities:
                    continue

                by_targetname: dict[str, list[dict[str, str]]] = defaultdict(list)
                for ent in entities:
                    targetname = ent.get("targetname")
                    if targetname:
                        by_targetname[targetname].append(ent)

                discovered: list[dict[str, Any]] = []
                for ent in entities:
                    if ent.get("classname") != "trigger_objective_info":
                        continue

                    display_name = (
                        ent.get("shortname")
                        or ent.get("track")
                        or ent.get("message")
                        or ent.get("target")
                        or "objective"
                    )

                    target = ent.get("target", "")
                    origin = ent.get("origin") or resolve_origin(target, by_targetname)
                    if not origin:
                        origin = resolve_origin(ent.get("targetname", ""), by_targetname)
                    if not origin:
                        continue

                    coords = parse_origin(origin)
                    if not coords:
                        continue

                    discovered.append(
                        {
                            "name": display_name,
                            "lua_name": to_lua_name(display_name),
                            "target": target,
                            "type": classify_type(display_name),
                            "x": int(coords[0]) if coords[0].is_integer() else coords[0],
                            "y": int(coords[1]) if coords[1].is_integer() else coords[1],
                            "z": int(coords[2]) if coords[2].is_integer() else coords[2],
                            "source_pk3": entry.name,
                            "source_bsp": bsp_name,
                        }
                    )

                seen: set[tuple[Any, ...]] = set()
                for item in discovered:
                    key = (item["name"], item["target"], item["x"], item["y"], item["z"])
                    if key in seen:
                        continue
                    seen.add(key)
                    output_maps[map_name].append(item)

    return {
        "meta": {
            "etmain_dir": str(etmain_path),
            "filtered_by_template": bool(allowed_maps) and not include_unfiltered,
        },
        "maps": dict(sorted(output_maps.items())),
    }


def main() -> int:
    args = parse_args()
    allowed_maps = load_map_filter(args.map_template)
    payload = scan_etmain(args.etmain_dir, allowed_maps, args.include_unfiltered)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    map_count = len(payload.get("maps", {}))
    objective_count = sum(len(v) for v in payload.get("maps", {}).values())
    print(f"Wrote {map_count} maps / {objective_count} objectives to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
