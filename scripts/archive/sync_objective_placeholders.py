#!/usr/bin/env python3
"""
Sync objective coords template with a map-rotation list.

Usage:
  python scripts/sync_objective_placeholders.py
"""

import json
from pathlib import Path

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def main() -> int:
    logger.info("Script started: %s", __file__)
    rotation_path = Path("proximity/map_rotation.txt")
    template_path = Path("proximity/objective_coords_template.json")

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


if __name__ == "__main__":
    raise SystemExit(main())
