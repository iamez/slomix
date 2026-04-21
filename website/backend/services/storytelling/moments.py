"""StorytellingService mixin: moments methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

import time

from .base import (
    CARRIER_RETURN_WINDOW_MS,
    KILL_STREAK_WINDOW_MS,
    MULTIKILL_EXTENDED_WINDOW_MS,
    MULTIKILL_SHORT_WINDOW_MS,
    OBJECTIVE_EVENT_WINDOW_MS,
    TRADE_KILL_DELTA_MS,
    _compute_locks,
    _format_time_ms,
    _safe_short,
    _to_date,
    asyncio,
    date,
    logger,
    strip_et_colors,
    traceback,
    weapon_name,
)

# Module-level cache for `detect_moments` results. The 11 detectors fire
# 11 parallel DB queries + objective-event loader on every request; story
# page typically triggers both `/moments` (limit=N from user) and
# `/narrative` (internal call with limit=1) on the same session, so
# without caching we recompute identically twice.
#
# Keyed by (session_date, limit) — moments are a pure function of the
# data in the DB for that date, and the limit determines type-diversity
# truncation so we cache per-limit to preserve exact behavior.
_MOMENTS_CACHE: dict[tuple[date, int], tuple[list, float]] = {}
_MOMENTS_CACHE_MAX = 32  # 16 sessions × 2 typical limits
_MOMENTS_TTL_TODAY = 300    # 5 min — new rounds may still arrive
_MOMENTS_TTL_HISTORICAL = 3600  # 1 h — stable, bounded for retro-corrections


def _moments_cache_ttl(sd: date) -> int:
    return _MOMENTS_TTL_TODAY if sd >= date.today() else _MOMENTS_TTL_HISTORICAL


def _moments_cache_evict_oldest() -> None:
    if len(_MOMENTS_CACHE) <= _MOMENTS_CACHE_MAX:
        return
    oldest = min(_MOMENTS_CACHE, key=lambda k: _MOMENTS_CACHE[k][1])
    _MOMENTS_CACHE.pop(oldest, None)


class _MomentsMixin:
    """Moments methods for StorytellingService."""

    async def detect_moments(self, session_date: str | date, limit: int = 10) -> list:
        """Detect highlight-reel moments for a session across 11 detectors.

        Results are memoized at module level per (session_date, limit) —
        TTL 5 min for today, 1 h for historical. First caller computes,
        subsequent callers hit the cache.
        """
        sd = _to_date(session_date)
        now = time.time()
        ttl = _moments_cache_ttl(sd)
        key = (sd, limit)
        cached = _MOMENTS_CACHE.get(key)
        if cached and (now - cached[1]) < ttl:
            return cached[0]

        # Double-check under lock to prevent concurrent recompute when
        # several coroutines all miss the cache before any of them writes.
        lock = _compute_locks.get(f"moments:{sd}:{limit}")
        async with lock:
            cached = _MOMENTS_CACHE.get(key)
            if cached and (time.time() - cached[1]) < ttl:
                return cached[0]

            result = await self._detect_moments_uncached(sd, limit)
            _MOMENTS_CACHE[key] = (result, time.time())
            _moments_cache_evict_oldest()
            return result

    async def _detect_moments_uncached(self, sd: date, limit: int) -> list:
        """Run all 11 detectors, diversify by type, sort by stars, truncate."""
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
        # Run all detectors in parallel — each hits DB independently (-1.5s per session)
        results = await asyncio.gather(
            *(detector(sd) for detector in detectors),
            return_exceptions=True,
        )
        for detector, result in zip(detectors, results, strict=True):
            if isinstance(result, Exception):
                logger.error("Moment detector %s failed: %s\n%s",
                             detector.__name__, result,
                             "".join(traceback.format_exception(type(result), result, result.__traceback__)))
                continue
            logger.info("Moment detector %s returned %d results", detector.__name__, len(result))
            moments.extend(result)

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
        # RANGE BETWEEN N PRECEDING cannot accept query params in PostgreSQL,
        # so we interpolate the trusted module constant directly.
        rows = await self.db.fetch_all(f"""
            WITH windowed AS (
                SELECT killer_guid, killer_name, kill_time, round_number, map_name,
                       round_start_unix,
                       COUNT(*) OVER (
                           PARTITION BY killer_guid, round_start_unix
                           ORDER BY kill_time
                           RANGE BETWEEN {KILL_STREAK_WINDOW_MS} PRECEDING AND CURRENT ROW
                       ) AS streak
                FROM proximity_kill_outcome
                WHERE session_date = $1
            )
            SELECT killer_guid, killer_name, kill_time, round_number, map_name,
                   round_start_unix, streak
            FROM windowed
            WHERE streak >= 3
            ORDER BY streak DESC, kill_time
        """, (sd,))  # nosec B608 - trusted module constant, not user input

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
                    "killer_name": strip_et_colors(killer_name or _safe_short(killer_guid)),
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
                if abs(kt - evt_time) <= OBJECTIVE_EVENT_WINDOW_MS:
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
                AND (cr.return_time - ck.kill_time) BETWEEN 0 AND $2
            ORDER BY ck.kill_time
        """, (sd, CARRIER_RETURN_WINDOW_MS))

        moments = []
        for r in (rows or []):
            killer_name = strip_et_colors(r[1] or _safe_short(r[0]))
            returner_name = strip_et_colors(r[4] or _safe_short(r[3]))
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
        """Detector C: Survived 3v1+ focus fire.

        Joins `combat_engagement` to recover `end_time_ms` — without it
        the moment carries `time_ms: 0` and the UI renders every focus
        survival at the pistol round.

        The JOIN key mirrors `combat_engagement`'s UNIQUE constraint
        `(session_date, round_number, round_start_unix, engagement_id)`
        so multiple rounds on the same day can't collide. `map_name` is
        added as a final safety net (different maps share engagement_id
        counters when rounds start from 1 again). LEFT JOIN keeps rows
        whose engagement never landed — `time_ms` then stays 0.
        """
        rows = await self.db.fetch_all("""
            SELECT ff.target_guid, ff.target_name, ff.attacker_count, ff.focus_score,
                   ff.round_number, ff.map_name, ff.engagement_id,
                   ce.end_time_ms
            FROM proximity_focus_fire ff
            LEFT JOIN combat_engagement ce
                   ON ce.session_date = ff.session_date
                  AND ce.round_number = ff.round_number
                  AND ce.round_start_unix = ff.round_start_unix
                  AND ce.engagement_id = ff.engagement_id
                  AND ce.map_name = ff.map_name
            WHERE ff.session_date = $1 AND ff.attacker_count >= 3
                AND ff.focus_score >= 0.5
            ORDER BY ff.focus_score DESC
            LIMIT 10
        """, (sd,))

        moments = []
        for r in (rows or []):
            name = strip_et_colors(r[1] or _safe_short(r[0]))
            attackers = int(r[2])
            score = float(r[3])
            stars = 3 if attackers == 3 else (4 if attackers == 4 else 5)
            moments.append({
                "type": "focus_survival",
                "round_number": r[4],
                "map_name": r[5],
                "time_ms": int(r[7]) if r[7] is not None else 0,
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
            WHERE session_date = $1 AND delta_ms <= $2
            ORDER BY delta_ms ASC
            LIMIT 10
        """, (sd, TRADE_KILL_DELTA_MS))

        moments = []
        for r in (rows or []):
            trader_name = strip_et_colors(r[1] or _safe_short(r[0]))
            victim_name = strip_et_colors(r[3] or _safe_short(r[2]))
            avenger_target = strip_et_colors(r[5] or _safe_short(r[4]))
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
            name = strip_et_colors(r[1] or _safe_short(r[0]))
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
            name = strip_et_colors(r[1] or _safe_short(r[0]))
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
            carrier_name = strip_et_colors(r[1] or _safe_short(r[0]))
            killer_name = strip_et_colors(r[3] or _safe_short(r[2]))
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
            name = strip_et_colors(r[1] or _safe_short(r[0]))
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
        # RANGE BETWEEN N PRECEDING cannot accept query params in PostgreSQL,
        # so we interpolate the trusted module constant directly.
        rows = await self.db.fetch_all(f"""
            WITH revives AS (
                SELECT reviver_guid, reviver_name, outcome_time,
                       round_number, map_name, round_start_unix,
                       COUNT(*) OVER (
                           PARTITION BY reviver_guid, round_start_unix
                           ORDER BY outcome_time
                           RANGE BETWEEN {OBJECTIVE_EVENT_WINDOW_MS} PRECEDING AND CURRENT ROW
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
        """, (sd,))  # nosec B608 - trusted module constant, not user input

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
                "killer": strip_et_colors(r[2] or _safe_short(r[1])),
                "killer_team": r[3],
                "victim_guid": r[4],
                "victim": strip_et_colors(r[5] or _safe_short(r[4])),
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
                        if team_kills[j]["time"] - window_start > OBJECTIVE_EVENT_WINDOW_MS:
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
                "killer": strip_et_colors(r[2] or _safe_short(r[1])),
                "killer_team": r[3],
                "victim_guid": r[4],
                "victim": strip_et_colors(r[5] or _safe_short(r[4])),
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
                    max_window = MULTIKILL_SHORT_WINDOW_MS if len(window_kills) < 3 else MULTIKILL_EXTENDED_WINDOW_MS
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
                    if abs(first_kill["time"] - evt_time) <= OBJECTIVE_EVENT_WINDOW_MS:
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

