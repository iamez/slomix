"""
Analyze October 2nd Data in Production Database
Compare with raw files to verify SuperBoyy's graphs
"""

import os
import sqlite3

# Use absolute path to avoid confusion
workspace_root = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(workspace_root, "bot", "bot", "etlegacy_production.db")


def analyze_october_2nd():
    """Analyze October 2nd session data"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    print("=" * 80)
    print("📊 OCTOBER 2ND DATA ANALYSIS")
    print("=" * 80)
    print()

    # Get October 2nd overview
    query = """
        SELECT
            COUNT(DISTINCT map_name) as maps,
            COUNT(DISTINCT player_guid) as players,
            COUNT(*) as total_records,
            SUM(CASE WHEN time_played_seconds > 0 THEN 1 ELSE 0 END) as with_time,
            SUM(CASE WHEN time_played_seconds = 0 THEN 1 ELSE 0 END) as without_time
        FROM player_comprehensive_stats
        WHERE session_date LIKE '2025-10-02%'
    """

    c.execute(query)
    result = c.fetchone()

    if not result or result[2] == 0:
        print("❌ No October 2nd data found in database!")
        print()
        print("This means the database doesn't have the October 2nd session yet.")
        print("The raw files are attached to this conversation, but they haven't been imported.")
        conn.close()
        return

    maps, players, total, with_time, without_time = result

    print(f"📅 Date: 2025-10-02")
    print(f"🗺️  Maps Played: {maps}")
    print(f"👥 Players: {players}")
    print(f"📝 Total Records: {total}")
    print(f"✅ Records with time > 0: {with_time} ({with_time / total * 100:.1f}%)")
    print(f"❌ Records with time = 0: {without_time} ({without_time / total * 100:.1f}%)")
    print()

    # Get vid's stats
    print("=" * 80)
    print("👤 VID'S OCTOBER 2ND STATS")
    print("=" * 80)
    print()

    vid_query = """
        SELECT
            map_name,
            round_number,
            kills,
            deaths,
            damage_given,
            time_played_seconds,
            time_display,
            dpm
        FROM player_comprehensive_stats
        WHERE session_date LIKE '2025-10-02%'
        AND (clean_name LIKE '%vid%' OR player_name LIKE '%vid%')
        ORDER BY id
    """

    c.execute(vid_query)
    vid_records = c.fetchall()

    if not vid_records:
        print("❌ No records found for vid")
        conn.close()
        return

    print(f"{'Map':<20} {'R':<3} {'K':<4} {'D':<4} {'Damage':<8} {'Time':<8} {'DPM':<8}")
    print("-" * 80)

    total_damage = 0
    total_seconds = 0
    total_kills = 0
    total_deaths = 0

    for record in vid_records:
        map_name, round_num, kills, deaths, damage, seconds, time_display, dpm = record
        print(
            f"{
                map_name:<20} {
                round_num:<3} {
                kills:<4} {
                    deaths:<4} {
                        damage:<8} {
                            time_display:<8} {
                                dpm:<8.2f}"
        )

        total_damage += damage
        total_seconds += seconds
        total_kills += kills
        total_deaths += deaths

    print("-" * 80)

    # Calculate weighted DPM
    weighted_dpm = (total_damage * 60) / total_seconds if total_seconds > 0 else 0

    minutes = total_seconds // 60
    seconds_remainder = total_seconds % 60
    total_time_display = f"{minutes}:{seconds_remainder:02d}"

    print(
        f"{
            'TOTALS':<20} {
            '':<3} {
                total_kills:<4} {
                    total_deaths:<4} {
                        total_damage:<8} {
                            total_time_display:<8} {
                                weighted_dpm:<8.2f}"
    )
    print()

    print("=" * 80)
    print("📈 COMPARISON WITH SUPERBOYY'S GRAPHS")
    print("=" * 80)
    print()
    print(f"Our Data:")
    print(f"  Total Rounds: {len(vid_records)}")
    print(f"  Total Kills: {total_kills}")
    print(f"  Total Damage: {total_damage:,}")
    print(f"  Total Time: {total_time_display} ({total_seconds} seconds)")
    print(f"  Weighted DPM: {weighted_dpm:.2f}")
    print()
    print("SuperBoyy's Graphs:")
    print("  (Please describe what you see in SuperBoyy's images)")
    print()
    print("🎯 If the difference is minimal (1-2%), this confirms:")
    print("   1. Our parser reads correct time from files")
    print("   2. Our weighted DPM calculation is correct")
    print("   3. The small difference is likely rounding or in-game display vs file time")

    conn.close()


if __name__ == '__main__':
    analyze_october_2nd()
