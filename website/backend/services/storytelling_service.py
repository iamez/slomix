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
import logging
import re
import traceback
from datetime import date, datetime
from typing import Optional, Union
from website.backend.logging_config import get_app_logger

logger = get_app_logger("storytelling")

# Per-session locks to prevent concurrent TOCTOU races on lazy compute
_compute_locks: dict[str, asyncio.Lock] = {}

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

# ── Team Synergy Score constants ────────────────────────────────
SYNERGY_WEIGHTS = {
    'crossfire': 0.25,
    'trade': 0.25,
    'cohesion': 0.20,
    'push': 0.15,
    'medic': 0.15,
}
COHESION_MAX_DISPERSION = 1500      # Game units; above this = 0 cohesion


def _to_date(val: Union[str, date]) -> date:
    """Normalize to datetime.date for asyncpg DATE params (proximity tables use DATE type)."""
    if isinstance(val, date):
        return val
    return datetime.strptime(val, "%Y-%m-%d").date()


def _to_date_str(val: Union[str, date]) -> str:
    """Normalize to YYYY-MM-DD string for TEXT columns (player_comprehensive_stats.round_date)."""
    if isinstance(val, date):
        return val.isoformat()
    datetime.strptime(val, "%Y-%m-%d")  # validate
    return val


def _strip_et_colors(name: str) -> str:
    """Remove ET:Legacy color codes (^0-^9, ^a-^z, ^A-^Z) from names."""
    if not name:
        return name
    return re.sub(r'\^[0-9a-zA-Z]', '', name)


class StorytellingService:
    def __init__(self, db):
        self.db = db

    async def compute_session_kis(self, session_date: Union[str, date], force: bool = False) -> dict:
        """Compute KIS for all kills in a session. Returns summary stats."""
        sd = _to_date(session_date)
        lock_key = str(sd)
        if lock_key not in _compute_locks:
            _compute_locks[lock_key] = asyncio.Lock()

        async with _compute_locks[lock_key]:
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

        # 3. Score each kill
        scored = []
        for kill in kills:
            impact = self._score_kill(kill, carrier_kills, carrier_returns,
                                      pushes, crossfires, spawn_timings, victim_classes)
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
                 total_impact, is_carrier_kill, is_during_push, is_crossfire, is_objective_area,
                 kill_time_ms)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
            """, batch)

        logger.info("KIS computed for %s: %d kills scored", sd, len(scored))
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

        # TODO: Implement when per-kill distance data available
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

    # ── Match Moments Detection ──

    async def detect_moments(self, session_date: Union[str, date], limit: int = 10) -> list:
        """Detect highlight-reel moments for a session across 5 detectors."""
        sd = _to_date(session_date)
        moments = []

        # Run all 5 detectors
        detectors = [
            self._detect_kill_streaks,
            self._detect_carrier_chains,
            self._detect_focus_survivals,
            self._detect_push_successes,
            self._detect_trade_chains,
        ]
        for detector in detectors:
            try:
                found = await detector(sd)
                logger.info("Moment detector %s returned %d results", detector.__name__, len(found))
                moments.extend(found)
            except Exception as e:
                logger.error("Moment detector %s failed: %s\n%s",
                             detector.__name__, e, traceback.format_exc())

        # Sort by impact_stars desc, then by time
        moments.sort(key=lambda m: (-m["impact_stars"], m.get("time_ms", 0)))
        return moments[:limit]

    async def _detect_kill_streaks(self, sd: date) -> list:
        """Detector A: Multi-kill streaks (3+ kills within 10s window)."""
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
                    "killer_name": _strip_et_colors(killer_name or killer_guid[:8]),
                    "kill_time": kill_time,
                    "round_number": round_number,
                    "map_name": map_name,
                    "streak": streak,
                }

        moments = []
        for info in seen.values():
            streak = info["streak"]
            stars = min(5, streak - 1)  # 3-kill=2★, 4-kill=3★, 5-kill=4★, 6+=5★
            name = info["killer_name"]
            moments.append({
                "type": "kill_streak",
                "round_number": info["round_number"],
                "map_name": info["map_name"],
                "time_ms": info["kill_time"] or 0,
                "player": name,
                "narrative": f"{name} went on a {streak}-kill streak in 10s",
                "impact_stars": stars,
                "detail": {"streak_count": streak, "killer_guid": info["killer_guid"]},
            })
        return moments

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
            killer_name = _strip_et_colors(r[1] or r[0][:8])
            returner_name = _strip_et_colors(r[4] or r[3][:8])
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
            name = _strip_et_colors(r[1] or r[0][:8])
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
            trader_name = _strip_et_colors(r[1] or r[0][:8])
            victim_name = _strip_et_colors(r[3] or r[2][:8])
            avenger_target = _strip_et_colors(r[5] or r[4][:8])
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

    async def get_kis_leaderboard(self, session_date: Union[str, date], limit: int = 20) -> list:
        """Get KIS leaderboard for a session, including server-side archetype."""
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

        kis_entries = [
            {
                "guid": r[0], "name": _strip_et_colors(r[1] or r[0][:8]),
                "total_kis": float(r[2] or 0), "kills": int(r[3] or 0),
                "carrier_kills": int(r[4] or 0), "push_kills": int(r[5] or 0),
                "crossfire_kills": int(r[6] or 0), "avg_impact": float(r[7] or 0),
            }
            for r in (rows or [])
        ]

        # Enrich with server-side archetypes
        if kis_entries:
            archetypes = await self.classify_players(sd, kis_entries)
            for entry in kis_entries:
                entry["archetype"] = archetypes.get(entry["guid"], "frontline_warrior")

        return kis_entries

    # ── Server-side archetype classification ──────────────────────────

    async def classify_players(
        self, session_date: date, kis_entries: list[dict]
    ) -> dict[str, str]:
        """Classify each player's archetype using all available data.

        Returns {guid: archetype_string}.
        """
        guids = [e["guid"] for e in kis_entries]
        if not guids:
            return {}

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
            }

        # 1. PCS stats: kills, deaths, headshots, revives (PCS kills are authoritative)
        pcs_rows = await self.db.fetch_all("""
            SELECT player_guid,
                   SUM(kills) as pcs_kills,
                   SUM(deaths) as deaths,
                   SUM(headshot_kills) as hs,
                   SUM(revives_given) as revives,
                   SUM(objectives_returned) as obj_returned
            FROM player_comprehensive_stats
            WHERE round_date = $1
            GROUP BY player_guid
        """, (_to_date_str(session_date),))
        for r in (pcs_rows or []):
            guid = r[0]
            if guid in stats_by_guid:
                s = stats_by_guid[guid]
                s["pcs_kills"] = int(r[1] or 0)  # authoritative kill count
                s["deaths"] = int(r[2] or 0)
                s["headshot_kills"] = int(r[3] or 0)
                pcs_kills = s["pcs_kills"]
                s["headshot_pct"] = s["headshot_kills"] / pcs_kills if pcs_kills > 0 else 0.0
                s["revives_given"] = int(r[4] or 0)
                s["carrier_returns"] = int(r[5] or 0)

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
            session_stats["avg_kills"] = sum(s.get("kills", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_trades"] = sum(s.get("trade_kills", 0) for s in all_stats) / len(all_stats)
            session_stats["avg_kd"] = sum(s.get("kills", 0) / max(s.get("deaths", 1), 1) for s in all_stats) / len(all_stats)

        # Classify each player relative to session
        result = {}
        for guid, s in stats_by_guid.items():
            result[guid] = self._classify_archetype(s, session_stats)
        return result

    @staticmethod
    def _classify_archetype(stats: dict, session_stats: dict = None) -> str:
        """Priority-based archetype classification using relative thresholds.
        session_stats: {avg_kills, avg_trades, avg_kd} for relative comparison."""
        # Use PCS kills (authoritative) for KD, KIS kills for context scoring
        pcs_kills = stats.get("pcs_kills", stats.get("kills", 0))
        deaths = stats.get("deaths", 0)
        carrier_kills = stats.get("carrier_kills", 0)
        revives = stats.get("revives_given", 0)
        trades = stats.get("trade_kills", 0)
        crossfire = stats.get("crossfire_kills", 0)
        avg_impact = stats.get("avg_impact", 0)
        push_kills = stats.get("push_kills", 0)
        hs_pct = stats.get("headshot_pct", 0)
        avg_distance = stats.get("avg_kill_distance", 0)
        kd = pcs_kills / max(deaths, 1)
        kills = pcs_kills  # use authoritative count for thresholds

        # Session averages for relative comparison
        ss = session_stats or {}
        avg_session_kills = ss.get("avg_kills", kills)
        avg_session_trades = ss.get("avg_trades", trades)

        # Objective player — carrier kills are rare and always significant
        if carrier_kills >= 3 or stats.get("carrier_returns", 0) >= 2:
            return "objective_specialist"
        # Medic — high revives, low KD
        if revives >= 8 and kd < 1.5:
            return "medic_anchor"
        # Sniper — long range, precise
        if avg_distance >= 600 and hs_pct >= 0.15 and kd >= 1.5:
            return "silent_assassin"
        # Pressure engine — top fragger with highest kills + impact
        if kills >= avg_session_kills * 1.15 and avg_impact >= 4.0 and push_kills >= 5:
            return "pressure_engine"
        # Chaos agent — dies a lot but makes an impact
        if deaths >= kills * 1.3 and kills >= 10 and avg_impact >= 3:
            return "chaos_agent"
        # Survivor — rarely dies
        if kd >= 2.0 and deaths <= kills * 0.6:
            return "survivor"
        # Trade master — significantly more trades than average
        if trades >= avg_session_trades * 1.3 and trades >= 10:
            return "trade_master"
        # Wall breaker — push/crossfire focused
        if push_kills >= kills * 0.6 or crossfire >= 5:
            return "wall_breaker"
        return "frontline_warrior"

    # ── Team Synergy Score ──────────────────────────────────────────

    async def compute_team_synergy(self, session_date: Union[str, date]) -> dict:
        """Compute Team Synergy Score (5 axes) per faction for a session."""
        sd = _to_date(session_date)

        round_team_map = await self._build_round_team_map(sd)
        if not round_team_map:
            return {"status": "no_data", "session_date": str(sd), "teams": {}}

        crossfire = await self._synergy_crossfire(sd)
        trade = await self._synergy_trade(sd, round_team_map)
        cohesion = await self._synergy_cohesion(sd)
        push = await self._synergy_push(sd)
        medic = await self._synergy_medic(sd, round_team_map)

        teams = {}
        for faction in ('AXIS', 'ALLIES'):
            cf = crossfire.get(faction, 0)
            tr = trade.get(faction, 0)
            co = cohesion.get(faction, 0)
            pu = push.get(faction, 0)
            me = medic.get(faction, 0)
            composite = (cf * SYNERGY_WEIGHTS['crossfire'] +
                         tr * SYNERGY_WEIGHTS['trade'] +
                         co * SYNERGY_WEIGHTS['cohesion'] +
                         pu * SYNERGY_WEIGHTS['push'] +
                         me * SYNERGY_WEIGHTS['medic'])
            teams[faction] = {
                "crossfire": round(cf, 1),
                "trade": round(tr, 1),
                "cohesion": round(co, 1),
                "push": round(pu, 1),
                "medic": round(me, 1),
                "composite": round(composite, 1),
            }

        logger.info("Synergy computed for %s: AXIS=%.1f, ALLIES=%.1f",
                     sd, teams.get('AXIS', {}).get('composite', 0),
                     teams.get('ALLIES', {}).get('composite', 0))

        return {"status": "ok", "session_date": str(sd), "teams": teams,
                "weights": SYNERGY_WEIGHTS}

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

    async def _synergy_crossfire(self, sd: date) -> dict:
        """Crossfire execution rate per attacking faction (0-100)."""
        rows = await self.db.fetch_all("""
            SELECT target_team,
                   COUNT(*) as total,
                   COUNT(*) FILTER (WHERE was_executed) as executed
            FROM proximity_crossfire_opportunity
            WHERE session_date = $1
            GROUP BY target_team
        """, (sd,))
        result = {}
        for r in (rows or []):
            target_team = r[0]
            if target_team not in ('AXIS', 'ALLIES'):
                continue
            attacking = 'ALLIES' if target_team == 'AXIS' else 'AXIS'
            result[attacking] = min(100, (int(r[2] or 0) / max(int(r[1] or 1), 1)) * 100)
        return result

    async def _synergy_trade(self, sd: date, rtm: dict) -> dict:
        """Trade coverage per faction: % of team deaths avenged (0-100)."""
        trades = await self.db.fetch_all(
            "SELECT original_victim_guid, round_number, COUNT(*) "
            "FROM proximity_lua_trade_kill WHERE session_date = $1 "
            "GROUP BY original_victim_guid, round_number", (sd,))

        deaths_rows = await self.db.fetch_all(
            "SELECT team, SUM(deaths) FROM player_comprehensive_stats "
            "WHERE round_date = $1 AND team IN (1, 2) GROUP BY team", (_to_date_str(sd),))

        # Build guid-only fallback map (majority team assignment)
        guid_teams: dict[str, list[str]] = {}
        for (g, _rn), faction in rtm.items():
            guid_teams.setdefault(g, []).append(faction)
        guid_majority: dict[str, str] = {}
        for g, teams in guid_teams.items():
            guid_majority[g] = 'AXIS' if teams.count('AXIS') >= teams.count('ALLIES') else 'ALLIES'

        tt = {'AXIS': 0, 'ALLIES': 0}
        for r in (trades or []):
            team = rtm.get((r[0], r[1])) or guid_majority.get(r[0])
            if team:
                tt[team] += int(r[2] or 0)

        td = {'AXIS': 0, 'ALLIES': 0}
        for r in (deaths_rows or []):
            td['AXIS' if r[0] == 1 else 'ALLIES'] = int(r[1] or 0)

        return {f: min(100, tt[f] / max(td[f], 1) * 100) for f in ('AXIS', 'ALLIES')}

    async def _synergy_cohesion(self, sd: date) -> dict:
        """Team cohesion per faction: inverted average dispersion (0-100)."""
        rows = await self.db.fetch_all(
            "SELECT team, AVG(dispersion) FROM proximity_team_cohesion "
            "WHERE session_date = $1 GROUP BY team", (sd,))
        result = {}
        for r in (rows or []):
            if r[0] not in ('AXIS', 'ALLIES'):
                continue
            avg_disp = float(r[1] or 0)
            result[r[0]] = max(0, min(100, (1 - avg_disp / COHESION_MAX_DISPERSION) * 100))
        return result

    async def _synergy_push(self, sd: date) -> dict:
        """Push quality per faction: quality + participation bonus (0-100)."""
        rows = await self.db.fetch_all(
            "SELECT team, AVG(push_quality), AVG(participant_count) "
            "FROM proximity_team_push WHERE session_date = $1 GROUP BY team", (sd,))
        result = {}
        for r in (rows or []):
            if r[0] not in ('AXIS', 'ALLIES'):
                continue
            quality = min(80, float(r[1] or 0) * 80)
            participation = min(20, float(r[2] or 0) / 6 * 20)
            result[r[0]] = min(100, quality + participation)
        return result

    async def _synergy_medic(self, sd: date, rtm: dict) -> dict:
        """Medic bond per faction: revive rate scaled to 0-100 (50% revive rate = 100)."""
        revives = await self.db.fetch_all(
            "SELECT victim_guid, round_number, COUNT(*) "
            "FROM proximity_kill_outcome "
            "WHERE session_date = $1 AND outcome = 'revived' "
            "GROUP BY victim_guid, round_number", (sd,))

        deaths_rows = await self.db.fetch_all(
            "SELECT team, SUM(deaths) FROM player_comprehensive_stats "
            "WHERE round_date = $1 AND team IN (1, 2) GROUP BY team", (_to_date_str(sd),))

        # Build guid-only fallback map (majority team assignment)
        guid_teams: dict[str, list[str]] = {}
        for (g, _rn), faction in rtm.items():
            guid_teams.setdefault(g, []).append(faction)
        guid_majority: dict[str, str] = {}
        for g, teams in guid_teams.items():
            guid_majority[g] = 'AXIS' if teams.count('AXIS') >= teams.count('ALLIES') else 'ALLIES'

        tr = {'AXIS': 0, 'ALLIES': 0}
        for r in (revives or []):
            team = rtm.get((r[0], r[1])) or guid_majority.get(r[0])
            if team:
                tr[team] += int(r[2] or 0)

        td = {'AXIS': 0, 'ALLIES': 0}
        for r in (deaths_rows or []):
            td['AXIS' if r[0] == 1 else 'ALLIES'] = int(r[1] or 0)

        return {f: min(100, tr[f] / max(td[f], 1) * 200) for f in ('AXIS', 'ALLIES')}
