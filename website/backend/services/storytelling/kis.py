"""StorytellingService mixin: kis methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    CARRIER_CHAIN_MULTIPLIER,
    CARRIER_KILL_MULTIPLIER,
    CARRIER_RETURN_WINDOW_MS,
    CLASS_WEIGHTS,
    CROSSFIRE_MULTIPLIER,
    CROSSFIRE_TIMING_WINDOW_MS,
    DISTANCE_NORMAL,
    LOW_HEALTH_MULTIPLIER,
    LOW_HEALTH_THRESHOLD,
    OUTCOME_GIBBED,
    OUTCOME_REVIVED,
    OUTNUMBERED_MULTIPLIER,
    PUSH_BUFFER_MS,
    PUSH_QUALITY_THRESHOLD,
    PUSH_TOWARD_EXCLUDE,
    REINF_PENALTY_THRESHOLD,
    SOLO_CLUTCH_MULTIPLIER,
    SOLO_CLUTCH_THRESHOLD,
    SPAWN_TIMING_WINDOW_MS,
    _compute_locks,
    _to_date,
    asyncio,
    date,
    logger,
)


class _KisMixin:
    """Kis methods for StorytellingService."""

    async def compute_session_kis(self, session_date: str | date, force: bool = False) -> dict:
        """Compute KIS for all kills in a session. Returns summary stats."""
        sd = _to_date(session_date)
        lock_key = str(sd)
        async with _compute_locks.get(lock_key):
            return await self._compute_session_kis_locked(sd, force)

    async def _compute_session_kis_locked(self, sd: date, force: bool) -> dict:
        """Inner compute logic — must be called while holding the session lock."""
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

        # 2. Pre-load context data for the session (parallel — independent queries)
        (
            carrier_kills,
            carrier_returns,
            pushes,
            crossfires,
            spawn_timings,
            victim_classes,
            combat_positions,
        ) = await asyncio.gather(
            self._load_carrier_kills(sd),
            self._load_carrier_returns(sd),
            self._load_pushes(sd),
            self._load_crossfires(sd),
            self._load_spawn_timings(sd),
            self._load_victim_classes(sd),
            self._load_combat_positions(sd),
        )

        # 3. Score each kill
        scored = []
        for kill in kills:
            impact = self._score_kill(kill, carrier_kills, carrier_returns,
                                      pushes, crossfires, spawn_timings, victim_classes,
                                      combat_positions)
            scored.append(impact)

        # 4. Store in DB (delete old, batch insert new)
        await self.db.execute(
            "DELETE FROM storytelling_kill_impact WHERE session_date = $1", (sd,)
        )

        if scored:
            batch = [
                (
                    s['kill_outcome_id'], s['session_date'], s['round_number'], s['round_start_unix'],
                    s['map_name'], s['killer_guid'], s['killer_name'], s['victim_guid'], s['victim_name'],
                    s['base_impact'], s['carrier_multiplier'], s['push_multiplier'], s['crossfire_multiplier'],
                    s['spawn_multiplier'], s['outcome_multiplier'], s['class_multiplier'], s['distance_multiplier'],
                    s['health_multiplier'], s['alive_multiplier'], s['reinf_multiplier'],
                    s['killer_health'], s['axis_alive'], s['allies_alive'], s['victim_reinf'],
                    s['total_impact'], s['is_carrier_kill'], s['is_during_push'], s['is_crossfire'],
                    s['is_objective_area'], s['kill_time_ms'],
                )
                for s in scored
            ]
            await self.db.executemany("""
                INSERT INTO storytelling_kill_impact
                (kill_outcome_id, session_date, round_number, round_start_unix, map_name,
                 killer_guid, killer_name, victim_guid, victim_name,
                 base_impact, carrier_multiplier, push_multiplier, crossfire_multiplier,
                 spawn_multiplier, outcome_multiplier, class_multiplier, distance_multiplier,
                 health_multiplier, alive_multiplier, reinf_multiplier,
                 killer_health, axis_alive, allies_alive, victim_reinf,
                 total_impact, is_carrier_kill, is_during_push, is_crossfire, is_objective_area,
                 kill_time_ms)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30)
            """, batch)

        logger.info("KIS computed for %s: %d kills scored", sd, len(scored))
        return {"status": "computed", "kills_scored": len(scored)}

    def _score_kill(self, kill, carrier_kills, carrier_returns, pushes, crossfires,
                    spawn_timings, victim_classes, combat_positions=None):
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
        if ck_key in carrier_kills and kill_time in carrier_kills[ck_key]:
            cr_key = (round_start_unix, round_number)
            if cr_key in carrier_returns:
                chain = False
                for ret in carrier_returns[cr_key]:
                    if 0 < (ret - kill_time) <= CARRIER_RETURN_WINDOW_MS:
                        carrier_mult = CARRIER_CHAIN_MULTIPLIER
                        chain = True
                        break
                if not chain:
                    carrier_mult = CARRIER_KILL_MULTIPLIER
            else:
                carrier_mult = CARRIER_KILL_MULTIPLIER
            is_carrier = True

        # Push context — quality-gated with tighter window
        push_mult = 1.0
        is_push = False
        if round_key in pushes:
            best_pq = 0.0
            for push_start, push_end, pq, toward_obj in pushes[round_key]:
                if push_start <= kill_time <= push_end + PUSH_BUFFER_MS:
                    if (pq >= PUSH_QUALITY_THRESHOLD
                            and toward_obj not in PUSH_TOWARD_EXCLUDE):
                        if pq > best_pq:
                            best_pq = pq
            if best_pq > 0:
                push_mult = 1.0 + min(best_pq * 0.5, 1.0)
                is_push = True

        # Crossfire context (kill within 3s of crossfire event)
        cf_mult = 1.0
        is_cf = False
        if round_key in crossfires:
            for cf_time in crossfires[round_key]:
                if abs(kill_time - cf_time) <= CROSSFIRE_TIMING_WINDOW_MS:
                    cf_mult = CROSSFIRE_MULTIPLIER
                    is_cf = True
                    break

        # Spawn timing bonus (1.0 + score, range 1.0-2.0)
        spawn_mult = 1.0
        if round_key in spawn_timings:
            best_score = max(
                (st_data[2] for st_data in spawn_timings[round_key]
                 if st_data[0] == killer_guid and abs(st_data[1] - kill_time) <= SPAWN_TIMING_WINDOW_MS),
                default=0.0,
            )
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

        # TODO: Implement when per-kill distance data available
        dist_mult = DISTANCE_NORMAL

        # Oksii adoption: health multiplier (clutch kill with low HP)
        health_mult = 1.0
        # Oksii adoption: alive count multiplier (outnumbered/solo clutch)
        alive_mult = 1.0
        # Oksii adoption: reinforcement timing multiplier
        reinf_mult = 1.0

        cp = None
        cp_key = (killer_guid, round_start_unix, round_number, kill_time)
        if combat_positions:
            cp = combat_positions.get(cp_key)
            if cp:
                # Health multiplier
                if cp['killer_health'] > 0 and cp['killer_health'] < LOW_HEALTH_THRESHOLD:
                    health_mult = LOW_HEALTH_MULTIPLIER

                # Alive multiplier — dynamic threshold: max(1, team_size // 3)
                atk_team = cp['attacker_team'].upper()
                if atk_team in ('AXIS', '1'):
                    my_alive = cp['axis_alive']
                    enemy_alive = cp['allies_alive']
                else:
                    my_alive = cp['allies_alive']
                    enemy_alive = cp['axis_alive']

                team_size = my_alive + enemy_alive  # approximate total players
                outnumbered_threshold = max(1, team_size // 3) if team_size > 0 else 2

                if my_alive == 1 and enemy_alive >= SOLO_CLUTCH_THRESHOLD:
                    alive_mult = SOLO_CLUTCH_MULTIPLIER
                elif my_alive > 0 and (enemy_alive - my_alive) >= outnumbered_threshold:
                    alive_mult = OUTNUMBERED_MULTIPLIER

        # Reinforcement timing multiplier (Oksii adoption)
        # Only apply if victim has a long wait until respawn relative to spawn interval
        victim_reinf_stored = 0.0
        if round_key in spawn_timings:
            for st_data in spawn_timings[round_key]:
                if st_data[0] == killer_guid and abs(st_data[1] - kill_time) <= SPAWN_TIMING_WINDOW_MS:
                    # Check if we have reinf data (extended tuple)
                    if len(st_data) > 4:
                        victim_reinf_val = st_data[4]  # victim_reinf seconds
                        victim_reinf_stored = float(victim_reinf_val)
                        enemy_spawn_interval_val = st_data[3]  # enemy_spawn_interval ms
                        spawn_interval_s = enemy_spawn_interval_val / 1000.0 if enemy_spawn_interval_val > 0 else 30
                        if spawn_interval_s > 0 and victim_reinf_val > (spawn_interval_s * REINF_PENALTY_THRESHOLD):
                            reinf_mult = 1.2
                    break

        # Total impact = product of all multipliers
        raw = (1.0 * carrier_mult * push_mult * cf_mult
               * spawn_mult * outcome_mult * class_mult * dist_mult
               * health_mult * alive_mult * reinf_mult)
        # Soft cap: linear compression above 5.0 (25% above threshold)
        # Preserves ordering while preventing outlier dominance
        total = raw if raw <= 5.0 else 5.0 + (raw - 5.0) * 0.25

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
            'health_multiplier': round(health_mult, 2),
            'alive_multiplier': round(alive_mult, 2),
            'reinf_multiplier': round(reinf_mult, 2),
            'killer_health': cp['killer_health'] if cp else 0,
            'axis_alive': cp['axis_alive'] if cp else 0,
            'allies_alive': cp['allies_alive'] if cp else 0,
            'victim_reinf': victim_reinf_stored,
            'total_impact': round(total, 2),
            'is_carrier_kill': is_carrier,
            'is_during_push': is_push,
            'is_crossfire': is_cf,
            'is_objective_area': False,  # TODO: Implement when per-kill distance data available
            'kill_time_ms': kill_time,
        }

