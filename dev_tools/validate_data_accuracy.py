#!/usr/bin/env python3
"""
DATA ACCURACY VALIDATOR
========================

Validates that database values match the raw .txt stats files.

CRITICAL UNDERSTANDING:
- Round 1 files: Stats = exactly what's in the file
- Round 2 files: Raw file has R1+R2 combined stats
- Round 2 database: Should have ONLY R2 differential (R2 - R1)

This script will:
1. Pick random samples from each date range
2. Parse the raw .txt file
3. Query the database
4. Compare values accounting for R2 differential
5. Report any mismatches
"""
import sqlite3
import sys
from pathlib import Path
from random import sample

sys.path.insert(0, str(Path(__file__).parent))
from bot.community_stats_parser import C0RNP0RN3StatsParser

print("=" * 100)
print("DATA ACCURACY VALIDATION")
print("=" * 100)

db_path = "bot/etlegacy_production.db"
stats_dir = Path("local_stats")
parser = C0RNP0RN3StatsParser()

# Get all Round 1 and Round 2 files
all_files = sorted(stats_dir.glob("2025*.txt"))
round1_files = [f for f in all_files if "-round-1.txt" in f.name]
round2_files = [f for f in all_files if "-round-2.txt" in f.name]

print(f"\n📁 Found {len(round1_files)} Round 1 files and {len(round2_files)} Round 2 files")

# Sample some files to validate
num_samples = 5
r1_samples = sample(round1_files, min(num_samples, len(round1_files)))
r2_samples = sample(round2_files, min(num_samples, len(round2_files)))

print(f"\n🎲 Randomly selected {len(r1_samples)} R1 files and {len(r2_samples)} R2 files for validation")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

mismatches = []
validated = 0

def validate_round1(file_path):
    """Validate Round 1 file - should match database exactly"""
    global validated, mismatches
    
    print(f"\n{'='*100}")
    print(f"✅ ROUND 1: {file_path.name}")
    
    # Parse file
    parsed = parser.parse_stats_file(str(file_path))
    if not parsed.get('success'):
        print(f"   ❌ Failed to parse file: {parsed.get('error')}")
        return
    
    # Extract metadata
    file_date = '-'.join(file_path.name.split('-')[:3])
    map_name = parsed.get('map_name')
    round_num = 1
    
    print(f"   📅 Date: {file_date}, Map: {map_name}, Round: {round_num}")
    
    # Query database
    cursor.execute("""
        SELECT id FROM rounds 
        WHERE round_date = ? AND map_name = ? AND round_number = ?
    """, (file_date, map_name, round_num))
    
    session = cursor.fetchone()
    if not session:
        print("   ⚠️  Round not found in database!")
        mismatches.append(f"{file_path.name}: Session not in database")
        return
    
    round_id = session[0]
    print(f"   🔍 Round ID: {round_id}")
    
    # Check each player
    players = parsed.get('players', [])
    print(f"   👥 Validating {len(players)} players...")
    
    for player in players[:2]:  # Check first 2 players as sample
        name = player.get('name')
        guid = player.get('guid')
        
        # Get from database
        cursor.execute("""
            SELECT kills, deaths, damage_given, accuracy, time_played_seconds
            FROM player_comprehensive_stats
            WHERE round_id = ? AND player_guid = ?
        """, (round_id, guid))
        
        db_row = cursor.fetchone()
        if not db_row:
            print(f"      ❌ Player {name} not found in database")
            mismatches.append(f"{file_path.name}: Player {name} missing")
            continue
        
        db_kills, db_deaths, db_damage, db_accuracy, db_time = db_row
        
        # Compare key stats
        file_kills = player.get('kills', 0)
        file_deaths = player.get('deaths', 0)
        file_damage = player.get('damage_given', 0)
        file_accuracy = player.get('accuracy', 0.0)
        file_time = player.get('time_played_seconds', 0)
        
        # Check for mismatches
        checks = [
            ('Kills', file_kills, db_kills),
            ('Deaths', file_deaths, db_deaths),
            ('Damage', file_damage, db_damage),
            ('Time', file_time, db_time),
        ]
        
        player_ok = True
        for stat_name, file_val, db_val in checks:
            if file_val != db_val:
                print(f"      ❌ {name}: {stat_name} mismatch! File={file_val}, DB={db_val}")
                mismatches.append(f"{file_path.name}: {name} {stat_name} file={file_val} db={db_val}")
                player_ok = False
        
        # Accuracy needs tolerance check (floating point)
        if abs(file_accuracy - db_accuracy) > 0.1:
            print(f"      ❌ {name}: Accuracy mismatch! File={file_accuracy:.2f}, DB={db_accuracy:.2f}")
            mismatches.append(f"{file_path.name}: {name} Accuracy file={file_accuracy} db={db_accuracy}")
            player_ok = False
        
        if player_ok:
            print(f"      ✅ {name}: All stats match!")
            validated += 1

def validate_round2(file_path):
    """Validate Round 2 file - database should have R2-R1 differential"""
    global validated, mismatches
    
    print(f"\n{'='*100}")
    print(f"🔄 ROUND 2: {file_path.name}")
    print("   ⚠️  Note: Round 2 raw file contains R1+R2 combined stats")
    print("   ⚠️  Database should contain ONLY R2 differential (R2-R1)")
    
    # Parse R2 file (contains R1+R2 combined)
    parsed_r2 = parser.parse_stats_file(str(file_path))
    if not parsed_r2.get('success'):
        print(f"   ❌ Failed to parse R2 file: {parsed_r2.get('error')}")
        return
    
    # Find corresponding R1 file - need to match by date and map, not exact timestamp
    file_date = '-'.join(file_path.name.split('-')[:3])  # e.g., 2025-06-29
    map_name = parsed_r2.get('map_name')
    
    # Look for R1 file with same date and map
    r1_candidates = list(stats_dir.glob(f"{file_date}-*-{map_name}-round-1.txt"))
    
    if not r1_candidates:
        print(f"   ⚠️  R1 file not found for date {file_date} and map {map_name}")
        print("   ⚠️  Cannot validate differential without R1 file")
        return
    
    if len(r1_candidates) > 1:
        print(f"   ⚠️  Multiple R1 files found for {file_date} {map_name}: {len(r1_candidates)}")
        print(f"   ⚠️  Using first match: {r1_candidates[0].name}")
    
    r1_path = r1_candidates[0]
    
    # Parse R1 file
    parsed_r1 = parser.parse_stats_file(str(r1_path))
    if not parsed_r1.get('success'):
        print(f"   ❌ Failed to parse R1 file: {parsed_r1.get('error')}")
        return
    
    print(f"   ✅ Found R1 file: {r1_path.name}")
    
    # Extract metadata
    file_date = '-'.join(file_path.name.split('-')[:3])
    map_name = parsed_r2.get('map_name')
    round_num = 2
    
    print(f"   📅 Date: {file_date}, Map: {map_name}, Round: {round_num}")
    
    # Query database
    cursor.execute("""
        SELECT id FROM rounds 
        WHERE round_date = ? AND map_name = ? AND round_number = ?
    """, (file_date, map_name, round_num))
    
    session = cursor.fetchone()
    if not session:
        print("   ⚠️  Round not found in database!")
        mismatches.append(f"{file_path.name}: Session not in database")
        return
    
    round_id = session[0]
    print(f"   🔍 Round ID: {round_id}")
    
    # Check each player
    players_r2 = {p.get('guid'): p for p in parsed_r2.get('players', [])}
    players_r1 = {p.get('guid'): p for p in parsed_r1.get('players', [])}
    
    print(f"   👥 Validating differential for {len(players_r2)} players...")
    
    for guid in list(players_r2.keys())[:2]:  # Sample first 2 players
        if guid not in players_r1:
            print(f"      ⚠️  Player {guid} not in R1 file (late joiner)")
            continue
        
        p_r2 = players_r2[guid]
        p_r1 = players_r1[guid]
        name = p_r2.get('name')
        
        # Calculate expected differential
        expected_kills = p_r2.get('kills', 0) - p_r1.get('kills', 0)
        expected_deaths = p_r2.get('deaths', 0) - p_r1.get('deaths', 0)
        expected_damage = p_r2.get('damage_given', 0) - p_r1.get('damage_given', 0)
        
        print(f"      📊 {name}:")
        print(f"         R1 kills: {p_r1.get('kills', 0)}, R2 total: {p_r2.get('kills', 0)}, Diff: {expected_kills}")
        
        # Get from database
        cursor.execute("""
            SELECT kills, deaths, damage_given
            FROM player_comprehensive_stats
            WHERE round_id = ? AND player_guid = ?
        """, (round_id, guid))
        
        db_row = cursor.fetchone()
        if not db_row:
            print("         ❌ Player not found in database")
            mismatches.append(f"{file_path.name}: Player {name} missing from R2")
            continue
        
        db_kills, db_deaths, db_damage = db_row
        
        # Compare differentials
        checks = [
            ('Kills', expected_kills, db_kills),
            ('Deaths', expected_deaths, db_deaths),
            ('Damage', expected_damage, db_damage),
        ]
        
        player_ok = True
        for stat_name, expected, actual in checks:
            if expected != actual:
                print(f"         ❌ {stat_name} mismatch! Expected={expected}, DB={actual}")
                mismatches.append(f"{file_path.name}: {name} R2 {stat_name} expected={expected} db={actual}")
                player_ok = False
        
        if player_ok:
            print("         ✅ All differentials match!")
            validated += 1

# Run validations
print("\n" + "=" * 100)
print("VALIDATING ROUND 1 FILES (should match exactly)")
print("=" * 100)

for file_path in r1_samples:
    validate_round1(file_path)

print("\n" + "=" * 100)
print("VALIDATING ROUND 2 FILES (should have R2-R1 differential)")
print("=" * 100)

for file_path in r2_samples:
    validate_round2(file_path)

# Summary
print("\n" + "=" * 100)
print("VALIDATION SUMMARY")
print("=" * 100)
print(f"✅ Successfully validated: {validated} player records")
print(f"❌ Mismatches found: {len(mismatches)}")

if mismatches:
    print("\n🔍 MISMATCHES DETAILS:")
    for mismatch in mismatches[:10]:  # Show first 10
        print(f"   - {mismatch}")
    if len(mismatches) > 10:
        print(f"   ... and {len(mismatches) - 10} more")
    print("\n⚠️  DATA VALIDATION FAILED!")
else:
    print("\n🎉 ALL DATA VALIDATED SUCCESSFULLY!")
    print("   Database values match raw .txt files (accounting for R2 differential)")

conn.close()
print("\n" + "=" * 100)
