"""
Request Logging Middleware

Logs all HTTP requests/responses with:
- Request ID correlation
- Duration tracking
- Client IP (with proxy awareness)
- Security event detection
- Error tracking
"""

import time
import uuid
import logging
import ipaddress
import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..logging_config import get_access_logger, get_security_logger


access_logger = get_access_logger()
security_logger = get_security_logger()


# Paths that shouldn't be logged in detail (reduce noise)
QUIET_PATHS = {
    "/health",
    "/favicon.ico",
    "/static",
}

# Expected auth failures for background/polling reads should stay informational.
INFO_AUTH_FAILURE_PATHS = {
    "/api/availability/promotions/campaign",
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

        # Start timing
        start_time = time.perf_counter()

        # Check for suspicious activity
        await self._check_security(request, client_ip, request_id)

        # Determine if this is a quiet path
        is_quiet = any(request.url.path.startswith(p) for p in QUIET_PATHS)

        # Log request (unless quiet)
        if not is_quiet:
            access_logger.info(
                f"→ {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "method": request.method,
                    "path": request.url.path,
                    "user_agent": request.headers.get("user-agent", "unknown")[:100],
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
                    and request.url.path in INFO_AUTH_FAILURE_PATHS
                )
                log_func = access_logger.info if status_code < 400 or expected_auth_failure else access_logger.warning

                log_func(
                    f"← {request.method} {request.url.path} → {status_code} ({duration_ms:.1f}ms)",
                    extra={
                        "request_id": request_id,
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )

            # Log errors
            if error:
                logging.getLogger("app").error(
                    f"Request failed: {error}",
                    extra={"request_id": request_id},
                    exc_info=True
                )

            # Security logging for auth paths
            if any(request.url.path.startswith(p) for p in SECURITY_PATHS):
                self._log_security_event(request, status_code, client_ip, request_id)

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
        client_ip: str,
        request_id: str
    ) -> None:
        """Check for suspicious request patterns and log security events."""

        # Check URL path for suspicious patterns
        path = request.url.path.lower()
        query = str(request.url.query).lower() if request.url.query else ""

        for pattern in SUSPICIOUS_PATTERNS:
            if pattern.lower() in path or pattern.lower() in query:
                security_logger.warning(
                    f"🚨 SUSPICIOUS REQUEST DETECTED: pattern='{pattern}'",
                    extra={
                        "request_id": request_id,
                        "client_ip": client_ip,
                        "method": request.method,
                        "path": request.url.path,
                        "query": query[:200],  # Limit logged query length
                        "event_type": "suspicious_request",
                        "pattern": pattern,
                    }
                )
                break

        # Check for auth abuse (many failed attempts would be tracked separately)
        if request.url.path.startswith("/auth/"):
            security_logger.info(
                f"🔐 Auth request: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "client_ip": client_ip,
                    "event_type": "auth_attempt",
                }
            )

    def _log_security_event(
        self,
        request: Request,
        status_code: int,
        client_ip: str,
        request_id: str
    ) -> None:
        """Log security-relevant events."""

        event_type = "auth_success" if status_code < 400 else "auth_failure"
        log_level = logging.INFO if status_code < 400 else logging.WARNING

        security_logger.log(
            log_level,
            f"{'✅' if status_code < 400 else '❌'} Security event: {event_type} on {request.url.path}",
            extra={
                "request_id": request_id,
                "client_ip": client_ip,
                "status_code": status_code,
                "event_type": event_type,
                "path": request.url.path,
            }
        )
