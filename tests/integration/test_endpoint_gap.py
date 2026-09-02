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
# The NEW frontend is `src/app` — nothing else. `src/` also holds the older
# React tree (src/pages, src/api/hooks.ts), which is a THIRD frontend: not the
# vanilla site in production, not the app being built. Scanning all of `src`
# counted its calls as migration progress, so an endpoint only that tree ever
# called looked covered. Measured when the miscount was found: gap 64 as
# reported, 120 when only `app` counts — 56 paths hidden (Codex on #835 found
# the first of them, /api/skill/adjusted-lifetime, one endpoint at a time).
# The mistake it prevents is silent; the direction it can still err in is not:
# an app call made from a shared module OUTSIDE this root simply goes unseen
# and its path stays listed, which shows up as work that will not delete.
APP_SRC = FRONTEND_SRC / "app"
GAP_FILE = REPO_ROOT / "tests" / "data" / "endpoint_gap.txt"
EXTRA_FILE = REPO_ROOT / "tests" / "data" / "endpoint_required_extra.txt"

# The new tree's call shapes (measured on client.ts): the thin wrappers take
# a path-only literal — `get<T>(`/stats/overview?...`)` — plus the same
# `${API_BASE}/...` template and hardcoded `/api/...` literals the legacy
# extractor knows. Captured up to the first `?`, quote or interpolation:
# static prefixes, same contract as test_route_contract.
# Braces included: a typed template call — apiGet('/api/seasons/{season_id}/
# awards') — must be captured WHOLE, or the capture stops at '{' and
# registers a bare two-segment prefix (found in phase 2, batch 2).
# apiPost/apiUpload/apiDelete joined the alternation in phase 6 slice 2: a
# templated WRITE — apiPost('/api/bets/market/{market_id}/bet') — was not a
# wrapper match, so only _NEW_LITERAL_RE saw it, and that charset stops at
# '{': the capture was the bare '/api/bets/market', which is a DIFFERENT
# operation (the admin market-open POST, unbuilt) — the line would have been
# reported stale and deleted for work that did not happen. Pinned by
# test_templated_write_does_not_register_its_truncated_prefix.
_NEW_WRAPPER_RE = re.compile(
    r"\b(?:get|post|put|patch|del|apiGet|apiFetch|apiPost|apiUpload|apiDelete)"
    r"(?:<[^>]{0,200}>)?\(\s*[`'\"](/[a-zA-Z0-9/_{}-]+)"
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


def _extract_new_frontend_paths(root: Path | None = None) -> tuple[set[str], set[str]]:
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

    root = APP_SRC if root is None else root
    for ts_file in sorted(root.rglob("*.ts")) + sorted(root.rglob("*.tsx")):
        if "generated" in ts_file.parts or ts_file.name.endswith((".test.ts", ".test.tsx")):
            continue
        # probes.ts is the About page's diagnostics table: it PINGS endpoints
        # to report reachability, it does not render their data — counting it
        # would clear ~10 gap lines for pages that don't exist (measured
        # while building About). test_probe_registry_paths_exist keeps the
        # excluded file from rotting.
        if ts_file.name == "probes.ts":
            continue
        text = _strip_comments(ts_file.read_text(encoding="utf-8"))
        for rx in (_NEW_WRAPPER_RE, _NEW_TEMPLATE_RE):
            for match in rx.finditer(text):
                add(match.group(1), text, match.end())
        for match in _NEW_LITERAL_RE.finditer(text):
            # A literal whose charset stopped at '{' is the head of a spec
            # TEMPLATE, not a call: '/api/bets/market' cut out of
            # apiPost('/api/bets/market/{market_id}/bet'). The wrapper regex
            # registers the template whole; registering the stump as an
            # exact call would clear a legacy exact requirement for an
            # operation nobody built (slice 2 of phase 6).
            if text[match.end():match.end() + 1] == "{":
                continue
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


def _template_matches(template: str, path: str) -> bool:
    """A spec-templated app call (apiGet('/api/seasons/{season_id}/awards'))
    covers a legacy literal (/api/seasons/current/awards) when the concrete
    path instantiates the template — segment count equal, non-parameter
    segments identical. Without this, calling THROUGH the typed template
    would leave the legacy line stale forever (hit in phase 2, batch 2)."""
    if "{" not in template:
        return False
    t_segs = [s for s in template.split("/") if s]
    p_segs = [s for s in path.split("/") if s]
    if len(t_segs) != len(p_segs):
        return False
    return all(
        ts.startswith("{") and ts.endswith("}") or ts == ps
        for ts, ps in zip(t_segs, p_segs)
    )


def _covered(required: str, required_is_dynamic: bool, exact: set[str], dynamic: set[str]) -> bool:
    """Covered when: a call equals it; a spec template instantiates it; a
    call is DEEPER than it AND the required capture itself was a truncated
    dynamic prefix; or a DYNAMIC new-tree prefix of sufficient specificity
    leads into it. An exact literal never covers a deeper required path in
    either direction (Codex, twice), and a dynamic family stub never clears
    a whole family (CodeRabbit)."""
    if required in exact or required in dynamic:
        return True
    if any(_template_matches(candidate, required) for candidate in exact):
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


def test_the_other_react_tree_does_not_count_as_migrated():
    """A call from `src/pages` is not progress on `src/app`.

    This is the guard for the miscount described at APP_SRC, and it asserts
    the consequence rather than the setting: every path that the WIDER scan
    would call covered, but the app tree does not actually call, has to still
    be in the gap. Asserting `FRONTEND_SRC != APP_SRC` would pass for a scan
    root pointed anywhere at all.

    The first assertion is the load-bearing one: if the two trees ever stop
    differing the guard is vacuous, and a vacuous guard reads exactly like a
    passing one.
    """
    required_exact, required_dynamic = _extract_legacy_paths_tagged()
    required = required_exact | required_dynamic
    wide = _extract_new_frontend_paths(FRONTEND_SRC)
    narrow = _extract_new_frontend_paths(APP_SRC)

    def covered_by(sets: tuple[set[str], set[str]], path: str) -> bool:
        return _covered(path, path in required_dynamic and path not in required_exact, *sets)

    only_the_old_tree = {
        path for path in required
        if covered_by(wide, path) and not covered_by(narrow, path)
    }
    assert only_the_old_tree, (
        "no required path is called by the old React tree alone — either that "
        "tree is gone (delete this guard and the narrowing) or the scan root "
        "has drifted back to covering both"
    )
    leaked = sorted(only_the_old_tree - compute_gap())
    assert not leaked, (
        "path(s) counted as migrated on the strength of the OLD React tree:\n"
        + "\n".join(leaked)
    )


def test_probe_registry_paths_exist():
    """probes.ts is excluded from the extractor above AND from the H4
    fixture-coverage test — it is invisible to both ratchets, so the
    exclusion needs guards that actually hold what its docstring claims
    (brother's review on #809: the original asserted a row COUNT while
    claiming 'verbatim', and asserted nothing about data calls at all):

    - pings only: the file must never call apiGet nor read a body — a data
      call added here would count NOWHERE;
    - verbatim means verbatim: the (endpoint, required) pairs must equal
      the legacy diagnostics.js API table, read from the source;
    - every probed path must exist in the committed OpenAPI snapshot, so
      the table cannot rot into probing endpoints that are gone."""
    import json

    probes_file = FRONTEND_SRC / "app" / "lib" / "probes.ts"
    assert probes_file.exists(), "probes.ts moved — update BOTH ratchet exclusions too"
    probes_text = probes_file.read_text(encoding="utf-8")

    assert "apiGet" not in probes_text, (
        "probes.ts is excluded from both ratchets; an apiGet here counts nowhere"
    )
    assert ".json(" not in probes_text, (
        "a probe reports reachability — reading a body makes it a data call "
        "that neither ratchet can see"
    )

    probe_rows = {
        (m.group(1), m.group(2) == "true")
        for m in re.finditer(
            r"endpoint:\s*'([^']+)',\s*required:\s*(true|false)", probes_text
        )
    }
    legacy_text = (WEBSITE_JS_DIR / "diagnostics.js").read_text(encoding="utf-8")
    api_block = legacy_text.split("api: [", 1)[1].split("]", 1)[0]
    legacy_rows = {
        (m.group(1), m.group(2) == "true")
        for m in re.finditer(
            r"endpoint:\s*'([^']+)',\s*required:\s*(true|false)", api_block
        )
    }
    assert legacy_rows, "diagnostics.js API table not found — extraction broke"
    assert probe_rows == legacy_rows, (
        "the probe table must be diagnostics.js's API table verbatim; diff: "
        f"only-in-probes={sorted(probe_rows - legacy_rows)}, "
        f"only-in-legacy={sorted(legacy_rows - probe_rows)}"
    )

    spec_paths = set(
        json.loads((REPO_ROOT / "docs" / "api" / "openapi.json").read_text(encoding="utf-8"))["paths"]
    )
    missing = sorted({e.split("?")[0] for e, _ in probe_rows} - spec_paths)
    assert not missing, f"probe path(s) not in the OpenAPI snapshot: {missing}"


def test_gap_only_shrinks_to_zero_goal():
    """Documentation guard: the file exists to reach EMPTY by switchover
    (docs/design/09 merilo #1). Fails only on an impossible state."""
    listed = _read_path_list(GAP_FILE)
    assert all(p.startswith(("/api/", "/auth/")) for p in listed), (
        "gap entries must be absolute /api or /auth paths"
    )


def test_templated_write_does_not_register_its_truncated_prefix(tmp_path: Path):
    """A templated apiPost/apiDelete must be captured WHOLE (template), never
    as the two-or-three-segment literal its '{' cuts it down to. The control
    is the pre-slice-2 alternation, run on the same text: it DID register
    the truncated prefix — that is the false coverage this test exists for."""
    src = tmp_path / "app"
    src.mkdir()
    (src / "queries.ts").write_text(
        "export const bet = (id: number) =>\n"
        "  apiPost('/api/bets/market/{market_id}/bet', {}, { pathParams: { market_id: id } });\n"
        "export const unlink = (c: string) =>\n"
        "  apiDelete('/api/availability/subscriptions/{channel_type}', { pathParams: { channel_type: c } });\n",
        encoding="utf-8",
    )
    exact, dynamic = _extract_new_frontend_paths(src)
    assert "/api/bets/market/{market_id}/bet" in exact
    assert "/api/availability/subscriptions/{channel_type}" in exact
    assert "/api/bets/market" not in exact, "the truncated prefix registered as an exact call"
    assert "/api/availability/subscriptions" not in exact
    assert not dynamic
    # The template must NOT clear the legacy exact requirement /api/bets/market
    # (different segment count -> not an instantiation).
    assert not _covered("/api/bets/market", False, exact, dynamic)

    # Control: the previous alternation, on the same file, registers the
    # truncated prefix — the guard has a subject.
    old_wrapper = re.compile(
        r"\b(?:get|post|put|patch|del|apiGet|apiFetch)(?:<[^>]{0,200}>)?\(\s*[`'\"](/[a-zA-Z0-9/_{}-]+)"
    )
    text = (src / "queries.ts").read_text(encoding="utf-8")
    assert not old_wrapper.search(text)
    literal_hits = {m.group(0).rstrip("/") for m in _NEW_LITERAL_RE.finditer(text)}
    assert "/api/bets/market" in literal_hits, "control: the old extraction no longer misreads — retire this test"
