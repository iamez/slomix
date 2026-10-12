"""Delivery-queue hardening for the liveview tailer (2026-08-18).

The old tailer dropped a batch after one retry — 44 lost batches in one
evening (Cloudflare 403/530), and every lost MAP/TEAM_CHANGE corrupted the
live state for a whole map. The bounded queue must (a) retry with backoff,
(b) evict telemetry-only batches first, (c) never slice-and-discard.
"""
# ruff: noqa: SLF001 — the queue internals ARE the unit under test
from __future__ import annotations

import socket
from io import BytesIO
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("url", [
    "http://localhost.example.invalid/api/live/events",
    "http://127.0.0.1.example.invalid/api/live/events",
    "http://localhost@elsewhere.invalid/api/live/events",
    "http://127.0.0.1@elsewhere.invalid/api/live/events",
    "http://localhost:bad/api/live/events",
])
def test_http_loopback_lookalikes_are_refused_before_transport(monkeypatch, url):
    from vps_scripts import liveview_tailer as lt
    monkeypatch.setattr(socket, "getaddrinfo", lt._orig_getaddrinfo)
    transport = Mock(side_effect=AssertionError("transport must not run"))
    monkeypatch.setattr(lt.urllib.request, "urlopen", transport)
    monkeypatch.setattr(lt.urllib.request, "build_opener", transport)
    assert lt._url_allowed(url) is False
    assert lt._post_once(url, "fixture", [], "fixture") is False
    transport.assert_not_called()


@pytest.mark.parametrize("url", [
    "https://www.example.invalid/api/live/events",
    "http://localhost:8000/api/live/events",
    "http://127.0.0.1:8000/api/live/events",
    "http://127.0.0.10:8000/api/live/events",
])
def test_explicit_https_and_exact_loopback_remain_supported(monkeypatch, url):
    from vps_scripts import liveview_tailer as lt
    monkeypatch.setattr(socket, "getaddrinfo", lt._orig_getaddrinfo)
    assert lt._url_allowed(url) is True
    transport = Mock()
    transport.open.return_value = BytesIO(b'{"status":"ok"}')
    factory = Mock(return_value=transport)
    monkeypatch.setattr(lt.urllib.request, "build_opener", factory)
    monkeypatch.setattr(lt.urllib.request, "urlopen", Mock(side_effect=AssertionError("network forbidden")))
    assert lt._post_once(url, "fixture", [], "fixture") is True
    assert any(isinstance(h, lt._NoRedirect) for h in factory.call_args.args)
    assert transport.open.call_args.args[0].full_url == url


def test_authenticated_post_does_not_follow_redirects(monkeypatch):
    from vps_scripts import liveview_tailer as lt
    monkeypatch.setattr(socket, "getaddrinfo", lt._orig_getaddrinfo)
    req = lt.urllib.request.Request("https://www.example.invalid/api/live/events",
                                    data=b"{}", headers={"X-Internal-Token": "fixture"})
    handler = lt._NoRedirect()
    assert handler.redirect_request(req, None, 302, "Found", {},
                                    "http://elsewhere.invalid/events") is None
    transport = Mock()
    transport.open.side_effect = lt.urllib.error.HTTPError(req.full_url, 302, "Found", {}, None)
    factory = Mock(return_value=transport)
    monkeypatch.setattr(lt.urllib.request, "build_opener", factory)
    monkeypatch.setattr(lt.urllib.request, "urlopen", Mock(side_effect=AssertionError("network forbidden")))
    assert lt._post_once(req.full_url, "fixture", [], "fixture") is False
    assert any(isinstance(h, lt._NoRedirect) for h in factory.call_args.args)
    transport.open.assert_called_once()


def _delivery(monkeypatch, results):
    import socket

    from vps_scripts import liveview_tailer as lt

    # Importing the module monkeypatches socket.getaddrinfo (IPv4-only for
    # the game box) — restore it so the side-effect can't leak into other
    # tests in the same process (coderabbit, PR #773).
    monkeypatch.setattr(socket, "getaddrinfo", lt._orig_getaddrinfo)

    calls = []

    def fake_post(url, secret, batch, source):
        calls.append(list(batch))
        return results.pop(0) if results else True
    monkeypatch.setattr(lt, "_post_once", fake_post)
    return lt, lt._Delivery("http://x", "s", "tailer"), calls


def test_failed_batch_is_retried_not_dropped(monkeypatch):
    lt, d, calls = _delivery(monkeypatch, [False, True])
    d.push([{"type": "MAP", "fields": {}}])
    d.pump()            # fails -> stays queued, backoff armed
    assert d.depth == 1
    d._next_try = 0.0   # fast-forward past the backoff
    d.pump()            # succeeds
    assert d.depth == 0
    assert len(calls) == 2


def test_eviction_prefers_telemetry_over_control(monkeypatch):
    lt, d, _ = _delivery(monkeypatch, [])
    control = [{"type": "MAP", "fields": {}}]
    telemetry = [{"type": "LIVE_MOVEMENT", "fields": {}}]
    for _i in range(lt.QUEUE_MAX_BATCHES):
        d.push(list(control))
    d.push(list(telemetry))  # over budget -> telemetry evicted, control kept
    assert d.depth == lt.QUEUE_MAX_BATCHES
    assert all(b[0]["type"] == "MAP" for b in d._queue)
