"""
Populate session_teams table with October 2nd data.

Reads Round 1 files from each map to determine team rosters,
then inserts into session_teams table.
"""

import sqlite3
import os
import json
import re
from collections import defaultdict


def strip_color_codes(text):
    """Remove ET color codes from text."""
    return re.sub(r'\^\w', '', text)


def parse_round1_file(filepath):
    """Parse a Round 1 stats file to extract team rosters."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    # Parse header
    header = lines[0].strip()
    parts = header.split('\\')
    
    map_name = parts[1] if len(parts) > 1 else "unknown"
    round_num = int(parts[3]) if len(parts) > 3 else 0
    
    # Only process Round 1 files
    if round_num != 1:
        return None
    
    # Extract timestamp from filename
    # Format: 2025-10-02-211808-etl_adlernest-round-1.txt
    filename = os.path.basename(filepath)
    timestamp_part = filename.split('-')[:4]  # ['2025', '10', '02', '211808']
    session_date = f"{timestamp_part[0]}-{timestamp_part[1]}-{timestamp_part[2]} {timestamp_part[3][:2]}:{timestamp_part[3][2:4]}:{timestamp_part[3][4:6]}"
    
    # Parse players
    team_a = []  # Allies (team "1")
    team_b = []  # Axis (team "2")
    
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
        
        if team == '1':  # Allies
            team_a.append({'guid': guid, 'name': name_clean})
        elif team == '2':  # Axis
            team_b.append({'guid': guid, 'name': name_clean})
    
    return {
        'session_date': session_date,
        'map_name': map_name,
        'team_a': team_a,
        'team_b': team_b
    }


def populate_session_teams():
    """Populate session_teams table with October 2nd data."""
    
    stats_dir = "local_stats"
    db_path = "etlegacy_production.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return False
    
    # Get all October 2nd Round 1 files
    oct2_round1_files = []
    for filename in os.listdir(stats_dir):
        if filename.startswith("2025-10-02") and "round-1" in filename and filename.endswith(".txt"):
            oct2_round1_files.append(filename)
    
    oct2_round1_files.sort()
    
    print(f"📁 Found {len(oct2_round1_files)} Round 1 files for October 2nd\n")
    
    if not oct2_round1_files:
        print("❌ No October 2nd Round 1 files found!")
        return False
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Parse each Round 1 file
    maps_processed = 0
    teams_inserted = 0
    
    for filename in oct2_round1_files:
        filepath = os.path.join(stats_dir, filename)
        
        print(f"📄 Processing: {filename}")
        
        data = parse_round1_file(filepath)
        if not data:
            print(f"  ⚠️  Skipped (not Round 1)")
            continue
        
        session_date = data['session_date']
        map_name = data['map_name']
        team_a = data['team_a']
        team_b = data['team_b']
        
        print(f"  📅 Session: {session_date}")
        print(f"  🗺️  Map: {map_name}")
        print(f"  👥 Team A (Allies): {len(team_a)} players")
        if team_a:
            team_a_names = ', '.join([p['name'] for p in team_a])
            print(f"     {team_a_names}")
        print(f"  👥 Team B (Axis): {len(team_b)} players")
        if team_b:
            team_b_names = ', '.join([p['name'] for p in team_b])
            print(f"     {team_b_names}")
        
        # Insert Team A
        if team_a:
            team_a_guids = json.dumps([p['guid'] for p in team_a])
            team_a_names_json = json.dumps([p['name'] for p in team_a])
            
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO session_teams 
                    (session_start_date, map_name, team_name, player_guids, player_names)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_date, map_name, 'Team A', team_a_guids, team_a_names_json))
                teams_inserted += 1
                print(f"  ✅ Team A inserted")
            except Exception as e:
                print(f"  ❌ Error inserting Team A: {e}")
        
        # Insert Team B
        if team_b:
            team_b_guids = json.dumps([p['guid'] for p in team_b])
            team_b_names_json = json.dumps([p['name'] for p in team_b])
            
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO session_teams 
                    (session_start_date, map_name, team_name, player_guids, player_names)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_date, map_name, 'Team B', team_b_guids, team_b_names_json))
                teams_inserted += 1
                print(f"  ✅ Team B inserted")
            except Exception as e:
                print(f"  ❌ Error inserting Team B: {e}")
        
        maps_processed += 1
        print()
    
    # Commit changes
    conn.commit()
    
    # Verify inserts
    print("="*80)
    print("📊 VERIFICATION")
    print("="*80)
    
    cursor.execute("SELECT COUNT(*) FROM session_teams")
    total_records = cursor.fetchone()[0]
    print(f"✅ Total records in session_teams: {total_records}")
    
    cursor.execute('''
        SELECT session_start_date, map_name, team_name, player_names
        FROM session_teams
        ORDER BY session_start_date, map_name, team_name
    ''')
    
    print(f"\n📋 Inserted Teams:")
    for row in cursor.fetchall():
        session_date, map_name, team_name, player_names_json = row
        player_names = json.loads(player_names_json)
        players_str = ', '.join(player_names)
        print(f"  {session_date} | {map_name:20} | {team_name:7} | {players_str}")
    
    conn.close()
    
    print(f"\n🎉 SUCCESS!")
    print(f"  Maps processed: {maps_processed}")
    print(f"  Teams inserted: {teams_inserted}")
    
    return True


if __name__ == "__main__":
    print("=" * 80)
    print("🎮 ET:Legacy - Populate session_teams Table")
    print("=" * 80)
    print()
    
    success = populate_session_teams()
    
    if success:
        print("\n✅ October 2nd team data populated successfully!")
        print("Next step: Validate the data with a query script")
    else:
        print("\n❌ Failed to populate data")
