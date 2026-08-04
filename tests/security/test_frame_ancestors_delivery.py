"""frame-ancestors must be delivered as a header, and only as a header.

The CSP spec ignores frame-ancestors (along with report-uri and sandbox) when
the policy arrives in a <meta> tag. It sat in website/index.html's meta policy
for a long time, doing nothing except making browsers log a warning on every
page load, while X-Frame-Options carried the actual protection.

These pin both halves of the fix: the header exists, and the meta copy does not
come back. A regression in either direction is silent in a browser.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_PY = REPO_ROOT / "website" / "backend" / "main.py"
INDEX_HTML = REPO_ROOT / "website" / "index.html"


def _meta_csp() -> str:
    html = INDEX_HTML.read_text(encoding="utf-8")
    match = re.search(
        r'<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]*)"',
        html,
    )
    assert match, "index.html has no meta Content-Security-Policy"
    return match.group(1)


def test_meta_policy_does_not_claim_frame_ancestors():
    assert "frame-ancestors" not in _meta_csp(), (
        "frame-ancestors is ignored in a <meta> policy — it belongs in the "
        "response header set by add_security_headers() in main.py"
    )


def test_meta_policy_still_carries_the_directives_that_do_work():
    """Guard against 'fixing' this by deleting the whole meta policy."""
    policy = _meta_csp()
    for directive in ("default-src", "script-src", "object-src", "base-uri", "form-action"):
        assert directive in policy, directive


def test_response_header_sets_frame_ancestors():
    source = MAIN_PY.read_text(encoding="utf-8")
    assert 'response.headers["Content-Security-Policy"]' in source
    assert "frame-ancestors 'self'" in source


def test_x_frame_options_is_kept_alongside():
    """X-Frame-Options is the older equivalent and still the one some clients
    honour, so the CSP header supplements it rather than replacing it."""
    source = MAIN_PY.read_text(encoding="utf-8")
    assert 'response.headers["X-Frame-Options"] = "SAMEORIGIN"' in source
