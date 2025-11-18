import sqlite3
from pathlib import Path

dbs_to_check = [
    "bot/etlegacy_production.db",
    "etlegacy_production.db",
    "dev/etlegacy_perfect.db",
    "dev/etlegacy_comprehensive.db",
    "database/etlegacy_production.db",
]

print("=" * 120)
print("CHECKING MULTIPLE DATABASE FILES FOR DATA")
print("=" * 120)

for db_path in dbs_to_check:
    if not Path(db_path).exists():
        print(f"\n❌ {db_path} - NOT FOUND")
        continue
        
    print(f"\n{'=' * 120}")
    print(f"📂 {db_path}")
    print("=" * 120)
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check rounds
        cursor.execute("SELECT COUNT(*) FROM rounds")
        sessions_count = cursor.fetchone()[0]
        
        # Check player stats
        cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
        player_count = cursor.fetchone()[0]
        
        # Check weapon stats
        cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
        weapon_count = cursor.fetchone()[0]
        
        # Check processed files
        cursor.execute("SELECT COUNT(*) FROM processed_files")
        processed_count = cursor.fetchone()[0]
        
        # Check date range
        cursor.execute("SELECT DISTINCT round_date FROM rounds ORDER BY round_date LIMIT 5")
        dates = cursor.fetchall()
        
        print(f"   Sessions:        {sessions_count:,}")
        print(f"   Player Stats:    {player_count:,}")
        print(f"   Weapon Stats:    {weapon_count:,}")
        print(f"   Processed Files: {processed_count:,}")
        
        if dates:
            print(f"\n   Sample Dates:")
            for date in dates:
                print(f"      - {date[0]}")
        
        # Check if this looks like the REAL data
        if sessions_count > 100:
            print(f"\n   🎯 THIS DATABASE HAS REAL DATA! ({sessions_count} sessions)")
        elif sessions_count == 8:
            print(f"\n   ⚠️  This has only test data (8 sessions from 2025-01-01)")
        else:
            print(f"\n   ❓ Unknown state ({sessions_count} sessions)")
        
        conn.close()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "=" * 120)
