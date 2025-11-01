#!/usr/bin/env python3
"""
🔍 COMPREHENSIVE DPM DEBUG
==========================
Shows per-round DPM, session DPM, and traces the entire calculation pipeline
"""

import sqlite3
import sys
from pathlib import Path

from community_stats_parser import C0RNP0RN3StatsParser

# Add bot to path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))


def show_per_round_dpm():
    """Display DPM for each round in the latest session"""
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    # Get latest session date
    latest_date = c.execute(
        'SELECT DISTINCT session_date FROM sessions ORDER BY session_date DESC LIMIT 1'
    ).fetchone()[0]

    print('=' * 100)
    print(f'📅 LATEST SESSION: {latest_date}')
    print('=' * 100)

    # Get all rounds for this session
    rounds = c.execute(
        '''
        SELECT DISTINCT s.map_name, s.round_number, s.actual_time, s.id
        FROM sessions s
        WHERE s.session_date = ?
        ORDER BY s.map_name, s.round_number
    ''',
        (latest_date,),
    ).fetchall()

    print(f'\n📊 FOUND {len(rounds)} ROUNDS:\n')

    for map_name, rnd, actual_time, session_id in rounds:
        print(f'\n{"=" * 100}')
        print(f'🗺️  {map_name} - Round {rnd} (Session Time: {actual_time})')
        print('=' * 100)

        # Get top 10 players for this round
        players = c.execute(
            '''
            SELECT
                p.player_name,
                p.damage_given,
                p.time_played_minutes,
                p.dpm,
                p.kills,
                p.deaths
            FROM player_comprehensive_stats p
            WHERE p.session_id = ?
            ORDER BY p.damage_given DESC
            LIMIT 10
        ''',
            (session_id,),
        ).fetchall()

        header = f"{
            'Player':20} | {
            'Damage':>8} | {
            'Time(min)':>10} | {
                'DPM':>8} | {
                    'K':>3} | {
                        'D':>3}"
        print(f'\n{header}')
        print('-' * 80)

        for name, dmg, time_min, dpm, k, d in players:
            # Verify DPM calculation
            expected_dpm = dmg / time_min if time_min > 0 else 0
            marker = "✅" if abs(dpm - expected_dpm) < 0.1 else "❌"
            print(
                f'{
                    name:20} | {
                    dmg:8.0f} | {
                    time_min:10.2f} | {
                    dpm:8.2f} | {
                        k:3} | {
                            d:3} {marker}'
            )

    conn.close()
    return latest_date


def show_session_dpm_bot_method(session_date):
    """Show how the bot currently calculates DPM (using AVG)"""
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    print('\n\n' + '=' * 100)
    print('🤖 BOT METHOD: AVG(dpm) - Current Implementation')
    print('=' * 100)

    # This is how the bot currently does it
    results = c.execute(
        '''
        SELECT
            p.player_name,
            COUNT(*) as rounds_played,
            AVG(p.dpm) as avg_dpm,
            SUM(p.damage_given) as total_damage,
            SUM(p.kills) as total_kills
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.session_date = ?
        GROUP BY p.player_guid
        HAVING SUM(p.damage_given) > 1000
        ORDER BY avg_dpm DESC
        LIMIT 15
    ''',
        (session_date,),
    ).fetchall()

    print(f"\n{'Player':20} | {'Rounds':>6} | {'Bot DPM':>10} | {'Total Dmg':>10} | {'Kills':>6}")
    print('-' * 80)

    for name, rounds, avg_dpm, total_dmg, kills in results:
        print(f'{name:20} | {rounds:6} | {avg_dpm:10.2f} | {total_dmg:10.0f} | {kills:6}')

    conn.close()


def show_session_dpm_correct_method(session_date):
    """Show the CORRECT DPM calculation (weighted by time)"""
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    print('\n\n' + '=' * 100)
    print('✅ CORRECT METHOD: SUM(damage) / SUM(time_played_minutes)')
    print('=' * 100)

    results = c.execute(
        '''
        SELECT
            p.player_name,
            COUNT(*) as rounds_played,
            SUM(p.damage_given) as total_damage,
            SUM(p.time_played_minutes) as total_time,
            CASE
                WHEN SUM(p.time_played_minutes) > 0
                THEN SUM(p.damage_given) / SUM(p.time_played_minutes)
                ELSE 0
            END as weighted_dpm,
            AVG(p.dpm) as bot_dpm,
            SUM(p.kills) as total_kills
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.session_date = ?
        GROUP BY p.player_guid
        HAVING SUM(p.damage_given) > 1000
        ORDER BY weighted_dpm DESC
        LIMIT 15
    ''',
        (session_date,),
    ).fetchall()

    print(
        f"\n{
            'Player':20} | {
            'Rounds':>6} | {
                'Correct DPM':>11} | {
                    'Bot DPM':>10} | {
                        'Diff %':>8} | {
                            'Total Time':>11}"
    )
    print('-' * 110)

    for name, rounds, total_dmg, total_time, weighted_dpm, bot_dpm, kills in results:
        diff_pct = ((weighted_dpm - bot_dpm) / bot_dpm * 100) if bot_dpm > 0 else 0
        marker = "❌" if abs(diff_pct) > 5 else "✅"
        print(
            f'{
                name:20} | {
                rounds:6} | {
                weighted_dpm:11.2f} | {
                    bot_dpm:10.2f} | {
                        diff_pct:7.1f}% | {
                            total_time:11.2f} {marker}'
        )

    conn.close()


def trace_calculation_pipeline(session_date):
    """Trace how DPM flows from stats file -> parser -> database -> bot"""
    print('\n\n' + '=' * 100)
    print('🔍 DPM CALCULATION PIPELINE TRACE')
    print('=' * 100)

    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    # Get a sample stats file from this session
    sample_file = c.execute(
        '''
        SELECT filename FROM sessions
        WHERE session_date = ?
        LIMIT 1
    ''',
        (session_date,),
    ).fetchone()

    if not sample_file:
        print("❌ No files found for this session")
        conn.close()
        return

    filename = sample_file[0]
    filepath = Path('local_stats') / filename

    print(f'\n📄 Sample File: {filename}')

    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        conn.close()
        return

    # Parse the file
    parser = C0RNP0RN3StatsParser()
    result = parser.parse_file(str(filepath))

    if not result:
        print("❌ Parse failed")
        conn.close()
        return

    print(f'\n✅ Parsed successfully!')
    print(f'   Players found: {len(result["players"])}')

    # Show sample player data flow
    sample_player = list(result['players'].items())[0]
    guid, player_data = sample_player

    print(f'\n👤 Sample Player: {player_data["name"]}')
    print(f'   GUID: {guid}')
    print(f'\n   📊 FROM STATS FILE (via parser):')
    print(f'      Damage: {player_data.get("damage_given", 0)}')
    print(f'      DPM: {player_data.get("dpm", 0):.2f}')
    print(
        f'      Time Played: {
            player_data.get(
                "objective_stats",
                {}).get(
                "time_played_minutes",
                0):.2f} min'
    )

    # Get from database
    db_data = c.execute(
        '''
        SELECT
            p.damage_given,
            p.dpm,
            p.time_played_minutes
        FROM sessions s
        JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.filename = ? AND p.player_guid = ?
    ''',
        (filename, guid),
    ).fetchone()

    if db_data:
        print(f'\n   💾 FROM DATABASE:')
        print(f'      Damage: {db_data[0]}')
        print(f'      DPM: {db_data[1]:.2f}')
        print(f'      Time Played: {db_data[2]:.2f} min')

        # Verify match
        if abs(player_data.get("damage_given", 0) - db_data[0]) < 1:
            print(f'\n   ✅ Data matches between parser and database!')
        else:
            print(f'\n   ❌ Data MISMATCH between parser and database!')

    conn.close()


def review_database_schema():
    """Review database structure vs what c0rnp0rn3.lua provides"""
    print('\n\n' + '=' * 100)
    print('🗄️  DATABASE SCHEMA REVIEW')
    print('=' * 100)

    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()

    tables = {
        'player_comprehensive_stats': 'Main player stats',
        'player_objective_stats': 'Objective/support stats',
        'weapon_comprehensive_stats': 'Weapon performance',
    }

    for table_name, description in tables.items():
        print(f'\n📋 {table_name.upper()} - {description}')
        print('-' * 100)

        cols = c.execute(f'PRAGMA table_info({table_name})').fetchall()

        for col in cols:
            col_name = col[1]
            col_type = col[2]
            not_null = " NOT NULL" if col[3] else ""
            default = f" DEFAULT {col[4]}" if col[4] else ""
            print(f'   {col_name:30} {col_type:10}{not_null}{default}')

    # Check what c0rnp0rn3.lua provides
    print('\n\n📜 WHAT C0RNP0RN3.LUA PROVIDES:')
    print('-' * 100)
    print(
        '''
From the stats file format, c0rnp0rn3.lua provides these fields per player:

TAB-SEPARATED SECTION (37+ fields):
  0. guid
  1. name
  2. team (Axis/Allies)
  3. kills
  4. deaths
  5. suicides
  6. team_kills
  7. team_damage
  8. damage_given
  9. damage_received
  10. damage_team
  11. hits
  12. shots (bullets fired)
  13. headshots
  14. kills_obj
  15. deaths_obj
  16. K/D ratio
  17. efficiency
  18. DPM ⭐ (calculated by lua)
  19. medal
  20. medals_won
  21. DPM again (duplicate?)
  22. time_played_minutes ⭐ (actual playtime)
  23. killing_spree_best
  24. death_spree_worst
  25. kill_assists
  26. kill_steals
  27. objectives_stolen
  28. objectives_returned
  29. dynamites_planted
  30. dynamites_defused
  31. times_revived
  32. bullets_fired (duplicate of 12?)
  33. tank_meatshield_score
  34. time_dead_ratio
  35. time_dead_minutes
  36. useful_kills
  37. useless_kills
  38. denied_playtime_seconds
  39. full_selfkills
  40. repairs_constructions
  41-46. multikill_2x through multikill_6x

WEAPON SECTION (per weapon):
  - weapon_id
  - kills
  - deaths
  - headshots
  - hits
  - shots
  - damage
  - pickups
  - drops
  - accuracy %
  - efficiency %
    '''
    )

    # Check for missing fields
    print('\n\n🔍 FIELD COVERAGE CHECK:')
    print('-' * 100)

    # Check if time_played_minutes exists
    has_time = c.execute(
        '''
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE time_played_minutes > 0
    '''
    ).fetchone()[0]

    total = c.execute('SELECT COUNT(*) FROM player_comprehensive_stats').fetchone()[0]

    print(f'✅ time_played_minutes field: EXISTS')
    print(f'   Records with time > 0: {has_time:,} / {total:,} ({has_time / total * 100:.1f}%)')

    # Check objective stats table
    obj_count = c.execute('SELECT COUNT(*) FROM player_objective_stats').fetchone()[0]
    print(f'\n✅ player_objective_stats table: EXISTS')
    print(f'   Records: {obj_count:,}')

    # Check weapon stats
    weapon_count = c.execute('SELECT COUNT(*) FROM weapon_comprehensive_stats').fetchone()[0]
    print(f'\n✅ weapon_comprehensive_stats table: EXISTS')
    print(f'   Records: {weapon_count:,}')

    conn.close()


if __name__ == '__main__':
    print('\n🎯 COMPREHENSIVE DPM DEBUG SESSION\n')

    # 1. Show per-round DPM
    session_date = show_per_round_dpm()

    # 2. Show bot's current method (AVG)
    show_session_dpm_bot_method(session_date)

    # 3. Show correct method (weighted)
    show_session_dpm_correct_method(session_date)

    # 4. Trace pipeline
    trace_calculation_pipeline(session_date)

    # 5. Review schema
    review_database_schema()

    print('\n\n' + '=' * 100)
    print('✅ DEBUG SESSION COMPLETE')
    print('=' * 100)
