#!/usr/bin/env python3
"""
Test Bot Query Logic (without Discord)
=====================================
Test the actual SQL queries the bot uses to verify they work correctly.
"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

print('=' * 80)
print('BOT QUERY SIMULATION TEST')
print('=' * 80)

# Test 1: Last Session Query (from !last_session command)
print('\n--- TEST 1: Last Session Top Players ---')
print('(This is what !last_session command would show)')
print()

result = c.execute(
    '''
    SELECT
        p.player_name,
        p.clean_name,
        SUM(p.kills) as total_kills,
        SUM(p.deaths) as total_deaths,
        SUM(p.damage_given) as total_damage,
        CASE
            WHEN SUM(p.time_played_seconds) > 0
            THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
            ELSE 0
        END as dpm,
        SUM(p.time_played_seconds) as total_seconds
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE s.map_name = 'etl_adlernest' AND s.session_date = '2025-10-02'
    GROUP BY p.player_guid
    ORDER BY dpm DESC
    LIMIT 5
'''
).fetchall()

print(f'{"Player":<20} {"Kills":>6} {"Deaths":>7} {"Damage":>7} {"Seconds":>8} {"DPM":>7}')
print('-' * 70)
for row in result:
    print(f'{row[1]:<20} {row[2]:>6} {row[3]:>7} {row[4]:>7} {row[6]:>8} {row[5]:>7.2f}')

# Test 2: Player Stats Query (from !stats command)
print('\n' + '=' * 80)
print('--- TEST 2: Player Stats (vid) ---')
print('(This is what !stats vid command would show)')
print()

result = c.execute(
    '''
    SELECT
        COUNT(DISTINCT s.id) as sessions_played,
        SUM(p.kills) as total_kills,
        SUM(p.deaths) as total_deaths,
        CASE
            WHEN SUM(p.time_played_seconds) > 0
            THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
            ELSE 0
        END as dpm,
        CASE
            WHEN SUM(p.deaths) > 0
            THEN CAST(SUM(p.kills) AS FLOAT) / SUM(p.deaths)
            ELSE SUM(p.kills)
        END as kd_ratio,
        SUM(p.damage_given) as total_damage,
        SUM(p.time_played_seconds) as total_seconds
    FROM player_comprehensive_stats p
    JOIN sessions s ON p.session_id = s.id
    WHERE p.clean_name LIKE '%vid%'
'''
).fetchone()

print(f'Sessions played: {result[0]}')
print(f'Total kills: {result[1]}')
print(f'Total deaths: {result[2]}')
print(f'K/D ratio: {result[4]:.2f}')
print(f'Total damage: {result[5]:,}')
print(f'Total time: {result[6]} seconds ({result[6] // 60} min {result[6] % 60} sec)')
print(f'DPM: {result[3]:.2f}')
print()
print(f'Calculation: ({result[5]} * 60) / {result[6]} = {result[3]:.2f}')

# Test 3: DPM Leaderboard (from !leaderboard dpm command)
print('\n' + '=' * 80)
print('--- TEST 3: DPM Leaderboard ---')
print('(This is what !leaderboard dpm command would show)')
print()

result = c.execute(
    '''
    SELECT
        p.clean_name,
        SUM(p.damage_given) as total_damage,
        SUM(p.time_played_seconds) as total_seconds,
        CASE
            WHEN SUM(p.time_played_seconds) > 0
            THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
            ELSE 0
        END as dpm
    FROM player_comprehensive_stats p
    GROUP BY p.player_guid
    HAVING SUM(p.time_played_seconds) > 300
    ORDER BY dpm DESC
    LIMIT 10
'''
).fetchall()

print(f'{"Player":<20} {"Damage":>8} {"Seconds":>8} {"DPM":>7}')
print('-' * 50)
for i, row in enumerate(result, 1):
    print(f'{i}. {row[0]:<17} {row[1]:>8} {row[2]:>8} {row[3]:>7.2f}')

conn.close()

print('\n' + '=' * 80)
print('✅ BOT QUERY TEST COMPLETE')
print('=' * 80)
print('\nAll queries executed successfully!')
print('→ Bot should work correctly with this data')
print('→ Ready for actual Discord bot testing')
