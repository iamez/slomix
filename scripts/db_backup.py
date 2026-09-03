#!/usr/bin/env python3
"""Create an atomic PostgreSQL dump and target-bound verification manifest.

WHICH DATABASE and AS WHOM are two different questions, and this tool needs
different answers than the web service does.

`resolve_env_file` prefers `website/.env` over the root `.env` so a migration
validates against the database the running service actually uses (Codex
PX-DB-001). That is right for host/port/database. It is wrong for the ROLE:
the service runs least-privilege as `website_app`, and a dump must read every
table. On 2026-09-03 that cost a backup — `pg_dump` died with "permission
denied for table voice_members", one of seven tables `website_app` cannot
read, and the backup that was gating an 8,721-row repair simply did not exist.
It failed loudly, which is the good outcome; the bad one is a tool that picks
a role by accident.

So the target still follows the service, and the role is resolved separately:

    BACKUP_DB_USER  ->  the root .env's POSTGRES_USER  ->  whatever the
                        connection resolved (the old behaviour)

The manifest still binds to host:port/database only — the role is not part of
a backup's identity, and making it one would refuse a perfectly good dump.
"""

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


def resolve_dump_role(connection: dict, repo_root: Path | None = None,
                      environ: dict | None = None) -> tuple[str, str, str]:
    """(user, password, where_it_came_from) for the role the dump runs as.

    Explicit beats implicit: an operator who sets BACKUP_DB_USER means it. The
    root .env comes next, because that is where this project keeps the owner
    role (`etlegacy_user`), and the file that shadowed it (website/.env) keeps
    the service's least-privilege one on purpose. Falling back to the resolved
    connection preserves the old behaviour for anyone whose setup has neither.
    """
    environ = os.environ if environ is None else environ
    repo_root = ROOT if repo_root is None else repo_root
    fallback_password = str(connection.get("password") or "")

    explicit = environ.get("BACKUP_DB_USER")
    if explicit:
        return (explicit,
                environ.get("BACKUP_DB_PASSWORD") or fallback_password,
                "BACKUP_DB_USER")

    root_env = repo_root / ".env"
    if root_env.exists():
        try:
            from dotenv import dotenv_values
        except ImportError:
            values = {}
        else:
            # dotenv_values parses without touching os.environ — this must not
            # change what any later tool in the same process resolves.
            values = dotenv_values(root_env) or {}
        root_user = values.get("POSTGRES_USER") or values.get("DB_USER")
        if root_user and root_user != connection.get("user"):
            return (str(root_user),
                    str(values.get("POSTGRES_PASSWORD")
                        or values.get("DB_PASSWORD") or fallback_password),
                    f"root {root_env.name}")

    return str(connection["user"]), fallback_password, "resolved connection"


def create_backup() -> tuple[Path, Path, str]:
    connection = get_connection_kwargs()
    host = str(connection["host"])
    port = int(connection["port"])
    database = str(connection["database"])
    user, password, role_source = resolve_dump_role(connection)
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
    print(f"[db_backup] dumping {db_identity} as {user} (role from {role_source})")

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
                hint = ""
                if "permission denied" in details.lower():
                    hint = (
                        f"\n  The dump ran as {user!r} (role from {role_source}). "
                        f"A backup must read EVERY table; the web service's role "
                        f"cannot. Re-run with BACKUP_DB_USER set to the owning "
                        f"role (this project: etlegacy_user), or fix the grant."
                    )
                raise RuntimeError(
                    f"pg_dump failed with exit code {return_code}: {details}{hint}"
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
