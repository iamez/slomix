#!/usr/bin/env python3
"""Check if round differential fix was properly implemented"""

import sqlite3

def check_differential_implementation():
    """Check if the round differential calculator was properly applied"""
    print('🔍 CHECKING ROUND DIFFERENTIAL FIX IMPLEMENTATION:')
    print('=' * 60)

    conn = sqlite3.connect('etlegacy_fixed_bulk.db')
    cursor = conn.cursor()

    # Check database structure
    print('1. 📊 Database Structure Check:')
    cursor.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    tables = [t[0] for t in cursor.fetchall()]
    print(f'   Tables: {tables}')

    # Check rounds table columns
    cursor.execute('PRAGMA table_info(rounds)')
    round_columns = [col[1] for col in cursor.fetchall()]
    print(f'   Rounds table columns: {round_columns}')

    # Find a sample round pair
    print('\n2. 🔍 Sample Round Pair Analysis:')
    print('   Looking for te_escape2 rounds from same session...')

    cursor.execute('''
        SELECT r1.id as r1_id, r2.id as r2_id, r1.map_name, r1.round_number, r2.round_number,
               r1.timestamp as r1_time, r2.timestamp as r2_time
        FROM rounds r1
        JOIN rounds r2 ON r1.session_id = r2.session_id 
        WHERE r1.map_name = r2.map_name 
          AND r1.round_number = 1 
          AND r2.round_number = 2
          AND r1.map_name = 'te_escape2'
        LIMIT 1
    ''')

    pair = cursor.fetchone()
    if pair:
        r1_id, r2_id, map_name, r1_num, r2_num, r1_time, r2_time = pair
        print(f'   Found pair: Round {r1_id} and Round {r2_id} ({map_name})')
        print(f'   Times: {r1_time} -> {r2_time}')
        
        # Check player stats for same player in both rounds
        print('\n3. 🎯 Player Stats Comparison (Same Player, Both Rounds):')
        cursor.execute('''
            SELECT ps1.clean_name_final, 
                   ps1.kills as r1_kills, ps2.kills as r2_kills,
                   ps1.deaths as r1_deaths, ps2.deaths as r2_deaths,
                   ps1.headshots as r1_hs, ps2.headshots as r2_hs
            FROM player_round_stats ps1
            JOIN player_round_stats ps2 ON ps1.player_guid = ps2.player_guid
            WHERE ps1.round_id = ? AND ps2.round_id = ?
            LIMIT 5
        ''', (r1_id, r2_id))
        
        comparisons = cursor.fetchall()
        differential_count = 0
        cumulative_count = 0
        
        for name, r1k, r2k, r1d, r2d, r1hs, r2hs in comparisons:
            print(f'   {name:15s}:')
            print(f'     Round 1: {r1k:2d}K/{r1d:2d}D {r1hs:2d}HS')
            print(f'     Round 2: {r2k:2d}K/{r2d:2d}D {r2hs:2d}HS')
            
            # Check if Round 2 looks like cumulative
            if r2k >= r1k and r2d >= r1d and r2hs >= r1hs and (r2k > 0 or r2d > 0):
                print(f'     ⚠️  Round 2 >= Round 1 (possibly CUMULATIVE - NOT FIXED)')
                cumulative_count += 1
            elif r2k < r1k or r2d < r1d:  # Round 2 is clearly different/lower
                print(f'     ✅ Round 2 appears to be DIFFERENTIAL (FIXED)')
                differential_count += 1
            else:
                print(f'     🤔 Unclear (both rounds might be zero)')
            print()
        
        print(f'   Summary: {differential_count} differential, {cumulative_count} cumulative')
        
        if cumulative_count > differential_count:
            print('   🚨 ISSUE: More cumulative than differential - FIX NOT APPLIED!')
        elif differential_count > 0:
            print('   ✅ GOOD: Differential fix appears to be working')
        else:
            print('   🤔 UNCLEAR: Need more data to determine')
            
    else:
        print('   No round pairs found')

    # Check processing info
    print('\n4. 📝 Processing Information:')
    cursor.execute('SELECT COUNT(*) FROM rounds WHERE round_number = 2')
    round2_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM rounds WHERE round_number = 1')
    round1_count = cursor.fetchone()[0]
    
    print(f'   Round 1 records: {round1_count}')
    print(f'   Round 2 records: {round2_count}')
    print(f'   Ratio: {round2_count/round1_count:.2f} (should be close to 1.0)')

    # Check recent processing
    cursor.execute('''
        SELECT processed_at, COUNT(*) as count
        FROM player_round_stats 
        GROUP BY processed_at 
        ORDER BY processed_at DESC 
        LIMIT 3
    ''')
    processing_times = cursor.fetchall()
    print(f'   Recent processing timestamps:')
    for proc_time, count in processing_times:
        print(f'     {proc_time}: {count} records')

    # Quick cumulative bug test
    print('\n5. 🧪 Quick Cumulative Bug Test:')
    cursor.execute('''
        SELECT ps1.clean_name_final,
               ps1.kills as r1_kills, ps2.kills as r2_kills,
               ps1.deaths as r1_deaths, ps2.deaths as r2_deaths
        FROM player_round_stats ps1
        JOIN player_round_stats ps2 ON ps1.player_guid = ps2.player_guid
        JOIN rounds r1 ON ps1.round_id = r1.id
        JOIN rounds r2 ON ps2.round_id = r2.id
        WHERE r1.session_id = r2.session_id
          AND r1.map_name = r2.map_name
          AND r1.round_number = 1
          AND r2.round_number = 2
          AND ps1.kills > 5
        LIMIT 10
    ''')
    
    tests = cursor.fetchall()
    cumulative_indicators = 0
    differential_indicators = 0
    
    for name, r1k, r2k, r1d, r2d in tests:
        if r2k >= r1k and r2d >= r1d and r2k > 0:
            cumulative_indicators += 1
            print(f'   ⚠️  {name}: R1={r1k}K/{r1d}D, R2={r2k}K/{r2d}D (cumulative?)')
        else:
            differential_indicators += 1
            print(f'   ✅ {name}: R1={r1k}K/{r1d}D, R2={r2k}K/{r2d}D (differential)')
    
    print(f'\n   Test Results: {differential_indicators} differential, {cumulative_indicators} cumulative')
    
    if cumulative_indicators > differential_indicators:
        print('   🚨 CUMULATIVE BUG STILL EXISTS - NEED TO APPLY FIX!')
    else:
        print('   ✅ DIFFERENTIAL FIX APPEARS TO BE WORKING!')

    conn.close()

if __name__ == "__main__":
    check_differential_implementation()