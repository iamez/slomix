"""H1 — the endpoint ratchet (docs/design/09 §H1).

`tests/data/endpoint_gap.txt` is the number "91 missing endpoints" turned
into a file in git that must reach zero: every API path the legacy frontend
calls (plus the deliberately-adopted extras in endpoint_required_extra.txt —
owner decision O9) that the NEW frontend does not yet call. Each build phase
deletes lines; this test fails when a deleted line comes back (regression)
and when a missing path appears that the file does not list (drift).

House rule carried from docs/design/07 §C.1: before deleting a line, verify
the path against the live /openapi.json AND call it once — two of seven
extraction anomalies there were real bugs, one was a comment.
"""
from __future__ import annotations

import re
from pathlib import Path

from tests.integration.test_route_contract import _extract_frontend_api_paths

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_SRC = REPO_ROOT / "website" / "frontend" / "src"
GAP_FILE = REPO_ROOT / "tests" / "data" / "endpoint_gap.txt"
EXTRA_FILE = REPO_ROOT / "tests" / "data" / "endpoint_required_extra.txt"

# The new tree's call shapes (measured on client.ts): the thin wrappers take
# a path-only literal — `get<T>(`/stats/overview?...`)` — plus the same
# `${API_BASE}/...` template and hardcoded `/api/...` literals the legacy
# extractor knows. Captured up to the first `?`, quote or interpolation:
# static prefixes, same contract as test_route_contract.
_NEW_WRAPPER_RE = re.compile(
    r"\b(?:get|post|put|patch|del|apiGet|apiFetch)(?:<[^>]{0,200}>)?\(\s*[`'\"](/[a-zA-Z0-9/_-]+)"
)
_NEW_TEMPLATE_RE = re.compile(r"\$\{API(?:_BASE)?\}(/[a-zA-Z0-9/_-]+)")
_NEW_LITERAL_RE = re.compile(r"(?<=['\"`}])/(?:api|auth)/[a-zA-Z0-9/_-]+")


def _extract_new_frontend_paths() -> set[str]:
    paths: set[str] = set()
    for ts_file in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        if "generated" in ts_file.parts or ts_file.name.endswith((".test.ts", ".test.tsx")):
            continue
        text = ts_file.read_text(encoding="utf-8")
        for match in _NEW_WRAPPER_RE.finditer(text):
            candidate = match.group(1).rstrip("/")
            if candidate and not candidate.startswith(("/api/", "/auth/")):
                candidate = "/api" + candidate
            if candidate:
                paths.add(candidate)
        for match in _NEW_TEMPLATE_RE.finditer(text):
            candidate = match.group(1).rstrip("/")
            if candidate:
                paths.add("/api" + candidate if not candidate.startswith("/api") else candidate)
        for match in _NEW_LITERAL_RE.finditer(text):
            paths.add(match.group(0).rstrip("/"))
    return paths


def _read_path_list(file: Path) -> set[str]:
    lines = set()
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.add(line)
    return lines


def _covered(required: str, new_paths: set[str]) -> bool:
    """A required path counts as covered when a new-tree path equals it or
    is a prefix of it (the new literal was captured before a dynamic
    segment), or extends it (required itself was a truncated legacy prefix)."""
    for candidate in new_paths:
        if candidate == required:
            return True
        if required.startswith(candidate + "/") or candidate.startswith(required + "/"):
            return True
    return False


def compute_gap() -> set[str]:
    legacy = _extract_frontend_api_paths()
    extras = _read_path_list(EXTRA_FILE)
    new_paths = _extract_new_frontend_paths()
    gap = {path for path in legacy if not _covered(path, new_paths)}
    # Extras demand an EXACT call: prefix coverage would close
    # /storytelling/win-contribution/formula the moment anything calls its
    # /storytelling/win-contribution sibling (measured while seeding).
    gap |= {path for path in extras if path not in new_paths}
    return gap


def test_endpoint_gap_matches_reality():
    assert GAP_FILE.exists(), "tests/data/endpoint_gap.txt missing — seed it (docs/design/08 faza 0)"
    listed = _read_path_list(GAP_FILE)
    actual = compute_gap()

    regressed = sorted(actual - listed)
    assert not regressed, (
        "endpoint(s) the new frontend previously covered went MISSING again "
        "(or a new legacy call appeared without a gap entry):\n"
        + "\n".join(regressed)
    )

    stale = sorted(listed - actual)
    assert not stale, (
        "gap file lists endpoint(s) the new frontend now covers — before "
        "deleting each line, verify the path against live /openapi.json and "
        "call it once (docs/design/07 §C.1), then remove:\n"
        + "\n".join(stale)
    )


def test_gap_only_shrinks_to_zero_goal():
    """Documentation guard: the file exists to reach EMPTY by switchover
    (docs/design/09 merilo #1). Fails only on an impossible state."""
    listed = _read_path_list(GAP_FILE)
    assert all(p.startswith(("/api/", "/auth/")) for p in listed), (
        "gap entries must be absolute /api or /auth paths"
    )
