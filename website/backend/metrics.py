"""Prometheus metric helpers for middleware instrumentation."""

try:
    from prometheus_client import Counter
except ImportError:  # pragma: no cover - optional dependency fallback
    class _NoopCounter:
        def __init__(self, *args, **kwargs):
            pass

        def inc(self, amount: float = 1.0) -> None:
            return None

    Counter = _NoopCounter


API_CACHE_HITS = Counter(
    "slomix_api_cache_hits_total",
    "Total number of API cache hits",
)

API_CACHE_MISSES = Counter(
    "slomix_api_cache_misses_total",
    "Total number of API cache misses",
)

API_CACHE_INVALIDATIONS = Counter(
    "slomix_api_cache_invalidations_total",
    "Total number of cache namespace invalidations",
)

API_RATE_LIMIT_REJECTIONS = Counter(
    "slomix_api_rate_limit_rejections_total",
    "Total number of API requests rejected by rate limiting",
)
