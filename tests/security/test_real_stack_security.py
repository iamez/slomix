"""Real-stack security regression (IMP-006).

test_host_path_security.py proves the security PRIMITIVES on a minimal app
built from the same building blocks. This test goes one step further and
exercises the REAL `website.backend.main.app` — the production middleware
stack in its production order — because the audit's residual risk was exactly
"the minimal app might not match what main.py actually wires".

Isolation: main.py reads env at import and fails fast without secrets, so the
assertions run in a SUBPROCESS with a minimal, explicit environment (the
pytest process's own env/config never leaks in, and the heavyweight app import
never pollutes the test runner). httpx ASGITransport drives the app without
its lifespan, so no DB/Redis is needed: /health answers 503 (DB unavailable),
which still proves the request PASSED the outermost host gate (≠ 400).

Proven order, with a REAL signed session cookie (built exactly like
Starlette's SessionMiddleware: json → b64 → itsdangerous TimestampSigner):

  mutation with disallowed Origin + good Host → 403 (CSRF fired)
  same request with bad Host              → 400 (host gate fired FIRST)
  same request without the cookie         → 404 (no session → CSRF skipped)

The 403-vs-400-vs-404 triangle is what pins the ordering: a stack with the
host gate inside CSRF would 403 the bad-Host request, and a stack that never
decodes the session cookie would 404 the first request.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SUBPROCESS_SCRIPT = r"""
import asyncio
import base64
import json
import os

import httpx
import itsdangerous

from website.backend.main import app

GOOD_HOST = "www.slomix.fyi"
BAD_HOSTS = [
    "evil.example",                 # not on the allow-list
    "www.slomix.fyi/",              # trailing slash — malformed
    "www.slomix.fyi/../admin",      # embedded path
    "www.slomix.fyi:443/../admin",  # colon-embedded path (split(':')[0] bypass)
    "www.slomix.fyi:notaport",      # non-numeric port
]


def build_session_cookie() -> str:
    # Exactly Starlette SessionMiddleware's write path: json -> b64 ->
    # TimestampSigner(secret).sign. A valid signature is REQUIRED for the
    # CSRF middleware to see request.session["user"].
    payload = base64.b64encode(
        json.dumps({"user": {"id": "42", "username": "real-stack-test"}}).encode("utf-8")
    )
    signer = itsdangerous.TimestampSigner(str(os.environ["SESSION_SECRET"]))
    return signer.sign(payload).decode("utf-8")


async def main() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="https://www.slomix.fyi"
    ) as client:
        # 1) Outermost host gate: good Host passes (503 = DB-less /health,
        #    anything but 400 proves the gate let it through)...
        r = await client.get("/health", headers={"host": GOOD_HOST})
        assert r.status_code != 400, f"good Host must pass the gate, got {r.status_code}"

        # 2) ...and every malformed/untrusted Host dies with 400 first.
        for bad in BAD_HOSTS:
            r = await client.get("/health", headers={"host": bad})
            assert r.status_code == 400, f"Host {bad!r} must 400, got {r.status_code}"

        # 3) Host gate runs BEFORE CSRF — proven with a real signed session.
        cookie = build_session_cookie()
        mutation = "/api/csrf-order-probe"
        evil_origin = "https://evil.example"

        r = await client.post(
            mutation,
            headers={"host": GOOD_HOST, "origin": evil_origin, "cookie": f"session={cookie}"},
        )
        assert r.status_code == 403, f"good Host + bad Origin must hit CSRF (403), got {r.status_code}"

        r = await client.post(
            mutation,
            headers={"host": "evil.example", "origin": evil_origin, "cookie": f"session={cookie}"},
        )
        assert r.status_code == 400, f"bad Host must 400 BEFORE CSRF, got {r.status_code}"

        # Control: without the session cookie there is no user, CSRF skips,
        # and the unknown route 404s — proving the 403 above came from the
        # DECODED session, not from some blanket Origin filter. The jar must
        # be emptied first: SessionMiddleware re-issued the session as a
        # Set-Cookie on the 403 and httpx stored it.
        client.cookies.clear()
        r = await client.post(mutation, headers={"host": GOOD_HOST, "origin": evil_origin})
        # 404 or 405 (a GET-only wildcard route may claim the path): either
        # way the ROUTER answered, i.e. CSRF let the session-less request by.
        assert r.status_code in (404, 405), f"no session must skip CSRF, got {r.status_code}"


asyncio.run(main())
print("REAL-STACK-SECURITY-OK")
"""


def test_real_app_host_gate_and_csrf_order():
    env = {
        # Minimal, explicit environment: nothing from the runner's env may
        # leak in (a developer's .env-sourced TRUSTED_HOSTS/SESSION_* would
        # change what is being proven). PATH is needed to exec python.
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": str(REPO_ROOT),
        "SESSION_SECRET": "real-stack-test-session-secret-0123456789",
        "INTERNAL_API_SECRET": "real-stack-test-internal-secret-0123456789",
        # Production posture: https-only sessions + explicit host allow-list.
        "SESSION_HTTPS_ONLY": "true",
        "TRUSTED_HOSTS": "www.slomix.fyi,slomix.fyi,localhost,127.0.0.1",
        "CSRF_ORIGIN_CHECK_ENABLED": "true",
        "CSRF_ALLOWED_ORIGINS": "https://www.slomix.fyi",
    }
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _SUBPROCESS_SCRIPT],
        env=env,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"real-stack security subprocess failed (rc={result.returncode})\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "REAL-STACK-SECURITY-OK" in result.stdout
