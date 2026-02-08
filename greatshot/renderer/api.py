"""Renderer pipeline entrypoints for demo clips."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict

from greatshot.config import CONFIG

import shutil


class _MissingValueDict(dict):
    def __missing__(self, key):  # type: ignore[override]
        raise KeyError(key)


def check_render_dependencies() -> Dict[str, Any]:
    ffmpeg_bin = shutil.which(CONFIG.ffmpeg_path or "ffmpeg")
    client_path = (
        Path(CONFIG.etlegacy_client_path).expanduser()
        if CONFIG.etlegacy_client_path
        else None
    )

    return {
        "ffmpeg": ffmpeg_bin,
        "ffmpeg_ok": bool(ffmpeg_bin),
        "etlegacy_client": str(client_path) if client_path else None,
        "etlegacy_client_ok": bool(client_path and client_path.exists()),
        "render_command": CONFIG.render_command,
        "render_command_ok": bool(CONFIG.render_command),
    }


def _run_command(cmd: list[str], timeout_seconds: int) -> None:
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Render command timed out after {timeout_seconds}s.") from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        stdout = (proc.stdout or "").strip()
        details = stderr or stdout or "no output"
        raise RuntimeError(
            f"Render command failed with code {proc.returncode}: {details[:800]}"
        )


def _build_render_command(
    template: str,
    demo_clip_path: Path,
    output_mp4_path: Path,
    options: Dict[str, Any],
) -> list[str]:
    values: Dict[str, Any] = {
        "input_demo": str(demo_clip_path),
        "demo_clip_path": str(demo_clip_path),
        "output_mp4": str(output_mp4_path),
        "output_dir": str(output_mp4_path.parent),
        "output_stem": output_mp4_path.stem,
        "output_name": output_mp4_path.name,
    }
    values.update(options)

    tokens = shlex.split(template)
    expanded: list[str] = []
    mapping = _MissingValueDict(values)
    for token in tokens:
        try:
            expanded.append(token.format_map(mapping))
        except KeyError as exc:
            missing = str(exc).strip("'")
            raise RuntimeError(
                f"Render command references unknown placeholder '{missing}'."
            ) from exc
    return expanded


def _transcode_to_mp4(
    source_video_path: Path,
    output_mp4_path: Path,
    ffmpeg_bin: str,
    timeout_seconds: int,
) -> Path:
    if not source_video_path.exists() or not source_video_path.is_file():
        raise RuntimeError(f"Source video not found for transcode: {source_video_path}")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i",
        str(source_video_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        str(output_mp4_path),
    ]
    _run_command(cmd, timeout_seconds=timeout_seconds)
    return output_mp4_path


def render_clip(
    demo_clip_path: str | Path,
    output_mp4_path: str | Path,
    options: Dict[str, Any] | None = None,
) -> Path:
    """Render a cut demo to MP4 using a configured worker command or transcode."""
    opts = dict(options or {})
    clip_path = Path(demo_clip_path).expanduser().resolve()
    output_path = Path(output_mp4_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not clip_path.exists() or not clip_path.is_file():
        raise RuntimeError(f"Clip demo not found: {clip_path}")

    timeout_seconds = int(opts.get("timeout_seconds") or CONFIG.render_timeout_seconds)
    deps = check_render_dependencies()
    command_template = str(opts.get("render_command") or deps.get("render_command") or "").strip()

    if command_template:
        cmd = _build_render_command(command_template, clip_path, output_path, opts)
        _run_command(cmd, timeout_seconds=timeout_seconds)
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

    source_video_raw = opts.get("source_video_path")
    if source_video_raw:
        source_video_path = Path(str(source_video_raw)).expanduser().resolve()
        if not deps["ffmpeg_ok"]:
            raise RuntimeError(
                "Cannot transcode render output: ffmpeg binary not found in PATH."
            )
        _transcode_to_mp4(
            source_video_path=source_video_path,
            output_mp4_path=output_path,
            ffmpeg_bin=str(deps["ffmpeg"]),
            timeout_seconds=timeout_seconds,
        )
        if output_path.exists() and output_path.stat().st_size > 0:
            return output_path

    raise RuntimeError(
        "Renderer could not produce MP4 output. Configure GREATSHOT_RENDER_COMMAND "
        "(for example: 'python3 worker.py --input {input_demo} --output {output_mp4}') "
        "or provide source_video_path for ffmpeg transcode."
    )
