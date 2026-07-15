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
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


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
