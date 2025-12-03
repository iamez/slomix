#!/usr/bin/env python3
"""
Verify last session data by comparing raw stats files with database entries
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parser to path
sys.path.insert(0, str(Path(__file__).parent))
from community_stats_parser import C0RNP0RN3StatsParser

db_path = "bot/etlegacy_production.db"
stats_dir = Path("local_stats")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 100)
print("🔍 VERIFYING LAST SESSION - RAW FILES vs DATABASE")
print("=" * 100)

# Step 1: Get gaming session IDs
cursor.execute("""
    SELECT id, map_name, round_number, round_date, round_time
    FROM rounds
    ORDER BY round_date DESC, round_time DESC
    LIMIT 1
""")
last_row = cursor.fetchone()
last_id, last_map, last_round, last_date, last_time = last_row

last_dt = datetime.strptime(f"{last_date}-{last_time}", '%Y-%m-%d-%H%M%S')
gaming_session_ids = [last_id]
current_dt = last_dt

search_start_date = (last_dt - timedelta(days=1)).strftime('%Y-%m-%d')

cursor.execute("""
    SELECT id, map_name, round_number, round_date, round_time
    FROM rounds
    WHERE round_date >= ?
      AND id < ?
    ORDER BY round_date DESC, round_time DESC
""", (search_start_date, last_id))

previous_sessions = cursor.fetchall()

for sess in previous_sessions:
    sess_id, sess_map, sess_round, sess_date, sess_time = sess
    sess_dt = datetime.strptime(f"{sess_date}-{sess_time}", '%Y-%m-%d-%H%M%S')
    gap_minutes = (current_dt - sess_dt).total_seconds() / 60
    
    if gap_minutes <= 30:
        gaming_session_ids.insert(0, sess_id)
        current_dt = sess_dt
    else:
        break

print(f"\n✅ Gaming Round: {len(gaming_session_ids)} rounds (IDs: {min(gaming_session_ids)} - {max(gaming_session_ids)})")

# Step 2: Get all session details from database
cursor.execute("""
    SELECT id, round_date, round_time, map_name, round_number, match_id
    FROM rounds
    WHERE id IN ({','.join('?' * len(gaming_session_ids))})
    ORDER BY id
""", gaming_session_ids)

db_sessions = cursor.fetchall()

print(f"\n{'='*100}")
print("📋 VERIFYING EACH ROUND")
print(f"{'='*100}\n")

verification_results = []
missing_files = []
data_mismatches = []

for db_id, db_date, db_time, db_map, db_round, db_match_id in db_sessions:
    # Construct expected filename (try both formats: round1 and round-1)
    expected_filename_nodash = f"{db_date}-{db_time}-{db_map}-round{db_round}.txt"
    expected_filename_dash = f"{db_date}-{db_time}-{db_map}-round-{db_round}.txt"
    
    file_path = stats_dir / expected_filename_nodash
    expected_filename = expected_filename_nodash
    
    # If nodash doesn't exist, try with dash
    if not file_path.exists():
        file_path = stats_dir / expected_filename_dash
        expected_filename = expected_filename_dash
    
    print(f"🎮 Session ID {db_id}: {db_map} Round {db_round}")
    print(f"   Expected file: {expected_filename}")
    
    if not file_path.exists():
        print("   ❌ FILE NOT FOUND!")
        missing_files.append((db_id, expected_filename))
        verification_results.append(("MISSING", db_id, expected_filename))
        print()
        continue
    
    print("   ✅ File exists")
    
    # Parse the raw file
    try:
        parser = C0RNP0RN3StatsParser()
        result = parser.parse_stats_file(str(file_path))
        
        # Get player stats from file
        raw_players = {}
        for player in result.get('players', []):
            guid = player.get('guid', '')
            raw_players[guid] = {
                'name': player.get('name', ''),
                'kills': player.get('kills', 0),
                'deaths': player.get('deaths', 0),
                'team': player.get('team', 'Unknown')
            }
        
        # Get player stats from database for this session
        cursor.execute("""
            SELECT player_name, player_guid, kills, deaths, team
            FROM player_comprehensive_stats
            WHERE round_id = ?
        """, (db_id,))
        
        db_players = {}
        for name, guid, kills, deaths, team in cursor.fetchall():
            db_players[guid] = {
                'name': name,
                'kills': kills,
                'deaths': deaths,
                'team': team
            }
        
        # Compare
        print(f"   Players: {len(raw_players)} in file, {len(db_players)} in DB")
        
        if len(raw_players) != len(db_players):
            print("   ⚠️  PLAYER COUNT MISMATCH!")
            data_mismatches.append((db_id, "Player count", len(raw_players), len(db_players)))
        
        # Check each player
        all_guids = set(raw_players.keys()) | set(db_players.keys())
        mismatches_in_session = []
        
        for guid in all_guids:
            if guid not in raw_players:
                print(f"   ❌ GUID {guid[:8]}... in DB but NOT in file!")
                mismatches_in_session.append(f"GUID {guid[:8]} missing from file")
            elif guid not in db_players:
                print(f"   ❌ GUID {guid[:8]}... in file but NOT in DB!")
                mismatches_in_session.append(f"GUID {guid[:8]} missing from DB")
            else:
                raw = raw_players[guid]
                db = db_players[guid]
                
                # Compare stats
                issues = []
                if raw['kills'] != db['kills']:
                    issues.append(f"Kills: file={raw['kills']}, db={db['kills']}")
                if raw['deaths'] != db['deaths']:
                    issues.append(f"Deaths: file={raw['deaths']}, db={db['deaths']}")
                if raw['name'] != db['name']:
                    issues.append(f"Name: file='{raw['name']}', db='{db['name']}'")
                
                if issues:
                    print(f"   ⚠️  {raw['name']} (GUID {guid[:8]}...):")
                    for issue in issues:
                        print(f"      - {issue}")
                    mismatches_in_session.append(f"{raw['name']}: {', '.join(issues)}")
        
        if not mismatches_in_session:
            print("   ✅ All player stats MATCH!")
            verification_results.append(("OK", db_id, expected_filename))
        else:
            print(f"   ❌ {len(mismatches_in_session)} issues found")
            verification_results.append(("MISMATCH", db_id, expected_filename))
            data_mismatches.append((db_id, expected_filename, mismatches_in_session))
    
    except Exception as e:
        print(f"   ❌ ERROR parsing file: {e}")
        verification_results.append(("ERROR", db_id, expected_filename))
    
    print()

# Summary
print("="*100)
print("📊 VERIFICATION SUMMARY")
print("="*100)

ok_count = sum(1 for r in verification_results if r[0] == "OK")
missing_count = sum(1 for r in verification_results if r[0] == "MISSING")
mismatch_count = sum(1 for r in verification_results if r[0] == "MISMATCH")
error_count = sum(1 for r in verification_results if r[0] == "ERROR")

print(f"\n✅ MATCHED: {ok_count}/{len(verification_results)} rounds")
print(f"❌ MISSING FILES: {missing_count}")
print(f"⚠️  DATA MISMATCHES: {mismatch_count}")
print(f"💥 PARSE ERRORS: {error_count}")

if missing_files:
    print(f"\n{'='*100}")
    print("❌ MISSING FILES:")
    print(f"{'='*100}")
    for db_id, filename in missing_files:
        print(f"   Session ID {db_id}: {filename}")

if data_mismatches:
    print(f"\n{'='*100}")
    print("⚠️  DATA MISMATCHES:")
    print(f"{'='*100}")
    for db_id, filename, issues in data_mismatches:
        print(f"\n   Session ID {db_id}: {filename}")
        for issue in issues:
            print(f"      - {issue}")

if ok_count == len(verification_results):
    print("\n🎉 ALL CHECKS PASSED! Database perfectly matches raw stats files!")
else:
    print(f"\n⚠️  {len(verification_results) - ok_count} issues found - review above")

conn.close()
