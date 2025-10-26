"""
Test script to simulate Discord bot !last_session command
Tests with October 2nd, 2025 data (the most recent session)
"""

import sqlite3

DB_PATH = 'bot/bot/etlegacy_production.db'


def test_last_session():
    """Simulate the !last_session command"""

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    print("🎮 TESTING !last_session COMMAND (October 2nd, 2025)")
    print("=" * 80)

    # Get the most recent date
    cursor.execute(
        '''
        SELECT DISTINCT session_date as date
        FROM sessions
        ORDER BY date DESC
        LIMIT 1
    '''
    )
    result = cursor.fetchone()

    if not result:
        print("❌ No sessions found in database")
        return

    latest_date = result[0]
    print(f"\n📅 Latest Session Date: {latest_date}")

    # Get all session IDs for this date
    cursor.execute(
        '''
        SELECT id, map_name, round_number, time_limit
        FROM sessions
        WHERE session_date = ?
        ORDER BY session_date
    ''',
        (latest_date,),
    )
    sessions = cursor.fetchall()

    print(f"📊 Total Rounds: {len(sessions)}")
    print(f"\n🗺️  Maps Played:")
    for session_id, map_name, round_num, time_limit in sessions[:5]:
        print(f"   - {map_name} R{round_num} (limit: {time_limit})")
    if len(sessions) > 5:
        print(f"   ... and {len(sessions) - 5} more rounds")

    session_ids = [s[0] for s in sessions]

    # Get unique player count
    placeholders = ','.join('?' * len(session_ids))
    query = f'''
        SELECT COUNT(DISTINCT player_guid)
        FROM player_comprehensive_stats
        WHERE session_id IN ({placeholders})
    '''
    cursor.execute(query, session_ids)
    player_count = cursor.fetchone()[0]
    print(f"\n👥 Total Players: {player_count}")

    # Get top 5 players with WEIGHTED DPM
    query = f'''
        SELECT p.player_name,
               SUM(p.kills) as kills,
               SUM(p.deaths) as deaths,
               CASE
                   WHEN SUM(p.time_played_seconds) > 0
                   THEN (SUM(p.damage_given) * 60.0) / SUM(p.time_played_seconds)
                   ELSE 0
               END as weighted_dpm,
               SUM(p.damage_given) as total_damage,
               SUM(p.time_played_seconds) as total_seconds,
               COALESCE(SUM(w.headshots), 0) as total_headshots
        FROM player_comprehensive_stats p
        LEFT JOIN (
            SELECT session_id, player_guid,
                   SUM(headshots) as headshots
            FROM weapon_comprehensive_stats
            GROUP BY session_id, player_guid
        ) w ON p.session_id = w.session_id AND p.player_guid = w.player_guid
        WHERE p.session_id IN ({placeholders})
        GROUP BY p.player_name
        ORDER BY kills DESC
        LIMIT 10
    '''
    cursor.execute(query, session_ids)
    top_players = cursor.fetchall()

    print(f"\n🏆 TOP PLAYERS (by kills):")
    print(
        f"{'Player':<25} {'Kills':>6} {'Deaths':>6} {'K/D':>6} {'DPM':>7} {'Dmg':>8} {'Time':>8} {'HS':>5}"
    )
    print("-" * 88)

    for (
        player_name,
        kills,
        deaths,
        weighted_dpm,
        total_damage,
        total_seconds,
        headshots,
    ) in top_players:
        kd = kills / deaths if deaths > 0 else kills
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        time_str = f"{minutes}:{seconds:02d}"

        print(
            f"{
                player_name:<25} {
                kills:>6} {
                deaths:>6} {
                    kd:>6.2f} {
                        weighted_dpm:>7.1f} {
                            total_damage:>8} {
                                time_str:>8} {
                                    headshots:>5}"
        )

    # Show specific vid stats for verification
    print(f"\n" + "=" * 80)
    print("🔍 DETAILED VERIFICATION - vid's Stats:")
    print("=" * 80)

    query = f'''
        SELECT p.map_name, p.round_number, p.kills, p.deaths,
               p.damage_given, p.time_played_seconds, p.time_display, p.dpm,
               (p.damage_given * 60.0) / p.time_played_seconds as calculated_dpm
        FROM player_comprehensive_stats p
        JOIN sessions s ON p.session_id = s.id
        WHERE s.session_date = ? AND p.player_name = 'vid'
        ORDER BY s.session_date, p.map_name, p.round_number
    '''
    cursor.execute(query, (latest_date,))
    vid_rounds = cursor.fetchall()

    total_kills = 0
    total_deaths = 0
    total_damage = 0
    total_time = 0

    print(
        f"\n{
            'Map':<20} {
            'R':>2} {
                'K':>3} {
                    'D':>3} {
                        'Damage':>7} {
                            'Time':>8} {
                                'Stored DPM':>11} {
                                    'Calc DPM':>10}"
    )
    print("-" * 80)

    for (
        map_name,
        round_num,
        kills,
        deaths,
        damage,
        time_sec,
        time_display,
        stored_dpm,
        calc_dpm,
    ) in vid_rounds:
        total_kills += kills
        total_deaths += deaths
        total_damage += damage
        total_time += time_sec

        print(
            f"{
                map_name:<20} {
                round_num:>2} {
                kills:>3} {
                    deaths:>3} {
                        damage:>7} {
                            time_display:>8} {
                                stored_dpm:>11.2f} {
                                    calc_dpm:>10.2f}"
        )

    # Calculate overall weighted DPM
    weighted_dpm = (total_damage * 60.0) / total_time if total_time > 0 else 0
    overall_kd = total_kills / total_deaths if total_deaths > 0 else total_kills
    total_minutes = total_time // 60
    total_seconds_rem = total_time % 60

    print("-" * 80)
    print(
        f"{
            'TOTALS:':<20} {
            '':>2} {
                total_kills:>3} {
                    total_deaths:>3} {
                        total_damage:>7} {total_minutes}:{
                            total_seconds_rem:02d}"
    )
    print(f"\n📊 WEIGHTED DPM (correct): {weighted_dpm:.2f}")
    print(f"📊 K/D Ratio: {overall_kd:.2f}")
    print(f"⏱️  Total Time: {total_minutes}:{total_seconds_rem:02d} ({total_time} seconds)")

    # Compare with simple average (the WRONG way)
    avg_dpm_wrong = sum(stored_dpm for _, _, _, _, _, _, _, stored_dpm, _ in vid_rounds) / len(
        vid_rounds
    )
    print(f"\n⚠️  Simple AVG(dpm) (WRONG): {avg_dpm_wrong:.2f}")
    print(f"✅ Weighted DPM (RIGHT): {weighted_dpm:.2f}")
    print(f"📈 Difference: {weighted_dpm - avg_dpm_wrong:+.2f} DPM")

    conn.close()

    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    test_last_session()
