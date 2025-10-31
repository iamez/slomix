#!/usr/bin/env python3
"""Check olz's line structure in detail"""

file_path = 'local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print('\n' + '='*80)
print('DETAILED LINE STRUCTURE ANALYSIS')
print('='*80)

for i, line in enumerate(lines[1:], 2):  # Skip header
    line = line.strip()
    if not line or '\\' not in line:
        continue
    
    # Split by backslash
    parts = line.split('\\')
    
    if len(parts) < 5:
        continue
    
    guid = parts[0]
    name = parts[1]
    rounds = parts[2]
    team = parts[3]
    stats_section = parts[4]
    
    # Clean name
    import re
    clean_name = re.sub(r'\^[0-9a-zA-Z]', '', name)
    
    # Split weapon stats from extended stats
    if '\t' in stats_section:
        weapon_section, extended_section = stats_section.split('\t', 1)
        weapon_fields = weapon_section.split()
        tab_fields = extended_section.split('\t')
    else:
        weapon_fields = stats_section.split()
        tab_fields = []
    
    print(f"\nLine {i}: {clean_name}")
    print(f"  GUID: {guid}")
    print(f"  Rounds: {rounds}, Team: {team}")
    print(f"  Weapon fields (space-separated): {len(weapon_fields)}")
    print(f"  Extended fields (tab-separated): {len(tab_fields)}")
    
    if len(weapon_fields) < 30:
        print(f"  ⚠️  WARNING: Only {len(weapon_fields)} weapon fields (need 30+)")
        print(f"  ❌ THIS PLAYER WILL BE DROPPED BY PARSER!")
    
    if 'olz' in clean_name.lower():
        print(f"\n  🚨 OLZ FOUND!")
        print(f"  Weapon section: {weapon_section[:100]}...")
        print(f"  Weapon fields count: {len(weapon_fields)}")
        if len(weapon_fields) < 30:
            print(f"  🐛 BUG CONFIRMED: olz's line has only {len(weapon_fields)} weapon fields!")
            print(f"  Parser requires 30+ fields, so olz is being dropped!")

print('\n' + '='*80)
