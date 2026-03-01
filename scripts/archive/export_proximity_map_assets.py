#!/usr/bin/env python3
"""Export ET map minimaps + transform metadata for proximity overlays.

Reads `proximity/map_assets_manifest_from_etmain.json` and extracts the chosen
levelshot image from each PK3 into web-friendly PNG files.
Also writes a compact transform config consumed by website JS.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
import zipfile

from PIL import Image

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class MapRecord:
    map_name: str
    pk3: str
    minimap_file: str
    mapcoordsmins: str
    mapcoordsmaxs: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="proximity/map_assets_manifest_from_etmain.json",
        help="Path to generated map asset manifest JSON.",
    )
    parser.add_argument(
        "--etmain-dir",
        default="/home/samba/share/etmain",
        help="Directory containing PK3 files.",
    )
    parser.add_argument(
        "--out-dir",
        default="website/assets/maps/proximity",
        help="Output directory for map PNG assets + transform config.",
    )
    parser.add_argument(
        "--config-name",
        default="map_transforms.json",
        help="Output JSON transform config filename inside out-dir.",
    )
    return parser.parse_args()


def parse_vec2(raw: str | None) -> list[float] | None:
    if not raw:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    try:
        return [float(parts[0]), float(parts[1])]
    except ValueError:
        return None


def load_records(manifest_path: Path) -> list[MapRecord]:
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


def export_minimap(etmain_dir: Path, out_dir: Path, record: MapRecord) -> dict[str, Any] | None:
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

    mins = parse_vec2(record.mapcoordsmins)
    maxs = parse_vec2(record.mapcoordsmaxs)
    return {
        "map_name": record.map_name,
        "image": f"/assets/maps/proximity/{out_name}",
        "size": [width, height],
        "mapcoordsmins": mins,
        "mapcoordsmaxs": maxs,
        "source_pk3": record.pk3,
        "source_image": record.minimap_file,
    }


def main() -> int:
    logger.info("Script started: %s", __file__)
    args = parse_args()
    manifest_path = Path(args.manifest)
    etmain_dir = Path(args.etmain_dir)
    out_dir = Path(args.out_dir)

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest: {manifest_path}")
    if not etmain_dir.exists():
        raise FileNotFoundError(f"Missing etmain dir: {etmain_dir}")

    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(manifest_path)
    maps: dict[str, Any] = {}
    failures: list[str] = []

    for record in records:
        exported = export_minimap(etmain_dir, out_dir, record)
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


if __name__ == "__main__":
    raise SystemExit(main())
