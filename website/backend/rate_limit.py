try:
    from slowapi import Limiter

    from website.backend.security_utils import get_trusted_client_ip

    limiter = Limiter(key_func=get_trusted_client_ip)
except ImportError:
    # slowapi not installed (CI/test environments) — provide no-op stub
    class _NoOpLimiter:
        def limit(self, *args, **kwargs):
            def decorator(func):
                return func
            return decorator
    limiter = _NoOpLimiter()
