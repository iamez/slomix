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

    async def _get_player_stats_columns(self):
        """Get columns for player_comprehensive_stats (cached)."""
        if hasattr(self, "_player_stats_columns"):
            return self._player_stats_columns

        try:
            # SQLite
            cols = await self.db_adapter.fetch_all("PRAGMA table_info(player_comprehensive_stats)")
            self._player_stats_columns = {c[1] for c in cols}
            return self._player_stats_columns
        except Exception:
            pass

        try:
            # PostgreSQL
            cols = await self.db_adapter.fetch_all(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'player_comprehensive_stats'
                """
            )
            self._player_stats_columns = {c[0] for c in cols}
            return self._player_stats_columns
        except Exception:
            self._player_stats_columns = set()
            return self._player_stats_columns

    async def has_full_selfkills_column(self) -> bool:
        """Check if full_selfkills column exists."""
        columns = await self._get_player_stats_columns()
        return "full_selfkills" in columns

    async def aggregate_all_player_stats(self, session_ids: List, session_ids_str: str):
        """
        Aggregate ALL player stats across all rounds with weighted DPM

        DPM calculation uses time_played_seconds (actual time alive/playing),
        NOT round duration. This ensures DPM accurately reflects damage output
        during active playtime, excluding time spent dead.

        Returns: List of player stat tuples (includes NEW stats: gibs, revives, times revived, dmg received, useful kills)
        """
        columns = await self._get_player_stats_columns()
        has_full_selfkills = "full_selfkills" in columns
        has_kill_assists = "kill_assists" in columns
        full_selfkills_select = (
            "SUM(p.full_selfkills) as total_full_selfkills"
            if has_full_selfkills
            else "0 as total_full_selfkills"
        )
        kill_assists_select = (
            "SUM(p.kill_assists) as total_kill_assists"
            if has_kill_assists
            else "0 as total_kill_assists"
        )
        if not has_kill_assists and not getattr(self, "_warned_missing_kill_assists", False):
            logger.warning(
                "player_comprehensive_stats.kill_assists column missing; defaulting total_kill_assists to 0"
            )
            self._warned_missing_kill_assists = True

        query = f"""
            SELECT MAX(p.player_name) as player_name,
                p.player_guid,
                SUM(p.kills) as kills,
                SUM(p.deaths) as deaths,
                CASE
                    WHEN SUM(p.time_played_seconds) > 0
                    THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                    ELSE 0
                END as weighted_dpm,
                COALESCE(SUM(w.hits), 0) as total_hits,
                COALESCE(SUM(w.shots), 0) as total_shots,
                COALESCE(SUM(w.headshots), 0) as total_headshots,
                SUM(p.headshot_kills) as headshot_kills,
                SUM(p.time_played_seconds) as total_seconds,
                -- FIX (2026-02-01): Use time_dead_minutes directly instead of ratio calculation
                -- The ratio in R2 files is calculated against cumulative time_played, but we store
                -- differential time_played. Using time_dead_minutes is correct for both R1 and R2.
                CAST(SUM(
                    LEAST(
                        COALESCE(p.time_dead_minutes, 0) * 60,
                        p.time_played_seconds
                    )
                ) AS INTEGER) as total_time_dead,
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
                SUM(p.mega_kills) as total_mega_kills,
                SUM(p.self_kills) as total_self_kills,
                {full_selfkills_select},
                {kill_assists_select}
            FROM player_comprehensive_stats p
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
            GROUP BY p.player_guid
            ORDER BY kills DESC
        """
        return await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

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
            query = """
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
            return await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        # Get all player stats (with R0 and round_status filtering)
        query = """
            SELECT MAX(p.player_name) as player_name, p.player_guid,
                SUM(p.kills) as total_kills,
                SUM(p.deaths) as total_deaths,
                SUM(p.damage_given) as total_damage
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.round_id IN ({session_ids_str})
              AND r.round_number IN (1, 2)
              AND (r.round_status = 'completed' OR r.round_status IS NULL)
            GROUP BY p.player_guid
        """
        player_stats = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

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

    async def calculate_session_scores(self, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict] = None) -> Dict[str, int]:
        """
        Calculate session score based on winner_team from rounds.

        Uses the winner_team column (1 or 2) to track wins per team.
        If hardcoded_teams provided, maps team numbers to team names.

        Args:
            session_ids: List of round IDs
            session_ids_str: Comma-separated placeholder string
            hardcoded_teams: Optional team data from session_teams table

        Returns:
            {
                'team_a_score': 3,  # Number of rounds won
                'team_b_score': 2,
                'team_a_name': 'Team A',  # Or custom name if hardcoded
                'team_b_name': 'Team B'
            }
        """
        query = """
            SELECT
                winner_team,
                COUNT(*) as wins
            FROM rounds
            WHERE id IN ({session_ids_str})
              AND round_number IN (1, 2)
              AND winner_team > 0
              AND (round_status = 'completed' OR round_status IS NULL)
            GROUP BY winner_team
            ORDER BY winner_team
        """

        results = await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

        # Initialize scores
        team_a_score = 0
        team_b_score = 0

        # Count wins
        for row in results:
            winner_team, wins = row[0], row[1]
            if winner_team == 1:
                team_a_score = wins
            elif winner_team == 2:
                team_b_score = wins
            else:
                logger.warning(f"Unexpected winner_team={winner_team} with {wins} wins (skipped from scoring)")

        # Determine team names
        team_a_name = "Team A"
        team_b_name = "Team B"

        if hardcoded_teams:
            team_names = list(hardcoded_teams.keys())
            if len(team_names) >= 2:
                team_a_name = team_names[0]
                team_b_name = team_names[1]

        return {
            'team_a_score': team_a_score,
            'team_b_score': team_b_score,
            'team_a_name': team_a_name,
            'team_b_name': team_b_name
        }

    async def aggregate_weapon_stats(self, session_ids, session_ids_str):
        """Aggregate weapon statistics PER PLAYER across sessions."""
        if not session_ids:
            return []

        # weapon_comprehensive_stats schema: kills, deaths, shots, hits, headshots, accuracy
        # Returns: player_guid, player_name, weapon_name, kills, hits, shots, headshots
        query = """
            SELECT
                player_guid,
                MAX(player_name) as player_name,
                weapon_name,
                SUM(kills) AS total_kills,
                SUM(hits) AS total_hits,
                SUM(shots) AS total_shots,
                SUM(headshots) AS total_headshots
            FROM weapon_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY player_guid, weapon_name
            ORDER BY player_name, total_kills DESC
        """

        return await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str), tuple(session_ids))

    async def get_dpm_leaderboard(self, session_ids: List, session_ids_str: str, limit: int = 10):
        """Get DPM leaderboard based on individual player playtime"""
        # Validate limit is a safe integer to prevent SQL injection
        limit = int(limit)  # Raises ValueError if not convertible
        if limit < 1 or limit > 1000:
            raise ValueError(f"Limit must be between 1 and 1000, got {limit}")

        query = """
            SELECT MAX(player_name) as player_name,
                CASE
                    WHEN SUM(time_played_seconds) > 0
                    THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                    ELSE 0
                END as weighted_dpm,
                SUM(kills) as total_kills,
                SUM(deaths) as total_deaths
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
            GROUP BY player_guid
            ORDER BY weighted_dpm DESC
            LIMIT {limit}
        """
        return await self.db_adapter.fetch_all(query.format(session_ids_str=session_ids_str, limit=limit), tuple(session_ids))
