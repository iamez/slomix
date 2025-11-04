import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

print("=" * 100)
print("COPYING DATA FROM ROOT DB TO BOT DB")
print("=" * 100)

source_db = "etlegacy_production.db"
target_db = "bot/etlegacy_production.db"

# First, backup the bot DB
print("\n📦 Step 1: Backing up bot/etlegacy_production.db...")
backup_path = f"bot/etlegacy_production_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
if Path(target_db).exists():
    shutil.copy2(target_db, backup_path)
    print(f"   ✅ Backup created: {backup_path}")
else:
    print("   ⚠️  Target DB doesn't exist (will be created)")

# Check source DB
print("\n📊 Step 2: Checking source database...")
conn_source = sqlite3.connect(source_db)
cursor = conn_source.cursor()

cursor.execute("SELECT COUNT(*) FROM rounds")
sessions = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
players = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
weapons = cursor.fetchone()[0]

print(f"   Sessions:     {sessions:,}")
print(f"   Player stats: {players:,}")
print(f"   Weapon stats: {weapons:,}")

if sessions == 0:
    print("   ❌ Source database is empty! Aborting.")
    conn_source.close()
    exit(1)

# Just copy the entire file!
print("\n📋 Step 3: Copying entire database file...")
print(f"   Source: {source_db}")
print(f"   Target: {target_db}")

conn_source.close()

# Ensure bot directory exists
Path("bot").mkdir(exist_ok=True)

# Copy the file
shutil.copy2(source_db, target_db)
print("   ✅ Database file copied!")

# Verify target
print("\n✅ Step 4: Verifying target database...")
conn_target = sqlite3.connect(target_db)
cursor = conn_target.cursor()

cursor.execute("SELECT COUNT(*) FROM rounds")
sessions_target = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats")
players_target = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM weapon_comprehensive_stats")
weapons_target = cursor.fetchone()[0]
cursor.execute("SELECT MIN(round_date), MAX(round_date) FROM rounds")
date_range = cursor.fetchone()

conn_target.close()

print(f"   Sessions:     {sessions_target:,}")
print(f"   Player stats: {players_target:,}")
print(f"   Weapon stats: {weapons_target:,}")
print(f"   Date range:   {date_range[0]} to {date_range[1]}")

# Verify match
if sessions == sessions_target and players == players_target:
    print("\n🎉 SUCCESS! Bot database now has all the data!")
    print(f"   ✅ {sessions:,} sessions")
    print(f"   ✅ {players:,} player stats")
    print(f"   ✅ {weapons:,} weapon stats")
    print(f"   ✅ Date range: {date_range[0]} to {date_range[1]}")
else:
    print("\n❌ ERROR: Data mismatch after copy!")
    print(f"   Source had {sessions} sessions, target has {sessions_target}")

print("\n" + "=" * 100)
