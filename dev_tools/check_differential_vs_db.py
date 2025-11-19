"""Compare parser differential output vs database values"""
import sqlite3
import sys
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Parse the Nov 2 midnight R2 file (should give differential)
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-11-02-000624-etl_adlernest-round-2.txt')

print("=" * 80)
print("PARSER OUTPUT (R2 Differential - R2 only stats)")
print("=" * 80)
print()

# Get carniee's stats from parser
carniee_parser = [p for p in result['players'] if 'carniee' in p['name'].lower()][0]
print(f"Player: {carniee_parser['name']}")
print(f"  Kills: {carniee_parser['kills']}")
print(f"  Deaths: {carniee_parser['deaths']}")
print(f"  Damage: {carniee_parser['damage_given']}")
print(f"  Headshots: {carniee_parser['headshots']}")
print(f"  XP: {carniee_parser.get('xp_total', 'N/A')}")
print(f"  Time: {carniee_parser['time_played_seconds']}s")
print()
print("Available keys:", list(carniee_parser.keys()))
print()

# Get carniee's stats from database (round 192 is the midnight round)
conn = sqlite3.connect('bot/etlegacy_production.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT player_name, kills, deaths, damage_given, headshot_kills, xp, time_played_seconds
    FROM player_comprehensive_stats
    WHERE round_id = 192 AND player_name LIKE "%carniee%"
''')
db_row = cursor.fetchone()

print("=" * 80)
print("DATABASE VALUES (Round ID 192 - Midnight Round)")
print("=" * 80)
print()
print(f"Player: {db_row[0]}")
print(f"  Kills: {db_row[1]}")
print(f"  Deaths: {db_row[2]}")
print(f"  Damage: {db_row[3]}")
print(f"  Headshots: {db_row[4]}")
print(f"  XP: {db_row[5]}")
print(f"  Time: {db_row[6]}s")
print()

# Compare
print("=" * 80)
print("COMPARISON")
print("=" * 80)
print()

matches = []
mismatches = []

fields = [
    ('kills', carniee_parser['kills'], db_row[1]),
    ('deaths', carniee_parser['deaths'], db_row[2]),
    ('damage', carniee_parser['damage_given'], db_row[3]),
    ('headshots', carniee_parser['headshots'], db_row[4]),
    ('time', carniee_parser['time_played_seconds'], db_row[6]),
]

for field_name, parser_val, db_val in fields:
    if parser_val == db_val:
        matches.append(field_name)
        print(f"✅ {field_name}: {parser_val} == {db_val}")
    else:
        mismatches.append(field_name)
        print(f"❌ {field_name}: parser={parser_val}, db={db_val}, diff={abs(parser_val - db_val)}")

print()
print(f"Matches: {len(matches)}/5")
print(f"Mismatches: {len(mismatches)}/5")
print()

if len(mismatches) == 0:
    print("🎉 PERFECT! Database has correct differential values!")
else:
    print(f"⚠️  {len(mismatches)} fields don't match - investigating...")
    print()
    print("Checking if database has CUMULATIVE values instead of differential...")
    print()
    
    # Parse R1 file to get cumulative calculation
    r1_result = parser.parse_stats_file('local_stats/2025-11-01-235515-etl_adlernest-round-1.txt')
    carniee_r1 = [p for p in r1_result['players'] if 'carniee' in p['name'].lower()]
    
    if carniee_r1:
        carniee_r1 = carniee_r1[0]
        print("R1 values:")
        print(f"  Kills: {carniee_r1['kills']}")
        print(f"  XP: {carniee_r1['xp']}")
        print()
        
        # Check if DB = R1 + R2_differential
        expected_cumulative_kills = carniee_r1['kills'] + carniee_parser['kills']
        expected_cumulative_xp = carniee_r1['xp'] + carniee_parser['xp']
        
        print("If database had CUMULATIVE (R1 + R2):")
        print(f"  Expected kills: {carniee_r1['kills']} (R1) + {carniee_parser['kills']} (R2) = {expected_cumulative_kills}")
        print(f"  Database kills: {db_row[1]}")
        print(f"  Match: {expected_cumulative_kills == db_row[1]}")
        print()
        print(f"  Expected XP: {carniee_r1['xp']} (R1) + {carniee_parser['xp']} (R2) = {expected_cumulative_xp}")
        print(f"  Database XP: {db_row[5]}")
        print(f"  Match: {expected_cumulative_xp == db_row[5]}")

conn.close()
