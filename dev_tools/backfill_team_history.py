#!/usr/bin/env python3
"""
Backfill Team History Data

Populates team_lineups and session_results tables with data from existing sessions.

Process:
1. Find all sessions with team assignments in session_teams
2. For each session:
   - Calculate lineup hash for each team
   - Create/update team_lineups records
   - Calculate session score using StopwatchScoring
   - Create round_results record
   - Update lineup win/loss/tie stats
"""

import sqlite3
import json
import hashlib
from typing import Dict, Tuple, Optional
from datetime import datetime

# Add parent to path for imports
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from tools.stopwatch_scoring import StopwatchScoring

DB_PATH = "bot/etlegacy_production.db"


def calculate_lineup_hash(player_guids: list) -> str:
    """
    Calculate deterministic hash for a team lineup.
    
    Args:
        player_guids: List of player GUIDs
    
    Returns:
        SHA256 hash of sorted GUIDs
    """
    # Sort to ensure same roster always produces same hash
    sorted_guids = sorted(player_guids)
    guid_string = ",".join(sorted_guids)
    return hashlib.sha256(guid_string.encode()).hexdigest()[:16]


def get_or_create_lineup(
    cursor: sqlite3.Cursor, 
    player_guids: list, 
    round_date: str
) -> int:
    """
    Get existing lineup_id or create new lineup record.
    
    Returns:
        lineup_id
    """
    lineup_hash = calculate_lineup_hash(player_guids)
    player_count = len(player_guids)
    player_guids_json = json.dumps(sorted(player_guids))
    
    # Check if lineup exists
    cursor.execute(
        "SELECT id, first_seen, last_seen FROM team_lineups WHERE lineup_hash = ?",
        (lineup_hash,)
    )
    row = cursor.fetchone()
    
    if row:
        lineup_id, first_seen, last_seen = row
        
        # Update last_seen if this session is newer
        if round_date > last_seen:
            cursor.execute(
                """
                UPDATE team_lineups 
                SET last_seen = ?, 
                    total_rounds = total_rounds + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (round_date, lineup_id)
            )
        
        return lineup_id
    else:
        # Create new lineup
        cursor.execute(
            """
            INSERT INTO team_lineups 
            (lineup_hash, player_guids, player_count, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            """,
            (lineup_hash, player_guids_json, player_count, round_date, round_date)
        )
        return cursor.lastrowid


def update_lineup_stats(
    cursor: sqlite3.Cursor,
    lineup_id: int,
    result: str
):
    """
    Update win/loss/tie stats for a lineup.
    
    Args:
        lineup_id: ID of lineup to update
        result: 'win', 'loss', or 'tie'
    """
    if result == 'win':
        cursor.execute(
            "UPDATE team_lineups SET total_wins = total_wins + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lineup_id,)
        )
    elif result == 'loss':
        cursor.execute(
            "UPDATE team_lineups SET total_losses = total_losses + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lineup_id,)
        )
    elif result == 'tie':
        cursor.execute(
            "UPDATE team_lineups SET total_ties = total_ties + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (lineup_id,)
        )


def backfill_session(
    cursor: sqlite3.Cursor,
    round_date: str,
    team_data: Dict
) -> bool:
    """
    Process one session and create history records.
    
    Args:
        cursor: Database cursor
        round_date: Session date (YYYY-MM-DD)
        team_data: Dict with team names and GUIDs
    
    Returns:
        True if successful, False otherwise
    """
    # Get team data
    teams = list(team_data.items())
    if len(teams) != 2:
        print(f"  ⚠️  Skipping {round_date}: expected 2 teams, got {len(teams)}")
        return False
    
    team_1_name, team_1_data = teams[0]
    team_2_name, team_2_data = teams[1]
    
    team_1_guids = team_1_data['guids']
    team_2_guids = team_2_data['guids']
    
    # Create/get lineup IDs
    team_1_lineup_id = get_or_create_lineup(cursor, team_1_guids, round_date)
    team_2_lineup_id = get_or_create_lineup(cursor, team_2_guids, round_date)
    
    # Calculate scores
    scorer = StopwatchScoring(DB_PATH)
    scoring_result = scorer.calculate_session_scores(round_date)
    
    if not scoring_result:
        print(f"  ⚠️  No scoring data for {round_date}")
        return False
    
    team_1_score = scoring_result.get(team_1_name, 0)
    team_2_score = scoring_result.get(team_2_name, 0)
    total_maps = scoring_result.get('total_maps', 0)
    
    # Determine winner
    if team_1_score > team_2_score:
        winner = team_1_name
        team_1_result = 'win'
        team_2_result = 'loss'
    elif team_2_score > team_1_score:
        winner = team_2_name
        team_1_result = 'loss'
        team_2_result = 'win'
    else:
        winner = 'TIE'
        team_1_result = 'tie'
        team_2_result = 'tie'
    
    # Check if session_results already exists
    cursor.execute(
        "SELECT id FROM session_results WHERE round_date = ?",
        (round_date,)
    )
    if cursor.fetchone():
        print(f"  ⏭️  Skipping {round_date}: already exists")
        return False
    
    # Create round_results record
    cursor.execute(
        """
        INSERT INTO session_results 
        (round_date, team_1_lineup_id, team_2_lineup_id, 
         team_1_name, team_2_name, team_1_score, team_2_score, 
         winner, total_maps)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (round_date, team_1_lineup_id, team_2_lineup_id,
         team_1_name, team_2_name, team_1_score, team_2_score,
         winner, total_maps)
    )
    
    # Update lineup stats
    update_lineup_stats(cursor, team_1_lineup_id, team_1_result)
    update_lineup_stats(cursor, team_2_lineup_id, team_2_result)
    
    print(f"  ✅ {round_date}: {team_1_name} {team_1_score} - {team_2_score} {team_2_name} (Winner: {winner})")
    return True


def backfill_all_sessions():
    """Find and process all sessions with team data"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("🔄 Backfilling team history from existing sessions...\n")
    
    # Get all sessions with team assignments
    cursor.execute("""
        SELECT DISTINCT session_start_date 
        FROM session_teams 
        WHERE map_name = 'ALL'
        ORDER BY session_start_date ASC
    """)
    
    session_dates = [row[0] for row in cursor.fetchall()]
    
    print(f"📅 Found {len(session_dates)} sessions with team data\n")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for round_date in session_dates:
        try:
            # Get team data for this session
            cursor.execute(
                """
                SELECT team_name, player_guids, player_names
                FROM session_teams
                WHERE session_start_date = ? AND map_name = 'ALL'
                ORDER BY team_name
                """,
                (round_date,)
            )
            
            team_data = {}
            for team_name, guids_json, names_json in cursor.fetchall():
                team_data[team_name] = {
                    'guids': json.loads(guids_json),
                    'names': json.loads(names_json)
                }
            
            if backfill_session(cursor, round_date, team_data):
                success_count += 1
                conn.commit()
            else:
                skip_count += 1
                
        except Exception as e:
            print(f"  ❌ Error processing {round_date}: {e}")
            error_count += 1
            conn.rollback()
    
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ Backfill complete!")
    print(f"{'='*60}")
    print(f"  Processed: {success_count}")
    print(f"  Skipped:   {skip_count}")
    print(f"  Errors:    {error_count}")
    print(f"  Total:     {len(session_dates)}")
    
    # Show summary stats
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM team_lineups")
    lineup_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM session_results")
    result_count = cursor.fetchone()[0]
    
    print(f"\n📊 Database Stats:")
    print(f"  Unique lineups: {lineup_count}")
    print(f"  Session results: {result_count}")
    
    # Show top lineups by sessions played
    cursor.execute("""
        SELECT player_count, total_rounds, total_wins, total_losses, total_ties
        FROM team_lineups
        ORDER BY total_rounds DESC
        LIMIT 5
    """)
    
    print(f"\n🏆 Top Lineups by Sessions Played:")
    for i, (pc, sessions, wins, losses, ties) in enumerate(cursor.fetchall(), 1):
        wr = (wins / sessions * 100) if sessions > 0 else 0
        print(f"  {i}. {pc} players: {sessions} sessions ({wins}W-{losses}L-{ties}T, {wr:.1f}% WR)")
    
    conn.close()


if __name__ == "__main__":
    try:
        backfill_all_sessions()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
