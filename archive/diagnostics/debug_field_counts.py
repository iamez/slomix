"""Debug script to check tab field counts for all players in files with warnings"""


def check_file_field_counts(filepath):
    """Check tab field count for each player line"""
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    print(f"\n{'=' * 80}")
    print(f"File: {filepath}")
    print(f"{'=' * 80}")

    # Skip header (first line)
    for i, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            continue

        # Split on tab to count tab-separated fields in extended section
        parts = line.split('\t')
        field_count = len(parts)

        # Extract player name (second field after first backslash in first part)
        first_part_fields = parts[0].split('\\')
        player_name = first_part_fields[1] if len(first_part_fields) > 1 else "UNKNOWN"

        # Show all lines, highlight problems
        status = "✅ OK" if field_count == 37 else f"❌ PROBLEM - {field_count} fields"
        print(f"Line {i}: {status:25} Player: {player_name[:30]:30}")

        if field_count != 37:
            print(f"       Full line: {line[:150]}...")


# Check a few files that showed warnings
test_files = [
    "local_stats/2025-03-23-212237-etl_adlernest-round-1.txt",
    "local_stats/2025-03-23-212823-etl_adlernest-round-2.txt",
]

for filepath in test_files:
    try:
        check_file_field_counts(filepath)
    except FileNotFoundError:
        print(f"\n❌ File not found: {filepath}")
    except Exception as e:
        print(f"\n❌ Error processing {filepath}: {e}")
