"""Simple in-process rate limiting middleware for API endpoints."""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Callable

logger = logging.getLogger('website.middleware.rate_limit')

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from website.backend.env_utils import getenv_int
from website.backend.metrics import API_RATE_LIMIT_REJECTIONS
from website.backend.security_utils import get_trusted_client_ip, routed_path


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.window_seconds = max(1, getenv_int("RATE_LIMIT_WINDOW_SECONDS", 60))
        self.standard_limit = max(1, getenv_int("RATE_LIMIT_REQUESTS_PER_WINDOW", 180))
        self.heavy_limit = max(1, getenv_int("RATE_LIMIT_HEAVY_REQUESTS_PER_WINDOW", 45))
        # A single proximity page load fans out to ~38 distinct /api/proximity/*
        # GET requests (measured from logs/access.log, 2026-07-19 09:51:19 —
        # see docs/W2_RATE_LIMIT_TUNING_2026-07-29.md). At the old default of
        # 200, one IP could only load the page ~5 times per window before the
        # *last* endpoints dispatched in a batch started 429ing — the "site
        # rate-limits itself" pattern reported in the task backlog. 450
        # supports ~12 full loads/window (2 tabs open + a few reloads/session
        # switches) while still bounding a real burst.
        #
        # NOTE (rebase, #578 onto #579): this branch was written against the
        # old default of 200. Keep 450 — it is measured, and reverting it here
        # would silently reintroduce the self-rate-limiting bug #579 fixed.
        self.proximity_limit = max(1, getenv_int("RATE_LIMIT_PROXIMITY_REQUESTS_PER_WINDOW", 450))
        # /api/client-error is public, unauthenticated, and POST-only: FastAPI
        # validates the request body (and, on a validation error, echoes an
        # oversized field straight back in the 422) BEFORE the route's own
        # @limiter.limit(...) decorator ever runs, so an attacker sending
        # repeated malformed/oversized bodies was never rate-limited at all
        # (Codex P2 review on #578). This bucket sits in ASGI middleware,
        # outside FastAPI's routing/body-parsing entirely, so it applies
        # before a single byte of the body is read.
        self.client_error_limit = max(1, getenv_int("RATE_LIMIT_CLIENT_ERROR_REQUESTS_PER_WINDOW", 20))
        # Default derived from ClientErrorReport's own field limits rather than
        # picked round: those caps are in CHARACTERS (2000 message + 2000 stack
        # + 500 page_url + 300 user_agent + 64 timestamp = 4864), while this
        # check is on BYTES. A schema-valid report can therefore be several
        # times its character count once serialized — 2000 CJK characters in
        # both message and stack already exceeds 10 KiB, and JSON-escaped
        # control characters cost 6 bytes each, putting the true worst case at
        # ~29 KiB. The old 10240 default rejected such reports with 413 before
        # validation ever ran (Codex review on #578). 32 KiB clears the worst
        # case with headroom; the character limits, not this number, are what
        # actually bound the content.
        self.client_error_max_body_bytes = max(
            1024, getenv_int("RATE_LIMIT_CLIENT_ERROR_MAX_BODY_BYTES", 32768)
        )
        # Trusted-proxy resolution deliberately does NOT live here any more:
        # this branch moved it into security_utils.get_trusted_client_ip(),
        # which dispatch() calls, so the middleware no longer keeps its own
        # parsed proxy lists. (Carried in by mistake during the rebase onto
        # main; the class has neither _load_trusted_proxies nor
        # _DEFAULT_TRUSTED_PROXIES.)
        self.client_error_prefixes = ("/api/client-error",)
        self.proximity_prefixes = ("/api/proximity",)
        self.heavy_prefixes = (
            "/api/stats/leaderboard",
            "/api/stats/matches",
            "/api/sessions",
        )
        self.cleanup_interval_seconds = max(
            10, getenv_int("RATE_LIMIT_CLEANUP_INTERVAL_SECONDS", 60)
        )
        self.max_tracked_keys = max(1000, getenv_int("RATE_LIMIT_MAX_TRACKED_KEYS", 50000))
        self._next_cleanup_at = time.time() + self.cleanup_interval_seconds
        self._requests: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # routed_path() reads the raw ASGI scope path — NOT request.url.path,
        # which Starlette rebuilds from the client-controlled Host header and a
        # malformed Host can distort (Codex review on #510). Bucketing/limiting
        # decisions must use the un-distortable path.
        path = routed_path(request)

        # Body cap runs BEFORE the enabled/should_limit early return. It is a
        # payload-validity gate, not a rate limit: with RATE_LIMIT_ENABLED=false
        # this used to return at the check below, leaving the public
        # unauthenticated endpoint parsing arbitrarily large or chunked JSON and
        # recreating exactly the pre-validation DoS this middleware was added to
        # close (Codex review on #578).
        if body_cap_response := self._enforce_client_error_body_cap(request, path):
            return body_cap_response

        if not self.enabled or not self._should_limit(path):
            return await call_next(request)

        now = time.time()
        if now >= self._next_cleanup_at:
            self._cleanup_inactive_buckets(now)
            self._next_cleanup_at = now + self.cleanup_interval_seconds

        client_ip = get_trusted_client_ip(request, trusted_proxies_env_var="RATE_LIMIT_TRUSTED_PROXIES")

        if path.startswith(self.client_error_prefixes):
            bucket = "client_error"
        elif path.startswith(self.proximity_prefixes):
            bucket = "proximity"
        elif path.startswith(self.heavy_prefixes):
            bucket = "heavy"
        else:
            bucket = "standard"
        key = f"{client_ip}:{bucket}"
        limits = {
            "standard": self.standard_limit,
            "heavy": self.heavy_limit,
            "proximity": self.proximity_limit,
            "client_error": self.client_error_limit,
        }
        limit = limits[bucket]

        timeline = self._requests.get(key)
        if timeline is None:
            if len(self._requests) >= self.max_tracked_keys:
                self._cleanup_inactive_buckets(now)
            if len(self._requests) >= self.max_tracked_keys:
                API_RATE_LIMIT_REJECTIONS.inc()
                # SUPPRESSION (py/clear-text-logging-sensitive-data) — false
                # positive. The taint starts at `os.getenv(...)` inside
                # get_trusted_client_ip(), which CodeQL heuristically treats as
                # a secret source. That variable is RATE_LIMIT_TRUSTED_PROXIES,
                # a list of proxy addresses/CIDRs — not a credential — and its
                # value never reaches this log line: every return path of that
                # function yields either request.client.host or an address
                # parsed out of X-Forwarded-For/X-Real-IP. The env value is
                # only ever *compared* against, inside _is_trusted().
                #
                # Logging the client IP on a rate-limit rejection is deliberate
                # and predates this branch (same two logger.warning calls exist
                # on main, unflagged); without it a limiter breach is
                # untraceable. Owner: iamez.
                # codeql[py/clear-text-logging-sensitive-data]
                logger.warning("Rate limiter capacity reached (max_keys=%d, client=%s)",
                               self.max_tracked_keys, client_ip)
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
            # SUPPRESSION (py/clear-text-logging-sensitive-data) — same false
            # positive as the capacity branch above; see the reasoning there.
            # codeql[py/clear-text-logging-sensitive-data]
            logger.warning("Rate limit exceeded: client=%s bucket=%s limit=%d path=%s",
                           client_ip, bucket, limit, path)
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

    def _enforce_client_error_body_cap(self, request: Request, path: str) -> Response | None:
        """413/411/400 for an oversized or unmeasurable /api/client-error body.

        A Content-Length check is the only body-size gate available here: this is
        ASGI middleware, so reading the body to measure it would consume the
        stream before FastAPI can parse it. That means a client using
        `Transfer-Encoding: chunked` (or otherwise omitting Content-Length) would
        skip the cap entirely and get arbitrarily large JSON read and parsed
        downstream. So the header is *required* on this endpoint rather than
        merely checked when present: no length, no request. Legitimate callers
        are unaffected — `fetch()`/`sendBeacon()` with a string or Blob body
        always set Content-Length, and this endpoint has no streaming use case.

        Returns None when the request is acceptable (or isn't a client-error
        POST at all), so the caller can continue.
        """
        if not path.startswith(self.client_error_prefixes) or request.method != "POST":
            return None
        content_length = request.headers.get("content-length")
        if content_length is None:
            return JSONResponse(
                status_code=411,
                content={"detail": "Content-Length required"},
            )
        try:
            declared_length = int(content_length)
        except ValueError:
            # Malformed header — can't be size-checked, so refuse rather than
            # fall through to the handler unbounded.
            return JSONResponse(
                status_code=400,
                content={"detail": "Invalid Content-Length"},
            )
        if declared_length > self.client_error_max_body_bytes:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )
        return None

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
        return path.startswith(("/api/", "/auth/"))
