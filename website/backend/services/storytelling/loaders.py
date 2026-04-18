"""StorytellingService mixin: loaders methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    date,
)


class _LoadersMixin:
    """Loaders methods for StorytellingService."""

    async def _load_carrier_kills(self, session_date):
        """Load carrier kills indexed by (killer_guid, round_start_unix, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT killer_guid, round_start_unix, round_number, kill_time "
            "FROM proximity_carrier_kill WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            result.setdefault((r[0], r[1], r[2]), []).append(r[3])
        return result

    async def _load_carrier_returns(self, session_date):
        """Load carrier returns indexed by (round_start_unix, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, return_time "
            "FROM proximity_carrier_return WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1])
            result.setdefault(key, []).append(r[2])
        return result

    async def _load_pushes(self, session_date):
        """Load push events indexed by (round_start_unix, round_number).

        Each entry is (start_time, end_time, push_quality, toward_objective).
        """
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, start_time, end_time, "
            "push_quality, toward_objective "
            "FROM proximity_team_push WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1])
            result.setdefault(key, []).append(
                (r[2], r[3], float(r[4] or 0), r[5] or ''))
        return result

    async def _load_crossfires(self, session_date):
        """Load executed crossfire events indexed by (round_start_unix, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, event_time "
            "FROM proximity_crossfire_opportunity WHERE was_executed = true AND session_date = $1",
            (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1])
            result.setdefault(key, []).append(r[2])
        return result

    async def _load_spawn_timings(self, session_date):
        """Load spawn timings indexed by (round_start_unix, round_number).

        Each entry is a tuple of (guid, kill_time, score, enemy_spawn_interval, victim_reinf).
        """
        rows = await self.db.fetch_all(
            "SELECT killer_guid, kill_time, spawn_timing_score, round_start_unix, round_number, "
            "enemy_spawn_interval, victim_reinf "
            "FROM proximity_spawn_timing WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[3], r[4])
            result.setdefault(key, []).append(
                (r[0], r[1], float(r[2] or 0.5), r[5] or 0, float(r[6] or 0)))
        return result

    async def _load_victim_classes(self, session_date):
        """Load victim classes from reaction_metric, indexed by (target_guid, round_start_unix, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT target_guid, round_start_unix, round_number, target_class "
            "FROM proximity_reaction_metric WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1], r[2])
            if key not in result:
                result[key] = r[3] or ''
        return result

    async def _load_combat_positions(self, sd: date) -> dict:
        """Load combat position data indexed by (killer_guid, round_start_unix, round_number, kill_time)."""
        rows = await self.db.fetch_all(
            "SELECT attacker_guid, round_start_unix, round_number, event_time, "
            "killer_health, axis_alive, allies_alive, attacker_team "
            "FROM proximity_combat_position "
            "WHERE session_date = $1 AND event_type = 'kill'",
            (sd,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1], r[2], r[3])  # (killer_guid, round_start_unix, round_number, event_time)
            result[key] = {
                'killer_health': r[4] or 0,
                'axis_alive': r[5] or 0,
                'allies_alive': r[6] or 0,
                'attacker_team': r[7] or '',
            }
        return result

