"""
Async Stopwatch Scoring Service

Calculates Stopwatch mode scores using async PostgreSQL adapter.
Replacement for tools/stopwatch_scoring.py (sync SQLite version).

Correct Stopwatch scoring (independent round scoring):
- Each map has two rounds with a shared time limit.
- Round 1: Team1 attacks vs Team2 defends.
  - If attackers complete under time limit → Team1 gets 1 point
  - If time runs out (fullhold) → Team2 gets 1 point
- Round 2: Team2 attacks vs Team1 defends.
  - If attackers complete under time limit → Team2 gets 1 point
  - If time runs out (fullhold) → Team1 gets 1 point

Map score = sum of the two round results (0, 1, or 2 points per team).
"""

import json
import logging
from typing import Dict, Tuple, Optional, List, Any

logger = logging.getLogger(__name__)


class StopwatchScoringService:
    """Calculate Stopwatch mode map scores (async PostgreSQL version)"""

    def __init__(self, db_adapter):
        """
        Initialize with database adapter.

        Args:
            db_adapter: Async DatabaseAdapter instance
        """
        self.db = db_adapter

    def parse_time_to_seconds(self, time_str: str) -> int:
        """Convert MM:SS or M:SS to seconds"""
        if not time_str:
            return 0
        try:
            if ':' in str(time_str):
                parts = str(time_str).split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            return int(float(time_str))
        except (ValueError, IndexError):
            return 0

    def calculate_map_score(
        self,
        round1_time_limit: str,
        round1_actual_time: str,
        round2_actual_time: str
    ) -> Tuple[int, int, str]:
        """
        Calculate map score using independent round scoring.

        Args:
            round1_time_limit: Max map time (MM:SS)
            round1_actual_time: R1 completion time (MM:SS)
            round2_actual_time: R2 completion time (MM:SS)

        Returns:
            (team1_score, team2_score, description)
            team1 = R1 attackers, team2 = R2 attackers
        """
        # Parse times to seconds
        limit_sec = self.parse_time_to_seconds(round1_time_limit)
        r1_sec = self.parse_time_to_seconds(round1_actual_time)
        r2_sec = self.parse_time_to_seconds(round2_actual_time)

        # Determine round outcomes
        r1_attackers_succeed = (r1_sec > 0) and (r1_sec < limit_sec)
        r2_attackers_succeed = (r2_sec > 0) and (r2_sec < limit_sec)

        # Award points independently per round
        team1_points = 0
        team2_points = 0

        # Round 1: Team1 attacks
        if r1_attackers_succeed:
            team1_points += 1
            r1_desc = f"R1: completed {round1_actual_time} (Team1 +1)"
        else:
            team2_points += 1
            r1_desc = (
                f"R1: fullhold {round1_time_limit} (Team2 +1)"
                if limit_sec > 0
                else "R1: fullhold (Team2 +1)"
            )

        # Round 2: Team2 attacks
        if r2_attackers_succeed:
            team2_points += 1
            r2_desc = f"R2: completed {round2_actual_time} (Team2 +1)"
        else:
            team1_points += 1
            r2_desc = (
                f"R2: fullhold {round1_time_limit} (Team1 +1)"
                if limit_sec > 0
                else "R2: fullhold (Team1 +1)"
            )

        description = f"{r1_desc}; {r2_desc}"
        return (team1_points, team2_points, description)

    async def calculate_session_scores(
        self,
        session_date: str,
        session_ids: Optional[List[int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate total scores for a gaming session.

        Args:
            session_date: Session date (YYYY-MM-DD)
            session_ids: Optional list of round IDs to filter

        Returns:
            Dict with team names as keys and scores, or None if no data
        """
        try:
            # Get rounds for this session
            if session_ids:
                placeholders = ','.join(['$' + str(i+1) for i in range(len(session_ids))])
                rounds_query = f"""
                    SELECT map_name, match_id, round_number, defender_team,
                           winner_team, time_limit, actual_time
                    FROM rounds
                    WHERE id IN ({placeholders})
                    AND match_id IS NOT NULL
                    ORDER BY match_id, round_number
                """
                rows = await self.db.fetch_all(rounds_query, tuple(session_ids))
            else:
                rounds_query = """
                    SELECT map_name, match_id, round_number, defender_team,
                           winner_team, time_limit, actual_time
                    FROM rounds
                    WHERE SUBSTRING(round_date, 1, 10) = $1
                    AND match_id IS NOT NULL
                    ORDER BY match_id, round_number
                """
                rows = await self.db.fetch_all(rounds_query, (session_date,))

            if not rows:
                logger.debug(f"No rounds found for {session_date}")
                return None

            # Group rounds by match_id (proper R1+R2 pairs)
            maps_dict: Dict[str, Dict] = {}
            for row in rows:
                map_name, match_id, round_num, defender, winner, \
                    time_limit, actual_time = row

                if match_id not in maps_dict:
                    maps_dict[match_id] = {
                        'map_name': map_name,
                        'match_id': match_id,
                        'round1': None,
                        'round2': None
                    }

                round_data = {
                    'defender': defender,
                    'winner': winner,
                    'time_limit': time_limit,
                    'actual_time': actual_time
                }

                if round_num == 1:
                    maps_dict[match_id]['round1'] = round_data
                elif round_num == 2:
                    maps_dict[match_id]['round2'] = round_data

            # Filter to complete maps only (both R1 and R2)
            maps = [
                m for m in maps_dict.values()
                if m['round1'] is not None and m['round2'] is not None
            ]

            if not maps:
                logger.debug(f"No complete map pairs for {session_date}")
                return None

            # Get team assignments from session_teams
            teams_query = """
                SELECT DISTINCT team_name, player_guids
                FROM session_teams
                WHERE SUBSTRING(session_start_date, 1, 10) = $1
            """
            team_rows = await self.db.fetch_all(teams_query, (session_date,))

            if not team_rows or len(team_rows) < 2:
                logger.debug(f"Not enough teams found for {session_date}")
                return None

            # Parse team assignments
            team_names_list = []
            team_guids_list = []
            for row in team_rows:
                team_name, player_guids_json = row
                player_guids = json.loads(player_guids_json)
                team_names_list.append(team_name)
                team_guids_list.append(set(player_guids))

            # Map game team numbers to actual team names
            sample_query = """
                SELECT player_guid, team
                FROM player_comprehensive_stats
                WHERE SUBSTRING(session_date, 1, 10) = $1
                AND round_number = 1
                LIMIT 1
            """
            sample_player = await self.db.fetch_one(sample_query, (session_date,))

            if not sample_player:
                logger.debug(f"No player stats for mapping teams: {session_date}")
                return None

            sample_guid, sample_team = sample_player

            # Determine which actual team this GUID belongs to
            if sample_guid in team_guids_list[0]:
                if sample_team == 1:
                    team_mapping = {1: 0, 2: 1}
                else:
                    team_mapping = {1: 1, 2: 0}
            else:
                if sample_team == 1:
                    team_mapping = {1: 1, 2: 0}
                else:
                    team_mapping = {1: 0, 2: 1}

            teams = {
                1: {'name': team_names_list[team_mapping[1]], 'score': 0},
                2: {'name': team_names_list[team_mapping[2]], 'score': 0}
            }

            # Calculate scores for each map pair
            map_results = []
            for map_data in maps:
                r1 = map_data['round1']
                r2 = map_data['round2']

                team1_pts, team2_pts, desc = self.calculate_map_score(
                    r1['time_limit'], r1['actual_time'],
                    r2['actual_time']
                )

                teams[1]['score'] += team1_pts
                teams[2]['score'] += team2_pts

                map_results.append({
                    'map': map_data['map_name'],
                    'team1_points': team1_pts,
                    'team2_points': team2_pts,
                    'description': desc
                })

            # Return team scores with names
            return {
                teams[1]['name']: teams[1]['score'],
                teams[2]['name']: teams[2]['score'],
                'maps': map_results,
                'total_maps': len(map_results)
            }

        except Exception as e:
            logger.error(f"Error calculating session scores: {e}", exc_info=True)
            return None
