"""Graph rendering must not starve the event loop (FIX 4 regression guard).

`!last_session graphs` renders five matplotlib figures. Before the fix the
rendering ran inline in the event loop: one uninterrupted ~3.5s stall per
call (measured on the dev box: max heartbeat gap 3636ms, i.e. every other
command and task loop frozen). After the fix the pure-CPU rendering runs in
a worker thread via asyncio.to_thread, and the loop keeps ticking
(measured: max gap 69ms).

The test runs a 50ms heartbeat concurrently with graph generation and
asserts the loop never stalls for more than a generous CI-safe threshold —
an order of magnitude below the pre-fix stall, an order above post-fix
jitter.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from bot.services.session_graph_generator import SessionGraphGenerator


class _FakeDbAdapter:
    async def fetch_all(self, query, params=None):
        if "FROM player_comprehensive_stats p" in query and "GROUP BY p.player_guid" in query:
            # Two players so grouped bar charts and playstyle panels have data.
            return [
                ("Alpha", 30, 12, 9000, 5000, 350.0, 1500, 5.0, 4, 2, 6, 9, 240, 12, 2, 1, "GUID_ALPHA", 4),
                ("Bravo", 18, 20, 6000, 7000, 250.0, 1450, 8.0, 9, 5, 2, 3, 400, 7, 4, 2, "GUID_BRAVO", 4),
            ]
        # Timeline query (JOIN rounds) and anything else: no rows.
        return []


@pytest.mark.asyncio
async def test_graph_rendering_does_not_starve_event_loop(monkeypatch):
    generator = SessionGraphGenerator(_FakeDbAdapter())

    async def _fake_columns():
        return {"full_selfkills"}

    monkeypatch.setattr(generator, "_get_player_stats_columns", _fake_columns)

    gaps: list[float] = []
    stop = asyncio.Event()

    async def heartbeat():
        prev = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(0.05)
            now = time.perf_counter()
            gaps.append(now - prev)
            prev = now

    hb = asyncio.create_task(heartbeat())
    try:
        bufs = await generator.generate_performance_graphs("2026-01-01", [1, 2], "1,2")
    finally:
        stop.set()
        await hb

    # Rendering succeeded: figures 1-4 rendered (timeline is None — no rows).
    assert all(b is not None for b in bufs[:4])

    # The event loop kept breathing during the whole call. Pre-fix this was
    # a single ~render-length stall; post-fix worst gap is ~0.07s locally.
    assert gaps, "heartbeat never ticked — event loop was blocked throughout"
    assert max(gaps) < 1.0, f"event loop stalled {max(gaps):.2f}s during graph rendering"
