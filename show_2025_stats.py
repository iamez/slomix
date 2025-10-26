#!/usr/bin/env python3
"""Quick 2025 stats summary"""

import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

print('\n' + '=' * 70)
print('🎮 2025 YEAR-TO-DATE STATS SUMMARY')
print('=' * 70)

# Date range and totals
cursor.execute(
    '''
    SELECT MIN(session_date), MAX(session_date),
           COUNT(DISTINCT session_date), COUNT(*)
    FROM sessions
    WHERE session_date LIKE '2025%'
'''
)
row = cursor.fetchone()
print(f'\n📅 DATE RANGE: {row[0]} to {row[1]}')
print(f'📊 TOTAL GAMING DAYS: {row[2]} days')
print(f'🗺️  TOTAL MAPS PLAYED: {row[3] // 2} complete maps')
print(f'🔄 TOTAL ROUNDS: {row[3]} rounds')

# Unique players
cursor.execute(
    '''
    SELECT COUNT(DISTINCT clean_name)
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
'''
)
print(f'👥 UNIQUE PLAYERS: {cursor.fetchone()[0]} players')

# Total playtime
cursor.execute(
    '''
    SELECT SUM(time_played_seconds) / 3600.0
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
'''
)
total_hours = cursor.fetchone()[0]
print(f'⏱️  TOTAL PLAYTIME: {total_hours:,.1f} hours')

# Top 5 most played maps
cursor.execute(
    '''
    SELECT map_name, COUNT(*)/2 as plays
    FROM sessions
    WHERE session_date LIKE '2025%'
    GROUP BY map_name
    ORDER BY plays DESC
    LIMIT 5
'''
)
print(f'\n🏆 TOP 5 MOST PLAYED MAPS:')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f'  {i}. {row[0]:20s} - {int(row[1]):3d} plays')

# Top 10 killers
cursor.execute(
    '''
    SELECT clean_name,
           SUM(kills) as total_kills,
           SUM(deaths) as total_deaths,
           ROUND(CAST(SUM(kills) AS FLOAT) / NULLIF(SUM(deaths), 0), 2) as kd_ratio,
           SUM(damage_given) as total_damage
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
    GROUP BY clean_name
    ORDER BY total_kills DESC
    LIMIT 10
'''
)
print(f'\n⚔️  TOP 10 KILLERS OF 2025:')
for i, row in enumerate(cursor.fetchall(), 1):
    print(
        f'  {
            i:2d}. {
            row[0]:20s} | {
                row[1]:5d} K | {
                    row[2]:5d} D | {
                        row[3]:4.2f} K/D | {
                            row[4]:,} DMG'
    )

# Top 5 by DPM
cursor.execute(
    '''
    SELECT clean_name,
           ROUND((SUM(damage_given) * 60.0) / NULLIF(SUM(time_played_seconds), 0), 1) as dpm,
           SUM(time_played_seconds) / 3600.0 as hours_played
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
    GROUP BY clean_name
    HAVING hours_played >= 10
    ORDER BY dpm DESC
    LIMIT 5
'''
)
print(f'\n💥 TOP 5 BY DAMAGE PER MINUTE (10+ hours):')
for i, row in enumerate(cursor.fetchall(), 1):
    print(f'  {i}. {row[0]:20s} | {row[1]:6.1f} DPM | {row[2]:5.1f} hrs played')

# Most active player
cursor.execute(
    '''
    SELECT clean_name,
           SUM(time_played_seconds) / 3600.0 as hours,
           COUNT(DISTINCT session_id) as sessions_played
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
    GROUP BY clean_name
    ORDER BY hours DESC
    LIMIT 1
'''
)
row = cursor.fetchone()
print(f'\n🏅 MOST ACTIVE PLAYER: {row[0]} ({row[1]:,.1f} hours, {row[2]} sessions)')

# Chaos stats
cursor.execute(
    '''
    SELECT
        SUM(team_kills) as teamkills,
        SUM(self_kills) as selfkills,
        SUM(kill_steals) as steals,
        SUM(useless_kills) as useless
    FROM player_comprehensive_stats
    WHERE session_id IN (SELECT id FROM sessions WHERE session_date LIKE '2025%')
'''
)
row = cursor.fetchone()
print(f'\n💀 CHAOS STATS:')
print(f'  Friendly Fire Kills: {row[0]:,}')
print(f'  Self Destructions: {row[1]:,}')
print(f'  Kill Steals: {row[2]:,}')
print(f'  Useless Kills: {row[3]:,}')

print('\n' + '=' * 70)
print('✨ Use !stats_2025 in Discord for full interactive stats!')
print('=' * 70 + '\n')

conn.close()
