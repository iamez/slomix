#!/usr/bin/env python3
"""Build and validate deployable SPA provenance; timestamps are not evidence.

Run through npm run build:app (its pre-hook generates API types). Deployable
builds require a committed clean tree and no local frontend env overrides.
This is integrity/provenance bookkeeping, not a cryptographic signer or a
claim that node_modules was reproduced from the lockfile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

MANIFEST = ".slomix-build.json"
FRONTEND = Path("website/frontend")
OUTPUT = Path("website/static/app")
GENERATED = FRONTEND / "src/api/generated/openapi.d.ts"
INPUTS = [str(FRONTEND), "docs/api/openapi.json", ".nvmrc", "scripts/spa_artifact.py"]


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args])


def reject_symlink_path(root, relative):
    """Check every component before any write can traverse an output parent."""
    current = root
    for component in (".", *relative.parts):
        current = current / component
        if current.is_symlink():
            raise ValueError(f"symlinked source/output path is unsupported: {current}")


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected regular file: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(root):
    reject_symlink_path(root, OUTPUT)
    reject_symlink_path(root, GENERATED)
    commit = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if git(root, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked source is dirty; commit changes before npm run build:app")
    extras = git(root, "ls-files", "--others", "--exclude-standard", "--", str(FRONTEND))
    if extras:
        raise ValueError("untracked frontend inputs exist; track or remove them before building")
    ignored = git(root, "ls-files", "--others", "--ignored", "--exclude-standard", "-z", "--",
                  str(FRONTEND / "src"), str(FRONTEND / "public")).split(b"\0")
    if any(p and os.fsdecode(p) != str(GENERATED) for p in ignored):
        raise ValueError("ignored source/public inputs exist; only generated API types may be untracked")
    for name in [".env", ".env.local", ".env.production", ".env.production.local"]:
        if (root / FRONTEND / name).exists():
            raise ValueError("unsupported frontend .env override; use the committed build configuration")
    if any(name.startswith("VITE_") for name in os.environ):
        raise ValueError("unsupported VITE_* override; unset it before building or validating")
    if os.environ.get("NODE_ENV", "production") != "production":
        raise ValueError("deployable SPA requires NODE_ENV=production or unset")
    paths = git(root, "ls-files", "-z", "--", *INPUTS).split(b"\0")
    hashes = {}
    for path in filter(None, paths):
        relative = Path(os.fsdecode(path))
        reject_symlink_path(root, relative)
        hashes[str(relative)] = digest(root / relative)
    hashes[str(GENERATED)] = digest(root / GENERATED)
    return {"source_commit": commit, "inputs": hashes}


def output_hashes(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("missing or symlinked SPA artifact directory")
    hashes = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise ValueError("symlinks are not allowed in SPA artifacts")
        if path.is_dir():
            continue
        relative = path.relative_to(directory).as_posix()
        if relative != MANIFEST:
            hashes[relative] = digest(path)
    if "app.html" not in hashes or not any(p.endswith(".js") for p in hashes):
        raise ValueError("incomplete SPA artifact: app.html and JavaScript are required")
    return hashes


def validate(root, directory, target):
    expected = identity(root)
    record = json.loads((directory / MANIFEST).read_text())
    if record.get("version") != 1:
        raise ValueError("unsupported SPA provenance version; rebuild")
    if record.get("source_commit") != target or expected["source_commit"] != target:
        raise ValueError("SPA artifact/source does not match exact deployment target; check out target and rebuild")
    if record.get("inputs") != expected["inputs"]:
        raise ValueError("SPA build inputs changed; regenerate API types and rebuild")
    if record.get("outputs") != output_hashes(directory):
        raise ValueError("SPA artifact integrity check failed; rebuild")
    return record


def build(root):
    reject_symlink_path(root, OUTPUT)
    reject_symlink_path(root, FRONTEND)
    marker = root / OUTPUT / MANIFEST
    # Invalidate previous proof before any build attempt, including failed preflight.
    marker.unlink(missing_ok=True)
    before = identity(root)
    subprocess.run(["node", "node_modules/vite/bin/vite.js", "build", "--config", "vite.app.config.ts"],
                   cwd=root / FRONTEND, check=True)
    if identity(root) != before:
        raise ValueError("source changed during build; no deployable provenance written")
    record = {"version": 1, **before, "outputs": output_hashes(root / OUTPUT),
              "node": subprocess.check_output(["node", "--version"], text=True).strip()}
    marker.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(f"SPA provenance recorded for {before['source_commit']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "stage", "verify"])
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target")
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args()
    root = args.source.resolve()
    if args.command == "build":
        build(root)
        return
    if not args.target or not args.stage:
        parser.error("stage/verify require --target and --stage")
    if args.command == "stage":
        validate(root, root / OUTPUT, args.target)
        shutil.copytree(root / OUTPUT, args.stage, symlinks=True)
    validate(root, args.stage, args.target)
    print(f"SPA artifact verified for {args.target}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"SPA preflight refused: {error}", file=sys.stderr)
        raise SystemExit(3) from error
