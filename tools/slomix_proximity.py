#!/usr/bin/env python3
"""slomix_proximity.py — Unified proximity coordinate tool for Slomix.

Consolidates 6 proximity scripts into a single CLI with subcommands:
  slomix_proximity.py gate [--template] [--config] [--top-maps] [--print-json]
  slomix_proximity.py export-assets [--manifest] [--etmain-dir] [--out-dir] [--config-name]
  slomix_proximity.py export-zones [--source] [--output] [--radius]
  slomix_proximity.py coords-to-lua [--source]
  slomix_proximity.py sync-placeholders
  slomix_proximity.py update-lua

All paths are resolved relative to the project root.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

# Setup sys.path and load .env
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# SUBCOMMAND: gate
# ============================================================================

def _gate_normalize_map_name(value: str) -> str:
    return (value or "").strip().lower()


def _gate_parse_top_maps_arg(value: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in (value or "").split(","):
        normalized = _gate_normalize_map_name(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _gate_entry_has_complete_xyz(entry: dict[str, Any]) -> bool:
    return entry.get("x") is not None and entry.get("y") is not None and entry.get("z") is not None


def _gate_build_template_index(maps: dict[str, Any]) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    index: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for map_key, entries_raw in maps.items():
        normalized = _gate_normalize_map_name(map_key)
        entries = entries_raw if isinstance(entries_raw, list) else []
        typed_entries: list[dict[str, Any]] = [entry for entry in entries if isinstance(entry, dict)]
        current = index.get(normalized)
        if current is None:
            index[normalized] = (map_key, typed_entries)
            continue
        # Prefer canonical lowercase key when both uppercase/lowercase variants exist.
        if map_key == normalized and current[0] != normalized:
            index[normalized] = (map_key, typed_entries)
    return index


def _gate_map_coverage(map_name: str, template_index: dict[str, tuple[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    record = template_index.get(map_name)
    if record is None:
        return {
            "map_name": map_name,
            "template_key": None,
            "total_entries": 0,
            "complete_entries": 0,
            "incomplete_entries": 0,
            "fully_covered": False,
        }

    template_key, entries = record
    total_entries = len(entries)
    complete_entries = sum(1 for entry in entries if _gate_entry_has_complete_xyz(entry))
    incomplete_entries = total_entries - complete_entries
    fully_covered = total_entries > 0 and incomplete_entries == 0

    return {
        "map_name": map_name,
        "template_key": template_key,
        "total_entries": total_entries,
        "complete_entries": complete_entries,
        "incomplete_entries": incomplete_entries,
        "fully_covered": fully_covered,
    }


def evaluate_gate(
    template_payload: dict[str, Any],
    config_payload: dict[str, Any],
    runtime_top_maps: list[str] | None = None,
) -> dict[str, Any]:
    runtime_top_maps = runtime_top_maps or []

    template_maps = template_payload.get("maps")
    if not isinstance(template_maps, dict):
        raise ValueError("Template JSON must contain a 'maps' object.")

    static_guard_maps_raw = config_payload.get("static_guard_maps", [])
    if not isinstance(static_guard_maps_raw, list):
        raise ValueError("Gate config 'static_guard_maps' must be a list.")
    static_guard_maps = [_gate_normalize_map_name(map_name) for map_name in static_guard_maps_raw if _gate_normalize_map_name(map_name)]

    runtime_config = config_payload.get("runtime", {})
    if runtime_config is None:
        runtime_config = {}
    if not isinstance(runtime_config, dict):
        raise ValueError("Gate config 'runtime' must be an object.")

    allow_todo_raw = runtime_config.get("allow_todo_maps", [])
    if not isinstance(allow_todo_raw, list):
        raise ValueError("Gate config 'runtime.allow_todo_maps' must be a list.")
    allow_todo_maps = {_gate_normalize_map_name(map_name) for map_name in allow_todo_raw if _gate_normalize_map_name(map_name)}

    expected_top_n = runtime_config.get("top_n", 0)
    expected_top_n = int(expected_top_n) if isinstance(expected_top_n, (int, float, str)) and str(expected_top_n).strip() else 0
    if expected_top_n < 0:
        expected_top_n = 0

    template_index = _gate_build_template_index(template_maps)
    errors: list[str] = []
    warnings: list[str] = []

    static_results: list[dict[str, Any]] = []
    for map_name in static_guard_maps:
        coverage = _gate_map_coverage(map_name, template_index)
        static_results.append(coverage)
        if coverage["template_key"] is None:
            errors.append(f"static_guard:{map_name}: missing map entry in template")
            continue
        if coverage["total_entries"] == 0 or coverage["complete_entries"] == 0:
            errors.append(f"static_guard:{map_name}: no complete objective coordinates")
            continue
        if coverage["incomplete_entries"] > 0:
            errors.append(
                f"static_guard:{map_name}: incomplete objective entries "
                f"({coverage['incomplete_entries']}/{coverage['total_entries']})"
            )

    runtime_results: list[dict[str, Any]] = []
    if runtime_top_maps:
        if expected_top_n and len(runtime_top_maps) < expected_top_n:
            warnings.append(
                f"runtime_top_maps: received {len(runtime_top_maps)} maps, "
                f"below configured top_n={expected_top_n}"
            )
        for map_name in runtime_top_maps:
            coverage = _gate_map_coverage(map_name, template_index)
            runtime_results.append(coverage)

            if coverage["fully_covered"]:
                continue

            if map_name in allow_todo_maps:
                warnings.append(f"runtime_top_map:{map_name}: unresolved but allowlisted")
                continue

            if coverage["template_key"] is None:
                errors.append(f"runtime_top_map:{map_name}: missing map entry in template")
            elif coverage["complete_entries"] == 0:
                errors.append(f"runtime_top_map:{map_name}: no complete objective coordinates")
            else:
                errors.append(
                    f"runtime_top_map:{map_name}: incomplete objective entries "
                    f"({coverage['incomplete_entries']}/{coverage['total_entries']})"
                )

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "config": {
            "static_guard_maps": static_guard_maps,
            "runtime_top_n": expected_top_n,
            "runtime_allow_todo_maps": sorted(allow_todo_maps),
        },
        "static_results": static_results,
        "runtime_results": runtime_results,
    }


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def cmd_gate(args):
    template_payload = _load_json(args.template)
    config_payload = _load_json(args.config)
    runtime_top_maps = _gate_parse_top_maps_arg(args.top_maps)

    result = evaluate_gate(
        template_payload=template_payload,
        config_payload=config_payload,
        runtime_top_maps=runtime_top_maps,
    )

    if args.print_json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        status = "PASS" if result["ok"] else "FAIL"
        print(f"[{status}] Objective coordinates gate")
        print(f"  static_guard_maps={len(result['static_results'])}")
        print(f"  runtime_maps_checked={len(result['runtime_results'])}")
        if result["warnings"]:
            print(f"  warnings={len(result['warnings'])}")
            for line in result["warnings"]:
                print(f"    WARN: {line}")
        if result["errors"]:
            print(f"  errors={len(result['errors'])}")
            for line in result["errors"]:
                print(f"    ERR:  {line}")

    return 0 if result["ok"] else 2

# ============================================================================
# SUBCOMMAND: export-assets
# ============================================================================

@dataclass
class MapRecord:
    map_name: str
    pk3: str
    minimap_file: str
    mapcoordsmins: str
    mapcoordsmaxs: str


def _assets_parse_vec2(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    try:
        return [float(parts[0]), float(parts[1])]
    except ValueError:
        return None


def _assets_load_records(manifest_path: Path) -> list[MapRecord]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    maps = payload.get("maps", {})
    records: list[MapRecord] = []
    for map_name, entries in maps.items():
        if not entries:
            continue
        chosen = None
        # Prefer entry with _cc minimap if available.
        for entry in entries:
            minimap_file = entry.get("minimap_file") or ""
            if "_cc" in minimap_file.lower():
                chosen = entry
                break
        if not chosen:
            chosen = entries[0]
        minimap_file = chosen.get("minimap_file")
        pk3 = chosen.get("pk3")
        if not minimap_file or not pk3:
            continue
        records.append(
            MapRecord(
                map_name=map_name,
                pk3=pk3,
                minimap_file=minimap_file,
                mapcoordsmins=chosen.get("mapcoordsmins"),
                mapcoordsmaxs=chosen.get("mapcoordsmaxs"),
            )
        )
    records.sort(key=lambda r: r.map_name.lower())
    return records


def _assets_export_minimap(etmain_dir: Path, out_dir: Path, record: MapRecord) -> dict[str, Any] | None:
    from PIL import Image

    pk3_path = etmain_dir / record.pk3
    if not pk3_path.exists():
        return None

    with zipfile.ZipFile(pk3_path) as archive:
        try:
            data = archive.read(record.minimap_file)
        except KeyError:
            return None

    with Image.open(BytesIO(data)) as image:
        rgba = image.convert("RGBA")
        out_name = f"{record.map_name.lower()}.png"
        out_path = out_dir / out_name
        rgba.save(out_path, format="PNG")
        width, height = rgba.size

    mins = _assets_parse_vec2(record.mapcoordsmins)
    maxs = _assets_parse_vec2(record.mapcoordsmaxs)
    return {
        "map_name": record.map_name,
        "image": f"/assets/maps/proximity/{out_name}",
        "size": [width, height],
        "mapcoordsmins": mins,
        "mapcoordsmaxs": maxs,
        "source_pk3": record.pk3,
        "source_image": record.minimap_file,
    }


def cmd_export_assets(args):
    manifest_path = Path(args.manifest)
    etmain_dir = Path(args.etmain_dir)
    out_dir = Path(args.out_dir)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    if not etmain_dir.exists():
        raise FileNotFoundError(f"Missing etmain dir: {etmain_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    records = _assets_load_records(manifest_path)
    maps: dict[str, Any] = {}
    failures: list[str] = []

    for record in records:
        exported = _assets_export_minimap(etmain_dir, out_dir, record)
        if not exported:
            failures.append(record.map_name)
            continue
        maps[record.map_name] = exported
        maps[record.map_name.lower()] = exported

    config = {
        "meta": {
            "manifest": str(manifest_path),
            "etmain_dir": str(etmain_dir),
            "map_count": len({k for k in maps.keys() if k == k.lower()}),
            "failures": failures,
        },
        "maps": maps,
    }
    config_path = out_dir / args.config_name
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    print(f"Exported maps: {config['meta']['map_count']}")
    print(f"Wrote config: {config_path}")
    if failures:
        print(f"Failed maps ({len(failures)}): {', '.join(sorted(failures))}")
    return 0

# ============================================================================
# SUBCOMMAND: export-zones
# ============================================================================

def _zones_normalize_name(name: str) -> str:
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


def cmd_export_zones(args):
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
            base = row.get("lua_name") or _zones_normalize_name(row.get("name", "objective"))
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

# ============================================================================
# SUBCOMMAND: coords-to-lua
# ============================================================================

def cmd_coords_to_lua(args):
    src = Path(args.source)
    if not src.exists():
        print(f"[ERR] File not found: {src}", file=sys.stderr)
        return 1

    data = json.loads(src.read_text(encoding="utf-8"))
    maps = data.get("maps", {})

    print("objectives = {")
    for map_name in sorted(maps.keys()):
        print(f"    {map_name} = {{")
        entries = maps.get(map_name, [])
        for entry in entries:
            name = entry.get("name", "unknown")
            obj_type = entry.get("type", "objective")
            x, y, z = entry.get("x"), entry.get("y"), entry.get("z")
            if x is None or y is None or z is None:
                print(f"        -- TODO: {map_name}.{name} missing coords")
                continue
            print(
                f"        {{ name = \"{name}\", x = {x}, y = {y}, z = {z}, type = \"{obj_type}\" }},"
            )
        print("    },")
    print("}")
    return 0

# ============================================================================
# SUBCOMMAND: sync-placeholders
# ============================================================================

def cmd_sync_placeholders(args):
    rotation_path = ROOT / "proximity" / "map_rotation.txt"
    template_path = ROOT / "proximity" / "objective_coords_template.json"

    if not rotation_path.exists():
        print(f"[ERR] Missing map rotation list: {rotation_path}")
        return 1
    if not template_path.exists():
        print(f"[ERR] Missing template: {template_path}")
        return 1

    maps = []
    for line in rotation_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        maps.append(line)

    data = json.loads(template_path.read_text(encoding="utf-8"))
    data.setdefault("maps", {})

    for map_name in maps:
        if map_name not in data["maps"]:
            data["maps"][map_name] = [
                {
                    "name": "todo_objective",
                    "type": "objective",
                    "x": None,
                    "y": None,
                    "z": None,
                    "note": "TODO: add coordinates",
                }
            ]

    template_path.write_text(
        json.dumps(data, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(f"[OK] Synced {len(maps)} maps into {template_path}")
    return 0

# ============================================================================
# SUBCOMMAND: update-lua
# ============================================================================

def _lua_is_identifier(name: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) is not None


def _lua_build_objectives(maps: dict) -> str:
    lines = []
    lines.append("    objectives = {")
    lines.append("        -- Coordinates sourced from proximity/objective_coords_template.json")
    for map_name in sorted(maps.keys()):
        key = map_name if _lua_is_identifier(map_name) else f"[\"{map_name}\"]"
        lines.append(f"        {key} = {{")
        entries = maps.get(map_name) or []
        wrote_entry = False
        for entry in entries:
            x = entry.get("x")
            y = entry.get("y")
            z = entry.get("z")
            name = entry.get("name", "unknown")
            obj_type = entry.get("type", "objective")
            if x is None or y is None or z is None:
                lines.append("            -- TODO: add coordinates (see proximity/objective_coords_template.json)")
                continue
            wrote_entry = True
            lines.append(
                f"            {{ name = \"{name}\", x = {x}, y = {y}, z = {z}, type = \"{obj_type}\" }},"
            )
        if not wrote_entry and not entries:
            lines.append("            -- TODO: add coordinates (see proximity/objective_coords_template.json)")
        lines.append("        },")
    lines.append("    },")
    return "\n".join(lines)


def cmd_update_lua(args):
    json_path = ROOT / "proximity" / "objective_coords_template.json"
    lua_path = ROOT / "proximity" / "lua" / "proximity_tracker.lua"

    if not json_path.exists():
        print(f"[ERR] Missing JSON: {json_path}")
        return 1
    if not lua_path.exists():
        print(f"[ERR] Missing Lua: {lua_path}")
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    maps = data.get("maps", {})
    lua_block = _lua_build_objectives(maps)

    content = lua_path.read_text(encoding="utf-8")
    start_match = re.search(r"^\s*objectives\s*=\s*{\s*$", content, re.MULTILINE)
    if not start_match:
        print("[ERR] Could not find objectives block start.")
        return 1
    start_index = start_match.start()

    # Find the closing line for the objectives table (same indentation + "},")
    indent = content[start_match.start():start_match.end()].split("objectives")[0]
    close_pattern = re.compile(rf"^{re.escape(indent)}}},\s*$", re.MULTILINE)
    close_match = close_pattern.search(content, start_match.end())
    if not close_match:
        print("[ERR] Could not find objectives block end.")
        return 1
    end_index = close_match.end()

    new_content = content[:start_index] + lua_block + content[end_index:]
    lua_path.write_text(new_content, encoding="utf-8")
    print("[OK] Updated objectives block in proximity_tracker.lua")
    return 0

# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Unified proximity coordinate tool for Slomix",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/slomix_proximity.py gate
  python tools/slomix_proximity.py gate --print-json
  python tools/slomix_proximity.py export-assets --etmain-dir /home/samba/share/etmain
  python tools/slomix_proximity.py export-zones --radius 600
  python tools/slomix_proximity.py coords-to-lua
  python tools/slomix_proximity.py sync-placeholders
  python tools/slomix_proximity.py update-lua
        """
    )

    subs = parser.add_subparsers(dest='command', required=True, help='Proximity subcommand')

    # GATE subcommand
    sub = subs.add_parser('gate', help='Validate objective coordinate coverage for top-played maps')
    sub.add_argument('--template', default=str(ROOT / "proximity" / "objective_coords_template.json"),
                     help='Path to objective coords template JSON.')
    sub.add_argument('--config', default=str(ROOT / "proximity" / "objective_coords_gate_config.json"),
                     help='Path to objective gate config JSON.')
    sub.add_argument('--top-maps', default='',
                     help='Optional comma-separated top map list for runtime gate checks.')
    sub.add_argument('--print-json', action='store_true',
                     help='Print full result JSON instead of concise text.')
    sub.set_defaults(func=cmd_gate)

    # EXPORT-ASSETS subcommand
    sub = subs.add_parser('export-assets', help='Export ET map minimaps + transform metadata')
    sub.add_argument('--manifest', default=str(ROOT / "proximity" / "map_assets_manifest_from_etmain.json"),
                     help='Path to generated map asset manifest JSON.')
    sub.add_argument('--etmain-dir', default='/home/samba/share/etmain',
                     help='Directory containing PK3 files.')
    sub.add_argument('--out-dir', default=str(ROOT / "website" / "assets" / "maps" / "proximity"),
                     help='Output directory for map PNG assets + transform config.')
    sub.add_argument('--config-name', default='map_transforms.json',
                     help='Output JSON transform config filename inside out-dir.')
    sub.set_defaults(func=cmd_export_assets)

    # EXPORT-ZONES subcommand
    sub = subs.add_parser('export-zones', help='Export objective coordinate zones for web minimap overlays')
    sub.add_argument('--source', default=str(ROOT / "proximity" / "objective_coords_from_etmain.json"),
                     help='Objective coordinates JSON source.')
    sub.add_argument('--output', default=str(ROOT / "website" / "assets" / "maps" / "proximity" / "objective_zones.json"),
                     help='Output path for zone config.')
    sub.add_argument('--radius', type=int, default=500,
                     help='Default objective zone radius in world units.')
    sub.set_defaults(func=cmd_export_zones)

    # COORDS-TO-LUA subcommand
    sub = subs.add_parser('coords-to-lua', help='Convert JSON objective-coordinates to Lua table snippet')
    sub.add_argument('--source', default=str(ROOT / "proximity" / "objective_coords_template.json"),
                     help='Path to objective coords JSON.')
    sub.set_defaults(func=cmd_coords_to_lua)

    # SYNC-PLACEHOLDERS subcommand
    sub = subs.add_parser('sync-placeholders', help='Sync objective coords template with map-rotation list')
    sub.set_defaults(func=cmd_sync_placeholders)

    # UPDATE-LUA subcommand
    sub = subs.add_parser('update-lua', help='Update proximity_tracker.lua objectives from JSON')
    sub.set_defaults(func=cmd_update_lua)

    args = parser.parse_args()
    logger.info("Script started: %s with command: %s", __file__, args.command)

    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
