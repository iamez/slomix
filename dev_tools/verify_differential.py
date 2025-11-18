#!/usr/bin/env python3
"""Verify differential calculation for endekk across R1 and R2."""

# R1 stats for endekk
r1_line = "7B84BE88\\endekk\\0\\2\\134219832 1 6 0 0 0 0 0 0 5 0 82 180 5 0 12 4 5 1 0 0 1 2 0 0 0 \t1943\t1426\t0\t0\t1\t3\t0\t0\t83.1\t44"

parts = r1_line.split('\\')
stats = parts[4]
if '\t' in stats:
    weapon, extended = stats.split('\t', 1)
    tab_fields = extended.split('\t')
    r1_damage_given = int(tab_fields[0])
    r1_damage_received = int(tab_fields[1])
else:
    r1_damage_given = 0
    r1_damage_received = 0

print("endekk R1 stats:")
print(f"  damage_given: {r1_damage_given}")
print(f"  damage_received: {r1_damage_received}")

# R2 cumulative stats for endekk
r2_line = "7B84BE88\\endekk\\1\\1\\134219836 3 5 1 0 0 1 6 0 1 0 27 68 2 5 5 115 253 7 2 18 4 8 1 1 0 1 3 0 0 0 \t3309\t2521\t0\t53\t4\t3\t0\t0\t80.8\t34"

parts = r2_line.split('\\')
stats = parts[4]
if '\t' in stats:
    weapon, extended = stats.split('\t', 1)
    tab_fields = extended.split('\t')
    r2_damage_given = int(tab_fields[0])
    r2_damage_received = int(tab_fields[1])
else:
    r2_damage_given = 0
    r2_damage_received = 0

print("\nendekk R2 cumulative stats (raw file):")
print(f"  damage_given: {r2_damage_given}")
print(f"  damage_received: {r2_damage_received}")

# Calculate differential
diff_damage_given = r2_damage_given - r1_damage_given
diff_damage_received = r2_damage_received - r1_damage_received

print("\nendekk R2 differential (R2 - R1):")
print(f"  damage_given: {diff_damage_given}")
print(f"  damage_received: {diff_damage_received}")

# Check database
import sqlite3
conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute("""
    SELECT damage_given, damage_received
    FROM player_comprehensive_stats
    WHERE round_id = 3405 AND player_guid = '7B84BE88'
""")

db_stats = c.fetchone()
if db_stats:
    print("\nendekk R2 in DATABASE:")
    print(f"  damage_given: {db_stats[0]}")
    print(f"  damage_received: {db_stats[1]}")
    
    print("\n" + "="*60)
    if db_stats[0] == diff_damage_given and db_stats[1] == diff_damage_received:
        print("✅ DATABASE MATCHES DIFFERENTIAL CALCULATION!")
    else:
        print("❌ DATABASE DOES NOT MATCH!")
        print(f"   Expected: {diff_damage_given}/{diff_damage_received}")
        print(f"   Got:      {db_stats[0]}/{db_stats[1]}")
else:
    print("\n❌ endekk not found in database for session 3405")

conn.close()
