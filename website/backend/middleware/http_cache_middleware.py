"""HTTP response cache middleware with ETag and Cache-Control support."""

from __future__ import annotations

import base64
import hashlib
import os
from typing import Callable
from urllib.parse import urlencode

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from website.backend.env_utils import getenv_int
from website.backend.metrics import API_CACHE_HITS, API_CACHE_INVALIDATIONS, API_CACHE_MISSES
from website.backend.services.http_cache_backend import CacheBackend


class HTTPCacheMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, cache_backend: CacheBackend):
        super().__init__(app)
        self.cache_backend = cache_backend
        self.default_ttl = getenv_int("CACHE_DEFAULT_TTL_SECONDS", 120)
        self.live_ttl = getenv_int("CACHE_LIVE_TTL_SECONDS", 15)
        self.leaderboard_ttl = getenv_int("CACHE_LEADERBOARD_TTL_SECONDS", 300)
        self.max_body_bytes = max(0, getenv_int("CACHE_MAX_BODY_BYTES", 2097152))
        self.cacheable_prefixes = (
            "/api/live-status",
            "/api/stats/live-session",
            "/api/monitoring/status",
            "/api/server-activity/history",
            "/api/voice-activity/history",
            "/api/voice-activity/current",
            "/api/stats/overview",
            "/api/stats/leaderboard",
            "/api/stats/quick-leaders",
            "/api/hall-of-fame",
            "/api/stats/trends",
            "/api/proximity/",
            "/api/stats/maps",
            "/api/stats/weapons",
            "/api/stats/matches",
            "/api/sessions",
            "/api/seasons/current",
        )
        invalidate_prefixes_raw = os.getenv(
            "CACHE_INVALIDATE_ON_WRITE_PREFIXES",
            "/api/stats,/api/sessions,/api/proximity,/api/monitoring",
        )
        self.invalidate_on_write_prefixes = tuple(
            prefix.strip() for prefix in invalidate_prefixes_raw.split(",") if prefix.strip()
        )

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        if not path.startswith("/api/"):
            return await call_next(request)

        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            response = await call_next(request)
            if response.status_code < 500 and self._should_invalidate_on_write(path):
                await self.cache_backend.invalidate_all()
                API_CACHE_INVALIDATIONS.inc()
            return response

        if request.method != "GET":
            return await call_next(request)

        if not path.startswith(self.cacheable_prefixes):
            return await call_next(request)

        # Avoid caching user/session-specific data.
        if request.headers.get("authorization") or request.headers.get("cookie"):
            response = await call_next(request)
            response.headers["Cache-Control"] = "private, no-store"
            return response

        ttl = self._ttl_for_path(path)
        if ttl <= 0:
            return await call_next(request)

        cache_key = self._build_cache_key(request)
        namespace = await self.cache_backend.get_namespace()
        cached = await self.cache_backend.get(namespace, cache_key)

        if cached is not None:
            API_CACHE_HITS.inc()
            etag = str(cached.get("etag", ""))
            cache_control = self._cache_control_header(ttl)
            headers = {
                "ETag": etag,
                "Cache-Control": cache_control,
                "X-Cache": "HIT",
            }

            if self._etag_matches(request.headers.get("if-none-match"), etag):
                return Response(status_code=304, headers=headers)

            body = base64.b64decode(cached.get("body_b64", ""))
            content_type = cached.get("content_type") or "application/json"
            return Response(
                content=body,
                status_code=int(cached.get("status_code", 200)),
                media_type=content_type,
                headers=headers,
            )

        API_CACHE_MISSES.inc()
        response = await call_next(request)
        if response.status_code != 200:
            return response

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            return response

        consumed_stream = False
        content_length = self._parse_content_length(response.headers.get("content-length"))
        if self.max_body_bytes > 0 and content_length is not None and content_length > self.max_body_bytes:
            response.headers["Cache-Control"] = self._cache_control_header(ttl)
            response.headers["X-Cache"] = "BYPASS"
            return response

        response_body = self._extract_response_body(response)
        if response_body is None:
            # For unknown-length streamed responses, avoid unbounded buffering.
            if self.max_body_bytes > 0 and content_length is None:
                response.headers["Cache-Control"] = self._cache_control_header(ttl)
                response.headers["X-Cache"] = "BYPASS"
                return response

            response_body = await self._read_streaming_body(response)
            if response_body is None:
                response.headers["Cache-Control"] = self._cache_control_header(ttl)
                response.headers["X-Cache"] = "BYPASS"
                return response
            consumed_stream = True

        if self.max_body_bytes > 0 and len(response_body) > self.max_body_bytes:
            if not consumed_stream:
                response.headers["Cache-Control"] = self._cache_control_header(ttl)
                response.headers["X-Cache"] = "BYPASS"
                return response
            bypass_headers = dict(response.headers)
            bypass_headers.pop("content-length", None)
            bypass_headers["Cache-Control"] = self._cache_control_header(ttl)
            bypass_headers["X-Cache"] = "BYPASS"
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=bypass_headers,
                media_type=content_type.split(";")[0],
                background=response.background,
            )

        etag = self._compute_etag(response_body)
        cache_control = self._cache_control_header(ttl)

        if self._etag_matches(request.headers.get("if-none-match"), etag):
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": cache_control, "X-Cache": "MISS"},
            )

        await self.cache_backend.set(
            namespace,
            cache_key,
            {
                "status_code": response.status_code,
                "content_type": content_type.split(";")[0],
                "body_b64": base64.b64encode(response_body).decode("ascii"),
                "etag": etag,
            },
            ttl=ttl,
        )

        headers = dict(response.headers)
        headers.pop("content-length", None)
        headers["ETag"] = etag
        headers["Cache-Control"] = cache_control
        headers["X-Cache"] = "MISS"

        return Response(
            content=response_body,
            status_code=response.status_code,
            headers=headers,
            media_type=content_type.split(";")[0],
            background=response.background,
        )

    @staticmethod
    def _extract_response_body(response: Response) -> bytes | None:
        body = getattr(response, "body", None)
        if body is None:
            return None
        if isinstance(body, bytes):
            return body
        if isinstance(body, bytearray):
            return bytes(body)
        if isinstance(body, memoryview):
            return body.tobytes()
        return bytes(body)

    @staticmethod
    async def _read_streaming_body(response: Response) -> bytes | None:
        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is None:
            return None

        chunks: list[bytes] = []
        async for chunk in body_iterator:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            elif isinstance(chunk, bytearray):
                chunks.append(bytes(chunk))
            elif isinstance(chunk, memoryview):
                chunks.append(chunk.tobytes())
            elif isinstance(chunk, str):
                chunks.append(chunk.encode("utf-8"))
            else:
                chunks.append(bytes(chunk))
        return b"".join(chunks)

    @staticmethod
    def _parse_content_length(raw_value: str | None) -> int | None:
        if raw_value is None:
            return None
        try:
            parsed = int(raw_value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    def _ttl_for_path(self, path: str) -> int:
        live_prefixes = (
            "/api/live-status",
            "/api/stats/live-session",
            "/api/monitoring/",
            "/api/voice-activity/current",
        )
        leaderboard_prefixes = (
            "/api/stats/leaderboard",
            "/api/stats/quick-leaders",
            "/api/hall-of-fame",
            "/api/stats/overview",
            "/api/proximity/",
        )

        if path.startswith(live_prefixes):
            return self.live_ttl
        if path.startswith(leaderboard_prefixes):
            return self.leaderboard_ttl
        return self.default_ttl

    def _should_invalidate_on_write(self, path: str) -> bool:
        if not self.invalidate_on_write_prefixes:
            return False
        return path.startswith(self.invalidate_on_write_prefixes)

    @staticmethod
    def _cache_control_header(ttl: int) -> str:
        stale = min(max(ttl * 2, ttl), 900)
        return f"public, max-age={ttl}, stale-while-revalidate={stale}"

    @staticmethod
    def _compute_etag(payload: bytes) -> str:
        digest = hashlib.sha256(payload).hexdigest()[:24]
        return f"\"{digest}\""

    @staticmethod
    def _etag_matches(if_none_match: str | None, etag: str) -> bool:
        if not if_none_match:
            return False
        values = [v.strip() for v in if_none_match.split(",")]
        return etag in values or "*" in values

    @staticmethod
    def _build_cache_key(request: Request) -> str:
        query_items = sorted(request.query_params.multi_items())
        query = urlencode(query_items, doseq=True)
        if query:
            return f"{request.url.path}?{query}"
        return request.url.path
