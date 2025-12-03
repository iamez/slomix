#!/usr/bin/env python3
"""Test Round 2 file parsing with debug output"""
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-12-220306-te_escape2-round-2.txt')

print("\n✅ Parsed successfully!")
print(f"Players: {len(result.get('players', []))}")
print(f"Map: {result.get('map_name', 'unknown')}")
