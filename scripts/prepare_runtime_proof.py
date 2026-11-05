"""Prepare a fresh local PostgreSQL proof cluster; never activate a service.

Run as the owner, not root. Generated data/logs/units stay outside Git. A
failure preserves partial output for inspection; rerunning creates a new target.
No application environment, existing cluster or credentials are consumed.
"""

import argparse
import hashlib
import json
import os
import pwd
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def safe_directory(value):
    """Reject ambiguous paths and systemd/shell interpolation before writes."""
    path = Path(value)
    if (not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(value))
            or not path.is_dir() or path.resolve() != path):
        raise ValueError("An existing canonical absolute directory without special characters is required")
    return path


def write_new(path, text):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def unit_text(root, socket, bindir):
    # Inputs are canonical restricted paths, not arbitrary systemd strings.
    settings = {
        "listen_addresses": "", "port": "5432",
        "unix_socket_directories": str(socket), "unix_socket_permissions": "0700",
        "max_connections": "10", "shared_buffers": "16MB", "work_mem": "1MB",
        "maintenance_work_mem": "16MB", "wal_buffers": "1MB",
        "min_wal_size": "32MB", "max_wal_size": "64MB",
        "logging_collector": "off",
    }
    arguments = " ".join(f"-c {key}={value}" for key, value in settings.items())
    return f"""[Unit]
Description=Isolated Slomix PostgreSQL proof (owner-started, no application data)

[Service]
Type=exec
WorkingDirectory={root}
ExecStart={bindir}/postgres -D {root}/data {arguments}
Restart=no
RuntimeMaxSec=60min
TimeoutStopSec=30s
KillSignal=SIGINT
MemoryMax=256M
TasksMax=32
UMask=0077
NoNewPrivileges=yes
StandardOutput=append:{root}/service.log
StandardError=append:{root}/service.log
"""


def prepare(parent, bindir):
    uid = os.getuid()
    if uid == 0 or os.geteuid() != uid:
        raise ValueError("Run as the unprivileged proof owner, without sudo")
    owner = pwd.getpwuid(uid).pw_name
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", owner):
        raise ValueError("Unsupported proof owner name")
    parent, bindir = safe_directory(parent), safe_directory(bindir)
    if any((ancestor / ".git").exists() for ancestor in (parent, *parent.parents)):
        raise ValueError("Proof files must stay outside a Git checkout")
    if parent.stat().st_uid != uid:
        raise ValueError("Proof parent must belong to the current user")
    for binary in (bindir / "initdb", bindir / "postgres", Path("/usr/bin/systemd-analyze")):
        if not binary.is_file() or not os.access(binary, os.X_OK):
            raise ValueError(f"Required executable unavailable: {binary}")

    root = Path(tempfile.mkdtemp(prefix="slomix-clean-proof-", dir=parent))
    socket = None
    try:
        socket = Path(tempfile.mkdtemp(prefix="slomix-runtime-pg-", dir="/tmp"))
        # Deliberately no inherited PG*, application dotenv or loader variables.
        env = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
               "XDG_RUNTIME_DIR": f"/run/user/{uid}"}
        with (root / "prepare.log").open("x", encoding="utf-8") as log:
            subprocess.run(
                [str(bindir / "initdb"), "-D", str(root / "data"),
                 "--username", owner, "--auth-local=peer", "--auth-host=reject",
                 "--encoding=UTF8", "--locale=C", "--no-instructions", "--no-clean"],
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=120,
            )
            unit = root / f"{root.name}.service"
            write_new(unit, unit_text(root, socket, bindir))
            subprocess.run(
                ["/usr/bin/systemd-analyze", "--user", "verify", str(unit)],
                env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                check=True, timeout=30,
            )
        manifest = {
            "status": "prepared_not_started", "owner": owner, "uid": uid,
            "root": str(root), "socket": str(socket), "unit": str(unit),
            "pg_major": (root / "data/PG_VERSION").read_text().strip(),
            "unit_sha256": hashlib.sha256(unit.read_bytes()).hexdigest(),
            "postgres_sha256": hashlib.sha256((bindir / "postgres").read_bytes()).hexdigest(),
            "owner_commands": [f"systemctl --user link {unit}", f"systemctl --user start {unit.name}"],
        }
        write_new(root / "manifest.json", json.dumps(manifest, indent=2) + "\n")
        return manifest
    except Exception as exc:
        raise RuntimeError(
            f"Preparation failed; retained files at {root}; socket={socket}; cause: {exc}"
        ) from exc


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Create a NEW offline cluster; never start it")
    parser.add_argument("--parent", required=True, help="Existing owner-owned directory outside the repository")
    parser.add_argument("--pg-bindir", required=True, help="Installed PostgreSQL binary directory")
    args = parser.parse_args(argv)
    if not args.prepare:
        parser.error("Explicit --prepare is required; no files were created")
    try:
        manifest = prepare(args.parent, args.pg_bindir)
    except (ValueError, OSError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
