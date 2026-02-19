"""Cache backends used by API middleware."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Optional, Protocol

from website.backend.logging_config import get_app_logger

logger = get_app_logger("cache")

try:
    from redis.asyncio import Redis
except ImportError:  # pragma: no cover - optional dependency fallback
    Redis = None


class CacheBackend(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def get_namespace(self) -> str: ...
    async def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]: ...
    async def set(self, namespace: str, key: str, value: dict[str, Any], ttl: int) -> None: ...
    async def invalidate_all(self) -> None: ...


class MemoryCacheBackend:
    def __init__(self) -> None:
        self._namespace = "1"
        self._entries: dict[str, tuple[float, str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        async with self._lock:
            self._entries.clear()

    async def get_namespace(self) -> str:
        return self._namespace

    async def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        now = time.time()
        full_key = f"{namespace}:{key}"
        async with self._lock:
            entry = self._entries.get(full_key)
            if not entry:
                return None
            expires_at, payload = entry
            if expires_at <= now:
                self._entries.pop(full_key, None)
                return None
        return json.loads(payload)

    async def set(self, namespace: str, key: str, value: dict[str, Any], ttl: int) -> None:
        full_key = f"{namespace}:{key}"
        expires_at = time.time() + ttl
        payload = json.dumps(value)
        async with self._lock:
            self._entries[full_key] = (expires_at, payload)

    async def invalidate_all(self) -> None:
        async with self._lock:
            self._namespace = str(int(self._namespace) + 1)
            self._entries.clear()


class RedisCacheBackend:
    def __init__(self, redis_url: str, namespace_key: str = "slomix:api_cache:namespace") -> None:
        self.redis_url = redis_url
        self.namespace_key = namespace_key
        self._client: Optional[Redis] = None

    async def connect(self) -> None:
        if Redis is None:
            raise RuntimeError("redis package is not installed")
        self._client = Redis.from_url(self.redis_url, decode_responses=True)
        await self._client.ping()
        await self._client.setnx(self.namespace_key, "1")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_namespace(self) -> str:
        client = self._require_client()
        namespace = await client.get(self.namespace_key)
        if namespace is None:
            await client.set(self.namespace_key, "1")
            return "1"
        return namespace

    async def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        client = self._require_client()
        payload = await client.get(self._cache_key(namespace, key))
        if payload is None:
            return None
        return json.loads(payload)

    async def set(self, namespace: str, key: str, value: dict[str, Any], ttl: int) -> None:
        client = self._require_client()
        payload = json.dumps(value)
        await client.set(self._cache_key(namespace, key), payload, ex=max(1, ttl))

    async def invalidate_all(self) -> None:
        client = self._require_client()
        await client.incr(self.namespace_key)

    @staticmethod
    def _cache_key(namespace: str, key: str) -> str:
        return f"slomix:api_cache:{namespace}:{key}"

    def _require_client(self) -> Redis:
        if self._client is None:
            raise RuntimeError("Redis cache backend is not connected")
        return self._client


class ResilientCacheBackend:
    """Wrapper that falls back to memory cache if Redis is unavailable."""

    def __init__(self, primary: CacheBackend, fallback: CacheBackend) -> None:
        self.primary = primary
        self.fallback = fallback
        self.active: CacheBackend = primary

    async def connect(self) -> None:
        try:
            await self.primary.connect()
            self.active = self.primary
        except Exception as error:  # pragma: no cover - startup environment dependent
            logger.warning("Primary cache backend unavailable, using memory fallback: %s", error)
            await self.fallback.connect()
            self.active = self.fallback

    async def close(self) -> None:
        await self.active.close()

    async def get_namespace(self) -> str:
        return await self.active.get_namespace()

    async def get(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        return await self.active.get(namespace, key)

    async def set(self, namespace: str, key: str, value: dict[str, Any], ttl: int) -> None:
        await self.active.set(namespace, key, value, ttl)

    async def invalidate_all(self) -> None:
        await self.active.invalidate_all()


def create_cache_backend_from_env() -> CacheBackend:
    backend = os.getenv("CACHE_BACKEND", "memory").strip().lower()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    if backend == "redis":
        return ResilientCacheBackend(
            primary=RedisCacheBackend(redis_url=redis_url),
            fallback=MemoryCacheBackend(),
        )

    return MemoryCacheBackend()
