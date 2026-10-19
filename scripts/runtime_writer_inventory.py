#!/usr/bin/env python3
"""Read named systemd unit metadata without certifying writer exclusion."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

UNIT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*\.(?:service|timer)\Z")
PROPERTIES = (
    "Id", "ActiveState", "SubState", "FragmentPath", "Triggers", "TriggeredBy",
    "ActiveEnterTimestamp", "ActiveExitTimestamp", "InactiveEnterTimestamp",
    "InactiveExitTimestamp",
)
TIMEOUT_SECONDS = 5


def unit_name(value: str) -> str:
    if len(value) > 255 or not UNIT.fullmatch(value):
        raise argparse.ArgumentTypeError("expected an explicit service or timer unit name")
    return value


def observe(scope: str, unit: str) -> dict:
    """Unknown includes missing units, failed probes and incomplete metadata."""
    unit_name(unit)
    if scope not in {"system", "user"}:
        raise ValueError("invalid manager scope")
    result = {"scope": scope, "unit": unit, "observation": "unknown", "properties": {}}
    properties = PROPERTIES + (("MainPID", "Restart") if unit.endswith(".service") else ())
    command = ["systemctl", f"--{scope}", "show", "--no-pager", "--all",
               "--property=" + ",".join(properties), "--", unit]
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            check=False, env={**os.environ, "LC_ALL": "C", "SYSTEMD_COLORS": "0"},
        )
    except subprocess.TimeoutExpired:
        return {**result, "error": "timeout"}
    except (OSError, UnicodeError):
        return {**result, "error": "probe_unavailable"}
    if completed.returncode:
        return {**result, "error": "probe_failed"}
    parsed = {}
    for line in completed.stdout.splitlines():
        key, separator, value = line.partition("=")
        if not separator or key not in properties or key in parsed:
            return {**result, "error": "invalid_metadata"}
        parsed[key] = value
    if (set(parsed) != set(properties) or parsed["Id"] != unit
            or not parsed["FragmentPath"] or not parsed["SubState"]):
        return {**result, "error": "incomplete_metadata"}
    if unit.endswith(".service"):
        if not parsed["MainPID"].isascii() or not parsed["MainPID"].isdigit() or not parsed["Restart"]:
            return {**result, "error": "invalid_metadata"}
        if parsed["ActiveState"] == "inactive" and int(parsed["MainPID"]) != 0:
            return {**result, "error": "inconsistent_metadata"}
    state = parsed["ActiveState"]
    result["properties"] = parsed
    if state in {"active", "inactive"}:
        result["observation"] = state
    else:
        result["error"] = "transitional_or_failed_state"
    return result


def inventory(system_units: list[str], user_units: list[str]) -> dict:
    started = datetime.now(timezone.utc).isoformat()
    observations = [observe(scope, unit) for scope, names in
                    (("system", system_units), ("user", user_units))
                    for unit in dict.fromkeys(names)]
    return {
        "capture_started_at_utc": started,
        "capture_finished_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "explicit_named_units_only",
        "observations": observations,
        "all_writers_absent": None,
        "handover_verified": False,
        "activation_ready": False,
        "manual_writer_review": "pending",
        "schema_evidence": "unmeasured",
    }


def write_report(path: Path, report: str) -> None:
    if path.name in {".git", ".slomix-release.json"}:
        raise ValueError("output basename is reserved")
    parent = path.parent.resolve(strict=True)
    if any((ancestor / ".git").exists() or (ancestor / ".git").is_symlink()
           for ancestor in (parent, *parent.parents)):
        raise ValueError("output must be outside a Git checkout")
    if any((ancestor / ".slomix-release.json").exists() or (ancestor / ".slomix-release.json").is_symlink()
           for ancestor in (parent, *parent.parents)):
        raise ValueError("output must be outside an immutable release")
    descriptor = os.open(parent / path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(report)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system-unit", action="append", type=unit_name, default=[])
    parser.add_argument("--user-unit", action="append", type=unit_name, default=[])
    parser.add_argument("--output", type=Path, help="new private file outside Git; otherwise stdout")
    args = parser.parse_args(argv)
    if not args.system_unit and not args.user_unit:
        parser.error("at least one explicit unit is required")
    report = inventory(args.system_unit, args.user_unit)
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    try:
        if args.output:
            write_report(args.output, encoded)
        else:
            print(encoded, end="")
    except (OSError, ValueError):
        parser.exit(2, "Could not create an exclusive external report file.\n")
    return 1 if any(row["observation"] == "unknown" for row in report["observations"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
