"""Live current-state reducer (Live-view A0).

The event ring in routers/live.py is a play-by-play LOG. Driving the UI
straight off it makes stale events read as "live" (the page shows a kill
from ten minutes ago as if a match were on). The professional pattern for
live dashboards is snapshot + delta (event sourcing): the server folds the
event stream into an authoritative CURRENT-STATE snapshot, the client reads
that snapshot on load to render who/team/map/state instantly, and only then
tails the event log for the ticker.

This module is that reducer — pure, stdlib-only, no I/O. routers/live.py
holds one instance, calls ``apply()`` for every accepted event, and serves
``snapshot()`` at GET /api/live/state.

Design decisions:
- Roster keyed by engine slot; team 1=Axis, 2=Allies, 3=spectator. A
  DISCONNECT removes the slot, so the snapshot reflects CURRENT membership,
  never someone who already left — the root fix for the stale display.
- Timestamps are the ingest wall-clock (event ``received_at``): connected_at
  (first seen), team_since (last side change), so the UI can show "on the
  server 23 min / on this side 8 min".
- game_state is a small state machine over ROUND_START / ROUND_END / MAP /
  INIT_GAME / EXIT. It is advisory; staleness (no events for a while) makes
  the snapshot report is_live=False so an old state never masquerades as now.
"""

from __future__ import annotations

import time
from typing import Any

# A session is considered live only if an event landed within this window;
# past that the snapshot reads idle so a stale ring can't look "on".
_LIVE_WINDOW_SECONDS = 90
# How long a recent objective action stays surfaced in the snapshot.
_OBJECTIVE_WINDOW_SECONDS = 20


class LiveStateReducer:
    """Folds the live event stream into a current-state snapshot."""

    def __init__(self) -> None:
        # slot -> {name, team, connected_at, team_since}
        self._roster: dict[int, dict[str, Any]] = {}
        self._current_map: str | None = None
        self._previous_map: str | None = None
        self._game_state: str = "unknown"  # warmup|live|between|mapchange|unknown
        self._round_number: int | None = None
        self._round_started_at: float | None = None
        self._last_event_at: float | None = None
        # recent objective actions (steal/return/plant/defuse), newest last
        self._objectives: list[dict[str, Any]] = []

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _slot(ev: dict[str, Any], key: str = "slot") -> int | None:
        v = ev.get(key)
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.lstrip("-").isdigit():
            return int(v)
        return None

    # -- reduce -------------------------------------------------------------
    def apply(self, ev: dict[str, Any]) -> None:
        """Fold one accepted event into the state."""
        etype = ev.get("type")
        at = ev.get("received_at") or time.time()
        self._last_event_at = at

        if etype == "TEAM_CHANGE":
            slot = self._slot(ev)
            if slot is None:
                return
            team = ev.get("team")
            entry = self._roster.get(slot)
            if entry is None:
                entry = {"name": ev.get("name") or f"slot {slot}",
                         "team": team, "connected_at": at, "team_since": at}
                self._roster[slot] = entry
            else:
                if ev.get("name"):
                    entry["name"] = ev["name"]
                if team != entry.get("team"):
                    entry["team"] = team
                    entry["team_since"] = at

        elif etype in ("CONNECT", "BEGIN"):
            slot = self._slot(ev)
            if slot is not None and slot not in self._roster:
                self._roster[slot] = {"name": f"slot {slot}", "team": None,
                                      "connected_at": at, "team_since": at}

        elif etype == "DISCONNECT":
            slot = self._slot(ev)
            if slot is not None:
                self._roster.pop(slot, None)

        elif etype in ("MAP", "LIVE_MAP"):
            new_map = ev.get("map_name")
            if new_map and new_map != self._current_map:
                self._previous_map = self._current_map
                self._current_map = new_map
                self._game_state = "mapchange"
                self._round_number = None
                self._objectives = []

        elif etype == "INIT_GAME":
            if self._game_state != "live":
                self._game_state = "warmup"

        elif etype == "ROUND_START":
            self._game_state = "live"
            self._round_started_at = at
            self._round_number = (self._round_number or 0) + 1

        elif etype in ("ROUND_END", "STATS_SAVED"):
            if self._game_state == "live":
                self._game_state = "between"

        elif etype == "EXIT":
            self._game_state = "between"

        elif etype == "POPUP":
            verb = ev.get("verb")
            if verb in ("stole", "returned", "planted", "defused"):
                self._objectives.append({
                    "team": ev.get("team"), "verb": verb,
                    "objective": ev.get("objective"), "at": at,
                })
                self._objectives = self._objectives[-10:]

    # -- snapshot -----------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        now = time.time()
        is_live = (self._last_event_at is not None
                   and (now - self._last_event_at) <= _LIVE_WINDOW_SECONDS)

        axis, allies, spectators = [], [], []
        session_start: float | None = None
        for slot, e in sorted(self._roster.items()):
            session_start = (e["connected_at"] if session_start is None
                             else min(session_start, e["connected_at"]))
            member = {
                "slot": slot,
                "name": e["name"],
                "on_server_seconds": int(now - e["connected_at"]),
                "on_side_seconds": int(now - e["team_since"]),
            }
            if e.get("team") == 1:
                axis.append(member)
            elif e.get("team") == 2:
                allies.append(member)
            else:
                spectators.append(member)

        recent_objectives = [
            o for o in self._objectives
            if (now - o["at"]) <= _OBJECTIVE_WINDOW_SECONDS
        ] if is_live else []

        round_elapsed = (int(now - self._round_started_at)
                         if (is_live and self._game_state == "live"
                             and self._round_started_at) else None)

        return {
            "status": "ok",
            "is_live": is_live,
            "game_state": self._game_state if is_live else "idle",
            "current_map": self._current_map,
            "previous_map": self._previous_map,
            "round_number": self._round_number if is_live else None,
            "round_elapsed_seconds": round_elapsed,
            "roster": {
                "axis": axis,
                "allies": allies,
                "spectators": spectators,
                "player_count": len(axis) + len(allies),
                "has_bots": any(
                    str(m["name"]).startswith("[BOT]")
                    for m in (axis + allies + spectators)
                ),
            },
            "session_start_seconds": (int(now - session_start)
                                      if (is_live and session_start) else None),
            "recent_objectives": recent_objectives,
            "last_event_age_seconds": (int(now - self._last_event_at)
                                       if self._last_event_at else None),
            "server_time": now,
        }
