"""
Verify October 2nd Session Times
Compare raw file times vs database times vs SuperBoyy's data
"""

import os
import sqlite3


def parse_time_mm_ss(time_str):
    """Convert MM:SS string to seconds"""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def extract_file_times():
    """Extract actual times from raw stat files"""
    files = sorted([f for f in os.listdir('local_stats') if f.startswith('2025-10-02')])

    file_data = []
    for filename in files:
        filepath = os.path.join('local_stats', filename)
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            header = f.readline().strip()

        # Parse header:
        # ^a#^7p^au^7rans^a.^7only\map_name\config\round\winner\totalrounds\timelimit\actualtime
        parts = header.split('\\')
        if len(parts) >= 8:
            map_name = parts[1]
            round_num = parts[3]
            actual_time = parts[7]  # MM:SS format

            # Parse timestamp from filename: 2025-10-02-211808
            timestamp = filename.split('-')[0:4]
            time_str = f"{timestamp[0]}-{timestamp[1]}-{timestamp[2]} {timestamp[3][:2]}:{timestamp[3][2:4]}:{timestamp[3][4:6]}"

            seconds = parse_time_mm_ss(actual_time)

            file_data.append(
                {
                    'filename': filename,
                    'timestamp': time_str,
                    'map': map_name,
                    'round': round_num,
                    'time_mmss': actual_time,
                    'time_seconds': seconds,
                    'time_minutes': round(seconds / 60, 2),
                }
            )

    return file_data


def get_database_times():
    """Get times from database for October 2nd"""
    conn = sqlite3.connect('etlegacy_production.db')
    cursor = conn.cursor()

    query = """
        SELECT
            s.map_name,
            s.round_number,
            s.created_at,
            COUNT(DISTINCT p.player_guid) as player_count,
            MIN(p.time_played_seconds) as min_time,
            MAX(p.time_played_seconds) as max_time,
            AVG(p.time_played_seconds) as avg_time
        FROM sessions s
        LEFT JOIN player_comprehensive_stats p ON s.id = p.session_id
        WHERE s.session_date = '2025-10-02'
        GROUP BY s.map_name, s.round_number, s.created_at
        ORDER BY s.created_at
    """

    cursor.execute(query)
    results = cursor.fetchall()
    conn.close()

    db_data = []
    for row in results:
        map_name, round_num, created_at, player_count, min_time, max_time, avg_time = row

        # Format times
        min_mmss = f"{int(min_time // 60)}:{int(min_time % 60):02d}" if min_time else "N/A"
        max_mmss = f"{int(max_time // 60)}:{int(max_time % 60):02d}" if max_time else "N/A"
        avg_mmss = f"{int(avg_time // 60)}:{int(avg_time % 60):02d}" if avg_time else "N/A"

        db_data.append(
            {
                'map': map_name,
                'round': round_num,
                'created_at': created_at,
                'player_count': player_count,
                'min_seconds': min_time,
                'max_seconds': max_time,
                'avg_seconds': avg_time,
                'min_mmss': min_mmss,
                'max_mmss': max_mmss,
                'avg_mmss': avg_mmss,
            }
        )

    return db_data


def compare_data():
    """Compare raw file times with database times"""
    print("=" * 100)
    print("🔍 OCTOBER 2ND SESSION TIME VERIFICATION")
    print("=" * 100)
    print()

    # Get data
    file_times = extract_file_times()
    db_times = get_database_times()

    print(f"📄 Raw Files Found: {len(file_times)}")
    print(f"💾 Database Sessions: {len(db_times)}")
    print()

    # Display file times
    print("=" * 100)
    print("📄 RAW FILE TIMES (from c0rnp0rn3.lua files)")
    print("=" * 100)
    print(
        f"{
            'Timestamp':<20} {
            'Map':<20} {
                'R':<3} {
                    'Time (MM:SS)':<12} {
                        'Seconds':<8} {
                            'Minutes':<8}"
    )
    print("-" * 100)

    for data in file_times:
        print(
            f"{data['timestamp']:<20} {data['map']:<20} {data['round']:<3} "
            f"{data['time_mmss']:<12} {data['time_seconds']:<8} {data['time_minutes']:<8}"
        )

    print()

    # Display database times
    print("=" * 100)
    print("💾 DATABASE TIMES (stored in player_comprehensive_stats)")
    print("=" * 100)
    print(f"{'Map':<20} {'R':<3} {'Players':<8} {'Min Time':<12} {'Max Time':<12} {'Avg Time':<12}")
    print("-" * 100)

    for data in db_times:
        print(
            f"{data['map']:<20} {data['round']:<3} {data['player_count']:<8} "
            f"{data['min_mmss']:<12} {data['max_mmss']:<12} {data['avg_mmss']:<12}"
        )

    print()

    # Check for mismatches
    print("=" * 100)
    print("⚠️ CHECKING FOR DISCREPANCIES")
    print("=" * 100)

    mismatches = []
    for file_data in file_times:
        # Find matching database entry
        matching_db = [
            d for d in db_times if d['map'] == file_data['map'] and d['round'] == file_data['round']
        ]

        if not matching_db:
            print(
                f"❌ Missing in DB: {
                    file_data['map']} R{
                    file_data['round']} ({
                    file_data['time_mmss']})"
            )
            mismatches.append(file_data)
            continue

        db_data = matching_db[0]

        # Check if all players have the same time (they should!)
        if db_data['min_seconds'] != db_data['max_seconds']:
            print(f"⚠️ TIME VARIATION: {file_data['map']} R{file_data['round']}")
            print(f"   File: {file_data['time_mmss']} ({file_data['time_seconds']}s)")
            print(f"   DB Range: {db_data['min_mmss']} - {db_data['max_mmss']}")
            mismatches.append({'file': file_data, 'db': db_data})
            continue

        # Check if database time matches file time
        if abs(db_data['avg_seconds'] - file_data['time_seconds']) > 1:  # Allow 1 second tolerance
            print(f"❌ MISMATCH: {file_data['map']} R{file_data['round']}")
            print(f"   File: {file_data['time_mmss']} ({file_data['time_seconds']}s)")
            print(f"   DB: {db_data['avg_mmss']} ({db_data['avg_seconds']:.0f}s)")
            print(
                f"   Difference: {abs(db_data['avg_seconds'] -
                                      file_data['time_seconds']):.0f} seconds"
            )
            mismatches.append({'file': file_data, 'db': db_data})

    if not mismatches:
        print("✅ ALL TIMES MATCH PERFECTLY!")
        print("   File times = Database times")
        print("   All players have same time per round (as expected)")

    print()
    print("=" * 100)
    print("📊 SUMMARY")
    print("=" * 100)

    total_file_seconds = sum(d['time_seconds'] for d in file_times)
    total_file_minutes = total_file_seconds / 60

    print(
        f"Total October 2nd Playtime: {int(total_file_minutes //
                                           60)}h {int(total_file_minutes %
                                                      60)}m ({total_file_seconds} seconds)"
    )
    print(
        f"Average Round Duration: {
            total_file_seconds /
            len(file_times):.0f} seconds ({
            total_file_minutes /
            len(file_times):.1f} minutes)"
    )
    print()

    # Show unique maps
    unique_maps = set(d['map'] for d in file_times)
    print(f"Maps Played: {', '.join(sorted(unique_maps))}")
    print()


if __name__ == '__main__':
    compare_data()
