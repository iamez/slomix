"""StorytellingService mixin: loaders methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.

Canonical-key contract (codex follow-up audit findings #10/#11): every
context dict here is keyed by the round it belongs to via `round_ctx_key`,
whose ordering is `(round_start_unix, map_name, round_number)` — the same
repo-wide canonical round key ois.py / ssr use. `round_start_unix` alone is
NOT unique repo-wide (two rounds on different maps can share a start second
across sessions), so `map_name` is part of every key. `_score_kill` in kis.py
looks these up through the SAME helper, so the build side and the lookup side
can never drift apart. Guid-prefixed / kill_time-suffixed keys compose the
helper: `(guid, *round_ctx_key(...))`, `(*..., kill_time)`.
"""
from __future__ import annotations

from .base import (
    date,
    round_ctx_key,
)


class _LoadersMixin:
    """Loaders methods for StorytellingService."""

    async def _load_carrier_kills(self, session_date):
        """Carrier kills indexed by (killer_guid, round_start_unix, map_name, round_number) → [kill_time]."""
        rows = await self.db.fetch_all(
            "SELECT killer_guid, round_start_unix, round_number, kill_time, map_name "
            "FROM proximity_carrier_kill WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], *round_ctx_key(r[1], r[4], r[2]))
            result.setdefault(key, []).append(r[3])
        return result

    async def _load_carrier_returns(self, session_date):
        """Carrier returns indexed by (round_start_unix, map_name, round_number) → [return_time]."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, return_time, map_name "
            "FROM proximity_carrier_return WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = round_ctx_key(r[0], r[3], r[1])
            result.setdefault(key, []).append(r[2])
        return result

    async def _load_pushes(self, session_date):
        """Push events indexed by (round_start_unix, map_name, round_number).

        Each entry is (start_time, end_time, push_quality, toward_objective).
        """
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, start_time, end_time, "
            "push_quality, toward_objective, map_name "
            "FROM proximity_team_push WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = round_ctx_key(r[0], r[6], r[1])
            result.setdefault(key, []).append(
                (r[2], r[3], float(r[4] or 0), r[5] or ''))
        return result

    async def _load_crossfires(self, session_date):
        """Executed crossfire events indexed by (round_start_unix, map_name, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, event_time, map_name "
            "FROM proximity_crossfire_opportunity WHERE was_executed = true AND session_date = $1",
            (session_date,))
        result = {}
        for r in (rows or []):
            key = round_ctx_key(r[0], r[3], r[1])
            result.setdefault(key, []).append(r[2])
        return result

    async def _load_spawn_timings(self, session_date):
        """Spawn timings indexed by (round_start_unix, map_name, round_number).

        Each entry is a tuple of (guid, kill_time, score, victim_reinf).
        `enemy_spawn_interval` was stored at index 3 through KIS v2 where
        reinf_mult was a ratio `victim_reinf / spawn_interval`; KIS v3
        (graduated tiers by absolute seconds) no longer needs it, so it
        is dropped from the tuple and from the SELECT list.
        """
        rows = await self.db.fetch_all(
            "SELECT killer_guid, kill_time, spawn_timing_score, round_start_unix, round_number, "
            "victim_reinf, map_name "
            "FROM proximity_spawn_timing WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = round_ctx_key(r[3], r[6], r[4])
            # A stored spawn_timing_score of 0 is the Lua `interval <= 0`
            # sentinel (spawn interval undetermined → score 0,0). The old
            # `float(r[2] or 0.5)` promoted every such 0 to the 0.5
            # neutral default, so a kill with an unknown-interval spawn row
            # got a 1.5x spawn bonus while an identical kill with NO spawn
            # row got 1.0x — inconsistent. Now 0 is kept, so unknown-timing
            # kills score the same 1.0x as no-data kills; only a genuine
            # NULL (which the table never stores today — all 0s are real
            # sentinels) would fall back to 0.5 (Codex SS-E). NB: every
            # historical 0 is an orphaned 2026-03-17..19 row matching no
            # kill_outcome, so this changes 0 currently-displayed kills;
            # it fixes the semantics for any future unknown-interval data.
            # kis_shadow.py's `st` CTE mirrors this exact rule.
            score = 0.5 if r[2] is None else float(r[2])
            result.setdefault(key, []).append(
                (r[0], r[1], score, float(r[5] or 0)))
        return result

    async def _load_victim_classes(self, session_date):
        """Victim classes from reaction_metric, indexed by (target_guid, round_start_unix, map_name, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT target_guid, round_start_unix, round_number, target_class, map_name "
            "FROM proximity_reaction_metric WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], *round_ctx_key(r[1], r[4], r[2]))
            if key not in result:
                result[key] = r[3] or ''
        return result

    async def _load_combat_positions(self, sd: date) -> dict:
        """Combat positions indexed by (killer_guid, round_start_unix, map_name, round_number, kill_time)."""
        rows = await self.db.fetch_all(
            "SELECT attacker_guid, round_start_unix, round_number, event_time, "
            "killer_health, axis_alive, allies_alive, attacker_team, map_name, "
            "victim_x, victim_y, victim_z "
            "FROM proximity_combat_position "
            "WHERE session_date = $1 AND event_type = 'kill'",
            (sd,))
        result = {}
        for r in (rows or []):
            # (killer_guid, round_start_unix, map_name, round_number, event_time)
            key = (r[0], *round_ctx_key(r[1], r[8], r[2]), r[3])
            result[key] = {
                'killer_health': r[4] or 0,
                'axis_alive': r[5] or 0,
                'allies_alive': r[6] or 0,
                'attacker_team': r[7] or '',
                # victim death position (for is_objective_area, KIS v4)
                'victim_x': r[9],
                'victim_y': r[10],
                'victim_z': r[11],
            }
        return result
