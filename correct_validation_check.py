"""
Compare database headshot_kills against TAB field 14 (not weapon sum!)
"""

import sqlite3

# Parse raw file TAB field 14 for all players
raw_headshot_kills = {}

with open('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt', 'r') as f:
    lines = f.readlines()

for line in lines[1:]:  # Skip header
    parts = line.strip().split('\\')
    if len(parts) < 5:
        continue
    
    guid = parts[0][:8]  # 8 chars
    
    # Parse TAB field 14
    weapon_and_tab = parts[4]
    sections = weapon_and_tab.split('\t')
    tab_fields = sections[1:]
    
    headshot_kills = int(tab_fields[14]) if len(tab_fields) > 14 else 0
    raw_headshot_kills[guid] = headshot_kills

# Query database
conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute('''
    SELECT player_guid, player_name, headshot_kills
    FROM player_comprehensive_stats
    WHERE round_id = 2134
    ORDER BY player_name
''')

print("="*70)
print("COMPARING DATABASE vs RAW FILE TAB FIELD 14 (headshot_kills)")
print("="*70)

matches = 0
mismatches = 0

for row in c.fetchall():
    guid = row[0]
    name = row[1]
    db_value = row[2]
    raw_value = raw_headshot_kills.get(guid, -1)
    
    if db_value == raw_value:
        print(f"✅ {name:20s} DB:{db_value:3d} == RAW:{raw_value:3d}")
        matches += 1
    else:
        print(f"❌ {name:20s} DB:{db_value:3d} != RAW:{raw_value:3d}")
        mismatches += 1

print("="*70)
print(f"Matches: {matches}, Mismatches: {mismatches}")

if mismatches == 0:
    print("✅ DATABASE IS CORRECT! It stores headshot_kills from TAB field 14")
    print("❌ VALIDATION SCRIPT IS WRONG! It compares weapon sum vs headshot_kills")
else:
    print("❌ DATABASE HAS ISSUES")

conn.close()
