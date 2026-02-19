"""Simple in-process rate limiting middleware for API endpoints."""

from __future__ import annotations

import ipaddress
import os
import time
from collections import deque
from typing import Callable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from website.backend.env_utils import getenv_int
from website.backend.metrics import API_RATE_LIMIT_REJECTIONS


class RateLimitMiddleware(BaseHTTPMiddleware):
    _DEFAULT_TRUSTED_PROXIES = "127.0.0.1,::1"

    def __init__(self, app):
        super().__init__(app)
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.window_seconds = max(1, getenv_int("RATE_LIMIT_WINDOW_SECONDS", 60))
        self.standard_limit = max(1, getenv_int("RATE_LIMIT_REQUESTS_PER_WINDOW", 180))
        self.heavy_limit = max(1, getenv_int("RATE_LIMIT_HEAVY_REQUESTS_PER_WINDOW", 45))
        self._trusted_proxy_networks, self._trusted_proxy_hosts = self._load_trusted_proxies(
            os.getenv("RATE_LIMIT_TRUSTED_PROXIES", self._DEFAULT_TRUSTED_PROXIES)
        )
        self.heavy_prefixes = (
            "/api/stats/leaderboard",
            "/api/stats/matches",
            "/api/sessions",
            "/api/proximity",
        )
        self.cleanup_interval_seconds = max(
            10, getenv_int("RATE_LIMIT_CLEANUP_INTERVAL_SECONDS", 60)
        )
        self.max_tracked_keys = max(1000, getenv_int("RATE_LIMIT_MAX_TRACKED_KEYS", 50000))
        self._next_cleanup_at = time.time() + self.cleanup_interval_seconds
        self._requests: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.enabled or not self._should_limit(request.url.path):
            return await call_next(request)

        now = time.time()
        if now >= self._next_cleanup_at:
            self._cleanup_inactive_buckets(now)
            self._next_cleanup_at = now + self.cleanup_interval_seconds

        client_ip = self._get_client_ip(request)
        bucket = "heavy" if request.url.path.startswith(self.heavy_prefixes) else "standard"
        key = f"{client_ip}:{bucket}"
        limit = self.heavy_limit if bucket == "heavy" else self.standard_limit

        timeline = self._requests.get(key)
        if timeline is None:
            if len(self._requests) >= self.max_tracked_keys:
                self._cleanup_inactive_buckets(now)
            if len(self._requests) >= self.max_tracked_keys:
                API_RATE_LIMIT_REJECTIONS.inc()
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": "Rate limiter capacity reached",
                        "retry_after_seconds": self.window_seconds,
                    },
                    headers={"Retry-After": str(self.window_seconds)},
                )
            timeline = deque()
            self._requests[key] = timeline
        cutoff = now - self.window_seconds
        while timeline and timeline[0] <= cutoff:
            timeline.popleft()

        if len(timeline) >= limit:
            retry_after = max(1, int(timeline[0] + self.window_seconds - now))
            API_RATE_LIMIT_REJECTIONS.inc()
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "bucket": bucket,
                    "limit": limit,
                    "window_seconds": self.window_seconds,
                    "retry_after_seconds": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(now + retry_after)),
                },
            )

        timeline.append(now)
        response = await call_next(request)
        remaining = max(0, limit - len(timeline))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window_seconds))
        return response

    def _cleanup_inactive_buckets(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale_keys = []
        for key, timeline in self._requests.items():
            while timeline and timeline[0] <= cutoff:
                timeline.popleft()
            if not timeline:
                stale_keys.append(key)
        for key in stale_keys:
            self._requests.pop(key, None)

    @staticmethod
    def _should_limit(path: str) -> bool:
        return path.startswith("/api/") or path.startswith("/auth/")

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
        # Strip optional IPv4 port suffix (e.g. "203.0.113.8:4123").
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

    def _get_client_ip(self, request: Request) -> str:
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
