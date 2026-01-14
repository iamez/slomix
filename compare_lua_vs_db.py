#!/usr/bin/env python3
"""Check what the Lua script actually outputs vs what's in the database."""

from bot.community_stats_parser import C0RNP0RN3StatsParser
import sqlite3

parser = C0RNP0RN3StatsParser()

print("=" * 70)
print("COMPARING RAW LUA OUTPUT vs DATABASE VALUES")
print("=" * 70)
print()

# Parse a file with qmr
data = parser.parse_stats_file('local_stats/2025-10-30-222929-etl_frostbite-round-1.txt')

if data.get('success'):
    for p in data['players']:
        if 'qmr' in p['name'].lower():
            obj = p.get('objective_stats', {})
            name = p['name']
            
            print(f"Player: {name}")
            print()
            print("RAW FROM LUA (TAB fields in stats file):")
            print(f"  Field 22 (time_played_minutes): {obj.get('time_played_minutes', 'N/A')}")
            print(f"  Field 24 (time_dead_ratio):     {obj.get('time_dead_ratio', 'N/A')}")
            print(f"  Field 25 (time_dead_minutes):   {obj.get('time_dead_minutes', 'N/A')}")
            break

# Now check what's in the database for this date/map
print()
print("DATABASE VALUES (after import):")
conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT time_played_minutes, time_dead_minutes, time_dead_ratio
    FROM player_comprehensive_stats
    WHERE clean_name = 'qmr' 
    AND session_date = '2025-10-30'
    AND map_name LIKE '%frostbite%'
""")

row = cursor.fetchone()
if row:
    played, dead, ratio = row
    print(f"  time_played_minutes: {played}")
    print(f"  time_dead_minutes:   {dead}")
    print(f"  time_dead_ratio:     {ratio}")
else:
    print("  (No matching record found)")

conn.close()

print()
print("=" * 70)
print("ANALYSIS:")
print("=" * 70)
print()
print("If RAW LUA shows reasonable values (e.g., 1.2 min dead)")
print("but DATABASE shows impossible values (e.g., 427 min dead)")
print("=> Bug is in the IMPORT process (postgresql_database_manager.py)")
print()
print("If RAW LUA already shows impossible values")
print("=> Bug is in the LUA script itself")
