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

from tests.integration.test_route_contract import (
    _API_BASE_PREFIX,
    _EXCLUDED_JS_FILES,
    _FE_LITERAL_API_RE,
    _FE_PATH_RE,
    WEBSITE_JS_DIR,
    _extract_frontend_api_paths,
)

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


_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
_LINE_COMMENT_RE = re.compile(r"^\s*//.*$", re.M)


def _strip_comments(text: str) -> str:
    """Paths quoted in comments are documentation, not calls — the api.ts
    doc-comment's example literally registered /api/rounds as coverage
    (Codex on #802). Block comments and full-line // comments go; trailing
    // after code is left alone (a ':' in 'https://' makes that cut unsafe)."""
    return _LINE_COMMENT_RE.sub("", _BLOCK_COMMENT_RE.sub("", text))


def _extract_new_frontend_paths() -> tuple[set[str], set[str]]:
    """Returns (exact, dynamic_prefixes): a capture that stopped at an
    interpolation (`${`) is a truncated DYNAMIC prefix and may claim deeper
    coverage; an exact literal covers only itself (Codex on #802 — an exact
    /api/bets call must not clear /api/bets/market)."""
    exact: set[str] = set()
    dynamic: set[str] = set()

    def add(candidate: str, text: str, end: int) -> None:
        candidate = candidate.rstrip("/")
        if not candidate:
            return
        if not candidate.startswith(("/api/", "/auth/")):
            candidate = "/api" + candidate
        (dynamic if text[end:end + 2] == "${" else exact).add(candidate)

    for ts_file in sorted(FRONTEND_SRC.rglob("*.ts")) + sorted(FRONTEND_SRC.rglob("*.tsx")):
        if "generated" in ts_file.parts or ts_file.name.endswith((".test.ts", ".test.tsx")):
            continue
        text = _strip_comments(ts_file.read_text(encoding="utf-8"))
        for rx in (_NEW_WRAPPER_RE, _NEW_TEMPLATE_RE):
            for match in rx.finditer(text):
                add(match.group(1), text, match.end())
        for match in _NEW_LITERAL_RE.finditer(text):
            add(match.group(0), text, match.end())
    return exact, dynamic


def _extract_legacy_paths_tagged() -> tuple[set[str], set[str]]:
    """Same captures as test_route_contract's extractor, plus a tag: a match
    immediately followed by an interpolation is a DYNAMIC (truncated) prefix.
    Needed because an EXACT legacy call (availability.js's /api/bets/market)
    must stay in the gap even when a deeper sibling is migrated first —
    deeper-candidate coverage is only sound for truncated prefixes (Codex
    third-wave on #802)."""
    exact: set[str] = set()
    dynamic: set[str] = set()
    for js_file in sorted(WEBSITE_JS_DIR.glob("*.js")):
        if js_file.name in _EXCLUDED_JS_FILES:
            continue
        text = js_file.read_text(encoding="utf-8")
        for match in _FE_PATH_RE.finditer(text):
            path = match.group(1).rstrip("/")
            if path:
                target = dynamic if text[match.end():match.end() + 2] == "${" else exact
                target.add(_API_BASE_PREFIX + path)
        for match in _FE_LITERAL_API_RE.finditer(text):
            path = match.group(0).rstrip("/")
            if path:
                target = dynamic if text[match.end():match.end() + 2] == "${" else exact
                target.add(path)
    return exact, dynamic


def _read_path_list(file: Path) -> set[str]:
    lines = set()
    for raw in file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            lines.add(line)
    return lines


# A candidate shorter than this many segments ("/api/proximity" = 2) may NOT
# claim coverage of deeper required paths: one templated call captured as a
# bare family prefix would otherwise clear every /api/proximity/* line and
# hide missing migration work (CodeRabbit on #802).
_MIN_COVERING_SEGMENTS = 3


def _covered(required: str, required_is_dynamic: bool, exact: set[str], dynamic: set[str]) -> bool:
    """Covered when: a call equals it; a call is DEEPER than it AND the
    required capture itself was a truncated dynamic prefix; or a DYNAMIC
    new-tree prefix of sufficient specificity leads into it. An exact
    literal never covers a deeper required path in either direction (Codex,
    twice), and a dynamic family stub never clears a whole family
    (CodeRabbit)."""
    if required in exact or required in dynamic:
        return True
    if required_is_dynamic:
        for candidate in exact | dynamic:
            if candidate.startswith(required + "/"):
                return True
    for candidate in dynamic:
        if (
            required.startswith(candidate + "/")
            and len([seg for seg in candidate.split("/") if seg]) >= _MIN_COVERING_SEGMENTS
        ):
            return True
    return False


def compute_gap() -> set[str]:
    legacy_exact, legacy_dynamic = _extract_legacy_paths_tagged()
    # Cross-check against the untagged extractor so the two can never drift.
    assert legacy_exact | legacy_dynamic == _extract_frontend_api_paths(), (
        "tagged legacy extraction diverged from test_route_contract's"
    )
    extras = _read_path_list(EXTRA_FILE)
    exact, dynamic = _extract_new_frontend_paths()
    gap = {
        path
        for path in legacy_exact | legacy_dynamic
        # captured exact ANYWHERE -> the exact requirement wins
        if not _covered(path, path in legacy_dynamic and path not in legacy_exact, exact, dynamic)
    }
    # Extras demand an EXACT call: prefix coverage would close
    # /storytelling/win-contribution/formula the moment anything calls its
    # /storytelling/win-contribution sibling (measured while seeding).
    gap |= {path for path in extras if path not in exact}
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
