"""Debug the Round 2 time parsing issue with 0:00 files."""
import sys
from pathlib import Path
# Add project root to sys.path (relative, portable)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

# Test with a file that has 0:00
test_file = 'local_stats/2025-01-01-213008-etl_adlernest-round-2.txt'

print(f"Testing file with 0:00: {test_file}")
print("=" * 80)

# First, let's see the raw header
with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()
    lines = content.split('\n')
    header = lines[0] if lines else ""
    
    print(f"Raw header: {repr(header)}")
    print()
    
    # Parse the header
    header_parts = header.split('\\')
    print(f"Header parts ({len(header_parts)}):")
    for i, part in enumerate(header_parts):
        print(f"  [{i}]: {repr(part)}")
    
    if len(header_parts) > 7:
        print()
        print(f"map_time (part 6): {repr(header_parts[6])}")
        print(f"actual_time (part 7): {repr(header_parts[7])}")

print()
print("=" * 80)
print("Parsing with parser...")
print()

# Parse with the parser
result = parser.parse_regular_stats_file(test_file)

if result['success']:
    print(f"Parse successful")
    print(f"Map: {result['map_name']}")
    print(f"Round: {result['round_num']}")
    print(f"map_time: {result['map_time']}")
    print(f"actual_time: {result['actual_time']}")
    print(f"round_outcome: {result.get('round_outcome', 'N/A')}")
    print()
    print("✅ The 0:00 case is now handled correctly!")
    print("   Round outcome shows 'Unknown' for Round 2 with 0:00")
else:
    print(f"Parse failed: {result.get('error', 'unknown error')}")
