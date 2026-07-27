#!/usr/bin/env python3
"""Create an atomic PostgreSQL dump and target-bound verification manifest."""

from __future__ import annotations

import gzip
import hashlib
import os
import re
import shutil
import subprocess  # nosec B404
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

# The only subprocess is a fixed pg_dump argv and never executes a shell.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.apply_migrations import get_connection_kwargs  # noqa: E402

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.-]+$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(path: Path, *, dump_path: Path, db_identity: str) -> None:
    values = (
        f"db_identity={db_identity}\n"
        f"dump_file={dump_path}\n"
        f"sha256={_sha256(dump_path)}\n"
        f"created_unix={int(time.time())}\n"
    )
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(values)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def create_backup() -> tuple[Path, Path, str]:
    connection = get_connection_kwargs()
    host = str(connection["host"])
    port = int(connection["port"])
    database = str(connection["database"])
    user = str(connection["user"])
    password = str(connection["password"])
    if not _SAFE_FILENAME.fullmatch(database):
        raise ValueError(f"database name is unsafe for a backup filename: {database!r}")

    backup_dir = Path(os.environ.get("BACKUP_DIR", ROOT / "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = backup_dir.resolve()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
    output_path = backup_dir / f"{database}_{timestamp}.sql.gz"
    manifest_path = output_path.with_suffix(output_path.suffix + ".manifest")
    if output_path.exists() or manifest_path.exists():
        raise FileExistsError(f"backup destination already exists: {output_path}")

    if shutil.which("pg_dump") is None:
        raise FileNotFoundError("pg_dump was not found on PATH")
    child_env = os.environ.copy()
    child_env.update({
        "PGHOST": host,
        "PGPORT": str(port),
        "PGDATABASE": database,
        "PGUSER": user,
        "PGPASSWORD": password,
    })
    db_identity = f"{host}:{port}/{database}"

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=backup_dir
    )
    os.close(fd)
    temporary_path = Path(temporary_name)
    try:
        # PATH is operator-controlled and the binary was proven present above.
        with tempfile.TemporaryFile() as stderr, subprocess.Popen(  # nosec B603 B607
            ["pg_dump", "--no-owner", "--no-privileges", "--clean", "--if-exists"],
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=child_env,
        ) as process:
            if process.stdout is None:  # pragma: no cover - guaranteed by PIPE
                raise RuntimeError("pg_dump stdout pipe was not created")
            with gzip.open(temporary_path, "wb", compresslevel=9) as compressed:
                shutil.copyfileobj(process.stdout, compressed, length=1024 * 1024)
            return_code = process.wait()
            if return_code != 0:
                stderr.seek(0)
                details = stderr.read().decode(errors="replace").strip()
                raise RuntimeError(
                    f"pg_dump failed with exit code {return_code}: {details}"
                )

        if temporary_path.stat().st_size == 0:
            raise RuntimeError("pg_dump produced an empty compressed file")
        os.replace(temporary_path, output_path)
        try:
            _write_manifest(
                manifest_path,
                dump_path=output_path,
                db_identity=db_identity,
            )
        except Exception:
            output_path.unlink(missing_ok=True)
            raise
    finally:
        temporary_path.unlink(missing_ok=True)

    return output_path, manifest_path, db_identity


def main() -> int:
    old_umask = os.umask(0o077)
    try:
        output_path, manifest_path, db_identity = create_backup()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"[db_backup] ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        os.umask(old_umask)

    size_mib = output_path.stat().st_size / (1024 * 1024)
    print(f"[db_backup] done: {output_path} ({size_mib:.1f} MiB)")
    print(f"[db_backup] verified manifest: {manifest_path}")
    print(
        "[db_backup] rollback target: "
        f"{db_identity} (restore remains manual and owner-gated)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
