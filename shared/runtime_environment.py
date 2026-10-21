"""Explicit external configuration for Git-free releases; legacy stays opt-in.

SLOMIX_ENV_FILE uses literal dotenv values (no ${...} interpolation); existing
process environment wins only in unmarked legacy checkouts. Marked releases
refuse shadowed or additional database settings before changing any environment.
This module never prints values or searches ancestor directories in release mode.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def external_config_path(value: str, root: Path = ROOT) -> Path:
    """Require a canonical, private regular file outside the code payload."""
    path = Path(value)
    try:
        if (not value or not path.is_absolute() or path.resolve(strict=True) != path
                or not path.is_file() or path.is_relative_to(root.resolve())
                or path.stat().st_mode & 0o077):
            raise ValueError
    except (OSError, ValueError, RuntimeError):
        raise ValueError("External configuration must be an absolute canonical private file outside code") from None
    return path


def explicit_env_file(root: Path = ROOT) -> Path | None:
    """None permits legacy behavior only in an unmarked source checkout."""
    value = os.environ.get("SLOMIX_ENV_FILE")
    if value is not None:
        return external_config_path(value, root)
    marker = root / ".slomix-release.json"
    if marker.exists() or marker.is_symlink():
        raise ValueError("Git-free release requires explicit SLOMIX_ENV_FILE")
    return None


def load_environment(legacy_file: str | Path | None = None, *, root: Path = ROOT) -> None:
    selected = explicit_env_file(root)
    try:
        from dotenv import load_dotenv
    except ImportError:
        if selected is not None:
            raise RuntimeError("Explicit configuration requires python-dotenv") from None
        return  # Preserve legacy optional dependency behavior.
    if selected is None:
        load_dotenv(legacy_file)
        return
    values = read_external_environment(selected, root=root,
                                       expected_digest=os.environ.get("SLOMIX_ENV_SHA256"))
    if (root / ".slomix-release.json").exists() or (root / ".slomix-release.json").is_symlink():
        if any((key in values and value != values[key])
               or (key.startswith(("POSTGRES_", "DB_", "PG", "DATABASE_")) and key not in values)
               for key, value in os.environ.items()):
            raise ValueError("Inherited environment overrides explicit application configuration")
    for key, value in values.items():
        if value is not None:
            os.environ.setdefault(key, value)


def read_external_environment(path: Path, *, root: Path = ROOT, expected_digest: str | None = None) -> dict:
    """Read the exact explicit-loader syntax without mutating process env."""
    from dotenv import dotenv_values
    from dotenv.parser import parse_stream

    selected = external_config_path(str(path), root)
    with selected.open("rb") as source:
        raw = source.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("External configuration exceeds size limit")
    if expected_digest is not None and hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("External configuration differs from approved startup digest")
    with io.StringIO(raw.decode("utf-8")) as stream:
        if any(binding.error for binding in parse_stream(stream)):
            raise ValueError("Invalid external dotenv syntax")
        stream.seek(0)
        return dict(dotenv_values(stream=stream, interpolate=False))


def refuse_config_overrides(values: dict, environment: dict) -> None:
    """Pre-start guard: a file proof cannot certify shadowed process settings."""
    if any(key in values or key.startswith(("POSTGRES_", "DB_", "PG", "DATABASE_"))
           or key in {"PYTHONPATH", "PYTHONHOME", "LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"}
           for key in environment):
        raise ValueError("Inherited environment overrides explicit application configuration")


def validate_bot_state_paths(*, root: Path = ROOT) -> None:
    """Refuse implicit or payload-local writes before importing bot services."""
    marker = root / ".slomix-release.json"
    if not (marker.exists() or marker.is_symlink()):
        return
    names = {"STATS_DIRECTORY", "LOCAL_STATS_PATH", "BACKUP_DIRECTORY", "BOT_LOG_DIR"}
    for enabled, name in (("GAMETIMES_ENABLED", "LOCAL_GAMETIMES_PATH"),
                          ("PROXIMITY_ENABLED", "PROXIMITY_LOCAL_PATH")):
        if os.environ.get(enabled, "false").lower() == "true":
            names.add(name)
    # Explicit optional paths must also be safe even when their feature is off.
    names.update(name for name in ("LOCAL_GAMETIMES_PATH", "PROXIMITY_LOCAL_PATH",
                                   "METRICS_DB_PATH", "XDG_CACHE_HOME", "MPLCONFIGDIR",
                                   "GREATSHOT_STORAGE_ROOT", "UPLOAD_STORAGE_ROOT")
                 if name in os.environ)
    for name in names:
        value = os.environ.get(name, "")
        path = Path(value)
        if (not value or not path.is_absolute() or path.resolve() != path
                or path.is_relative_to(root.resolve())):
            raise ValueError("Marked bot requires canonical external mutable paths")
