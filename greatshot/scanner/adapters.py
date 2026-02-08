"""Parser adapters for ET-family demo files."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from greatshot.config import CONFIG
from greatshot.scanner.errors import ParseToolFailedError, ParseToolMissingError


def find_udt_json_binary(explicit_path: str | None = None) -> str:
    # Resolve project-local bin/ relative to this file's location
    _project_bin = Path(__file__).resolve().parent.parent.parent / "bin" / "UDT_json"
    candidates = [
        explicit_path,
        CONFIG.udt_json_bin,
        shutil.which("UDT_json"),
        str(_project_bin) if _project_bin.is_file() else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise ParseToolMissingError(
        "UDT_json parser binary not found. Set GREATSHOT_UDT_JSON_BIN or install UDT_json in PATH."
    )


def run_udt_json_parser(
    demo_path: Path,
    timeout_seconds: int,
    max_output_bytes: int,
    binary_path: str | None = None,
) -> Dict[str, Any]:
    parser_bin = find_udt_json_binary(binary_path)
    cmd = [parser_bin, "-q", "-c", str(demo_path)]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParseToolFailedError(
            f"Scanner timed out after {timeout_seconds}s while parsing {demo_path.name}"
        ) from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace").strip()
        raise ParseToolFailedError(
            f"UDT_json exited with code {proc.returncode}: {stderr[:500]}"
        )

    if len(proc.stdout) > max_output_bytes:
        raise ParseToolFailedError(
            f"Parser output too large ({len(proc.stdout)} bytes > {max_output_bytes})."
        )

    raw = proc.stdout.decode("utf-8", errors="replace")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        excerpt = raw[:300].replace("\n", " ")
        raise ParseToolFailedError(
            f"Parser output is not valid JSON: {excerpt}"
        ) from exc
