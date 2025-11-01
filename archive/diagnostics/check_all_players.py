lines = open(
    'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt', 'r', encoding='utf-8'
).readlines()

print("Player lines:")
for i, line in enumerate(lines[1:], 1):
    # Split by backslash first to get the player header
    if '\\' in line:
        parts = line.split('\\')
        guid_part = parts[0]
        name = parts[1] if len(parts) > 1 else "UNKNOWN"
        print(f"{i}. {name} - GUID: {guid_part[:8]}")

        # Now check tab fields
        tab_parts = line.split('\t')
        print(f"   Tab fields: {len(tab_parts)}")
