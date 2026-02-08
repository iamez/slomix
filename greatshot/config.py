"""Greatshot configuration — loaded from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class GreatshotConfig:
    storage_root: Path = field(default_factory=lambda: Path("data/greatshot"))
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 MB
    allow_extensions: tuple[str, ...] = (".dm_84", ".tv_84")

    scanner_timeout_seconds: int = 60
    scanner_max_output_bytes: int = 30 * 1024 * 1024  # 30 MB
    scanner_max_events: int = 250_000

    cutter_timeout_seconds: int = 45
    render_timeout_seconds: int = 100

    analysis_queue_workers: int = 1
    render_queue_workers: int = 1

    udt_json_bin: Optional[str] = None
    udt_cutter_bin: Optional[str] = None
    etlegacy_client_path: Optional[str] = None
    ffmpeg_path: str = "ffmpeg"
    render_command: Optional[str] = None


def _env(name: str, legacy_name: str | None = None, default: str | None = None) -> str | None:
    """Read env var, with optional legacy fallback name."""
    value = os.getenv(name)
    if value is not None:
        return value
    if legacy_name:
        value = os.getenv(legacy_name)
        if value is not None:
            return value
    return default


DEF_ROOT = Path(_env("GREATSHOT_STORAGE_ROOT", "DEMOS_STORAGE_ROOT", "data/greatshot")).expanduser()

CONFIG = GreatshotConfig(
    storage_root=DEF_ROOT,
    max_upload_bytes=int(_env("GREATSHOT_MAX_UPLOAD_BYTES", "DEMOS_MAX_UPLOAD_BYTES", str(200 * 1024 * 1024))),
    allow_extensions=tuple(
        ext.strip().lower()
        for ext in (_env("GREATSHOT_ALLOWED_EXTENSIONS", "DEMOS_ALLOWED_EXTENSIONS", ".dm_84,.tv_84")).split(",")
        if ext.strip()
    ),
    scanner_timeout_seconds=int(_env("GREATSHOT_SCANNER_TIMEOUT_SECONDS", "DEMOS_SCANNER_TIMEOUT_SECONDS", "60")),
    scanner_max_output_bytes=int(_env("GREATSHOT_SCANNER_MAX_OUTPUT_BYTES", "DEMOS_SCANNER_MAX_OUTPUT_BYTES", str(30 * 1024 * 1024))),
    scanner_max_events=int(_env("GREATSHOT_SCANNER_MAX_EVENTS", "DEMOS_SCANNER_MAX_EVENTS", "250000")),
    cutter_timeout_seconds=int(_env("GREATSHOT_CUTTER_TIMEOUT_SECONDS", "DEMOS_CUTTER_TIMEOUT_SECONDS", "45")),
    render_timeout_seconds=int(_env("GREATSHOT_RENDER_TIMEOUT_SECONDS", "DEMOS_RENDER_TIMEOUT_SECONDS", "100")),
    analysis_queue_workers=max(1, int(_env("GREATSHOT_ANALYSIS_WORKERS", "DEMOS_ANALYSIS_WORKERS", "1"))),
    render_queue_workers=max(1, int(_env("GREATSHOT_RENDER_WORKERS", "DEMOS_RENDER_WORKERS", "1"))),
    udt_json_bin=_env("GREATSHOT_UDT_JSON_BIN", "DEMOS_UDT_JSON_BIN") or os.getenv("UDT_JSON_BIN"),
    udt_cutter_bin=_env("GREATSHOT_UDT_CUTTER_BIN", "DEMOS_UDT_CUTTER_BIN") or os.getenv("UDT_CUTTER_BIN"),
    etlegacy_client_path=_env("GREATSHOT_ETLEGACY_CLIENT_PATH", "DEMOS_ETLEGACY_CLIENT_PATH"),
    ffmpeg_path=_env("GREATSHOT_FFMPEG_PATH", "DEMOS_FFMPEG_PATH", "ffmpeg"),
    render_command=_env("GREATSHOT_RENDER_COMMAND", "DEMOS_RENDER_COMMAND"),
)

HIGHLIGHT_DEFAULTS = {
    "multi_kill_window_ms": int(_env("GREATSHOT_MULTI_KILL_WINDOW_MS", "DEMOS_MULTI_KILL_WINDOW_MS", "4000")),
    "multi_kill_min": int(_env("GREATSHOT_MULTI_KILL_MIN", "DEMOS_MULTI_KILL_MIN", "3")),
    "multi_kill_big_window_ms": int(_env("GREATSHOT_MULTI_KILL_BIG_WINDOW_MS", "DEMOS_MULTI_KILL_BIG_WINDOW_MS", "8000")),
    "multi_kill_big_min": int(_env("GREATSHOT_MULTI_KILL_BIG_MIN", "DEMOS_MULTI_KILL_BIG_MIN", "3")),
    "spree_min": int(_env("GREATSHOT_SPREE_MIN", "DEMOS_SPREE_MIN", "4")),
    "quick_headshot_window_ms": int(_env("GREATSHOT_QUICK_HEADSHOT_WINDOW_MS", "DEMOS_QUICK_HEADSHOT_WINDOW_MS", "2500")),
    "quick_headshot_min": int(_env("GREATSHOT_QUICK_HEADSHOT_MIN", "DEMOS_QUICK_HEADSHOT_MIN", "2")),
    "aim_moment_headshots": int(_env("GREATSHOT_AIM_MOMENT_HS", "DEMOS_AIM_MOMENT_HS", "3")),
}
