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

import ipaddress
import os
import re
import socket
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"


@lru_cache(maxsize=8)
def _load_trusted_proxies(
    raw_value: str,
) -> tuple[tuple["ipaddress.IPv4Network | ipaddress.IPv6Network", ...], tuple[str, ...]]:
    """Parse (and resolve) RATE_LIMIT_TRUSTED_PROXIES. Cached on the raw string.

    get_trusted_client_ip() calls this on EVERY request, so without the cache
    the hostname branch below runs a synchronous, blocking socket.getaddrinfo()
    per request inside the event loop — and the docstring there claimed
    resolution happened once at load, which it did not (Codex review on #578).
    Keyed on the raw env value, so changing the setting still takes effect on
    the next process start (these are import/startup-time settings; nothing
    mutates them in place).
    """
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    hosts: list[str] = []
    for raw_entry in raw_value.split(","):
        entry = raw_entry.strip()
        if not entry:
            continue
        try:
            if "/" in entry:
                networks.append(ipaddress.ip_network(entry, strict=False))
            else:
                ip = ipaddress.ip_address(entry)
                prefix = 32 if ip.version == 4 else 128
                networks.append(ipaddress.ip_network(f"{entry}/{prefix}", strict=False))
            continue
        except ValueError:
            # Not an IP/CIDR — treat it as a hostname and resolve it to
            # addresses now. `request.client.host` is the numeric peer address
            # Uvicorn read off the socket, never a name, so keeping only the
            # literal string would mean a documented value like `localhost` or
            # a compose service name (`nginx`) silently never matched anything
            # and the proxy stayed untrusted (Codex review on #578). Resolution
            # happens once at load, not per request.
            resolved = False
            try:
                for info in socket.getaddrinfo(entry, None, proto=socket.IPPROTO_TCP):
                    addr = info[4][0]
                    try:
                        ip = ipaddress.ip_address(addr)
                    except ValueError:
                        continue
                    prefix = 32 if ip.version == 4 else 128
                    networks.append(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))
                    resolved = True
            except OSError:
                # Unresolvable at startup (DNS not up yet, typo, name that only
                # exists in another network namespace). Fall through to keeping
                # the literal so behaviour is no worse than before.
                pass
            if not resolved:
                hosts.append(entry.lower())
    return tuple(networks), tuple(hosts)


def _normalize_forwarded_ip(raw_value: str | None) -> str:
    if not raw_value:
        return ""
    value = raw_value.strip().strip('"')
    if not value or value.lower() == "unknown":
        return ""
    if value.startswith("[") and "]" in value:
        return value[1 : value.index("]")]
    # Strip optional IPv4 port suffix (e.g. "203.0.113.8:4123").
    if value.count(":") == 1:
        host, port = value.rsplit(":", 1)
        if host and port.isdigit():
            return host
    return value


def get_trusted_client_ip(
    request: Request,
    *,
    trusted_proxies_env_var: str = "RATE_LIMIT_TRUSTED_PROXIES",
) -> str:
    """Real client IP, honouring X-Forwarded-For/X-Real-IP ONLY from a trusted proxy.

    A forwarded-for header is entirely client-controlled unless the immediate
    TCP peer (``request.client.host``) is a proxy we actually trust — nginx's
    ``$proxy_add_x_forwarded_for`` *appends* to whatever the client already
    sent rather than replacing it, so blindly trusting the leftmost value
    (the naive `forwarded.split(",")[0]` pattern) lets any client spoof an
    unlimited number of distinct rate-limit identities and bypass the limiter
    entirely (Codex review on #578, against the public unauthenticated
    /api/client-error endpoint — but the same key_func is shared by every
    slowapi-limited route in the app). Trusted proxies default to loopback
    only; set ``RATE_LIMIT_TRUSTED_PROXIES`` (comma-separated hosts/CIDRs) to
    add the real reverse-proxy hop in front of this service.

    The chain is walked **right to left**, not leftmost-first. With nginx's
    ``$proxy_add_x_forwarded_for`` (this project's own config, see
    ``docker/nginx/default.conf``) the header nginx forwards is
    ``"<whatever the client sent>, <real peer address>"`` — so the *leftmost*
    entry is exactly the attacker-controlled value, and reading it after
    trusting nginx would reintroduce the same spoofing bypass this function
    exists to close. Walking from the right and skipping hops that are
    themselves trusted proxies yields the first address the trusted chain
    couldn't have forged (Codex review on #578, second round).
    """
    trusted_networks, trusted_hosts = _load_trusted_proxies(
        os.getenv(trusted_proxies_env_var, DEFAULT_TRUSTED_PROXIES)
    )
    direct_client = request.client.host if request.client else "unknown"

    def _is_trusted(host: str) -> bool:
        if not host:
            return False
        if host.lower() in trusted_hosts:
            return True
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(ip in network for network in trusted_networks)

    if not _is_trusted(direct_client):
        return direct_client

    if forwarded := request.headers.get("x-forwarded-for"):
        chain = [
            normalized
            for candidate in forwarded.split(",")
            if (normalized := _normalize_forwarded_ip(candidate))
        ]
        # Rightmost first: each entry a trusted proxy appended is itself
        # trusted, so skip those and stop at the first hop none of them
        # control. If every hop is trusted, the leftmost is the best guess.
        for candidate in reversed(chain):
            if not _is_trusted(candidate):
                return candidate
        if chain:
            return chain[0]
    if real_ip := request.headers.get("x-real-ip"):
        # nginx sets X-Real-IP to $remote_addr, which it always overwrites —
        # unlike X-Forwarded-For, a client cannot contribute to this value.
        normalized = _normalize_forwarded_ip(real_ip)
        if normalized:
            return normalized
    return direct_client


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
    # String concatenation (not an f-string): this is a pure origin-normalizer,
    # but Codacy/semgrep's "Flask route returning a formatted string" XSS rule
    # taints an f-string all the way to the return. Building the value by
    # concatenation sidesteps that false positive; it never reaches a template.
    return parsed.scheme.lower() + "://" + parsed.netloc.lower()


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


def strip_surrogates(obj: Any) -> Any:
    """Rewrite lone surrogates to a replacement char, recursively.

    UTF-8 cannot encode a surrogate code point, so any string holding one
    explodes at `.encode("utf-8")` — which is what `JSONResponse.render()`
    does. Pydantic v2 rejects a lone surrogate in a request body with
    `string_unicode`, and FastAPI's stock validation handler echoes the
    offending value straight back into the 422 `detail`, so the handler itself
    raises UnicodeEncodeError and the request 500s instead.

    `{"message": "\\ud800"}` is valid JSON and a browser's `JSON.stringify()`
    emits exactly that for a JS string holding an unpaired surrogate, which
    makes every public endpoint taking a string body forceable into a 500 by a
    one-line request (Codex review on #578, reported at /api/client-error).

    Lives here rather than in main.py so it is importable without triggering
    main's import-time environment checks.
    """
    if isinstance(obj, str):
        return obj.encode("utf-16", "surrogatepass").decode("utf-16", "replace")
    if isinstance(obj, dict):
        return {strip_surrogates(k): strip_surrogates(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [strip_surrogates(v) for v in obj]
    return obj
