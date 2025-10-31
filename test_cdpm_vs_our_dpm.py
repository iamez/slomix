#!/usr/bin/env python3
"""
COMPREHENSIVE DPM TEST - Show cDPM vs Our DPM
============================================
Tests both c0rnp0rn3.lua's DPM and our factual DPM calculation
"""
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
c = conn.cursor()

# Get latest session
latest_date = c.execute(
    '''
    SELECT DISTINCT session_date
    FROM sessions
    ORDER BY session_date DESC
    LIMIT 1
'''
).fetchone()[0]

print('=' * 100)
print(f'📅 SESSION: {latest_date}')
print('=' * 100)

# Get session-wide stats with BOTH DPM calculations
print('\n🔍 COMPARING cDPM (current) vs Our DPM (factual)\n')

results = c.execute(
    '''
    SELECT
        p.player_name,
        COUNT(*) as rounds,
        SUM(p.damage_given) as total_damage,
        SUM(p.time_played_minutes) as total_time,
        AVG(p.dpm) as avg_cdpm,
        CASE
            WHEN SUM(p.time_played_minutes) > 0
            THEN SUM(p.damage_given) / SUM(p.time_played_minutes)
            ELSE 0
        END as our_dpm
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = ?
    GROUP BY p.player_guid
    HAVING SUM(p.damage_given) > 1000
    ORDER BY our_dpm DESC
    LIMIT 10
''',
    (latest_date,),
).fetchall()

print(
    f'{
        "Player":20} | {
            "Rounds":>6} | {
                "cDPM":>8} | {
                    "Our DPM":>10} | {
                        "Diff":>8} | {
                            "Status":>10}'
)
print('-' * 90)

for name, rounds, total_dmg, total_time, avg_cdpm, our_dpm in results:
    diff_pct = ((our_dpm - avg_cdpm) / avg_cdpm * 100) if avg_cdpm > 0 else 0

    # Determine status
    if abs(diff_pct) < 5:
        status = '✅ Close'
    elif diff_pct > 0:
        status = f'⬆️ +{diff_pct:.1f}%'
    else:
        status = f'⬇️ {diff_pct:.1f}%'

    print(
        f'{
            name:20} | {
            rounds:6} | {
                avg_cdpm:8.2f} | {
                    our_dpm:10.2f} | {
                        diff_pct:7.1f}% | {
                            status:>10}'
    )

print('\n' + '=' * 100)
print('📊 PER-ROUND BREAKDOWN (showing both cDPM and Our DPM)')
print('=' * 100)

# Get per-round data for top player
top_player = results[0][0]
print(f'\n🎯 Player: {top_player}\n')

rounds_data = c.execute(
    '''
    SELECT
        s.map_name,
        s.round_number,
        s.actual_time,
        p.damage_given,
        p.time_played_minutes,
        p.dpm as cdpm,
        CASE
            WHEN p.time_played_minutes > 0
            THEN p.damage_given / p.time_played_minutes
            ELSE 0
        END as our_dpm
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = ? AND p.player_name = ?
    ORDER BY s.map_name, s.round_number
''',
    (latest_date, top_player),
).fetchall()

print(
    f'{
        "Map":20} | {
            "R":>2} | {
                "Time":>6} | {
                    "Damage":>7} | {
                        "Player T":>8} | {
                            "cDPM":>8} | {
                                "Our DPM":>9}'
)
print('-' * 90)

for map_name, rnd, actual_time, damage, player_time, cdpm, our_dpm in rounds_data:
    time_status = '❌' if player_time == 0 else '✅'
    print(
        f'{
            map_name:20} | {
            rnd:2} | {
                actual_time:>6} | {
                    damage:7} | {
                        player_time:7.2f}m | {
                            cdpm:8.2f} | {
                                our_dpm:9.2f} {time_status}'
    )

print('\n' + '=' * 100)
print('💡 KEY INSIGHTS')
print('=' * 100)
print(
    '''
cDPM (Current "DPM" in database):
  - Calculated by parser using SESSION time (e.g., 3:51)
  - Same for ALL players in that round
  - Formula: damage / session_actual_time
  - ❌ Not accurate for players who join late or leave early

Our DPM (Factual):
  - Calculated using PLAYER'S actual time_played_minutes
  - Different for each player
  - Formula: damage / time_played_minutes
  - ✅ Accurate per-player metric
  - ⚠️  Some records have time_played_minutes = 0 (need investigation)

RECOMMENDATION:
  1. Keep cDPM in database (rename column to "cdpm" or "session_dpm")
  2. Add new column "our_dpm" for factual calculation
  3. Bot should primarily display Our DPM
  4. Optionally show both for comparison
'''
)

# Check how many records have time_played = 0
zero_time_count = c.execute(
    '''
    SELECT COUNT(*)
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = ? AND p.time_played_minutes = 0
''',
    (latest_date,),
).fetchone()[0]

total_count = c.execute(
    '''
    SELECT COUNT(*)
    FROM sessions s
    JOIN player_comprehensive_stats p ON s.id = p.session_id
    WHERE s.session_date = ?
''',
    (latest_date,),
).fetchone()[0]

print(
    f'\n⚠️  Records with time_played_minutes = 0: {zero_time_count}/{total_count} ({
        zero_time_count / total_count * 100:.1f}%)'
)
print('   These records CANNOT use Our DPM calculation!')

conn.close()
