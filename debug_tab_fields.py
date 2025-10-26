# Test the supply R2 file (should fail)
file_path = r'local_stats\2025-10-02-214239-supply-round-2.txt'
print(f"\nTesting: {file_path}")
print("=" * 80)

# Read the entire file as one string
with open(file_path, 'r') as f:
    content = f.read()

# The file format: header line, then player entries separated by newlines
# But sometimes all on one line with specific delimiters
lines = content.split('\n')
header = lines[0]
print(f"Header: {header[:100]}")

# Find vid's hashed GUID in the content (CRC32 hash)
guid_hash = "D8423F90"  # vid's hashed GUID

# Try searching in the full content
if guid_hash in content:
    print(f"\n✓ Found GUID hash '{guid_hash}' in file")

    # Find the player entry - it's between the GUID and the next GUID or end
    guid_start = content.find(guid_hash)

    # Extract context around the GUID (100 chars before, 500 after)
    context_start = max(0, guid_start - 100)
    context_end = min(len(content), guid_start + 1000)
    context = content[context_start:context_end]

    print(f"\nContext around GUID:\n{context[:500]}")

    # The format seems to be: GUID\Name\Team\Round\Stats
    # Let's find the stats part which contains tabs
    # Look for the pattern after the GUID
    after_guid = content[guid_start:]
    parts = after_guid.split('\\', 4)  # Split on backslash

    if len(parts) >= 5:
        stats_section = parts[4]
        # The stats section goes until the next GUID
        # Let's truncate at a reasonable point
        next_guid_pos = stats_section.find('\n')
        if next_guid_pos > 0:
            stats_section = stats_section[:next_guid_pos]

        print(f"\nStats section (first 300 chars):\n{stats_section[:300]}")

        # Now check if there are tabs
        if '\t' in stats_section:
            weapon_section, extended_section = stats_section.split('\t', 1)
            print(f"\nWeapon section: {weapon_section[:100]}")
            print(f"\nExtended section (first 300 chars):\n{extended_section[:300]}")

            # Split by tabs
            tab_fields = extended_section.split('\t')
            print(f"\nTab fields count: {len(tab_fields)}")

            # Show field 23
            if len(tab_fields) > 23:
                print(f"\nTab[23]: '{tab_fields[23]}'")
            else:
                print(f"\n⚠️ Only {len(tab_fields)} fields!")
else:
    print(f"\n✗ GUID hash '{guid_hash}' NOT found in file")
