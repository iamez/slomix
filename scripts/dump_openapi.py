#!/usr/bin/env python3
"""Freeze this checkout's OpenAPI spec into docs/api/openapi.json.

The committed snapshot is the API's changelog and the spine of the parity
harness (docs/design/06 §4a): openapi-typescript generates the new
frontend's path/query types from it, and tests/integration/
test_openapi_snapshot.py regenerates it in CI and diffs — so an endpoint
change that nobody re-froze turns a PR red instead of drifting silently.

The app is imported in a fresh subprocess with the same minimal, explicit
environment as tests/integration/test_route_contract.py — never the
developer's .env — so the output depends only on the checkout.

Usage: python scripts/dump_openapi.py [--check]
  --check  regenerate to a temp buffer and exit 1 on diff (what CI runs)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "docs" / "api" / "openapi.json"

_SUBPROCESS_SCRIPT = r"""
import json
from website.backend.main import app

print(json.dumps(app.openapi(), sort_keys=True))
"""

# One list, shared shape with test_route_contract.py: prove "THIS checkout's
# app" — env-independent, DB-free import.
MINIMAL_ENV = {
    "PATH": os.environ.get("PATH", ""),
    "PYTHONPATH": str(REPO_ROOT),
    "BOT_ENVIRONMENT": "dev",
    "SSH_ENABLED": "false",
    "SESSION_SECRET": "openapi-snapshot-secret-0123456789",
    "INTERNAL_API_SECRET": "openapi-snapshot-internal-0123456789",
    "SESSION_HTTPS_ONLY": "false",
    "TRUSTED_HOSTS": "*",
    "CACHE_BACKEND": "memory",
    "PROMETHEUS_ENABLED": "false",
    "RATE_LIMIT_ENABLED": "false",
    "LOG_LEVEL": "WARNING",
}


def generate_spec() -> str:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        env=MINIMAL_ENV,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"app import failed (rc={result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    spec = json.loads(result.stdout.strip().splitlines()[-1])
    return json.dumps(spec, sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def main() -> int:
    rendered = generate_spec()
    if "--check" in sys.argv:
        current = SNAPSHOT.read_text(encoding="utf-8") if SNAPSHOT.exists() else ""
        if current != rendered:
            print(
                "docs/api/openapi.json is stale — the app's routes changed "
                "without re-freezing the snapshot. Run: python scripts/dump_openapi.py",
                file=sys.stderr,
            )
            return 1
        print("openapi snapshot up to date")
        return 0
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(rendered, encoding="utf-8")
    print(f"wrote {SNAPSHOT} ({len(rendered)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
