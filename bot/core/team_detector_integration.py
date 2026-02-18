"""
Team Detector Integration Layer

Provides a unified interface for team detection that:
1. Uses the advanced detector by default
2. Falls back to simple detection if needed
3. Provides validation and confidence reporting
4. Handles edge cases gracefully
"""

import json
import logging
import sqlite3
from typing import Dict, Tuple

from bot.core.advanced_team_detector import AdvancedTeamDetector

logger = logging.getLogger(__name__)


class TeamDetectorIntegration:
    """
    Unified team detection interface with automatic fallback
    """
    
    def __init__(self, db_path: str = "bot/etlegacy_production.db"):
        self.db_path = db_path
        self.advanced_detector = AdvancedTeamDetector(db_path)
        
    def detect_and_validate(
        self,
        db: sqlite3.Connection,
        session_date: str,
        require_high_confidence: bool = False
    ) -> Tuple[Dict, bool]:
        """
        Detect teams with automatic validation
        
        Args:
            db: Database connection
            session_date: Session date (YYYY-MM-DD)
            require_high_confidence: If True, reject low-confidence detections
            
        Returns:
            (teams_dict, is_reliable)
            
        The teams_dict format:
        {
            'Team A': {'guids': [...], 'names': [...], 'confidence': 0.85},
            'Team B': {'guids': [...], 'names': [...], 'confidence': 0.85},
            'metadata': {
                'strategy_used': 'multi-strategy',
                'avg_confidence': 0.85,
                'uncertain_players': [],
                'detection_quality': 'high'
            }
        }
        """
        try:
            # Try advanced detection
            result = self.advanced_detector.detect_session_teams(
                db, session_date, use_historical=True
            )
            
            if not result or 'Team A' not in result or 'Team B' not in result:
                logger.warning(f"Advanced detection failed for {session_date}")
                return {}, False
            
            metadata = result.get('metadata', {})
            quality = metadata.get('detection_quality', 'unknown')
            confidence = metadata.get('avg_confidence', 0.0)
            
            # Validate results
            team_a_size = len(result['Team A']['guids'])
            team_b_size = len(result['Team B']['guids'])
            
            # Check for reasonable team sizes
            if team_a_size == 0 or team_b_size == 0:
                logger.error("One team has no players!")
                return {}, False
            
            # Warn about imbalanced teams
            size_ratio = max(team_a_size, team_b_size) / min(team_a_size, team_b_size)
            if size_ratio > 2.0:
                logger.warning(f"Teams are imbalanced: {team_a_size} vs {team_b_size}")
                metadata['warning'] = 'imbalanced_teams'
            
            # Check confidence requirements
            if require_high_confidence and quality != 'high':
                logger.warning(f"Detection quality '{quality}' below required threshold")
                return result, False
            
            # Log detection results
            logger.info("✅ Team detection successful:")
            logger.info(f"   Quality: {quality}, Confidence: {confidence:.1%}")
            logger.info(f"   Team A: {team_a_size} players")
            logger.info(f"   Team B: {team_b_size} players")
            
            if metadata.get('uncertain_players'):
                logger.info(f"   ⚠️  Uncertain: {metadata['uncertain_players']}")
            
            is_reliable = (quality in ['high', 'medium'] and confidence > 0.5)
            
            return result, is_reliable
            
        except Exception as e:
            logger.exception(f"Error in team detection: {e}")
            return {}, False
    
    def store_detected_teams(
        self,
        db: sqlite3.Connection,
        session_date: str,
        teams_result: Dict
    ) -> bool:
        """
        Store detected teams in session_teams table
        
        Args:
            db: Database connection
            session_date: Session date
            teams_result: Result from detect_and_validate()
            
        Returns:
            True if successful
        """
        if not teams_result or 'Team A' not in teams_result:
            return False
        
        cursor = db.cursor()
        
        try:
            # Delete existing entries
            cursor.execute(
                "DELETE FROM session_teams WHERE session_start_date LIKE ? AND map_name = 'ALL'",
                (f"{session_date}%",)
            )
            
            # Store Team A
            cursor.execute(
                """
                INSERT INTO session_teams 
                (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, 'ALL', 'Team A', ?, ?)
                """,
                (
                    session_date,
                    json.dumps(teams_result['Team A']['guids']),
                    json.dumps(teams_result['Team A']['names'])
                )
            )
            
            # Store Team B
            cursor.execute(
                """
                INSERT INTO session_teams 
                (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, 'ALL', 'Team B', ?, ?)
                """,
                (
                    session_date,
                    json.dumps(teams_result['Team B']['guids']),
                    json.dumps(teams_result['Team B']['names'])
                )
            )
            
            # Store metadata if needed (could add to separate table)
            metadata = teams_result.get('metadata', {})
            
            db.commit()
            
            logger.info(f"✅ Stored team data for {session_date}")
            logger.info(f"   Confidence: {metadata.get('avg_confidence', 0):.1%}")
            logger.info(f"   Quality: {metadata.get('detection_quality', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.exception(f"Error storing teams: {e}")
            db.rollback()
            return False
    
    def get_or_detect_teams(
        self,
        db: sqlite3.Connection,
        session_date: str,
        auto_detect: bool = True,
        force_redetect: bool = False
    ) -> Dict:
        """
        Get teams from DB or detect if not found
        
        Args:
            db: Database connection
            session_date: Session date
            auto_detect: Auto-detect if not found
            force_redetect: Force re-detection even if stored
            
        Returns:
            Teams dictionary
        """
        # Check if we should force redetection
        if not force_redetect:
            # Try to get from database
            cursor = db.cursor()
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
        if auto_detect or force_redetect:
            logger.info(f"{'Re-detecting' if force_redetect else 'Detecting'} teams for {session_date}...")
            result, is_reliable = self.detect_and_validate(db, session_date)
            
            if result and is_reliable:
                # Store the results
                self.store_detected_teams(db, session_date, result)
                
                # Return in expected format
                return {
                    'Team A': result['Team A'],
                    'Team B': result['Team B']
                }
        
        return {}
    
    def validate_stored_teams(
        self,
        db: sqlite3.Connection,
        session_date: str
    ) -> Tuple[bool, str]:
        """
        Validate that stored teams make sense
        
        Returns:
            (is_valid, reason)
        """
        cursor = db.cursor()
        
        cursor.execute(
            """
            SELECT team_name, player_guids
            FROM session_teams
            WHERE session_start_date LIKE ? AND map_name = 'ALL'
            """,
            (f"{session_date}%",)
        )
        
        rows = cursor.fetchall()
        
        if not rows:
            return False, "No teams stored"
        
        if len(rows) != 2:
            return False, f"Expected 2 teams, found {len(rows)}"
        
        # Check team sizes
        team_sizes = []
        for team_name, guids_json in rows:
            guids = json.loads(guids_json)
            team_sizes.append(len(guids))
        
        if min(team_sizes) == 0:
            return False, "One team has no players"
        
        size_ratio = max(team_sizes) / min(team_sizes)
        if size_ratio > 3.0:
            return False, f"Teams very imbalanced: {team_sizes[0]} vs {team_sizes[1]}"
        
        return True, "Valid"


# Convenience function for quick integration
# NOTE: SQLite-only — requires a local .db file path. Not used in PostgreSQL mode.
def detect_session_teams_smart(
    db_path: str,
    session_date: str,
    auto_store: bool = True
) -> Dict:
    """
    Quick function to detect teams using the advanced system.

    WARNING: SQLite-only convenience function. Will raise FileNotFoundError
    if the db_path does not exist (e.g. when running in PostgreSQL mode).
    For async/PostgreSQL usage, use TeamManager via the bot's database adapter.

    Args:
        db_path: Path to SQLite database file
        session_date: Session date (YYYY-MM-DD)
        auto_store: Automatically store results

    Returns:
        Teams dictionary
    """
    import os
    import sqlite3

    if not db_path or not os.path.exists(db_path):
        raise FileNotFoundError(
            f"SQLite DB not found at '{db_path}'. "
            "This function is SQLite-only; use TeamManager for PostgreSQL."
        )

    conn = sqlite3.connect(db_path)
    detector = TeamDetectorIntegration(db_path)

    result = detector.get_or_detect_teams(
        conn,
        session_date,
        auto_detect=True,
        force_redetect=False
    )

    conn.close()

    return result
