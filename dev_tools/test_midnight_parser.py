"""Test midnight-crossing R2 file parsing"""
import sys
import os
sys.path.insert(0, 'bot')

from community_stats_parser import C0RNP0RN3StatsParser
from pathlib import Path

# Test with relative path (like database_manager uses)
parser = C0RNP0RN3StatsParser()

test_file = "local_stats/2025-11-02-000624-etl_adlernest-round-2.txt"
print(f"Testing with relative path: {test_file}")
print(f"Current working directory: {os.getcwd()}")
print(f"File exists: {os.path.exists(test_file)}")
print(f"Directory: {os.path.dirname(test_file)}")
print()

# Check what the parser searches for
import glob
directory = os.path.dirname(test_file)
print(f"Parser will search in directory: '{directory}'")

# Same day search
search_pattern = "2025-11-02-*-etl_adlernest-round-1.txt"
pattern_path = os.path.join(directory, search_pattern) if directory else search_pattern
print(f"Same day pattern: {pattern_path}")
same_day_files = glob.glob(pattern_path)
print(f"Same day files found: {same_day_files}")
print()

# Previous day search
prev_search_pattern = "2025-11-01-*-etl_adlernest-round-1.txt"
pattern_path = os.path.join(directory, prev_search_pattern) if directory else prev_search_pattern
print(f"Previous day pattern: {pattern_path}")
prev_day_files = glob.glob(pattern_path)
print(f"Previous day files found: {prev_day_files}")
print()

# Now test actual parser
print("="*60)
print("Running actual parser:")
print("="*60)
result = parser.parse_stats_file(test_file)
