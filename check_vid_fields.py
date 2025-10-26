lines = open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8'
).readlines()

vid_line = [l for l in lines[1:] if '^pvid' in l][0]
parts = vid_line.split('\\')
stats_section = parts[4]
weapon_section, extended_section = stats_section.split('\t', 1)
tab_fields = extended_section.split('\t')

print(f"Total tab fields: {len(tab_fields)}")
print(f"tab_fields[20] (bullets): {tab_fields[20]}")
print(f"tab_fields[21] (dpm from lua): {tab_fields[21]}")
print(f"tab_fields[22]: {tab_fields[22]}")
print(f"tab_fields[23]: {tab_fields[23]}")
print(f"tab_fields[24]: {tab_fields[24]}")
print(f"tab_fields[25]: {tab_fields[25]}")
