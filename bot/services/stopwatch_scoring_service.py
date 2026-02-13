"""
Async Stopwatch Scoring Service

Calculates Stopwatch mode scores using async PostgreSQL adapter.
Replacement for tools/stopwatch_scoring.py (sync SQLite version).

        Stopwatch scoring (map-winner, Superboyy-aligned):
- Each map has two rounds with a shared time limit.
        - Prefer R2 header winner side (map winner) when available.
        - If header winner is missing, fall back to time comparison.

Map score = 1 point to the map winner (0-0 for tie).
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
            text = str(time_str).strip()
            if ':' in text:
                parts = text.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            if '.' in text:
                minutes = float(text)
                return int(minutes * 60)
            return int(float(text))
        except (ValueError, IndexError):
            return 0

    def calculate_map_score(
        self,
        round1_time_limit: str,
        round1_actual_time: str,
        round2_actual_time: str
    ) -> Tuple[int, int, str]:
        """
        Calculate map score using map-winner scoring.

        Stopwatch scoring rules (map winner):
        - Team1 = Round 1 attackers
        - Team2 = Round 2 attackers
        - If both complete, faster time wins (tie goes to Team1)
        - If only one completes, that team wins
        - If neither completes or time is unknown, map is a tie

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

        # Determine completion outcomes
        if limit_sec <= 0:
            # No time limit known - treat any positive time as completion
            r1_attackers_succeed = r1_sec > 0
            r2_attackers_succeed = r2_sec > 0
        else:
            r1_attackers_succeed = (r1_sec > 0) and (r1_sec < limit_sec)
            r2_attackers_succeed = (r2_sec > 0) and (r2_sec < limit_sec)

        team1_points = 0
        team2_points = 0

        # Map winner logic
        if r1_attackers_succeed and r2_attackers_succeed:
            # Both teams completed; faster time wins (tie -> Team1)
            if r1_sec <= r2_sec:
                team1_points = 1
                desc = (
                    f"Map win: R1 attackers {round1_actual_time} "
                    f"vs {round2_actual_time}"
                )
            else:
                team2_points = 1
                desc = (
                    f"Map win: R2 attackers {round2_actual_time} "
                    f"vs {round1_actual_time}"
                )
        elif r1_attackers_succeed and not r2_attackers_succeed:
            team1_points = 1
            desc = (
                f"Map win: R1 attackers set time {round1_actual_time} "
                f"(R2 fullhold)"
            )
        elif r2_attackers_succeed and not r1_attackers_succeed:
            team2_points = 1
            desc = (
                f"Map win: R2 attackers completed {round2_actual_time} "
                f"(R1 fullhold)"
            )
        else:
            desc = "Map tie: no completion or time data"

        return (team1_points, team2_points, desc)

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
                    ORDER BY gaming_session_id,
                             round_date,
                             CAST(REPLACE(round_time, ':', '') AS INTEGER),
                             round_number
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
                    ORDER BY gaming_session_id,
                             round_date,
                             CAST(REPLACE(round_time, ':', '') AS INTEGER),
                             round_number
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
            session_id_candidates = sorted(
                {
                    m.get("gaming_session_id")
                    for m in maps
                    if m.get("gaming_session_id") is not None
                }
            )
            resolved_session_id = (
                session_id_candidates[0] if len(session_id_candidates) == 1 else None
            )
            if resolved_session_id is not None:
                teams_query = """
                    SELECT DISTINCT team_name, player_guids
                    FROM session_teams
                    WHERE gaming_session_id = ?
                      AND map_name = 'ALL'
                """
                team_rows = await self.db.fetch_all(teams_query, (resolved_session_id,))
            else:
                teams_query = """
                    SELECT DISTINCT team_name, player_guids
                    FROM session_teams
                    WHERE SUBSTRING(session_start_date, 1, 10) = ?
                      AND map_name = 'ALL'
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
                if isinstance(player_guids_json, str):
                    player_guids = json.loads(player_guids_json) if player_guids_json else []
                else:
                    player_guids = player_guids_json or []
                team_names_list.append(team_name)
                team_guids_list.append(set(player_guids))

            # Map game team numbers to actual team names
            if session_ids:
                placeholders = ",".join(["?" for _ in session_ids])
                sample_query = f"""
                    SELECT p.player_guid, p.team
                    FROM player_comprehensive_stats p
                    JOIN rounds r ON r.id = p.round_id
                    WHERE p.round_id IN ({placeholders})
                      AND p.round_number = 1
                    ORDER BY r.round_date, r.round_time
                    LIMIT 1
                """
                sample_player = await self.db.fetch_one(sample_query, tuple(session_ids))
            elif resolved_session_id is not None:
                sample_query = """
                    SELECT p.player_guid, p.team
                    FROM player_comprehensive_stats p
                    JOIN rounds r ON r.id = p.round_id
                    WHERE r.gaming_session_id = ?
                      AND p.round_number = 1
                    ORDER BY p.round_date, p.round_time
                    LIMIT 1
                """
                sample_player = await self.db.fetch_one(sample_query, (resolved_session_id,))
            else:
                sample_query = """
                    SELECT player_guid, team
                    FROM player_comprehensive_stats
                    WHERE SUBSTRING(round_date, 1, 10) = ?
                      AND round_number = 1
                    ORDER BY round_date, round_time
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

            # Record matchup for analytics
            await self._record_matchup_analytics(
                lineup_a_guids=team_1_guids,
                lineup_b_guids=team_2_guids,
                session_date=session_date,
                gaming_session_id=gaming_session_id,
                winner='a' if team_1_score > team_2_score else ('b' if team_2_score > team_1_score else None),
                lineup_a_score=team_1_score,
                lineup_b_score=team_2_score
            )

            return True

        except Exception as e:
            logger.error(f"Failed to save session results: {e}", exc_info=True)
            return False

    async def _record_matchup_analytics(
        self,
        lineup_a_guids: List[str],
        lineup_b_guids: List[str],
        session_date: str,
        gaming_session_id: int,
        winner: Optional[str],
        lineup_a_score: int,
        lineup_b_score: int,
        map_name: Optional[str] = None
    ):
        """
        Record matchup for analytics tracking.

        Args:
            lineup_a_guids: GUIDs for lineup A
            lineup_b_guids: GUIDs for lineup B
            session_date: Session date
            gaming_session_id: Gaming session ID
            winner: 'a', 'b', or None for tie
            lineup_a_score: Score for lineup A
            lineup_b_score: Score for lineup B
            map_name: Optional map name
        """
        try:
            from bot.services.matchup_analytics_service import MatchupAnalyticsService

            matchup_service = MatchupAnalyticsService(self.db)

            # Get player stats for this session
            placeholders = ','.join(['$' + str(i+1) for i in range(1)])
            query = """
                SELECT player_guid, MAX(player_name) as name,
                       SUM(kills) as kills, SUM(deaths) as deaths,
                       CASE WHEN SUM(time_played_seconds) > 0
                            THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                            ELSE 0 END as dpm,
                       CASE WHEN SUM(deaths) > 0
                            THEN SUM(kills)::float / SUM(deaths)
                            ELSE SUM(kills) END as kd
                FROM player_comprehensive_stats
                WHERE round_date LIKE $1
                  AND round_number IN (1, 2)
                GROUP BY player_guid
            """
            rows = await self.db.fetch_all(query, (f"{session_date}%",))

            player_stats = {}
            for row in rows:
                guid, name, kills, deaths, dpm, kd = row
                player_stats[guid] = {
                    'name': name,
                    'kills': int(kills or 0),
                    'deaths': int(deaths or 0),
                    'dpm': float(dpm or 0),
                    'kd': float(kd or 0)
                }

            await matchup_service.record_matchup(
                lineup_a_guids=lineup_a_guids,
                lineup_b_guids=lineup_b_guids,
                session_date=session_date,
                gaming_session_id=gaming_session_id,
                winner_lineup=winner,
                lineup_a_score=lineup_a_score,
                lineup_b_score=lineup_b_score,
                map_name=map_name,
                player_stats=player_stats
            )

        except Exception as e:
            logger.warning(f"Failed to record matchup analytics (non-fatal): {e}")

    async def calculate_session_scores_with_teams(
        self,
        session_date: str,
        session_ids: List[int],
        team_rosters: Dict[str, List[str]]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate map scores and map side-winner to persistent teams.

        This method combines stopwatch scoring with team detection to produce
        accurate session scores where Team A vs Team B is tracked across
        side swaps.

        Stopwatch Mode Logic (map-winner):
        - Round 1: Team A attacks (as Axis), Team B defends (as Allies)
        - Round 2: Teams swap sides - Team B attacks (as Axis), Team A defends (as Allies)
        - Map winner by time:
          - Both complete → faster time wins (tie goes to R1 attackers)
          - Only one completes → that team wins
          - Neither completes/unknown → tie
        - Map points = 1 point to map winner (0-0 for tie)

        Key insight: `defender_team` in R1 tells us which SIDE defended.
        We need to map that side to persistent team using player GUIDs.

        Args:
            session_date: Session date (YYYY-MM-DD)
            session_ids: List of round IDs in this session
            team_rosters: Dict mapping team_name -> list of player_guids
                         e.g., {"puran": ["guid1", "guid2"], "sWat": ["guid3", "guid4"]}

        Returns:
            Dict with team names as keys and map scores, plus detailed breakdown
        """
        try:
            if not team_rosters or len(team_rosters) < 2:
                logger.debug("Not enough team rosters for team-aware scoring")
                return None

            # Get team names and GUIDs
            team_names = list(team_rosters.keys())
            team_a_name = team_names[0]
            team_b_name = team_names[1]
            team_a_guids = set(team_rosters[team_a_name])
            team_b_guids = set(team_rosters[team_b_name])

            # Fetch rounds with timing data
            placeholders = ','.join(['$' + str(i+1) for i in range(len(session_ids))])
            # nosec B608 - safe: parameterized placeholders
            rounds_query = f"""
                SELECT r.id, r.map_name, r.gaming_session_id, r.round_number,
                       r.defender_team, r.winner_team, r.time_limit, r.actual_time,
                       r.round_date, r.round_time
                FROM rounds r
                WHERE r.id IN ({placeholders})
                AND r.round_status = 'completed'
                ORDER BY r.gaming_session_id,
                         r.round_date,
                         CAST(REPLACE(r.round_time, ':', '') AS INTEGER),
                         r.round_number
            """
            rows = await self.db.fetch_all(rounds_query, tuple(session_ids))

            if not rows:
                logger.debug(f"No completed rounds found for session {session_date}")
                return None

            # Group rounds into map pairs (R1 + R2)
            maps_dict: Dict[str, Dict] = {}
            pending_r1: Dict[str, str] = {}
            map_play_count: Dict[str, int] = {}

            for row in rows:
                (round_id, map_name, gaming_session_id, round_num,
                 defender_team, winner_team, time_limit, actual_time,
                 round_date, round_time) = row

                base_key = f"{gaming_session_id}:{map_name}"

                round_data = {
                    'round_id': round_id,
                    'defender_team': defender_team,
                    'winner_team': winner_team,
                    'time_limit': time_limit,
                    'actual_time': actual_time,
                    'round_date': round_date,
                    'round_time': round_time
                }

                if round_num == 1:
                    if base_key not in map_play_count:
                        map_play_count[base_key] = 0
                    map_play_count[base_key] += 1
                    play_num = map_play_count[base_key]

                    map_key = f"{base_key}:play{play_num}"
                    maps_dict[map_key] = {
                        'map_name': map_name,
                        'gaming_session_id': gaming_session_id,
                        'round1': round_data,
                        'round2': None
                    }
                    pending_r1[base_key] = map_key

                elif round_num == 2:
                    if base_key in pending_r1:
                        map_key = pending_r1[base_key]
                        if map_key in maps_dict:
                            maps_dict[map_key]['round2'] = round_data
                        del pending_r1[base_key]

            # Separate complete and incomplete map pairs
            complete_maps = [
                m for m in maps_dict.values()
                if m['round1'] is not None and m['round2'] is not None
            ]
            incomplete_maps = [
                m for m in maps_dict.values()
                if m['round1'] is not None and m['round2'] is None
            ]

            if not complete_maps and not incomplete_maps:
                logger.debug(f"No map data found for {session_date}")
                return None

            # For each map, determine which persistent team was attacking in R1
            # We need to look at player stats to see which team was on which side
            sample_query = """
                SELECT player_guid, team
                FROM player_comprehensive_stats
                WHERE round_id = $1
            """

            # Initialize scores
            team_a_maps = 0
            team_b_maps = 0
            map_results = []

            for map_data in complete_maps:
                r1 = map_data['round1']
                r2 = map_data['round2']
                map_name = map_data['map_name']

                # Get player→side mapping for R1 to determine team→side
                r1_players = await self.db.fetch_all(sample_query, (r1['round_id'],))

                # Count how many players from each team were on each side in R1
                team_a_on_side = {1: 0, 2: 0}
                team_b_on_side = {1: 0, 2: 0}

                def _normalize_side(value):
                    if value in (1, '1', 'Axis', 'axis'):
                        return 1
                    if value in (2, '2', 'Allies', 'allies'):
                        return 2
                    return None

                for player_guid, side in r1_players:
                    side_key = _normalize_side(side)
                    if side_key is None:
                        continue
                    if player_guid in team_a_guids:
                        team_a_on_side[side_key] = team_a_on_side.get(side_key, 0) + 1
                    elif player_guid in team_b_guids:
                        team_b_on_side[side_key] = team_b_on_side.get(side_key, 0) + 1

                # Determine which side Team A was on in R1 (majority wins)
                ambiguous_team_sides = False
                team_a_r1_side = None
                if team_a_on_side[1] > team_a_on_side[2]:
                    team_a_r1_side = 1
                elif team_a_on_side[2] > team_a_on_side[1]:
                    team_a_r1_side = 2
                else:
                    # Tie or no Team A players: use Team B as inverse if possible
                    if team_b_on_side[1] > team_b_on_side[2]:
                        team_a_r1_side = 2
                    elif team_b_on_side[2] > team_b_on_side[1]:
                        team_a_r1_side = 1
                    else:
                        ambiguous_team_sides = True

                def _infer_defender_side_from_winner(r1_data):
                    """Infer defender side using winner_team + time (fallback when header is stale)."""
                    winner_side = r1_data.get('winner_team')
                    if winner_side not in (1, 2):
                        return None

                    limit_sec = self.parse_time_to_seconds(r1_data.get('time_limit'))
                    actual_sec = self.parse_time_to_seconds(r1_data.get('actual_time'))
                    if limit_sec <= 0 or actual_sec <= 0:
                        return None

                    attackers_succeed = actual_sec < limit_sec
                    if attackers_succeed:
                        return 2 if winner_side == 1 else 1
                    return winner_side

                # R1 attackers are NOT the defender_team side
                # defender_team tells us which SIDE defended
                r1_defender_side = r1.get('defender_team', 2)
                inferred_defender_side = _infer_defender_side_from_winner(r1)

                if r1_defender_side not in (1, 2):
                    r1_defender_side = inferred_defender_side or 2  # Default Allies defend
                elif inferred_defender_side and inferred_defender_side != r1_defender_side:
                    logger.warning(
                        f"Defender side mismatch for {map_name} (R1). "
                        f"Header={r1_defender_side}, inferred={inferred_defender_side}; "
                        "using inferred value."
                    )
                    r1_defender_side = inferred_defender_side

                if ambiguous_team_sides:
                    # Cannot infer team sides reliably; skip scoring this map
                    map_results.append({
                        'map': map_name,
                        'team_a_points': 0,
                        'team_b_points': 0,
                        'team_a_time': '',
                        'team_b_time': '',
                        'winner': 'tie',
                        'emoji': '⚪',
                        'description': 'Unscored: team sides ambiguous',
                        'winner_side': r2.get('winner_team'),
                        'team_a_r1_side': None,
                        'team_a_r2_side': None,
                        'r1_defender_side': r1.get('defender_team'),
                        'scoring_source': 'ambiguous',
                        'counted': False,
                        'note': 'Unscored: team sides ambiguous'
                    })
                    logger.debug(
                        "[SCORING DEBUG] %s | ambiguous sides; skipping score",
                        map_name
                    )
                    continue

                if team_a_r1_side is None:
                    # Fall back using defender side if team counts were inconclusive
                    if team_a_on_side.get(r1_defender_side, 0) > team_b_on_side.get(r1_defender_side, 0):
                        team_a_r1_side = r1_defender_side
                    elif team_b_on_side.get(r1_defender_side, 0) > team_a_on_side.get(r1_defender_side, 0):
                        team_a_r1_side = 1 if r1_defender_side == 2 else 2
                    else:
                        # Final fallback
                        team_a_r1_side = 1

                # Was Team A attacking or defending in R1?
                team_a_attacking_r1 = (team_a_r1_side != r1_defender_side)

                team_a_pts = 0
                team_b_pts = 0
                desc = "Map tie: no completion or time data"
                scoring_source = "time"

                # Prefer header winner side from R2 (map winner in stopwatch)
                winner_side = r2.get('winner_team')
                if winner_side in (1, 2) and team_a_r1_side in (1, 2):
                    team_a_r2_side = 2 if team_a_r1_side == 1 else 1
                    if winner_side == team_a_r2_side:
                        team_a_pts = 1
                        desc = f"Map win: side {winner_side} (R2 winner)"
                    else:
                        team_b_pts = 1
                        desc = f"Map win: side {winner_side} (R2 winner)"
                    scoring_source = "header"
                else:
                    # Fallback to time-based scoring
                    team1_pts, team2_pts, desc = self.calculate_map_score(
                        r1['time_limit'], r1['actual_time'], r2['actual_time']
                    )

                    # team1_pts = R1 attackers' score, team2_pts = R2 attackers' (R1 defenders)
                    # Map back to persistent teams
                    if team_a_attacking_r1:
                        # Team A attacked R1, so team1_pts goes to Team A
                        team_a_pts = team1_pts
                        team_b_pts = team2_pts
                    else:
                        # Team B attacked R1, so team1_pts goes to Team B
                        team_a_pts = team2_pts
                        team_b_pts = team1_pts
                    scoring_source = "time"

                team_a_maps += team_a_pts
                team_b_maps += team_b_pts

                # Format timing for display
                r1_time = r1['actual_time'] or "fullhold"
                r2_time = r2['actual_time'] or "fullhold"
                limit_sec = self.parse_time_to_seconds(r1['time_limit'])
                r1_sec = self.parse_time_to_seconds(r1_time) if r1_time != "fullhold" else limit_sec
                r2_sec = self.parse_time_to_seconds(r2_time) if r2_time != "fullhold" else limit_sec

                # Determine if times are fullholds
                r1_fullhold = (r1_sec >= limit_sec) if limit_sec > 0 else False
                r2_fullhold = (r2_sec >= limit_sec) if limit_sec > 0 else False

                # Build timing display
                if team_a_attacking_r1:
                    team_a_time = "fullhold" if r1_fullhold else r1['actual_time']
                    team_b_time = "fullhold" if r2_fullhold else r2['actual_time']
                else:
                    team_a_time = "fullhold" if r2_fullhold else r2['actual_time']
                    team_b_time = "fullhold" if r1_fullhold else r1['actual_time']

                # Determine map winner for emoji
                if team_a_pts > team_b_pts:
                    winner = team_a_name
                    emoji = "🟢"
                elif team_b_pts > team_a_pts:
                    winner = team_b_name
                    emoji = "🔴"
                else:
                    winner = "tie"
                    emoji = "🟡"

                map_results.append({
                    'map': map_name,
                    'team_a_points': team_a_pts,
                    'team_b_points': team_b_pts,
                    'team_a_time': team_a_time,
                    'team_b_time': team_b_time,
                    'winner': winner,
                    'emoji': emoji,
                    'description': desc,
                    'winner_side': winner_side,
                    'team_a_r1_side': team_a_r1_side,
                    'team_a_r2_side': 2 if team_a_r1_side == 1 else 1,
                    'r1_defender_side': r1_defender_side,
                    'scoring_source': scoring_source,
                    'counted': True
                })

                logger.debug(
                    "[SCORING DEBUG] %s | winner_side=%s | teamA_r1_side=%s teamA_r2_side=%s | "
                    "r1_def=%s | teamA_pts=%s teamB_pts=%s | source=%s",
                    map_name,
                    winner_side,
                    team_a_r1_side,
                    2 if team_a_r1_side == 1 else 1,
                    r1_defender_side,
                    team_a_pts,
                    team_b_pts,
                    scoring_source
                )

            # Add incomplete maps as not-counted entries (R1 only)
            for map_data in incomplete_maps:
                r1 = map_data['round1']
                map_name = map_data['map_name']
                map_results.append({
                    'map': map_name,
                    'team_a_points': 0,
                    'team_b_points': 0,
                    'team_a_time': '',
                    'team_b_time': '',
                    'winner': 'tie',
                    'emoji': '⚪',
                    'description': 'R1 only (not counted)',
                    'winner_side': None,
                    'team_a_r1_side': None,
                    'team_a_r2_side': None,
                    'r1_defender_side': r1.get('defender_team'),
                    'scoring_source': 'incomplete',
                    'counted': False,
                    'note': 'R1 only (not counted)'
                })

            # Build result
            result = {
                'team_a_name': team_a_name,
                'team_b_name': team_b_name,
                'team_a_maps': team_a_maps,
                'team_b_maps': team_b_maps,
                'maps': map_results,
                'total_maps': len(map_results),
                # Legacy compatibility
                team_a_name: team_a_maps,
                team_b_name: team_b_maps,
                # Internal fields for save_session_results
                '_team1_name': team_a_name,
                '_team2_name': team_b_name,
                '_team1_score': team_a_maps,
                '_team2_score': team_b_maps,
                '_team1_guids': list(team_a_guids),
                '_team2_guids': list(team_b_guids),
                '_gaming_session_id': complete_maps[0]['gaming_session_id'] if complete_maps else None,
                '_session_date': session_date
            }

            logger.info(f"Calculated team scores: {team_a_name} {team_a_maps} - {team_b_maps} {team_b_name}")
            return result

        except Exception as e:
            logger.error(f"Error calculating team-aware session scores: {e}", exc_info=True)
            return None
