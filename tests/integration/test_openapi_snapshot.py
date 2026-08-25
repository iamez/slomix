"""The committed OpenAPI snapshot must match this checkout's app.

docs/api/openapi.json is the parity harness' spine (docs/design/06 §4a):
openapi-typescript generates the new frontend's path/query types from it.
If a router change lands without re-freezing the snapshot, the generated
types silently describe an API that no longer exists — so CI regenerates
and diffs here. Fix is one command: python scripts/dump_openapi.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from dump_openapi import SNAPSHOT, generate_spec  # noqa: E402


def test_openapi_snapshot_matches_app():
    assert SNAPSHOT.exists(), (
        "docs/api/openapi.json missing — run: python scripts/dump_openapi.py"
    )
    rendered = generate_spec()
    committed = SNAPSHOT.read_text(encoding="utf-8")
    assert committed == rendered, (
        "docs/api/openapi.json is stale — the app's routes changed without "
        "re-freezing the snapshot. Run: python scripts/dump_openapi.py"
    )
