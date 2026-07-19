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
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_SUBPROCESS_SCRIPT = r"""
import asyncio
import base64
import json
import os

# Neutralize python-dotenv BEFORE anything imports the app: main.py (and any
# transitively imported module) would otherwise merge a developer/CI
# checkout's .env into this minimal environment via load_dotenv's
# add-if-absent, and ANY import-time int()/path parse anywhere in the import
# graph (greatshot.config, diagnostics_router, ...) could crash the
# subprocess before the ordering probes run. Stubbing the loader makes the
# explicit env passed by the test the ONLY configuration source — no more
# per-variable pin whack-a-mole (Codex on #520).
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

import httpx
import itsdangerous

try:
    import prometheus_fastapi_instrumentator  # noqa: F401
    HAS_PROMETHEUS = True
except ImportError:  # minimal local env — CI installs the root pins
    HAS_PROMETHEUS = False

from website.backend.main import PROMETHEUS_ENABLED, app

# The ordering guarantee this test exists for must cover the Prometheus
# instrumentator when available (Codex on #520): its middleware constructs a
# Request and reads request.url, so it is exactly the kind of inner layer the
# outermost host gate protects. With the dependency present (CI), the app MUST
# have been built with it enabled — otherwise the bad-Host probes would pass
# while a gate-outside-Prometheus regression slipped by.
if HAS_PROMETHEUS:
    assert PROMETHEUS_ENABLED, "subprocess env must keep PROMETHEUS_ENABLED=true"

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

        # 2b) With Prometheus available, prove the instrumentator is REALLY in
        # the stack (a live /metrics endpoint) and — via an ordering SIDE
        # EFFECT — that a bad Host never reaches it: a 400 status alone can't
        # distinguish gate-first from instrumentator-first, because the inner
        # gate would still 400 after Prometheus observed the request (Codex on
        # #520). So: count the /health samples Prometheus has recorded, fire
        # bad-Host /health probes, and require the count to be UNCHANGED — the
        # vulnerable ordering would have counted them.
        if HAS_PROMETHEUS:
            def health_samples(metrics_text: str) -> float:
                total = 0.0
                for line in metrics_text.splitlines():
                    if line.startswith("#") or 'handler="/health"' not in line:
                        continue
                    if line.split("{", 1)[0].endswith("_count") or line.split("{", 1)[0].endswith("_total"):
                        total += float(line.rsplit(" ", 1)[1])
                return total

            r = await client.get("/metrics", headers={"host": GOOD_HOST})
            assert r.status_code == 200, f"/metrics must serve with Prometheus on, got {r.status_code}"
            before = health_samples(r.text)
            assert before > 0, "good-Host /health probes must already be counted"

            for _ in range(3):
                r = await client.get("/health", headers={"host": "www.slomix.fyi:443/../admin"})
                assert r.status_code == 400, f"bad Host must 400, got {r.status_code}"

            r = await client.get("/metrics", headers={"host": GOOD_HOST})
            assert r.status_code == 200
            after = health_samples(r.text)
            assert after == before, (
                f"bad-Host requests were OBSERVED by the instrumentator "
                f"({before} -> {after}) — the host gate is no longer outermost"
            )

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
        # main.py calls load_dotenv() at import, and dotenv ADDS any key that
        # is absent from this env — so a developer/CI checkout's .env could
        # still leak config that import or the probes touch (Codex on #520:
        # e.g. CACHE_BACKEND=redis + broad invalidation prefixes would make
        # the POST probe hit an unstarted cache backend, and an exotic
        # WEB_LOG_DIR would crash setup_logging's mkdir before any probe).
        # Pin everything import-time config and the probed request paths can
        # reach; explicit values always win over dotenv's add-if-absent.
        "CACHE_BACKEND": "memory",
        "CACHE_INVALIDATE_ON_WRITE_PREFIXES": "",
        "RATE_LIMIT_ENABLED": "false",
        # Prometheus stays at its production DEFAULT (enabled): the
        # instrumentator middleware reads request.url, so the ordering proof
        # must include it inside the host gate — the subprocess asserts it is
        # really wired and probes /metrics with a bad Host (Codex on #520).
        "PROMETHEUS_ENABLED": "true",
        "WEB_LOG_DIR": tempfile.mkdtemp(prefix="slomix-real-stack-logs-"),
        "LOG_LEVEL": "WARNING",
        # Import-time int()/float() parses in routers (auth OAuth knobs,
        # availability throttle, greatshot timeout): an unparseable value from
        # a checkout .env would crash the import before any probe (Codex on
        # #520) — pin them all to their documented defaults.
        "DISCORD_OAUTH_STATE_TTL_SECONDS": "600",
        "DISCORD_OAUTH_RATE_LIMIT_WINDOW_SECONDS": "60",
        "DISCORD_OAUTH_RATE_LIMIT_MAX_REQUESTS": "40",
        "AVAILABILITY_LINK_TOKEN_MIN_INTERVAL_SECONDS": "30",
        "GREATSHOT_STARTUP_TIMEOUT_SECONDS": "20",
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
