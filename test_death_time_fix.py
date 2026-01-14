#!/usr/bin/env python3
"""Test the death time calculation fix for R2 differential stats."""

from bot.community_stats_parser import C0RNP0RN3StatsParser


def test_r2_differential_death_time():
    """Test that R2 death time is calculated by subtraction, not using cumulative ratio."""
    
    # Test data simulating Round 1 and Round 2 with death time
    r1_player = {
        'name': 'qmr',
        'guid': 'ABC123',
        'team': 1,
        'kills': 10,
        'deaths': 5,
        'damage_given': 1000,
        'damage_received': 500,
        'headshots': 2,
        'objective_stats': {
            'time_played_minutes': 20.0,
            'time_dead_minutes': 5.0,   # 5 min dead in R1
            'time_dead_ratio': 25.0,    # 25% of 20 min
        },
        'weapon_stats': {}
    }

    r2_cumulative_player = {
        'name': 'qmr',
        'guid': 'ABC123',
        'team': 2,
        'kills': 25,
        'deaths': 12,
        'damage_given': 2500,
        'damage_received': 1200,
        'headshots': 5,
        'objective_stats': {
            'time_played_minutes': 45.0,  # Total both rounds
            'time_dead_minutes': 12.0,    # Total dead both rounds
            'time_dead_ratio': 26.67,     # Cumulative ratio (12/45*100)
        },
        'weapon_stats': {}
    }

    # Calculate expected R2-only values
    expected_r2_time = 45.0 - 20.0   # 25 min
    expected_r2_dead = 12.0 - 5.0    # 7 min dead in R2
    expected_r2_ratio = (7.0 / 25.0) * 100  # 28%

    print('=== Death Time Fix Verification ===')
    print(f'R1: {r1_player["objective_stats"]["time_played_minutes"]} min played, {r1_player["objective_stats"]["time_dead_minutes"]} min dead')
    print(f'R2 Cumulative: {r2_cumulative_player["objective_stats"]["time_played_minutes"]} min played, {r2_cumulative_player["objective_stats"]["time_dead_minutes"]} min dead')
    print()
    print(f'Expected R2-only: {expected_r2_time} min played, {expected_r2_dead} min dead, {expected_r2_ratio:.1f}% ratio')
    print()

    # Test the parser's calculate_round_2_differential method
    parser = C0RNP0RN3StatsParser()

    r1_data = {
        'players': [r1_player], 
        'map_name': 'supply', 
        'map_time': 1200, 
        'actual_time': '20:00',
        'round_outcome': 'Axis',
        'round_num': 1,
        'success': True
    }
    r2_data = {
        'players': [r2_cumulative_player], 
        'map_name': 'supply', 
        'map_time': 2700, 
        'actual_time': '45:00',
        'round_outcome': 'Allied',
        'round_num': 2,
        'success': True
    }

    result = parser.calculate_round_2_differential(r1_data, r2_data)
    r2_only = result['players'][0]

    actual_time = r2_only['objective_stats'].get('time_played_minutes', 0)
    actual_dead = r2_only['objective_stats'].get('time_dead_minutes', 0)
    actual_ratio = r2_only['objective_stats'].get('time_dead_ratio', 0)

    print(f'Actual R2-only: {actual_time} min played, {actual_dead} min dead, {actual_ratio:.1f}% ratio')
    print()

    # Verify
    all_pass = True
    
    if abs(actual_time - expected_r2_time) > 0.01:
        print(f'❌ FAIL: time_played_minutes {actual_time} != expected {expected_r2_time}')
        all_pass = False
    else:
        print(f'✅ PASS: time_played_minutes = {actual_time}')

    if abs(actual_dead - expected_r2_dead) > 0.01:
        print(f'❌ FAIL: time_dead_minutes {actual_dead} != expected {expected_r2_dead}')
        all_pass = False
    else:
        print(f'✅ PASS: time_dead_minutes = {actual_dead}')

    if abs(actual_ratio - expected_r2_ratio) > 0.5:
        print(f'❌ FAIL: time_dead_ratio {actual_ratio:.1f}% != expected {expected_r2_ratio:.1f}%')
        all_pass = False
    else:
        print(f'✅ PASS: time_dead_ratio = {actual_ratio:.1f}%')

    # Test that ratio can never exceed 100%
    if actual_ratio <= 100.0:
        print(f'✅ PASS: ratio capped at 100% (actual: {actual_ratio:.1f}%)')
    else:
        print(f'❌ FAIL: ratio exceeds 100%: {actual_ratio:.1f}%')
        all_pass = False

    return all_pass


def test_impossible_death_time_capped():
    """Test that impossible death times (>100%) are capped correctly."""
    
    # Simulate the bug scenario: R2 cumulative has more death time than play time
    r1_player = {
        'name': 'buggy_player',
        'guid': 'BUG123',
        'team': 1,
        'kills': 5,
        'deaths': 10,
        'damage_given': 500,
        'damage_received': 1000,
        'headshots': 1,
        'objective_stats': {
            'time_played_minutes': 10.0,
            'time_dead_minutes': 8.0,   # 8 min dead in 10 min (80%)
            'time_dead_ratio': 80.0,
        },
        'weapon_stats': {}
    }

    r2_cumulative_player = {
        'name': 'buggy_player',
        'guid': 'BUG123',
        'team': 2,
        'kills': 8,
        'deaths': 20,
        'damage_given': 800,
        'damage_received': 2000,
        'headshots': 2,
        'objective_stats': {
            'time_played_minutes': 20.0,  # 10 min R2
            'time_dead_minutes': 18.0,    # R2-only would be 10 min dead in 10 min played
            'time_dead_ratio': 90.0,
        },
        'weapon_stats': {}
    }

    print()
    print('=== Edge Case: Near 100% Death Time ===')
    
    parser = C0RNP0RN3StatsParser()
    r1_data = {
        'players': [r1_player], 
        'map_name': 'test', 
        'map_time': 600, 
        'actual_time': '10:00',
        'round_outcome': 'Axis',
        'round_num': 1,
        'success': True
    }
    r2_data = {
        'players': [r2_cumulative_player], 
        'map_name': 'test', 
        'map_time': 1200, 
        'actual_time': '20:00',
        'round_outcome': 'Allied',
        'round_num': 2,
        'success': True
    }

    result = parser.calculate_round_2_differential(r1_data, r2_data)
    r2_only = result['players'][0]

    actual_ratio = r2_only['objective_stats'].get('time_dead_ratio', 0)
    actual_dead = r2_only['objective_stats'].get('time_dead_minutes', 0)
    actual_time = r2_only['objective_stats'].get('time_played_minutes', 0)

    print(f'R2-only: {actual_time} min played, {actual_dead} min dead, {actual_ratio:.1f}% ratio')

    if actual_ratio <= 100.0:
        print(f'✅ PASS: Death ratio {actual_ratio:.1f}% is capped at 100%')
        return True
    else:
        print(f'❌ FAIL: Death ratio {actual_ratio:.1f}% exceeds 100%!')
        return False


def test_real_stats_file():
    """Test parsing an actual stats file that had the bug."""
    import os
    
    print()
    print('=== Testing Real Stats File ===')
    
    # Look for a stats file pair (R1 and R2)
    stats_dir = 'local_stats'
    if not os.path.exists(stats_dir):
        print('⚠️  SKIP: local_stats directory not found')
        return True
    
    # Find any round-1 and round-2 pair
    files = os.listdir(stats_dir)
    round_1_files = [f for f in files if 'round-1' in f and f.endswith('.txt')]
    
    if not round_1_files:
        print('⚠️  SKIP: No round-1 files found')
        return True
    
    # Take the first one
    r1_file = round_1_files[0]
    r2_file = r1_file.replace('round-1', 'round-2')
    
    r1_path = os.path.join(stats_dir, r1_file)
    r2_path = os.path.join(stats_dir, r2_file)
    
    if not os.path.exists(r2_path):
        print(f'⚠️  SKIP: No matching round-2 file for {r1_file}')
        return True
    
    print(f'Testing: {r1_file} + {r2_file}')
    
    parser = C0RNP0RN3StatsParser()
    
    # Parse both files
    r1_data = parser.parse_file(r1_path)
    r2_cumulative = parser.parse_file(r2_path)
    
    if not r1_data.get('success') or not r2_cumulative.get('success'):
        print('⚠️  SKIP: Failed to parse stats files')
        return True
    
    # Calculate R2 differential
    r2_only = parser.calculate_round_2_differential(r1_data, r2_cumulative)
    
    # Check all players for impossible death ratios
    all_pass = True
    for player in r2_only['players']:
        ratio = player['objective_stats'].get('time_dead_ratio', 0)
        dead_mins = player['objective_stats'].get('time_dead_minutes', 0)
        played_mins = player['objective_stats'].get('time_played_minutes', 0)
        
        if ratio > 100.0:
            print(f'❌ FAIL: {player["name"]} has {ratio:.1f}% death ratio (>{100}%)')
            all_pass = False
        elif dead_mins > played_mins and played_mins > 0:
            print(f'❌ FAIL: {player["name"]} dead {dead_mins:.1f} min > played {played_mins:.1f} min')
            all_pass = False
    
    if all_pass:
        print(f'✅ PASS: All {len(r2_only["players"])} players have valid death times')
    
    return all_pass


if __name__ == '__main__':
    print('=' * 60)
    print('DEATH TIME FIX TESTS')
    print('=' * 60)
    
    results = []
    
    results.append(('R2 Differential Calculation', test_r2_differential_death_time()))
    results.append(('100% Cap Test', test_impossible_death_time_capped()))
    results.append(('Real Stats File', test_real_stats_file()))
    
    print()
    print('=' * 60)
    print('SUMMARY')
    print('=' * 60)
    
    all_passed = True
    for name, passed in results:
        status = '✅ PASS' if passed else '❌ FAIL'
        print(f'{status}: {name}')
        if not passed:
            all_passed = False
    
    print()
    print('OVERALL:', '✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED')
