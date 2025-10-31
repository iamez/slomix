#!/usr/bin/env python3
"""Debug the differential calculation to see why olz gets dropped"""

import sys
sys.path.insert(0, '.')

from bot.community_stats_parser import C0RNP0RN3StatsParser

parser = C0RNP0RN3StatsParser()

print('\n' + '='*80)
print('DIFFERENTIAL CALCULATION DEBUG')
print('='*80)

# Parse Round 1 independently
print('\n📄 Parsing Round 1 independently...')
r1 = parser.parse_regular_stats_file('local_stats/2025-10-02-232339-erdenberg_t2-round-1.txt')

print(f"\nRound 1 Success: {r1['success']}")
print(f"Round 1 Players: {len(r1['players'])}\n")

for p in r1['players']:
    name = p['name']
    clean = parser.strip_color_codes(name)
    print(f"  Name (raw): {name:30s} | Clean: {clean:20s} | GUID: {p['guid']}")

# Parse Round 2 independently (no differential)
print('\n\n📄 Parsing Round 2 independently (cumulative)...')
r2_cum = parser.parse_regular_stats_file('local_stats/2025-10-02-232818-erdenberg_t2-round-2.txt')

print(f"\nRound 2 Success: {r2_cum['success']}")
print(f"Round 2 Players (cumulative): {len(r2_cum['players'])}\n")

for p in r2_cum['players']:
    name = p['name']
    clean = parser.strip_color_codes(name)
    print(f"  Name (raw): {name:30s} | Clean: {clean:20s} | GUID: {p['guid']}")

# Now parse Round 2 with differential (this is what actually happens)
print('\n\n📄 Parsing Round 2 with differential calculation...')
r2_diff = parser.parse_stats_file('local_stats/2025-10-02-232818-erdenberg_t2-round-2.txt')

print(f"\nRound 2 Differential Success: {r2_diff['success']}")
print(f"Round 2 Differential Players: {len(r2_diff['players'])}\n")

for p in r2_diff['players']:
    name = p['name']
    clean = parser.strip_color_codes(name)
    print(f"  Name (raw): {name:30s} | Clean: {clean:20s} | GUID: {p['guid']}")

# Check why olz might be missing
print('\n\n' + '='*80)
print('🔍 INVESTIGATING OLZ')
print('='*80)

r1_names = [p['name'] for p in r1['players']]
r2_names = [p['name'] for p in r2_cum['players']]

print(f"\nRound 1 names (raw): {r1_names}")
print(f"Round 2 names (raw): {r2_names}")

# Check for olz in both
olz_r1 = [p for p in r1['players'] if 'olz' in p['name'].lower()]
olz_r2 = [p for p in r2_cum['players'] if 'olz' in p['name'].lower()]

print(f"\nolz in Round 1: {len(olz_r1)} entries")
if olz_r1:
    for p in olz_r1:
        print(f"  Name: '{p['name']}'")
        print(f"  GUID: {p['guid']}")
        print(f"  K/D: {p['kills']}/{p['deaths']}")

print(f"\nolz in Round 2 (cumulative): {len(olz_r2)} entries")
if olz_r2:
    for p in olz_r2:
        print(f"  Name: '{p['name']}'")
        print(f"  GUID: {p['guid']}")
        print(f"  K/D: {p['kills']}/{p['deaths']}")

# Check if names match
if olz_r1 and olz_r2:
    r1_name = olz_r1[0]['name']
    r2_name = olz_r2[0]['name']
    print(f"\n⚠️  Name comparison:")
    print(f"   R1: '{r1_name}' (len={len(r1_name)})")
    print(f"   R2: '{r2_name}' (len={len(r2_name)})")
    print(f"   Match: {r1_name == r2_name}")
    
    if r1_name != r2_name:
        print(f"\n🚨 NAMES DON'T MATCH!")
        print(f"   This is why differential calculation drops olz!")
        print(f"   Differential calculator looks for exact name matches.")
