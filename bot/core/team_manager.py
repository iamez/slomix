"""
Team Manager - Core Team Tracking System

This module handles all team-related functionality:
- Automatic team detection from game sessions
- Team roster tracking and lineup changes
- Win/Loss records per lineup
- Custom team names (overriding Team A/Team B)
- Session scoring and map performance

The game uses Axis/Allies (roles that switch), but we track persistent teams
across the entire session regardless of which side they play on.
"""

import json
import logging
import os
from typing import Dict, List, Tuple, Optional, Set, Any
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)


class TeamManager:
    """Manages team detection, tracking, and statistics"""

    def __init__(self, db_adapter, config=None):
        """
        Initialize TeamManager with async database adapter.

        Args:
            db_adapter: DatabaseAdapter instance (supports both SQLite and PostgreSQL)
        """
        self.db = db_adapter
        self._session_teams_columns = None
        if config is not None:
            self.enable_map_performance = getattr(
                config, "enable_team_map_performance", False
            )
        else:
            self.enable_map_performance = (
                os.getenv("ENABLE_TEAM_MAP_PERFORMANCE", "false").lower() == "true"
            )

    async def _ensure_session_teams_table(self) -> None:
        """
        Ensure session_teams table exists (safe no-op if already present).
        """
        await self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS session_teams (
                session_start_date TEXT NOT NULL,
                map_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                player_guids TEXT,
                player_names TEXT,
                gaming_session_id INTEGER,
                color INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (session_start_date, map_name, team_name)
            )
            """
        )

    async def _get_session_teams_columns(self) -> Set[str]:
        """
        Fetch session_teams column names (cached).
        """
        if self._session_teams_columns is not None:
            return self._session_teams_columns

        try:
            rows = await self.db.fetch_all(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'session_teams'
                """
            )
            self._session_teams_columns = {row[0] for row in rows}
        except Exception:
            # If schema inspection fails, fall back to minimal known columns.
            self._session_teams_columns = {
                "session_start_date",
                "map_name",
                "team_name",
                "player_guids",
                "player_names",
            }

        return self._session_teams_columns

    # =========================================================================
    # REAL-TIME TEAM TRACKING (New approach - Feb 2026)
    # Create teams on R1, track additions on subsequent rounds
    # =========================================================================

    async def create_initial_teams_from_round(
        self,
        round_id: int,
        session_date: str,
        gaming_session_id: int
    ) -> bool:
        """
        Create initial team assignments from the first round of a new session.

        Called when R1 of a new gaming session is imported. At this point:
        - Players haven't swapped sides yet
        - Side 1 = Team A, Side 2 = Team B (clean split)

        Args:
            round_id: The round ID that was just imported
            session_date: Session date (YYYY-MM-DD)
            gaming_session_id: The gaming session ID

        Returns:
            True if teams were created successfully
        """
        try:
            await self._ensure_session_teams_table()
            columns = await self._get_session_teams_columns()

            # Check if teams already exist for this session
            existing = await self.db.fetch_one(
                """
                SELECT COUNT(*) FROM session_teams
                WHERE session_start_date LIKE $1 AND map_name = 'ALL'
                """,
                (f"{session_date}%",)
            )

            if existing and existing[0] > 0:
                logger.debug(f"Teams already exist for session {session_date}, skipping creation")
                return True

            # Get all players from this round with their sides
            query = """
                SELECT player_guid, player_name, team
                FROM player_comprehensive_stats
                WHERE round_id = $1
            """
            rows = await self.db.fetch_all(query, (round_id,))

            if not rows:
                logger.warning(f"No players found in round {round_id}")
                return False

            # Split by side - side 1 = Team A, side 2 = Team B
            team_a_guids = []
            team_a_names = []
            team_b_guids = []
            team_b_names = []

            for guid, name, side in rows:
                if side in (1, '1', 'Axis', 'axis'):
                    team_a_guids.append(guid)
                    team_a_names.append(name)
                elif side in (2, '2', 'Allies', 'allies'):
                    team_b_guids.append(guid)
                    team_b_names.append(name)
                else:
                    logger.warning(f"Unknown side {side} for player {name}")

            if not team_a_guids and not team_b_guids:
                logger.warning(f"No players assigned to teams in round {round_id}")
                return False

            # Store teams with default names (will be randomly assigned later)
            teams = {
                'Team A': {
                    'guids': sorted(team_a_guids),
                    'names': sorted(team_a_names),
                    'count': len(team_a_guids)
                },
                'Team B': {
                    'guids': sorted(team_b_guids),
                    'names': sorted(team_b_names),
                    'count': len(team_b_guids)
                }
            }

            # Store in database
            for team_name, team_data in teams.items():
                if "gaming_session_id" in columns:
                    await self.db.execute(
                        """
                        INSERT INTO session_teams
                        (session_start_date, map_name, team_name, player_guids, player_names, gaming_session_id)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                            player_guids = EXCLUDED.player_guids,
                            player_names = EXCLUDED.player_names,
                            gaming_session_id = EXCLUDED.gaming_session_id
                        """,
                        (
                            session_date,
                            "ALL",
                            team_name,
                            json.dumps(team_data["guids"]),
                            json.dumps(team_data["names"]),
                            gaming_session_id,
                        ),
                    )
                else:
                    await self.db.execute(
                        """
                        INSERT INTO session_teams
                        (session_start_date, map_name, team_name, player_guids, player_names)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (session_start_date, map_name, team_name) DO UPDATE SET
                            player_guids = EXCLUDED.player_guids,
                            player_names = EXCLUDED.player_names
                        """,
                        (
                            session_date,
                            "ALL",
                            team_name,
                            json.dumps(team_data["guids"]),
                            json.dumps(team_data["names"]),
                        ),
                    )

            # Auto-assign random team names
            try:
                team_a_final, team_b_final = await self.assign_random_team_names(session_date, force=True)
                logger.info(f"🎯 Created teams for session {session_date}: "
                           f"{team_a_final} ({len(team_a_guids)}p) vs {team_b_final} ({len(team_b_guids)}p)")
            except Exception as e:
                logger.warning(f"Could not assign random team names: {e}")
                logger.info(f"🎯 Created teams for session {session_date}: "
                           f"Team A ({len(team_a_guids)}p) vs Team B ({len(team_b_guids)}p)")

            return True

        except Exception as e:
            logger.error(f"Failed to create initial teams: {e}", exc_info=True)
            return False

    async def update_teams_from_round(
        self,
        round_id: int,
        session_date: str,
        gaming_session_id: int
    ) -> Dict[str, List[str]]:
        """
        Update teams with any new players from a round.

        Called after each round is imported. Checks for new players and adds
        them to the appropriate team based on which side they're on.

        In stopwatch mode, sides swap between R1 and R2, but within a round,
        new players joining a side join the same persistent team as existing
        players on that side.

        Args:
            round_id: The round ID that was just imported
            session_date: Session date (YYYY-MM-DD)
            gaming_session_id: The gaming session ID

        Returns:
            Dict of new players added: {'Team A': ['player1'], 'Team B': ['player2']}
        """
        try:
            await self._ensure_session_teams_table()

            # Get existing teams
            teams_data = await self.get_session_teams(session_date, auto_detect=False)
            if not teams_data:
                logger.debug(f"No teams found for {session_date}, cannot update")
                return {}

            # Get all GUIDs currently in teams
            team_names = list(teams_data.keys())
            all_known_guids = set()
            team_guid_sets = {}

            for team_name in team_names:
                guids = set(teams_data[team_name].get('guids', []))
                team_guid_sets[team_name] = guids
                all_known_guids.update(guids)

            # Get players from this round
            query = """
                SELECT player_guid, player_name, team
                FROM player_comprehensive_stats
                WHERE round_id = $1
            """
            rows = await self.db.fetch_all(query, (round_id,))

            if not rows:
                return {}

            # Group round players by side
            side_players = {1: [], 2: []}
            for guid, name, side in rows:
                if side in (1, '1', 'Axis', 'axis'):
                    side_key = 1
                elif side in (2, '2', 'Allies', 'allies'):
                    side_key = 2
                else:
                    # Ignore spectators/unknown teams
                    continue
                side_players[side_key].append((guid, name))

            # Find which team is currently on which side
            # Look at overlap: which team's players are on which side in this round
            team_to_side = {}
            for side, players in side_players.items():
                side_guids = {p[0] for p in players}
                for team_name, team_guids in team_guid_sets.items():
                    overlap = len(side_guids & team_guids)
                    if overlap > 0:
                        if team_name not in team_to_side or overlap > team_to_side[team_name][1]:
                            team_to_side[team_name] = (side, overlap)

            # Build side to team mapping
            side_to_team = {}
            for team_name, (side, _) in team_to_side.items():
                if side not in side_to_team:
                    side_to_team[side] = team_name

            # Find new players and add them to appropriate teams
            new_players = {'added': {}}

            for side, players in side_players.items():
                for guid, name in players:
                    if guid not in all_known_guids:
                        # New player! Add to the team on this side
                        target_team = side_to_team.get(side)
                        if target_team:
                            # Update the team
                            team_data = teams_data[target_team]
                            guids = team_data.get('guids', [])
                            names = team_data.get('names', [])

                            if guid not in guids:
                                guids.append(guid)
                                names.append(name)

                                # Update database
                                await self.db.execute(
                                    """
                                    UPDATE session_teams
                                    SET player_guids = $1, player_names = $2
                                    WHERE session_start_date LIKE $3
                                      AND map_name = 'ALL'
                                      AND team_name = $4
                                    """,
                                    (
                                        json.dumps(guids),
                                        json.dumps(names),
                                        f"{session_date}%",
                                        target_team
                                    )
                                )

                                if target_team not in new_players['added']:
                                    new_players['added'][target_team] = []
                                new_players['added'][target_team].append(name)

                                logger.info(f"➕ Added {name} to {target_team} (joined on side {side})")

            return new_players

        except Exception as e:
            logger.error(f"Failed to update teams from round: {e}", exc_info=True)
            return {}

    async def detect_session_teams(
        self,
        session_date: str
    ) -> Dict[str, Dict]:
        """
        Automatically detect persistent teams for a session.

        Algorithm:
        1. Seed from Round 1 (or earliest available round)
        2. Use defender_team from R1 to strengthen team assignments (authoritative)
        3. For late joiners, use co-membership voting (who they played with most)
        4. Return team rosters with GUIDs and names

        Enhancements (Jan 2026):
        - Uses defender_team from stats file headers for validation
        - In stopwatch R1, defender_team is one persistent team's initial role
        - Players on defender_team in R1 confirmed as same persistent team

        Args:
            session_date: Session date (YYYY-MM-DD format)

        Returns:
            {
                'Team A': {
                    'guids': ['guid1', 'guid2', ...],
                    'names': ['Player1', 'Player2', ...],
                    'count': 5,
                    'detection_confidence': 'high'  # 'high'/'medium'/'low'
                },
                'Team B': { ... }
            }
        """
        # Get all players from session grouped by round_id and game-team
        # IMPORTANT: Use round_id (unique per map+round), NOT round_number (1 or 2)
        # because in stopwatch mode, teams swap between maps!
        # ALSO: Include defender_team for validation (Jan 2026)
        query = """
            SELECT p.round_id, p.team, p.player_guid, p.player_name,
                   r.round_number, r.defender_team, r.round_date, r.round_time
            FROM player_comprehensive_stats p
            JOIN rounds r ON p.round_id = r.id
            WHERE p.round_date LIKE $1
              AND p.round_number IN (1, 2)
            ORDER BY r.round_date, r.round_time, p.round_id, p.team
        """
        rows = await self.db.fetch_all(query, (f"{session_date}%",))

        if not rows:
            logger.warning(f"No player data found for session {session_date}")
            return {}

        # Organize by round_id (each map's R1/R2 is a unique round_id)
        rounds = defaultdict(lambda: {'team1': set(), 'team2': set()})
        player_names = {}  # guid -> most recent name
        round_meta = {}  # Store metadata (round_number, defender_team, round_date, round_time) per round_id

        # Check what team values we're getting
        team_values = set()
        for row_data in rows:
            if len(row_data) >= 8:
                round_id, game_team, guid, name, round_number, defender_team, round_date, round_time = row_data[0:8]
            else:
                # Fallback for older tuple format
                round_id, game_team, guid, name = row_data[0:4]
                round_number = None
                defender_team = None
                round_date = ""
                round_time = ""

            team_values.add(game_team)
            player_names[guid] = name

            # Store metadata
            if round_id not in round_meta:
                round_meta[round_id] = {
                    'round_number': round_number,
                    'defender_team': defender_team,
                    'round_date': round_date,
                    'round_time': round_time
                }

            # Handle both integer (1/2) and possible string ('1'/'2') team values
            # Also handle Axis=1, Allies=2 convention
            if game_team in (1, '1', 'Axis', 'axis'):
                team_key = 'team1'
            elif game_team in (2, '2', 'Allies', 'allies'):
                team_key = 'team2'
            else:
                # Unknown team value - log and skip
                logger.debug(f"Unknown team value {game_team} for {name} in round_id {round_id}")
                continue
            rounds[round_id][team_key].add(guid)

        logger.info(f"Team values found in data: {team_values}, {len(rounds)} unique rounds")
        
        # Seed from earliest Round 1 (prefer actual Round 1 by timestamp)
        # This gives us the initial team composition before any stopwatch swaps
        def _normalize_time(t):
            if not t:
                return "000000"
            return str(t).replace(":", "").zfill(6)

        r1_candidates = [
            rid for rid, meta in round_meta.items()
            if meta.get('round_number') == 1
        ]
        if r1_candidates:
            earliest_round_id = min(
                r1_candidates,
                key=lambda rid: (
                    round_meta[rid].get('round_date', ''),
                    _normalize_time(round_meta[rid].get('round_time', ''))
                )
            )
        else:
            earliest_round_id = min(
                rounds.keys(),
                key=lambda rid: (
                    round_meta.get(rid, {}).get('round_date', ''),
                    _normalize_time(round_meta.get(rid, {}).get('round_time', ''))
                )
            )
        persistent_team1 = set(rounds[earliest_round_id]['team1'])
        persistent_team2 = set(rounds[earliest_round_id]['team2'])

        logger.info(f"Seeded teams from round_id {earliest_round_id}: "
                   f"Team1={len(persistent_team1)}, Team2={len(persistent_team2)}")

        # Validate: If one team is empty but we have players, something is wrong
        all_players = set(player_names.keys())
        if len(persistent_team1) == 0 and len(persistent_team2) > 0:
            logger.warning(f"⚠️ Team detection issue: All {len(persistent_team2)} players in team2, none in team1")
            logger.warning(f"Team values in data: {team_values} - check if 'team' column is populated correctly")
        elif len(persistent_team2) == 0 and len(persistent_team1) > 0:
            logger.warning(f"⚠️ Team detection issue: All {len(persistent_team1)} players in team1, none in team2")
            logger.warning(f"Team values in data: {team_values} - check if 'team' column is populated correctly")
        
        # Handle late joiners using co-membership voting
        all_players = set(player_names.keys())
        unassigned = all_players - persistent_team1 - persistent_team2

        if unassigned:
            logger.info(f"Assigning {len(unassigned)} late joiners...")
            for guid in unassigned:
                # Count which team they co-appeared with more often
                team1_votes = 0
                team2_votes = 0

                for round_id, teams in rounds.items():
                    if guid in teams['team1']:
                        # Check overlap with persistent teams
                        team1_overlap = len(teams['team1'] & persistent_team1)
                        team2_overlap = len(teams['team1'] & persistent_team2)
                        team1_votes += team1_overlap
                        team2_votes += team2_overlap
                    elif guid in teams['team2']:
                        team1_overlap = len(teams['team2'] & persistent_team1)
                        team2_overlap = len(teams['team2'] & persistent_team2)
                        team1_votes += team1_overlap
                        team2_votes += team2_overlap

                # Assign to team with most votes
                if team1_votes > team2_votes:
                    persistent_team1.add(guid)
                    logger.debug(f"Assigned {player_names[guid]} to Team1 "
                               f"(votes: {team1_votes} vs {team2_votes})")
                else:
                    persistent_team2.add(guid)
                    logger.debug(f"Assigned {player_names[guid]} to Team2 "
                               f"(votes: {team1_votes} vs {team2_votes})")
        
        # Calculate detection confidence based on consistency and data validation
        # High confidence: Teams consistent across multiple maps, defender_team aligns
        # Medium confidence: Teams detected but some variations, or single map session
        # Low confidence: Inconsistent team assignments or heavy reliance on late-joiner voting

        early_round_ids = sorted(rounds.keys())[:3]  # Check first few maps
        consistent_count = 0

        for rid in early_round_ids:
            if rid in round_meta:
                meta = round_meta[rid]
                # Check if defender_team in R1 aligns with our team assignments
                if meta.get('round_number') == 1 and meta.get('defender_team'):
                    defender = meta['defender_team']
                    # If defender is in team1, that's good confirmation
                    if defender in (1, '1') and persistent_team1:
                        consistent_count += 1
                    elif defender in (2, '2') and persistent_team2:
                        consistent_count += 1

        # Confidence logic
        if len(unassigned) == 0 and consistent_count >= len(early_round_ids) * 0.7:
            confidence = 'high'
        elif len(unassigned) <= 1 and consistent_count >= 1:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Build result with confidence scores
        teams = {
            'Team A': {
                'guids': sorted(list(persistent_team1)),
                'names': sorted([player_names[g] for g in persistent_team1]),
                'count': len(persistent_team1),
                'detection_confidence': confidence
            },
            'Team B': {
                'guids': sorted(list(persistent_team2)),
                'names': sorted([player_names[g] for g in persistent_team2]),
                'count': len(persistent_team2),
                'detection_confidence': confidence
            }
        }

        logger.info(f"✅ Detected teams for {session_date}: "
                   f"Team A ({teams['Team A']['count']} players), "
                   f"Team B ({teams['Team B']['count']} players) "
                   f"(confidence: {confidence})")

        return teams
    
    async def store_session_teams(
        self,
        session_date: str,
        teams: Dict[str, Dict],
        auto_assign_names: bool = True
    ) -> bool:
        """
        Store detected teams in the session_teams table.

        Args:
            session_date: Session date (YYYY-MM-DD)
            teams: Team data from detect_session_teams()
            auto_assign_names: If True, assign random team names from pool

        Returns:
            True if successful
        """
        await self._ensure_session_teams_table()

        # Delete existing entries for this session
        await self.db.execute(
            "DELETE FROM session_teams WHERE session_start_date LIKE $1 AND map_name = 'ALL'",
            (f"{session_date}%",)
        )

        # Insert new team data
        for team_name, team_data in teams.items():
            await self.db.execute(
                """
                INSERT INTO session_teams
                (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES ($1, 'ALL', $2, $3, $4)
                """,
                (
                    session_date,
                    team_name,
                    json.dumps(team_data['guids']),
                    json.dumps(team_data['names'])
                )
            )

        logger.info(f"✅ Stored teams for session {session_date}")

        # Auto-assign random team names from pool
        if auto_assign_names:
            try:
                team_a, team_b = await self.assign_random_team_names(session_date, force=True)
                logger.info(f"✅ Auto-assigned team names: {team_a} vs {team_b}")
            except Exception as e:
                logger.warning(f"Failed to auto-assign team names: {e}")
                # Continue anyway - teams are stored with default names

        return True
    
    async def get_session_teams(
        self,
        session_date: str,
        auto_detect: bool = True
    ) -> Dict[str, Dict]:
        """
        Get teams for a session (from DB or auto-detect).

        Args:
            session_date: Session date (YYYY-MM-DD)
            auto_detect: If True, auto-detect and store if not found

        Returns:
            Team data dictionary
        """
        await self._ensure_session_teams_table()

        # Try to get from database
        rows = await self.db.fetch_all(
            """
            SELECT team_name, player_guids, player_names
            FROM session_teams
            WHERE session_start_date LIKE $1 AND map_name = 'ALL'
            ORDER BY team_name
            """,
            (f"{session_date}%",)
        )

        if rows:
            teams = {}
            for team_name, guids_json, names_json in rows:
                teams[team_name] = {
                    'guids': json.loads(guids_json),
                    'names': json.loads(names_json),
                    'count': len(json.loads(guids_json))
                }

            # Validate: Check for corrupted data (both teams have identical players)
            team_keys = list(teams.keys())
            if len(team_keys) >= 2:
                guids_a = set(teams[team_keys[0]].get('guids', []))
                guids_b = set(teams[team_keys[1]].get('guids', []))
                if guids_a == guids_b and len(guids_a) > 0:
                    logger.warning(f"⚠️ Corrupted team data for {session_date}: "
                                 f"both teams have identical {len(guids_a)} players. Re-detecting...")
                    # Delete corrupted data and re-detect
                    await self.db.execute(
                        "DELETE FROM session_teams WHERE session_start_date LIKE $1",
                        (f"{session_date}%",)
                    )
                    if auto_detect:
                        teams = await self.detect_session_teams(session_date)
                        if teams:
                            await self.store_session_teams(session_date, teams, auto_assign_names=False)
                        return teams
                    return {}

            logger.info(f"✅ Found stored teams for {session_date}")
            return teams

        # Auto-detect if requested
        if auto_detect:
            logger.info(f"No stored teams found for {session_date}, auto-detecting...")
            teams = await self.detect_session_teams(session_date)
            if teams:
                # Don't auto-assign names here - let caller decide
                await self.store_session_teams(session_date, teams, auto_assign_names=False)
            return teams

        return {}
    
    async def detect_lineup_changes(
        self,
        session_date: str,
        previous_session_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Detect lineup changes between sessions.

        Args:
            session_date: Current session date
            previous_session_date: Previous session to compare (if None, find most recent)

        Returns:
            {
                'current': { team rosters },
                'previous': { team rosters },
                'changes': {
                    'Team A': {
                        'added': ['player1', ...],
                        'removed': ['player2', ...],
                        'unchanged': ['player3', ...]
                    },
                    'Team B': { ... }
                },
                'summary': "2 players changed on Team A, 1 on Team B"
            }
        """
        current_teams = await self.get_session_teams(session_date)

        if not previous_session_date:
            # Find most recent session before this one
            row = await self.db.fetch_one(
                """
                SELECT DISTINCT SUBSTR(round_date, 1, 10) as date
                FROM rounds
                WHERE SUBSTR(round_date, 1, 10) < $1
                ORDER BY date DESC
                LIMIT 1
                """,
                (session_date,)
            )
            if not row:
                return {
                    'current': current_teams,
                    'previous': {},
                    'changes': {},
                    'summary': "No previous session found"
                }
            previous_session_date = row[0]

        previous_teams = await self.get_session_teams(previous_session_date, auto_detect=False)
        
        if not previous_teams:
            return {
                'current': current_teams,
                'previous': {},
                'changes': {},
                'summary': f"No team data for previous session {previous_session_date}"
            }
        
        # Calculate changes
        changes = {}
        total_added = 0
        total_removed = 0
        
        for team_name in current_teams:
            current_guids = set(current_teams[team_name]['guids'])
            previous_guids = set(previous_teams.get(team_name, {}).get('guids', []))
            
            added_guids = current_guids - previous_guids
            removed_guids = previous_guids - current_guids
            unchanged_guids = current_guids & previous_guids
            
            # Get names for readability
            guid_to_name = {
                g: n for g, n in zip(
                    current_teams[team_name]['guids'],
                    current_teams[team_name]['names']
                )
            }
            prev_guid_to_name = {
                g: n for g, n in zip(
                    previous_teams.get(team_name, {}).get('guids', []),
                    previous_teams.get(team_name, {}).get('names', [])
                )
            }
            
            changes[team_name] = {
                'added': [guid_to_name.get(g, g) for g in added_guids],
                'removed': [prev_guid_to_name.get(g, g) for g in removed_guids],
                'unchanged': [guid_to_name.get(g, g) for g in unchanged_guids]
            }
            
            total_added += len(added_guids)
            total_removed += len(removed_guids)
        
        summary_parts = []
        if total_added > 0:
            summary_parts.append(f"{total_added} player(s) added")
        if total_removed > 0:
            summary_parts.append(f"{total_removed} player(s) removed")
        if not summary_parts:
            summary_parts.append("No changes")
        
        return {
            'current': current_teams,
            'previous': previous_teams,
            'changes': changes,
            'summary': ", ".join(summary_parts),
            'previous_date': previous_session_date
        }
    
    async def set_custom_team_names(
        self,
        session_date: str,
        team_a_name: str,
        team_b_name: str
    ) -> bool:
        """
        Set custom names for teams (e.g., "Lakers" vs "Mavericks").

        Args:
            session_date: Session date
            team_a_name: Custom name for Team A
            team_b_name: Custom name for Team B

        Returns:
            True if successful
        """
        # Update Team A
        await self.db.execute(
            """
            UPDATE session_teams
            SET team_name = $1
            WHERE session_start_date LIKE $2 AND map_name = 'ALL' AND team_name = 'Team A'
            """,
            (team_a_name, f"{session_date}%")
        )

        # Update Team B
        await self.db.execute(
            """
            UPDATE session_teams
            SET team_name = $1
            WHERE session_start_date LIKE $2 AND map_name = 'ALL' AND team_name = 'Team B'
            """,
            (team_b_name, f"{session_date}%")
        )

        logger.info(f"✅ Set custom team names for {session_date}: "
                   f"{team_a_name} vs {team_b_name}")
        return True
    
    async def get_map_performance(
        self,
        session_date: str
    ) -> Dict[str, Dict]:
        """
        Get team performance per map for a session.

        Returns:
            {
                'supply': {
                    'Team A': {'rounds_won': 1, 'rounds_lost': 1, 'points': 1},
                    'Team B': {'rounds_won': 1, 'rounds_lost': 1, 'points': 1}
                },
                'etl_adlernest': { ... },
                ...
            }
        """
        if not getattr(self, "enable_map_performance", False):
            # Feature flag: disabled by default
            logger.info("Map performance disabled (enable_map_performance=False)")
            return {}

        try:
            from bot.services.stopwatch_scoring_service import StopwatchScoringService

            # Get round IDs for this session date
            rows = await self.db.fetch_all(
                """
                SELECT id
                FROM rounds
                WHERE SUBSTRING(round_date, 1, 10) = $1
                  AND round_number IN (1, 2)
                  AND (round_status IN ('completed', 'cancelled', 'substitution') OR round_status IS NULL)
                ORDER BY round_date, CAST(REPLACE(round_time, ':', '') AS INTEGER)
                """,
                (session_date,),
            )

            session_ids = [row[0] for row in rows]
            if not session_ids:
                return {}

            # Load hardcoded teams for this session
            team_rows = await self.db.fetch_all(
                """
                SELECT team_name, player_guids
                FROM session_teams
                WHERE SUBSTRING(session_start_date, 1, 10) = $1
                  AND map_name = 'ALL'
                ORDER BY team_name
                """,
                (session_date,),
            )

            if not team_rows or len(team_rows) < 2:
                return {}

            team_rosters = {}
            for team_name, guids_json in team_rows:
                team_rosters[team_name] = json.loads(guids_json) if guids_json else []

            scoring_service = StopwatchScoringService(self.db)
            scoring_result = await scoring_service.calculate_session_scores_with_teams(
                session_date, session_ids, team_rosters
            )

            if not scoring_result or 'maps' not in scoring_result:
                return {}

            team_a_name = scoring_result.get('team_a_name', 'Team A')
            team_b_name = scoring_result.get('team_b_name', 'Team B')

            map_perf: Dict[str, Dict] = {}
            for map_result in scoring_result['maps']:
                map_name = map_result.get('map', 'Unknown')
                if map_name not in map_perf:
                    map_perf[map_name] = {
                        team_a_name: {'points': 0},
                        team_b_name: {'points': 0}
                    }
                map_perf[map_name][team_a_name]['points'] += map_result.get('team_a_points', 0)
                map_perf[map_name][team_b_name]['points'] += map_result.get('team_b_points', 0)

            return map_perf

        except Exception as e:
            logger.warning(f"Map performance calculation failed: {e}")
            return {}

    # =========================================================================
    # TEAM POOL & RANDOM ASSIGNMENT
    # =========================================================================

    async def get_team_pool(self, active_only: bool = True) -> List[Dict]:
        """
        Get available team names from the pool.

        Args:
            active_only: If True, only return active teams

        Returns:
            List of team dicts: [{'name': 'sWat', 'display_name': 'sWat', 'color': 3447003}, ...]
        """
        if active_only:
            query = "SELECT name, display_name, color FROM team_pool WHERE active = TRUE ORDER BY name"
            rows = await self.db.fetch_all(query, ())
        else:
            query = "SELECT name, display_name, color FROM team_pool ORDER BY name"
            rows = await self.db.fetch_all(query, ())

        return [
            {'name': name, 'display_name': display_name or name, 'color': color}
            for name, display_name, color in rows
        ]

    async def get_team_color(self, team_name: str) -> Optional[int]:
        """
        Get Discord embed color for a team name.

        Args:
            team_name: Team name (e.g., 'sWat')

        Returns:
            Integer color value or None if not found
        """
        row = await self.db.fetch_one(
            "SELECT color FROM team_pool WHERE name = $1",
            (team_name,)
        )
        return row[0] if row else None

    async def assign_random_team_names(
        self,
        session_date: str,
        force: bool = False
    ) -> Tuple[str, str]:
        """
        Randomly assign team names from the pool to a session.

        This picks 2 random team names and stores them in session_teams.
        If teams are already named (not 'Team A'/'Team B'), returns existing names
        unless force=True.

        Args:
            session_date: Session date (YYYY-MM-DD)
            force: If True, override existing custom names

        Returns:
            (team_a_name, team_b_name)
        """
        import random
        await self._ensure_session_teams_table()
        columns = await self._get_session_teams_columns()

        # Check if session already has custom team names
        if not force:
            existing = await self.get_session_teams(session_date, auto_detect=False)
            if existing:
                team_names = list(existing.keys())
                # If already has custom names (not 'Team A'/'Team B'), return them
                if team_names and team_names[0] not in ('Team A', 'Team B'):
                    logger.info(f"Session {session_date} already has team names: {team_names}")
                    return (team_names[0], team_names[1] if len(team_names) > 1 else 'Team B')

        # Get available teams from pool
        pool = await self.get_team_pool(active_only=True)

        if len(pool) < 2:
            logger.warning("Not enough teams in pool, using defaults")
            return ("Team A", "Team B")

        # Pick 2 random teams
        chosen = random.sample(pool, 2)
        team_a_name = chosen[0]['name']
        team_b_name = chosen[1]['name']
        team_a_color = chosen[0]['color']
        team_b_color = chosen[1]['color']

        logger.info(f"Randomly assigned teams for {session_date}: {team_a_name} vs {team_b_name}")

        # Ensure teams exist in session_teams table first
        teams = await self.get_session_teams(session_date, auto_detect=True)
        if not teams:
            logger.warning(f"Could not detect teams for {session_date}")
            return (team_a_name, team_b_name)

        # Update the team names and colors
        set_fields_a = ["team_name = ?"]
        params_a = [team_a_name]
        if "color" in columns:
            set_fields_a.append("color = ?")
            params_a.append(team_a_color)
        params_a.append(f"{session_date}%")

        await self.db.execute(
            f"""
            UPDATE session_teams
            SET {", ".join(set_fields_a)}
            WHERE session_start_date LIKE ? AND map_name = 'ALL' AND team_name = 'Team A'
            """,
            tuple(params_a)
        )

        set_fields_b = ["team_name = ?"]
        params_b = [team_b_name]
        if "color" in columns:
            set_fields_b.append("color = ?")
            params_b.append(team_b_color)
        params_b.append(f"{session_date}%")

        await self.db.execute(
            f"""
            UPDATE session_teams
            SET {", ".join(set_fields_b)}
            WHERE session_start_date LIKE ? AND map_name = 'ALL' AND team_name = 'Team B'
            """,
            tuple(params_b)
        )

        logger.info(f"✅ Assigned random teams: {team_a_name} vs {team_b_name}")
        return (team_a_name, team_b_name)

    async def add_team_to_pool(
        self,
        name: str,
        display_name: Optional[str] = None,
        color: Optional[int] = None
    ) -> bool:
        """
        Add a new team to the pool.

        Args:
            name: Team name (must be unique)
            display_name: Optional display name
            color: Optional Discord embed color (int)

        Returns:
            True if added successfully
        """
        try:
            await self.db.execute(
                """
                INSERT INTO team_pool (name, display_name, color)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO UPDATE SET
                    display_name = COALESCE(EXCLUDED.display_name, team_pool.display_name),
                    color = COALESCE(EXCLUDED.color, team_pool.color)
                """,
                (name, display_name, color)
            )
            logger.info(f"✅ Added team to pool: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add team {name}: {e}")
            return False

    # =========================================================================
    # TEAM RECORDS & HISTORY (REQUIRES session_results TABLE)
    # =========================================================================

    async def get_team_record(
        self,
        team_name: str,
        days_back: int = 90
    ) -> Dict:
        """
        Get win/loss record for a team by name.

        Args:
            team_name: Team name from pool (e.g., 'sWat')
            days_back: How far back to look (default 90 days)

        Returns:
            {
                'team_name': 'sWat',
                'wins': 5,
                'losses': 3,
                'ties': 1,
                'total': 9,
                'win_rate': 0.556,
                'recent_matches': [...]
            }
        """
        try:
            query = """
                SELECT
                    session_date,
                    team_1_name,
                    team_2_name,
                    team_1_score,
                    team_2_score,
                    winning_team
                FROM session_results
                WHERE (team_1_name = $1 OR team_2_name = $1)
                  AND session_date >= (CURRENT_DATE - $2 * INTERVAL '1 day')::text
                ORDER BY session_date DESC
            """

            rows = await self.db.fetch_all(query, (team_name, days_back))

            wins = 0
            losses = 0
            ties = 0
            matches = []

            for row in rows:
                date, t1_name, t2_name, t1_score, t2_score, winner = row

                # Determine if this team was team 1 or team 2
                is_team_1 = (t1_name == team_name)
                our_score = t1_score if is_team_1 else t2_score
                their_score = t2_score if is_team_1 else t1_score
                opponent = t2_name if is_team_1 else t1_name
                expected_winner = 1 if is_team_1 else 2

                if winner == 0:
                    ties += 1
                    result = 'T'
                elif winner == expected_winner:
                    wins += 1
                    result = 'W'
                else:
                    losses += 1
                    result = 'L'

                matches.append({
                    'date': date,
                    'opponent': opponent,
                    'our_score': our_score,
                    'their_score': their_score,
                    'result': result
                })

            total = wins + losses + ties
            win_rate = wins / total if total > 0 else 0.0

            return {
                'team_name': team_name,
                'wins': wins,
                'losses': losses,
                'ties': ties,
                'total': total,
                'win_rate': win_rate,
                'recent_matches': matches[:10]  # Last 10
            }

        except Exception as e:
            logger.error(f"Error getting team record for {team_name}: {e}", exc_info=True)
            return {
                'team_name': team_name,
                'wins': 0,
                'losses': 0,
                'ties': 0,
                'total': 0,
                'win_rate': 0.0,
                'recent_matches': []
            }

    async def get_head_to_head(
        self,
        team_a: str,
        team_b: str,
        days_back: int = 365
    ) -> Dict:
        """
        Get head-to-head record between two teams.

        Args:
            team_a: First team name
            team_b: Second team name
            days_back: How far back to look (default 1 year)

        Returns:
            {
                'team_a': 'sWat',
                'team_b': 'madDogz',
                'team_a_wins': 5,
                'team_b_wins': 3,
                'ties': 1,
                'total_matches': 9,
                'team_a_maps_won': 15,
                'team_b_maps_won': 12,
                'recent_matches': [...]
            }
        """
        try:
            query = """
                SELECT
                    session_date,
                    team_1_name,
                    team_2_name,
                    team_1_score,
                    team_2_score,
                    winning_team
                FROM session_results
                WHERE ((team_1_name = $1 AND team_2_name = $2)
                    OR (team_1_name = $2 AND team_2_name = $1))
                  AND session_date >= (CURRENT_DATE - $3 * INTERVAL '1 day')::text
                ORDER BY session_date DESC
            """

            rows = await self.db.fetch_all(query, (team_a, team_b, days_back))

            team_a_wins = 0
            team_b_wins = 0
            ties = 0
            team_a_maps = 0
            team_b_maps = 0
            matches = []

            for row in rows:
                date, t1_name, t2_name, t1_score, t2_score, winner = row

                # Normalize: team_a is always "our" perspective
                if t1_name == team_a:
                    a_score, b_score = t1_score, t2_score
                    a_expected_winner = 1
                else:
                    a_score, b_score = t2_score, t1_score
                    a_expected_winner = 2

                team_a_maps += a_score
                team_b_maps += b_score

                if winner == 0:
                    ties += 1
                    result = 'TIE'
                elif winner == a_expected_winner:
                    team_a_wins += 1
                    result = f'{team_a} WIN'
                else:
                    team_b_wins += 1
                    result = f'{team_b} WIN'

                matches.append({
                    'date': date,
                    f'{team_a}_score': a_score,
                    f'{team_b}_score': b_score,
                    'result': result
                })

            return {
                'team_a': team_a,
                'team_b': team_b,
                'team_a_wins': team_a_wins,
                'team_b_wins': team_b_wins,
                'ties': ties,
                'total_matches': team_a_wins + team_b_wins + ties,
                'team_a_maps_won': team_a_maps,
                'team_b_maps_won': team_b_maps,
                'recent_matches': matches[:10]
            }

        except Exception as e:
            logger.error(f"Error getting head-to-head {team_a} vs {team_b}: {e}", exc_info=True)
            return {
                'team_a': team_a,
                'team_b': team_b,
                'team_a_wins': 0,
                'team_b_wins': 0,
                'ties': 0,
                'total_matches': 0,
                'team_a_maps_won': 0,
                'team_b_maps_won': 0,
                'recent_matches': []
            }
