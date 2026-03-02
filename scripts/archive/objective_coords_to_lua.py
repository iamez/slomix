#!/usr/bin/env python3
"""
Convert a simple JSON objective-coordinates file into a Lua table snippet.

Usage:
  python scripts/objective_coords_to_lua.py proximity/objective_coords_template.json
"""

import json
import sys
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def main() -> int:
    logger.info("Script started: %s", __file__)
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("proximity/objective_coords_template.json")
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


if __name__ == "__main__":
    raise SystemExit(main())
