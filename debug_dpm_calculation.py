#!/usr/bin/env python3
"""
🔍 DEBUG DPM CALCULATION
========================
This script shows EXACTLY how DPM values are calculated throughout the pipeline:
1. From c0rnp0rn3.lua stats file (field 21 in TAB-separated data)
2. Through parser (community_stats_parser.py)
3. Into database (bulk_import_stats.py)
4. In Discord bot queries (!last_session command)

Goal: Understand why we get the DPM values we see in Discord
"""

import sqlite3
import sys
from pathlib import Path

from community_stats_parser import C0RNP0RN3StatsParser

# Add bot directory to path
sys.path.insert(0, str(Path(__file__).parent / 'bot'))


def parse_time_to_seconds(time_str: str) -> int:
    """Convert MM:SS format to total seconds"""
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        return int(time_str)
    except BaseException:
        return 0


def debug_dpm_for_latest_session():
    """Debug DPM calculation for the most recent session"""

    print("=" * 80)
    print("🔍 DPM CALCULATION DEBUG - FULL PIPELINE ANALYSIS")
    print("=" * 80)

    db_path = 'etlegacy_production.db'

    # Step 1: Get latest session
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        '''
        SELECT DISTINCT session_date
        FROM sessions
        ORDER BY session_date DESC
        LIMIT 1
    '''
    )
    latest_date = cursor.fetchone()[0]

    print(f"\n📅 Latest Session Date: {latest_date}")
    print("-" * 80)

    # Get all sessions for this date
    cursor.execute(
        '''
        SELECT id, map_name, round_number, time_limit, actual_time
        FROM sessions
        WHERE session_date = ?
        ORDER BY map_name, round_number
    ''',
        (latest_date,),
    )
    sessions = cursor.fetchall()

    print(f"\n📊 Sessions Found: {len(sessions)}")
    for session in sessions:
        sid, map_name, round_num, time_limit, actual_time = session
        print(
            f"  Session {sid}: {map_name} Round {round_num} - Time: {time_limit} (actual: {actual_time})")

    session_ids = [s[0] for s in sessions]
    session_ids_str = ','.join('?' * len(session_ids))

    # Step 2: Get player stats from database
    print(f"\n" + "=" * 80)
    print("💾 DATABASE VALUES (Raw from player_comprehensive_stats)")
    print("=" * 80)

    query = f'''
        SELECT
            p.player_name,
            p.session_id,
            s.map_name,
            s.round_number,
            s.time_limit,
            s.actual_time,
            p.kills,
            p.deaths,
            p.damage_given,
            p.dpm
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE p.session_id IN ({session_ids_str})
        ORDER BY p.player_name, s.map_name, s.round_number
    '''

    cursor.execute(query, session_ids)
    db_stats = cursor.fetchall()

    # Group by player
    player_data = {}
    for row in db_stats:
        name, sid, map_name, round_num, time_limit, actual_time, kills, deaths, dmg, dpm = row

        if name not in player_data:
            player_data[name] = []

        player_data[name].append(
            {
                'session_id': sid,
                'map': map_name,
                'round': round_num,
                'time_limit': time_limit,
                'actual_time': actual_time,
                'kills': kills,
                'deaths': deaths,
                'damage': dmg,
                'dpm': dpm,
            }
        )

    # Show per-player breakdown
    for player_name in sorted(player_data.keys()):
        print(f"\n👤 Player: {player_name}")
        print("   " + "-" * 76)

        rounds = player_data[player_name]
        total_damage = 0
        total_time_seconds = 0

        for r in rounds:
            # Calculate actual playtime for this round
            actual_seconds = parse_time_to_seconds(r['actual_time'])
            total_time_seconds += actual_seconds
            total_damage += r['damage']

            print(f"   Session {r['session_id']}: {r['map']} R{r['round']}")
            print(f"      Time: {r['time_limit']} (actual: {r['actual_time']} = {actual_seconds}s)")
            print(f"      Stats: {r['kills']}K/{r['deaths']}D, {r['damage']} DMG")
            print(f"      DPM in DB: {r['dpm']:.2f}")
            print(
                f"      ✅ Verification: {
                    r['damage']} dmg ÷ {actual_seconds}s × 60 = {
                    (
                        r['damage'] /
                        actual_seconds *
                        60) if actual_seconds > 0 else 0:.2f} DPM"
            )
            print()

        # Calculate aggregated DPM (how bot calculates it)
        print(f"   📊 AGGREGATED STATS (Bot Calculation):")
        print(f"      Total Rounds: {len(rounds)}")
        print(f"      Total Damage: {total_damage:,}")
        print(f"      Total Time: {total_time_seconds}s ({total_time_seconds / 60:.1f} minutes)")

        # Bot uses AVG(dpm) from database
        avg_dpm_from_db = sum(r['dpm'] for r in rounds) / len(rounds)
        print(f"      AVG(dpm) from DB: {avg_dpm_from_db:.2f}")

        # Manual calculation (what it SHOULD be)
        manual_dpm = (total_damage / total_time_seconds * 60) if total_time_seconds > 0 else 0
        print(f"      Manual DPM Calculation: {manual_dpm:.2f}")
        print(f"      Difference: {abs(avg_dpm_from_db - manual_dpm):.2f}")
        print()

    # Step 3: Show bot query logic
    print("\n" + "=" * 80)
    print("🤖 BOT QUERY LOGIC (!last_session command)")
    print("=" * 80)

    print("\nThe bot uses this query for top players:")
    print(
        f"""
    SELECT p.player_name,
           SUM(p.kills) as kills,
           SUM(p.deaths) as deaths,
           AVG(p.dpm) as dpm,           ← ⚠️ AVERAGES the per-round DPM values
           ... other stats ...
    FROM player_comprehensive_stats p
    WHERE p.session_id IN ({session_ids_str})
    GROUP BY p.player_name
    ORDER BY kills DESC
    """
    )

    query = f'''
        SELECT
            p.player_name,
            SUM(p.kills) as total_kills,
            SUM(p.deaths) as total_deaths,
            AVG(p.dpm) as avg_dpm,
            SUM(p.damage_given) as total_damage
        FROM player_comprehensive_stats p
        WHERE p.session_id IN ({session_ids_str})
        GROUP BY p.player_name
        ORDER BY total_kills DESC
        LIMIT 5
    '''

    cursor.execute(query, session_ids)
    top_players = cursor.fetchall()

    print("\n📊 BOT RESULTS (Top 5 by Kills):")
    print("-" * 80)
    for i, (name, kills, deaths, avg_dpm, total_dmg) in enumerate(top_players, 1):
        kd = kills / deaths if deaths > 0 else kills
        print(f"\n{i}. {name}")
        print(f"   Kills/Deaths: {kills}/{deaths} (K/D: {kd:.2f})")
        print(f"   Total Damage: {total_dmg:,}")
        print(f"   AVG(dpm): {avg_dpm:.2f}  ← This is what shows in Discord")

    # Step 4: Find original stats files
    print("\n" + "=" * 80)
    print("📄 ORIGINAL STATS FILES (Source of Truth)")
    print("=" * 80)

    from pathlib import Path

    stats_dir = Path('local_stats')

    # Find files for this date
    date_files = list(stats_dir.glob(f"{latest_date.replace('-', '')}*.txt"))

    if date_files:
        print(f"\n✅ Found {len(date_files)} stats files for {latest_date}")

        # Parse first file to show raw DPM value
        parser = C0RNP0RN3StatsParser()

        print("\nSample file analysis:")
        for file_path in sorted(date_files)[:3]:  # Show first 3 files
            print(f"\n📝 File: {file_path.name}")

            # Read raw file
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            if len(lines) < 2:
                print("   ⚠️ File too short")
                continue

            # Parse header
            header_parts = lines[0].strip().split('\\')
            map_name = header_parts[2] if len(header_parts) > 2 else 'Unknown'
            actual_time = header_parts[5] if len(header_parts) > 5 else '0:00'
            round_num = int(header_parts[7]) if len(header_parts) > 7 else 1

            print(f"   Map: {map_name} Round {round_num}")
            print(f"   Actual Time: {actual_time}")

            # Parse file with parser
            result = parser.parse_stats_file(str(file_path))

            if result['success'] and result['players']:
                print(f"   Players: {len(result['players'])}")

                # Show top 3 players DPM calculation
                sorted_players = sorted(
                    result['players'], key=lambda x: x.get('dpm', 0), reverse=True
                )[:3]

                for p in sorted_players:
                    name = p['name']
                    damage = p.get('damage_given', 0)
                    dpm_from_file = p.get('dpm', 0)

                    # DPM is field 21 in TAB-separated data (comes directly from c0rnp0rn3.lua)
                    print(f"      {name}: {damage} damage, DPM = {dpm_from_file:.2f} (from lua)")
    else:
        print(f"\n❌ No stats files found for {latest_date}")
        print(f"   Looking in: {stats_dir.absolute()}")

    # Step 5: Explanation
    print("\n" + "=" * 80)
    print("💡 DPM CALCULATION EXPLAINED")
    print("=" * 80)
    print(
        """
DPM (Damage Per Minute) flows through this pipeline:

1️⃣  C0RNP0RN3.LUA (Game Server)
    - Calculates: damage_given ÷ time_played_minutes
    - Stored as field 21 in TAB-separated stats
    - This is PER-ROUND data

2️⃣  PARSER (community_stats_parser.py)
    - Reads field 21 from stats file
    - Line 672: dpm = float(tab_fields[21])
    - No calculation, just extracts raw value

3️⃣  DATABASE (bulk_import_stats.py)
    - Stores parsed DPM in player_comprehensive_stats.dpm column
    - Each round gets its own session_id
    - Each player gets one row per session (per round)

4️⃣  BOT (!last_session command)
    - Query: AVG(p.dpm) as avg_dpm
    - Groups by player_name across multiple sessions
    - Averages the per-round DPM values

⚠️  IMPORTANT: The bot uses AVG(dpm) which averages per-round DPM values.
    This is mathematically correct when rounds have similar playtime.

    Alternative would be: SUM(damage) ÷ SUM(time) × 60
    But we'd need time_played_minutes in database (currently not stored).

✅  CONCLUSION: DPM shown in Discord = Average of per-round DPM values
"""
    )

    conn.close()


if __name__ == "__main__":
    debug_dpm_for_latest_session()
