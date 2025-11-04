#!/usr/bin/env python3
"""
Parse the RAW stat files from October 2nd to see what time data EXISTS
in the files vs what we have in database.
"""
import sys
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser

# Files from user's attachments (in local_stats folder)
files_to_check = [
    ('etl_adlernest R1', 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'),
    ('etl_adlernest R2', 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'),
    ('supply R1', 'local_stats/2025-10-02-213333-supply-round-1.txt'),
    ('supply R2', 'local_stats/2025-10-02-214239-supply-round-2.txt'),
    ('etl_sp_delivery R1', 'local_stats/2025-10-02-214959-etl_sp_delivery-round-1.txt'),
    ('etl_sp_delivery R2', 'local_stats/2025-10-02-215634-etl_sp_delivery-round-2.txt'),
    ('te_escape2 R1 (1st)', 'local_stats/2025-10-02-220201-te_escape2-round-1.txt'),
    ('te_escape2 R2 (1st)', 'local_stats/2025-10-02-220708-te_escape2-round-2.txt'),
    ('te_escape2 R1 (2nd)', 'local_stats/2025-10-02-221225-te_escape2-round-1.txt'),
    ('te_escape2 R2 (2nd)', 'local_stats/2025-10-02-221711-te_escape2-round-2.txt'),
]

print("=" * 120)
print("🔍 RAW FILE ANALYSIS - October 2, 2025")
print("=" * 120)
print()

for label, filepath in files_to_check:
    print("=" * 120)
    print(f"📄 {label}")
    print(f"   File: {filepath}")
    print("=" * 120)
    print()
    
    # Read raw file
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"❌ File not found: {filepath}")
        print()
        continue
    
    # Parse header
    header = lines[0].strip()
    header_parts = header.split('\\')
    
    print(f"HEADER:")
    print(f"  Server: {header_parts[0]}")
    print(f"  Map: {header_parts[1]}")
    print(f"  Round: {header_parts[3]}")
    print(f"  Time Limit: {header_parts[6]}")
    print(f"  Actual Time: {header_parts[7]}")
    print()
    
    # Parse player lines
    print(f"PLAYERS (Raw Tab[22] time_played_minutes):")
    print(f"{'Player':<25} {'Tab[22] Time':<15} {'Damage':<10} {'Kills':<7}")
    print("-" * 120)
    
    for i, line in enumerate(lines[1:], 1):
        parts = line.strip().split('\t')
        
        if len(parts) < 23:
            continue
            
        # First part contains weapon stats + GUID + name
        weapon_part = parts[0]
        weapon_fields = weapon_part.split()
        
        # Extract GUID and name
        guid = weapon_fields[0] if weapon_fields else "Unknown"
        name = weapon_fields[1] if len(weapon_fields) > 1 else "Unknown"
        
        # Tab fields
        damage = parts[1] if len(parts) > 1 else "0"
        time_played = parts[22] if len(parts) > 22 else "N/A"
        
        # Try to get kills from weapon stats (need to parse the weapon part better)
        print(f"{name:<25} {time_played:<15} {damage:<10}")
    
    print()
    
    # Now parse with OUR PARSER (current fixed version)
    print("PARSED BY OUR PARSER (CURRENT VERSION):")
    print("-" * 120)
    
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_stats_file(filepath)
    
    if result and 'players' in result:
        print(f"{'Player':<25} {'Parsed Time':<15} {'Damage':<10} {'Kills':<7}")
        print("-" * 120)
        for player in result['players']:
            name = player.get('name', 'Unknown')
            time_mins = player.get('objective_stats', {}).get('time_played_minutes', 0)
            damage = player.get('damage_given', 0)
            kills = player.get('kills', 0)
            
            time_str = f"{time_mins:.1f}" if time_mins > 0 else "0.0 ❌"
            print(f"{name:<25} {time_str:<15} {damage:<10} {kills:<7}")
    else:
        print("❌ Parser returned None or no players!")
    
    print()
    print()

print("=" * 120)
print("🎯 KEY QUESTION:")
print("=" * 120)
print()
print("If players can't join late, why do Round 2 CUMULATIVE files show")
print("Tab[22] time_played_minutes = 0.0 for ALL players?")
print()
print("This suggests the lua script is NOT writing player time to Round 2 files!")
