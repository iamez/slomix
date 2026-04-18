"""StorytellingService mixin: archetypes methods.

Extracted from the monolithic storytelling_service.py in Sprint 6.
Imports all module-level names (constants, helpers) from .base.
"""
from __future__ import annotations

from .base import (
    _safe_short,
    _to_date,
    _to_date_str,
    date,
    strip_et_colors,
)


class _ArchetypesMixin:
    """Archetypes methods for StorytellingService."""

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
                "guid": r[0], "name": strip_et_colors(r[1] or _safe_short(r[0])),
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
                entry["revives_given"] = ps.get("revives_given", 0)

        return kis_entries

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

