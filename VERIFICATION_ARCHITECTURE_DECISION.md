# 🔒 Data Integrity Verification - Architecture Decision

## The Question: Where Should Verification Live?

### Option 1: SSH Monitor (monitor_stats.py)
### Option 2: Database Manager (postgresql_database_manager.py)
### Option 3: Parser (c0rnp0rn_stats_parser.py)
### Option 4: All of the Above (Defense in Depth)

---

## 🏗️ Architecture Analysis

### Current Data Flow:
```
Server creates file
    ↓
SSH Monitor detects new file
    ↓
SSH Monitor downloads file
    ↓
SSH Monitor calls: database_manager.process_file(filepath)
    ↓
Database Manager calls: parser.parse_file(filepath)
    ↓
Database Manager validates parsed data
    ↓
Database Manager saves to PostgreSQL
    ↓
Database Manager logs result
```

---

## 🎯 Responsibility Assignment

### **SSH Monitor** (`monitor_stats.py`)
**Responsibilities:**
- ✅ Detect new files on server
- ✅ Download files via SCP
- ✅ Verify file exists locally after download
- ✅ Call database_manager.process_file()
- ❌ **Should NOT verify database contents** (not its job!)

**What it SHOULD verify:**
```python
# File integrity during download
local_file_size = os.path.getsize(local_path)
if local_file_size == 0:
    logger.error(f"Downloaded file is empty: {local_path}")
    return False

# File is readable
try:
    with open(local_path, 'r') as f:
        first_line = f.readline()
except Exception as e:
    logger.error(f"Cannot read downloaded file: {e}")
    return False
```

**What it should NOT do:**
- ❌ Parse the file (parser's job)
- ❌ Validate stats (database manager's job)
- ❌ Query database to verify inserts (database manager's job)

---

### **Parser** (`c0rnp0rn_stats_parser.py`)
**Responsibilities:**
- ✅ Parse text file into structured dict
- ✅ Extract all 52 player fields
- ✅ Extract weapon stats
- ✅ Basic type conversion (string → int, etc.)
- ⚠️ **Light validation during parsing**

**What it SHOULD verify:**
```python
def parse_file(self, filepath):
    # ... parsing logic ...
    
    # Verify during parsing
    for player in players:
        # Type validation
        if not isinstance(player['kills'], int):
            raise ParserError(f"Kills must be int, got {type(player['kills'])}")
        
        # Range validation
        if player['kills'] < 0:
            raise ParserError(f"Negative kills for {player['name']}")
        
        # Logical validation
        if player['headshots'] > player['kills']:
            logger.warning(f"More headshots than kills for {player['name']}")
    
    # Verify structure
    if not players:
        raise ParserError("No players found in file")
    
    return {
        'success': True,
        'players': players,
        'weapons': weapons,
        ...
    }
```

**What it should NOT do:**
- ❌ Database queries (no DB connection)
- ❌ File downloading (SSH monitor's job)
- ❌ Verify data after database insert (database manager's job)

---

### **Database Manager** (`postgresql_database_manager.py`)
**Responsibilities:**
- ✅ Call parser to get structured data
- ✅ Validate parsed data (7-check system)
- ✅ Calculate gaming_session_id
- ✅ Insert into PostgreSQL
- ✅ **VERIFY INSERTS** ← THIS IS THE KEY!
- ✅ Mark file as processed
- ✅ Comprehensive logging

**What it SHOULD verify:**
```python
async def process_file(self, filepath: str) -> bool:
    # 1. Parse
    parsed_data = self.parser.parse_file(filepath)
    
    # 2. Validate parsed structure
    validation_result = self._validate_parsed_data(parsed_data)
    if not validation_result.passed:
        logger.error(f"Validation failed: {validation_result.errors}")
        return False
    
    # 3. Database operations
    async with self.pool.acquire() as conn:
        async with conn.transaction():
            # Insert round
            round_id = await conn.fetchval(
                "INSERT INTO rounds (...) VALUES (...) RETURNING round_id"
            )
            
            # Insert players WITH VERIFICATION
            for player in parsed_data['players']:
                inserted = await conn.fetchrow("""
                    INSERT INTO player_comprehensive_stats 
                    (round_id, player_name, headshots, kills, ...)
                    VALUES ($1, $2, $3, $4, ...)
                    RETURNING player_stat_id, headshots, kills
                """, round_id, player['name'], player['headshots'], player['kills'], ...)
                
                # ✅ VERIFY IMMEDIATELY
                if inserted['headshots'] != player['headshots']:
                    raise DatabaseIntegrityError(
                        f"Headshots mismatch for {player['name']}: "
                        f"tried to save {player['headshots']}, "
                        f"DB returned {inserted['headshots']}"
                    )
            
            # Insert weapons...
            
            # ✅ AGGREGATE VERIFICATION
            db_total_kills = await conn.fetchval(
                "SELECT SUM(kills) FROM player_comprehensive_stats WHERE round_id = $1",
                round_id
            )
            expected_total_kills = sum(p['kills'] for p in parsed_data['players'])
            
            if db_total_kills != expected_total_kills:
                raise DatabaseIntegrityError(
                    f"Kill totals don't match! Expected {expected_total_kills}, got {db_total_kills}"
                )
        
        # Transaction committed here
        
        # ✅ POST-COMMIT VERIFICATION (optional, paranoid mode)
        await self._verify_post_commit(conn, round_id, parsed_data)
    
    return True
```

**This is where verification MUST happen!** ✅

---

## 🚨 Why Database Manager is the Right Place

### 1. **It Has Database Access**
- Can use `RETURNING` clause to read back inserted values
- Can run aggregate queries to verify totals
- Can compare what was inserted vs what's in DB

### 2. **It Controls the Transaction**
- Can rollback if verification fails
- Can ensure atomicity (all or nothing)
- Can prevent corrupted data from being committed

### 3. **It Has Context**
- Knows what was parsed (source data)
- Knows what was inserted (operation)
- Can compare source vs destination

### 4. **It's the Last Line of Defense**
- SSH monitor verified file download ✓
- Parser verified data structure ✓
- Database manager verifies **data persistence** ✓

---

## 🛡️ Defense in Depth - Multi-Layer Verification

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: SSH Monitor                                        │
│ ✓ File exists on server                                    │
│ ✓ File downloaded successfully                             │
│ ✓ File is not empty                                        │
│ ✓ File is readable                                         │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Parser                                             │
│ ✓ File format is valid                                     │
│ ✓ All required fields present                              │
│ ✓ Data types are correct (int, str, float)                 │
│ ✓ No negative values                                       │
│ ✓ Basic logic checks (headshots ≤ kills)                   │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Database Manager - PRE-INSERT Validation          │
│ ✓ 7-check validation system                                │
│ ✓ Kill/death balance (±5 tolerance)                        │
│ ✓ Team distribution (Round 1 only)                         │
│ ✓ Minimum player count (≥4)                                │
│ ✓ Accuracy calculations correct                            │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Database Manager - INSERT Verification            │
│ ✓ Read back inserted values (RETURNING clause)             │
│ ✓ Compare inserted vs expected                             │
│ ✓ Verify each player's stats match                         │
│ ✓ Verify each weapon's stats match                         │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 5: Database Manager - POST-COMMIT Verification       │
│ ✓ Re-query database for round                              │
│ ✓ Compare aggregate totals                                 │
│ ✓ Verify cross-table consistency                           │
│ ✓ Check for orphaned records                               │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ Layer 6: PostgreSQL Constraints (Database Level)           │
│ ✓ NOT NULL constraints                                     │
│ ✓ CHECK constraints (kills >= 0, etc.)                     │
│ ✓ FOREIGN KEY constraints                                  │
│ ✓ UNIQUE constraints                                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 What Each Component Should Verify

### **SSH Monitor** (`monitor_stats.py`)
```python
def download_file(self, remote_path, local_path):
    # Download via SCP
    scp.get(remote_path, local_path)
    
    # ✅ Verify file downloaded
    if not os.path.exists(local_path):
        raise DownloadError("File not found after download")
    
    # ✅ Verify file size
    if os.path.getsize(local_path) == 0:
        raise DownloadError("Downloaded file is empty")
    
    # ✅ Verify file readable
    with open(local_path, 'r') as f:
        f.read(1)  # Try to read first byte
    
    return True
```

### **Parser** (`c0rnp0rn_stats_parser.py`)
```python
def parse_file(self, filepath):
    # Parse file
    players = self._parse_players(content)
    
    # ✅ Verify structure
    for player in players:
        if 'player_guid' not in player:
            raise ParserError("Missing player_guid")
        if player['kills'] < 0:
            raise ParserError("Negative kills")
        if player['headshots'] > player['kills']:
            logger.warning("More headshots than kills (possible file corruption)")
    
    return {'success': True, 'players': players, ...}
```

### **Database Manager** (`postgresql_database_manager.py`)
```python
async def process_file(self, filepath):
    # Parse
    parsed_data = self.parser.parse_file(filepath)
    
    # ✅ Pre-insert validation
    if not self._validate_parsed_data(parsed_data):
        return False
    
    async with conn.transaction():
        # Insert with verification
        for player in parsed_data['players']:
            # ✅ Use RETURNING to verify
            inserted = await conn.fetchrow(
                "INSERT ... RETURNING *"
            )
            
            # ✅ Verify match
            if inserted['headshots'] != player['headshots']:
                raise DatabaseIntegrityError("Insert verification failed")
        
        # ✅ Aggregate verification
        if not await self._verify_aggregates(conn, round_id, parsed_data):
            raise DatabaseIntegrityError("Aggregate verification failed")
    
    # ✅ Post-commit verification
    if not await self._verify_post_commit(conn, round_id):
        logger.error("Post-commit verification failed!")
    
    return True
```

---

## 🎯 Recommended Implementation

### **Add to `postgresql_database_manager.py`:**

1. **Method: `_verify_insert()`**
   - Use `RETURNING` clause
   - Compare inserted vs expected
   - Raise error on mismatch

2. **Method: `_verify_aggregates()`**
   - Sum all kills, deaths, headshots in DB
   - Compare with parsed totals
   - Allow ±5 tolerance

3. **Method: `_verify_cross_table()`**
   - Verify weapon kills sum to player kills
   - Check no orphaned weapon records
   - Verify GUIDs match between tables

4. **Method: `_verify_post_commit()` (optional)**
   - Re-query entire round from DB
   - Deep comparison with source data
   - Log any discrepancies

### **Update `process_file()` to call these methods**

---

## 🚫 What NOT to Do

### **DON'T add verification to SSH Monitor**
```python
# ❌ BAD - SSH monitor querying database
def process_new_file(self, filepath):
    database_manager.process_file(filepath)
    
    # ❌ DON'T DO THIS - not SSH monitor's responsibility!
    conn = psycopg2.connect(...)
    result = conn.execute("SELECT * FROM rounds WHERE ...")
    verify_data(result)
```

### **DON'T add database queries to Parser**
```python
# ❌ BAD - parser with database connection
class Parser:
    def parse_file(self, filepath):
        # ... parse ...
        
        # ❌ DON'T DO THIS - parser should be stateless!
        conn = psycopg2.connect(...)
        verify_in_db(parsed_data)
```

---

## ✅ Summary - Where Verification Goes

| Component | Verification Responsibility | Implementation |
|-----------|----------------------------|----------------|
| **SSH Monitor** | File download integrity | File exists, readable, non-empty |
| **Parser** | Data structure validity | Required fields, types, basic logic |
| **Database Manager** | **Data persistence integrity** | **RETURNING clause, aggregates, post-commit** |
| **PostgreSQL** | Constraint enforcement | NOT NULL, CHECK, FK, UNIQUE |

### **The Answer:**
**Implement verification in `postgresql_database_manager.py`** - specifically in the `process_file()` method after each INSERT and after COMMIT.

**NOT in SSH monitor** - it's just responsible for downloading files, not verifying database contents.

---

## 🔧 Next Steps

1. Add `_verify_insert()` method to DatabaseManager
2. Add `_verify_aggregates()` method to DatabaseManager
3. Add `_verify_cross_table()` method to DatabaseManager
4. Update `process_file()` to call verification after inserts
5. Add comprehensive logging for verification results
6. Test with a few files to ensure it works
7. Deploy to production with verification enabled

Want me to implement this in your `postgresql_database_manager.py`? 🎯
