#!/usr/bin/env python3
"""
Investigate files with 0:00 session time - what OTHER data do they have?
Can we calculate/infer player time from something else?
"""
import sys
from pathlib import Path
sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Find files with 0:00
print('='*80)
print('FINDING FILES WITH 0:00 SESSION TIME')
print('='*80)

stats_dir = Path('local_stats')
all_files = list(stats_dir.glob('*.txt'))
zero_time_files = []

parser = C0RNP0RN3StatsParser()

for f in all_files:
    # Quick check - read first line
    with open(f, 'r', encoding='utf-8', errors='ignore') as file:
        first_line = file.readline()
        if '\\0:00' in first_line:
            zero_time_files.append(f)

print(f'Total files: {len(all_files)}')
print(f'Files with 0:00: {len(zero_time_files)} ({len(zero_time_files)/len(all_files)*100:.1f}%)')
print()

# Analyze a few zero-time files in detail
print('='*80)
print('DETAILED ANALYSIS OF 0:00 FILES')
print('='*80)

sample_files = zero_time_files[:5]

for filepath in sample_files:
    print(f'\n📄 {filepath.name}')
    print('-'*80)
    
    result = parser.parse_stats_file(str(filepath))
    
    if not result or 'players' not in result:
        print('  ❌ Failed to parse')
        continue
    
    print(f'  Session time: {result.get("actual_time", "N/A")}')
    print(f'  Map: {result.get("map_name", "N/A")}')
    print(f'  Round: {result.get("round_number", "N/A")}')
    print(f'  Players: {len(result["players"])}')
    
    # Check if players have time_played_minutes
    if result['players']:
        sample_player = result['players'][0]
        obj_stats = sample_player.get('objective_stats', {})
        time_played = obj_stats.get('time_played_minutes', -999)
        
        print(f'  Sample player time_played_minutes: {time_played}')
        
        # Check other potentially useful fields
        print('\n  🔍 OTHER AVAILABLE DATA:')
        print(f'     - damage_given: {sample_player.get("damage_given", "N/A")}')
        print(f'     - kills: {sample_player.get("kills", "N/A")}')
        print(f'     - deaths: {sample_player.get("deaths", "N/A")}')
        
        # Check if there's XP or other time-related fields
        if 'objective_stats' in sample_player:
            obj = sample_player['objective_stats']
            print(f'     - xp: {obj.get("xp", "N/A")}')
            print(f'     - time_dead_ratio: {obj.get("time_dead_ratio", "N/A")}')
            
            # NEW: Check if Round 1 exists for this map!
            # If we have Round 2 with 0:00, maybe Round 1 has the time limit?

print()
print('='*80)
print('POSSIBLE SOLUTIONS:')
print('='*80)
print('''
1. **Use Round 1 time as estimate for Round 2**
   - If Round 2 shows 0:00, check if Round 1 file exists
   - Round 1 actual_time might be close to Round 2 duration
   
2. **Calculate from damage/kills patterns**
   - Compare damage in Round 2 to Round 1
   - Estimate time based on damage rate
   
3. **Use map-specific averages**
   - Calculate typical round times per map
   - Use average when time = 0:00
   
4. **Use XP or other metrics**
   - XP might correlate with time played
   - Check if time_dead_ratio gives clues
   
5. **Accept incomplete data**
   - Mark these records as "time unknown"
   - Don't use them in DPM calculations
''')
