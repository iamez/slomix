"""
Smart Storytelling Stats — Kill Impact Score (KIS) Engine

Computes contextual kill impact scores by combining:
- proximity_kill_outcome (what happened after each kill)
- proximity_carrier_kill (carrier interceptions)
- proximity_team_push (team push context)
- proximity_crossfire_opportunity (coordinated attacks)
- proximity_spawn_timing (spawn wave denial)
- proximity_reaction_metric (target class info)
"""

import logging
from datetime import date, datetime
from typing import Optional, Union
from website.backend.logging_config import get_app_logger

logger = get_app_logger("storytelling")

# Competitive ET:Legacy multipliers (calibrated for pro play)
CARRIER_KILL_MULTIPLIER = 3.0       # Killed flag/doc carrier
CARRIER_CHAIN_MULTIPLIER = 5.0      # Carrier kill + teammate returned within 10s
PUSH_MULTIPLIER = 2.0               # Kill during coordinated team push
CROSSFIRE_MULTIPLIER = 1.5          # Kill as part of crossfire setup
SPAWN_TIMING_BONUS = 1.0            # Added to 1.0 (so range 1.0-2.0 based on score 0-1)
OUTCOME_GIBBED = 1.3                # Kill was permanent (gibbed, no revive possible)
OUTCOME_REVIVED = 0.5               # Kill was undone by medic
OUTCOME_TAPPED = 1.0                # Normal (tapped out)
CLASS_WEIGHTS = {
    "MEDIC": 1.5,       # Removing healer = devastating
    "ENGINEER": 1.3,    # Removing objective player = opens path
    "FIELDOPS": 1.1,    # Removing supplier
    "SOLDIER": 1.0,     # Baseline
    "COVERTOPS": 1.0,   # Context-dependent
}
DISTANCE_LONG_RANGE = 1.2           # Kill at >800u (sniper pick)
DISTANCE_NORMAL = 1.0               # 100-800u
DISTANCE_MELEE = 0.9                # <100u (knife/close)


def _to_date(val: Union[str, date]) -> date:
    """Convert string to datetime.date for asyncpg DATE params."""
    if isinstance(val, date):
        return val
    return datetime.strptime(val, "%Y-%m-%d").date()


class StorytellingService:
    def __init__(self, db):
        self.db = db

    async def compute_session_kis(self, session_date: Union[str, date], force: bool = False) -> dict:
        """Compute KIS for all kills in a session. Returns summary stats."""
        sd = _to_date(session_date)

        # Check if already computed (unless force)
        if not force:
            existing = await self.db.fetch_one(
                "SELECT COUNT(*) FROM storytelling_kill_impact WHERE session_date = $1",
                (sd,)
            )
            if existing and existing[0] > 0:
                return {"status": "cached", "kills_scored": existing[0]}

        # 1. Get all kill outcomes for the session
        kills = await self.db.fetch_all("""
            SELECT ko.id, ko.session_date, ko.round_number, ko.round_start_unix,
                   ko.map_name, ko.killer_guid, ko.killer_name,
                   ko.victim_guid, ko.victim_name,
                   ko.outcome, ko.kill_time
            FROM proximity_kill_outcome ko
            WHERE ko.session_date = $1
            ORDER BY ko.round_start_unix, ko.kill_time
        """, (sd,))

        if not kills:
            return {"status": "no_data", "kills_scored": 0}

        # 2. Pre-load context data for the session
        carrier_kills = await self._load_carrier_kills(sd)
        carrier_returns = await self._load_carrier_returns(sd)
        pushes = await self._load_pushes(sd)
        crossfires = await self._load_crossfires(sd)
        spawn_timings = await self._load_spawn_timings(sd)
        victim_classes = await self._load_victim_classes(sd)

        # 3. Score each kill
        scored = []
        for kill in kills:
            impact = self._score_kill(kill, carrier_kills, carrier_returns,
                                      pushes, crossfires, spawn_timings, victim_classes)
            scored.append(impact)

        # 4. Store in DB (delete old, insert new)
        await self.db.execute(
            "DELETE FROM storytelling_kill_impact WHERE session_date = $1", (sd,)
        )

        for s in scored:
            await self.db.execute("""
                INSERT INTO storytelling_kill_impact
                (kill_outcome_id, session_date, round_number, round_start_unix, map_name,
                 killer_guid, killer_name, victim_guid, victim_name,
                 base_impact, carrier_multiplier, push_multiplier, crossfire_multiplier,
                 spawn_multiplier, outcome_multiplier, class_multiplier, distance_multiplier,
                 total_impact, is_carrier_kill, is_during_push, is_crossfire, is_objective_area,
                 kill_time_ms)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
            """, (
                s['kill_outcome_id'], s['session_date'], s['round_number'], s['round_start_unix'],
                s['map_name'], s['killer_guid'], s['killer_name'], s['victim_guid'], s['victim_name'],
                s['base_impact'], s['carrier_multiplier'], s['push_multiplier'], s['crossfire_multiplier'],
                s['spawn_multiplier'], s['outcome_multiplier'], s['class_multiplier'], s['distance_multiplier'],
                s['total_impact'], s['is_carrier_kill'], s['is_during_push'], s['is_crossfire'],
                s['is_objective_area'], s['kill_time_ms']
            ))

        logger.info(f"KIS computed for {session_date}: {len(scored)} kills scored")
        return {"status": "computed", "kills_scored": len(scored)}

    def _score_kill(self, kill, carrier_kills, carrier_returns, pushes, crossfires,
                    spawn_timings, victim_classes):
        """Score a single kill with all context multipliers."""
        ko_id = kill[0]
        session_date = kill[1]
        round_number = kill[2]
        round_start_unix = kill[3]
        map_name = kill[4]
        killer_guid = kill[5]
        killer_name = kill[6] or ''
        victim_guid = kill[7]
        victim_name = kill[8] or ''
        outcome = kill[9] or 'tapped_out'
        kill_time = kill[10] or 0

        round_key = (round_start_unix, round_number)

        # Carrier kill check
        carrier_mult = 1.0
        is_carrier = False
        ck_key = (killer_guid, round_start_unix, round_number)
        if ck_key in carrier_kills:
            ck_time = carrier_kills[ck_key]
            cr_key = (round_start_unix, round_number)
            if cr_key in carrier_returns:
                chain = False
                for ret in carrier_returns[cr_key]:
                    if 0 < (ret - ck_time) <= 10000:  # returned within 10s
                        carrier_mult = CARRIER_CHAIN_MULTIPLIER
                        chain = True
                        break
                if not chain:
                    carrier_mult = CARRIER_KILL_MULTIPLIER
            else:
                carrier_mult = CARRIER_KILL_MULTIPLIER
            is_carrier = True

        # Push context (kill within 5s of push start_time)
        push_mult = 1.0
        is_push = False
        if round_key in pushes:
            for push_start, push_end in pushes[round_key]:
                if push_start <= kill_time <= push_end + 5000:
                    push_mult = PUSH_MULTIPLIER
                    is_push = True
                    break

        # Crossfire context (kill within 3s of crossfire event)
        cf_mult = 1.0
        is_cf = False
        if round_key in crossfires:
            for cf_time in crossfires[round_key]:
                if abs(kill_time - cf_time) <= 3000:
                    cf_mult = CROSSFIRE_MULTIPLIER
                    is_cf = True
                    break

        # Spawn timing bonus (1.0 + score, range 1.0-2.0)
        spawn_mult = 1.0
        if round_key in spawn_timings:
            best_score = 0.0
            for st_guid, st_time, st_score in spawn_timings[round_key]:
                if st_guid == killer_guid and abs(st_time - kill_time) <= 2000:
                    best_score = st_score
                    break
            spawn_mult = 1.0 + best_score

        # Kill outcome multiplier
        outcome_mult = 1.0
        if outcome == 'gibbed':
            outcome_mult = OUTCOME_GIBBED
        elif outcome == 'revived':
            outcome_mult = OUTCOME_REVIVED

        # Target class multiplier (from reaction_metric)
        victim_class = victim_classes.get((victim_guid, round_start_unix, round_number), '').upper()
        class_mult = CLASS_WEIGHTS.get(victim_class, 1.0)

        # Distance (not available per-kill yet, placeholder)
        dist_mult = DISTANCE_NORMAL

        # Total impact = product of all multipliers
        total = (1.0 * carrier_mult * push_mult * cf_mult
                 * spawn_mult * outcome_mult * class_mult * dist_mult)

        return {
            'kill_outcome_id': ko_id,
            'session_date': session_date,
            'round_number': round_number,
            'round_start_unix': round_start_unix,
            'map_name': map_name,
            'killer_guid': killer_guid,
            'killer_name': killer_name,
            'victim_guid': victim_guid,
            'victim_name': victim_name,
            'base_impact': 1.0,
            'carrier_multiplier': carrier_mult,
            'push_multiplier': push_mult,
            'crossfire_multiplier': cf_mult,
            'spawn_multiplier': round(spawn_mult, 3),
            'outcome_multiplier': outcome_mult,
            'class_multiplier': class_mult,
            'distance_multiplier': dist_mult,
            'total_impact': round(total, 2),
            'is_carrier_kill': is_carrier,
            'is_during_push': is_push,
            'is_crossfire': is_cf,
            'is_objective_area': False,
            'kill_time_ms': kill_time,
        }

    async def _load_carrier_kills(self, session_date):
        """Load carrier kills indexed by (killer_guid, round_start_unix, round_number)."""
        rows = await self.db.fetch_all(
            "SELECT killer_guid, round_start_unix, round_number, kill_time "
            "FROM proximity_carrier_kill WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            result[(r[0], r[1], r[2])] = r[3]
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
        """Load push events indexed by (round_start_unix, round_number) as (start_time, end_time) pairs."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, start_time, end_time "
            "FROM proximity_team_push WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[0], r[1])
            result.setdefault(key, []).append((r[2], r[3]))
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
        """Load spawn timings indexed by (round_start_unix, round_number) as (guid, kill_time, score) tuples."""
        rows = await self.db.fetch_all(
            "SELECT killer_guid, kill_time, spawn_timing_score, round_start_unix, round_number "
            "FROM proximity_spawn_timing WHERE session_date = $1", (session_date,))
        result = {}
        for r in (rows or []):
            key = (r[3], r[4])
            result.setdefault(key, []).append((r[0], r[1], float(r[2] or 0.5)))
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

    async def get_kis_leaderboard(self, session_date: Union[str, date], limit: int = 20) -> list:
        """Get KIS leaderboard for a session."""
        sd = _to_date(session_date)
        rows = await self.db.fetch_all("""
            SELECT killer_guid, MAX(killer_name) as name,
                   ROUND(SUM(total_impact)::numeric, 1) as total_kis,
                   COUNT(*) as kills,
                   SUM(CASE WHEN is_carrier_kill THEN 1 ELSE 0 END) as carrier_kills,
                   SUM(CASE WHEN is_during_push THEN 1 ELSE 0 END) as push_kills,
                   SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) as crossfire_kills,
                   ROUND(AVG(total_impact)::numeric, 2) as avg_impact
            FROM storytelling_kill_impact
            WHERE session_date = $1
            GROUP BY killer_guid
            ORDER BY SUM(total_impact) DESC
            LIMIT $2
        """, (sd, limit))

        return [
            {
                "guid": r[0], "name": r[1] or r[0][:8],
                "total_kis": float(r[2] or 0), "kills": int(r[3] or 0),
                "carrier_kills": int(r[4] or 0), "push_kills": int(r[5] or 0),
                "crossfire_kills": int(r[6] or 0), "avg_impact": float(r[7] or 0),
            }
            for r in (rows or [])
        ]
