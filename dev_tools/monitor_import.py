"""
Monitor import process - REAL-TIME tracking of ALL files
Run this in a separate terminal DURING the import

IMPORTANT: Start this BEFORE running postgresql_database_manager.py
"""
import time
import asyncio
import asyncpg
import os
from datetime import datetime
from bot.config import load_config

# Load PostgreSQL config
config = load_config()

PROBLEM_FILES = [
    '2025-11-04-225627-etl_frostbite-round-1.txt',
    '2025-11-04-224353-te_escape2-round-2.txt'
]

print("=" * 80)
print("IMPORT MONITOR - Real-time tracking")
print("=" * 80)
print(f"\nTarget files:")
for f in PROBLEM_FILES:
    print(f"  - {f}")
print(f"\nMonitoring database: {DB_PATH}")

# Check current state
if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM processed_files WHERE filename IN (?, ?)", PROBLEM_FILES)
        existing = cursor.fetchone()[0]
        
        if existing > 0:
            print(f"\n⚠️  WARNING: {existing} target files already in processed_files table!")
            print("   This means they were imported before.")
            print("   You need to DELETE the database first for fresh monitoring.")
            print("\n   Run this first:")
            print("   > del bot\\etlegacy_production.db")
            print("   > python postgresql_database_manager.py")
            conn.close()
            input("\nPress ENTER to exit...")
            exit(1)
    except:
        pass  # Tables don't exist yet - good!
    
    conn.close()

print("\n✅ Database ready for fresh import monitoring")
print("\nWaiting for import to start...")
print("Press Ctrl+C to stop monitoring\n")
print("=" * 80)

last_check = {}
check_interval = 2  # seconds

try:
    while True:
        if not os.path.exists(DB_PATH):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Waiting for database to be created...")
            time.sleep(check_interval)
            continue
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        if 'processed_files' not in tables:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] ⏳ Waiting for tables to be created...")
            conn.close()
            time.sleep(check_interval)
            continue
        
        # Check processed_files for our targets
        for filename in PROBLEM_FILES:
            cursor.execute('''
                SELECT success, error_message, processed_at 
                FROM processed_files 
                WHERE filename = ?
            ''', (filename,))
            
            result = cursor.fetchone()
            
            if result and filename not in last_check:
                # File just got processed!
                success, error, processed_at = result
                status = "✅ SUCCESS" if success else "❌ FAILED"
                
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {status}: {filename}")
                print(f"  Processed: {processed_at}")
                if error:
                    print(f"  Error: {error}")
                
                # Check if data actually made it to player_comprehensive_stats
                map_name = 'etl_frostbite' if 'frostbite' in filename else 'te_escape2'
                round_num = 1 if 'round-1' in filename else 2
                
                cursor.execute('''
                    SELECT COUNT(*) 
                    FROM player_comprehensive_stats 
                    WHERE round_date = '2025-11-04' 
                    AND map_name = ? 
                    AND round_number = ?
                ''', (map_name, round_num))
                
                record_count = cursor.fetchone()[0]
                
                if record_count > 0:
                    print(f"  ✅ Database records: {record_count} players")
                else:
                    print(f"  ⚠️  WARNING: ZERO records in database despite success flag!")
                
                last_check[filename] = True
        
        conn.close()
        
        # Check if we've seen both files
        if len(last_check) == len(PROBLEM_FILES):
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ✅ All target files processed. Monitoring complete.")
            break
        
        time.sleep(check_interval)

except KeyboardInterrupt:
    print("\n\nMonitoring stopped by user.")
except Exception as e:
    print(f"\n❌ Monitor error: {e}")

print("\n" + "=" * 80)
print("Monitor exiting")
print("=" * 80)
