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
        Calculate map score using proper competitive stopwatch logic.

        Stopwatch scoring rules:
        - Each map awards 1 point to the winner (not per-round)
        - R1 attackers set the benchmark time
        - R2 attackers must beat the benchmark to win
        - Full hold = attackers fail to complete before time limit
        - Double full hold = 0-0, no one wins the map

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

        # Determine if each team completed objectives
        # Full hold = actual_time equals or exceeds time_limit
        r1_completed = (r1_sec > 0) and (r1_sec < limit_sec)
        r2_completed = (r2_sec > 0) and (r2_sec < limit_sec)

        team1_points = 0
        team2_points = 0

        # Apply stopwatch logic
        if r1_completed and r2_completed:
            # Both teams completed - faster team wins
            if r2_sec < r1_sec:
                # R2 attackers were faster - Team 2 wins map
                team2_points = 1
                description = (
                    f"R1: {round1_actual_time}, R2: {round2_actual_time} "
                    f"(Team2 faster by {r1_sec - r2_sec}s)"
                )
            elif r1_sec < r2_sec:
                # R1 attackers were faster - Team 1 wins map
                team1_points = 1
                description = (
                    f"R1: {round1_actual_time}, R2: {round2_actual_time} "
                    f"(Team1 faster by {r2_sec - r1_sec}s)"
                )
            else:
                # Exact same time - tie (rare)
                description = f"R1: {round1_actual_time}, R2: {round2_actual_time} (exact tie!)"

        elif r1_completed and not r2_completed:
            # R1 completed, R2 full hold - Team 1 wins
            team1_points = 1
            description = (
                f"R1: {round1_actual_time}, R2: fullhold "
                f"(Team1 wins - Team2 failed to beat benchmark)"
            )

        elif not r1_completed and r2_completed:
            # R1 full hold, R2 completed - Team 2 wins
            team2_points = 1
            description = (
                f"R1: fullhold, R2: {round2_actual_time} "
                f"(Team2 wins - completed after Team1 fullhold)"
            )

        else:
            # Double full hold - both teams defended successfully = 1-1
            team1_points = 1  # Team 1 defended in R2 (fullhold)
            team2_points = 1  # Team 2 defended in R1 (fullhold)
            description = "Double fullhold (1-1, both teams defended)"

        return (team1_points, team2_points, description)

    async def calculate_session_scores(
        self,
        session_date: str,
        session_ids: Optional[List[int]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate total scores for a gaming session.

        In Stopwatch mode, each MAP has TWO ROUNDS:
        - Round 1: Team A attacks, Team B defends
        - Round 2: Team B attacks, Team A defends (sides swap)

        We must group rounds by (gaming_session_id, map_name) to pair R1+R2,
        NOT by match_id (which is unique per file/round).

        Args:
            session_date: Session date (YYYY-MM-DD)
            session_ids: Optional list of round IDs to filter

        Returns:
            Dict with team names as keys and scores, or None if no data
        """
        try:
            # Get rounds for this session - GROUP BY map_name within session
            # Key change: We need gaming_session_id to properly pair R1+R2
            if session_ids:
                placeholders = ','.join(
                    ['$' + str(i+1) for i in range(len(session_ids))]
                )
                # nosec B608 - safe: parameterized placeholders ($1, $2...)
                rounds_query = f"""
                    SELECT map_name, gaming_session_id, round_number,
                           defender_team, winner_team, time_limit, actual_time,
                           round_date, round_time
                    FROM rounds
                    WHERE id IN ({placeholders})
                    AND round_status = 'completed'
                    ORDER BY gaming_session_id, map_name, round_number
                """
                rows = await self.db.fetch_all(rounds_query, tuple(session_ids))
            else:
                rounds_query = """
                    SELECT map_name, gaming_session_id, round_number,
                           defender_team, winner_team, time_limit, actual_time,
                           round_date, round_time
                    FROM rounds
                    WHERE SUBSTRING(round_date, 1, 10) = $1
                    AND round_status = 'completed'
                    ORDER BY gaming_session_id, map_name, round_number
                """
                rows = await self.db.fetch_all(rounds_query, (session_date,))

            if not rows:
                logger.debug(f"No rounds found for {session_date}")
                return None

            # Group rounds by (gaming_session_id, map_name) for proper R1+R2
            # Handle repeated maps: pair each R1 with its subsequent R2
            # Rounds are ordered by gaming_session_id, map_name, round_number
            maps_dict: Dict[str, Dict] = {}
            pending_r1: Dict[str, str] = {}  # base_key -> map_key waiting for R2
            map_play_count: Dict[str, int] = {}  # Plays per map in session

            for row in rows:
                (map_name, gaming_session_id, round_num, defender, winner,
                 time_limit, actual_time, round_date, round_time) = row

                # Base key for this map within the gaming session
                base_key = f"{gaming_session_id}:{map_name}"

                round_data = {
                    'defender': defender,
                    'winner': winner,
                    'time_limit': time_limit,
                    'actual_time': actual_time,
                    'round_date': round_date,
                    'round_time': round_time
                }

                if round_num == 1:
                    # Track how many times this map has been played
                    if base_key not in map_play_count:
                        map_play_count[base_key] = 0
                    map_play_count[base_key] += 1
                    play_num = map_play_count[base_key]

                    # Create unique key for this specific map play
                    map_key = f"{base_key}:play{play_num}"
                    maps_dict[map_key] = {
                        'map_name': map_name,
                        'gaming_session_id': gaming_session_id,
                        'round1': round_data,
                        'round2': None
                    }
                    # Mark this R1 as pending, waiting for its R2
                    pending_r1[base_key] = map_key

                elif round_num == 2:
                    # Find the pending R1 for this map
                    if base_key in pending_r1:
                        map_key = pending_r1[base_key]
                        if map_key in maps_dict:
                            maps_dict[map_key]['round2'] = round_data
                        # R1 is no longer pending
                        del pending_r1[base_key]
                    else:
                        # R2 without a matching R1 - create partial entry
                        logger.debug(
                            f"R2 without R1 for {map_name} in session {gaming_session_id}"
                        )

            # Filter to complete maps only (both R1 and R2)
            maps = [
                m for m in maps_dict.values()
                if m['round1'] is not None and m['round2'] is not None
            ]

            if not maps:
                logger.debug(f"No complete map pairs for {session_date}")
                # Log what we found for debugging
                for key, data in maps_dict.items():
                    has_r1 = data['round1'] is not None
                    has_r2 = data['round2'] is not None
                    logger.debug(
                        f"  {key}: R1={has_r1}, R2={has_r2}"
                    )
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
                WHERE SUBSTRING(round_date, 1, 10) = $1
                AND round_number = 1
                LIMIT 1
            """
            sample_player = await self.db.fetch_one(
                sample_query, (session_date,)
            )

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

            # Build result object
            result = {
                teams[1]['name']: teams[1]['score'],
                teams[2]['name']: teams[2]['score'],
                'maps': map_results,
                'total_maps': len(map_results),
                # Include internal data for save_session_results
                '_team1_name': teams[1]['name'],
                '_team2_name': teams[2]['name'],
                '_team1_score': teams[1]['score'],
                '_team2_score': teams[2]['score'],
                '_team1_guids': list(team_guids_list[team_mapping[1]]),
                '_team2_guids': list(team_guids_list[team_mapping[2]]),
                '_gaming_session_id': maps[0]['gaming_session_id'] if maps else None,
                '_session_date': session_date
            }

            return result

        except Exception as e:
            logger.error(f"Error calculating session scores: {e}", exc_info=True)
            return None

    async def save_session_results(
        self,
        scores: Dict[str, Any],
        team1_names: Optional[List[str]] = None,
        team2_names: Optional[List[str]] = None
    ) -> bool:
        """
        Save session results to database.

        This is the critical piece that enables team win/loss record queries.
        Call this after calculate_session_scores() to persist results.

        Args:
            scores: Result from calculate_session_scores() (includes _internal fields)
            team1_names: Optional list of player names for team 1
            team2_names: Optional list of player names for team 2

        Returns:
            True if saved successfully
        """
        try:
            # Extract internal data
            session_date = scores.get('_session_date')
            team_1_name = scores.get('_team1_name')
            team_2_name = scores.get('_team2_name')
            team_1_score = scores.get('_team1_score', 0)
            team_2_score = scores.get('_team2_score', 0)
            team_1_guids = scores.get('_team1_guids', [])
            team_2_guids = scores.get('_team2_guids', [])
            gaming_session_id = scores.get('_gaming_session_id')
            map_results = scores.get('maps', [])

            if not session_date or not team_1_name or not team_2_name:
                logger.warning("Missing required data for save_session_results")
                return False

            # Determine winner (0 = tie, 1 = team_1, 2 = team_2)
            if team_1_score > team_2_score:
                winning_team = 1
            elif team_2_score > team_1_score:
                winning_team = 2
            else:
                winning_team = 0

            # Format for storage
            format_str = f"{len(team_1_guids)}v{len(team_2_guids)}"
            round_details = json.dumps(map_results)
            # Each map has 2 rounds
            round_numbers = json.dumps([1, 2] * len(map_results))

            # Use player names if provided, otherwise empty arrays
            team_1_names_json = json.dumps(team1_names or [])
            team_2_names_json = json.dumps(team2_names or [])

            query = """
                INSERT INTO session_results (
                    session_date,
                    map_name,
                    gaming_session_id,
                    team_1_guids,
                    team_2_guids,
                    team_1_names,
                    team_2_names,
                    team_1_name,
                    team_2_name,
                    format,
                    total_rounds,
                    team_1_score,
                    team_2_score,
                    winning_team,
                    round_details,
                    round_numbers,
                    session_start
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, NOW()
                )
                ON CONFLICT (session_date, map_name, gaming_session_id) DO UPDATE SET
                    team_1_score = EXCLUDED.team_1_score,
                    team_2_score = EXCLUDED.team_2_score,
                    team_1_name = EXCLUDED.team_1_name,
                    team_2_name = EXCLUDED.team_2_name,
                    winning_team = EXCLUDED.winning_team,
                    round_details = EXCLUDED.round_details,
                    updated_at = NOW()
            """

            await self.db.execute(query, (
                session_date,
                'ALL',  # Overall session result
                gaming_session_id,
                json.dumps(team_1_guids),
                json.dumps(team_2_guids),
                team_1_names_json,
                team_2_names_json,
                team_1_name,
                team_2_name,
                format_str,
                len(map_results) * 2,
                team_1_score,
                team_2_score,
                winning_team,
                round_details,
                round_numbers
            ))

            logger.info(f"Saved session results: {session_date} - "
                       f"{team_1_name} {team_1_score} vs {team_2_score} {team_2_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to save session results: {e}", exc_info=True)
            return False
