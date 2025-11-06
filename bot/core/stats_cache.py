#!/usr/bin/env python3
"""
StatsCache - High-performance caching system for database queries

Features:
- TTL-based expiration (default 5 minutes)
- Automatic cache invalidation
- Memory-efficient storage
- Reduces repeated queries by 80% during active sessions

This was extracted from ultimate_bot.py during the modular refactoring.
Original location: Line 121-190 of ultimate_bot.py
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("UltimateBot.StatsCache")


class StatsCache:
    """
    High-performance caching system for database queries.
    Reduces repeated queries by 80% during active sessions.

    Features:
    - TTL-based expiration (default 5 minutes)
    - Automatic cache invalidation
    - Memory-efficient storage

    Usage:
        cache = StatsCache(ttl_seconds=300)
        cached = cache.get("stats_player123")
        if not cached:
            cached = await fetch_from_db()
            cache.set("stats_player123", cached)
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize the cache with a time-to-live.

        Args:
            ttl_seconds: How long cached values remain valid (default: 300 seconds = 5 minutes)
        """
        self.cache: Dict[str, Any] = {}
        self.timestamps: Dict[str, datetime] = {}
        self.ttl: int = ttl_seconds
        logger.info(f"📦 StatsCache initialized (TTL: {ttl_seconds}s)")

    def get(self, key: str) -> Optional[Any]:
        """
        Get cached value if still valid, None otherwise.

        Args:
            key: Cache key to retrieve

        Returns:
            Cached value if valid, None if expired or not found
        """
        if key in self.cache:
            age = (datetime.now() - self.timestamps[key]).total_seconds()
            if age < self.ttl:
                logger.debug(f"✅ Cache HIT: {key} (age: {age:.1f}s)")
                return self.cache[key]
            else:
                logger.debug(f"⏰ Cache EXPIRED: {key} (age: {age:.1f}s)")
                del self.cache[key]
                del self.timestamps[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self.cache[key] = value
        self.timestamps[key] = datetime.now()
        logger.debug(f"💾 Cache SET: {key} (total keys: {len(self.cache)})")

    def clear(self) -> None:
        """Clear all cached data."""
        count = len(self.cache)
        self.cache.clear()
        self.timestamps.clear()
        logger.info(f"🗑️  Cache CLEARED: {count} keys removed")

    def stats(self) -> Dict[str, int]:
        """
        Get cache statistics.

        Returns:
            Dictionary with total_keys, valid_keys, expired_keys, ttl_seconds
        """
        total = len(self.cache)
        expired = sum(
            1
            for k in self.cache
            if (datetime.now() - self.timestamps[k]).total_seconds() >= self.ttl
        )
        return {
            "total_keys": total,
            "valid_keys": total - expired,
            "expired_keys": expired,
            "ttl_seconds": self.ttl,
        }

    def __len__(self) -> int:
        """Return number of items in cache."""
        return len(self.cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists and is valid in cache."""
        return self.get(key) is not None
