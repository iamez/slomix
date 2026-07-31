"""Client-side error reporting (W4, docs/TASKS_FOR_SONNET_2026-07-29.md).

Public, unauthenticated endpoint the frontend calls when window.onerror or
unhandledrejection fires, so a browser exception is visible server-side
without the visitor needing to have devtools open and paste it in by hand.

This endpoint is public and unauthenticated by design — the whole point is
that it fires before anyone has logged in, or for visitors who never will.
That makes it a denial-of-service/log-flood vector pointed at our own disk,
so it is rate-limited hard (both by the route's own slowapi limiter and by a
dedicated ASGI-level bucket in RateLimitMiddleware that applies before the
body is even parsed — see that middleware for why the route-level limiter
alone isn't enough) and every field is length-capped server-side (the
frontend also truncates and dedupes, but a client is not trusted to have run
that code faithfully).
"""

import json
import re

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from website.backend.env_utils import getenv_int
from website.backend.logging_config import get_client_error_logger
from website.backend.rate_limit import limiter

router = APIRouter()
logger = get_client_error_logger()

# Derived from the same env vars RateLimitMiddleware's client_error bucket uses,
# so raising the configured quota actually raises it. A hard-coded "20/minute"
# here silently capped the endpoint at 20/min no matter what the middleware was
# configured to allow, making the documented knobs unable to increase throughput
# (Codex review on #578). Read at import time, like every other limit here.
_CLIENT_ERROR_LIMIT = max(1, getenv_int("RATE_LIMIT_CLIENT_ERROR_REQUESTS_PER_WINDOW", 20))
_CLIENT_ERROR_WINDOW_SECONDS = max(1, getenv_int("RATE_LIMIT_WINDOW_SECONDS", 60))
CLIENT_ERROR_RATE_LIMIT = f"{_CLIENT_ERROR_LIMIT}/{_CLIENT_ERROR_WINDOW_SECONDS} seconds"

# Every field here is attacker-controlled and, with the default
# LOG_FORMAT_JSON=false, gets interpolated directly into a line-oriented
# plain-text log. SensitiveDataFilter redacts known secret *patterns* but
# doesn't touch newlines/control characters, so an unescaped \n lets a caller
# forge what looks like a second log entry, and raw control/escape sequences
# can corrupt a terminal that later `tail`s the file (Codex P2 review on
# #578). Replace CR/LF with visible escapes and drop other C0 control chars
# before anything reaches the logger.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Defense in depth against lone surrogates. UTF-8 cannot encode one, so a
# surrogate reaching the RotatingFileHandler raises UnicodeEncodeError, logging
# swallows it into its own "--- Logging error ---" trace, and the record is
# never written.
#
# To be accurate about the reported case (Codex review on #578): a surrogate
# does NOT reach this function today. Pydantic v2 rejects it first with
# `string_unicode`, so the request never enters the handler — it fails earlier,
# and louder, in FastAPI's own validation-error rendering (fixed app-wide in
# main.py's RequestValidationError handler). This guard covers the paths
# Pydantic does not gate: a future caller that logs a string built here rather
# than parsed from a request body.
#
# Rewritten to a visible \uXXXX escape rather than dropped, so a triager can
# still see what arrived. ensure_ascii=False stays on the json.dumps() below —
# it keeps ordinary non-ASCII (player names, CJK) readable when tailing.
_SURROGATES_RE = re.compile(r"[\ud800-\udfff]")


def _sanitize_for_log(value: str | None) -> str:
    if not value:
        return ""
    value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    value = _SURROGATES_RE.sub(lambda m: f"\\u{ord(m.group()):04x}", value)
    return _CONTROL_CHARS_RE.sub("", value)


class ClientErrorReport(BaseModel):
    message: str = Field(..., max_length=2000)
    stack: str | None = Field(default=None, max_length=2000)
    page_url: str | None = Field(default=None, max_length=500)
    user_agent: str | None = Field(default=None, max_length=300)
    timestamp: str | None = Field(default=None, max_length=64)


@router.post("/client-error", status_code=204, response_class=Response)
@limiter.limit(CLIENT_ERROR_RATE_LIMIT)
async def report_client_error(request: Request, report: ClientErrorReport) -> Response:
    # One line, whole record JSON-serialized. The previous format string put a
    # literal "\n" before the stack, which meant even a fully newline-escaped
    # stack still began on its own fresh line — a stack starting with
    # "2026-07-29 ... | CRITICAL | ..." therefore rendered as a second,
    # standalone-looking log entry, i.e. log-entry forgery survived the
    # per-field escaping (Codex P2 review on #578, second round).
    # json.dumps() is the actual guarantee here: it escapes newlines and
    # control characters in its output, so no field value can terminate the
    # line no matter what it contains. _sanitize_for_log stays as
    # defense-in-depth and to keep the values readable rather than
    # \u-escaped when tailing.
    logger.warning(
        "Client error: %s",
        json.dumps(
            {
                "message": _sanitize_for_log(report.message) or "(empty)",
                "page": _sanitize_for_log(report.page_url) or "unknown",
                "ua": _sanitize_for_log(report.user_agent) or "unknown",
                "ts": _sanitize_for_log(report.timestamp) or "unknown",
                "stack": _sanitize_for_log(report.stack) or "(no stack)",
            },
            ensure_ascii=False,
        ),
    )
    return Response(status_code=204)
