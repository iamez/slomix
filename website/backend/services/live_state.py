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
# 180 s (was 90): tailer delivery gaps of a minute-plus are a measured
# reality (Cloudflare 403/530 windows, 2026-08-18) and every crossing of
# this edge used to blank the whole card — leave slowly, enter instantly.
_LIVE_WINDOW_SECONDS = 180
# The roster outlives is_live: through a delivery gap the line-up is still
# the best truth we have, so keep showing it (with roster_age_seconds so the
# UI can dim it) until the gap is long enough to be a session boundary.
_ROSTER_LINGER_SECONDS = 600
# A map change that reverts to the previous map this soon after the last
# change is a dueling-sources ping-pong (legacy3 MAP vs LIVEX LIVE_MAP), not
# a real remap — ignore it.
_MAP_FLIPBACK_SECONDS = 60
# How long a recent objective action stays surfaced in the snapshot.
_OBJECTIVE_WINDOW_SECONDS = 20
# A gap this long between events is a session boundary (server down + restart),
# not a quiet stretch of one match — the first event after it resets the roster.
# Deliberately much longer than _LIVE_WINDOW_SECONDS so a sparse warmup can't
# wipe a live line-up.
_IDLE_RESET_SECONDS = 600


def _is_named(name: Any) -> bool:
    """True for a real player name — not a bare "slot N" placeholder (the reducer
    invents that before userinfo arrives) and not empty."""
    return bool(name) and not str(name).startswith("slot ")


class LiveStateReducer:
    """Folds the live event stream into a current-state snapshot."""

    def __init__(self) -> None:
        # slot -> {name, team, connected_at, team_since}
        self._roster: dict[int, dict[str, Any]] = {}
        self._current_map: str | None = None
        self._previous_map: str | None = None
        self._map_changed_at: float | None = None
        # ⭐ CHANGED and ASSERTED are different questions. `_map_changed_at`
        # only moves when the map is a NEW one, so a map confirmed by events
        # for twenty minutes would report a twenty-minute-old "change". This
        # moves on every map event, including one naming the map we already
        # hold, because that is a fresh assertion that it is still the map.
        self._map_asserted_at: float | None = None
        self._game_state: str = "unknown"  # warmup|live|between|mapchange|unknown
        self._round_number: int | None = None
        self._round_started_at: float | None = None
        self._last_event_at: float | None = None
        # recent objective actions (steal/return/plant/defuse), newest last
        self._objectives: list[dict[str, Any]] = []
        # Recent roster changes (joined / left / switched side) — the "menjave"
        # (substitutions) a spectator wants to see, newest last, capped small.
        self._roster_changes: list[dict[str, Any]] = []
        # Live per-round tallies (Val A "Live Ladder"): slot -> kills/deaths/
        # damage sums from LIVE_AGGREGATE deltas (10-s cadence, reset each
        # flush at the source) + an instant alive flag from LIVE_KILL (dead)
        # and LIVE_MOVEMENT (moving = alive). Reset on round/map boundaries.
        self._live_stats: dict[int, dict[str, Any]] = {}

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

    def _name_for_slot(self, slot: int | None) -> str | None:
        """Resolve an engine slot to the current roster name (None if unknown —
        e.g. the objective event arrived before the player's CONNECT)."""
        if slot is None:
            return None
        entry = self._roster.get(slot)
        return entry["name"] if entry else None

    def _live_stat(self, slot: int) -> dict[str, Any]:
        return self._live_stats.setdefault(
            slot, {"kills": 0, "deaths": 0,
                   "damage_given": 0, "damage_received": 0, "alive": True})

    def _push_objective(self, entry: dict[str, Any]) -> None:
        """Append a recent-objective action, capped at the last 10."""
        self._objectives.append(entry)
        self._objectives = self._objectives[-10:]

    @staticmethod
    def _side(team: Any) -> str | None:
        """Engine team int → side label (1 Axis, 2 Allies, else spectators)."""
        if team == 1:
            return "Axis"
        if team == 2:
            return "Allies"
        return None

    def _record_change(self, name: str, action: str, team: Any, at: float) -> None:
        """Log one roster change (joined / left / switched), capped at the last 12."""
        self._roster_changes.append({"name": name, "action": action,
                                     "side": self._side(team), "at": at})
        self._roster_changes = self._roster_changes[-12:]

    # -- reduce -------------------------------------------------------------
    def apply(self, ev: dict[str, Any]) -> None:
        """Fold one accepted event into the state."""
        etype = ev.get("type")
        at = ev.get("received_at") or time.time()

        # A fresh event after a long quiet gap is a new session: the previous
        # roster is stale (a server that went away sends no DISCONNECTs). Reset
        # here too, not just in the snapshot — otherwise a reused slot's
        # CONNECT/BEGIN would be ignored (slot still present) and the old
        # player/team/timestamps would reappear once is_live flips true again.
        if (self._last_event_at is not None
                and (at - self._last_event_at) > _IDLE_RESET_SECONDS):
            self._roster.clear()
            self._objectives.clear()
            self._roster_changes.clear()
            self._live_stats.clear()
            self._round_number = None
            self._round_started_at = None
            # ⛔ THE MAP AND THE GAME STATE SURVIVED THIS RESET, and that made
            # a stale map look brand new. After a session gap the first event
            # is usually a CONNECT, not a MAP: `is_live` flips back to true,
            # `last_event_age_seconds` reads 1, and the snapshot presented the
            # PREVIOUS session's map with no field a client could use to doubt
            # it. Reproduced: 5,000 s of silence + one CONNECT gave
            # `is_live=True, current_map='supply', game_state='mapchange'`
            # (Codex on PR #806, via Fable).
            #
            # ⭐ The map is NOT cleared. A server that restarts usually comes
            # back on the same map, and blanking it would trade a stale answer
            # for no answer — this module's rule is to keep the value and
            # publish its age. Clearing the ASSERTION is what makes it stale.
            self._map_asserted_at = None
            self._game_state = "unknown"

        self._last_event_at = at

        if etype == "TEAM_CHANGE":
            slot = self._slot(ev)
            if slot is None:
                return
            team = ev.get("team")
            entry = self._roster.get(slot)
            if entry is None:
                name = ev.get("name") or f"slot {slot}"
                entry = {"name": name, "team": team, "connected_at": at, "team_since": at}
                self._roster[slot] = entry
                # First time this slot resolves to a real side = a join. Only log
                # a named player: a nameless TEAM_CHANGE (empty userinfo) would
                # otherwise surface "slot 7 joined Axis".
                if self._side(team) and _is_named(name):
                    self._record_change(name, "joined", team, at)
            else:
                if ev.get("name"):
                    entry["name"] = ev["name"]
                if team != entry.get("team"):
                    was_side = self._side(entry.get("team"))
                    entry["team"] = team
                    entry["team_since"] = at
                    # A move onto a real side is a switch/join; leaving to spec is
                    # not a "substitution" worth a line. Named players only.
                    if self._side(team) and _is_named(entry["name"]):
                        self._record_change(entry["name"],
                                            "switched" if was_side else "joined", team, at)

        elif etype in ("CONNECT", "BEGIN"):
            slot = self._slot(ev)
            if slot is not None and slot not in self._roster:
                self._roster[slot] = {"name": f"slot {slot}", "team": None,
                                      "connected_at": at, "team_since": at}

        elif etype == "DISCONNECT":
            slot = self._slot(ev)
            if slot is not None:
                entry = self._roster.pop(slot, None)
                # Only log a departure for a named player who was on a side —
                # a bare CONNECT slot that never picked a team isn't a "left".
                if entry and self._side(entry.get("team")) and _is_named(entry.get("name")):
                    self._record_change(entry["name"], "left", entry.get("team"), at)

        elif etype in ("MAP", "LIVE_MAP"):
            new_map = (ev.get("map_name") or "").strip()
            if new_map:
                # Before the change check: an event naming the map we already
                # hold changes nothing and CONFIRMS everything.
                self._map_asserted_at = at
            if new_map and new_map != self._current_map:
                # Anti ping-pong: two sources report the map (legacy3 `MAP`,
                # LIVEX `LIVE_MAP`). A "change" straight back to the previous
                # map moments after the last change is the lagging source
                # re-asserting stale truth — each hop used to wipe
                # round_number and objectives (2026-08-18 flapping).
                if (new_map == self._previous_map
                        and self._map_changed_at is not None
                        and (at - self._map_changed_at) < _MAP_FLIPBACK_SECONDS):
                    return
                self._previous_map = self._current_map
                self._current_map = new_map
                self._map_changed_at = at
                self._map_asserted_at = at
                self._game_state = "mapchange"
                self._round_number = None
                self._objectives = []
                self._live_stats.clear()

        elif etype == "INIT_GAME":
            if self._game_state != "live":
                self._game_state = "warmup"

        elif etype == "ROUND_START":
            self._game_state = "live"
            self._round_started_at = at
            self._live_stats.clear()  # the ladder is per-round, like HLTV's
            # Stopwatch has exactly R1/R2. A third ROUND_START without a MAP
            # in between means the MAP event was lost (dropped batch) — treat
            # it as a fresh map's R1 instead of counting "R5" forever.
            nxt = (self._round_number or 0) + 1
            self._round_number = 1 if nxt > 2 else nxt

        elif etype in ("ROUND_END", "STATS_SAVED"):
            if self._game_state == "live":
                self._game_state = "between"

        elif etype == "EXIT":
            self._game_state = "between"

        elif etype == "POPUP":
            verb = ev.get("verb")
            if verb in ("stole", "returned", "planted", "defused"):
                # POPUP carries the team but no slot, so it stays team-level
                # (player=None). FLAG_PICKUP/DYNAMITE below name the actor.
                self._push_objective({
                    "type": "popup", "team": ev.get("team"), "verb": verb,
                    "player": None, "objective": ev.get("objective"), "at": at,
                })

        elif etype == "FLAG_PICKUP":
            actor = self._name_for_slot(self._slot(ev))
            self._push_objective({
                "type": "flag", "team": None, "verb": "grabbed",
                "player": actor, "objective": ev.get("flag"), "at": at,
            })

        elif etype == "LIVE_AGGREGATE":
            slot = self._slot(ev)
            if slot is not None:
                st = self._live_stat(slot)
                # Source flushes-and-resets every ~10 s, so these are DELTAS.
                st["kills"] += int(ev.get("kills") or 0)
                st["deaths"] += int(ev.get("deaths") or 0)
                st["damage_given"] += int(ev.get("damage_given") or 0)
                st["damage_received"] += int(ev.get("damage_received") or 0)

        elif etype == "LIVE_KILL":
            victim = self._slot(ev, "victim_slot")
            if victim is not None:
                self._live_stat(victim)["alive"] = False

        elif etype == "LIVE_MOVEMENT":
            for entry in ev.get("players") or []:
                slot = entry.get("slot") if isinstance(entry, dict) else None
                if isinstance(slot, int):
                    # A moving player is alive (corpses don't emit positions).
                    self._live_stat(slot)["alive"] = True

        elif etype == "DYNAMITE":
            actor = self._name_for_slot(self._slot(ev))
            self._push_objective({
                "type": "dynamite", "team": None,
                "verb": ev.get("action"),  # plant | defuse
                "player": actor, "objective": ev.get("objective"), "at": at,
            })

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
            live = self._live_stats.get(slot)
            if live is not None:
                elapsed = (now - self._round_started_at
                           if self._round_started_at else None)
                member["live"] = {
                    "kills": live["kills"],
                    "deaths": live["deaths"],
                    "damage": live["damage_given"],
                    "dpm": (round(live["damage_given"] * 60 / elapsed)
                            if elapsed and elapsed >= 30 else None),
                    "alive": live["alive"],
                }
            if e.get("team") == 1:
                axis.append(member)
            elif e.get("team") == 2:
                allies.append(member)
            else:
                spectators.append(member)

        # The roster used to be blanked the moment is_live flipped false,
        # which made the card oscillate full↔empty across every tailer
        # delivery gap. Now it LINGERS (with roster_age_seconds so the UI
        # can dim it) and only empties once the gap is long enough to be a
        # session boundary — at which point a server restart without
        # DISCONNECTs can no longer freeze a dead line-up on screen either.
        event_age = (now - self._last_event_at) if self._last_event_at else None
        roster_stale = event_age is None or event_age > _ROSTER_LINGER_SECONDS
        if roster_stale:
            axis, allies, spectators = [], [], []
            session_start = None

        recent_objectives = [
            o for o in self._objectives
            if (now - o["at"]) <= _OBJECTIVE_WINDOW_SECONDS
        ] if is_live else []

        recent_roster_changes = [
            {"name": c["name"], "action": c["action"], "side": c["side"],
             "age_seconds": int(now - c["at"])}
            for c in self._roster_changes
            if (now - c["at"]) <= _OBJECTIVE_WINDOW_SECONDS
        ] if is_live else []

        round_elapsed = (int(now - self._round_started_at)
                         if (is_live and self._game_state == "live"
                             and self._round_started_at) else None)

        return {
            "status": "ok",
            "is_live": is_live,
            "game_state": self._game_state if is_live else "idle",
            "current_map": self._current_map,
            # ⭐ The map's own evidence, so a client can qualify it the way it
            # already qualifies the roster. `map_confirmed` is false when the
            # map has not been asserted by an event since the last session
            # boundary — the case where `is_live` is true, the event age is
            # seconds, and the map is still the previous session's.
            "map_confirmed": self._map_asserted_at is not None,
            "map_age_seconds": (int(now - self._map_asserted_at)
                                if self._map_asserted_at is not None else None),
            "previous_map": self._previous_map,
            "round_number": self._round_number if is_live else None,
            "round_elapsed_seconds": round_elapsed,
            "roster": {
                "axis": axis,
                "allies": allies,
                "spectators": spectators,
                "player_count": len(axis) + len(allies),
                # Age of the roster's supporting evidence — 0-ish while events
                # flow, grows through a delivery gap so the UI can dim the
                # line-up instead of flapping it away.
                "roster_age_seconds": (int(event_age)
                                       if (event_age is not None
                                           and not roster_stale) else None),
                "has_bots": any(
                    str(m["name"]).startswith("[BOT]")
                    for m in (axis + allies + spectators)
                ),
            },
            "session_start_seconds": (int(now - session_start)
                                      if session_start else None),
            "recent_objectives": recent_objectives,
            "recent_roster_changes": recent_roster_changes,
            "last_event_age_seconds": (int(now - self._last_event_at)
                                       if self._last_event_at else None),
            "server_time": now,
        }
