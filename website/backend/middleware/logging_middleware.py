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
                log_func = access_logger.info if status_code < 400 else access_logger.warning

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
        Extract real client IP, accounting for reverse proxies.

        Checks headers in order of trust:
        1. X-Real-IP (nginx)
        2. X-Forwarded-For (first IP)
        3. Direct client IP
        """
        # X-Real-IP (most reliable when set by trusted proxy)
        if x_real_ip := request.headers.get("x-real-ip"):
            return x_real_ip.strip()

        # X-Forwarded-For (may contain chain: client, proxy1, proxy2)
        if x_forwarded_for := request.headers.get("x-forwarded-for"):
            # First IP in chain is the original client
            return x_forwarded_for.split(",")[0].strip()

        # Fall back to direct client
        return request.client.host if request.client else "unknown"

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
