# 🔄 SQLite ↔️ PostgreSQL SQL Compatibility Reference

**Quick reference guide for converting SQL syntax**

---

## 📋 Query Placeholders

| SQLite | PostgreSQL | Adapter Handles? |
|--------|------------|------------------|
| `?` | `$1, $2, $3, ...` | ✅ Yes (automatic) |

**Example**:
```sql
-- SQLite (input)
SELECT * FROM players WHERE guid = ? AND team = ?

-- PostgreSQL (after adapter translation)
SELECT * FROM players WHERE guid = $1 AND team = $2
```

**Note**: You write SQLite-style `?`, adapter converts automatically!

---

## 📅 Date/Time Functions

### Current Timestamp

| SQLite | PostgreSQL | Compatible? | Action |
|--------|------------|-------------|--------|
| `datetime('now')` | `CURRENT_TIMESTAMP` or `NOW()` | ❌ No | Manual fix |

**Locations to Fix**: 4 occurrences

```sql
-- BEFORE (SQLite)
INSERT INTO players (name, created_at) VALUES (?, datetime('now'))

-- AFTER (PostgreSQL-compatible)
INSERT INTO players (name, created_at) VALUES (?, CURRENT_TIMESTAMP)
```

### Date Arithmetic

| SQLite | PostgreSQL | Compatible? | Action |
|--------|------------|-------------|--------|
| `date('now', '-30 days')` | `CURRENT_DATE - INTERVAL '30 days'` | ❌ No | Manual fix |
| `date('now', '+7 days')` | `CURRENT_DATE + INTERVAL '7 days'` | ❌ No | Manual fix |

**Locations to Fix**: 1 occurrence

```sql
-- BEFORE (SQLite)
HAVING MAX(p.round_date) >= date('now', '-30 days')

-- AFTER (PostgreSQL-compatible)
HAVING MAX(p.round_date) >= CURRENT_DATE - INTERVAL '30 days'
```

### Date Extraction

| SQLite | PostgreSQL | Compatible? | Action |
|--------|------------|-------------|--------|
| `DATE(column)` | `DATE(column)` | ✅ Yes | None |

```sql
-- Works in both!
SELECT DISTINCT DATE(round_date) as date FROM rounds
WHERE DATE(round_date) = ?
GROUP BY DATE(round_date)
```

### String Substring

| SQLite | PostgreSQL | Compatible? | Action |
|--------|------------|-------------|--------|
| `substr(text, pos, len)` | `SUBSTRING(text, pos, len)` or `substr()` | ✅ Yes | None |

```sql
-- Works in both! (PostgreSQL accepts substr as alias)
WHERE substr(round_date, 1, 10) = ?
SELECT DISTINCT substr(round_date, 1, 10) as date
```

---

## 🗄️ Schema Definitions

### Auto-Increment Primary Keys

| SQLite | PostgreSQL | Action |
|--------|------------|--------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | Schema conversion |

```sql
-- BEFORE (SQLite)
CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT
);

-- AFTER (PostgreSQL)
CREATE TABLE players (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);

-- OR (modern PostgreSQL)
CREATE TABLE players (
    id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(255)
);
```

### Data Types

| SQLite | PostgreSQL | Notes |
|--------|------------|-------|
| `TEXT` | `VARCHAR(n)` or `TEXT` | Review case-by-case |
| `INTEGER` | `INTEGER` or `BIGINT` | Same |
| `REAL` | `REAL` or `DOUBLE PRECISION` | Same |
| `BLOB` | `BYTEA` | Binary data |

**Type Recommendations**:
```sql
-- Names, short strings
player_name VARCHAR(255)

-- Long text (descriptions, notes)
notes TEXT

-- Timestamps
created_at TIMESTAMP
round_date TIMESTAMP

-- IDs
id SERIAL PRIMARY KEY
player_id INTEGER

-- Booleans
is_active BOOLEAN  -- PostgreSQL has native BOOLEAN type!

-- JSON data (PostgreSQL advantage!)
stats_json JSONB  -- Faster than JSON, supports indexing
```

### Default Values

| SQLite | PostgreSQL | Action |
|--------|------------|--------|
| `DEFAULT (datetime('now'))` | `DEFAULT CURRENT_TIMESTAMP` | Schema conversion |
| `DEFAULT 0` | `DEFAULT 0` | Same |
| `DEFAULT 'text'` | `DEFAULT 'text'` | Same |

---

## 🔑 Constraints & Indexes

### UNIQUE Constraints

**Same in both**:
```sql
-- Works in both
guid VARCHAR(50) NOT NULL UNIQUE

-- OR
CREATE UNIQUE INDEX idx_players_guid ON players(guid);
```

### Foreign Keys

**SQLite**: Must enable with PRAGMA  
**PostgreSQL**: Enabled by default

```sql
-- Works in both (but SQLite needs PRAGMA foreign_keys = ON)
CREATE TABLE player_stats (
    id SERIAL PRIMARY KEY,
    player_id INTEGER REFERENCES players(id) ON DELETE CASCADE
);
```

---

## 🔍 Query Functions

### String Operations

| Function | SQLite | PostgreSQL | Compatible? |
|----------|--------|------------|-------------|
| `LOWER()` | ✅ | ✅ | ✅ Yes |
| `UPPER()` | ✅ | ✅ | ✅ Yes |
| `LIKE` | ✅ | ✅ | ✅ Yes |
| `||` (concat) | ✅ | ✅ | ✅ Yes |
| `LENGTH()` | ✅ | ✅ | ✅ Yes |
| `TRIM()` | ✅ | ✅ | ✅ Yes |

### Aggregate Functions

| Function | SQLite | PostgreSQL | Compatible? |
|----------|--------|------------|-------------|
| `COUNT()` | ✅ | ✅ | ✅ Yes |
| `SUM()` | ✅ | ✅ | ✅ Yes |
| `AVG()` | ✅ | ✅ | ✅ Yes |
| `MAX()` | ✅ | ✅ | ✅ Yes |
| `MIN()` | ✅ | ✅ | ✅ Yes |
| `GROUP_CONCAT()` | ✅ | ❌ (use `STRING_AGG()`) | ⚠️ Different |

```sql
-- SQLite
SELECT GROUP_CONCAT(player_name, ', ') FROM players

-- PostgreSQL
SELECT STRING_AGG(player_name, ', ') FROM players
```

### Math Functions

| Function | SQLite | PostgreSQL | Compatible? |
|----------|--------|------------|-------------|
| `ROUND()` | ✅ | ✅ | ✅ Yes |
| `ABS()` | ✅ | ✅ | ✅ Yes |
| `RANDOM()` | ✅ | ✅ | ✅ Yes |
| `CAST()` | ✅ | ✅ | ✅ Yes |

---

## 🎯 Common Patterns in Our Codebase

### Pattern 1: Get Latest Session Date
```sql
-- Works in both!
SELECT DISTINCT DATE(round_date) as date 
FROM rounds 
ORDER BY date DESC 
LIMIT 1
```

### Pattern 2: Filter by Date
```sql
-- Works in both!
SELECT * FROM rounds
WHERE DATE(round_date) = ?
```

### Pattern 3: Count Players
```sql
-- Works in both!
SELECT COUNT(DISTINCT guid) as player_count
FROM player_comprehensive_stats
```

### Pattern 4: Get Player Stats
```sql
-- Works in both (after adapter translates ? to $1)
SELECT * FROM players
WHERE guid = ? OR LOWER(player_name) LIKE LOWER(?)
```

### Pattern 5: Insert New Record
```sql
-- BEFORE (SQLite-only)
INSERT INTO players (guid, name, created_at)
VALUES (?, ?, datetime('now'))

-- AFTER (Both)
INSERT INTO players (guid, name, created_at)
VALUES (?, ?, CURRENT_TIMESTAMP)
```

---

## ⚠️ PostgreSQL-Specific Gotchas

### 1. Case Sensitivity
**PostgreSQL**: Column/table names are case-insensitive UNLESS quoted

```sql
-- All the same in PostgreSQL
SELECT * FROM Players
SELECT * FROM players
SELECT * FROM PLAYERS

-- But this is DIFFERENT
SELECT * FROM "Players"  -- Must match exact case!
```

**Our approach**: Use lowercase always (matches SQLite behavior)

### 2. String Comparison
**PostgreSQL**: Single quotes for strings, double quotes for identifiers

```sql
-- CORRECT
WHERE player_name = 'John'

-- WRONG (double quotes mean column name)
WHERE player_name = "John"
```

### 3. Boolean Type
**PostgreSQL has native BOOLEAN**:
```sql
-- SQLite (uses INTEGER 0/1)
is_active INTEGER DEFAULT 0

-- PostgreSQL (native boolean)
is_active BOOLEAN DEFAULT FALSE
```

### 4. JSON Support
**PostgreSQL has superior JSON support**:
```sql
-- Can query JSON fields directly!
SELECT stats_json->'kills' as kills
FROM player_stats
WHERE (stats_json->>'team')::int = 1
```

---

## 📊 Performance Considerations

### Indexes
**PostgreSQL benefits MORE from indexes than SQLite**

```sql
-- Create indexes on frequently queried columns
CREATE INDEX idx_rounds_date ON rounds(round_date);
CREATE INDEX idx_stats_guid ON player_comprehensive_stats(guid);
CREATE INDEX idx_stats_round_id ON player_comprehensive_stats(round_id);

-- Composite indexes for common queries
CREATE INDEX idx_stats_guid_date ON player_comprehensive_stats(guid, round_date);
```

### Connection Pooling
**Critical for PostgreSQL, not needed for SQLite**

Our adapter handles this automatically:
- SQLite: Creates connection per query (lightweight)
- PostgreSQL: Uses connection pool (5-20 connections)

---

## 🔧 Quick Conversion Checklist

When migrating a query, check for:

- [ ] Placeholders: `?` → (adapter handles automatically)
- [ ] `datetime('now')` → `CURRENT_TIMESTAMP`
- [ ] `date('now', '-N days')` → `CURRENT_DATE - INTERVAL 'N days'`
- [ ] Data types in schema: `TEXT` → `VARCHAR` or `TEXT`
- [ ] Auto-increment: `AUTOINCREMENT` → `SERIAL`
- [ ] GROUP_CONCAT → `STRING_AGG` (if used)
- [ ] Boolean: `INTEGER 0/1` → `BOOLEAN` (optional optimization)

---

## 📚 Further Reading

**PostgreSQL Official Docs**:
- Date/Time Functions: https://www.postgresql.org/docs/current/functions-datetime.html
- String Functions: https://www.postgresql.org/docs/current/functions-string.html
- Data Types: https://www.postgresql.org/docs/current/datatype.html

**Migration Guides**:
- SQLite to PostgreSQL: https://wiki.postgresql.org/wiki/Converting_from_other_Databases_to_PostgreSQL

---

**Last Updated**: November 4, 2025  
**Maintained By**: Development Team
