"""
Session Data Service - Handles all database queries for session data

This service manages:
- Fetching latest session information
- Loading hardcoded team assignments
- Calculating team scores and mappings
- Determining team MVPs
"""

import json
import logging
from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Optional, Tuple

from tools.stopwatch_scoring import StopwatchScoring

logger = logging.getLogger("bot.services.session_data")


class SessionDataService:
    """Service for fetching and managing session data from database"""

    def __init__(self, db_adapter, db_path=None):
        """
        Initialize the session data service

        Args:
            db_adapter: Database adapter for queries
            db_path: Optional SQLite database path (for stopwatch scoring)
        """
        self.db_adapter = db_adapter
        self.db_path = db_path

    async def get_latest_session_date(self) -> Optional[str]:
        """
        Get the most recent gaming session date from database.

        Returns the most recent date that has session data.
        Now properly sorts by BOTH date AND time to get the actual last session.
        """
        result = await self.db_adapter.fetch_one(
            """
            SELECT SUBSTR(s.round_date, 1, 10) as date
            FROM rounds s
            WHERE EXISTS (
                SELECT 1 FROM player_comprehensive_stats p
                WHERE p.round_id = s.id
            )
            AND SUBSTR(s.round_date, 1, 4) = '2025'
            ORDER BY
                s.round_date DESC,
                CAST(REPLACE(s.round_time, ':', '') AS INTEGER) DESC
            LIMIT 1
            """
        )
        return result[0] if result else None

    async def fetch_session_data(self, latest_date: str) -> Tuple[Optional[List], Optional[List], Optional[str], int]:
        """
        Fetch session data for the MOST RECENT gaming session.

        BUG FIX: Now fetches ONLY the latest gaming_session_id, not all sessions
        that touched the latest date. This prevents including tail-end rounds from
        a previous day's session that spanned midnight.

        Example: If session 21 ran 2025-11-10 22:00 → 2025-11-11 00:15, and
        session 22 ran 2025-11-11 21:00 → 23:00, we want ONLY session 22 (the
        latest gaming session), not the midnight overflow from session 21.

        Uses gaming_session_id column (60-minute gap threshold).

        Returns:
            (sessions, session_ids, session_ids_str, player_count) or (None, None, None, 0)
        """
        # Get the SINGLE latest gaming_session_id globally (highest session ID)
        result = await self.db_adapter.fetch_one(
            """
            SELECT MAX(gaming_session_id)
            FROM rounds
            WHERE gaming_session_id IS NOT NULL
            """
        )

        if not result or result[0] is None:
            return None, None, None, 0

        latest_gaming_session_id = result[0]

        # Get R1 and R2 rounds only from this ONE gaming session
        # (exclude R0 match summaries to avoid triple-counting)
        # R0 contains cumulative R1+R2 data, so querying all three would give us: R0+R1+R2 = (R1+R2)+R1+R2 = wrong!
        # Using only R1+R2 lets SUM() aggregate correctly without duplication
        # 🆕 Also exclude 'cancelled' rounds (restarts/warmups)
        sessions = await self.db_adapter.fetch_all(
            """
            SELECT id, map_name, round_number, actual_time
            FROM rounds
            WHERE gaming_session_id = ?
              AND round_number IN (1, 2)
              AND (round_status = 'completed' OR round_status IS NULL)
            ORDER BY
                round_date,
                CAST(REPLACE(round_time, ':', '') AS INTEGER)
            """,
            (latest_gaming_session_id,)
        )

        if not sessions:
            return None, None, None, 0

        # Extract session IDs
        session_ids = [s[0] for s in sessions]
        session_ids_str = ",".join("?" * len(session_ids))

        # Get unique player count for this gaming session
        query = f"""
            SELECT COUNT(DISTINCT player_guid)
            FROM player_comprehensive_stats
            WHERE round_id IN ({session_ids_str})
        """
        player_count_result = await self.db_adapter.fetch_one(query, tuple(session_ids))
        player_count = player_count_result[0] if player_count_result else 0

        return sessions, session_ids, session_ids_str, player_count

    async def get_hardcoded_teams(self, session_ids: List[int]) -> Optional[Dict]:
        """
        Get hardcoded team assignments from session_teams table

        NOTE: Queries by date range of the gaming session rounds.

        Args:
            session_ids: List of session IDs (rounds) for this gaming session

        Returns:
            Dict with team names as keys, containing 'guids' and 'names' lists
        """
        try:
            # Get the date range for these session_ids
            placeholders = ','.join('?' * len(session_ids))
            dates_result = await self.db_adapter.fetch_all(
                f"""
                SELECT DISTINCT SUBSTR(round_date, 1, 10) as date
                FROM rounds
                WHERE id IN ({placeholders})
                """,
                tuple(session_ids)
            )
            dates = [row[0] for row in dates_result]

            if not dates:
                return None

            # Query session_teams for these dates
            date_placeholders = ','.join('?' * len(dates))
            rows = await self.db_adapter.fetch_all(
                f"""
                SELECT team_name, player_guids, player_names
                FROM session_teams
                WHERE session_start_date IN ({date_placeholders}) AND map_name = 'ALL'
                ORDER BY team_name
                """,
                tuple(dates)
            )

            if not rows:
                return None

            teams = {}
            for team_name, player_guids_json, player_names_json in rows:
                if team_name not in teams:
                    teams[team_name] = {
                        "guids": json.loads(player_guids_json) if player_guids_json else [],
                        "names": json.loads(player_names_json) if player_names_json else []
                    }

            return teams if teams else None

        except Exception as e:
            logger.debug(f"No hardcoded teams found: {e}")
            return None

    async def calculate_team_scores(self, session_ids: List[int]) -> Tuple[str, str, int, int, Optional[Dict]]:
        """
        Calculate Stopwatch team scores using StopwatchScoring

        NOTE: Calculates scores for a GAMING SESSION (multiple matches/rounds).

        Args:
            session_ids: List of session IDs (rounds) for this gaming session

        Returns: (team_1_name, team_2_name, team_1_score, team_2_score, scoring_result)
        """
        # Skip stopwatch scoring in PostgreSQL mode (requires refactor)
        if not self.db_path:
            return "Team 1", "Team 2", 0, 0, None

        scorer = StopwatchScoring(self.db_path)
        scoring_result = scorer.calculate_session_scores(session_ids=session_ids)

        if scoring_result:
            # Get team names (exclude 'maps' and 'total_maps' keys)
            team_names = [
                k for k in scoring_result.keys()
                if k not in ["maps", "total_maps"]
            ]
            if len(team_names) >= 2:
                team_1_name = team_names[0]
                team_2_name = team_names[1]
                team_1_score = scoring_result[team_1_name]
                team_2_score = scoring_result[team_2_name]
                return team_1_name, team_2_name, team_1_score, team_2_score, scoring_result

        return "Team 1", "Team 2", 0, 0, None

    async def build_team_mappings(self, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict]):
        """
        Build team mappings from hardcoded teams or auto-detect

        NOTE: Works with gaming session rounds (session_ids list).

        Args:
            session_ids: List of session IDs (rounds) for this gaming session
            session_ids_str: Comma-separated placeholders for SQL queries
            hardcoded_teams: Optional pre-defined team assignments

        Returns: (team_1_name, team_2_name, team_1_players, team_2_players, name_to_team)
        """
        if hardcoded_teams:
            logger.info("✅ Using hardcoded teams from session_teams table")

            # Extract team names
            team_names_list = list(hardcoded_teams.keys())
            team_1_name = team_names_list[0] if len(team_names_list) > 0 else "Team A"
            team_2_name = team_names_list[1] if len(team_names_list) > 1 else "Team B"

            # Create GUID -> team_name mapping
            guid_to_team = {}
            for team_name, team_data in hardcoded_teams.items():
                for guid in team_data["guids"]:
                    guid_to_team[guid] = team_name

            # Get player GUIDs to map names to teams
            query = f"""
                SELECT DISTINCT player_name, player_guid
                FROM player_comprehensive_stats
                WHERE round_id IN ({session_ids_str})
            """
            player_guid_map = await self.db_adapter.fetch_all(query, tuple(session_ids))

            # Build name -> team mapping
            name_to_team = {}
            for player_name, player_guid in player_guid_map:
                if player_guid in guid_to_team:
                    name_to_team[player_name] = guid_to_team[player_guid]

            # Organize players by team
            team_1_players = [name for name, team in name_to_team.items() if team == team_1_name]
            team_2_players = [name for name, team in name_to_team.items() if team == team_2_name]

            return team_1_name, team_2_name, team_1_players, team_2_players, name_to_team
        else:
            # Auto-detect teams using co-occurrence analysis
            logger.info("⚠️ No hardcoded teams - attempting smart auto-detection")

            # Get all player-side pairings
            # IMPORTANT: Include round_id in the key to handle multiple plays of same map
            query = f"""
                SELECT player_guid, player_name, team, round_id, map_name, round_number
                FROM player_comprehensive_stats
                WHERE round_id IN ({session_ids_str})
                ORDER BY round_id, map_name, round_number
            """
            all_records = await self.db_adapter.fetch_all(query, tuple(session_ids))

            if not all_records:
                return "Team 1", "Team 2", [], [], {}

            # Build round-by-round side assignments: (round_id, map, round) -> {guid: side}
            # Using round_id ensures each play of a map is tracked separately
            round_sides = defaultdict(dict)
            guid_to_name = {}
            all_guids = set()

            for guid, name, side, sess_id, map_name, round_num in all_records:
                round_sides[(sess_id, map_name, round_num)][guid] = side
                guid_to_name[guid] = name
                all_guids.add(guid)

            # Count how often each pair of players is on the SAME side
            # This works because actual teammates play together regardless of which side they're assigned
            cooccurrence = defaultdict(int)

            for (sess_id, map_name, round_num), sides in round_sides.items():
                guids_in_round = list(sides.keys())
                for guid1, guid2 in combinations(guids_in_round, 2):
                    if sides[guid1] == sides[guid2]:
                        # They were on same side this round -> likely same team
                        cooccurrence[(guid1, guid2)] += 1

            # Build team clusters using graph clustering
            # Strategy: Players with >50% co-occurrence are on same team
            if not all_guids:
                return "Team 1", "Team 2", [], [], {}

            # Build adjacency: guid -> set of guids they play with frequently
            teammates = defaultdict(set)

            for (guid1, guid2), cooccur_count in cooccurrence.items():
                # Calculate total rounds these two played together
                total_rounds_together = sum(
                    1 for sides in round_sides.values()
                    if guid1 in sides and guid2 in sides
                )

                if total_rounds_together > 0:
                    same_side_ratio = cooccur_count / total_rounds_together
                    if same_side_ratio > 0.5:  # More than 50% = same team
                        teammates[guid1].add(guid2)
                        teammates[guid2].add(guid1)

            # Use connected components to find teams
            team_a_guids = set()
            team_b_guids = set()
            visited = set()

            def get_cluster(start_guid):
                """Get all connected players (teammates)"""
                cluster = set()
                to_visit = [start_guid]

                while to_visit:
                    guid = to_visit.pop()
                    if guid in visited:
                        continue
                    visited.add(guid)
                    cluster.add(guid)
                    to_visit.extend(teammates.get(guid, []))

                return cluster

            # Find first cluster (Team A)
            if all_guids:
                first_guid = next(iter(all_guids))
                team_a_guids = get_cluster(first_guid)

                # Remaining players are Team B
                team_b_guids = all_guids - team_a_guids

            # Build name_to_team mapping
            name_to_team = {}
            team_a_players = []
            team_b_players = []

            for guid in team_a_guids:
                name = guid_to_name.get(guid)
                if name:
                    name_to_team[name] = "Team A"
                    team_a_players.append(name)

            for guid in team_b_guids:
                name = guid_to_name.get(guid)
                if name:
                    name_to_team[name] = "Team B"
                    team_b_players.append(name)

            logger.info(f"✅ Auto-detected Team A: {len(team_a_players)} players, Team B: {len(team_b_players)} players")

            return "Team A", "Team B", team_a_players, team_b_players, name_to_team

    async def get_team_mvps(self, session_ids: List, session_ids_str: str, hardcoded_teams: Optional[Dict], team_1_name: str, team_2_name: str):
        """
        Get MVP for each team with detailed stats

        Returns: (team_1_mvp_stats, team_2_mvp_stats)
        Each MVP stats tuple: (player_name, kills, dpm, deaths, revives, gibs)
        """
        team_1_mvp_stats = None
        team_2_mvp_stats = None

        if hardcoded_teams:
            # Calculate MVP per hardcoded team (by GUID)
            for team_name in [team_1_name, team_2_name]:
                if team_name not in hardcoded_teams:
                    continue

                team_guids = hardcoded_teams[team_name]["guids"]
                team_guids_placeholders = ",".join("?" * len(team_guids))

                # Get MVP by kills
                query = f"""
                    SELECT player_name, SUM(kills) as total_kills, player_guid
                    FROM player_comprehensive_stats
                    WHERE round_id IN ({session_ids_str})
                        AND player_guid IN ({team_guids_placeholders})
                    GROUP BY player_name, player_guid
                    ORDER BY total_kills DESC
                    LIMIT 1
                """
                params = session_ids + team_guids
                result = await self.db_adapter.fetch_one(query, tuple(params))

                if result:
                    player_name, kills, guid = result

                    # Get detailed stats for MVP
                    detail_query = f"""
                        SELECT
                            CASE
                                WHEN session_total.total_seconds > 0
                                THEN (SUM(damage_given) * 60.0) / session_total.total_seconds
                                ELSE 0
                            END as weighted_dpm,
                            SUM(deaths),
                            SUM(revives_given),
                            SUM(gibs)
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
                            AND player_name = ?
                            AND player_guid IN ({team_guids_placeholders})
                    """
                    detail_params = session_ids + [player_name] + team_guids
                    detail_result = await self.db_adapter.fetch_one(detail_query, tuple(detail_params))

                    if detail_result:
                        mvp_stats = (player_name, kills, detail_result[0], detail_result[1], detail_result[2], detail_result[3])
                        if team_name == team_1_name:
                            team_1_mvp_stats = mvp_stats
                        else:
                            team_2_mvp_stats = mvp_stats

        return team_1_mvp_stats, team_2_mvp_stats
