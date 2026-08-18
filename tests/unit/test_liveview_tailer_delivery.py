"""Delivery-queue hardening for the liveview tailer (2026-08-18).

The old tailer dropped a batch after one retry — 44 lost batches in one
evening (Cloudflare 403/530), and every lost MAP/TEAM_CHANGE corrupted the
live state for a whole map. The bounded queue must (a) retry with backoff,
(b) evict telemetry-only batches first, (c) never slice-and-discard.
"""
# ruff: noqa: SLF001 — the queue internals ARE the unit under test
from __future__ import annotations


def _delivery(monkeypatch, results):
    from vps_scripts import liveview_tailer as lt

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
