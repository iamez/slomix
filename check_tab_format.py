"""Check if file has TAB-separated extended stats"""

with open('local_stats/2025-10-28-212120-etl_adlernest-round-1.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Check SuperBoyy's line (line 1)
line = lines[1].strip()
parts = line.split('\\')
print(f"Parts in line: {len(parts)}")

if len(parts) >= 5:
    stats_section = parts[4]
    has_tab = '\t' in stats_section
    print(f"Has TAB character: {has_tab}")
    print(f"TAB count: {stats_section.count(chr(9))}")
    
    if has_tab:
        weapon_section, extended_section = stats_section.split('\t', 1)
        tab_fields = extended_section.split('\t')
        print(f"\nExtended fields count: {len(tab_fields)}")
        print(f"\nFirst 10 extended fields:")
        for i, field in enumerate(tab_fields[:10]):
            print(f"  [{i}] = {field}")
        
        print(f"\nField [2] (team_damage_given) = {tab_fields[2] if len(tab_fields) > 2 else 'MISSING'}")
        print(f"Field [3] (team_damage_received) = {tab_fields[3] if len(tab_fields) > 3 else 'MISSING'}")
        print(f"Field [14] (headshot_kills) = {tab_fields[14] if len(tab_fields) > 14 else 'MISSING'}")
    else:
        print("\n❌ NO TAB CHARACTER FOUND - Extended stats not present!")
        print(f"Stats section: {stats_section[:200]}")
