"""
Session Stats Aggregator - Handles all statistical aggregations

This service manages:
- Player statistics aggregation
- Team statistics aggregation
- Weapon statistics aggregation
- DPM leaderboard calculations
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("bot.services.session_stats_aggregator")


class SessionStatsAggregator:
    """Service for aggregating session statistics from database"""

    def __init__(self, db_adapter):
        """
        Initialize the session stats aggregator

        Args:
            db_adapter: Database adapter for queries
        """
        self.db_adapter = db_adapter

    async def aggregate_all_player_stats(self, session_ids: List, session_ids_str: str):
        """
        Aggregate ALL player stats across all rounds with weighted DPM

        DPM calculation uses time_played_seconds (actual time alive/playing),
        NOT round duration. This ensures DPM accurately reflects damage output
        during active playtime, excluding time spent dead.

        Returns: List of player stat tuples (includes NEW stats: gibs, revives, times revived, dmg received, useful kills)
        """
        query = f"""
            SELECT p.player_name,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                CASE
                    WHEN session_total.total_seconds > 0
                    THEN (SUM(p.damage_given) * 60.0) / session_total.total_seconds
                    ELSE 0
                END as weighted_dpm,
                COALESCE(SUM(w.hits), 0) as total_hits,
                COALESCE(SUM(w.shots), 0) as total_shots,
                COALESCE(SUM(w.headshots), 0) as total_headshots,
                SUM(p.headshot_kills) as headshot_kills,
                session_total.total_seconds as total_seconds,
                CAST(SUM(p.time_played_seconds * p.time_dead_ratio / 100.0) AS INTEGER) as total_time_dead,
                SUM(p.denied_playtime) as total_denied,
                SUM(p.gibs) as total_gibs,
                SUM(p.revives_given) as total_revives_given,
                SUM(p.times_revived) as total_times_revived,
                SUM(p.damage_received) as total_damage_received,
                SUM(p.damage_given) as total_damage_given,
                SUM(p.most_useful_kills) as total_useful_kills,
                SUM(p.double_kills) as total_double_kills,
                SUM(p.triple_kills) as total_triple_kills,
                SUM(p.quad_kills) as total_quad_kills,
                SUM(p.multi_kills) as total_multi_kills,
                SUM(p.mega_kills) as total_mega_kills
            FROM player_comprehensive_stats p
            CROSS JOIN (
                SELECT SUM(
                    CASE
                        WHEN r.actual_time LIKE '%:%' THEN
                            CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                            CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
                        ELSE
                            CAST(r.actual_time AS INTEGER)
                    END
                ) as total_seconds
                FROM rounds r
                WHERE r.id IN ({session_ids_str})
                  AND r.round_number IN (1, 2)
                  AND (r.round_status = 'completed' OR r.round_status IS NULL)
            ) session_total
            LEFT JOIN (
                SELECT round_id, player_guid,
                    SUM(hits) as hits,
                    SUM(shots) as shots,
                    SUM(headshots) as headshots
                FROM weapon_comprehensive_stats
                WHERE weapon_name NOT IN ('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')
                GROUP BY round_id, player_guid
            ) w ON p.round_id = w.round_id AND p.player_guid = w.player_guid
            WHERE p.round_id IN ({session_ids_str})
            GROUP BY p.player_guid, p.player_name, session_total.total_seconds
            ORDER BY kills DESC
        """
        return await self.db_adapter.fetch_all(query, tuple(session_ids))

    async def aggregate_team_stats(self, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict] = None, name_to_team: Optional[Dict] = None):
        """
        Get aggregated team statistics

        IMPORTANT: In stopwatch mode, players swap sides between rounds, so the 'team'
        column (1 or 2) represents the SIDE they played, not their actual team.
        We must use hardcoded teams or session_teams table to determine actual teams.

        Without hardcoded teams, stats will show ATTACKERS vs DEFENDERS, not actual teams!
        """
        if not hardcoded_teams or not name_to_team or len(name_to_team) == 0:
            # WARNING: In stopwatch mode this groups by SIDE (attacker/defender) not actual team!
            logger.warning("⚠️ No team rosters available - stats will group by SIDE not team")
            query = f"""
                SELECT p.team,
                    SUM(p.kills) as total_kills,
                    SUM(p.deaths) as total_deaths,
                    SUM(p.damage_given) as total_damage
                FROM player_comprehensive_stats p
                JOIN rounds r ON p.round_id = r.id
                WHERE p.round_id IN ({session_ids_str})
                  AND r.round_number IN (1, 2)
                  AND (r.round_status = 'completed' OR r.round_status IS NULL)
                GROUP BY p.team
            """
            return await self.db_adapter.fetch_all(query, tuple(session_ids))

        # Get all player stats (with R0 and round_status filtering)
        query = f"""
            SELECT p.player_name, p.player_guid,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths,
                SUM(p.damage_given) as total_damage
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.round_id IN ({session_ids_str})
              AND r.round_number IN (1, 2)
              AND (r.round_status = 'completed' OR r.round_status IS NULL)
            GROUP BY p.player_guid, p.player_name
        """
        player_stats = await self.db_adapter.fetch_all(query, tuple(session_ids))

        # Aggregate by actual team
        team_aggregates = {}
        for player_name, player_guid, kills, deaths, damage in player_stats:
            team_name = name_to_team.get(player_name)
            if team_name:
                if team_name not in team_aggregates:
                    team_aggregates[team_name] = {"kills": 0, "deaths": 0, "damage": 0}
                team_aggregates[team_name]["kills"] += kills
                team_aggregates[team_name]["deaths"] += deaths
                team_aggregates[team_name]["damage"] += damage

        # Convert to expected format (team_number, kills, deaths, damage)
        # We'll use 1 and 2 as team numbers, but they now represent actual teams
        result = []
        team_names = list(team_aggregates.keys())
        for i, team_name in enumerate(team_names[:2], start=1):
            stats = team_aggregates[team_name]
            result.append((i, stats["kills"], stats["deaths"], stats["damage"]))

        return result

    async def aggregate_weapon_stats(self, session_ids, session_ids_str):
        """Aggregate weapon statistics PER PLAYER across sessions."""
        if not session_ids:
            return []

        # weapon_comprehensive_stats schema: kills, deaths, shots, hits, headshots, accuracy
        # Returns: player_name, weapon_name, kills, hits, shots, headshots
        query = f"""
            SELECT
                player_name,
                weapon_name,
                SUM(kills) AS total_kills,
                SUM(hits) AS total_hits,
                SUM(shots) AS total_shots,
                SUM(headshots) AS total_headshots
            FROM weapon_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY player_guid, player_name, weapon_name
            ORDER BY player_name, total_kills DESC
        """

        return await self.db_adapter.fetch_all(query, tuple(session_ids))

    async def get_dpm_leaderboard(self, session_ids: List, session_ids_str: str, limit: int = 10):
        """Get DPM leaderboard based on total session duration (not individual playtime)"""
        query = f"""
            SELECT player_name,
                CASE
                    WHEN session_total.total_seconds > 0
                    THEN (SUM(damage_given) * 60.0) / session_total.total_seconds
                    ELSE 0
                END as weighted_dpm,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths
            FROM player_comprehensive_stats
            CROSS JOIN (
                SELECT SUM(
                    CASE
                        WHEN r.actual_time LIKE '%:%' THEN
                            CAST(SPLIT_PART(r.actual_time, ':', 1) AS INTEGER) * 60 +
                            CAST(SPLIT_PART(r.actual_time, ':', 2) AS INTEGER)
                        ELSE
                            CAST(r.actual_time AS INTEGER)
                    END
                ) as total_seconds
                FROM rounds r
                WHERE r.id IN ({session_ids_str})
                  AND r.round_number IN (1, 2)
                  AND (r.round_status = 'completed' OR r.round_status IS NULL)
            ) session_total
            WHERE round_id IN ({session_ids_str})
            GROUP BY player_guid, player_name, session_total.total_seconds
            ORDER BY weighted_dpm DESC
            LIMIT {limit}
        """
        return await self.db_adapter.fetch_all(query, tuple(session_ids))
