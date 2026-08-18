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
import json
import os
import time
import urllib.parse
import urllib.request
from collections import deque
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from website.backend.dependencies import require_internal_secret
from website.backend.services.live_state import LiveStateReducer

router = APIRouter()

# Current-state snapshot (Live-view A0). The event ring is the play-by-play
# log; this reducer is the authoritative "right now" state (roster, map,
# game state) so the page renders correctly on load instead of replaying a
# stale ring. See services/live_state.py.
_state = LiveStateReducer()

_BUFFER_MAX = 1000
_POST_MAX_EVENTS = 200

# Event types a tailer may publish — mirror of the parser's vocabulary that
# is meaningful to spectators. SAY is included (public chat), TEAM_CHAT is
# not (redacted at parse time and rejected here as defence in depth).
_ALLOWED_TYPES = frozenset({
    "ANNOUNCE", "POPUP", "FLAG_PICKUP", "DYNAMITE", "OBJECTIVE_DESTROYED",
    "KILL", "REVIVE", "TEAM_CHANGE", "CONNECT", "DISCONNECT", "BEGIN",
    "MAP", "GAMETYPE", "GAMETIME", "INIT_GAME",
    "ROUND_START", "ROUND_END", "STATS_SAVED", "EXIT",
    "SCORELINE", "TEAM_XP", "CALLVOTE", "VOTE_PASSED", "SAY",
    "SUPPLY", "SHOVE",
    # LIVEX types from live_events.lua / slomix-live.log (design doc
    # LIVE_EVENTS_LUA_DESIGN_2026-08-12). Inert until that module is deployed.
    "LIVE_KILL", "LIVE_AGGREGATE", "LIVE_MOVEMENT", "LIVE_MAP",
})
# BEGIN (reducer handles it), SUPPLY and SHOVE (the ticker's "support"
# category lists them) were produced by the parser but rejected here —
# dead handling on both sides until 2026-08-18.

# High-volume LIVEX telemetry that no feed consumer renders: it stays in the
# ring for /state derivation but is excluded from /feed responses unless the
# caller asks for it explicitly. At 12 players this is ~17 events per 10 s
# and it previously drowned both the 200-event feed page and the client
# buffer (the "one stale revive + quiet" symptom).
_FEED_HIDDEN_TYPES = frozenset({"LIVE_MOVEMENT", "LIVE_AGGREGATE"})

# Events older than this never leave /feed — a browser that reconnects after
# a long gap resyncs from /state, it must not replay a quarter hour of ring.
_FEED_RETENTION_SECONDS = 600

# Both tailers report the same obituary: legacy3.log ("KILL") and
# live_events.lua ("LIVE_KILL"). Slots identify the kill; suppress the legacy
# copy when the LIVEX one already landed within this window (the LIVEX record
# is richer — positions, health). The reverse order is left alone: the ring
# is append-only, and the client-side latch still hides the visual dup.
_KILL_DEDUP_SECONDS = 1.5

_events: deque[dict[str, Any]] = deque(maxlen=_BUFFER_MAX)
_seq = 0
_lock = asyncio.Lock()
# (killer_slot, victim_slot) -> received_at of the last LIVE_KILL
_recent_livex_kills: dict[tuple[int, int], float] = {}

# Dev mirror (2026-08-18): the tailers on the game server post ONLY to prod,
# so the dev ring is empty by construction and the Live page could never be
# exercised on dev. When LIVE_UPSTREAM_URL is set (dev .env only — e.g.
# "https://www.slomix.fyi/api/live") and the LOCAL ring is empty, the GET
# endpoints read through to the upstream. Local data (a replay test posting
# into dev) always wins, so `scripts/liveview_replay.py --post` still works.
_UPSTREAM = os.getenv("LIVE_UPSTREAM_URL", "").rstrip("/")


async def _proxy(path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Best-effort upstream GET; None on any failure (caller falls back)."""
    if not _UPSTREAM:
        return None
    url = f"{_UPSTREAM}/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None})

    if not url.startswith(("http://", "https://")):
        return None

    def _get() -> dict[str, Any]:
        req = urllib.request.Request(  # noqa: S310 — scheme validated above
            url, headers={"User-Agent": "slomix-live-proxy/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:  # noqa: S310 # nosec B310
            return json.loads(resp.read().decode("utf-8"))

    try:
        return await asyncio.to_thread(_get)
    except Exception:
        return None


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
            if etype == "LIVE_KILL":
                ks = ev.fields.get("killer_slot")
                vs = ev.fields.get("victim_slot")
                if isinstance(ks, int) and isinstance(vs, int):
                    _recent_livex_kills[(ks, vs)] = now
                    if len(_recent_livex_kills) > 64:
                        cutoff = now - _KILL_DEDUP_SECONDS
                        for key in [k for k, t in _recent_livex_kills.items()
                                    if t < cutoff]:
                            del _recent_livex_kills[key]
            elif etype == "KILL":
                ks = ev.fields.get("killer_slot")
                vs = ev.fields.get("victim_slot")
                seen = _recent_livex_kills.get((ks, vs))
                if seen is not None and now - seen <= _KILL_DEDUP_SECONDS:
                    continue  # LIVEX already carried this obituary
            _seq += 1
            record = {
                "seq": _seq,
                "type": etype,
                "level_ms": ev.level_ms,
                # LIVEX stamps epoch ms into level_ms; legacy3 stamps
                # level-relative ms. Consumers must not have to guess.
                "clock": "epoch" if etype.startswith("LIVE_") else "level",
                "source": batch.source,
                "received_at": now,
                **ev.fields,
            }
            _events.append(record)
            _state.apply(record)  # fold into the current-state snapshot
            accepted += 1
    return {"status": "ok", "accepted": accepted, "last_seq": _seq}


@router.get("/feed")
async def feed(
    since: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    types: str | None = Query(
        None,
        description="Comma-separated event types to include; default = all "
                    "renderable types (high-volume LIVEX telemetry excluded).",
    ),
) -> dict[str, Any]:
    """Events with seq > since, oldest first — the NEWEST ``limit`` of them.

    Before 2026-08-18 this returned the OLDEST page after the cursor, so a
    cold page load replayed the oldest fifth of the ring (a quarter-hour-old
    revive) while the newest events fell outside the page — the live feed's
    "stuck on quiet, then bursts" symptom. A gap is detectable client-side:
    ``oldest_seq > since + 1`` means events between were skipped (resync
    roster/map from /state, the play-by-play in between is gone).
    Age retention keeps stale ring content out entirely.
    """
    if _UPSTREAM and _seq == 0:
        upstream = await _proxy("feed", {"since": since, "limit": limit,
                                         "types": types})
        if upstream is not None:
            return upstream
    wanted: frozenset[str] | None = None
    if types:
        wanted = frozenset(t.strip().upper() for t in types.split(",") if t.strip())
    fresh_after = time.time() - _FEED_RETENTION_SECONDS
    async with _lock:
        selected = [
            e for e in _events
            if e["seq"] > since
            and e["received_at"] >= fresh_after
            and (e["type"] in wanted if wanted is not None
                 else e["type"] not in _FEED_HIDDEN_TYPES)
        ]
        out = selected[-limit:]
        last_seq = _seq
    return {
        "status": "ok",
        "events": out,
        "oldest_seq": out[0]["seq"] if out else None,
        "last_seq": last_seq,
        "server_time": time.time(),
    }


@router.get("/state")
async def state() -> dict[str, Any]:
    """Authoritative current-state snapshot (roster by side, current/previous
    map, game state, timers, recent objectives). The client reads this on
    load so the page shows the real "right now" instead of replaying stale
    events from the ring."""
    if _UPSTREAM and _seq == 0:
        upstream = await _proxy("state")
        if upstream is not None:
            return upstream
    async with _lock:
        return _state.snapshot()


@router.get("/status")
async def status() -> dict[str, Any]:
    """Liveness for dashboards: how fresh is the newest event."""
    if _UPSTREAM and _seq == 0:
        upstream = await _proxy("status")
        if upstream is not None:
            return upstream
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
