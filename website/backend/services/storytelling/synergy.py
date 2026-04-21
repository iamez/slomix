"""StorytellingService mixin: synergy methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

import asyncio

from .base import (
    COHESION_MAX_DISPERSION,
    SYNERGY_WEIGHTS,
    _to_date,
    _to_date_str,
    date,
    logger,
)


class _SynergyMixin:
    """Synergy methods for StorytellingService."""

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

        # Audit F9: partial_data signal from _build_player_groups_uncached
        # when PCS rows exist but R1 data is missing. Propagate to the
        # endpoint response so the frontend can render "Insufficient
        # data — R1 missing" instead of degenerate zero-bars.
        if groups.get('_status') == 'partial_data':
            return {
                "status": "partial_data",
                "reason": groups.get('_reason', 'unknown'),
                "session_date": str(sd),
                "groups": {},
            }

        rmap = groups['round_map']
        g2g = groups['guid_to_group']

        # Each axis hits a distinct table with no ordering dependency
        # — parallelising them matches the moments.py detector pattern
        # and turns 5 × round-trip into 1 × round-trip for the synergy
        # endpoint. Measured locally: ~250 ms → ~60 ms on a typical
        # session with full proximity data.
        crossfire, trade, cohesion, push, medic = await asyncio.gather(
            self._synergy_crossfire(sd, rmap),
            self._synergy_trade(sd, g2g),
            self._synergy_cohesion(sd, rmap),
            self._synergy_push(sd, rmap),
            self._synergy_medic(sd, g2g),
        )

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

        # F9: report how many subs/late joins hit the group_b default
        # in `_build_player_groups`. High counts indicate missing
        # stopwatch correlation rather than real substitutions; the
        # frontend can surface this as a secondary warning.
        defaulted = int(groups.get('defaulted_players_count', 0) or 0)
        response = {
            "status": "ok" if defaulted == 0 else "ok_with_defaults",
            "session_date": str(sd),
            "groups": result_groups,
            "weights": SYNERGY_WEIGHTS,
            "defaulted_players_count": defaulted,
        }
        return response

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
        """Memoized wrapper: see `_build_player_groups_uncached` for logic.

        Story page fans out to gravity/space-created/enabler/narratives
        concurrently; each of those mixins independently calls this.
        Caching on the request-scoped service instance collapses 3-4
        identical PCS JOIN rounds scans into one per request.

        A per-date asyncio.Lock around the cache-miss branch prevents
        the concurrent fan-out from all missing together and running
        `_build_player_groups_uncached` N times. Pattern:

            - Fast path: cache hit → return immediately (no lock).
            - Slow path: acquire the per-date lock; first waiter runs
              the uncached query and writes the cache; every other
              waiter wakes up into the fast path.
        """
        cache = getattr(self, "_groups_cache", None)
        if cache is None:
            # Defensive: any subclass that skips the __init__ cache
            # allocation still gets the old behaviour (no memo).
            return await self._build_player_groups_uncached(sd)
        if sd in cache:
            return cache[sd]

        locks = getattr(self, "_groups_locks", None)
        if locks is None:
            value = await self._build_player_groups_uncached(sd)
            cache[sd] = value
            return value

        lock = locks.setdefault(sd, asyncio.Lock())
        async with lock:
            # Double-check after acquiring — first waiter may have
            # already populated the cache while we queued for the lock.
            if sd in cache:
                return cache[sd]
            value = await self._build_player_groups_uncached(sd)
            cache[sd] = value
            return value

    async def _build_player_groups_uncached(self, sd: date) -> dict | None:
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
            # Audit F9: session has only R2 data (stopwatch crash,
            # surrender before R1 stats, incomplete correlation). Signal
            # the partial state so the caller can surface an
            # "Insufficient data" badge instead of silently rendering
            # a degenerate single-group layout.
            logger.warning(
                "synergy: session %s has rows but no R1 — partial_data",
                sd,
            )
            return {
                "_status": "partial_data",
                "_reason": "no_r1_data",
                "round_map": {},
                "guid_to_group": {},
                "group_a_players": [],
                "group_b_players": [],
                "defaulted_players_count": 0,
            }

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

        # Assign any players not in initial groups (subs, late joins).
        # Audit F9: track how many players hit the `round_map.get(...,
        # 'group_b')` default so the caller can expose "N players
        # defaulted" in the synergy response. High counts indicate
        # missing stopwatch correlation data rather than real subs.
        defaulted_player_guids: set[str] = set()
        for guid, _name, rn, team, rsu in rows:
            if guid not in group_a_guids and guid not in group_b_guids:
                faction = 'AXIS' if team == 1 else 'ALLIES'
                default_used = (rsu, faction) not in round_map
                group = round_map.get((rsu, faction), 'group_b')
                if default_used:
                    defaulted_player_guids.add(guid)
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
            'defaulted_players_count': len(defaulted_player_guids),
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
            # Proximity GUIDs are 32-char, stats GUIDs are 8-char prefix
            guid = r[0][:8] if r[0] and len(r[0]) > 8 else r[0]
            group = guid_to_group.get(guid)
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
            # Proximity GUIDs are 32-char, stats GUIDs are 8-char prefix
            guid = r[0][:8] if r[0] and len(r[0]) > 8 else r[0]
            group = guid_to_group.get(guid)
            if group:
                tr[group] += int(r[1] or 0)

        td: dict[str, int] = {'group_a': 0, 'group_b': 0}
        for r in (deaths_rows or []):
            group = guid_to_group.get(r[0])
            if group:
                td[group] += int(r[1] or 0)

        return {g: min(100, tr[g] / max(td[g], 1) * 200)
                for g in ('group_a', 'group_b')}

