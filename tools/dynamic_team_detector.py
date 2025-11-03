"""
Dynamic Team Detection System
Automatically detects and assigns team names based on Round 1 player compositions.

NO hardcoded player rosters - team assignment is dynamic per session!
"""

import sqlite3
import os
import json
import re
import random
from datetime import datetime
from collections import defaultdict


# Team name pool - randomly assigned to detected teams
TEAM_NAMES = ['sWat', 'slo', 'slomix', 'madDogs', 'puran', 'insAne', 'SF']


def strip_color_codes(text):
    """Remove ET color codes from text."""
    return re.sub(r'\^\w', '', text)


def parse_round1_file(filepath):
    """
    Parse a Round 1 stats file to detect team compositions.
    
    Returns:
        dict with session_date, map_name, team_axis (list of player dicts), 
        team_allies (list of player dicts)
    """
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    if not lines:
        return None
    
    # Parse header: mapname\round\totalrounds\gamemode etc.
    header = lines[0].strip()
    parts = header.split('\\')
    
    if len(parts) < 4:
        return None
    
    map_name = parts[1] if len(parts) > 1 else "unknown"
    round_num = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
    
    # Only process Round 1 files
    if round_num != 1:
        return None
    
    # Extract timestamp from filename
    # Format: YYYY-MM-DD-HHMMSS-mapname-round-1.txt
    filename = os.path.basename(filepath)
    timestamp_part = filename.split('-')[:4]
    
    if len(timestamp_part) < 4:
        return None
    
    try:
        session_date = (
            f"{timestamp_part[0]}-{timestamp_part[1]}-{timestamp_part[2]} "
            f"{timestamp_part[3][:2]}:{timestamp_part[3][2:4]}:{timestamp_part[3][4:6]}"
        )
    except:
        return None
    
    # Parse players
    team_axis = []  # Team "2"
    team_allies = []  # Team "1"
    
    for line in lines[1:]:
        if not line.strip():
            continue
        
        parts = line.split('\\')
        if len(parts) < 4:
            continue
        
        guid = parts[0]
        name_raw = parts[1]
        name_clean = strip_color_codes(name_raw)
        team = parts[3]  # "1" = Allies, "2" = Axis
        
        player = {'guid': guid, 'name': name_clean}
        
        if team == '1':  # Allies
            team_allies.append(player)
        elif team == '2':  # Axis
            team_axis.append(player)
    
    # Only return if we have players on both teams
    if not team_axis or not team_allies:
        return None
    
    return {
        'session_date': session_date,
        'map_name': map_name,
        'team_axis': team_axis,
        'team_allies': team_allies
    }


def assign_team_names(used_names=None):
    """
    Randomly assign two team names from the pool.
    
    Args:
        used_names: Set of already used names (to avoid duplicates in same session)
    
    Returns:
        tuple: (team_name_1, team_name_2)
    """
    available = list(TEAM_NAMES)
    
    if used_names:
        available = [name for name in TEAM_NAMES if name not in used_names]
    
    if len(available) < 2:
        # If we've used all names, reset and allow reuse
        available = list(TEAM_NAMES)
    
    # Randomly pick two different names
    team_names = random.sample(available, 2)
    
    return tuple(team_names)


def detect_session_teams(stats_dir, session_date_prefix):
    """
    Detect teams for a session by analyzing Round 1 files.
    
    Args:
        stats_dir: Directory containing stats files
        session_date_prefix: Date prefix to filter files (e.g., "2025-10-02")
    
    Returns:
        dict: Session team information or None if no Round 1 files found
    """
    # Find all Round 1 files for this session date
    round1_files = []
    
    for filename in os.listdir(stats_dir):
        if filename.startswith(session_date_prefix) and 'round-1' in filename:
            round1_files.append(filename)
    
    if not round1_files:
        print(f"⚠️  No Round 1 files found for {session_date_prefix}")
        return None
    
    # Parse the first Round 1 file to detect teams
    first_round1 = sorted(round1_files)[0]
    filepath = os.path.join(stats_dir, first_round1)
    
    data = parse_round1_file(filepath)
    
    if not data:
        print(f"⚠️  Could not parse {first_round1}")
        return None
    
    # Assign random team names
    team_name_1, team_name_2 = assign_team_names()
    
    # Randomly decide which detected team gets which name
    if random.random() < 0.5:
        team_assignments = {
            team_name_1: data['team_axis'],
            team_name_2: data['team_allies']
        }
    else:
        team_assignments = {
            team_name_1: data['team_allies'],
            team_name_2: data['team_axis']
        }
    
    return {
        'session_date': data['session_date'],
        'teams': team_assignments
    }


def populate_session_teams_dynamic(db_path, stats_dir, session_date_prefix):
    """
    Dynamically populate session_teams table for a session.
    
    Args:
        db_path: Path to database
        stats_dir: Directory containing stats files
        session_date_prefix: Date prefix (e.g., "2025-10-02")
    
    Returns:
        bool: Success status
    """
    print("=" * 80)
    print("🎮 Dynamic Team Detection")
    print("=" * 80)
    print(f"Session Date: {session_date_prefix}")
    print(f"Stats Directory: {stats_dir}")
    print()
    
    # Detect teams from Round 1
    session_info = detect_session_teams(stats_dir, session_date_prefix)
    
    if not session_info:
        print("❌ Could not detect teams for this session")
        return False
    
    session_date = session_info['session_date']
    teams = session_info['teams']
    
    print(f"✅ Detected {len(teams)} teams:")
    for team_name, players in teams.items():
        player_names = [p['name'] for p in players]
        print(f"   {team_name}: {', '.join(player_names)} ({len(players)} players)")
    print()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if session_teams table exists
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='session_teams'
    """)
    
    if not cursor.fetchone():
        print("⚠️  session_teams table doesn't exist. Creating it...")
        cursor.execute("""
            CREATE TABLE session_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_start_date TEXT NOT NULL,
                map_name TEXT NOT NULL,
                team_name TEXT NOT NULL,
                player_guids TEXT NOT NULL,
                player_names TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_start_date, map_name, team_name)
            )
        """)
        cursor.execute("""
            CREATE INDEX idx_session_teams_date 
            ON session_teams(session_start_date)
        """)
        cursor.execute("""
            CREATE INDEX idx_session_teams_map 
            ON session_teams(session_start_date, map_name)
        """)
        print("✅ Table created")
        print()
    
    # Get all maps for this session
    all_files = [f for f in os.listdir(stats_dir) if f.startswith(session_date_prefix)]
    
    # Extract unique map names
    maps = set()
    for filename in all_files:
        parts = filename.split('-')
        if len(parts) >= 7:
            # Extract map name (between timestamp and "round")
            map_part_start = 4
            map_part_end = filename.index('-round-')
            map_name = '-'.join(filename.split('-')[map_part_start:]).split('-round-')[0]
            maps.add(map_name)
    
    print(f"📋 Found {len(maps)} maps in session:")
    for map_name in sorted(maps):
        print(f"   • {map_name}")
    print()
    
    # Delete existing records for this session
    cursor.execute("""
        DELETE FROM session_teams 
        WHERE session_start_date LIKE ?
    """, (f"{session_date_prefix}%",))
    
    if cursor.rowcount > 0:
        print(f"🗑️  Deleted {cursor.rowcount} old records")
        print()
    
    # Insert team records for each map
    inserts = 0
    for map_name in sorted(maps):
        for team_name, players in teams.items():
            guids = [p['guid'] for p in players]
            names = [p['name'] for p in players]
            
            cursor.execute("""
                INSERT INTO session_teams 
                (session_start_date, map_name, team_name, player_guids, player_names)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_date,
                map_name,
                team_name,
                json.dumps(guids),
                json.dumps(names)
            ))
            inserts += 1
    
    conn.commit()
    
    print(f"✅ Inserted {inserts} team records")
    print()
    
    # Verification
    print("=" * 80)
    print("📊 VERIFICATION")
    print("=" * 80)
    
    cursor.execute("""
        SELECT DISTINCT team_name, player_names
        FROM session_teams
        WHERE session_start_date LIKE ?
        ORDER BY team_name
    """, (f"{session_date_prefix}%",))
    
    for team_name, names_json in cursor.fetchall():
        names = json.loads(names_json)
        print(f"{team_name}: {', '.join(names)}")
    
    print()
    
    cursor.execute("""
        SELECT COUNT(*) FROM session_teams
        WHERE session_start_date LIKE ?
    """, (f"{session_date_prefix}%",))
    
    total = cursor.fetchone()[0]
    print(f"Total records: {total}")
    
    conn.close()
    
    return True


def main():
    """Main function for command-line usage."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python dynamic_team_detector.py <session_date>")
        print("Example: python dynamic_team_detector.py 2025-10-02")
        return
    
    session_date = sys.argv[1]
    db_path = "bot/etlegacy_production.db"
    stats_dir = "local_stats"
    
    success = populate_session_teams_dynamic(db_path, stats_dir, session_date)
    
    if success:
        print("\n✅ Dynamic team detection complete!")
        print("Teams have been assigned and tracked for the session.")
    else:
        print("\n❌ Failed to detect teams")


if __name__ == "__main__":
    main()
