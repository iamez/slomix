"""
Clean rebuild: Wipe database and re-import only October and November 2025 data
"""
import sqlite3
import os
import glob
from datetime import datetime

print("="*70)
print("CLEAN DATABASE REBUILD - October & November 2025")
print("="*70)

db_path = 'bot/etlegacy_production.db'

# Backup current database
backup_path = f'{db_path}.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
print(f"\n1. Creating backup: {backup_path}")
import shutil
shutil.copy2(db_path, backup_path)
print("   ✅ Backup created")

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clear all data
print("\n2. Clearing all session data...")
cursor.execute("DELETE FROM weapon_comprehensive_stats")
print(f"   Deleted {cursor.rowcount} weapon stats")

cursor.execute("DELETE FROM player_comprehensive_stats")
print(f"   Deleted {cursor.rowcount} player stats")

cursor.execute("DELETE FROM rounds")
print(f"   Deleted {cursor.rowcount} sessions")

cursor.execute("DELETE FROM session_teams")
print(f"   Deleted {cursor.rowcount} team records")

cursor.execute("DELETE FROM processed_files")
print(f"   Deleted {cursor.rowcount} processed file records")

conn.commit()
print("   ✅ Database cleared")

# Find October and November files
print("\n3. Finding October & November 2025 files...")
all_files = glob.glob('bot/local_stats/*.txt')
oct_nov_files = [
    f for f in all_files 
    if os.path.basename(f).startswith('2025-10-') or 
       os.path.basename(f).startswith('2025-11-')
]

print(f"   Found {len(oct_nov_files)} files")

# Group by date
by_date = {}
for f in oct_nov_files:
    basename = os.path.basename(f)
    date = basename[:10]  # YYYY-MM-DD
    if date not in by_date:
        by_date[date] = []
    by_date[date].append(basename)

print("\n   Files by date:")
for date in sorted(by_date.keys()):
    print(f"     {date}: {len(by_date[date])} files")

conn.close()

print("\n" + "="*70)
print("DATABASE CLEARED - Ready for re-import")
print("="*70)
print("\nNext steps:")
print("1. Run: !sync_stats all")
print("   OR manually import using the parser")
print(f"\nBackup saved at: {backup_path}")
