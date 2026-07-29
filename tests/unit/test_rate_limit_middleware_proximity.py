"""Regression test for W2 (docs/W2_RATE_LIMIT_TUNING_2026-07-29.md).

A single proximity page load fans out to ~38 distinct /api/proximity/*
GET requests sharing one "proximity" bucket per IP. The default budget
must stay comfortably above one page load, or the site rate-limits
itself under normal use (2 tabs, a couple of reloads).
"""

from website.backend.middleware.rate_limit_middleware import RateLimitMiddleware

MEASURED_CALLS_PER_PAGE_LOAD = 38


def test_default_proximity_limit_covers_several_page_loads(monkeypatch):
    for var in (
        "RATE_LIMIT_PROXIMITY_REQUESTS_PER_WINDOW",
        "RATE_LIMIT_REQUESTS_PER_WINDOW",
        "RATE_LIMIT_HEAVY_REQUESTS_PER_WINDOW",
    ):
        monkeypatch.delenv(var, raising=False)

    middleware = RateLimitMiddleware(app=None)

    assert middleware.proximity_limit >= MEASURED_CALLS_PER_PAGE_LOAD * 10, (
        "proximity_limit should comfortably cover 10+ full page loads per "
        "window per IP, not just 1-2 — see W2 for the incident this guards"
    )


def test_proximity_limit_env_override_still_works(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PROXIMITY_REQUESTS_PER_WINDOW", "999")
    middleware = RateLimitMiddleware(app=None)
    assert middleware.proximity_limit == 999
