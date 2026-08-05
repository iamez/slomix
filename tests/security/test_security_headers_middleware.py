"""add_security_headers must add defaults without overriding route decisions.

The middleware runs AFTER call_next, so a plain assignment overwrites whatever
the route already set. That matters for exactly one class of response: routes
serving user-uploaded bytes. uploads.py sends `default-src 'none'` (plus
`media-src 'self'` for inline media) and `X-Frame-Options: DENY` precisely so
attacker-supplied files cannot execute or be framed.

Isolation follows test_real_stack_security.py: main.py reads env at import and
fails fast without secrets, so the assertions run in a SUBPROCESS with a
minimal explicit environment. The middleware is invoked directly rather than
through a request, because main.py mounts StaticFiles at "/" — a probe route
registered after import is shadowed by that mount and never runs, which is a
trap worth not falling into twice.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SUBPROCESS_SCRIPT = '''
import asyncio
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

from starlette.responses import Response

from website.backend.main import add_security_headers


async def run_through(route_headers):
    async def call_next(_request):
        return Response("x", headers=route_headers)

    return await add_security_headers(None, call_next)


async def main():
    # 1. Ordinary page: middleware supplies everything.
    plain = await run_through({})
    assert plain.headers["Content-Security-Policy"] == "frame-ancestors 'self'", (
        plain.headers.get("Content-Security-Policy")
    )
    assert plain.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert plain.headers["X-Content-Type-Options"] == "nosniff"

    # 2. Upload inline (video): trailing semicolon, no X-Frame-Options.
    inline = await run_through(
        {"Content-Security-Policy": "default-src 'none'; media-src 'self';"}
    )
    csp = inline.headers["Content-Security-Policy"]
    assert "default-src 'none'" in csp, f"route policy lost: {csp}"
    assert "media-src 'self'" in csp, f"route policy lost: {csp}"
    assert "frame-ancestors 'self'" in csp, f"frame-ancestors missing: {csp}"
    assert ";;" not in csp, f"malformed policy: {csp}"

    # 3. Upload attachment: no trailing semicolon, and a STRICTER
    #    X-Frame-Options than the middleware default.
    attach = await run_through(
        {"Content-Security-Policy": "default-src 'none'", "X-Frame-Options": "DENY"}
    )
    csp = attach.headers["Content-Security-Policy"]
    assert csp == "default-src 'none'; frame-ancestors 'self'", csp
    assert attach.headers["X-Frame-Options"] == "DENY", (
        "DENY must not be downgraded to SAMEORIGIN"
    )

    # 4. A route that already scopes frame-ancestors keeps its own value.
    scoped = await run_through(
        {"Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'"}
    )
    assert scoped.headers["Content-Security-Policy"].count("frame-ancestors") == 1
    assert "frame-ancestors 'none'" in scoped.headers["Content-Security-Policy"]

    print("SECURITY_HEADERS_OK")


asyncio.run(main())
'''


def test_security_headers_do_not_clobber_route_policies():
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "SESSION_SECRET": "security-headers-test-secret-0123456789",
        "INTERNAL_API_SECRET": "security-headers-test-internal-0123456789",
        "TRUSTED_HOSTS": "www.slomix.fyi,slomix.fyi,localhost,127.0.0.1",
        "WEB_LOG_DIR": os.environ.get("WEB_LOG_DIR", "/tmp"),
        "BOT_LOG_DIR": os.environ.get("BOT_LOG_DIR", "/tmp"),
    }

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(REPO_ROOT),
    )

    assert "SECURITY_HEADERS_OK" in result.stdout, (
        f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
    )
