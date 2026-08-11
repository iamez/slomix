"""Live view feed (S1 of the Live-view plan).

Event flow: the tail daemon on the game server (S2,
vps_scripts/liveview_tailer.py) parses ``legacy3.log`` lines the moment the
engine writes them and POSTs batches here; browsers poll the feed with a
``since`` cursor every few seconds (S3, the Tonight panel).

Storage is a process-local ring buffer, deliberately NOT Redis: the site
runs a single uvicorn worker (systemd unit has no --workers), live events
are ephemeral by definition (a page load only ever needs the last few
minutes), and the ``since`` cursor makes polling lossless while the buffer
holds more events than a round produces (~330 lines/round median, buffer
1000). If the worker restarts the buffer starts empty and clients simply
resync — the authoritative record is legacy3.log, not this buffer.

Design notes pinned by research (LIVE_VIEW_RESEARCH_2026-08-11):
- POST is authenticated with the existing X-Internal-Token secret; the
  browser side is read-only.
- Feed responses must never be cached (the HTTP cache middleware already
  marks non-cacheable /api paths "private, no-store").
- Team chat never reaches this process — the parser redacts it at the
  source — but the ingest endpoint still refuses unknown event types, so a
  misconfigured tailer cannot turn this into a generic message bus.
"""

from __future__ import annotations

import asyncio
import time
from collections import deque
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from website.backend.dependencies import require_internal_secret

router = APIRouter()

_BUFFER_MAX = 1000
_POST_MAX_EVENTS = 200

# Event types a tailer may publish — mirror of the parser's vocabulary that
# is meaningful to spectators. SAY is included (public chat), TEAM_CHAT is
# not (redacted at parse time and rejected here as defence in depth).
_ALLOWED_TYPES = frozenset({
    "ANNOUNCE", "POPUP", "FLAG_PICKUP", "DYNAMITE", "OBJECTIVE_DESTROYED",
    "KILL", "REVIVE", "TEAM_CHANGE", "CONNECT", "DISCONNECT",
    "MAP", "GAMETYPE", "GAMETIME", "INIT_GAME",
    "ROUND_START", "ROUND_END", "STATS_SAVED", "EXIT",
    "SCORELINE", "TEAM_XP", "CALLVOTE", "VOTE_PASSED", "SAY",
    # LIVEX types from live_events.lua / slomix-live.log (design doc
    # LIVE_EVENTS_LUA_DESIGN_2026-08-12). Inert until that module is deployed.
    "LIVE_KILL", "LIVE_AGGREGATE", "LIVE_MOVEMENT", "LIVE_MAP",
})

_events: deque[dict[str, Any]] = deque(maxlen=_BUFFER_MAX)
_seq = 0
_lock = asyncio.Lock()


class LiveEventIn(BaseModel):
    type: str
    level_ms: int | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class LiveEventBatch(BaseModel):
    events: list[LiveEventIn]
    source: str = "tailer"


@router.post("/events", dependencies=[Depends(require_internal_secret)])
async def ingest_events(batch: LiveEventBatch) -> dict[str, Any]:
    """Accept a batch of parsed live events from the log tailer."""
    global _seq
    if len(batch.events) > _POST_MAX_EVENTS:
        raise HTTPException(status_code=413, detail="batch too large")
    accepted = 0
    now = time.time()
    async with _lock:
        for ev in batch.events:
            etype = ev.type.upper()
            if etype not in _ALLOWED_TYPES:
                continue
            _seq += 1
            _events.append({
                "seq": _seq,
                "type": etype,
                "level_ms": ev.level_ms,
                "received_at": now,
                **ev.fields,
            })
            accepted += 1
    return {"status": "ok", "accepted": accepted, "last_seq": _seq}


@router.get("/feed")
async def feed(
    since: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
) -> dict[str, Any]:
    """Events with seq > since, oldest first. Poll every ~3 s with the last
    seen seq; an empty page just means nothing happened."""
    async with _lock:
        out = [e for e in _events if e["seq"] > since][:limit]
        last_seq = _seq
    return {
        "status": "ok",
        "events": out,
        "last_seq": last_seq,
        "server_time": time.time(),
    }


@router.get("/status")
async def status() -> dict[str, Any]:
    """Liveness for dashboards: how fresh is the newest event."""
    async with _lock:
        newest = _events[-1]["received_at"] if _events else None
        count = len(_events)
        last_seq = _seq
    return {
        "status": "ok",
        "buffered": count,
        "last_seq": last_seq,
        "newest_age_seconds": (time.time() - newest) if newest else None,
    }
