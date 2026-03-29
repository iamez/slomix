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

import asyncio
import traceback
from datetime import date, datetime

from website.backend.logging_config import get_app_logger
from website.backend.utils.et_constants import strip_et_colors, weapon_name

logger = get_app_logger("storytelling")

# Per-session locks to prevent concurrent TOCTOU races on lazy compute
class _BoundedLockDict:
    """Bounded dict of asyncio.Lock — evicts oldest when full."""
    def __init__(self, maxsize: int = 64):
        self._locks: dict[str, asyncio.Lock] = {}
        self._order: list[str] = []
        self._maxsize = maxsize

    def get(self, key: str) -> asyncio.Lock:
        if key in self._locks:
            return self._locks[key]
        if len(self._locks) >= self._maxsize:
            oldest = self._order.pop(0)
            self._locks.pop(oldest, None)
        lock = asyncio.Lock()
        self._locks[key] = lock
        self._order.append(key)
        return lock

_compute_locks = _BoundedLockDict()

# Competitive ET:Legacy multipliers (calibrated for pro play)
CARRIER_KILL_MULTIPLIER = 3.0       # Killed flag/doc carrier
CARRIER_CHAIN_MULTIPLIER = 5.0      # Carrier kill + teammate returned within 10s
PUSH_QUALITY_THRESHOLD = 0.9          # Minimum push_quality to earn bonus
PUSH_BUFFER_MS = 2000                 # Tighter window (was 5000ms)
PUSH_TOWARD_EXCLUDE = frozenset(('NO', 'N/A', ''))  # Not a real objective push
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

# Oksii adoption multipliers
LOW_HEALTH_THRESHOLD = 30           # HP threshold for clutch kill
LOW_HEALTH_MULTIPLIER = 1.3         # Kill with <30 HP = clutch
SOLO_CLUTCH_THRESHOLD = 3           # Enemies alive for solo clutch
SOLO_CLUTCH_MULTIPLIER = 2.0        # 1v3+ kill
OUTNUMBERED_MULTIPLIER = 1.5        # Kill while outnumbered
REINF_PENALTY_THRESHOLD = 0.75      # victim_reinf > 75% of spawn interval = bonus

# ── Team Synergy Score constants ────────────────────────────────
SYNERGY_WEIGHTS = {
    'crossfire': 0.25,
    'trade': 0.25,
    'cohesion': 0.20,
    'push': 0.15,
    'medic': 0.15,
}
COHESION_MAX_DISPERSION = 1500      # Game units; above this = 0 cohesion

def _to_date(val: str | date) -> date:
    """Normalize to datetime.date for asyncpg DATE params (proximity tables use DATE type)."""
    if isinstance(val, date):
        return val
    return datetime.strptime(val, "%Y-%m-%d").date()


def _to_date_str(val: str | date) -> str:
    """Normalize to YYYY-MM-DD string for TEXT columns (player_comprehensive_stats.round_date)."""
    if isinstance(val, date):
        return val.isoformat()
    datetime.strptime(val, "%Y-%m-%d")  # validate
    return val


def _format_time_ms(ms: int) -> str:
    """Format milliseconds from round start as MM:SS."""
    if not ms or ms <= 0:
        return "0:00"
    total_seconds = ms // 1000
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:02d}"


class StorytellingService:
    def __init__(self, db):
        self.db = db

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

        # 2. Pre-load context data for the session
        carrier_kills = await self._load_carrier_kills(sd)
        carrier_returns = await self._load_carrier_returns(sd)
        pushes = await self._load_pushes(sd)
        crossfires = await self._load_crossfires(sd)
        spawn_timings = await self._load_spawn_timings(sd)
        victim_classes = await self._load_victim_classes(sd)
        combat_positions = await self._load_combat_positions(sd)

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
                    if 0 < (ret - kill_time) <= 10000:  # returned within 10s
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
                if abs(kill_time - cf_time) <= 3000:
                    cf_mult = CROSSFIRE_MULTIPLIER
                    is_cf = True
                    break

        # Spawn timing bonus (1.0 + score, range 1.0-2.0)
        spawn_mult = 1.0
        if round_key in spawn_timings:
            best_score = max(
                (st_data[2] for st_data in spawn_timings[round_key]
                 if st_data[0] == killer_guid and abs(st_data[1] - kill_time) <= 2000),
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
        if round_key in spawn_timings:
            for st_data in spawn_timings[round_key]:
                if st_data[0] == killer_guid and abs(st_data[1] - kill_time) <= 2000:
                    # Check if we have reinf data (extended tuple)
                    if len(st_data) > 4:
                        victim_reinf_val = st_data[4]  # victim_reinf seconds
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
            'victim_reinf': 0.0,
            'total_impact': round(total, 2),
            'is_carrier_kill': is_carrier,
            'is_during_push': is_push,
            'is_crossfire': is_cf,
            'is_objective_area': False,  # TODO: Implement when per-kill distance data available
            'kill_time_ms': kill_time,
        }

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

    # ── Match Moments Detection ──

    async def detect_moments(self, session_date: str | date, limit: int = 10) -> list:
        """Detect highlight-reel moments for a session across 11 detectors."""
        sd = _to_date(session_date)
        moments = []

        # Run all 11 detectors (5 original + 4 objective + 2 combat)
        detectors = [
            self._detect_kill_streaks,
            self._detect_carrier_chains,
            self._detect_focus_survivals,
            self._detect_push_successes,
            self._detect_trade_chains,
            self._detect_objective_secured,
            self._detect_objective_run_moments,
            self._detect_objective_denied,
            self._detect_multi_revive,
            self._detect_team_wipes,
            self._detect_multikills,
        ]
        for detector in detectors:
            try:
                found = await detector(sd)
                logger.info("Moment detector %s returned %d results", detector.__name__, len(found))
                moments.extend(found)
            except Exception as e:
                logger.error("Moment detector %s failed: %s\n%s",
                             detector.__name__, e, traceback.format_exc())

        # Enrich all moments with time_formatted
        for m in moments:
            if "time_formatted" not in m:
                m["time_formatted"] = _format_time_ms(m.get("time_ms", 0))

        # Ensure type diversity: reserve one slot per type, fill remainder by stars
        by_type: dict[str, list] = {}
        for m in moments:
            by_type.setdefault(m["type"], []).append(m)
        for bucket in by_type.values():
            bucket.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))

        # Pick the best moment from each type first
        result = []
        seen_ids = set()
        for t, bucket in by_type.items():
            if bucket:
                best = bucket[0]
                result.append(best)
                seen_ids.add(id(best))

        # Fill remaining slots from all moments by stars
        remaining = [m for m in moments if id(m) not in seen_ids]
        remaining.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
        result.extend(remaining[:max(0, limit - len(result))])

        result.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
        return result[:limit]

    async def _detect_kill_streaks(self, sd: date) -> list:
        """Detector A: Multi-kill streaks (3+ kills within 10s window).
        Enhanced with objective proximity bonus: +1★ if streak overlaps with
        carrier event, objective run, or team push in the same round."""
        rows = await self.db.fetch_all("""
            WITH windowed AS (
                SELECT killer_guid, killer_name, kill_time, round_number, map_name,
                       round_start_unix,
                       COUNT(*) OVER (
                           PARTITION BY killer_guid, round_start_unix
                           ORDER BY kill_time
                           RANGE BETWEEN 10000 PRECEDING AND CURRENT ROW
                       ) AS streak
                FROM proximity_kill_outcome
                WHERE session_date = $1
            )
            SELECT killer_guid, killer_name, kill_time, round_number, map_name,
                   round_start_unix, streak
            FROM windowed
            WHERE streak >= 3
            ORDER BY streak DESC, kill_time
        """, (sd,))

        # Pre-load objective event times for proximity bonus
        obj_times = await self._load_objective_event_times(sd)

        # Group by (killer_guid, round_start_unix) and take best streak per player per round
        seen = {}
        for r in (rows or []):
            killer_guid, killer_name, kill_time, round_number, map_name, round_start_unix, streak = (
                r[0], r[1], r[2], r[3], r[4], r[5], int(r[6])
            )
            key = (killer_guid, round_start_unix)
            if key not in seen or streak > seen[key]["streak"]:
                seen[key] = {
                    "killer_guid": killer_guid,
                    "killer_name": strip_et_colors(killer_name or killer_guid[:8]),
                    "kill_time": kill_time,
                    "round_number": round_number,
                    "map_name": map_name,
                    "round_start_unix": round_start_unix,
                    "streak": streak,
                }

        moments = []
        for info in seen.values():
            streak = info["streak"]
            stars = min(5, streak - 1)  # 3-kill=2★, 4-kill=3★, 5-kill=4★, 6+=5★

            # Objective proximity bonus: +1★ if streak happened near an objective event
            near_obj = False
            rkey = (info["round_start_unix"], info["round_number"])
            kt = info["kill_time"] or 0
            for evt_time in obj_times.get(rkey, []):
                if abs(kt - evt_time) <= 15000:  # within 15s of objective event
                    near_obj = True
                    break
            if near_obj:
                stars = min(5, stars + 1)

            name = info["killer_name"]
            suffix = " near objective!" if near_obj else ""
            moments.append({
                "type": "kill_streak",
                "round_number": info["round_number"],
                "map_name": info["map_name"],
                "time_ms": kt,
                "player": name,
                "narrative": f"{name} went on a {streak}-kill streak in 10s{suffix}",
                "impact_stars": stars,
                "detail": {"streak_count": streak, "killer_guid": info["killer_guid"],
                           "near_objective": near_obj},
            })
        return moments

    async def _load_objective_event_times(self, sd: date) -> dict:
        """Load all objective event timestamps indexed by (round_start_unix, round_number).
        Combines carrier events, objective runs, and construction events."""
        result: dict[tuple, list[int]] = {}

        # Carrier pickups/drops/secures
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, pickup_time FROM proximity_carrier_event "
            "WHERE session_date = $1", (sd,))
        for r in (rows or []):
            if r[2] and r[2] > 0:
                result.setdefault((r[0], r[1]), []).append(r[2])

        # Objective runs (plants, constructions, defuses)
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, action_time FROM proximity_objective_run "
            "WHERE session_date = $1", (sd,))
        for r in (rows or []):
            if r[2] and r[2] > 0:
                result.setdefault((r[0], r[1]), []).append(r[2])

        # Construction events
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, round_number, event_time FROM proximity_construction_event "
            "WHERE session_date = $1", (sd,))
        for r in (rows or []):
            if r[2] and r[2] > 0:
                result.setdefault((r[0], r[1]), []).append(r[2])

        return result

    async def _detect_carrier_chains(self, sd: date) -> list:
        """Detector B: Carrier kill → teammate returns within 10s."""
        rows = await self.db.fetch_all("""
            SELECT ck.killer_guid, ck.killer_name, ck.kill_time,
                   cr.returner_guid, cr.returner_name, cr.return_time,
                   ck.round_number, ck.map_name
            FROM proximity_carrier_kill ck
            JOIN proximity_carrier_return cr
                ON cr.session_date = ck.session_date
                AND cr.round_number = ck.round_number
                AND cr.round_start_unix = ck.round_start_unix
            WHERE ck.session_date = $1
                AND (cr.return_time - ck.kill_time) BETWEEN 0 AND 10000
            ORDER BY ck.kill_time
        """, (sd,))

        moments = []
        for r in (rows or []):
            killer_name = strip_et_colors(r[1] or r[0][:8])
            returner_name = strip_et_colors(r[4] or r[3][:8])
            delta_s = round((r[5] - r[2]) / 1000, 1)
            moments.append({
                "type": "carrier_chain",
                "round_number": r[6],
                "map_name": r[7],
                "time_ms": r[2] or 0,
                "player": killer_name,
                "narrative": f"{killer_name} intercepted the carrier, {returner_name} returned it {delta_s}s later",
                "impact_stars": 5,
                "detail": {
                    "killer_guid": r[0], "returner_guid": r[3],
                    "returner_name": returner_name, "delta_ms": r[5] - r[2],
                },
            })
        return moments

    async def _detect_focus_survivals(self, sd: date) -> list:
        """Detector C: Survived 3v1+ focus fire."""
        rows = await self.db.fetch_all("""
            SELECT target_guid, target_name, attacker_count, focus_score,
                   round_number, map_name, engagement_id
            FROM proximity_focus_fire
            WHERE session_date = $1 AND attacker_count >= 3
                AND focus_score >= 0.5
            ORDER BY focus_score DESC
            LIMIT 10
        """, (sd,))

        moments = []
        for r in (rows or []):
            name = strip_et_colors(r[1] or r[0][:8])
            attackers = int(r[2])
            score = float(r[3])
            stars = 3 if attackers == 3 else (4 if attackers == 4 else 5)
            moments.append({
                "type": "focus_survival",
                "round_number": r[4],
                "map_name": r[5],
                "time_ms": 0,
                "player": name,
                "narrative": f"{name} survived a {attackers}v1 focus fire (score {score:.0%})",
                "impact_stars": stars,
                "detail": {
                    "target_guid": r[0], "attacker_count": attackers,
                    "focus_score": score,
                },
            })
        return moments

    async def _detect_push_successes(self, sd: date) -> list:
        """Detector D: High-quality team pushes (3+ participants, high push_quality)."""
        rows = await self.db.fetch_all("""
            SELECT team, participant_count, push_quality, alignment_score,
                   toward_objective, round_number, map_name, start_time
            FROM proximity_team_push
            WHERE session_date = $1
                AND participant_count >= 3
                AND push_quality >= 0.7
                AND toward_objective != 'NO'
            ORDER BY push_quality DESC
            LIMIT 5
        """, (sd,))

        moments = []
        for r in (rows or []):
            team = r[0] or "Unknown"
            count = int(r[1])
            quality = float(r[2])
            objective = r[4] or "objective"
            stars = 3 if quality < 0.8 else (4 if quality < 0.9 else 5)
            obj_label = objective.replace('_', ' ')
            moments.append({
                "type": "push_success",
                "round_number": r[5],
                "map_name": r[6],
                "time_ms": r[7] or 0,
                "player": f"Team {team}",
                "narrative": f"Team {team} pushed {obj_label} with {count} players (quality {quality:.0%})",
                "impact_stars": stars,
                "detail": {
                    "team": team, "participant_count": count,
                    "push_quality": quality, "alignment_score": float(r[3] or 0),
                    "objective": objective,
                },
            })
        return moments

    async def _detect_trade_chains(self, sd: date) -> list:
        """Detector E: Trade kills (A kills B, C avenges A within delta_ms)."""
        rows = await self.db.fetch_all("""
            SELECT trader_guid, trader_name, original_victim_guid, original_victim_name,
                   original_killer_guid, original_killer_name, delta_ms,
                   round_number, map_name, traded_kill_time
            FROM proximity_lua_trade_kill
            WHERE session_date = $1 AND delta_ms <= 5000
            ORDER BY delta_ms ASC
            LIMIT 10
        """, (sd,))

        moments = []
        for r in (rows or []):
            trader_name = strip_et_colors(r[1] or r[0][:8])
            victim_name = strip_et_colors(r[3] or r[2][:8])
            avenger_target = strip_et_colors(r[5] or r[4][:8])
            delta_s = round(int(r[6]) / 1000, 1)
            stars = 4 if delta_s <= 2 else 3
            moments.append({
                "type": "trade_chain",
                "round_number": r[7],
                "map_name": r[8],
                "time_ms": r[9] or 0,
                "player": trader_name,
                "narrative": f"{trader_name} avenged {victim_name} by trading {avenger_target} in {delta_s}s",
                "impact_stars": stars,
                "detail": {
                    "trader_guid": r[0], "victim_guid": r[2],
                    "target_guid": r[4], "delta_ms": int(r[6]),
                },
            })
        return moments

    # ── Objective-Based Moment Detectors (OW2/HLTV-inspired) ──

    async def _detect_objective_secured(self, sd: date) -> list:
        """Detector F: Carrier picks up objective and successfully secures it,
        OR carrier kill → return chain (enhanced carrier_chain with pickup context)."""
        rows = await self.db.fetch_all("""
            SELECT carrier_guid, carrier_name, pickup_time, drop_time,
                   duration_ms, outcome, carry_distance, map_name,
                   round_number, efficiency
            FROM proximity_carrier_event
            WHERE session_date = $1 AND outcome = 'secured'
            ORDER BY pickup_time
        """, (sd,))

        moments = []
        for r in (rows or []):
            name = strip_et_colors(r[1] or r[0][:8])
            duration_s = round((r[4] or 0) / 1000, 1)
            distance = int(r[6] or 0)
            efficiency = float(r[9] or 0)
            # 5★ always — securing the objective is game-changing
            stars = 5
            eff_pct = f" ({efficiency:.0%} efficiency)" if efficiency > 0 else ""
            moments.append({
                "type": "objective_secured",
                "round_number": r[8],
                "map_name": r[7],
                "time_ms": r[2] or 0,
                "player": name,
                "narrative": f"{name} carried the objective {distance}u in {duration_s}s and secured it{eff_pct}",
                "impact_stars": stars,
                "detail": {
                    "carrier_guid": r[0], "duration_ms": r[4] or 0,
                    "carry_distance": distance, "efficiency": efficiency,
                },
            })
        return moments

    async def _detect_objective_run_moments(self, sd: date) -> list:
        """Detector G: Engineer completes objective action under fire (enemies_nearby >= 2)
        or any successful dynamite plant / construction in contested area."""
        rows = await self.db.fetch_all("""
            SELECT engineer_guid, engineer_name, action_type, track_name,
                   enemies_nearby, nearby_teammates, map_name, round_number,
                   action_time, approach_distance, self_kills, team_kills
            FROM proximity_objective_run
            WHERE session_date = $1
                AND action_type IN ('dynamite_plant', 'construction_complete', 'objective_destroyed')
                AND enemies_nearby >= 2
            ORDER BY enemies_nearby DESC, action_time
            LIMIT 10
        """, (sd,))

        moments = []
        for r in (rows or []):
            name = strip_et_colors(r[1] or r[0][:8])
            action = r[2] or 'objective'
            track = r[3] or 'the objective'
            enemies = int(r[4] or 0)
            teammates = int(r[5] or 0)
            self_kills = int(r[10] or 0)

            # 4★ base for contested objective, 5★ if solo (no teammates) or many enemies
            if enemies >= 3 or (enemies >= 2 and teammates == 0):
                stars = 5
            else:
                stars = 4

            action_label = {
                'dynamite_plant': 'planted dynamite on',
                'construction_complete': 'built',
                'objective_destroyed': 'destroyed',
            }.get(action, 'completed')

            combat_ctx = f" with {enemies} enemies nearby"
            if self_kills > 0:
                combat_ctx += f", getting {self_kills} kill{'s' if self_kills > 1 else ''}"

            moments.append({
                "type": "objective_run",
                "round_number": r[7],
                "map_name": r[6],
                "time_ms": r[8] or 0,
                "player": name,
                "narrative": f"{name} {action_label} {track}{combat_ctx}",
                "impact_stars": stars,
                "detail": {
                    "engineer_guid": r[0], "action_type": action,
                    "track_name": track, "enemies_nearby": enemies,
                    "nearby_teammates": teammates, "self_kills": self_kills,
                },
            })
        return moments

    async def _detect_objective_denied(self, sd: date) -> list:
        """Detector H: Player kills carrier before extraction, or defuses dynamite,
        or kills engineer during construction."""
        moments = []

        # H1: Carrier killed before extraction (outcome = 'killed')
        carrier_rows = await self.db.fetch_all("""
            SELECT ce.carrier_guid, ce.carrier_name, ce.killer_guid, ce.killer_name,
                   ce.carry_distance, ce.duration_ms, ce.map_name, ce.round_number,
                   ce.pickup_time
            FROM proximity_carrier_event ce
            WHERE ce.session_date = $1 AND ce.outcome = 'killed'
                AND ce.killer_guid IS NOT NULL AND ce.killer_guid != ''
            ORDER BY ce.carry_distance DESC
            LIMIT 10
        """, (sd,))

        for r in (carrier_rows or []):
            carrier_name = strip_et_colors(r[1] or r[0][:8])
            killer_name = strip_et_colors(r[3] or r[2][:8])
            distance = int(r[4] or 0)
            duration_s = round((r[5] or 0) / 1000, 1)
            # 4★ base, 5★ if carrier had traveled far (close to scoring)
            stars = 5 if distance >= 500 else 4
            moments.append({
                "type": "objective_denied",
                "round_number": r[7],
                "map_name": r[6],
                "time_ms": r[8] or 0,
                "player": killer_name,
                "narrative": f"{killer_name} killed carrier {carrier_name} after {distance}u carry ({duration_s}s)",
                "impact_stars": stars,
                "detail": {
                    "killer_guid": r[2], "carrier_guid": r[0],
                    "carry_distance": distance, "duration_ms": r[5] or 0,
                    "sub_type": "carrier_denied",
                },
            })

        # H2: Dynamite defused (enemy planted, defender defused)
        defuse_rows = await self.db.fetch_all("""
            SELECT engineer_guid, engineer_name, track_name, map_name,
                   round_number, action_time, enemies_nearby
            FROM proximity_objective_run
            WHERE session_date = $1 AND action_type = 'dynamite_defuse'
            ORDER BY action_time
            LIMIT 10
        """, (sd,))

        for r in (defuse_rows or []):
            name = strip_et_colors(r[1] or r[0][:8])
            track = r[2] or 'the dynamite'
            enemies = int(r[6] or 0)
            stars = 5 if enemies >= 2 else 4
            suffix = f" under fire ({enemies} enemies)" if enemies >= 1 else ""
            moments.append({
                "type": "objective_denied",
                "round_number": r[4],
                "map_name": r[3],
                "time_ms": r[5] or 0,
                "player": name,
                "narrative": f"{name} defused dynamite at {track}{suffix}",
                "impact_stars": stars,
                "detail": {
                    "engineer_guid": r[0], "track_name": track,
                    "enemies_nearby": enemies, "sub_type": "dynamite_defuse",
                },
            })

        return moments

    async def _detect_multi_revive(self, sd: date) -> list:
        """Detector I: Medic revives 3+ teammates within a 15s window.
        Inspired by Overwatch's mass-rez moments — in high-TTK games like ET,
        rapid revives swing fights dramatically."""
        rows = await self.db.fetch_all("""
            WITH revives AS (
                SELECT reviver_guid, reviver_name, outcome_time,
                       round_number, map_name, round_start_unix,
                       COUNT(*) OVER (
                           PARTITION BY reviver_guid, round_start_unix
                           ORDER BY outcome_time
                           RANGE BETWEEN 15000 PRECEDING AND CURRENT ROW
                       ) AS revive_burst
                FROM proximity_kill_outcome
                WHERE session_date = $1
                    AND outcome = 'revived'
                    AND reviver_guid IS NOT NULL
                    AND reviver_guid != ''
            )
            SELECT reviver_guid, reviver_name, outcome_time, round_number,
                   map_name, round_start_unix, revive_burst
            FROM revives
            WHERE revive_burst >= 3
            ORDER BY revive_burst DESC, outcome_time
        """, (sd,))

        # Group by (reviver_guid, round_start_unix) and take best burst per medic per round
        seen = {}
        for r in (rows or []):
            reviver_guid, reviver_name, outcome_time, round_number, map_name, round_start_unix, burst = (
                r[0], r[1], r[2], r[3], r[4], r[5], int(r[6])
            )
            key = (reviver_guid, round_start_unix)
            if key not in seen or burst > seen[key]["burst"]:
                seen[key] = {
                    "reviver_guid": reviver_guid,
                    "reviver_name": strip_et_colors(reviver_name or reviver_guid[:8]),
                    "outcome_time": outcome_time,
                    "round_number": round_number,
                    "map_name": map_name,
                    "burst": burst,
                }

        moments = []
        for info in seen.values():
            burst = info["burst"]
            # 4★ for 3 revives, 5★ for 4+
            stars = 5 if burst >= 4 else 4
            name = info["reviver_name"]
            moments.append({
                "type": "multi_revive",
                "round_number": info["round_number"],
                "map_name": info["map_name"],
                "time_ms": info["outcome_time"] or 0,
                "player": name,
                "narrative": f"{name} revived {burst} teammates in 15s — team rez!",
                "impact_stars": stars,
                "detail": {"reviver_guid": info["reviver_guid"], "revive_count": burst},
            })
        return moments

    async def _detect_team_wipes(self, sd: date) -> list:
        """Detector J: Team Wipe — all enemies killed within a 15s window.
        In competitive 3v3 ET, wiping all 3 enemies is the highest impact play.
        Uses combat_position for team info + kill_outcome for kill details."""

        # Get all kills with team info for this session
        rows = await self.db.fetch_all("""
            SELECT cp.event_time, cp.attacker_guid, cp.attacker_name, cp.attacker_team,
                   cp.victim_guid, cp.victim_name, cp.victim_team,
                   cp.means_of_death, cp.round_number, cp.map_name, cp.round_start_unix
            FROM proximity_combat_position cp
            WHERE cp.session_date = $1
                AND cp.event_type = 'kill'
                AND cp.attacker_team IS NOT NULL
                AND cp.victim_team IS NOT NULL
                AND cp.attacker_team != cp.victim_team
            ORDER BY cp.round_start_unix, cp.event_time
        """, (sd,))

        if not rows:
            return []

        # Get team sizes per round
        team_sizes = await self.db.fetch_all("""
            SELECT round_start_unix, round_number, attacker_team,
                   COUNT(DISTINCT attacker_guid) as team_size
            FROM proximity_combat_position
            WHERE session_date = $1 AND event_type = 'kill'
            GROUP BY round_start_unix, round_number, attacker_team
        """, (sd,))

        ts_map: dict[tuple, dict[str, int]] = {}
        for r in (team_sizes or []):
            key = (r[0], r[1])
            ts_map.setdefault(key, {})[r[2]] = int(r[3])

        # Group kills by round
        kills_by_round: dict[tuple, list] = {}
        for r in (rows or []):
            rkey = (r[10], r[8])  # (round_start_unix, round_number)
            kills_by_round.setdefault(rkey, []).append({
                "time": r[0], "killer_guid": r[1],
                "killer": strip_et_colors(r[2] or r[1][:8]),
                "killer_team": r[3],
                "victim_guid": r[4],
                "victim": strip_et_colors(r[5] or r[4][:8]),
                "victim_team": r[6],
                "weapon": weapon_name(r[7] or 0),
                "kill_mod": r[7] or 0,
                "round_number": r[8], "map_name": r[9],
                "round_start_unix": r[10],
            })

        moments = []
        for rkey, kills in kills_by_round.items():
            sizes = ts_map.get(rkey, {})
            # Check both teams as potential wipe targets
            for target_team in ('AXIS', 'ALLIES'):
                enemy_size = sizes.get(target_team, 0)
                if enemy_size < 2:
                    continue  # need at least 2 enemies for a meaningful wipe

                # Get kills of this team, sorted by time
                team_kills = [k for k in kills if k["victim_team"] == target_team]
                if len(team_kills) < enemy_size:
                    continue

                # Sliding window: find windows where all enemies die
                for i in range(len(team_kills)):
                    window_start = team_kills[i]["time"]
                    window_kills = []
                    victims_in_window = set()

                    for j in range(i, len(team_kills)):
                        if team_kills[j]["time"] - window_start > 15000:
                            break
                        window_kills.append(team_kills[j])
                        victims_in_window.add(team_kills[j]["victim_guid"])

                    if len(victims_in_window) >= enemy_size:
                        # TEAM WIPE detected!
                        # Deduplicate: keep first kill per victim (the lethal one)
                        seen_victims = set()
                        wipe_kills = []
                        for k in window_kills:
                            if k["victim_guid"] not in seen_victims:
                                seen_victims.add(k["victim_guid"])
                                wipe_kills.append(k)
                            if len(seen_victims) >= enemy_size:
                                break

                        first_kill = wipe_kills[0]
                        last_kill = wipe_kills[-1]
                        duration_ms = last_kill["time"] - first_kill["time"]
                        duration_s = round(duration_ms / 1000, 1)
                        wiping_team = first_kill["killer_team"]
                        map_name = first_kill["map_name"]
                        round_number = first_kill["round_number"]

                        # Build rich kill context
                        kill_details = []
                        for k in wipe_kills:
                            kill_details.append({
                                "killer": k["killer"],
                                "killer_guid": k["killer_guid"],
                                "victim": k["victim"],
                                "victim_guid": k["victim_guid"],
                                "weapon": k["weapon"],
                                "time_ms": k["time"],
                                "time_formatted": _format_time_ms(k["time"]),
                            })

                        victims_list = [k["victim"] for k in wipe_kills]
                        killers = list({k["killer"] for k in wipe_kills})

                        moments.append({
                            "type": "team_wipe",
                            "round_number": round_number,
                            "map_name": map_name,
                            "time_ms": first_kill["time"],
                            "time_formatted": _format_time_ms(first_kill["time"]),
                            "player": killers[0] if len(killers) == 1 else f"Team {wiping_team}",
                            "impact_stars": 5,
                            "narrative": (
                                f"TEAM WIPE — {wiping_team} eliminated all {enemy_size} "
                                f"{target_team} players in {duration_s}s"
                            ),
                            "kills": kill_details,
                            "team": wiping_team,
                            "victims": victims_list,
                            "duration_ms": duration_ms,
                            "detail": {
                                "wiping_team": wiping_team,
                                "wiped_team": target_team,
                                "team_size": enemy_size,
                                "killers": killers,
                                "duration_ms": duration_ms,
                            },
                        })
                        break  # Only report first wipe per team per round

        # Deduplicate: max 1 wipe per (round_start_unix, round_number, wiped_team)
        seen_wipes = set()
        unique_moments = []
        for m in moments:
            wipe_key = (m["round_number"], m["detail"]["wiped_team"], m.get("map_name"))
            if wipe_key not in seen_wipes:
                seen_wipes.add(wipe_key)
                unique_moments.append(m)

        return unique_moments

    async def _detect_multikills(self, sd: date) -> list:
        """Detector K: Personal Multikill — a single player kills 2+ enemies
        in rapid succession (tighter window than kill_streak).
        - Double kill: 2 kills in 5s → 2★
        - Triple kill: 3 kills in 5s → 3★
        - Quad kill: 4 kills in 8s → 4★
        - Ace (all enemies): 5★
        Uses combat_position for weapon/team context."""

        # Get all kills with full context
        rows = await self.db.fetch_all("""
            SELECT cp.event_time, cp.attacker_guid, cp.attacker_name, cp.attacker_team,
                   cp.victim_guid, cp.victim_name, cp.victim_team,
                   cp.means_of_death, cp.round_number, cp.map_name, cp.round_start_unix
            FROM proximity_combat_position cp
            WHERE cp.session_date = $1
                AND cp.event_type = 'kill'
                AND cp.attacker_team IS NOT NULL
                AND cp.victim_team IS NOT NULL
                AND cp.attacker_team != cp.victim_team
            ORDER BY cp.attacker_guid, cp.round_start_unix, cp.event_time
        """, (sd,))

        if not rows:
            return []

        # Get team sizes for ace detection
        team_sizes = await self.db.fetch_all("""
            SELECT round_start_unix, round_number, victim_team,
                   COUNT(DISTINCT victim_guid) as team_size
            FROM proximity_combat_position
            WHERE session_date = $1 AND event_type = 'kill'
                AND attacker_team != victim_team
            GROUP BY round_start_unix, round_number, victim_team
        """, (sd,))
        ts_map: dict[tuple, dict[str, int]] = {}
        for r in (team_sizes or []):
            ts_map.setdefault((r[0], r[1]), {})[r[2]] = int(r[3])

        # Group kills by (attacker_guid, round_start_unix)
        by_player_round: dict[tuple, list] = {}
        for r in (rows or []):
            pkey = (r[1], r[10], r[8])  # (attacker_guid, round_start_unix, round_number)
            by_player_round.setdefault(pkey, []).append({
                "time": r[0], "killer_guid": r[1],
                "killer": strip_et_colors(r[2] or r[1][:8]),
                "killer_team": r[3],
                "victim_guid": r[4],
                "victim": strip_et_colors(r[5] or r[4][:8]),
                "victim_team": r[6],
                "weapon": weapon_name(r[7] or 0),
                "kill_mod": r[7] or 0,
                "round_number": r[8], "map_name": r[9],
                "round_start_unix": r[10],
            })

        # Load objective event times for proximity check
        obj_times = await self._load_objective_event_times(sd)

        moments = []
        for pkey, kills in by_player_round.items():
            attacker_guid, round_start_unix, round_number = pkey
            kills.sort(key=lambda k: k["time"])

            # Sliding window: find best multikill burst per player per round
            best_burst = None
            best_count = 0

            for i in range(len(kills)):
                # Tight window: 5s for double/triple, expand to 8s for quad+
                window_kills = [kills[i]]
                distinct_victims = {kills[i]["victim_guid"]}

                for j in range(i + 1, len(kills)):
                    delta = kills[j]["time"] - kills[i]["time"]
                    # 5s base window, extend to 8s if already 3+ kills
                    max_window = 5000 if len(window_kills) < 3 else 8000
                    if delta > max_window:
                        break
                    window_kills.append(kills[j])
                    distinct_victims.add(kills[j]["victim_guid"])

                n_distinct = len(distinct_victims)
                if n_distinct >= 2 and n_distinct > best_count:
                    best_count = n_distinct
                    best_burst = window_kills[:n_distinct]  # keep only unique-victim kills

            if best_burst and best_count >= 2:
                # Deduplicate: first kill per unique victim
                seen_v = set()
                unique_kills = []
                for k in best_burst:
                    if k["victim_guid"] not in seen_v:
                        seen_v.add(k["victim_guid"])
                        unique_kills.append(k)

                first_kill = unique_kills[0]
                last_kill = unique_kills[-1]
                duration_ms = last_kill["time"] - first_kill["time"]
                duration_s = round(duration_ms / 1000, 1)
                name = first_kill["killer"]
                map_name = first_kill["map_name"]
                victim_team = first_kill["victim_team"]
                n = len(unique_kills)

                # Check if ace (killed all enemies)
                rkey = (round_start_unix, round_number)
                enemy_size = ts_map.get(rkey, {}).get(victim_team, 0)
                is_ace = (n >= enemy_size >= 2)

                # Star rating
                if is_ace:
                    stars = 5
                elif n >= 4:
                    stars = 4
                elif n >= 3:
                    stars = 3
                else:
                    stars = 2

                # Objective proximity bonus
                near_obj = False
                for evt_time in obj_times.get(rkey, []):
                    if abs(first_kill["time"] - evt_time) <= 15000:
                        near_obj = True
                        break
                if near_obj and stars < 5:
                    stars += 1

                # Label
                labels = {2: "DOUBLE KILL", 3: "TRIPLE KILL", 4: "QUAD KILL"}
                label = "ACE" if is_ace else labels.get(n, f"{n}-KILL")

                # Build rich kill context
                kill_details = []
                for k in unique_kills:
                    kill_details.append({
                        "killer": k["killer"],
                        "killer_guid": k["killer_guid"],
                        "victim": k["victim"],
                        "victim_guid": k["victim_guid"],
                        "weapon": k["weapon"],
                        "time_ms": k["time"],
                        "time_formatted": _format_time_ms(k["time"]),
                    })

                obj_suffix = " near objective" if near_obj else ""
                victims_list = [k["victim"] for k in unique_kills]

                moments.append({
                    "type": "multikill",
                    "round_number": round_number,
                    "map_name": map_name,
                    "time_ms": first_kill["time"],
                    "time_formatted": _format_time_ms(first_kill["time"]),
                    "player": name,
                    "impact_stars": stars,
                    "narrative": (
                        f"{label} — {name} eliminated {n} enemies "
                        f"in {duration_s}s{obj_suffix}"
                    ),
                    "kills": kill_details,
                    "team": first_kill["killer_team"],
                    "victims": victims_list,
                    "duration_ms": duration_ms,
                    "detail": {
                        "kill_count": n, "killer_guid": attacker_guid,
                        "is_ace": is_ace, "near_objective": near_obj,
                        "duration_ms": duration_ms, "label": label,
                    },
                })

        # Sort by stars descending, limit
        moments.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
        return moments[:20]

    async def get_kis_leaderboard(self, session_date: str | date, limit: int = 20) -> list:
        """Get KIS leaderboard for a session, including server-side archetype."""
        sd = _to_date(session_date)
        rows = await self.db.fetch_all("""
            SELECT killer_guid, MAX(killer_name) as name,
                   ROUND(SUM(total_impact)::numeric, 1) as total_kis,
                   COUNT(*) as kills,
                   SUM(CASE WHEN is_carrier_kill THEN 1 ELSE 0 END) as carrier_kills,
                   SUM(CASE WHEN is_during_push THEN 1 ELSE 0 END) as push_kills,
                   SUM(CASE WHEN is_crossfire THEN 1 ELSE 0 END) as crossfire_kills,
                   ROUND(AVG(total_impact)::numeric, 2) as avg_impact,
                   SUM(CASE WHEN COALESCE(health_multiplier, 1) > 1 THEN 1 ELSE 0 END) as clutch_kills,
                   SUM(CASE WHEN COALESCE(alive_multiplier, 1) >= 2 THEN 1 ELSE 0 END) as solo_clutch_kills,
                   SUM(CASE WHEN COALESCE(alive_multiplier, 1) > 1 AND COALESCE(alive_multiplier, 1) < 2 THEN 1 ELSE 0 END) as outnumbered_kills,
                   SUM(CASE WHEN COALESCE(reinf_multiplier, 1) > 1 THEN 1 ELSE 0 END) as spawn_denial_kills
            FROM storytelling_kill_impact
            WHERE session_date = $1
            GROUP BY killer_guid
            ORDER BY SUM(total_impact) DESC
            LIMIT $2
        """, (sd, limit))

        kis_entries = [
            {
                "guid": r[0], "name": strip_et_colors(r[1] or r[0][:8]),
                "total_kis": float(r[2] or 0), "kills": int(r[3] or 0),
                "carrier_kills": int(r[4] or 0), "push_kills": int(r[5] or 0),
                "crossfire_kills": int(r[6] or 0), "avg_impact": float(r[7] or 0),
                "clutch_kills": int(r[8] or 0),
                "solo_clutch_kills": int(r[9] or 0),
                "outnumbered_kills": int(r[10] or 0),
                "spawn_denial_kills": int(r[11] or 0),
            }
            for r in (rows or [])
        ]

        # Enrich with server-side archetypes and PCS metrics
        if kis_entries:
            archetypes, player_stats = await self.classify_players(sd, kis_entries)
            for entry in kis_entries:
                entry["archetype"] = archetypes.get(entry["guid"], "frontline_warrior")
                ps = player_stats.get(entry["guid"], {})
                entry["dpm"] = round(ps.get("dpm", 0), 1)
                entry["denied_time"] = round(ps.get("denied_time", 0))
                entry["time_dead_pct"] = round(ps.get("time_dead_pct", 0), 2)

        return kis_entries

    # ── Server-side archetype classification ──────────────────────────

    async def classify_players(
        self, session_date: date, kis_entries: list[dict]
    ) -> tuple[dict[str, str], dict[str, dict]]:
        """Classify each player's archetype using all available data.

        Returns (archetypes: {guid: archetype_string}, stats_by_guid: {guid: stats_dict}).
        """
        guids = [e["guid"] for e in kis_entries]
        if not guids:
            return {}, {}

        # Build a stats dict per player starting from KIS data
        stats_by_guid: dict[str, dict] = {}
        for e in kis_entries:
            stats_by_guid[e["guid"]] = {
                "kills": e["kills"],
                "carrier_kills": e["carrier_kills"],
                "push_kills": e["push_kills"],
                "crossfire_kills": e["crossfire_kills"],
                "avg_impact": e["avg_impact"],
                "total_kis": e["total_kis"],
                "deaths": 0,
                "revives_given": 0,
                "headshot_kills": 0,
                "headshot_pct": 0.0,
                "carrier_returns": 0,
                "trade_kills": 0,
                "avg_kill_distance": 0.0,
                "dpm": 0.0,
                "denied_time": 0,
                "time_dead_pct": 0.0,
            }

        # 1. PCS stats: kills, deaths, headshots, revives (PCS kills are authoritative)
        pcs_rows = await self.db.fetch_all("""
            SELECT player_guid,
                   SUM(kills) as pcs_kills,
                   SUM(deaths) as deaths,
                   SUM(headshots) as hs_hits,
                   SUM(bullets_fired) as shots,
                   AVG(accuracy) as avg_accuracy,
                   SUM(revives_given) as revives,
                   SUM(objectives_returned) as obj_returned,
                   SUM(damage_given) as dmg,
                   SUM(time_played_minutes) as time_played,
                   SUM(denied_playtime) as denied_time,
                   SUM(time_dead_minutes) as time_dead
            FROM player_comprehensive_stats
            WHERE round_date = $1
            GROUP BY player_guid
        """, (_to_date_str(session_date),))
        # Build short→long GUID lookup (PCS uses 8-char, proximity uses 32-char)
        short_to_long = {g[:8]: g for g in stats_by_guid}

        for r in (pcs_rows or []):
            pcs_guid = r[0]
            # Match by first 8 chars (PCS stores truncated GUIDs)
            long_guid = short_to_long.get(pcs_guid) or short_to_long.get(pcs_guid[:8])
            if long_guid and long_guid in stats_by_guid:
                s = stats_by_guid[long_guid]
                s["pcs_kills"] = int(r[1] or 0)  # authoritative kill count
                s["deaths"] = int(r[2] or 0)
                hs_hits = float(r[3] or 0)
                shots = float(r[4] or 0)
                avg_acc = float(r[5] or 0)
                total_hits = shots * avg_acc / 100 if avg_acc > 0 else 0
                # Real HS% = headshot HITS / total HITS (not headshot kills / kills!)
                s["headshot_pct"] = hs_hits / total_hits if total_hits > 0 else 0.0
                s["revives_given"] = int(r[6] or 0)
                s["carrier_returns"] = int(r[7] or 0)
                dmg = float(r[8] or 0)
                time_played = float(r[9] or 0)
                denied_time = float(r[10] or 0)
                time_dead = float(r[11] or 0)
                s["dpm"] = dmg / max(time_played, 1)
                s["denied_time"] = denied_time
                s["time_dead_pct"] = time_dead / max(time_played, 0.1)

        # 2. Trade kills from proximity_lua_trade_kill
        trade_rows = await self.db.fetch_all("""
            SELECT trader_guid, COUNT(*) as trades
            FROM proximity_lua_trade_kill
            WHERE session_date = $1
            GROUP BY trader_guid
        """, (session_date,))
        for r in (trade_rows or []):
            guid = r[0]
            if guid in stats_by_guid:
                stats_by_guid[guid]["trade_kills"] = int(r[1] or 0)

        # 3. Average kill distance from proximity_combat_position
        dist_rows = await self.db.fetch_all("""
            SELECT attacker_guid,
                   AVG(SQRT(
                       POWER(attacker_x - victim_x, 2) +
                       POWER(attacker_y - victim_y, 2) +
                       POWER(attacker_z - victim_z, 2)
                   )) as avg_dist
            FROM proximity_combat_position
            WHERE session_date = $1
            GROUP BY attacker_guid
        """, (session_date,))
        for r in (dist_rows or []):
            guid = r[0]
            if guid in stats_by_guid:
                stats_by_guid[guid]["avg_kill_distance"] = float(r[1] or 0)

        # Compute session averages for relative classification
        all_stats = list(stats_by_guid.values())
        session_stats = {}
        if all_stats:
            session_stats["avg_kills"] = sum(s.get("pcs_kills", s.get("kills", 0)) for s in all_stats) / len(all_stats)
            session_stats["avg_trades"] = sum(s.get("trade_kills", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_revives"] = sum(s.get("revives_given", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_kd"] = sum(
                s.get("pcs_kills", s.get("kills", 0)) / max(s.get("deaths", 1), 1)
                for s in all_stats
            ) / len(all_stats)
            session_stats["avg_dpm"] = sum(s.get("dpm", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_denied"] = sum(s.get("denied_time", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_time_dead_pct"] = sum(s.get("time_dead_pct", 0) for s in all_stats) / len(all_stats)

        # Classify each player relative to session
        result = {}
        for guid, s in stats_by_guid.items():
            result[guid] = self._classify_archetype(s, session_stats)
        return result, stats_by_guid

    @staticmethod
    def _classify_archetype(stats: dict, session_stats: dict = None) -> str:
        """Priority-based archetype classification using relative thresholds.
        session_stats: {avg_kills, avg_trades, avg_kd, avg_dpm, avg_denied,
                        avg_time_dead_pct} for relative comparison."""
        # Use PCS kills (authoritative) for KD, KIS kills for context scoring
        pcs_kills = stats.get("pcs_kills", stats.get("kills", 0))
        deaths = stats.get("deaths", 0)
        carrier_kills = stats.get("carrier_kills", 0)
        revives = stats.get("revives_given", 0)
        trades = stats.get("trade_kills", 0)
        crossfire = stats.get("crossfire_kills", 0)
        push_kills = stats.get("push_kills", 0)
        hs_pct = stats.get("headshot_pct", 0)
        dpm = stats.get("dpm", 0)
        denied_time = stats.get("denied_time", 0)
        time_dead_pct = stats.get("time_dead_pct", 0)
        kd = pcs_kills / max(deaths, 1)
        kills = pcs_kills  # use authoritative count for thresholds

        # Session averages for relative comparison
        ss = session_stats or {}
        avg_kills = ss.get("avg_kills", kills)
        avg_trades = ss.get("avg_trades", trades)
        avg_revives = ss.get("avg_revives", revives)
        avg_kd = ss.get("avg_kd", kd)
        avg_dpm = ss.get("avg_dpm", dpm)
        avg_denied = ss.get("avg_denied", denied_time)
        avg_tdp = ss.get("avg_time_dead_pct", time_dead_pct)

        # In competitive 3v3, everyone does everything. Archetypes must be
        # RELATIVE to the session — who stands out in what dimension.

        # Objective player — carrier kills are rare and always significant
        if carrier_kills >= 3 or stats.get("carrier_returns", 0) >= 2:
            return "objective_specialist"
        # Pressure engine — top DPM OR top kills+KD (sustained aggression)
        if dpm >= avg_dpm * 1.12 and kills >= avg_kills * 1.05:
            return "pressure_engine"
        if kills >= avg_kills * 1.1 and kd >= avg_kd * 1.15:
            return "pressure_engine"
        # Medic anchor — SIGNIFICANTLY more revives than average
        if revives >= avg_revives * 1.35 and revives >= 20:
            return "medic_anchor"
        # Silent assassin — high precision (real HS% = hs_hits/total_hits, typically 10-14%)
        if hs_pct >= 0.12 and kd >= avg_kd * 1.05:
            return "silent_assassin"
        # Chaos agent — high DPM but terrible KD (aggressive but reckless)
        if dpm >= avg_dpm * 0.95 and kd < avg_kd * 0.75:
            return "chaos_agent"
        # Wall breaker — high denied time (denies enemy spawns)
        if denied_time >= avg_denied * 1.2 and denied_time >= 100:
            return "wall_breaker"
        # Trade master — significantly more trades than average
        if trades >= avg_trades * 1.25 and trades >= 10:
            return "trade_master"
        # Survivor — best KD + stays alive
        if kd >= avg_kd * 1.2 and time_dead_pct <= avg_tdp * 0.85:
            return "survivor"
        # Fallback survivor — great KD even without low time_dead data
        if kd >= avg_kd * 1.3:
            return "survivor"
        # Push/crossfire focused
        if push_kills >= 8 or crossfire >= 5:
            return "frontline_warrior"
        return "frontline_warrior"

    # ── Team Synergy Score ──────────────────────────────────────────

    async def compute_team_synergy(self, session_date: str | date) -> dict:
        """Compute Team Synergy Score (5 axes) per stable player group.

        In stopwatch mode teams swap sides between R1/R2, so aggregating
        by faction (AXIS/ALLIES) mixes two different player compositions.
        Instead, we identify the two stable player groups and aggregate
        synergy per group.
        """
        sd = _to_date(session_date)

        groups = await self._build_player_groups(sd)
        if not groups:
            return {"status": "no_data", "session_date": str(sd), "groups": {}}

        rmap = groups['round_map']
        g2g = groups['guid_to_group']

        crossfire = await self._synergy_crossfire(sd, rmap)
        trade = await self._synergy_trade(sd, g2g)
        cohesion = await self._synergy_cohesion(sd, rmap)
        push = await self._synergy_push(sd, rmap)
        medic = await self._synergy_medic(sd, g2g)

        result_groups = {}
        for gkey in ('group_a', 'group_b'):
            cf = crossfire.get(gkey, 0)
            tr = trade.get(gkey, 0)
            co = cohesion.get(gkey, 0)
            pu = push.get(gkey, 0)
            me = medic.get(gkey, 0)
            composite = (cf * SYNERGY_WEIGHTS['crossfire'] +
                         tr * SYNERGY_WEIGHTS['trade'] +
                         co * SYNERGY_WEIGHTS['cohesion'] +
                         pu * SYNERGY_WEIGHTS['push'] +
                         me * SYNERGY_WEIGHTS['medic'])
            result_groups[gkey] = {
                "players": groups[f'{gkey}_players'],
                "crossfire": round(cf, 1),
                "trade": round(tr, 1),
                "cohesion": round(co, 1),
                "push": round(pu, 1),
                "medic": round(me, 1),
                "composite": round(composite, 1),
            }

        logger.info("Synergy computed for %s: A=%.1f (%s), B=%.1f (%s)",
                     sd,
                     result_groups.get('group_a', {}).get('composite', 0),
                     ', '.join(groups['group_a_players'][:3]),
                     result_groups.get('group_b', {}).get('composite', 0),
                     ', '.join(groups['group_b_players'][:3]))

        return {"status": "ok", "session_date": str(sd),
                "groups": result_groups, "weights": SYNERGY_WEIGHTS}

    async def _build_round_team_map(self, sd: date) -> dict:
        """Build (player_guid, round_number) -> faction mapping from PCS."""
        rows = await self.db.fetch_all(
            "SELECT player_guid, round_number, team "
            "FROM player_comprehensive_stats "
            "WHERE round_date = $1 AND team IN (1, 2)",
            (_to_date_str(sd),))
        result = {}
        for r in (rows or []):
            result[(r[0], r[1])] = 'AXIS' if r[2] == 1 else 'ALLIES'
        return result

    async def _build_player_groups(self, sd: date) -> dict | None:
        """Identify stable player groups across stopwatch rounds.

        In stopwatch, teams swap sides between R1/R2.  Group A is defined
        as AXIS (team=1) in the first R1 seen; Group B is ALLIES (team=2).
        For each round_start_unix we determine which faction corresponds to
        which group via player-overlap voting.

        Returns dict with group_a_players, group_b_players (sorted name lists),
        round_map (round_start_unix, faction) -> group key, and
        guid_to_group mapping, or None if no data.
        """
        rows = await self.db.fetch_all(
            "SELECT pcs.player_guid, pcs.player_name, pcs.round_number, "
            "pcs.team, r.round_start_unix "
            "FROM player_comprehensive_stats pcs "
            "JOIN rounds r ON r.id = pcs.round_id "
            "WHERE pcs.round_date = $1 AND pcs.round_number IN (1, 2) "
            "AND pcs.team IN (1, 2)",
            (_to_date_str(sd),))

        if not rows:
            return None

        # Find the first R1 (lowest round_start_unix with round_number=1)
        r1_entries = [r for r in rows if r[2] == 1]
        if not r1_entries:
            return None

        first_rsu = min(r[4] for r in r1_entries)

        # Group A = team 1 (AXIS) in first R1, Group B = team 2 (ALLIES)
        group_a_guids: set[str] = set()
        group_b_guids: set[str] = set()
        all_names: dict[str, str] = {}

        for guid, name, _rn, team, rsu in r1_entries:
            if rsu == first_rsu:
                if team == 1:
                    group_a_guids.add(guid)
                else:
                    group_b_guids.add(guid)

        # Track latest player names
        for guid, name, _rn, _team, _rsu in rows:
            all_names[guid] = name or guid[:8]

        # Build round_map: (round_start_unix, faction) -> group key
        round_map: dict[tuple, str] = {}
        round_start_set = {r[4] for r in rows}
        for rsu in round_start_set:
            axis_guids = {r[0] for r in rows if r[4] == rsu and r[3] == 1}
            a_overlap = len(axis_guids & group_a_guids)
            b_overlap = len(axis_guids & group_b_guids)
            if a_overlap >= b_overlap:
                round_map[(rsu, 'AXIS')] = 'group_a'
                round_map[(rsu, 'ALLIES')] = 'group_b'
            else:
                round_map[(rsu, 'AXIS')] = 'group_b'
                round_map[(rsu, 'ALLIES')] = 'group_a'

        # Assign any players not in initial groups (subs, late joins)
        for guid, _name, rn, team, rsu in rows:
            if guid not in group_a_guids and guid not in group_b_guids:
                faction = 'AXIS' if team == 1 else 'ALLIES'
                group = round_map.get((rsu, faction), 'group_b')
                if group == 'group_a':
                    group_a_guids.add(guid)
                else:
                    group_b_guids.add(guid)

        # Build guid -> group mapping
        guid_to_group: dict[str, str] = {}
        for g in group_a_guids:
            guid_to_group[g] = 'group_a'
        for g in group_b_guids:
            guid_to_group[g] = 'group_b'

        return {
            'group_a_players': sorted(all_names.get(g, g[:8])
                                      for g in group_a_guids),
            'group_b_players': sorted(all_names.get(g, g[:8])
                                      for g in group_b_guids),
            'round_map': round_map,
            'guid_to_group': guid_to_group,
        }

    async def _synergy_crossfire(self, sd: date, round_map: dict) -> dict:
        """Crossfire execution rate per player group (0-100)."""
        rows = await self.db.fetch_all("""
            SELECT round_start_unix, target_team,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE was_executed) as executed
            FROM proximity_crossfire_opportunity
            WHERE session_date = $1
            GROUP BY round_start_unix, target_team
        """, (sd,))
        totals: dict[str, int] = {'group_a': 0, 'group_b': 0}
        executed: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (rows or []):
            rsu, target_team = r[0], r[1]
            if target_team not in ('AXIS', 'ALLIES'):
                continue
            attacking = 'ALLIES' if target_team == 'AXIS' else 'AXIS'
            group = round_map.get((rsu, attacking))
            if not group:
                continue
            totals[group] += int(r[2] or 0)
            executed[group] += int(r[3] or 0)
        return {g: min(100, executed[g] / max(totals[g], 1) * 100)
                for g in ('group_a', 'group_b')}

    async def _synergy_trade(self, sd: date, guid_to_group: dict) -> dict:
        """Trade coverage per player group: % of team deaths avenged (0-100)."""
        trades = await self.db.fetch_all(
            "SELECT original_victim_guid, COUNT(*) "
            "FROM proximity_lua_trade_kill WHERE session_date = $1 "
            "GROUP BY original_victim_guid", (sd,))

        deaths_rows = await self.db.fetch_all(
            "SELECT player_guid, SUM(deaths) FROM player_comprehensive_stats "
            "WHERE round_date = $1 AND round_number IN (1, 2) AND team IN (1, 2) "
            "GROUP BY player_guid", (_to_date_str(sd),))

        tt: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (trades or []):
            group = guid_to_group.get(r[0])
            if group:
                tt[group] += int(r[1] or 0)

        td: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (deaths_rows or []):
            group = guid_to_group.get(r[0])
            if group:
                td[group] += int(r[1] or 0)

        return {g: min(100, tt[g] / max(td[g], 1) * 100)
                for g in ('group_a', 'group_b')}

    async def _synergy_cohesion(self, sd: date, round_map: dict) -> dict:
        """Team cohesion per player group: inverted average dispersion (0-100)."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, team, dispersion "
            "FROM proximity_team_cohesion WHERE session_date = $1", (sd,))
        group_dispersions: dict[str, list[float]] = {'group_a': [], 'group_b': []}
        for r in (rows or []):
            rsu, faction = r[0], r[1]
            if faction not in ('AXIS', 'ALLIES'):
                continue
            group = round_map.get((rsu, faction))
            if not group:
                continue
            group_dispersions[group].append(float(r[2] or 0))
        result = {}
        for g in ('group_a', 'group_b'):
            if group_dispersions[g]:
                avg_disp = sum(group_dispersions[g]) / len(group_dispersions[g])
                result[g] = max(0, min(100, (1 - avg_disp / COHESION_MAX_DISPERSION) * 100))
            else:
                result[g] = 0
        return result

    async def _synergy_push(self, sd: date, round_map: dict) -> dict:
        """Push quality per player group: quality + participation bonus (0-100)."""
        rows = await self.db.fetch_all(
            "SELECT round_start_unix, team, push_quality, participant_count "
            "FROM proximity_team_push WHERE session_date = $1", (sd,))
        gq: dict[str, list[float]] = {'group_a': [], 'group_b': []}
        gp: dict[str, list[float]] = {'group_a': [], 'group_b': []}
        for r in (rows or []):
            rsu, faction = r[0], r[1]
            if faction not in ('AXIS', 'ALLIES'):
                continue
            group = round_map.get((rsu, faction))
            if not group:
                continue
            gq[group].append(float(r[2] or 0))
            gp[group].append(float(r[3] or 0))
        result = {}
        for g in ('group_a', 'group_b'):
            if gq[g]:
                quality = min(80, (sum(gq[g]) / len(gq[g])) * 80)
                participation = min(20, (sum(gp[g]) / len(gp[g])) / 6 * 20)
                result[g] = min(100, quality + participation)
            else:
                result[g] = 0
        return result

    async def _synergy_medic(self, sd: date, guid_to_group: dict) -> dict:
        """Medic bond per player group: revive rate scaled to 0-100."""
        revives = await self.db.fetch_all(
            "SELECT victim_guid, COUNT(*) "
            "FROM proximity_kill_outcome "
            "WHERE session_date = $1 AND outcome = 'revived' "
            "GROUP BY victim_guid", (sd,))

        deaths_rows = await self.db.fetch_all(
            "SELECT player_guid, SUM(deaths) FROM player_comprehensive_stats "
            "WHERE round_date = $1 AND round_number IN (1, 2) AND team IN (1, 2) "
            "GROUP BY player_guid", (_to_date_str(sd),))

        tr: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (revives or []):
            group = guid_to_group.get(r[0])
            if group:
                tr[group] += int(r[1] or 0)

        td: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (deaths_rows or []):
            group = guid_to_group.get(r[0])
            if group:
                td[group] += int(r[1] or 0)

        return {g: min(100, tr[g] / max(td[g], 1) * 200)
                for g in ('group_a', 'group_b')}

    # ── Player Win Contribution (PWC) ────────────────────────────────

    # PWC weights (normal / objectives-absent)
    _PWC_W_KILLS = 0.30
    _PWC_W_DAMAGE = 0.15
    _PWC_W_OBJECTIVES = 0.25
    _PWC_W_REVIVES = 0.15
    _PWC_W_SURVIVAL = 0.15

    async def compute_win_contribution(self, session_date: str | date) -> dict:
        """Compute Player Win Contribution for every player in a session.

        Returns dict with 'mvp', 'players' list (sorted by total_pwc desc),
        and 'session_date'.
        """
        sd_str = _to_date_str(session_date)

        # 1. Fetch per-player per-round stats from PCS joined with rounds
        rows = await self.db.fetch_all("""
            SELECT pcs.player_guid, pcs.player_name, pcs.round_number,
                   r.map_name, pcs.team, r.winner_team,
                   pcs.kills, pcs.damage_given,
                   COALESCE(pcs.objectives_completed, 0)
                     + COALESCE(pcs.objectives_destroyed, 0)
                     + COALESCE(pcs.objectives_stolen, 0)
                     + COALESCE(pcs.objectives_returned, 0)
                     + COALESCE(pcs.dynamites_planted, 0)
                     + COALESCE(pcs.dynamites_defused, 0)
                     + COALESCE(pcs.constructions, 0) AS objectives,
                   pcs.revives_given,
                   pcs.time_played_minutes,
                   r.id AS round_id
            FROM player_comprehensive_stats pcs
            JOIN rounds r ON r.id = pcs.round_id
            WHERE pcs.round_date = $1
              AND pcs.round_number IN (1, 2)
              AND r.round_number IN (1, 2)
              AND pcs.time_played_seconds > 0
            ORDER BY r.id, pcs.player_guid
        """, (sd_str,))

        if not rows:
            return {"session_date": sd_str, "mvp": None, "players": []}

        # 2. Group by round_id to compute team totals
        from collections import defaultdict

        # round_id → list of player rows
        rounds_map: dict[int, list] = defaultdict(list)
        for r in rows:
            rounds_map[r[11]].append(r)  # r[11] = round_id

        # 3. Compute PWC per player per round
        # player_guid → {name, per_round: [...], total_pwc, won_pwc, lost_pwc, rounds_won, rounds_lost}
        player_data: dict[str, dict] = {}

        for round_id, round_rows in rounds_map.items():
            winner_team = round_rows[0][5]  # same for all rows in this round
            map_name = round_rows[0][3]
            round_number = round_rows[0][2]

            # Team totals (per team integer: 1=Allies, 2=Axis)
            team_kills: dict[int, int] = defaultdict(int)
            team_damage: dict[int, int] = defaultdict(int)
            team_objectives: dict[int, int] = defaultdict(int)
            team_revives: dict[int, int] = defaultdict(int)
            team_alive: dict[int, float] = defaultdict(float)
            team_count: dict[int, int] = defaultdict(int)

            for r in round_rows:
                t = r[4]  # team
                team_kills[t] += int(r[6] or 0)
                team_damage[t] += int(r[7] or 0)
                team_objectives[t] += int(r[8] or 0)
                team_revives[t] += int(r[9] or 0)
                team_alive[t] += float(r[10] or 0)
                team_count[t] += 1

            # Check if objectives are zero for ALL players in this round
            all_objectives_zero = all(int(r[8] or 0) == 0 for r in round_rows)

            for r in round_rows:
                guid = r[0]
                name = strip_et_colors(r[1] or guid[:8])
                t = r[4]
                p_kills = int(r[6] or 0)
                p_damage = int(r[7] or 0)
                p_objectives = int(r[8] or 0)
                p_revives = int(r[9] or 0)
                p_alive = float(r[10] or 0)

                tk = max(team_kills[t], 1)
                td = max(team_damage[t], 1)
                to = max(team_objectives[t], 1)
                tr = max(team_revives[t], 1)
                team_avg_alive = team_alive[t] / max(team_count[t], 1)
                ta = max(team_avg_alive, 0.01)

                kill_share = p_kills / tk
                damage_share = p_damage / td
                obj_share = p_objectives / to
                revive_share = p_revives / tr
                survival_share = min(p_alive / ta, 2.0)  # cap at 2x

                if all_objectives_zero:
                    # Redistribute 0.25 objectives weight: +0.10 kills, +0.10 damage, +0.05 revives
                    pwc = ((self._PWC_W_KILLS + 0.10) * kill_share
                           + (self._PWC_W_DAMAGE + 0.10) * damage_share
                           + (self._PWC_W_REVIVES + 0.05) * revive_share
                           + self._PWC_W_SURVIVAL * survival_share)
                else:
                    pwc = (self._PWC_W_KILLS * kill_share
                           + self._PWC_W_DAMAGE * damage_share
                           + self._PWC_W_OBJECTIVES * obj_share
                           + self._PWC_W_REVIVES * revive_share
                           + self._PWC_W_SURVIVAL * survival_share)

                won = (t == winner_team and winner_team in (1, 2))

                if guid not in player_data:
                    player_data[guid] = {
                        "guid": guid,
                        "name": name,
                        "total_pwc": 0.0,
                        "won_pwc": 0.0,
                        "lost_pwc": 0.0,
                        "rounds_won": 0,
                        "rounds_lost": 0,
                        "per_round": [],
                        "components": {
                            "kills": 0.0, "damage": 0.0,
                            "objectives": 0.0, "revives": 0.0,
                            "survival": 0.0,
                        },
                    }
                else:
                    # Update name to latest non-empty
                    if name and name != guid[:8]:
                        player_data[guid]["name"] = name

                pd = player_data[guid]
                pd["total_pwc"] += pwc
                if won:
                    pd["won_pwc"] += pwc
                    pd["rounds_won"] += 1
                else:
                    pd["lost_pwc"] += pwc
                    pd["rounds_lost"] += 1

                # Accumulate component contributions for stacked bars
                if all_objectives_zero:
                    pd["components"]["kills"] += (self._PWC_W_KILLS + 0.10) * kill_share
                    pd["components"]["damage"] += (self._PWC_W_DAMAGE + 0.10) * damage_share
                    pd["components"]["revives"] += (self._PWC_W_REVIVES + 0.05) * revive_share
                else:
                    pd["components"]["kills"] += self._PWC_W_KILLS * kill_share
                    pd["components"]["damage"] += self._PWC_W_DAMAGE * damage_share
                    pd["components"]["objectives"] += self._PWC_W_OBJECTIVES * obj_share
                    pd["components"]["revives"] += self._PWC_W_REVIVES * revive_share
                pd["components"]["survival"] += self._PWC_W_SURVIVAL * survival_share

                pd["per_round"].append({
                    "round_number": round_number,
                    "map_name": map_name,
                    "pwc": round(pwc, 4),
                    "won": won,
                    "kills": p_kills,
                    "damage": p_damage,
                    "objectives": p_objectives,
                    "revives": p_revives,
                })

        # 4. Compute WIS (Win Impact Score) per player
        players_list = []
        for guid, pd in player_data.items():
            avg_won = pd["won_pwc"] / max(pd["rounds_won"], 1)
            avg_lost = pd["lost_pwc"] / max(pd["rounds_lost"], 1)
            wis = avg_won - avg_lost
            total_rounds = pd["rounds_won"] + pd["rounds_lost"]
            waa = pd["won_pwc"] / max(total_rounds, 1)  # Win-Adjusted Average

            players_list.append({
                "guid": pd["guid"],
                "name": pd["name"],
                "total_pwc": round(pd["total_pwc"], 3),
                "wis": round(wis, 3),
                "waa": round(waa, 3),
                "rounds_won": pd["rounds_won"],
                "rounds_lost": pd["rounds_lost"],
                "components": {k: round(v, 3) for k, v in pd["components"].items()},
                "per_round": pd["per_round"],
            })

        # Sort by total_pwc descending
        players_list.sort(key=lambda p: p["total_pwc"], reverse=True)

        # 5. Session MVP = highest total_pwc across won rounds
        mvp = None
        if players_list:
            # MVP by won_pwc (contribution in rounds the team actually won)
            mvp_candidates = [p for p in players_list if p["rounds_won"] > 0]
            if mvp_candidates:
                mvp_player = max(mvp_candidates, key=lambda p: float(p["waa"]))
            else:
                mvp_player = players_list[0]
            mvp = {
                "guid": mvp_player["guid"],
                "name": mvp_player["name"],
                "total_pwc": mvp_player["total_pwc"],
                "wis": mvp_player["wis"],
            }

        return {
            "session_date": sd_str,
            "mvp": mvp,
            "players": players_list,
        }

    # ── Momentum Chart ──────────────────────────────────────────────

    async def compute_momentum(self, session_date: str | date) -> dict:
        """Compute per-round team momentum in 30-second windows.

        Momentum decays each window (×0.85) and gains from kills and objectives.
        Returns dual-line data (AXIS vs ALLIES) normalized to 0-100 per round.
        """
        sd = _to_date(session_date)

        # 1. Get all kills with team info
        kills = await self.db.fetch_all("""
            SELECT ko.round_number, ko.round_start_unix, ko.map_name,
                   ko.kill_time, ko.killer_guid, ko.victim_guid
            FROM proximity_kill_outcome ko
            WHERE ko.session_date = $1
            ORDER BY ko.round_start_unix, ko.kill_time
        """, (sd,))

        if not kills:
            return {"status": "no_data", "session_date": str(sd), "rounds": []}

        # 2. Build team map from PCS
        rtm = await self._build_round_team_map(sd)

        # Fallback: majority-vote per GUID
        guid_teams: dict[str, list[str]] = {}
        for (g, _rn), faction in rtm.items():
            guid_teams.setdefault(g, []).append(faction)
        guid_majority: dict[str, str] = {}
        for g, teams in guid_teams.items():
            guid_majority[g] = 'AXIS' if teams.count('AXIS') >= teams.count('ALLIES') else 'ALLIES'

        # Build short→long for PCS 8-char to proximity 32-char
        all_guids = set()
        for k in kills:
            all_guids.add(k[4])
            all_guids.add(k[5])
        short_to_long = {g[:8]: g for g in all_guids}

        def _get_team(guid: str, rn: int) -> str:
            """Resolve team for a GUID in a round. Try PCS 8-char lookup, then majority."""
            t = rtm.get((guid[:8], rn)) or rtm.get((guid, rn))
            if t:
                return t
            long = short_to_long.get(guid[:8], guid)
            t = rtm.get((long[:8], rn))
            if t:
                return t
            return guid_majority.get(guid[:8]) or guid_majority.get(guid) or 'AXIS'

        # 3. Get objective events: carrier pickups/secured
        carrier_events = await self.db.fetch_all("""
            SELECT round_number, round_start_unix, map_name,
                   carrier_team, pickup_time, outcome
            FROM proximity_carrier_event
            WHERE session_date = $1
        """, (sd,))

        # Construction events
        construction_events = await self.db.fetch_all("""
            SELECT round_number, round_start_unix, map_name,
                   player_team, event_time, event_type
            FROM proximity_construction_event
            WHERE session_date = $1
        """, (sd,))

        # 4. Group kills by round
        rounds_data: dict[tuple[int, int], dict] = {}  # (rn, start_unix) -> {map, kills, objs}
        for k in kills:
            rn, start_unix, map_name = k[0], k[1], k[2]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": map_name, "kills": [], "objectives": []}
            kill_time_ms = k[3] or 0
            killer_guid = k[4]
            killer_team = _get_team(killer_guid, rn)
            rounds_data[key]["kills"].append({
                "t_ms": kill_time_ms,
                "team": killer_team,
            })

        # Add carrier objectives
        for ce in (carrier_events or []):
            rn, start_unix = ce[0], ce[1]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": ce[2], "kills": [], "objectives": []}
            team = ce[3] or 'AXIS'
            pickup_ms = (ce[4] or 0)
            outcome = ce[5] or ''
            bonus = 15 if outcome != 'secured' else 30
            rounds_data[key]["objectives"].append({
                "t_ms": pickup_ms,
                "team": team,
                "bonus": bonus,
            })

        # Add construction objectives
        for ce in (construction_events or []):
            rn, start_unix = ce[0], ce[1]
            key = (rn, start_unix)
            if key not in rounds_data:
                rounds_data[key] = {"map_name": ce[2], "kills": [], "objectives": []}
            team = ce[3] or 'AXIS'
            event_time_ms = (ce[4] or 0)
            rounds_data[key]["objectives"].append({
                "t_ms": event_time_ms,
                "team": team,
                "bonus": 20,
            })

        # 5. Compute momentum per round
        WINDOW_MS = 30_000
        DECAY = 0.85
        KILL_IMPACT = 5.0
        result_rounds = []

        for (rn, start_unix), rd in sorted(rounds_data.items()):
            # Find max time in this round
            all_times = [k["t_ms"] for k in rd["kills"]]
            all_times += [o["t_ms"] for o in rd["objectives"]]
            if not all_times:
                continue
            max_time = max(all_times)

            # Build windows
            axis_raw = 0.0
            allies_raw = 0.0
            points = []

            n_windows = max(1, (max_time // WINDOW_MS) + 2)
            for w in range(n_windows):
                t_start = w * WINDOW_MS
                t_end = t_start + WINDOW_MS

                # Decay previous momentum
                axis_raw *= DECAY
                allies_raw *= DECAY

                # Sum kill impacts in this window
                for k in rd["kills"]:
                    if t_start <= k["t_ms"] < t_end:
                        if k["team"] == 'AXIS':
                            axis_raw += KILL_IMPACT
                            allies_raw -= KILL_IMPACT * 0.3
                        else:
                            allies_raw += KILL_IMPACT
                            axis_raw -= KILL_IMPACT * 0.3

                # Sum objective bonuses
                for o in rd["objectives"]:
                    if t_start <= o["t_ms"] < t_end:
                        if o["team"] == 'AXIS':
                            axis_raw += o["bonus"]
                        else:
                            allies_raw += o["bonus"]

                points.append({
                    "t_ms": t_start,
                    "axis_raw": axis_raw,
                    "allies_raw": allies_raw,
                })

            # 6. Normalize to 0-100 range
            all_vals = [abs(p["axis_raw"]) for p in points] + [abs(p["allies_raw"]) for p in points]
            max_val = max(all_vals) if all_vals else 1.0
            if max_val < 0.01:
                max_val = 1.0

            normalized = []
            for p in points:
                # Map from raw to 0-100 centered at 50
                axis_norm = 50 + (p["axis_raw"] / max_val) * 50
                allies_norm = 50 + (p["allies_raw"] / max_val) * 50
                # Clamp
                axis_norm = max(0, min(100, axis_norm))
                allies_norm = max(0, min(100, allies_norm))
                normalized.append({
                    "t_ms": p["t_ms"],
                    "axis": round(axis_norm, 1),
                    "allies": round(allies_norm, 1),
                })

            result_rounds.append({
                "round_number": rn,
                "map_name": rd["map_name"],
                "points": normalized,
            })

        return {
            "status": "ok",
            "session_date": str(sd),
            "rounds": result_rounds,
        }

    # ── Session Narrative ───────────────────────────────────────────

    async def generate_narrative(self, session_date: str | date) -> dict:
        """Generate a human-readable paragraph summarizing the session.

        Uses KIS, moments, synergy, archetypes, and PWC data.
        """
        sd = _to_date(session_date)
        sd_str = _to_date_str(sd)

        # 1. Ensure KIS is computed, then fetch leaderboard + archetypes
        await self.compute_session_kis(sd)
        kis_board = await self.get_kis_leaderboard(sd, limit=50)
        archetypes, stats = await self.classify_players(sd, kis_board)

        if not kis_board:
            return {"status": "no_data", "narrative": ""}

        # 2. Maps played
        map_rows = await self.db.fetch_all(
            "SELECT DISTINCT map_name FROM proximity_kill_outcome WHERE session_date = $1",
            (sd,))
        maps_played = ", ".join(strip_et_colors(r[0]) for r in (map_rows or []) if r[0])

        # 3. MVP (top KIS player)
        mvp = kis_board[0]
        mvp_name = strip_et_colors(mvp.get("name", "Unknown"))
        mvp_archetype = (archetypes.get(mvp["guid"], "frontline_warrior")).replace("_", " ")
        mvp_guid = mvp["guid"]
        mvp_stats = stats.get(mvp_guid, {})
        mvp_dpm = round(mvp_stats.get("dpm", 0), 1)
        mvp_kis = mvp.get("total_kis", 0)

        # 4. Medic anchor (most revives)
        medic_name = ""
        medic_revives = 0
        for guid, s in stats.items():
            rev = s.get("revives_given", 0)
            if rev > medic_revives:
                medic_revives = rev
                # Find name from kis_board
                entry = next((e for e in kis_board if e["guid"] == guid), None)
                medic_name = strip_et_colors(entry["name"]) if entry else guid[:8]

        # 5. Top moment
        moments = await self.detect_moments(sd, limit=1)
        top_moment_time = ""
        top_moment_narrative = ""
        if moments:
            m = moments[0]
            top_moment_time = m.get("time_formatted", "")
            top_moment_narrative = strip_et_colors(m.get("narrative", "an intense play"))

        # 6. Team synergy
        synergy = await self.compute_team_synergy(sd)
        better_team = ""
        better_composite = 0.0
        worse_composite = 0.0
        best_axis_name = ""
        best_axis_val = 0.0
        teams = synergy.get("groups", {})
        if teams:
            composites = {t: d.get("composite", 0) for t, d in teams.items()}
            if composites:
                better_team = max(composites, key=composites.get)
                worse_team = min(composites, key=composites.get)
                better_composite = composites.get(better_team, 0)
                worse_composite = composites.get(worse_team, 0)
                # Find the best synergy axis for the better team
                better_data = teams.get(better_team, {})
                for axis in ('crossfire', 'trade', 'cohesion', 'push', 'medic'):
                    val = better_data.get(axis, 0)
                    if val > best_axis_val:
                        best_axis_val = val
                        best_axis_name = axis

        # 7. Session ID from gaming sessions
        session_id_row = await self.db.fetch_one(
            "SELECT gaming_session_id FROM rounds "
            "WHERE round_date = $1 LIMIT 1",
            (sd_str,))
        session_id = session_id_row[0] if session_id_row else "?"

        # 8. Build narrative
        parts = [f"Session {session_id} on {maps_played}"]

        parts.append(
            f" was defined by {mvp_name}'s {mvp_archetype} performance "
            f"({mvp_dpm} DPM, {mvp_kis:.0f} KIS)"
        )

        if medic_name and medic_revives > 0:
            parts.append(f". {medic_name} anchored the team with {medic_revives} revives")

        if top_moment_narrative:
            parts.append(
                f". The session's defining moment came at {top_moment_time} "
                f"when {top_moment_narrative}"
            )

        if better_team and better_composite > 0:
            parts.append(
                f". Team synergy favored {better_team} "
                f"({better_composite:.0f} vs {worse_composite:.0f}), "
                f"driven by superior {best_axis_name} ({best_axis_val:.0f})"
            )

        narrative = "".join(parts) + "."

        return {
            "status": "ok",
            "session_date": sd_str,
            "narrative": narrative,
        }
