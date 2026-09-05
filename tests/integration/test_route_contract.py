"""FE/API route contract test (Codex PX-DEV-003).

The frontend/backend can drift silently: a JS `fetch()` call to a path the
backend never registered returns a 404 that gets swallowed by
`Promise.allSettled` / a try/catch, and nobody notices until a user reports
a blank panel. This test proves every static API path literal referenced by
the legacy frontend (`website/js/*.js`) resolves to a REAL route on the
actual FastAPI app — from a fresh subprocess import (never the pytest
process' own already-imported module state), matching the coherence
guarantee PX-DEV-002's build handshake exists to prove at runtime.

This is intentionally a PREFIX match, not exact-path: a JS literal captured
before a `${dynamicSegment}` (e.g. `/proximity/player` before
`/${guid}/profile`) only proves the STATIC part is real; the dynamic tail is
out of static-analysis reach. That is still the failure mode PX-DEV-003
targets — a renamed/removed route prefix has no route to prefix-match at
all, and shows up here as a hard failure.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEBSITE_JS_DIR = REPO_ROOT / "website" / "js"

_SUBPROCESS_SCRIPT = r"""
import json
from website.backend.main import app

paths = sorted({route.path for route in app.routes if getattr(route, "path", None)})
print(json.dumps(paths))
"""


def _fetch_backend_route_paths() -> list[str]:
    """Import the real app in a fresh subprocess and return its route paths.

    Subprocess isolation matches tests/security/test_real_stack_security.py:
    a minimal, explicit environment (never the developer's own .env) is the
    only way "does THIS checkout's app register THIS route" is provable —
    importing main.py in-process would reuse whatever main.py some earlier
    test already imported and cached in sys.modules.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "BOT_ENVIRONMENT": "dev",
        "SESSION_SECRET": "route-contract-test-secret-0123456789",
        "INTERNAL_API_SECRET": "route-contract-test-internal-0123456789",
        "SESSION_HTTPS_ONLY": "false",
        "TRUSTED_HOSTS": "*",
        "CACHE_BACKEND": "memory",
        "PROMETHEUS_ENABLED": "false",
        "RATE_LIMIT_ENABLED": "false",
        "LOG_LEVEL": "WARNING",
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, (
        f"route-contract subprocess failed importing the app "
        f"(rc={result.returncode})\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


# API_BASE = '/api' (website/js/utils.js) — both `${API_BASE}/x` template
# literals and `scopedUrl('/x')` (which itself does `${API_BASE}${path}`,
# see proximity.js) resolve through that constant, so both forms need the
# `/api` prefix reattached; the regex captures only the path SEGMENT and
# the prefix is added below rather than hardcoded per-call-site.
_API_BASE_PREFIX = "/api"

# Matches: scopedUrl('/path/...'  OR  `${API_BASE}/path/...`  OR  `${API}/path/...`
# Captures everything up to the first `?`, closing quote/backtick, or `${`
# (an interpolation INSIDE the path — the static prefix before it is what we
# can verify; the dynamic tail is opaque to static analysis).
_FE_PATH_RE = re.compile(
    r"(?:scopedUrl\(['\"]|\$\{API(?:_BASE)?\})(/[a-zA-Z0-9/_-]+)"
)

# ⛔⛔ THE ABOVE STOPS AT THE FIRST `${`, AND THAT LOST 16 ENDPOINTS.
#
# `_FE_PATH_RE`'s comment is honest that the dynamic tail is "opaque to static
# analysis" — but a tail is only opaque if you stop there. `wrapped.js` calls
# `${API_BASE}/players/${guid}/wrapped`; the old capture was `/api/players`,
# a truncated prefix, and `_covered()` treats a truncated prefix as covered as
# soon as the new app calls ANYTHING deeper. The new app calls
# `/api/players/{identifier}/profile`, so `/api/players/{identifier}/wrapped`
# — a different operation, unbuilt — counted as migrated.
#
# Measured 2026-09-05: 29 legacy calls carry an interpolation with at least one
# more segment behind it, and 16 of them are endpoints the new app does not
# call and the gap file did not list. The ratchet read 3; the truth was 19.
#
# This is the same defect the gap file already documents for the OTHER
# extractor — a capture whose charset stops at '{' registering a stump that
# means a different operation — in the direction that HIDES work instead of
# inventing it.
#
# So: keep going across the interpolation and write each one as `{}`. The
# result is a shape, not a URL: `/api/players/{}/wrapped` can be matched
# against a spec template (`/api/players/{identifier}/wrapped`) segment by
# segment, which is exactly what `_template_matches` already does for the new
# tree. A call that ENDS in an interpolation still yields a truncated prefix,
# because there genuinely is nothing behind it to know.
_INTERPOLATION_RE = re.compile(r"\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}")
_FE_FULL_PATH_RE = re.compile(
    r"(?:scopedUrl\(['\"]|\$\{API(?:_BASE)?\})"
    r"((?:/(?:[a-zA-Z0-9_-]+|\$\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}))+)"
)


def _normalise_call(raw: str, glued: bool = False) -> tuple[str, bool]:
    """Return (path, is_truncated_prefix) for one captured call.

    A path whose last segment was an interpolation keeps the old meaning: we
    know a prefix and nothing more, so it is a DYNAMIC prefix. A path with a
    literal segment behind the interpolation is fully known as a shape.

    ⛔ `glued` is not a detail. `availability.js:1592` writes
    `${API_BASE}/planning${path}` — the interpolation is stuck to the segment
    with no '/' between them, so the regex (which needs a '/' to start a
    segment) stops after `/planning` and the result LOOKS like a complete
    two-segment path. It is not: the tail is opaque, exactly like a trailing
    interpolation. Called with glued=True the caller says "the source
    continues into an interpolation here", and this reports a prefix.
    Without it the first version of this change moved /api/planning from
    covered to missing and would have had someone hunting a phantom.
    """
    path = _API_BASE_PREFIX + _INTERPOLATION_RE.sub("{}", raw).rstrip("/")
    if glued:
        return path, True
    if path.endswith("/{}"):
        # Nothing is known behind the last interpolation. Strip every trailing
        # one and report a prefix — the old behaviour, still correct here.
        while path.endswith("/{}"):
            path = path[: -len("/{}")]
        return path, True
    return path, False

# Matches a hardcoded `/api/...` literal wherever it appears — covers call
# sites that skip the API_BASE constant entirely, e.g. auth.js's
# `fetch('/api/availability/link-token', ...)` and diagnostics.js's endpoint
# table (`{ endpoint: '/api/stats/overview', ... }`, later interpolated as
# `${getApiBase()}${test.endpoint}` — a variable name _FE_PATH_RE doesn't
# recognize, but the literal itself already carries the real `/api/...`
# path, so no prefix needs reattaching here). The lookbehind requires an
# opening quote/backtick or a template interpolation's closing `}`
# immediately before `/api/` — i.e. this must be the START of an actual
# string literal, not prose. Without it, doc-comments that merely MENTION a
# path (admin-panel.js: "Future: pull from a /api/version endpoint") would
# be scanned as real fetch targets and fail the test on a comment, not code.
_FE_LITERAL_API_RE = re.compile(r"(?<=['\"`}])/api/[a-zA-Z0-9/_-]+")


# website/js/community.js is dead code: no other JS module imports it and
# it is not <script>-tagged anywhere in website/index.html, so its
# fetch('${API_BASE}/community/...') call is unreachable — the backend
# genuinely has no /api/community route (confirmed: zero hits repo-wide).
# This test's job is FE/backend drift on LIVE code; an orphaned file with a
# stale call is a separate (low-severity) cleanup, not this PR's scope.
_EXCLUDED_JS_FILES = {"community.js"}


def _extract_frontend_api_paths() -> set[str]:
    paths: set[str] = set()
    for js_file in sorted(WEBSITE_JS_DIR.glob("*.js")):
        if js_file.name in _EXCLUDED_JS_FILES:
            continue
        text = js_file.read_text(encoding="utf-8")
        for match in _FE_FULL_PATH_RE.finditer(text):
            path, _ = _normalise_call(match.group(1), text[match.end():match.end() + 2] == "${")
            if path.strip("/"):
                paths.add(path)
        for match in _FE_LITERAL_API_RE.finditer(text):
            path = match.group(0).rstrip("/")
            if path:
                paths.add(path)
    return paths


def _segments(path: str) -> list[str]:
    return [p for p in path.split("/") if p]


def _is_param_segment(segment: str) -> bool:
    return segment.startswith("{") and segment.endswith("}")


def _backend_route_has_prefix(route_path: str, fe_prefix_segments: list[str]) -> bool:
    """True if `route_path`'s segments match `fe_prefix_segments` one-to-one
    (a FastAPI `{param}` segment matches anything) for the FULL length of the
    FE prefix — the route may continue further (the FE literal was captured
    before a dynamic segment, e.g. `/proximity/player` before
    `/${guid}/profile` on a route registered as
    `/proximity/player/{guid}/profile`)."""
    route_segments = _segments(route_path)
    if len(route_segments) < len(fe_prefix_segments):
        return False
    for fe_seg, route_seg in zip(fe_prefix_segments, route_segments):
        # Either side may be a parameter: the backend registers `{round_id}`,
        # and since the extractor started reading THROUGH interpolations the
        # frontend side carries `{}` for the same segment.
        if _is_param_segment(route_seg) or _is_param_segment(fe_seg):
            continue
        if fe_seg != route_seg:
            return False
    return True


@pytest.fixture(scope="module")
def backend_route_paths() -> list[str]:
    return _fetch_backend_route_paths()


def test_backend_exposes_routes():
    """Sanity: the subprocess import actually produced routes (a totally
    broken import would otherwise make every prefix-match test below
    vacuously pass with zero routes to check against)."""
    paths = _fetch_backend_route_paths()
    assert len(paths) > 50, f"suspiciously few routes registered: {len(paths)}"
    assert "/health" in paths
    assert "/api/build" in paths


def test_every_frontend_api_path_prefix_matches_a_real_route(backend_route_paths):
    fe_paths = _extract_frontend_api_paths()
    assert fe_paths, "extracted zero FE API paths — regex likely stopped matching website/js/*.js"

    unmatched = sorted(
        fe_path
        for fe_path in fe_paths
        if not any(
            _backend_route_has_prefix(route_path, _segments(fe_path))
            for route_path in backend_route_paths
        )
    )
    assert not unmatched, (
        "frontend references API path(s) with NO matching backend route "
        "(renamed/removed endpoint, or the regex needs updating for a new "
        "fetch pattern):\n" + "\n".join(unmatched)
    )
