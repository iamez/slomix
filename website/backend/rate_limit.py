try:
    from slowapi import Limiter
    from starlette.requests import Request

    def _get_real_ip(request: Request) -> str:
        """Return the real client IP, honouring X-Forwarded-For set by nginx."""
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    limiter = Limiter(key_func=_get_real_ip)
except ImportError:
    # slowapi not installed (CI/test environments) — provide no-op stub
    class _NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = _NoOpLimiter()
