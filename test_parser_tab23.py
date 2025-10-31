#!/usr/bin/env python3
"""
Test parser to verify Tab[23] field mapping is correct
"""

from bot.community_stats_parser import C0RNP0RN3StatsParser


def test_tab23_parsing():
    """Test that parser reads Tab[23] for time_played_minutes"""
    parser = C0RNP0RN3StatsParser()

    # Test Round 1 file
    print("=" * 60)
    print("Testing Round 1 file: etl_adlernest")
    print("=" * 60)

    file_path = 'local_stats/2025-10-02-211808-etl_adlernest-round-1.txt'
    data = parser.parse_stats_file(file_path)

    print("\n📋 Session Info:")
    print(f"   Map: {data['map_name']}")
    print(f"   Round: {data['round_num']}")
    print(f"   Session time (header): {data['actual_time']}")

    # Find vid
    vid = [p for p in data['players'] if 'vid' in p['name']][0]

    print(f"\n👤 Player: {vid['name']}")
    print(
        f"   Tab[23] time_played_minutes: {
            vid['objective_stats'].get(
                'time_played_minutes',
                'NOT FOUND')}"
    )
    print(f"   time_played_seconds: {vid.get('time_played_seconds', 'NOT SET')}")
    print(f"   time_display: {vid.get('time_display', 'NOT SET')}")
    print(f"   DPM: {vid.get('dpm', 'NOT SET')}")

    # Test Round 2 file
    print("\n" + "=" * 60)
    print("Testing Round 2 file: etl_adlernest")
    print("=" * 60)

    file_path2 = 'local_stats/2025-10-02-212249-etl_adlernest-round-2.txt'
    data2 = parser.parse_stats_file(file_path2)

    print("\n📋 Session Info:")
    print(f"   Map: {data2['map_name']}")
    print(f"   Round: {data2['round_num']}")
    print(f"   Session time (header): {data2['actual_time']}")

    # Find vid
    vid2 = [p for p in data2['players'] if 'vid' in p['name']][0]

    print(f"\n👤 Player: {vid2['name']}")
    print(
        f"   Tab[23] time_played_minutes (cumulative): {
            vid2['objective_stats'].get(
                'time_played_minutes',
                'NOT FOUND')}"
    )
    print(f"   time_played_seconds: {vid2.get('time_played_seconds', 'NOT SET')}")
    print(f"   time_display: {vid2.get('time_display', 'NOT SET')}")
    print(f"   DPM: {vid2.get('dpm', 'NOT SET')}")

    print("\n" + "=" * 60)
    print("✅ Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    test_tab23_parsing()
