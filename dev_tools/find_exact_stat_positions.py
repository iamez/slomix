#!/usr/bin/env python3
"""
Show exact field positions from raw stat file.
Parse using the actual tab-separated format.
"""

import sqlite3
import re

filepath = 'local_stats/2025-10-28-212120-etl_adlernest-round-1.txt'

with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

# Header
header = lines[0].strip()
print("="*100)
print("HEADER (raw bytes):")
print("="*100)
print(repr(header))
print()

parts = header.split('\\')
print("Header fields:")
for i, p in enumerate(parts):
    print(f"  [{i}]: {repr(p)}")

# First player
print("\n" + "="*100)
print("FIRST PLAYER LINE (raw bytes):")
print("="*100)
player_line = lines[1].strip()
print(repr(player_line[:200]))
print()

# Split by backslash
parts = player_line.split('\\')
print(f"Player has {len(parts)} backslash-separated parts:")
for i in range(min(5, len(parts))):
    print(f"  [{i}]: {repr(parts[i][:50])}")

# The stats are in the last part, separated by TABS
stats_section = parts[-1]
print(f"\nStats section length: {len(stats_section)} chars")
print(f"First 300 chars: {repr(stats_section[:300])}")

# Split by ANY whitespace (spaces AND tabs)
stats = re.split(r'\s+', stats_section.strip())
print(f"\nTotal stats fields: {len(stats)}")
print("\nFirst 50 stats fields:")
for i in range(min(50, len(stats))):
    print(f"  [{i:2d}]: {stats[i]}")

# Now get from database
conn = sqlite3.connect('bot/etlegacy_production.db')
c = conn.cursor()

c.execute("""
    SELECT 
        kills, deaths, damage_given, damage_received,
        efficiency, teamkills
    FROM player_comprehensive_stats
    WHERE round_id = 3404 AND player_guid = 'EDBB5DA9'
""")

db_stats = c.fetchone()
print("\n" + "="*100)
print("DATABASE VALUES for SuperBoyy:")
print("="*100)
print(f"  kills: {db_stats[0]}")
print(f"  deaths: {db_stats[1]}")
print(f"  damage_given: {db_stats[2]}")
print(f"  damage_received: {db_stats[3]}")
print(f"  efficiency: {db_stats[4]}")
print(f"  teamkills: {db_stats[5]}")

print("\n" + "="*100)
print("FINDING MATCHES in raw stats:")
print("="*100)

# Search for each DB value in the stats array
for db_val in db_stats:
    if db_val is not None:
        str_val = str(int(db_val)) if isinstance(db_val, float) and db_val == int(db_val) else str(db_val)
        try:
            idx = stats.index(str_val)
            print(f"  Value {str_val:<10} found at index [{idx}]")
        except ValueError:
            print(f"  Value {str_val:<10} NOT FOUND in stats array")

conn.close()
