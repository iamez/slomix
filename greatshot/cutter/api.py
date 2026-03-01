"""Demo cutting abstraction and concrete UDT cutter implementation."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from greatshot.config import CONFIG


def build_clip_window(
    highlight_start_ms: int,
    highlight_end_ms: int,
    demo_duration_ms: int,
    pre_roll_ms: int = 4000,
    post_roll_ms: int = 3000,
) -> tuple[int, int]:
    start_ms = max(0, int(highlight_start_ms) - int(pre_roll_ms))
    end_ms = min(int(demo_duration_ms), int(highlight_end_ms) + int(post_roll_ms))
    if end_ms <= start_ms:
        end_ms = min(int(demo_duration_ms), start_ms + 1000)
    return start_ms, end_ms


def _find_cutter_binary(explicit_path: str | None = None) -> str:
    # Resolve project-local bin/ relative to this file's location
    _project_bin = Path(__file__).resolve().parent.parent.parent / "bin" / "UDT_cutter"
    candidates = [
        explicit_path,
        CONFIG.udt_cutter_bin,
        shutil.which("UDT_cutter"),
        str(_project_bin) if _project_bin.is_file() else None,
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError(
        "No demo cutter binary configured. Set GREATSHOT_UDT_CUTTER_BIN to enable clip extraction."
    )


def _ceil_ms_to_seconds(value_ms: int) -> int:
    return max(0, (int(value_ms) + 999) // 1000)


def _pick_udt_output_file(output_dir: Path, input_demo: Path) -> Path:
    ext = input_demo.suffix.lower()
    candidates = [path for path in output_dir.glob(f"*{ext}") if path.is_file()]
    if not candidates:
        raise RuntimeError(
            f"UDT_cutter finished but produced no '{ext}' clip in {output_dir}."
        )

    preferred_marker = f"{input_demo.stem}_CUT_"
    preferred = [path for path in candidates if preferred_marker in path.name]
    selected_pool = preferred if preferred else candidates
    selected_pool.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
    return selected_pool[-1]


def cut_demo(
    input_demo: str | Path,
    start_ms: int,
    end_ms: int,
    output_demo: str | Path,
    cutter_binary: str | None = None,
    timeout_seconds: int | None = None,
) -> Path:
    """Cut a demo into a smaller segment using UDT_cutter cut-by-time mode."""
    source = Path(input_demo).expanduser().resolve()
    destination = Path(output_demo).expanduser().resolve()

    if not source.exists() or not source.is_file():
        raise FileNotFoundError(f"Demo file not found: {source}")

    start_ms = int(start_ms)
    end_ms = int(end_ms)
    if end_ms <= start_ms:
        raise ValueError(f"Invalid cut interval: start_ms={start_ms} end_ms={end_ms}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    cutter = _find_cutter_binary(cutter_binary)
    timeout = int(timeout_seconds or CONFIG.cutter_timeout_seconds)

    start_sec = max(0, start_ms // 1000)
    end_sec = max(start_sec + 1, _ceil_ms_to_seconds(end_ms))

    with tempfile.TemporaryDirectory(prefix="udt_cut_", dir=str(destination.parent)) as tmp_dir:
        tmp_path = Path(tmp_dir)
        cmd = [
            cutter,
            "t",
            "-q",
            f"-o={tmp_path}",
            f"-s={start_sec}",
            f"-e={end_sec}",
            str(source),
        ]

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"UDT_cutter timed out after {timeout}s while cutting '{source.name}'."
            ) from exc

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            stdout = (proc.stdout or "").strip()
            details = stderr or stdout or "no error output"
            raise RuntimeError(
                f"UDT_cutter failed with code {proc.returncode}: {details[:600]}"
            )

        produced = _pick_udt_output_file(tmp_path, source)
        shutil.move(str(produced), str(destination))

    if not destination.exists() or destination.stat().st_size <= 0:
        raise RuntimeError(f"Cut demo output missing or empty: {destination}")

    return destination
