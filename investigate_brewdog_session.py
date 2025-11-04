#!/usr/bin/env python3
"""
INVESTIGATE SPECIFIC SESSION
Detailed analysis of 2025-09-09-225817-et_brewdog-round-1.txt
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bot.community_stats_parser import C0RNP0RN3StatsParser

print("=" * 100)
print("INVESTIGATING: 2025-09-09-225817-et_brewdog-round-1.txt")
print("=" * 100)

file_path = Path("local_stats/2025-09-09-225817-et_brewdog-round-1.txt")
parser = C0RNP0RN3StatsParser()

# Parse the file
print("\n📄 PARSING FILE...")
parsed = parser.parse_stats_file(str(file_path))

if not parsed.get('success'):
    print(f"❌ Failed to parse: {parsed.get('error')}")
    sys.exit(1)

print(f"✅ Parsed successfully")
print(f"   Map: {parsed.get('map_name')}")
print(f"   Duration: {parsed.get('duration_seconds')}s")
print(f"   Players: {len(parsed.get('players', []))}")

# Show SuperBoyy and temu.wjs data from file
print("\n" + "=" * 100)
print("PLAYER DATA FROM FILE")
print("=" * 100)

target_players = ['SuperBoyy', 'temu.wjs']
for player in parsed.get('players', []):
    if player.get('name') in target_players:
        print(f"\n👤 {player.get('name')} (GUID: {player.get('guid')})")
        print(f"   Kills: {player.get('kills')}")
        print(f"   Deaths: {player.get('deaths')}")
        print(f"   Damage Given: {player.get('damage_given')}")
        print(f"   Time Played: {player.get('time_played_seconds')}s")
        print(f"   Accuracy: {player.get('accuracy'):.2f}%")

# Query database
print("\n" + "=" * 100)
print("PLAYER DATA FROM DATABASE")
print("=" * 100)

db_path = "bot/etlegacy_production.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

file_date = '2025-09-09'
map_name = parsed.get('map_name')

cursor.execute("""
    SELECT id FROM rounds 
    WHERE round_date = ? AND map_name = ? AND round_number = 1
""", (file_date, map_name))

session = cursor.fetchone()
if not session:
    print(f"❌ Round not found in database!")
    conn.close()
    sys.exit(1)

round_id = session[0]
print(f"✅ Session found: ID = {round_id}")

# Get player stats
cursor.execute("""
    SELECT player_guid, player_name, kills, deaths, damage_given, 
           accuracy, time_played_seconds
    FROM player_comprehensive_stats
    WHERE round_id = ?
""", (round_id,))

db_players = cursor.fetchall()
print(f"\n📊 Found {len(db_players)} players in database:")

for guid, player_name, kills, deaths, damage, accuracy, time in db_players:
    print(f"\n👤 {player_name} (GUID: {guid})")
    print(f"   Kills: {kills}")
    print(f"   Deaths: {deaths}")
    print(f"   Damage Given: {damage}")
    print(f"   Time Played: {time}s")
    if accuracy is not None:
        print(f"   Accuracy: {accuracy:.2f}%")
    else:
        print(f"   Accuracy: None")

# Check if this might be a Round 2 file misidentified as Round 1
print("\n" + "=" * 100)
print("HYPOTHESIS CHECK: Is this actually a Round 2 file?")
print("=" * 100)

# Check if there's a Round 2 file
r2_files = list(Path("local_stats").glob(f"{file_date}-*-{map_name}-round-2.txt"))
print(f"Round 2 files for this date/map: {len(r2_files)}")
for r2_file in r2_files:
    print(f"   - {r2_file.name}")

conn.close()

print("\n" + "=" * 100)
