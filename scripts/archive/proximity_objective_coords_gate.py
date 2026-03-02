#!/usr/bin/env python3
"""
Validate objective coordinate coverage for top-played maps.

This script enforces two gates:
1) Static gate: strict coverage for a curated top-map list in config.
2) Runtime gate: strict coverage for a provided top-map ranking (allowlist supported).

Exit codes:
  0 = pass
  2 = gate failure
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

def normalize_map_name(value: str) -> str:
    return (value or "").strip().lower()


def parse_top_maps_arg(value: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for token in (value or "").split(","):
        normalized = normalize_map_name(token)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def _entry_has_complete_xyz(entry: dict[str, Any]) -> bool:
    return entry.get("x") is not None and entry.get("y") is not None and entry.get("z") is not None


def _build_template_index(maps: dict[str, Any]) -> dict[str, tuple[str, list[dict[str, Any]]]]:
    index: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    for map_key, entries_raw in maps.items():
        normalized = normalize_map_name(map_key)
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


def _map_coverage(map_name: str, template_index: dict[str, tuple[str, list[dict[str, Any]]]]) -> dict[str, Any]:
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
    complete_entries = sum(1 for entry in entries if _entry_has_complete_xyz(entry))
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
    static_guard_maps = [normalize_map_name(map_name) for map_name in static_guard_maps_raw if normalize_map_name(map_name)]

    runtime_config = config_payload.get("runtime", {})
    if runtime_config is None:
        runtime_config = {}
    if not isinstance(runtime_config, dict):
        raise ValueError("Gate config 'runtime' must be an object.")

    allow_todo_raw = runtime_config.get("allow_todo_maps", [])
    if not isinstance(allow_todo_raw, list):
        raise ValueError("Gate config 'runtime.allow_todo_maps' must be a list.")
    allow_todo_maps = {normalize_map_name(map_name) for map_name in allow_todo_raw if normalize_map_name(map_name)}

    expected_top_n = runtime_config.get("top_n", 0)
    expected_top_n = int(expected_top_n) if isinstance(expected_top_n, (int, float, str)) and str(expected_top_n).strip() else 0
    if expected_top_n < 0:
        expected_top_n = 0

    template_index = _build_template_index(template_maps)
    errors: list[str] = []
    warnings: list[str] = []

    static_results: list[dict[str, Any]] = []
    for map_name in static_guard_maps:
        coverage = _map_coverage(map_name, template_index)
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
            coverage = _map_coverage(map_name, template_index)
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template",
        default="proximity/objective_coords_template.json",
        help="Path to objective coords template JSON.",
    )
    parser.add_argument(
        "--config",
        default="proximity/objective_coords_gate_config.json",
        help="Path to objective gate config JSON.",
    )
    parser.add_argument(
        "--top-maps",
        default="",
        help="Optional comma-separated top map list for runtime gate checks.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print full result JSON instead of concise text.",
    )
    return parser.parse_args()


def _load_json(path: str) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return payload


def main() -> int:
    logger.info("Script started: %s", __file__)
    args = _parse_args()
    template_payload = _load_json(args.template)
    config_payload = _load_json(args.config)
    runtime_top_maps = parse_top_maps_arg(args.top_maps)

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


if __name__ == "__main__":
    raise SystemExit(main())
