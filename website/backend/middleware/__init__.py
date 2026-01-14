"""Middleware package for the Slomix website backend."""

from .logging_middleware import RequestLoggingMiddleware

__all__ = ["RequestLoggingMiddleware"]
