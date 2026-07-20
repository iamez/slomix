"""StorytellingService mixin: kis methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from website.backend.services.session_scope import resolve_gaming_session_scope

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
    REINF_MULT_TIERS,
    SOLO_CLUTCH_MULTIPLIER,
    SOLO_CLUTCH_THRESHOLD,
    SPAWN_TIMING_WINDOW_MS,
    _compute_locks,
    _to_date,
    asyncio,
    date,
    logger,
    round_ctx_key,
)

# Bump on any change to _score_kill's multipliers/logic so
# _compute_session_kis_locked's cache-check stops serving stale rows
# scored under the old formula (migration 060 adds the storage column;
# codex, PR #478 follow-up audit finding #9).
FORMULA_VERSION = "kis-v2"


def _scope_row_filter(
    round_keys: tuple[tuple[int, str, int], ...] | None,
    dates: tuple[date, ...],
    prefix: str = "",
) -> tuple[str, tuple]:
    """SQL WHERE fragment + params scoping a query to this KIS compute.

    With round_keys (gsid-native path): filters by the EXACT
    (round_start_unix, map_name, round_number) triples the resolved
    GamingSessionScope contains — precise even when another, unrelated
    gaming session shares a calendar date with this one. A bare
    session_date filter here would silently pull that OTHER session's
    kills into this compute and stamp them with the wrong
    gaming_session_id (Copilot review on #525).

    Without round_keys (legacy session_date path): unchanged
    `session_date = ANY($1)` — the pre-existing, still-imprecise-on-a-
    shared-date behaviour of the two still-unconverted kill-impact
    endpoints, deliberately left untouched by this PR (see
    compute_session_kis's docstring).
    """
    col = f"{prefix}." if prefix else ""
    if round_keys:
        starts = [rk[0] for rk in round_keys]
        maps = [rk[1] for rk in round_keys]
        nums = [rk[2] for rk in round_keys]
        clause = (
            f"({col}round_start_unix, {col}map_name, {col}round_number) IN "
            "(SELECT * FROM unnest($1::bigint[], $2::varchar[], $3::int[]))"
        )
        return clause, (starts, maps, nums)
    return f"{col}session_date = ANY($1)", (list(dates),)


def _graduated_reinf_mult(victim_reinf_seconds: float) -> float:
    """Look up the graduated reinf multiplier for the given wait in seconds.

    Uses REINF_MULT_TIERS; first tier whose inclusive upper bound is at
    least the wait wins (so r=10.0 maps to the ≤10 tier, not the next).
    Negative/zero wait falls into the shortest tier.
    """
    r = float(victim_reinf_seconds or 0.0)
    for upper, mult in REINF_MULT_TIERS:
        if r <= upper:
            return mult
    return REINF_MULT_TIERS[-1][1]


class _KisMixin:
    """Kis methods for StorytellingService."""

    async def compute_session_kis(self, session_date: str | date, force: bool = False) -> dict:
        """Compute KIS for all kills in a session. Returns summary stats.

        Legacy single-date entrypoint — unchanged behaviour, kept for the
        existing session_date-scoped callers (storytelling_router.py's
        kill-impact endpoints). For a gsid-known caller, prefer
        compute_session_kis_for_gsid() below: it resolves the FULL gaming
        session scope (every date fragment a midnight-crossing session
        touches), not just the one date given here.
        """
        sd = _to_date(session_date)
        lock_key = str(sd)
        async with _compute_locks.get(lock_key):
            return await self._compute_kis_for_dates_locked((sd,), None, force)

    async def compute_session_kis_for_gsid(
        self, gaming_session_id: int, force: bool = False
    ) -> dict:
        """Gsid-native entrypoint (Codex §5/§8 SS-B).

        Resolves the caller's gaming_session_id through the shared
        GamingSessionScope resolver (session_scope.py) instead of a single
        session_date, so a session that crosses midnight gets ALL of its
        date fragments covered by one fetch/store/lock instead of only
        whichever date the caller happened to ask about (the same class of
        bug BOX score's PR-A fixed for scores; this is the same fix for
        kill-impact). Every row this path writes is stamped with
        gaming_session_id (migration 063) so a scope-wide lookup no longer
        needs to enumerate dates by hand.
        """
        scope = await resolve_gaming_session_scope(self.db, gaming_session_id=gaming_session_id)
        dates = tuple(_to_date(d) for d in scope.dates)
        lock_key = f"gsid:{gaming_session_id}"
        async with _compute_locks.get(lock_key):
            return await self._compute_kis_for_dates_locked(
                dates, gaming_session_id, force, round_keys=scope.round_keys
            )

    async def _compute_kis_for_dates_locked(
        self,
        dates: tuple[date, ...],
        gaming_session_id: int | None,
        force: bool,
        round_keys: tuple[tuple[int, str, int], ...] | None = None,
    ) -> dict:
        """Inner compute logic — must be called while holding the session lock.

        `dates` may be a single-element tuple (legacy session_date path,
        gaming_session_id=None, round_keys=None — filtering stays exactly
        `session_date = ANY($1)`, unchanged) or the full multi-date scope of
        a gaming session (gsid-native path, round_keys from the resolved
        GamingSessionScope — filtering switches to the precise round-key
        triple match _scope_row_filter builds, immune to another session
        sharing a calendar date with this one).
        """
        date_list = list(dates)
        row_filter, scope_params = _scope_row_filter(round_keys, dates)
        ko_row_filter, _ = _scope_row_filter(round_keys, dates, prefix="ko")
        fv_placeholder = f"${len(scope_params) + 1}"
        # Serve the cache only when it is BOTH current-formula AND fresh:
        # - formula_version guards against serving scores from an older
        #   formula after a version bump (#484).
        # - freshness guards against the subtler staleness where proximity
        #   context (kills, combat positions, spawn timing, ...) lands AFTER
        #   the KIS cache was written — a late re-import. The formula_version
        #   is unchanged there, so without a timestamp check the stale cache
        #   would be served forever. If any KIS input's created_at is newer
        #   than the newest cached row, fall through and recompute.
        if not force:
            existing = await self.db.fetch_one(
                "SELECT COUNT(*), MAX(created_at) FROM storytelling_kill_impact "
                f"WHERE {row_filter} AND formula_version = {fv_placeholder}",  # nosec B608 - row_filter from _scope_row_filter, all values $N-bound
                (*scope_params, FORMULA_VERSION)
            )
            if existing and existing[0] > 0:
                kis_ts = existing[1]
                ctx = await self.db.fetch_one(
                    "SELECT GREATEST("
                    f" (SELECT MAX(created_at) FROM proximity_kill_outcome          WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_combat_position       WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_spawn_timing          WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_team_push             WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_crossfire_opportunity WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_carrier_kill          WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_carrier_return        WHERE {row_filter}),"
                    f" (SELECT MAX(created_at) FROM proximity_reaction_metric       WHERE {row_filter})"
                    ")",  # nosec B608 - row_filter from _scope_row_filter, all values $N-bound
                    scope_params
                )
                ctx_ts = ctx[0] if ctx else None
                # kis_ts should never be NULL when count>0, but guard anyway:
                # a missing cache timestamp means we can't prove freshness, so
                # recompute rather than risk serving stale scores.
                if kis_ts is not None and (ctx_ts is None or ctx_ts <= kis_ts):
                    return {"status": "cached", "kills_scored": existing[0]}
                logger.info(
                    "KIS cache stale for dates=%s (context newer than cache) — recomputing", date_list
                )

        # 1. Get all kill outcomes for the session
        kills = await self.db.fetch_all(f"""
            SELECT ko.id, ko.session_date, ko.round_number, ko.round_start_unix,
                   ko.map_name, ko.killer_guid, ko.killer_name,
                   ko.victim_guid, ko.victim_name,
                   ko.outcome, ko.kill_time
            FROM proximity_kill_outcome ko
            WHERE {ko_row_filter}
            ORDER BY ko.round_start_unix, ko.kill_time
        """, scope_params)  # nosec B608 - ko_row_filter from _scope_row_filter, all values $N-bound

        if not kills:
            return {"status": "no_data", "kills_scored": 0}

        # 2. Pre-load context data for the session (parallel per date,
        # merged across date fragments — see _load_context_for_dates).
        (
            carrier_kills,
            carrier_returns,
            pushes,
            crossfires,
            spawn_timings,
            victim_classes,
            combat_positions,
        ) = await self._load_context_for_dates(dates)

        # 3. Score each kill
        scored = []
        for kill in kills:
            impact = self._score_kill(kill, carrier_kills, carrier_returns,
                                      pushes, crossfires, spawn_timings, victim_classes,
                                      combat_positions)
            scored.append(impact)

        # 4. Store in DB (delete old, batch insert new) — atomically, so a
        # failed insert can't leave the session's KIS cache empty and starve
        # Smart Stats / Good Night / moments until the next recompute.
        tx = getattr(self.db, "transaction", None)
        if callable(tx):
            async with tx():
                await self._store_scored_kills(row_filter, scope_params, gaming_session_id, scored)
        else:  # SQLite dev adapter has no transaction context
            await self._store_scored_kills(row_filter, scope_params, gaming_session_id, scored)

        logger.info("KIS computed for dates=%s: %d kills scored", date_list, len(scored))
        return {"status": "computed", "kills_scored": len(scored)}

    async def _load_context_for_dates(self, dates: tuple[date, ...]) -> tuple[dict, ...]:
        """Run the 7 KIS context loaders once per date fragment and merge.

        Safe to merge with plain dict.update(): every loader is keyed by
        round_ctx_key (round_start_unix, map_name, round_number) —
        round_start_unix is a unique Unix timestamp, so keys from different
        date fragments of the SAME gaming session can never collide.
        Without this, a midnight-crossing session's second-date kills would
        score with NO carrier/push/crossfire/spawn/class/position context —
        a silent wrong-score bug, not a crash (Codex §5/§8 SS-B).
        """
        carrier_kills: dict = {}
        carrier_returns: dict = {}
        pushes: dict = {}
        crossfires: dict = {}
        spawn_timings: dict = {}
        victim_classes: dict = {}
        combat_positions: dict = {}
        for d in dates:
            (ck, cr, pu, cf, st, vc, cp) = await asyncio.gather(
                self._load_carrier_kills(d),
                self._load_carrier_returns(d),
                self._load_pushes(d),
                self._load_crossfires(d),
                self._load_spawn_timings(d),
                self._load_victim_classes(d),
                self._load_combat_positions(d),
            )
            carrier_kills.update(ck)
            carrier_returns.update(cr)
            pushes.update(pu)
            crossfires.update(cf)
            spawn_timings.update(st)
            victim_classes.update(vc)
            combat_positions.update(cp)
        return (
            carrier_kills, carrier_returns, pushes, crossfires,
            spawn_timings, victim_classes, combat_positions,
        )

    async def _store_scored_kills(
        self,
        row_filter: str,
        scope_params: tuple,
        gaming_session_id: int | None,
        scored: list,
    ) -> None:
        # Same precise round-key filter as the fetch above (or the unchanged
        # date filter on the legacy path) — a broader delete here would wipe
        # out an unrelated session's rows sharing this session's date
        # (Copilot review on #525).
        await self.db.execute(
            f"DELETE FROM storytelling_kill_impact WHERE {row_filter}", scope_params  # nosec B608 - row_filter built by _scope_row_filter from internal constants, all values $N-bound
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
                    s['killer_guid'][:8] if s['killer_guid'] else None,
                    FORMULA_VERSION,
                    gaming_session_id,
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
                 kill_time_ms, killer_guid_canonical, formula_version, gaming_session_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28,$29,$30,$31,$32,$33)
            """, batch)

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

        # Canonical round key (round_start_unix, map_name, round_number) —
        # built through the same helper the loaders use so the build and
        # lookup key shapes can never drift (codex audit #10).
        round_key = round_ctx_key(round_start_unix, map_name, round_number)

        # Carrier kill check
        carrier_mult = 1.0
        is_carrier = False
        ck_key = (killer_guid, *round_key)
        if ck_key in carrier_kills and kill_time in carrier_kills[ck_key]:
            cr_key = round_key
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

        # Spawn timing bonus + victim reinf wait (combined single pass).
        # spawn_mult uses max score across all matching st_data; reinf_mult
        # uses the first matching st_data's victim_reinf (preserves prior
        # break-on-first-match semantics). Combining avoids a second walk
        # of spawn_timings[round_key] further down the function.
        spawn_mult = 1.0
        reinf_mult = 1.0
        victim_reinf_stored = 0.0
        if round_key in spawn_timings:
            best_score = 0.0
            first_match_reinf = None
            for st_data in spawn_timings[round_key]:
                if (
                    st_data[0] != killer_guid
                    or abs(st_data[1] - kill_time) > SPAWN_TIMING_WINDOW_MS
                ):
                    continue
                score = st_data[2]
                if score > best_score:
                    best_score = score
                if first_match_reinf is None:
                    # (guid, kill_time, score, victim_reinf) after F6.
                    # Older callers that still pass a 5-tuple with
                    # enemy_spawn_interval at index 3 → index 4 takes
                    # precedence (backward-compat for cached fixtures).
                    if len(st_data) >= 5:
                        first_match_reinf = st_data[4]
                    elif len(st_data) >= 4:
                        first_match_reinf = st_data[3]
            spawn_mult = 1.0 + best_score
            if first_match_reinf is not None:
                victim_reinf_stored = float(first_match_reinf)
                reinf_mult = _graduated_reinf_mult(first_match_reinf)

        # Kill outcome multiplier
        outcome_mult = 1.0
        if outcome == 'gibbed':
            outcome_mult = OUTCOME_GIBBED
        elif outcome == 'revived':
            outcome_mult = OUTCOME_REVIVED

        # Target class multiplier (from reaction_metric)
        victim_class = victim_classes.get((victim_guid, *round_key), '').upper()
        class_mult = CLASS_WEIGHTS.get(victim_class, 1.0)

        # TODO: Implement when per-kill distance data available
        dist_mult = DISTANCE_NORMAL

        # Oksii adoption: health multiplier (clutch kill with low HP)
        health_mult = 1.0
        # Oksii adoption: alive count multiplier (outnumbered/solo clutch)
        alive_mult = 1.0
        # reinf_mult is computed together with spawn_mult above

        cp = None
        cp_key = (killer_guid, *round_key, kill_time)
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

