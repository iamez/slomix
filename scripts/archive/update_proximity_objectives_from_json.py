#!/usr/bin/env python3
"""
Update proximity_tracker.lua objectives table from objective_coords_template.json.

Usage:
  python scripts/update_proximity_objectives_from_json.py
"""

import json
import re
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def is_lua_identifier(name: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name) is not None


def build_lua_objectives(maps: dict) -> str:
    lines = []
    lines.append("    objectives = {")
    lines.append("        -- Coordinates sourced from proximity/objective_coords_template.json")
    for map_name in sorted(maps.keys()):
        key = map_name if is_lua_identifier(map_name) else f"[\"{map_name}\"]"
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


def main() -> int:
    logger.info("Script started: %s", __file__)
    json_path = Path("proximity/objective_coords_template.json")
    lua_path = Path("proximity/lua/proximity_tracker.lua")

    if not json_path.exists():
        print(f"[ERR] Missing JSON: {json_path}")
        return 1
    if not lua_path.exists():
        print(f"[ERR] Missing Lua: {lua_path}")
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    maps = data.get("maps", {})
    lua_block = build_lua_objectives(maps)

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


if __name__ == "__main__":
    raise SystemExit(main())
