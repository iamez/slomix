"""
Check ALL players in the raw file for headshot inconsistencies
"""

with open('local_stats/2025-11-02-211530-etl_adlernest-round-1.txt', 'r') as f:
    lines = f.readlines()

print("="*80)
print("HEADSHOT CONSISTENCY CHECK - ALL PLAYERS")
print("="*80)

for line in lines[1:]:  # Skip header
    parts = line.strip().split('\\')
    if len(parts) < 5:
        continue
    
    guid = parts[0]
    name = parts[1].replace('^7', '').replace('^1', '').replace('^y', '').replace('^h', '').replace('^p', '').replace('^6', '').replace('^2', '').replace('^a', '').replace('^0', '')
    
    # Parse weapon/TAB
    weapon_and_tab = parts[4]
    sections = weapon_and_tab.split('\t')
    weapon_section = sections[0]
    tab_fields = sections[1:]
    
    # Parse weapon stats
    weapon_parts = weapon_section.strip().split(' ')
    weapon_mask = int(weapon_parts[0])
    
    stats_index = 1
    total_hs_weapons = 0
    
    for weapon_id in range(28):
        if weapon_mask & (1 << weapon_id):
            if stats_index + 4 < len(weapon_parts):
                headshots = int(weapon_parts[stats_index + 4])
                total_hs_weapons += headshots
                stats_index += 5
    
    # Get TAB field 14
    hs_from_tab = int(tab_fields[14]) if len(tab_fields) > 14 else 0
    
    # Compare
    status = "✅" if total_hs_weapons == hs_from_tab else "❌"
    diff = total_hs_weapons - hs_from_tab
    
    print(f"{status} {name:20s} Weapons:{total_hs_weapons:3d}  TAB:{hs_from_tab:3d}  Diff:{diff:3d}")

print("="*80)
print("\nCONCLUSION:")
print("If ALL players show mismatches, then c0rnp0rn3.lua has a bug in TAB field 14")
print("The weapon stats section is the CORRECT source of headshots")
print("="*80)
