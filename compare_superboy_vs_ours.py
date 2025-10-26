"""
Compare SuperBoyy's October 2nd Stats vs Our Database
Analyze where we might have gone wrong with stats/time/math
"""

import sqlite3

DB_PATH = "bot/bot/etlegacy_production.db"

# SuperBoyy's data from graphs
SUPERBOY_DATA = {
    'SuperBoyy': {'dpm': 315, 'damage': 36000, 'kills': 166},
    'vid': {'dpm': 284, 'damage': 33000, 'kills': 183},
    '.lgz / SmetarskiProner': {'dpm': 273, 'damage': 31000, 'kills': 163},
    '.oly / olympus': {'dpm': 273, 'damage': 31000, 'kills': 146},
    'endekk': {'dpm': 241, 'damage': 28000, 'kills': 149},
    'qmr': {'dpm': 230, 'damage': 26000, 'kills': 121},
}


def get_our_data():
    """Get our October 2nd data from database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = """
        SELECT
            player_name,
            clean_name,
            SUM(damage_given) as total_damage,
            SUM(kills) as total_kills,
            SUM(time_played_seconds) as total_seconds,
            COUNT(*) as rounds,
            CASE
                WHEN SUM(time_played_seconds) > 0
                THEN (SUM(damage_given) * 60.0) / SUM(time_played_seconds)
                ELSE 0
            END as weighted_dpm
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02'
        GROUP BY player_guid
        ORDER BY total_damage DESC
    """

    c.execute(query)
    results = c.fetchall()
    conn.close()

    return results


def calculate_expected_time(damage, dpm):
    """Calculate what time SHOULD be given damage and DPM"""
    # DPM = (damage * 60) / seconds
    # seconds = (damage * 60) / DPM
    seconds = (damage * 60) / dpm
    minutes = seconds / 60
    return seconds, minutes


def analyze_discrepancies():
    """Compare SuperBoyy's data with ours"""
    print("=" * 100)
    print("🔍 SUPERBOY vs OUR DATA - October 2nd 2025")
    print("=" * 100)
    print()

    our_data = get_our_data()

    if not our_data:
        print("❌ No October 2nd data in our database!")
        print()
        print("The database has 16,946 total records but no October 2nd session.")
        print("This means October 2nd files need to be imported first.")
        return

    print(
        f"{
            'Player':<20} | {
            'Our DMG':<10} | {
                'SB DMG':<10} | {
                    'DMG Diff':<10} | {
                        'Our K':<8} | {
                            'SB K':<8} | {
                                'K Diff':<8}"
    )
    print("-" * 100)

    player_mapping = {
        'vid': 'vid',
        'SuperBoyy': 'SuperBoyy',
        'SmetarskiProner': '.lgz / SmetarskiProner',
        '.olz': '.oly / olympus',
        'endekk': 'endekk',
        'qmr': 'qmr',
    }

    discrepancies = []

    for our_row in our_data:
        player_name, clean_name, our_damage, our_kills, our_seconds, rounds, our_dpm = our_row

        # Find matching SuperBoyy data
        sb_key = None
        for key in player_mapping:
            if key.lower() in clean_name.lower() or key.lower() in player_name.lower():
                sb_key = player_mapping[key]
                break

        if not sb_key or sb_key not in SUPERBOY_DATA:
            continue

        sb_data = SUPERBOY_DATA[sb_key]

        # Calculate differences
        dmg_diff = our_damage - sb_data['damage']
        kill_diff = our_kills - sb_data['kills']

        print(
            f"{
                player_name:<20} | {
                our_damage:<10,} | {
                sb_data['damage']:<10,} | {
                    dmg_diff:>+10,} | {
                        our_kills:<8} | {
                            sb_data['kills']:<8} | {
                                kill_diff:>+8}"
        )

        discrepancies.append(
            {
                'player': player_name,
                'our_damage': our_damage,
                'sb_damage': sb_data['damage'],
                'our_kills': our_kills,
                'sb_kills': sb_data['kills'],
                'our_dpm': our_dpm,
                'sb_dpm': sb_data['dpm'],
                'our_seconds': our_seconds,
                'rounds': rounds,
            }
        )

    print()
    print("=" * 100)
    print("📊 DPM COMPARISON")
    print("=" * 100)
    print()
    print(
        f"{
            'Player':<20} | {
            'Our DPM':<10} | {
                'SB DPM':<10} | {
                    'DPM Diff':<10} | {
                        '% Diff':<8} | {
                            'Our Time':<12}"
    )
    print("-" * 100)

    for disc in discrepancies:
        dpm_diff = disc['our_dpm'] - disc['sb_dpm']
        pct_diff = (dpm_diff / disc['sb_dpm'] * 100) if disc['sb_dpm'] > 0 else 0

        minutes = disc['our_seconds'] // 60
        seconds = disc['our_seconds'] % 60
        time_display = f"{minutes}:{seconds:02d}"

        print(
            f"{
                disc['player']:<20} | {
                disc['our_dpm']:<10.2f} | {
                disc['sb_dpm']:<10} | {
                    dpm_diff:>+10.2f} | {
                        pct_diff:>+7.1f}% | {
                            time_display:<12}"
        )

    print()
    print("=" * 100)
    print("🔬 TIME ANALYSIS - What time does SuperBoyy have?")
    print("=" * 100)
    print()
    print("SuperBoyy doesn't show time in graphs, but we can calculate it from DPM:")
    print()
    print(
        f"{
            'Player':<20} | {
            'SB DMG':<10} | {
                'SB DPM':<10} | {
                    'Calc Time':<12} | {
                        'Our Time':<12} | {
                            'Time Diff':<12}"
    )
    print("-" * 100)

    for disc in discrepancies:
        sb_seconds, sb_minutes = calculate_expected_time(disc['sb_damage'], disc['sb_dpm'])

        our_minutes = disc['our_seconds'] // 60
        our_seconds_rem = disc['our_seconds'] % 60
        our_time_display = f"{our_minutes}:{our_seconds_rem:02d}"

        sb_minutes_int = int(sb_seconds // 60)
        sb_seconds_rem = int(sb_seconds % 60)
        sb_time_display = f"{sb_minutes_int}:{sb_seconds_rem:02d}"

        time_diff_seconds = disc['our_seconds'] - sb_seconds
        time_diff_minutes = abs(time_diff_seconds) // 60
        time_diff_seconds_rem = abs(time_diff_seconds) % 60
        time_diff_display = f"{
            '+' if time_diff_seconds >= 0 else '-'}{
            int(time_diff_minutes)}:{
            int(time_diff_seconds_rem):02d}"

        print(
            f"{
                disc['player']:<20} | {
                disc['sb_damage']:<10,} | {
                disc['sb_dpm']:<10} | {
                    sb_time_display:<12} | {
                        our_time_display:<12} | {
                            time_diff_display:<12}"
        )

    print()
    print("=" * 100)
    print("💡 ANALYSIS - Where did we go wrong?")
    print("=" * 100)
    print()

    # Check damage differences
    avg_dmg_diff = sum(d['our_damage'] - d['sb_damage'] for d in discrepancies) / len(discrepancies)
    avg_kill_diff = sum(d['our_kills'] - d['sb_kills'] for d in discrepancies) / len(discrepancies)
    avg_dpm_diff = sum(d['our_dpm'] - d['sb_dpm'] for d in discrepancies) / len(discrepancies)
    avg_dpm_pct = (
        avg_dpm_diff / (sum(d['sb_dpm'] for d in discrepancies) / len(discrepancies))
    ) * 100

    print(f"Average Differences:")
    print(f"  Damage: {avg_dmg_diff:+,.0f} ({avg_dmg_diff / 30000 * 100:+.1f}%)")
    print(f"  Kills: {avg_kill_diff:+.1f} ({avg_kill_diff / 150 * 100:+.1f}%)")
    print(f"  DPM: {avg_dpm_diff:+.2f} ({avg_dpm_pct:+.1f}%)")
    print()

    # Hypothesis testing
    print("🔍 Possible Issues:")
    print()

    if avg_dpm_diff > 10:
        print(f"1. ⚠️ Our DPM is {avg_dpm_pct:+.1f}% HIGHER than SuperBoyy's")
        print(f"   This suggests we might be UNDERESTIMATING time (shorter time = higher DPM)")
        print(f"   OR SuperBoyy is using LONGER time than what's in files")
        print()
    elif avg_dpm_diff < -10:
        print(f"1. ⚠️ Our DPM is {avg_dpm_pct:+.1f}% LOWER than SuperBoyy's")
        print(f"   This suggests we might be OVERESTIMATING time (longer time = lower DPM)")
        print(f"   OR SuperBoyy is using SHORTER time than what's in files")
        print()
    else:
        print(f"1. ✅ Our DPM is within {abs(avg_dpm_pct):.1f}% of SuperBoyy's (EXCELLENT!)")
        print()

    if abs(avg_dmg_diff) > 1000:
        print(f"2. ⚠️ Damage differs by {abs(avg_dmg_diff):,.0f} on average")
        print(f"   Possible causes:")
        print(f"   - Missing rounds in our database")
        print(f"   - Different round selection criteria")
        print(f"   - SuperBoyy excludes certain maps?")
        print()
    else:
        print(f"2. ✅ Damage matches well (within {abs(avg_dmg_diff):,.0f})")
        print()

    if abs(avg_kill_diff) > 5:
        print(f"3. ⚠️ Kills differ by {abs(avg_kill_diff):.1f} on average")
        print(f"   Same causes as damage differences")
        print()
    else:
        print(f"3. ✅ Kills match well (within {abs(avg_kill_diff):.1f})")
        print()

    print("=" * 100)
    print("🎯 RECOMMENDATION")
    print("=" * 100)
    print()
    print("Based on the data comparison, we should:")
    print("1. Check if we're missing any October 2nd rounds")
    print("2. Verify our time calculation matches file times exactly")
    print("3. Consider that SuperBoyy processes from DEMO files (may have different timing)")
    print("4. Demo files record actual in-game time (may differ from server logs by a few seconds)")


if __name__ == '__main__':
    analyze_discrepancies()
