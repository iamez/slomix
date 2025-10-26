# 🗄️ Database Schema Extensions

**Last Updated:** October 6, 2025  
**Purpose:** Complete database schema for FIVEEYES analytics system

---

## 📊 Overview

This document describes all new tables needed for the FIVEEYES project, plus migration scripts to safely update your existing database.

### Existing Tables (No Changes)

✅ Your current tables remain untouched:
- `sessions` - Session metadata
- `player_comprehensive_stats` - Player stats per session (53 columns)
- `weapon_comprehensive_stats` - Weapon-specific stats
- `player_aliases` - Player name tracking
- `player_links` - Discord account linking
- `session_teams` - Team composition
- `processed_files` - Hybrid file tracking

---

## 🆕 New Tables

### Table 1: `player_synergies` (Phase 1)

**Purpose:** Store calculated synergy scores between all player pairs

```sql
CREATE TABLE IF NOT EXISTS player_synergies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Player pair identification
    player_a_guid TEXT NOT NULL,
    player_b_guid TEXT NOT NULL,
    
    -- Game count metrics
    games_together INTEGER DEFAULT 0,
    games_same_team INTEGER DEFAULT 0,
    games_opposite_team INTEGER DEFAULT 0,
    wins_together INTEGER DEFAULT 0,
    losses_together INTEGER DEFAULT 0,
    
    -- Performance metrics (together)
    avg_kills_together REAL DEFAULT 0,
    avg_deaths_together REAL DEFAULT 0,
    avg_damage_together REAL DEFAULT 0,
    avg_objectives_together REAL DEFAULT 0,
    
    -- Performance metrics (apart)
    avg_kills_a_solo REAL DEFAULT 0,
    avg_deaths_a_solo REAL DEFAULT 0,
    avg_damage_a_solo REAL DEFAULT 0,
    avg_kills_b_solo REAL DEFAULT 0,
    avg_deaths_b_solo REAL DEFAULT 0,
    avg_damage_b_solo REAL DEFAULT 0,
    
    -- Calculated synergy scores
    win_rate_together REAL DEFAULT 0,
    win_rate_a_solo REAL DEFAULT 0,
    win_rate_b_solo REAL DEFAULT 0,
    win_rate_boost REAL DEFAULT 0,
    performance_boost_a REAL DEFAULT 0,
    performance_boost_b REAL DEFAULT 0,
    performance_boost_avg REAL DEFAULT 0,
    synergy_score REAL DEFAULT 0,
    
    -- Metadata
    confidence_level REAL DEFAULT 0,
    last_played_together TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_a_guid, player_b_guid)
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_synergies_player_a 
ON player_synergies(player_a_guid);

CREATE INDEX IF NOT EXISTS idx_synergies_player_b 
ON player_synergies(player_b_guid);

CREATE INDEX IF NOT EXISTS idx_synergies_score 
ON player_synergies(synergy_score DESC);

CREATE INDEX IF NOT EXISTS idx_synergies_games 
ON player_synergies(games_same_team DESC);
```

**Column Descriptions:**

| Column | Type | Description |
|--------|------|-------------|
| `player_a_guid` | TEXT | First player GUID (alphabetically sorted) |
| `player_b_guid` | TEXT | Second player GUID |
| `games_together` | INT | Total games in same session |
| `games_same_team` | INT | Games on same team |
| `win_rate_together` | REAL | Win rate when on same team (0.0-1.0) |
| `win_rate_boost` | REAL | Win rate boost vs expected |
| `performance_boost_avg` | REAL | Average performance boost (%) |
| `synergy_score` | REAL | Overall synergy (-1.0 to 1.0, higher = better) |
| `confidence_level` | REAL | Statistical confidence (0.0-1.0) |

---

### Table 2: `player_ratings` (Phase 2)

**Purpose:** Store role-normalized ratings for each player

```sql
CREATE TABLE IF NOT EXISTS player_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Player identification
    player_guid TEXT NOT NULL UNIQUE,
    
    -- Overall ratings
    overall_rating REAL DEFAULT 1500,
    overall_confidence REAL DEFAULT 1.0,
    
    -- Class-specific ratings
    medic_rating REAL DEFAULT 1500,
    medic_games INTEGER DEFAULT 0,
    engineer_rating REAL DEFAULT 1500,
    engineer_games INTEGER DEFAULT 0,
    soldier_rating REAL DEFAULT 1500,
    soldier_games INTEGER DEFAULT 0,
    fieldops_rating REAL DEFAULT 1500,
    fieldops_games INTEGER DEFAULT 0,
    covert_rating REAL DEFAULT 1500,
    covert_games INTEGER DEFAULT 0,
    
    -- Map-specific ratings (top maps)
    goldrush_rating REAL DEFAULT 1500,
    supply_rating REAL DEFAULT 1500,
    radar_rating REAL DEFAULT 1500,
    sw_goldrush_rating REAL DEFAULT 1500,
    adlernest_rating REAL DEFAULT 1500,
    
    -- Performance metrics
    games_played INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    win_rate REAL DEFAULT 0,
    
    -- Normalized performance score
    normalized_score REAL DEFAULT 0,
    performance_percentile REAL DEFAULT 0,
    
    -- Metadata
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(player_guid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ratings_overall 
ON player_ratings(overall_rating DESC);

CREATE INDEX IF NOT EXISTS idx_ratings_score 
ON player_ratings(normalized_score DESC);

CREATE INDEX IF NOT EXISTS idx_ratings_games 
ON player_ratings(games_played DESC);
```

**Column Descriptions:**

| Column | Type | Description |
|--------|------|-------------|
| `overall_rating` | REAL | ELO-style rating (1500 = average) |
| `medic_rating` | REAL | Class-specific rating for medic |
| `normalized_score` | REAL | Role-normalized performance score |
| `performance_percentile` | REAL | Percentile rank (0-100) |

---

### Table 3: `proximity_events` (Phase 3 - Optional)

**Purpose:** Store proximity tracking data from Lua script

```sql
CREATE TABLE IF NOT EXISTS proximity_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Session linkage
    session_id INTEGER NOT NULL,
    
    -- Player pair
    player_a_guid TEXT NOT NULL,
    player_b_guid TEXT NOT NULL,
    
    -- Proximity metrics
    time_near_seconds REAL DEFAULT 0,
    shared_combat_events INTEGER DEFAULT 0,
    
    -- Derived metrics
    combat_proximity_score REAL DEFAULT 0,
    support_rating REAL DEFAULT 0,
    
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    UNIQUE(session_id, player_a_guid, player_b_guid)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_proximity_session 
ON proximity_events(session_id);

CREATE INDEX IF NOT EXISTS idx_proximity_players 
ON proximity_events(player_a_guid, player_b_guid);

CREATE INDEX IF NOT EXISTS idx_proximity_score 
ON proximity_events(combat_proximity_score DESC);
```

**Column Descriptions:**

| Column | Type | Description |
|--------|------|-------------|
| `time_near_seconds` | REAL | Total time within proximity threshold |
| `shared_combat_events` | INT | Number of crossfire/combat events |
| `combat_proximity_score` | REAL | Calculated teamwork score |

---

## 🔧 Migration Scripts

### Migration 1: Create player_synergies Table

**File:** `tools/migrations/001_create_player_synergies.py`

```python
"""
Migration 001: Create player_synergies table
Phase 1 - Synergy Detection
"""

import sqlite3
import os

DB_PATH = 'etlegacy_production.db'

def migrate():
    """Create player_synergies table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_synergies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_a_guid TEXT NOT NULL,
                player_b_guid TEXT NOT NULL,
                games_together INTEGER DEFAULT 0,
                games_same_team INTEGER DEFAULT 0,
                games_opposite_team INTEGER DEFAULT 0,
                wins_together INTEGER DEFAULT 0,
                losses_together INTEGER DEFAULT 0,
                avg_kills_together REAL DEFAULT 0,
                avg_deaths_together REAL DEFAULT 0,
                avg_damage_together REAL DEFAULT 0,
                avg_objectives_together REAL DEFAULT 0,
                avg_kills_a_solo REAL DEFAULT 0,
                avg_deaths_a_solo REAL DEFAULT 0,
                avg_damage_a_solo REAL DEFAULT 0,
                avg_kills_b_solo REAL DEFAULT 0,
                avg_deaths_b_solo REAL DEFAULT 0,
                avg_damage_b_solo REAL DEFAULT 0,
                win_rate_together REAL DEFAULT 0,
                win_rate_a_solo REAL DEFAULT 0,
                win_rate_b_solo REAL DEFAULT 0,
                win_rate_boost REAL DEFAULT 0,
                performance_boost_a REAL DEFAULT 0,
                performance_boost_b REAL DEFAULT 0,
                performance_boost_avg REAL DEFAULT 0,
                synergy_score REAL DEFAULT 0,
                confidence_level REAL DEFAULT 0,
                last_played_together TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_a_guid, player_b_guid)
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_player_a 
            ON player_synergies(player_a_guid)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_player_b 
            ON player_synergies(player_b_guid)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_score 
            ON player_synergies(synergy_score DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_synergies_games 
            ON player_synergies(games_same_team DESC)
        ''')
        
        conn.commit()
        
        # Verify
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='player_synergies'")
        if cursor.fetchone()[0] == 1:
            print("✅ Migration 001 complete: player_synergies table created")
            return True
        else:
            print("❌ Migration 001 failed: table not created")
            return False
    
    except Exception as e:
        print(f"❌ Migration 001 error: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

def rollback():
    """Rollback migration (drop table)"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('DROP TABLE IF EXISTS player_synergies')
        conn.commit()
        print("✅ Rolled back migration 001")
        return True
    except Exception as e:
        print(f"❌ Rollback error: {e}")
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'rollback':
        rollback()
    else:
        migrate()
```

---

### Migration 2: Add player_class Column & Create player_ratings

**File:** `tools/migrations/002_add_player_class_and_ratings.py`

```python
"""
Migration 002: Add player_class column and create player_ratings table
Phase 2 - Role Normalization
"""

import sqlite3
import os

DB_PATH = 'etlegacy_production.db'

def migrate():
    """Add player_class column and create player_ratings table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Part 1: Add player_class column to player_comprehensive_stats
        cursor.execute("PRAGMA table_info(player_comprehensive_stats)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'player_class' not in columns:
            cursor.execute('''
                ALTER TABLE player_comprehensive_stats
                ADD COLUMN player_class TEXT DEFAULT 'unknown'
            ''')
            print("✅ Added player_class column")
        else:
            print("⏭️  player_class column already exists")
        
        # Part 2: Create player_ratings table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_guid TEXT NOT NULL UNIQUE,
                overall_rating REAL DEFAULT 1500,
                overall_confidence REAL DEFAULT 1.0,
                medic_rating REAL DEFAULT 1500,
                medic_games INTEGER DEFAULT 0,
                engineer_rating REAL DEFAULT 1500,
                engineer_games INTEGER DEFAULT 0,
                soldier_rating REAL DEFAULT 1500,
                soldier_games INTEGER DEFAULT 0,
                fieldops_rating REAL DEFAULT 1500,
                fieldops_games INTEGER DEFAULT 0,
                covert_rating REAL DEFAULT 1500,
                covert_games INTEGER DEFAULT 0,
                goldrush_rating REAL DEFAULT 1500,
                supply_rating REAL DEFAULT 1500,
                radar_rating REAL DEFAULT 1500,
                sw_goldrush_rating REAL DEFAULT 1500,
                adlernest_rating REAL DEFAULT 1500,
                games_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0,
                normalized_score REAL DEFAULT 0,
                performance_percentile REAL DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(player_guid)
            )
        ''')
        
        # Create indexes
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ratings_overall 
            ON player_ratings(overall_rating DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ratings_score 
            ON player_ratings(normalized_score DESC)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_ratings_games 
            ON player_ratings(games_played DESC)
        ''')
        
        conn.commit()
        print("✅ Migration 002 complete: player_class column + player_ratings table created")
        return True
    
    except Exception as e:
        print(f"❌ Migration 002 error: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
```

---

### Migration 3: Create proximity_events Table

**File:** `tools/migrations/003_create_proximity_events.py`

```python
"""
Migration 003: Create proximity_events table
Phase 3 - Proximity Tracking (OPTIONAL)
"""

import sqlite3
import os

DB_PATH = 'etlegacy_production.db'

def migrate():
    """Create proximity_events table"""
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS proximity_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                player_a_guid TEXT NOT NULL,
                player_b_guid TEXT NOT NULL,
                time_near_seconds REAL DEFAULT 0,
                shared_combat_events INTEGER DEFAULT 0,
                combat_proximity_score REAL DEFAULT 0,
                support_rating REAL DEFAULT 0,
                FOREIGN KEY (session_id) REFERENCES sessions(id),
                UNIQUE(session_id, player_a_guid, player_b_guid)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_proximity_session 
            ON proximity_events(session_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_proximity_players 
            ON proximity_events(player_a_guid, player_b_guid)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_proximity_score 
            ON proximity_events(combat_proximity_score DESC)
        ''')
        
        conn.commit()
        print("✅ Migration 003 complete: proximity_events table created")
        return True
    
    except Exception as e:
        print(f"❌ Migration 003 error: {e}")
        conn.rollback()
        return False
    
    finally:
        conn.close()

if __name__ == '__main__':
    migrate()
```

---

## 🚀 Running Migrations

### All At Once

```bash
# Run all migrations
python tools/migrations/001_create_player_synergies.py
python tools/migrations/002_add_player_class_and_ratings.py
python tools/migrations/003_create_proximity_events.py  # Optional
```

### One At A Time (Recommended)

```bash
# Phase 1 only
python tools/migrations/001_create_player_synergies.py

# Phase 2 (after Phase 1 complete)
python tools/migrations/002_add_player_class_and_ratings.py

# Phase 3 (optional, after Phase 2)
python tools/migrations/003_create_proximity_events.py
```

---

## 📊 Verifying Schema

**Check all tables exist:**

```python
import sqlite3

conn = sqlite3.connect('etlegacy_production.db')
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print("Existing tables:")
for table in sorted(tables):
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    count = cursor.fetchone()[0]
    print(f"  {table}: {count} rows")

conn.close()
```

**Expected output:**

```
Existing tables:
  player_aliases: 45 rows
  player_comprehensive_stats: 12414 rows
  player_links: 8 rows
  player_ratings: 0 rows            # NEW (Phase 2)
  player_synergies: 0 rows          # NEW (Phase 1)
  processed_files: 42 rows
  proximity_events: 0 rows          # NEW (Phase 3)
  session_teams: 2856 rows
  sessions: 428 rows
  weapon_comprehensive_stats: 8234 rows
```

---

## 📈 Database Growth Estimates

### Current Size
- Database: ~15 MB
- Records: 12,414 player stats

### After Phase 1
- `player_synergies`: ~400-900 rows (30 players = 435 pairs)
- Growth: +0.5 MB

### After Phase 2
- `player_ratings`: ~30 rows (one per player)
- `player_class` column: negligible
- Growth: +0.1 MB

### After Phase 3 (Optional)
- `proximity_events`: ~1,000 rows per session
- Growth: +5-10 MB over time

### Total Estimated Size
- Current: ~15 MB
- After Phase 1+2: ~16 MB
- After Phase 3: ~25-30 MB (long term)

---

## 🔄 Maintenance

### Regular Tasks

```python
# Recalculate all synergies (weekly)
python analytics/recalculate_synergies.py

# Update player ratings (daily)
python analytics/update_ratings.py

# Clean old proximity data (monthly, Phase 3 only)
python analytics/cleanup_proximity.py --older-than 90
```

---

## 🎯 Summary

✅ **3 new tables** (4 if Phase 3)  
✅ **Backward compatible** (no changes to existing tables)  
✅ **Migration scripts** provided  
✅ **Minimal storage growth** (<2 MB for Phase 1+2)

**Next:** Implement Phase 1 and run migration 001!
