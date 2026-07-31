import logging

import httpx
import pytest
from fastapi import FastAPI

from website.backend.routers import client_error_router


@pytest.mark.asyncio
async def test_valid_report_returns_204_and_logs_to_client_error_logger(caplog):
    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with caplog.at_level(logging.WARNING, logger="client_error"):
            response = await client.post(
                "/api/client-error",
                json={
                    "message": "TypeError: x is not a function",
                    "stack": "at foo (bar.js:1:1)",
                    "page_url": "https://slomix.fyi/#/proximity",
                    "user_agent": "test-agent",
                    "timestamp": "2026-07-29T18:00:00Z",
                },
            )

    assert response.status_code == 204
    assert response.text == ""
    assert any("TypeError: x is not a function" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_oversized_message_is_rejected():
    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/api/client-error",
            json={"message": "x" * 5000},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_message_is_rejected():
    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post("/api/client-error", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_newlines_and_control_chars_cannot_forge_log_entries(caplog):
    """Codex P2 review on #578: an unescaped \\n in an attacker-controlled
    field let a caller forge what looks like a second log entry, and raw
    control/escape sequences could corrupt a terminal that later tails the
    file."""
    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")

    forged = "real message\n2026-07-29 00:00:00 | CRITICAL | forged | fake entry\x1b[31mred"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with caplog.at_level(logging.WARNING, logger="client_error"):
            response = await client.post("/api/client-error", json={"message": forged})

    assert response.status_code == 204
    logged = "\n".join(record.message for record in caplog.records)
    assert "\n2026-07-29 00:00:00 | CRITICAL" not in logged, "raw newline must not survive into the log text"
    assert "\x1b[31m" not in logged, "raw ANSI escape must not survive into the log text"
    assert "\\n2026-07-29 00:00:00 | CRITICAL" in logged, "the newline should be visibly escaped, not silently dropped"


@pytest.mark.asyncio
async def test_stack_field_cannot_start_a_forged_log_line(caplog):
    """Codex P2 review on #578 (second round): per-field newline escaping wasn't
    enough, because the format string itself put a literal "\\n" immediately
    before the attacker-controlled stack. A stack whose first characters look
    like a log preamble therefore rendered as a second, standalone-looking
    entry even with its own embedded newlines escaped.
    """
    app = FastAPI()
    app.state.limiter = client_error_router.limiter
    app.include_router(client_error_router.router, prefix="/api")

    forged_stack = "2026-07-29 00:00:00 | CRITICAL | forged | database wiped"

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        with caplog.at_level(logging.WARNING, logger="client_error"):
            response = await client.post(
                "/api/client-error",
                json={"message": "real message", "stack": forged_stack},
            )

    assert response.status_code == 204
    assert len(caplog.records) == 1
    logged = caplog.records[0].message

    assert "\n" not in logged, (
        "the whole record must occupy a single line — a literal newline "
        "anywhere lets the stack masquerade as its own log entry"
    )
    # The stack content is still there (this is about framing, not dropping it).
    assert "database wiped" in logged
    # ...but only ever as an interior, quoted JSON value, never at line start.
    assert not logged.startswith(forged_stack)
    assert forged_stack in logged


def test_sanitizer_escapes_lone_surrogates():
    """_sanitize_for_log must never emit a raw surrogate.

    UTF-8 cannot encode one, so a surrogate reaching the RotatingFileHandler
    raises UnicodeEncodeError, logging swallows it into its own error trace,
    and the record is silently lost. Defense in depth: Pydantic rejects such
    input before the handler today (see the app-wide RequestValidationError
    test), but nothing guarantees every future caller comes through Pydantic.
    """
    # Private by design: the sanitizer is an internal helper, and testing it
    # directly is the point — the public path is gated by Pydantic.
    out = client_error_router._sanitize_for_log("\ud800 boom")  # noqa: SLF001

    assert "\\ud800" in out, "the surrogate should survive as a visible escape"
    assert "\ud800" not in out, "…but never as a raw code point"
    out.encode("utf-8")  # the actual failure being guarded

    # Ordinary non-ASCII must be untouched — the guard must not degrade
    # readability for player names, CJK or emoji.
    assert client_error_router._sanitize_for_log("\U0001f600 ok") == "\U0001f600 ok"  # noqa: SLF001
