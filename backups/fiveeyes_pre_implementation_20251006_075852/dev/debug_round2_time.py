"""Debug the Round 2 time parsing issue."""
import sys
sys.path.insert(0, 'G:\\VisualStudio\\Python\\stats')

from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

# Test with the actual file we found
test_file = 'local_stats/2024-03-24-202605-etl_adlernest-round-2.txt'

print(f"Testing file: {test_file}")
print("=" * 80)

# First, let's see what parse_regular_stats_file returns
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
print("Now parsing with parser...")
print()

# Parse with the parser's parse_regular_stats_file (simulating what happens)
result = parser.parse_regular_stats_file(test_file)

if result['success']:
    print(f"✅ Parse successful")
    print(f"Map: {result['map_name']}")
    print(f"Round: {result['round_num']}")
    print(f"map_time: {result['map_time']}")
    print(f"actual_time: {result['actual_time']}")
    print(f"round_outcome: {result.get('round_outcome', 'N/A')}")
else:
    print(f"❌ Parse failed: {result.get('error', 'unknown error')}")

print()
print("=" * 80)
print("Now parsing as Round 2 with differential...")
print()

# Parse as Round 2 (which should trigger differential calculation)
result2 = parser.parse_round_2_with_differential(test_file)

if result2['success']:
    print(f"✅ Round 2 differential parse successful")
    print(f"Map: {result2['map_name']}")
    print(f"Round: {result2['round_num']}")
    print(f"map_time: {result2['map_time']}")
    print(f"actual_time: {result2['actual_time']}")
    print(f"round_outcome: {result2.get('round_outcome', 'N/A')}")
else:
    print(f"❌ Parse failed: {result2.get('error', 'unknown error')}")
