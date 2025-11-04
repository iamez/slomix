"""
The REAL format: First part has SPACE-separated values, THEN tabs!
"""

test_file = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'

with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

for line in lines[1:]:
    if '^pvid\\' in line:
        parts = line.strip().split('\\')
        if len(parts) >= 5:
            stats_part = parts[4]
            
            print("=" * 100)
            print("🔍 ACTUAL FORMAT DISCOVERY")
            print("=" * 100)
            print()
            print("Raw stats part:")
            print(stats_part[:200])
            print()
            
            # The FIRST part before tabs has SPACE-separated weapon stats!
            if '\t' in stats_part:
                weapon_part, *tab_parts = stats_part.split('\t')
                
                print(f"WEAPON STATS (space-separated): {weapon_part}")
                print(f"Number of tab-separated fields after: {len(tab_parts)}")
                print()
                
                print("TAB-SEPARATED FIELDS:")
                for i, field in enumerate(tab_parts):
                    print(f"  Tab[{i:2d}]: {field}")
                
                print()
                print("💡 REALIZATION:")
                print("  The parser is counting tab fields starting AFTER weapon stats!")
                print("  So 'tab_fields[22]' in the code is actually Tab[22] above")
                print()
                print(f"  Tab[22] = {tab_parts[22] if len(tab_parts) > 22 else 'N/A'} (parser reads as time)")
                print(f"  Tab[23] = {tab_parts[23] if len(tab_parts) > 23 else 'N/A'} (actual time!)")
        break
