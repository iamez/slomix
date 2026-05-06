"""Tests for SignalConnector pure helpers + __init__.

This connector sends operator-facing Signal notifications (admin
alerts, monitoring breakdowns). A regression silently:

- Ignores rate-limits → bot gets banned by daemon, all alerts drop.
- Misparses JSON → wrong retry_after used, exponential backoff broken.
- Init sanitises bad config → enabled when misconfigured.

`_extract_retry_after`, `_safe_json`, `_response_detail` are all pure;
the constructor has substantial validation/coercion logic worth
pinning.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from bot.services.signal_connector import SignalConnector


def _response(status=200, headers=None, json_value=None,
              json_raises=False, text=""):
    """Build a fake httpx.Response with controllable .headers, .json(), .text."""
    r = MagicMock()
    r.status_code = status
    r.headers = headers or {}
    if json_raises:
        r.json.side_effect = ValueError("not json")
    else:
        r.json.return_value = json_value
    r.text = text
    return r


# ---------------------------------------------------------------------------
# __init__ — validation + coercion
# ---------------------------------------------------------------------------


def test_init_disables_when_sender_number_missing():
    """enabled=True but sender_number empty → effectively disabled.
    Pin: a misconfigured deploy must NOT silently send unauth'd messages."""
    s = SignalConnector(enabled=True, sender_number="")
    assert s.enabled is False


def test_init_disables_when_enabled_flag_false():
    """enabled=False → disabled regardless of sender_number."""
    s = SignalConnector(enabled=False, sender_number="+1234567890")
    assert s.enabled is False


def test_init_enables_when_both_set():
    s = SignalConnector(enabled=True, sender_number="+1234567890")
    assert s.enabled is True


def test_init_normalises_mode_lowercase():
    """`MODE=CLI` env → 'cli'."""
    s = SignalConnector(enabled=True, sender_number="+1", mode="CLI")
    assert s.mode == "cli"


def test_init_unknown_mode_falls_back_to_cli():
    """`mode='websocket'` → 'cli' (safe default)."""
    s = SignalConnector(enabled=True, sender_number="+1", mode="websocket")
    assert s.mode == "cli"


def test_init_strips_whitespace_from_sender_number():
    s = SignalConnector(enabled=True, sender_number="  +1234567890  ")
    assert s.sender_number == "+1234567890"


def test_init_strips_trailing_slash_from_daemon_url():
    """`http://x/` → `http://x` so endpoint joining is consistent."""
    s = SignalConnector(
        enabled=True, sender_number="+1",
        daemon_url="http://daemon.local:8080/",
    )
    assert s.daemon_url == "http://daemon.local:8080"


def test_init_min_interval_clamped_to_zero():
    """Negative min_interval → 0 (no negative pacing)."""
    s = SignalConnector(
        enabled=True, sender_number="+1", min_interval_seconds=-5.0,
    )
    assert s.min_interval_seconds == 0.0


def test_init_max_retries_floored_at_one():
    """0 retries makes no sense — pin lower bound."""
    s = SignalConnector(enabled=True, sender_number="+1", max_retries=0)
    assert s.max_retries == 1


def test_init_request_timeout_floored_at_five():
    """Sub-5s timeout would tear down legitimate slow Signal requests."""
    s = SignalConnector(
        enabled=True, sender_number="+1", request_timeout_seconds=1,
    )
    assert s.request_timeout_seconds == 5


def test_init_uses_default_signal_cli_path_when_empty():
    s = SignalConnector(enabled=True, sender_number="+1", signal_cli_path="")
    assert s.signal_cli_path == "signal-cli"


# ---------------------------------------------------------------------------
# _safe_json — JSON parse with fail-safe
# ---------------------------------------------------------------------------


def test_safe_json_returns_parsed_dict():
    r = _response(json_value={"a": 1})
    assert SignalConnector._safe_json(r) == {"a": 1}


def test_safe_json_returns_none_on_value_error():
    """Non-JSON body → None (NOT raise). Pin so a malformed daemon
    response doesn't crash the whole notification pipeline."""
    r = _response(json_raises=True)
    assert SignalConnector._safe_json(r) is None


# ---------------------------------------------------------------------------
# _extract_retry_after — Retry-After header + JSON body fallback
# ---------------------------------------------------------------------------


@pytest.fixture
def connector():
    return SignalConnector(enabled=True, sender_number="+1")


def test_extract_retry_after_uses_header_value(connector):
    """`Retry-After: 5` → 5.0 (numeric seconds)."""
    r = _response(headers={"Retry-After": "5"})
    assert connector._extract_retry_after(r) == 5.0


def test_extract_retry_after_floors_negative_at_zero(connector):
    """`Retry-After: -3` → 0 (no negative wait)."""
    r = _response(headers={"Retry-After": "-3"})
    assert connector._extract_retry_after(r) == 0.0


def test_extract_retry_after_falls_back_to_json_when_header_unparseable(connector):
    """Header is present but not numeric → fall through to JSON body."""
    r = _response(
        headers={"Retry-After": "not-a-number"},
        json_value={"parameters": {"retry_after": 7}},
    )
    assert connector._extract_retry_after(r) == 7.0


def test_extract_retry_after_uses_error_object_in_json(connector):
    """Body shape: {"error": {"retry_after": 3}} (Discord-like)."""
    r = _response(json_value={"error": {"retry_after": 3.5}})
    assert connector._extract_retry_after(r) == 3.5


def test_extract_retry_after_uses_parameters_object_in_json(connector):
    """Body shape: {"parameters": {"retry_after": 2}}."""
    r = _response(json_value={"parameters": {"retry_after": 2}})
    assert connector._extract_retry_after(r) == 2.0


def test_extract_retry_after_returns_none_when_no_signal(connector):
    """No header, no JSON → None (caller picks default 1s)."""
    r = _response(json_value={})
    assert connector._extract_retry_after(r) is None


def test_extract_retry_after_returns_none_when_json_field_unparseable(connector):
    """`retry_after: "abc"` in JSON → None."""
    r = _response(json_value={"parameters": {"retry_after": "abc"}})
    assert connector._extract_retry_after(r) is None


def test_extract_retry_after_ignores_non_dict_error_field(connector):
    """`error: "string error"` (not a dict) → no retry_after extracted
    via that path. Pin so the isinstance() check stays."""
    r = _response(json_value={"error": "boom"})
    # Falls through to None (no parameters either)
    assert connector._extract_retry_after(r) is None


def test_extract_retry_after_returns_none_when_json_is_not_dict(connector):
    """JSON body is e.g. a list → not a dict → None."""
    r = _response(json_value=["some", "list"])
    assert connector._extract_retry_after(r) is None


# ---------------------------------------------------------------------------
# _response_detail — operator-facing diagnostic string
# ---------------------------------------------------------------------------


def test_response_detail_returns_str_for_dict_json(connector):
    """JSON dict → str(dict) for operator log readability."""
    r = _response(json_value={"err": "boom"})
    out = connector._response_detail(r)
    assert "err" in out
    assert "boom" in out


def test_response_detail_returns_text_when_json_unparseable(connector):
    """No JSON → trimmed text body, capped at 300 chars."""
    r = _response(json_raises=True, text="  some plain text  ")
    out = connector._response_detail(r)
    assert out == "some plain text"


def test_response_detail_truncates_long_text(connector):
    """Body > 300 chars → truncated. Pin so the operator log doesn't
    get spammed with a whole HTML error page."""
    r = _response(json_raises=True, text="x" * 500)
    out = connector._response_detail(r)
    assert len(out) == 300


def test_response_detail_returns_placeholder_for_empty_body(connector):
    r = _response(json_raises=True, text="")
    out = connector._response_detail(r)
    assert out == "no response body"


def test_response_detail_handles_whitespace_only_body(connector):
    """Whitespace-only text → strip() → empty → placeholder."""
    r = _response(json_raises=True, text="   \n\t  ")
    out = connector._response_detail(r)
    assert out == "no response body"
