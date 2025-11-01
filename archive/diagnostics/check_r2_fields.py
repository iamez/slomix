lines = open(
    'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt', 'r', encoding='utf-8'
).readlines()

for i, line in enumerate(lines[1:], 1):
    if '\\' in line:
        parts = line.split('\\')
        name = parts[1] if len(parts) > 1 else "UNKNOWN"
        stats_section = parts[4] if len(parts) > 4 else ""

        if '\t' in stats_section:
            weapon_section, extended_section = stats_section.split('\t', 1)
            tab_fields = extended_section.split('\t')
            print(f"{i}. {name}: {len(tab_fields)} tab fields")
