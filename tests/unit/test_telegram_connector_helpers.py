"""Tests for TelegramConnector — config defaults + retry/parsing helpers.

This connector ships availability reminders to Telegram via the Bot API.
A regression silently:

- `__init__` `enabled` flag stays True when bot_token is empty → caller
  thinks connector is ready, then crashes on send_message.
- `__init__` clamps `max_retries` to >=1 → drift to 0 means a single
  transient 502 burns the message.
- `_extract_retry_after` misses the JSON `parameters.retry_after`
  fallback → connector ignores the rate-limit hint and retries
  immediately → permaban.
- `_safe_json` raises on non-JSON 502 page → outer try/except
  doesn't catch it → message dispatch crashes.
- `_response_detail` returns empty string when both JSON and text
  empty → operator log shows nothing useful.
- `__init__` bot_token whitespace not stripped → API URL contains
  trailing newline → 404 from Telegram.

Pin every static and the __init__ defaults.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from bot.services.telegram_connector import TelegramConnector

# ---------------------------------------------------------------------------
# __init__ — config defaults + clamping
# ---------------------------------------------------------------------------


def test_init_default_api_base_url():
    """Default API base = `https://api.telegram.org`. Pin so a
    config-less deploy still reaches Telegram."""
    c = TelegramConnector(enabled=False, bot_token="")
    assert c.api_base_url == "https://api.telegram.org"


def test_init_strips_trailing_slash_from_api_base():
    """Trailing `/` stripped — pin so token concat doesn't produce
    `//bot{TOKEN}/sendMessage` (Telegram returns 404 on double slash)."""
    c = TelegramConnector(enabled=False, bot_token="", api_base_url="https://api.example.com/")
    assert c.api_base_url == "https://api.example.com"


def test_init_strips_bot_token_whitespace():
    """`.env` files often have trailing newlines on values. Pin so a
    `\\n`-suffixed token doesn't 404 every send."""
    c = TelegramConnector(enabled=True, bot_token="  abc:def\n  ")  # noqa: S106
    assert c.bot_token == "abc:def"  # noqa: S105


def test_init_disabled_when_token_missing():
    """enabled=True + empty token → enabled becomes False (no
    misleading "ready" state). Pin observed defensive default."""
    c = TelegramConnector(enabled=True, bot_token="")
    assert c.enabled is False


def test_init_disabled_when_token_whitespace_only():
    """Token = whitespace → stripped to empty → enabled=False."""
    c = TelegramConnector(enabled=True, bot_token="   ")  # noqa: S106
    assert c.enabled is False


def test_init_enabled_when_both_flag_and_token_set():
    c = TelegramConnector(enabled=True, bot_token="real-token")  # noqa: S106
    assert c.enabled is True


def test_init_disabled_when_flag_false_even_with_token():
    """enabled=False + valid token → still disabled."""
    c = TelegramConnector(enabled=False, bot_token="real-token")  # noqa: S106
    assert c.enabled is False


def test_init_max_retries_clamped_to_minimum_1():
    """max_retries=0 → clamped to 1. Pin so a misconfig doesn't
    disable retries entirely."""
    c = TelegramConnector(enabled=False, bot_token="", max_retries=0)
    assert c.max_retries == 1


def test_init_max_retries_clamped_for_negative():
    c = TelegramConnector(enabled=False, bot_token="", max_retries=-5)
    assert c.max_retries == 1


def test_init_request_timeout_clamped_to_minimum_5():
    """Timeout < 5s → clamped to 5. Pin so a 1s timeout doesn't
    cause every Telegram call to fail."""
    c = TelegramConnector(enabled=False, bot_token="", request_timeout_seconds=1)
    assert c.request_timeout_seconds == 5


def test_init_min_interval_clamped_to_zero():
    """Negative pacing interval → 0 (no pacing). Pin so a config
    error doesn't cause `await asyncio.sleep(-1)` confusion."""
    c = TelegramConnector(enabled=False, bot_token="", min_interval_seconds=-2.0)
    assert c.min_interval_seconds == 0.0


def test_init_passes_through_positive_values():
    c = TelegramConnector(
        enabled=False,
        bot_token="",
        min_interval_seconds=0.5,
        max_retries=5,
        request_timeout_seconds=20,
    )
    assert c.min_interval_seconds == 0.5
    assert c.max_retries == 5
    assert c.request_timeout_seconds == 20


def test_init_starts_with_no_pacing_state():
    """_next_send_at starts at 0.0 — first send fires immediately
    (no fake "wait" before the very first message)."""
    c = TelegramConnector(enabled=False, bot_token="")
    assert c._next_send_at == 0.0


def test_init_starts_with_no_client():
    """Lazy-init: client is None until first use. Pin so a disabled
    connector doesn't create an httpx pool."""
    c = TelegramConnector(enabled=False, bot_token="")
    assert c._client is None


# ---------------------------------------------------------------------------
# _safe_json — defensive JSON parse
# ---------------------------------------------------------------------------


def test_safe_json_returns_parsed_dict():
    response = SimpleNamespace(json=lambda: {"ok": True, "result": {"id": 42}})
    out = TelegramConnector._safe_json(response)
    assert out == {"ok": True, "result": {"id": 42}}


def test_safe_json_returns_none_on_value_error():
    """Non-JSON response (e.g., 502 HTML page) → None (NOT raise).
    Pin so a Telegram outage page doesn't crash dispatch."""
    def raise_value():
        raise ValueError("bad json")
    response = SimpleNamespace(json=raise_value)
    out = TelegramConnector._safe_json(response)
    assert out is None


def test_safe_json_returns_none_on_key_error():
    """KeyError caught too (some httpx versions raise KeyError on
    missing content-type header during json parse)."""
    def raise_key():
        raise KeyError("no key")
    response = SimpleNamespace(json=raise_key)
    out = TelegramConnector._safe_json(response)
    assert out is None


# ---------------------------------------------------------------------------
# _extract_retry_after
# ---------------------------------------------------------------------------


def _build_response(headers=None, body=None, raise_json=False):
    """Build a fake response with optional headers + JSON body."""
    if raise_json:
        def json_fn():
            raise ValueError("not json")
    else:
        def json_fn():
            return body

    return SimpleNamespace(
        headers=headers or {},
        json=json_fn,
    )


def test_extract_retry_after_from_header():
    """Standard `Retry-After: 30` header → 30.0 float."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(headers={"Retry-After": "30"})
    assert c._extract_retry_after(response) == 30.0


def test_extract_retry_after_header_clamps_negative_to_zero():
    """Negative header value → 0.0 (no negative sleep)."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(headers={"Retry-After": "-5"})
    assert c._extract_retry_after(response) == 0.0


def test_extract_retry_after_falls_back_to_json_parameters():
    """No header → parse JSON `parameters.retry_after` (Telegram-
    specific fallback). Pin so a connector that strips Retry-After
    headers via proxy still respects the limit."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(
        headers={},
        body={"parameters": {"retry_after": 60}},
    )
    assert c._extract_retry_after(response) == 60.0


def test_extract_retry_after_returns_none_when_no_signals():
    """No header AND no JSON → None (caller picks exponential backoff)."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(headers={}, body={"ok": False})
    assert c._extract_retry_after(response) is None


def test_extract_retry_after_invalid_header_value():
    """Header is non-numeric ("garbage") → falls through to JSON
    fallback (NOT raise)."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(
        headers={"Retry-After": "garbage"},
        body={"parameters": {"retry_after": 15}},
    )
    assert c._extract_retry_after(response) == 15.0


def test_extract_retry_after_invalid_json_body_returns_none():
    """JSON parse fails AND no header → None."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(headers={}, raise_json=True)
    assert c._extract_retry_after(response) is None


def test_extract_retry_after_invalid_json_param_value_returns_none():
    """JSON parses but `retry_after` is non-numeric → None (no crash)."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = _build_response(
        headers={},
        body={"parameters": {"retry_after": "not-a-number"}},
    )
    assert c._extract_retry_after(response) is None


# ---------------------------------------------------------------------------
# _response_detail — operator-facing error message
# ---------------------------------------------------------------------------


def test_response_detail_uses_json_description():
    """Standard Telegram error response: `{"description": "..."}`.
    Pin so the operator log shows the API's reason verbatim."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = SimpleNamespace(
        headers={},
        json=lambda: {"ok": False, "description": "chat not found"},
        text="",
    )
    assert c._response_detail(response) == "chat not found"


def test_response_detail_falls_back_to_str_dict_when_no_description():
    """JSON body without `description` → str(dict). Pin so we still
    log SOMETHING for diagnosis."""
    c = TelegramConnector(enabled=False, bot_token="")
    response = SimpleNamespace(
        headers={},
        json=lambda: {"ok": False, "error_code": 400},
        text="",
    )
    out = c._response_detail(response)
    assert "ok" in out  # str of dict


def test_response_detail_falls_back_to_text_when_no_json():
    """Non-JSON response → first 300 chars of body."""
    c = TelegramConnector(enabled=False, bot_token="")
    def raise_value():
        raise ValueError("not json")
    response = SimpleNamespace(
        headers={},
        json=raise_value,
        text="<html>502 Bad Gateway</html>",
    )
    assert c._response_detail(response) == "<html>502 Bad Gateway</html>"


def test_response_detail_truncates_long_text_to_300_chars():
    """Long error body → truncated. Pin so the log line stays bounded."""
    c = TelegramConnector(enabled=False, bot_token="")
    def raise_value():
        raise ValueError("not json")
    response = SimpleNamespace(
        headers={},
        json=raise_value,
        text="x" * 1000,
    )
    out = c._response_detail(response)
    assert len(out) == 300


def test_response_detail_returns_placeholder_when_empty():
    """Empty/missing body → "no response body" placeholder. Pin so
    the operator log never has a blank "Telegram error: " line."""
    c = TelegramConnector(enabled=False, bot_token="")
    def raise_value():
        raise ValueError("not json")
    response = SimpleNamespace(headers={}, json=raise_value, text="")
    assert c._response_detail(response) == "no response body"


def test_response_detail_strips_text_whitespace():
    c = TelegramConnector(enabled=False, bot_token="")
    def raise_value():
        raise ValueError("not json")
    response = SimpleNamespace(
        headers={},
        json=raise_value,
        text="   server error   ",
    )
    assert c._response_detail(response) == "server error"


# ---------------------------------------------------------------------------
# send_message — disabled / invalid input guards
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_message_raises_when_disabled():
    """Calling send_message on disabled connector → RuntimeError
    (NOT silent skip)."""
    c = TelegramConnector(enabled=False, bot_token="")
    with pytest.raises(RuntimeError, match="disabled"):
        await c.send_message("12345", "hi")


@pytest.mark.asyncio
async def test_send_message_rejects_empty_chat_id():
    """Empty chat_id → ValueError (loud)."""
    c = TelegramConnector(enabled=True, bot_token="real-token")  # noqa: S106
    with pytest.raises(ValueError, match="chat_id"):
        await c.send_message("", "hi")


@pytest.mark.asyncio
async def test_send_message_rejects_whitespace_chat_id():
    """All-whitespace chat_id → ValueError (stripped to empty)."""
    c = TelegramConnector(enabled=True, bot_token="real-token")  # noqa: S106
    with pytest.raises(ValueError):
        await c.send_message("   ", "hi")


# ---------------------------------------------------------------------------
# close — lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_close_is_safe_when_no_client():
    """close() before any send → no-op (no AttributeError)."""
    c = TelegramConnector(enabled=False, bot_token="")
    assert c._client is None
    await c.close()  # No raise


@pytest.mark.asyncio
async def test_close_clears_client_reference():
    """close() resets _client to None — pin so a re-use after close
    creates a fresh client (NOT use a closed pool)."""
    from unittest.mock import AsyncMock
    c = TelegramConnector(enabled=False, bot_token="")
    fake_client = AsyncMock()
    fake_client.aclose = AsyncMock()
    c._client = fake_client
    await c.close()
    assert c._client is None
    fake_client.aclose.assert_awaited_once()
