"""Build/revision handshake (Codex PX-DEV-002).

Root cause this closes: a long-lived dev Uvicorn process can keep running
OLD Python route handlers while `StaticFiles` serves a NEWER frontend from
the same mutable checkout, and some request-time lazy imports pull in newer
service code — three different "versions" answering one request with no way
for an operator (or the frontend) to detect the mismatch from outside.

`/api/build` gives every request a way to ask "what code is this process
actually running right now?" without touching the database:

- `revision`: the git commit this PROCESS was started from (read once at
  import — a mutable checkout that `git checkout`s a newer commit AFTER the
  process started must NOT silently start reporting the new SHA; that is
  exactly the mixed-revision state this endpoint exists to expose).
- `started_at`: process start time, so "has this actually restarted since
  the last deploy?" is answerable without SSH.
- `api_contract`: a stable hash of the live FastAPI route table (method +
  path). Two processes serving genuinely different route sets — the classic
  symptom of one on old code, one on new — get different hashes; comparable
  against the frontend's own build-time route manifest (PX-FE-001/PX-DEV-003).
- `schema_ledger_max_file`: the highest-numbered migration FILE present in
  this checkout's migrations/ directory. This is a static, DB-free read of
  "what migrations does this code EXPECT to exist" — not a live query of
  what has actually been applied (that's the separate, DB-touching
  fingerprint added to the migration runner for PX-DB-001).
"""

from __future__ import annotations

import hashlib
import re
import subprocess  # nosec B404 - used only by _read_git_revision() below with a fixed argv, no shell, no user input
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"

_NUM_PREFIX = re.compile(r"^(\d+)")

# Captured once at import (process start), not per-request: the whole point
# is to freeze "what commit was this PROCESS started from" so a later
# checkout-in-place can't retroactively rewrite what an already-running
# process claims to be.
_STARTED_AT = datetime.now(timezone.utc)


def _read_git_revision() -> tuple[str | None, str | None]:
    """(full_sha, short_sha) of HEAD, or (None, None) if unavailable.

    Never raises: a container image built without a .git directory (or with
    git absent) must not crash the app over a diagnostics field.
    """
    try:
        out = subprocess.run(  # noqa: S603 # nosec B603 - fixed argv, no shell, no user input
            ["/usr/bin/env", "git", "rev-parse", "HEAD"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if out.returncode != 0:
            return None, None
        full = out.stdout.strip()
        if not full:
            return None, None
        return full, full[:8]
    except Exception:  # pragma: no cover - defensive, must never crash startup
        return None, None


_GIT_REVISION, _GIT_REVISION_SHORT = _read_git_revision()


def _max_migration_file_version() -> str | None:
    """Highest numeric-prefixed migration filename in migrations/, or None.

    Legacy unnumbered files (e.g. add_session_results.sql) are ignored for
    this purpose — they predate the numbered-ledger convention and don't
    represent "the newest migration this build expects".
    """
    if not MIGRATIONS_DIR.is_dir():
        return None
    best: tuple[int, str] | None = None
    for path in MIGRATIONS_DIR.glob("*.sql"):
        m = _NUM_PREFIX.match(path.name)
        if not m:
            continue
        num = int(m.group(1))
        if best is None or num > best[0]:
            best = (num, path.stem)
    return best[1] if best else None


_SCHEMA_LEDGER_MAX_FILE = _max_migration_file_version()


def compute_api_contract_hash(app: Any) -> str:
    """Stable short hash of the live route table (method + path).

    Computed from `app.routes` at call time (not cached at import) so it
    always reflects whatever routers are ACTUALLY mounted on this app
    instance right now — including in tests that build a minimal app with a
    subset of routers.
    """
    pairs: list[str] = []
    for route in getattr(app, "routes", []):
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or not methods:
            continue
        pairs.extend(f"{method} {path}" for method in sorted(methods))
    pairs.sort()
    digest = hashlib.sha256("\n".join(pairs).encode("utf-8")).hexdigest()
    return digest[:16]


def get_build_info(app: Any) -> dict[str, Any]:
    return {
        "revision": _GIT_REVISION,
        "revision_short": _GIT_REVISION_SHORT,
        "started_at": _STARTED_AT.isoformat(),
        "api_contract": compute_api_contract_hash(app),
        "schema_ledger_max_file": _SCHEMA_LEDGER_MAX_FILE,
    }


def build_header_value() -> str:
    """Value for the X-Slomix-Build response header — cheap, no route hash
    (that requires the app object; the header is stamped per-response by
    middleware that doesn't have convenient route-table access on every
    call). revision_short + started_at is enough to catch "this response
    came from a stale process"."""
    rev = _GIT_REVISION_SHORT or "unknown"
    return f"{rev}@{_STARTED_AT.strftime('%Y%m%dT%H%M%SZ')}"
