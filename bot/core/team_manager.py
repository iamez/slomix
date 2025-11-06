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

import sqlite3
import json
import logging
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class TeamManager:
    """Manages team detection, tracking, and statistics"""
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        
    def detect_session_teams(
        self, 
        db: sqlite3.Connection,
        session_date: str
    ) -> Dict[str, Dict]:
        """
        Automatically detect persistent teams for a session.
        
        Algorithm:
        1. Seed from Round 1 (or earliest available round)
        2. For late joiners, use co-membership voting (who they played with most)
        3. Return team rosters with GUIDs and names
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD format)
            
        Returns:
            {
                'Team A': {
                    'guids': ['guid1', 'guid2', ...],
                    'names': ['Player1', 'Player2', ...],
                    'count': 5
                },
                'Team B': { ... }
            }
        """
        cursor = db.cursor()
        
        # Get all players from session grouped by round and game-team
        query = """
            SELECT round_number, team, player_guid, player_name
            FROM player_comprehensive_stats
            WHERE round_date LIKE ?
            ORDER BY round_number, team
        """
        cursor.execute(query, (f"{session_date}%",))
        rows = cursor.fetchall()
        
        if not rows:
            logger.warning(f"No player data found for session {session_date}")
            return {}
        
        # Organize by round
        rounds = defaultdict(lambda: {'team1': set(), 'team2': set()})
        player_names = {}  # guid -> most recent name
        
        for round_num, game_team, guid, name in rows:
            player_names[guid] = name
            team_key = 'team1' if game_team == 1 else 'team2'
            rounds[round_num][team_key].add(guid)
        
        # Seed from earliest round (usually Round 1)
        earliest_round = min(rounds.keys())
        persistent_team1 = set(rounds[earliest_round]['team1'])
        persistent_team2 = set(rounds[earliest_round]['team2'])
        
        logger.info(f"Seeded teams from Round {earliest_round}: "
                   f"Team1={len(persistent_team1)}, Team2={len(persistent_team2)}")
        
        # Handle late joiners using co-membership voting
        all_players = set(player_names.keys())
        unassigned = all_players - persistent_team1 - persistent_team2
        
        if unassigned:
            logger.info(f"Assigning {len(unassigned)} late joiners...")
            for guid in unassigned:
                # Count which team they co-appeared with more often
                team1_votes = 0
                team2_votes = 0
                
                for round_num, teams in rounds.items():
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
        
        # Build result
        teams = {
            'Team A': {
                'guids': sorted(list(persistent_team1)),
                'names': sorted([player_names[g] for g in persistent_team1]),
                'count': len(persistent_team1)
            },
            'Team B': {
                'guids': sorted(list(persistent_team2)),
                'names': sorted([player_names[g] for g in persistent_team2]),
                'count': len(persistent_team2)
            }
        }
        
        logger.info(f"✅ Detected teams for {session_date}: "
                   f"Team A ({teams['Team A']['count']} players), "
                   f"Team B ({teams['Team B']['count']} players)")
        
        return teams
    
    def store_session_teams(
        self,
        db: sqlite3.Connection,
        session_date: str,
        teams: Dict[str, Dict]
    ) -> bool:
        """
        Store detected teams in the session_teams table.
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD)
            teams: Team data from detect_session_teams()
            
        Returns:
            True if successful
        """
        cursor = db.cursor()
        
        # Delete existing entries for this session
        cursor.execute(
            "DELETE FROM session_teams WHERE session_start_date LIKE ? AND map_name = 'ALL'",
            (f"{session_date}%",)
        )
        
        # Insert new team data
        for team_name, team_data in teams.items():
            cursor.execute(
                """
                INSERT INTO session_teams 
                (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, 'ALL', ?, ?, ?)
                """,
                (
                    session_date,
                    team_name,
                    json.dumps(team_data['guids']),
                    json.dumps(team_data['names'])
                )
            )
        
        db.commit()
        logger.info(f"✅ Stored teams for session {session_date}")
        return True
    
    def get_session_teams(
        self,
        db: sqlite3.Connection,
        session_date: str,
        auto_detect: bool = True
    ) -> Dict[str, Dict]:
        """
        Get teams for a session (from DB or auto-detect).
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD)
            auto_detect: If True, auto-detect and store if not found
            
        Returns:
            Team data dictionary
        """
        cursor = db.cursor()
        
        # Try to get from database
        cursor.execute(
            """
            SELECT team_name, player_guids, player_names
            FROM session_teams
            WHERE session_start_date LIKE ? AND map_name = 'ALL'
            ORDER BY team_name
            """,
            (f"{session_date}%",)
        )
        
        rows = cursor.fetchall()
        
        if rows:
            teams = {}
            for team_name, guids_json, names_json in rows:
                teams[team_name] = {
                    'guids': json.loads(guids_json),
                    'names': json.loads(names_json),
                    'count': len(json.loads(guids_json))
                }
            logger.info(f"✅ Found stored teams for {session_date}")
            return teams
        
        # Auto-detect if requested
        if auto_detect:
            logger.info(f"No stored teams found for {session_date}, auto-detecting...")
            teams = self.detect_session_teams(db, session_date)
            if teams:
                self.store_session_teams(db, session_date, teams)
            return teams
        
        return {}
    
    def detect_lineup_changes(
        self,
        db: sqlite3.Connection,
        session_date: str,
        previous_session_date: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Detect lineup changes between sessions.
        
        Args:
            db: Database connection
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
        current_teams = self.get_session_teams(db, session_date)
        
        if not previous_session_date:
            # Find most recent session before this one
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT DISTINCT SUBSTR(round_date, 1, 10) as date
                FROM rounds
                WHERE SUBSTR(round_date, 1, 10) < ?
                ORDER BY date DESC
                LIMIT 1
                """,
                (session_date,)
            )
            row = cursor.fetchone()
            if not row:
                return {
                    'current': current_teams,
                    'previous': {},
                    'changes': {},
                    'summary': "No previous session found"
                }
            previous_session_date = row[0]
        
        previous_teams = self.get_session_teams(db, previous_session_date, auto_detect=False)
        
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
    
    def get_team_record(
        self,
        db: sqlite3.Connection,
        team_roster_guids: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Get win/loss record for a specific team lineup.
        
        Args:
            db: Database connection
            team_roster_guids: List of player GUIDs in the lineup
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            {
                'sessions_played': 5,
                'wins': 3,
                'losses': 2,
                'ties': 0,
                'win_rate': 0.60,
                'maps_won': 12,
                'maps_lost': 8,
                'sessions': [
                    {'date': '2025-10-28', 'result': 'WIN', 'score': '10-8'},
                    ...
                ]
            }
        """
        # TODO: Implement once we have session results stored
        # This will query the stopwatch scores and match them to team rosters
        pass
    
    def set_custom_team_names(
        self,
        db: sqlite3.Connection,
        session_date: str,
        team_a_name: str,
        team_b_name: str
    ) -> bool:
        """
        Set custom names for teams (e.g., "Lakers" vs "Mavericks").
        
        Args:
            db: Database connection
            session_date: Session date
            team_a_name: Custom name for Team A
            team_b_name: Custom name for Team B
            
        Returns:
            True if successful
        """
        cursor = db.cursor()
        
        # Update Team A
        cursor.execute(
            """
            UPDATE session_teams
            SET team_name = ?
            WHERE session_start_date LIKE ? AND map_name = 'ALL' AND team_name = 'Team A'
            """,
            (team_a_name, f"{session_date}%")
        )
        
        # Update Team B
        cursor.execute(
            """
            UPDATE session_teams
            SET team_name = ?
            WHERE session_start_date LIKE ? AND map_name = 'ALL' AND team_name = 'Team B'
            """,
            (team_b_name, f"{session_date}%")
        )
        
        db.commit()
        logger.info(f"✅ Set custom team names for {session_date}: "
                   f"{team_a_name} vs {team_b_name}")
        return True
    
    def get_map_performance(
        self,
        db: sqlite3.Connection,
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
        # This will integrate with StopwatchScoring
        # TODO: Implement
        pass
