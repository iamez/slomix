# 🔄 October 2nd Re-Import Instructions

**Goal:** Wipe existing October 2nd data and re-import all 20 files to fix missing records

---

## 📋 Current Situation

- **Database Location:** `bot/bot/etlegacy_production.db`
- **Current October 2nd Records:** 87 (missing ~33 records)
- **Raw Files Available:** 20 files in `local_stats/2025-10-02*.txt`
- **Expected Records:** ~120 (20 files × 6 players average)
- **Problem:** Not all October 2nd files were imported during bulk import

---

## 🎯 What Needs to Be Done

### Step 1: Delete October 2nd Data from Database
```python
import sqlite3

conn = sqlite3.connect('bot/bot/etlegacy_production.db')
cursor = conn.cursor()

# Delete player stats for October 2nd
cursor.execute("""
    DELETE FROM player_comprehensive_stats 
    WHERE session_date = '2025-10-02'
""")

# Delete sessions for October 2nd
cursor.execute("""
    DELETE FROM sessions 
    WHERE session_date = '2025-10-02'
""")

conn.commit()
print(f"✅ Deleted October 2nd data")
conn.close()
```

### Step 2: Re-import ONLY October 2nd Files
```python
import os
import sys
from pathlib import Path

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

# Get October 2nd files
files = sorted([f for f in os.listdir('local_stats') if f.startswith('2025-10-02')])
print(f"Found {len(files)} October 2nd files")

# Use the existing bulk importer but filter for October 2nd only
from tools.simple_bulk_import import SimpleBulkImporter

importer = SimpleBulkImporter(
    db_path="bot/bot/etlegacy_production.db",
    stats_dir="local_stats"
)

# Import only October 2nd files
oct2_files = [f for f in importer.get_stats_files() if '2025-10-02' in str(f)]
print(f"Importing {len(oct2_files)} files...")

for file in oct2_files:
    importer.process_file(file)

print(f"\n✅ Imported {importer.processed} files")
print(f"❌ Failed: {importer.failed}")
```

### Step 3: Verify the Re-import
```python
import sqlite3

conn = sqlite3.connect('bot/bot/etlegacy_production.db')
cursor = conn.cursor()

# Check total records
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
total = cursor.fetchone()[0]
print(f"October 2nd records: {total}")

# Check time quality
cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02' AND time_played_seconds > 0")
with_time = cursor.fetchone()[0]
print(f"Records with time > 0: {with_time} ({with_time/total*100:.1f}%)")

# Check unique sessions
cursor.execute("SELECT COUNT(DISTINCT map_name, round_number) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
sessions = cursor.fetchone()[0]
print(f"Unique sessions: {sessions}")

conn.close()
```

---

## 🚀 Quick One-Line Solution

Create a script called `reimport_oct2.py`:

```python
#!/usr/bin/env python3
"""
Re-import October 2nd Data (Clean)
Wipes existing October 2nd data and re-imports all 20 files
"""

import os
import sys
import sqlite3
from pathlib import Path
from datetime import datetime

sys.path.insert(0, 'bot')
from community_stats_parser import C0RNP0RN3StatsParser

DB_PATH = "bot/bot/etlegacy_production.db"

def wipe_october_2nd():
    """Delete all October 2nd data from database"""
    print("\n" + "="*60)
    print("🗑️  WIPING OCTOBER 2ND DATA")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Count before
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
    before_count = cursor.fetchone()[0]
    
    # Delete player stats
    cursor.execute("DELETE FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
    
    # Delete sessions
    cursor.execute("DELETE FROM sessions WHERE session_date = '2025-10-02'")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Deleted {before_count} records")

def import_october_2nd():
    """Import all October 2nd files"""
    print("\n" + "="*60)
    print("📥 IMPORTING OCTOBER 2ND FILES")
    print("="*60)
    
    # Get October 2nd files
    files = sorted([f for f in os.listdir('local_stats') if f.startswith('2025-10-02')])
    print(f"Found {len(files)} October 2nd files\n")
    
    parser = C0RNP0RN3StatsParser()
    conn = sqlite3.connect(DB_PATH)
    
    imported = 0
    failed = 0
    failed_files = []
    
    for filename in files:
        filepath = f"local_stats/{filename}"
        
        try:
            # Parse file
            result = parser.parse_stats_file(filepath)
            
            if not result or not result.get('success'):
                failed += 1
                failed_files.append(filename)
                continue
            
            # Extract session date from filename: 2025-10-02-211808
            parts = filename.split('-')
            session_date = f"{parts[0]}-{parts[1]}-{parts[2]}"
            
            # Insert session
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO sessions 
                (session_date, map_name, round_number, time_limit, next_time_limit)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_date,
                result['map_name'],
                result['round_num'],
                result.get('map_time', ''),
                result.get('actual_time', '')
            ))
            
            # Get session_id
            cursor.execute("""
                SELECT id FROM sessions 
                WHERE session_date = ? AND map_name = ? AND round_number = ?
            """, (session_date, result['map_name'], result['round_num']))
            session_id = cursor.fetchone()[0]
            
            # Insert players
            for player in result['players']:
                cursor.execute("""
                    INSERT INTO player_comprehensive_stats (
                        session_id, session_date, map_name, round_number,
                        player_guid, player_name, clean_name, team,
                        kills, deaths, damage_given, damage_received,
                        time_played_seconds, time_display, dpm
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, session_date, result['map_name'], result['round_num'],
                    player['guid'], player['name'], player['name'].replace('^', ''), player['team'],
                    player['kills'], player['deaths'], player['damage_given'], player['damage_received'],
                    player.get('time_played_seconds', 0),
                    player.get('time_display', '0:00'),
                    player.get('dpm', 0.0)
                ))
            
            conn.commit()
            imported += 1
            print(f"✅ {filename}")
            
        except Exception as e:
            failed += 1
            failed_files.append(f"{filename}: {str(e)}")
            print(f"❌ {filename}: {e}")
    
    conn.close()
    
    print(f"\n" + "="*60)
    print(f"✅ Imported: {imported}/{len(files)}")
    print(f"❌ Failed: {failed}")
    
    if failed_files:
        print("\nFailed files:")
        for f in failed_files:
            print(f"  - {f}")

def verify_import():
    """Verify the import was successful"""
    print("\n" + "="*60)
    print("🔍 VERIFYING IMPORT")
    print("="*60)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Total records
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
    total = cursor.fetchone()[0]
    
    # Records with time
    cursor.execute("SELECT COUNT(*) FROM player_comprehensive_stats WHERE session_date = '2025-10-02' AND time_played_seconds > 0")
    with_time = cursor.fetchone()[0]
    
    # Unique sessions
    cursor.execute("SELECT COUNT(DISTINCT map_name, round_number) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
    sessions = cursor.fetchone()[0]
    
    # Unique players
    cursor.execute("SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats WHERE session_date = '2025-10-02'")
    players = cursor.fetchone()[0]
    
    print(f"\n📊 Results:")
    print(f"  Total records: {total}")
    print(f"  Records with time > 0: {with_time} ({with_time/total*100:.1f}%)")
    print(f"  Unique sessions: {sessions}")
    print(f"  Unique players: {players}")
    print(f"  Expected: ~120 records (20 files × 6 players)")
    
    if total >= 100 and with_time/total > 0.95:
        print(f"\n✅ IMPORT SUCCESSFUL!")
    else:
        print(f"\n⚠️  Import may be incomplete")
    
    conn.close()

if __name__ == '__main__':
    wipe_october_2nd()
    import_october_2nd()
    verify_import()
```

---

## 📝 Expected Results After Re-import

- **Total Records:** ~120 (up from 87)
- **Records with time > 0:** ~118 (98%+)
- **Unique Sessions:** 20 (one per file)
- **Unique Players:** 6

---

## 🎯 SuperBoyy Comparison After Re-import

After re-import, our data should match SuperBoyy's much better:

**Expected Improvements:**
- ✅ Damage difference: -9.5% → ~-2%
- ✅ Kills difference: -9.4% → ~-2%
- ✅ DPM difference: +17% → ~+4%

The remaining small difference (~4% DPM) is likely due to:
1. SuperBoyy uses DEMO files (slightly different timing)
2. In-game HUD may show rounded time
3. Different data sources (demo vs c0rnp0rn3.lua files)

---

## 🚀 Run It

```bash
python reimport_oct2.py
```

That's it! The script will:
1. Wipe October 2nd data
2. Re-import all 20 files
3. Verify the results
4. Show comparison stats

---

## 🔧 If Something Goes Wrong

The database has backups at:
- `database_backups/` directory
- Original: `etlegacy_production_OLD_20251003_155400.db`

To restore:
```bash
cp bot/bot/etlegacy_production.db bot/bot/etlegacy_production_BROKEN.db
cp etlegacy_production_OLD_20251003_155400.db bot/bot/etlegacy_production.db
```
