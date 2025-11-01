#!/usr/bin/env python3
"""Deep dive into olz's weapon data to understand the real issue"""

file_path = 'local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt'

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

print('\n' + '='*80)
print('DEEP WEAPON DATA ANALYSIS')
print('='*80)

import re

def strip_color_codes(text):
    return re.sub(r'\^[0-9a-zA-Z]', '', text)

for i, line in enumerate(lines[1:], 2):  # Skip header
    line = line.strip()
    if not line or '\\' not in line:
        continue
    
    parts = line.split('\\')
    if len(parts) < 5:
        continue
    
    guid = parts[0]
    name = parts[1]
    clean_name = strip_color_codes(name)
    stats_section = parts[4]
    
    # Split weapon stats from extended stats
    if '\t' in stats_section:
        weapon_section, extended_section = stats_section.split('\t', 1)
    else:
        weapon_section = stats_section
        extended_section = None
    
    weapon_fields = weapon_section.split()
    
    if len(weapon_fields) > 0:
        weapon_mask = int(weapon_fields[0])
        
        # Count how many weapon bits are set
        weapon_bits_set = bin(weapon_mask).count('1')
        
        # Each weapon needs 5 fields (hits, shots, kills, deaths, headshots)
        expected_fields = 1 + (weapon_bits_set * 5)  # 1 for mask + 5 per weapon
        
        print(f"\n{clean_name}:")
        print(f"  Weapon mask: {weapon_mask} (binary: {bin(weapon_mask)})")
        print(f"  Weapons used: {weapon_bits_set}")
        print(f"  Expected fields: {expected_fields} (1 mask + {weapon_bits_set} × 5)")
        print(f"  Actual fields: {len(weapon_fields)}")
        
        if len(weapon_fields) != expected_fields:
            print(f"  ⚠️  MISMATCH! Expected {expected_fields} but got {len(weapon_fields)}")
            print(f"  Difference: {len(weapon_fields) - expected_fields}")
        
        if 'olz' in clean_name.lower():
            print(f"\n  🔍 OLZ DETAILED ANALYSIS:")
            print(f"  First 30 weapon fields: {weapon_fields[:30]}")
            print(f"  All weapon fields: {weapon_fields}")
            
            # Try to parse weapons manually
            print(f"\n  Parsing weapons from mask {weapon_mask}:")
            stats_index = 1
            for weapon_id in range(28):
                if weapon_mask & (1 << weapon_id):
                    weapon_name = {
                        0: "KNIFE", 1: "KNIFE_KBAR", 2: "LUGER", 3: "COLT",
                        4: "MP40", 5: "THOMPSON", 6: "STEN", 7: "FG42",
                        8: "PANZERFAUST", 9: "BAZOOKA", 10: "FLAMETHROWER",
                        11: "GRENADE", 12: "MORTAR", 13: "MORTAR2",
                        14: "DYNAMITE", 15: "AIRSTRIKE", 16: "ARTILLERY",
                        17: "SATCHEL", 18: "GRENADELAUNCHER", 19: "LANDMINE",
                        20: "MG42", 21: "BROWNING", 22: "CARBINE",
                        23: "KAR98", 24: "GARAND", 25: "K43", 26: "MP34",
                        27: "SYRINGE"
                    }.get(weapon_id, f"UNKNOWN_{weapon_id}")
                    
                    if stats_index + 4 < len(weapon_fields):
                        print(f"    Weapon {weapon_id} ({weapon_name}): fields {stats_index}-{stats_index+4}")
                        stats_index += 5
                    else:
                        print(f"    Weapon {weapon_id} ({weapon_name}): ⚠️  NOT ENOUGH FIELDS!")
                        break
            
            print(f"\n  Final stats_index: {stats_index}")
            print(f"  Fields remaining: {len(weapon_fields) - stats_index}")

print('\n' + '='*80)
