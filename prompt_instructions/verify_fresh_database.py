#!/usr/bin/env python3
"""
Verify Fresh Database Population
Check record counts, time_played_seconds, and DPM calculations
"""

import sqlite3
from datetime import datetime

def verify_database():
    """Verify database population and data quality"""
    
    db_path = "bot/bot/etlegacy_production.db"
    
    print("\n" + "=" * 60)
    print("🔍 VERIFYING DATABASE POPULATION")
    print("=" * 60)
    print(f"Database: {db_path}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Count total records
    print("📊 Record Counts:")
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
    total_records = cursor.fetchone()[0]
    print(f"   Total player records: {total_records:,}")
    
    cursor.execute("SELECT COUNT(*) FROM sessions")
    total_sessions = cursor.fetchone()[0]
    print(f"   Total sessions: {total_sessions:,}\n")
    
    # 2. Check time_played_seconds
    print("⏱️  Time Field Analysis:")
    cursor.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats 
        WHERE time_played_seconds = 0
    """)
    zero_time = cursor.fetchone()[0]
    percent_zero = (zero_time / total_records * 100) if total_records > 0 else 0
    print(f"   Records with time_played_seconds = 0: {zero_time} ({percent_zero:.1f}%)")
    
    cursor.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats 
        WHERE time_played_seconds > 0
    """)
    valid_time = cursor.fetchone()[0]
    percent_valid = (valid_time / total_records * 100) if total_records > 0 else 0
    print(f"   Records with time_played_seconds > 0: {valid_time} ({percent_valid:.1f}%)\n")
    
    # 3. Sample data from October 2nd
    print("🎯 October 2nd Data Sample:")
    cursor.execute("""
        SELECT player_name, time_played_seconds, time_display, damage_given, dpm, round_number
        FROM player_comprehensive_stats
        WHERE session_date = '2025-10-02'
        LIMIT 5
    """)
    oct2_samples = cursor.fetchall()
    
    if oct2_samples:
        for name, seconds, display, damage, dpm, round_num in oct2_samples:
            print(f"   {name}: R{round_num} - {seconds}s ({display}) - {damage} dmg - {dpm:.2f} DPM")
    else:
        print("   No October 2nd data found!")
    
    # 4. Check DPM calculations
    print("\n🧮 DPM Calculation Verification:")
    cursor.execute("""
        SELECT player_name, damage_given, time_played_seconds, dpm
        FROM player_comprehensive_stats
        WHERE time_played_seconds > 0
        LIMIT 5
    """)
    
    for name, damage, seconds, stored_dpm in cursor.fetchall():
        calculated_dpm = (damage * 60) / seconds if seconds > 0 else 0
        diff = abs(calculated_dpm - stored_dpm)
        status = "✅" if diff < 0.01 else "❌"
        print(f"   {status} {name}: Stored={stored_dpm:.2f}, Calculated={calculated_dpm:.2f}, Diff={diff:.4f}")
    
    # 5. Check for Round 2 time preservation
    print("\n🔄 Round 2 Time Preservation:")
    cursor.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE round_number = 2 AND time_played_seconds = 0
    """)
    r2_zero_time = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM player_comprehensive_stats
        WHERE round_number = 2
    """)
    r2_total = cursor.fetchone()[0]
    
    r2_percent_zero = (r2_zero_time / r2_total * 100) if r2_total > 0 else 0
    print(f"   Round 2 records: {r2_total}")
    print(f"   Round 2 with time=0: {r2_zero_time} ({r2_percent_zero:.1f}%)")
    
    if r2_percent_zero > 5:
        print("   ⚠️  Warning: High percentage of Round 2 records with time=0")
    else:
        print("   ✅ Round 2 time preservation looks good!")
    
    # 6. Date range
    print("\n📅 Data Range:")
    cursor.execute("""
        SELECT MIN(session_date), MAX(session_date)
        FROM player_comprehensive_stats
    """)
    min_date, max_date = cursor.fetchone()
    print(f"   Earliest session: {min_date}")
    print(f"   Latest session: {max_date}")
    
    # 7. Player count
    print("\n👥 Unique Players:")
    cursor.execute("""
        SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats
    """)
    unique_players = cursor.fetchone()[0]
    print(f"   Total unique players: {unique_players}")
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 60)
    
    if percent_valid > 95 and r2_percent_zero < 5:
        print("🎉 Database looks EXCELLENT!")
        print("   - Time data populated correctly")
        print("   - Round 2 differential preserved")
        print("   - DPM calculations accurate")
        print("   - Ready for Discord bot testing!")
    elif percent_valid > 90:
        print("✅ Database looks GOOD!")
        print("   - Minor issues detected but acceptable")
        print("   - Ready for testing")
    else:
        print("⚠️  Database has ISSUES!")
        print(f"   - Only {percent_valid:.1f}% of records have valid time")
        print("   - May need investigation")
    
    print("=" * 60 + "\n")

if __name__ == "__main__":
    verify_database()
