#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()
data = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

print('='*70)
print('RAW FILE PARSING - October 2, 2025, Session 1')
print('='*70)
print(f'Map: {data.get("map_name", "?")}')
print(f'Players: {len(data.get("players", []))}\n')

print('PLAYER TEAMS:')
for p in data.get('players', []):
    name = p.get('name', 'Unknown')[:20]
    team = p.get('team', '?')
    kills = p.get('kills', 0)
    deaths = p.get('deaths', 0)
    print(f'{name:20} Team={team} K={kills:2} D={deaths:2}')
