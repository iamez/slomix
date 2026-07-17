"""Request-security primitives shared by main.py and its tests.

Kept import-light (starlette + stdlib only) so security tests can exercise
CSRF / trusted-host behavior without booting the full application.

AUD-005 context: the pinned Starlette line has a published advisory where a
malformed Host header can distort `request.url`-derived values. Two defenses
live here:

1. `routed_path()` — security decisions read the raw ASGI routed path
   (`request.scope["path"]`), which the Host header cannot influence, instead
   of `request.url.path`.
2. `resolve_trusted_hosts()` — configuration for an outermost
   TrustedHostMiddleware that rejects unexpected/malformed Host values with
   400 before any application middleware runs. Deployments with the
   production posture (SESSION_HTTPS_ONLY=true) must configure
   TRUSTED_HOSTS explicitly or the app refuses to start.
"""

import os
import re
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


def routed_path(request: Request) -> str:
    """The raw ASGI path the router will dispatch on.

    Use this — never `request.url.path` — for security decisions:
    `request.url` is reconstructed with the client-controlled Host header.
    """
    return str(request.scope.get("path") or "")


def normalize_origin(origin: str | None) -> str | None:
    if not origin:
        return None
    parsed = urlsplit(origin.strip())
    if not parsed.scheme or not parsed.netloc:
        return None
    # Assign-then-return (not a bare `return f"..."`): this is a pure helper,
    # but Codacy/semgrep's "Flask route returning a formatted string" XSS rule
    # heuristically flags direct f-string returns. It never reaches a template.
    normalized = f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    return normalized


def parse_origin_list(raw_value: str) -> list[str]:
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def csrf_allowed_origins(cors_origins: list[str]) -> set[str]:
    configured = parse_origin_list(os.getenv("CSRF_ALLOWED_ORIGINS", ""))
    if not configured:
        configured = [*cors_origins]
        frontend_origin = os.getenv("FRONTEND_ORIGIN")
        public_origin = os.getenv("PUBLIC_FRONTEND_ORIGIN")
        if frontend_origin:
            configured.append(frontend_origin)
        if public_origin:
            configured.append(public_origin)
    return {
        normalized
        for normalized in (normalize_origin(origin) for origin in configured)
        if normalized
    }


class CSRFMiddleware(BaseHTTPMiddleware):
    """Origin-check guard for session-authenticated mutating requests."""

    _MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        allowed_origins: set[str],
    ):
        super().__init__(app)
        self.enabled = enabled
        self.allowed_origins = allowed_origins

    async def dispatch(self, request: Request, call_next):
        if not self.enabled or request.method.upper() not in self._MUTATING_METHODS:
            return await call_next(request)
        path = routed_path(request)
        if not path.startswith(("/api/", "/auth/")):
            return await call_next(request)
        if not request.session.get("user"):
            return await call_next(request)

        allowed_origins = self.allowed_origins
        if not allowed_origins:
            inferred_origin = normalize_origin(str(request.base_url))
            if inferred_origin:
                allowed_origins = {inferred_origin}

        request_origin = normalize_origin(request.headers.get("origin"))
        if not request_origin:
            request_origin = normalize_origin(request.headers.get("referer"))
        if request_origin and request_origin in allowed_origins:
            return await call_next(request)

        return JSONResponse(status_code=403, content={"detail": "CSRF origin check failed"})


# Strict Host syntax: a DNS name or a bracketed IPv6 literal, plus an optional
# numeric port — and NOTHING else. Starlette rebuilds request.url from the Host
# header, so a value carrying an embedded path ("good.example:443/../admin")
# would distort request.url.path for any inner code. This regex refuses it.
_HOST_SYNTAX_RE = re.compile(
    r"^(?:"
    r"(?P<host>[A-Za-z0-9](?:[A-Za-z0-9\-.]*[A-Za-z0-9])?)"  # DNS name
    r"|\[(?P<ip6>[0-9A-Fa-f:]+)\]"                            # [IPv6]
    r")(?::(?P<port>\d{1,5}))?$"
)


def host_is_allowed(host_header: str, allowed_hosts: list[str]) -> bool:
    """True if `host_header` is syntactically valid AND on the allow-list.

    Strict where Starlette's TrustedHostMiddleware is lax: Starlette compares
    only ``host.split(':')[0]``, so ``good.example:443/../admin`` passes when
    ``good.example`` is trusted and then distorts ``request.url.path`` for the
    inner middleware (Codex review on #510). Here the whole Host must parse as
    ``hostname[:port]`` before the hostname is matched (exact, or a ``*.suffix``
    wildcard as in Starlette).
    """
    lowered = [h.lower() for h in allowed_hosts]
    if "*" in lowered:
        return True
    if not host_header:
        return False
    m = _HOST_SYNTAX_RE.match(host_header.strip())
    if not m:
        return False
    hostname = (m.group("host") or m.group("ip6") or "").lower()
    if not hostname:
        return False
    for pattern in lowered:
        if pattern == hostname:
            return True
        if pattern.startswith("*.") and hostname.endswith(pattern[1:]):
            return True
    return False


class StrictTrustedHostMiddleware:
    """Outermost ASGI gate returning 400 on a malformed or untrusted Host.

    Must sit ABOVE any code that reads ``request.url`` (Starlette reconstructs
    request.url from the Host header). Registered after Prometheus
    instrumentation in main.py so an added instrumentator middleware can't slip
    outside it and read a distorted request.url first (Codex review on #510).
    Implemented as pure ASGI (not BaseHTTPMiddleware) to keep the outermost
    layer cheap.
    """

    def __init__(self, app, allowed_hosts: list[str]):
        self.app = app
        self.allowed_hosts = [h.lower() for h in allowed_hosts]
        self.allow_any = "*" in self.allowed_hosts

    async def __call__(self, scope, receive, send):
        if self.allow_any or scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        host_header = ""
        for key, value in scope.get("headers", []):
            if key == b"host":
                host_header = value.decode("latin-1")
                break
        if host_is_allowed(host_header, self.allowed_hosts):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        response = JSONResponse(status_code=400, content={"detail": "Invalid host header"})
        await response(scope, receive, send)


def resolve_trusted_hosts(*, https_only: bool) -> list[str]:
    """Allowed Host values for the outermost TrustedHostMiddleware.

    TRUSTED_HOSTS is a comma-separated list of hostnames (Starlette compares
    the Host header's hostname part, so ports need not be listed; `*.domain`
    wildcards are supported).

    Fail-fast rule: SESSION_HTTPS_ONLY=true is this app's production posture
    (dev opts out for local HTTP). Running that posture without an explicit
    trusted-host list would silently accept any Host value, so it is a
    startup error rather than a warning nobody reads.
    """
    raw = os.getenv("TRUSTED_HOSTS", "").strip()
    if raw:
        hosts = [h.strip().lower() for h in raw.split(",") if h.strip()]
        if hosts:
            return hosts
    if https_only:
        raise ValueError(
            "TRUSTED_HOSTS must be set when SESSION_HTTPS_ONLY=true (production posture). "
            "Example: TRUSTED_HOSTS=www.slomix.fyi,slomix.fyi,localhost,127.0.0.1"
        )
    return ["*"]
