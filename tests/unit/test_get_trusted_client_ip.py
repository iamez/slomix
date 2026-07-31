"""Regression test for the spoofable-XFF rate-limit bypass (Codex P1 review on #578).

_get_real_ip's old implementation trusted the leftmost X-Forwarded-For value
unconditionally. nginx's $proxy_add_x_forwarded_for APPENDS the real client IP
to whatever the client already sent rather than replacing it, so a client
could send X-Forwarded-For: 1.2.3.4 and have nginx forward
"1.2.3.4, <real-ip>" — the leftmost (attacker-controlled) value is what a
naive .split(",")[0] picks up. That lets any client spoof an unlimited number
of distinct rate-limit identities and bypass the limiter entirely, on the
public unauthenticated /api/client-error endpoint and every other
slowapi-limited route sharing the same key_func.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from website.backend.security_utils import get_trusted_client_ip


def _request(*, direct_ip: str, headers: dict[str, str]):
    request = MagicMock()
    request.client.host = direct_ip
    request.headers = headers
    return request


def test_untrusted_direct_client_cannot_spoof_forwarded_for(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_TRUSTED_PROXIES", raising=False)
    # Attacker connects directly (not through a trusted proxy) and forges a
    # forwarded-for header pointing at an arbitrary IP.
    request = _request(
        direct_ip="203.0.113.50",
        headers={"x-forwarded-for": "1.2.3.4, 9.9.9.9"},
    )

    result = get_trusted_client_ip(request)

    assert result == "203.0.113.50", (
        "an untrusted direct peer's forwarded-for header must be ignored — "
        "otherwise any client can spoof unlimited rate-limit identities"
    )


def test_trusted_proxy_forwarded_for_is_honoured(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "127.0.0.1")
    # nginx (a trusted proxy) connects directly and forwards the real client
    # IP as the leftmost value.
    request = _request(
        direct_ip="127.0.0.1",
        headers={"x-forwarded-for": "198.51.100.7, 127.0.0.1"},
    )

    result = get_trusted_client_ip(request)

    assert result == "198.51.100.7"


def test_no_forwarded_header_falls_back_to_direct_client():
    request = _request(direct_ip="203.0.113.50", headers={})
    assert get_trusted_client_ip(request) == "203.0.113.50"


def test_trusted_proxy_does_not_let_client_prepend_a_forged_hop(monkeypatch):
    """The leftmost XFF entry is attacker-controlled even behind a trusted proxy.

    nginx's `$proxy_add_x_forwarded_for` builds
    "$http_x_forwarded_for, $remote_addr" — it APPENDS, so a client that sends
    its own `X-Forwarded-For: 1.2.3.4` makes nginx forward
    "1.2.3.4, <real client ip>". Reading leftmost-first (the previous
    behaviour) returns the forged 1.2.3.4, which is the same unlimited-identity
    bypass this module exists to prevent — just re-opened the moment a real
    proxy is added to RATE_LIMIT_TRUSTED_PROXIES, which is exactly what the
    Docker deployment needs to do.
    """
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "172.20.0.0/16")
    request = _request(
        direct_ip="172.20.0.3",  # the nginx container, a trusted proxy
        headers={"x-forwarded-for": "1.2.3.4, 198.51.100.7"},
    )

    result = get_trusted_client_ip(request)

    assert result == "198.51.100.7", (
        "must return the address nginx itself appended, not the value the "
        f"client prepended to the header (got {result!r})"
    )


def test_multiple_trusted_hops_are_skipped_to_the_real_client(monkeypatch):
    """Two chained trusted proxies: the real client is left of both."""
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "172.20.0.0/16,10.0.0.0/8")
    request = _request(
        direct_ip="172.20.0.3",
        headers={"x-forwarded-for": "198.51.100.7, 10.0.0.5, 172.20.0.9"},
    )

    assert get_trusted_client_ip(request) == "198.51.100.7"


def test_all_hops_trusted_falls_back_to_leftmost(monkeypatch):
    """Internal-only traffic (e.g. a healthcheck through the proxy chain)."""
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "172.20.0.0/16")
    request = _request(
        direct_ip="172.20.0.3",
        headers={"x-forwarded-for": "172.20.0.8, 172.20.0.9"},
    )

    assert get_trusted_client_ip(request) == "172.20.0.8"


def test_x_real_ip_used_when_no_forwarded_for(monkeypatch):
    """nginx always overwrites X-Real-IP with $remote_addr — unforgeable."""
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "172.20.0.0/16")
    request = _request(
        direct_ip="172.20.0.3",
        headers={"x-real-ip": "198.51.100.7"},
    )

    assert get_trusted_client_ip(request) == "198.51.100.7"
