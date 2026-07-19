"""
Request Logging Middleware

Logs all HTTP requests/responses with:
- Request ID correlation
- Duration tracking
- Client IP (with proxy awareness)
- Security event detection
- Error tracking
"""

import ipaddress
import logging
import os
import re
import time
import uuid
from typing import Callable
from urllib.parse import unquote_plus

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from website.backend.logging_config import get_access_logger, get_security_logger
from website.backend.security_utils import routed_path

access_logger = get_access_logger()
security_logger = get_security_logger()


# Paths that shouldn't be logged in detail (reduce noise)
QUIET_PATHS = {
    "/health",
    "/favicon.ico",
    "/static",
    "/js/",
    "/css/",
    "/assets/",
}

# Expected auth failures for background/polling reads should stay informational.
# /auth/me is the canonical "am I logged in?" probe issued on every page
# load — a 401 here is the API contract reply, not a security event.
INFO_AUTH_FAILURE_PATHS = {
    "/api/availability/promotions/campaign",
    "/auth/me",
}

# Paths that should trigger security logging
SECURITY_PATHS = {
    "/auth/",
    "/api/link-player",
    "/api/admin",
}

# Suspicious patterns that warrant security alerts
SUSPICIOUS_PATTERNS = [
    "../",           # Path traversal
    "<script",       # XSS attempt
    "UNION SELECT",  # SQL injection
    "DROP TABLE",    # SQL injection
    "' OR '",        # SQL injection
    "%00",           # Null byte injection
]

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _log_safe(value: str) -> str:
    """Escape control characters for LOG OUTPUT only.

    ASGI decodes percent-encoded bytes into scope["path"], so a request for
    /api/a%0Ab arrives with a literal newline — written raw, it would let a
    good-Host client forge multiline access/security log entries (Codex on
    #520). Decisions keep the raw routed path; only the logged copies are
    escaped (\\n, \\r, \\x00…)."""
    return _CONTROL_CHARS_RE.sub(lambda m: repr(m.group())[1:-1], value)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for comprehensive request/response logging."""

    _DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"

    def __init__(self, app):
        super().__init__(app)
        self._trusted_proxy_networks, self._trusted_proxy_hosts = self._load_trusted_proxies(
            os.getenv("RATE_LIMIT_TRUSTED_PROXIES", self._DEFAULT_TRUSTED_PROXIES)
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Add request ID to request state for downstream access
        request.state.request_id = request_id

        # Get client IP (proxy-aware)
        client_ip = self._get_client_ip(request)

        # Path classifications and logged values read the raw ASGI routed
        # path — never the path off request.url, which Starlette reconstructs
        # with the client-controlled Host header (AUD-005/IMP-006): a crafted
        # Host must not be able to move a request into a QUIET path, out of a
        # SECURITY path, or dodge the suspicious-pattern classifier.
        path = routed_path(request)

        # Start timing
        start_time = time.perf_counter()

        # Check for suspicious activity
        await self._check_security(request, path, client_ip, request_id)

        # Determine if this is a quiet path
        is_quiet = any(path.startswith(p) for p in QUIET_PATHS)

        # Every LOGGED copy of the path goes through _log_safe (decisions
        # above/below keep the raw value).
        safe_path = _log_safe(path)

        # Log request (unless quiet)
        if not is_quiet:
            access_logger.info(
                f"→ {request.method} {safe_path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": safe_path,
                    "user_agent": _log_safe(request.headers.get("user-agent", "unknown")[:100]),
                }
            )

        # Process request
        response = None
        error = None
        try:
            response = await call_next(request)
        except Exception as e:
            error = e
            raise
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Get status code
            status_code = response.status_code if response else 500

            # Add request ID to response headers
            if response:
                response.headers["X-Request-ID"] = request_id

            # Log response (unless quiet and successful)
            if not (is_quiet and status_code < 400):
                expected_auth_failure = (
                    request.method == "GET"
                    and status_code in {401, 403}
                    and path in INFO_AUTH_FAILURE_PATHS
                )
                log_func = access_logger.info if status_code < 400 or expected_auth_failure else access_logger.warning

                log_func(
                    f"← {request.method} {safe_path} → {status_code} ({duration_ms:.1f}ms)",
                    extra={
                        "request_id": request_id,
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": safe_path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )

            # Log errors
            if error:
                logging.getLogger("app").error(
                    f"Request failed: {error}",
                    extra={"request_id": request_id},
                    exc_info=error
                )

            # Security logging for auth paths
            if any(path.startswith(p) for p in SECURITY_PATHS):
                self._log_security_event(request, path, status_code, client_ip, request_id)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract real client IP, accounting for trusted reverse proxies only.
        """
        direct_client = request.client.host if request.client else "unknown"
        if not self._is_trusted_proxy(direct_client):
            return direct_client

        if forwarded := request.headers.get("x-forwarded-for"):
            for candidate in forwarded.split(","):
                normalized = self._normalize_forwarded_ip(candidate)
                if normalized:
                    return normalized

        if real_ip := request.headers.get("x-real-ip"):
            normalized = self._normalize_forwarded_ip(real_ip)
            if normalized:
                return normalized

        return direct_client

    @staticmethod
    def _load_trusted_proxies(
        raw_value: str,
    ) -> tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...], tuple[str, ...]]:
        networks = []
        hosts = []
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
                hosts.append(entry.lower())
        return tuple(networks), tuple(hosts)

    @staticmethod
    def _normalize_forwarded_ip(raw_value: str | None) -> str:
        if not raw_value:
            return ""
        value = raw_value.strip().strip("\"")
        if not value or value.lower() == "unknown":
            return ""
        if value.startswith("[") and "]" in value:
            return value[1 : value.index("]")]
        if value.count(":") == 1:
            host, port = value.rsplit(":", 1)
            if host and port.isdigit():
                return host
        return value

    def _is_trusted_proxy(self, client_host: str) -> bool:
        if not client_host:
            return False
        if client_host.lower() in self._trusted_proxy_hosts:
            return True
        try:
            client_ip = ipaddress.ip_address(client_host)
        except ValueError:
            return False
        return any(client_ip in network for network in self._trusted_proxy_networks)

    async def _check_security(
        self,
        request: Request,
        path: str,
        client_ip: str,
        request_id: str
    ) -> None:
        """Check for suspicious request patterns and log security events.

        Both `path` and the query come from the raw ASGI scope — request.url
        is reconstructed with the client-controlled Host header, and a
        crafted Host (e.g. one carrying a '#fragment') can make
        request.url.query come back EMPTY, letting a suspicious query dodge
        this scan entirely in postures without the strict host gate
        (Codex on #520).
        """
        lowered_path = path.lower()
        query = request.scope.get("query_string", b"").decode("latin-1", "replace").lower()
        # Scan BOTH forms: the raw query catches literal patterns (%00), the
        # unquoted one catches percent-encoded evasion (DROP%20TABLE).
        query_decoded = unquote_plus(query)

        for pattern in SUSPICIOUS_PATTERNS:
            lowered = pattern.lower()
            if lowered in lowered_path or lowered in query or lowered in query_decoded:
                security_logger.warning(
                    f"🚨 SUSPICIOUS REQUEST DETECTED: pattern='{pattern}'",
                    extra={
                        "request_id": request_id,
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": _log_safe(path),
                        "query": _log_safe(query[:200]),  # Limit logged query length
                        "event_type": "suspicious_request",
                        "pattern": pattern,
                    }
                )
                break

        # Check for auth abuse (many failed attempts would be tracked separately)
        if path.startswith("/auth/"):
            security_logger.info(
                f"🔐 Auth request: {request.method} {_log_safe(path)}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "event_type": "auth_attempt",
                }
            )

    def _log_security_event(
        self,
        request: Request,
        path: str,
        status_code: int,
        client_ip: str,
        request_id: str
    ) -> None:
        """Log security-relevant events. `path` is the routed ASGI path."""

        event_type = "auth_success" if status_code < 400 else "auth_failure"
        # Downgrade benign auth probes (e.g. /auth/me 401 on every page
        # load before the user signs in) so the security log isn't drowned
        # in normal traffic. Same allow-list used for access-log downgrade,
        # and we mirror its `request.method == "GET"` guard — only read
        # probes are benign; a POST/PUT to /auth/me is suspicious enough
        # that it should still surface as WARNING.
        is_expected_probe = (
            request.method == "GET"
            and status_code in {401, 403}
            and path in INFO_AUTH_FAILURE_PATHS
        )
        log_level = logging.INFO if status_code < 400 or is_expected_probe else logging.WARNING

        security_logger.log(
            log_level,
            f"{'✅' if status_code < 400 else '❌'} Security event: {event_type} on {_log_safe(path)}",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "status_code": status_code,
                "event_type": event_type,
                "path": _log_safe(path),
            }
        )
