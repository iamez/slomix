"""Debug script to find exactly why we're getting index out of range errors"""


def analyze_player_line(line, line_num):
    """Analyze a single player line to see what's wrong"""
    parts = line.split('\t')

    # Get player info from first part
    first_part_fields = parts[0].split('\\')
    player_name = first_part_fields[1] if len(first_part_fields) > 1 else "UNKNOWN"

    print(f"\nLine {line_num}: Player '{player_name}'")
    print(f"  Total tab-separated parts: {len(parts)}")

    if len(parts) < 37:
        print(f"  ❌ PROBLEM: Only {len(parts)} parts, need 37!")
        print(f"  First part: {parts[0][:100]}")
        print(f"  Last part: {parts[-1]}")
        return False

    # Now try to parse each field
    try:
        tab_fields = parts[0].split()  # Wait, this is wrong!
        print(f"  ⚠️ WAIT - are we splitting the first part by spaces?")
        print(f"  First part split by spaces: {len(tab_fields)} fields")
        print(f"  First 5: {tab_fields[:5] if len(tab_fields) >= 5 else tab_fields}")
    except BaseException:
        pass

    return True


# Test with one of the files that showed errors
filepath = "local_stats/2025-04-03-215602-etl_adlernest-round-2.txt"

print(f"Analyzing: {filepath}")
print("=" * 80)

try:
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()

    # Skip header
    print(f"Total lines: {len(lines)}")
    print(f"Header: {lines[0].strip()}")

    for i, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            continue
        analyze_player_line(line, i)

except FileNotFoundError:
    print(f"❌ File not found: {filepath}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
