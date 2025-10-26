lines = open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8'
).readlines()

print("Checking tab field counts in extended section:")
for i, line in enumerate(lines[1:], 1):
    if '\\' in line:
        parts = line.split('\\')
        name = parts[1] if len(parts) > 1 else "UNKNOWN"
        stats_section = parts[4] if len(parts) > 4 else ""

        if '\t' in stats_section:
            weapon_section, extended_section = stats_section.split('\t', 1)
            tab_fields = extended_section.split('\t')
            print(f"{i}. {name}: {len(tab_fields)} tab fields")
            if len(tab_fields) < 38:
                print(f"   WARNING: Only {len(tab_fields)} fields!")
                print(f"   Last 3 fields: {tab_fields[-3:]}")
        else:
            print(f"{i}. {name}: NO TAB in stats_section!")
