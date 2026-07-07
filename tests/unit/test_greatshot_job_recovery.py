"""Greatshot restart recovery (Codex audit finding 9).

The job queues are in-memory asyncio.Queues: a restart between the DB insert
and job completion used to strand demos at 'uploaded'/'scanning' and renders
at 'queued'/'rendering' forever. _recover_stalled_jobs() must reset the
mid-flight states and re-enqueue everything pending.
"""
from __future__ import annotations

import pytest

from website.backend.services.greatshot_jobs import GreatshotJobService


class FakeDB:
    def __init__(self, *, scanning, uploaded, rendering, queued):
        self.scanning = scanning
        self.uploaded = uploaded
        self.rendering = rendering
        self.queued = queued
        self.updates: list[str] = []

    async def fetch_all(self, query, params=None):
        if "UPDATE greatshot_demos" in query:
            self.updates.append("demos-reset")
            reset, self.scanning = self.scanning, []
            self.uploaded = self.uploaded + reset
            return [(d,) for d in reset]
        if "UPDATE greatshot_renders" in query:
            self.updates.append("renders-reset")
            reset, self.rendering = self.rendering, []
            self.queued = self.queued + reset
            return [(r,) for r in reset]
        if "FROM greatshot_demos" in query:
            return [(d,) for d in self.uploaded]
        if "FROM greatshot_renders" in query:
            return [(r,) for r in self.queued]
        return []


@pytest.mark.asyncio
async def test_recovery_reenqueues_stranded_work():
    db = FakeDB(scanning=["demo-mid-scan"], uploaded=["demo-never-picked"],
                rendering=["render-mid"], queued=["render-waiting"])
    svc = GreatshotJobService(db=db, storage=None)

    await svc._recover_stalled_jobs()  # noqa: SLF001

    demos = {svc.analysis_queue.get_nowait() for _ in range(svc.analysis_queue.qsize())}
    renders = {svc.render_queue.get_nowait() for _ in range(svc.render_queue.qsize())}
    assert demos == {"demo-mid-scan", "demo-never-picked"}
    assert renders == {"render-mid", "render-waiting"}
    assert db.updates == ["demos-reset", "renders-reset"], (
        "mid-flight rows must be reset before re-enqueueing"
    )


@pytest.mark.asyncio
async def test_recovery_noop_on_clean_state():
    db = FakeDB(scanning=[], uploaded=[], rendering=[], queued=[])
    svc = GreatshotJobService(db=db, storage=None)
    await svc._recover_stalled_jobs()  # noqa: SLF001
    assert svc.analysis_queue.qsize() == 0
    assert svc.render_queue.qsize() == 0
