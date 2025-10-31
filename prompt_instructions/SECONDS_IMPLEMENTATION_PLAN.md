# 🎯 SECONDS-BASED TIME IMPLEMENTATION

**Date:** October 3, 2025  
**Decision:** Community vote - Convert ALL time to SECONDS  
**Status:** Ready to implement

---

## 📢 Community Decision

### What They Said:

**SuperBoyy:**
> "0.1 minute je 6 sekund. Mal vec decimalk rabis. Jz vse v sekunde spremenim."
> 
> (0.1 minute is 6 seconds. You need more decimals. I convert everything to seconds.)

**vid:**
> "sm glih hotu rect, convertej v sekunde pa bo lazi"
>
> (I was just about to say, convert to seconds and it will be clearer)

**ciril:**
> "zivcira me tole krozn tok pa take"
>
> (This decimal stuff is annoying me)

### Unanimous Decision: **USE SECONDS!** ⏱️

---

## 🔥 Why Seconds Solve Everything

### Problem with Decimal Minutes:
```
File time: 3:51 = 3.85 minutes
Lua rounded: 3.9 minutes
Difference: 0.05 minutes

What is 0.05 minutes anyway? 
Users have to calculate: 0.05 * 60 = 3 seconds 🤯
```

### Solution with Seconds:
```
File time: 3:51 = 231 seconds ✅
Lua rounded: 3.9 min = 234 seconds ✅
Difference: 3 seconds ← CLEAR!
```

### Benefits:
1. ✅ **No decimals** - Integer seconds are exact
2. ✅ **Human-readable** - "231 seconds" or "3:51" 
3. ✅ **No rounding errors** - 231 is 231, period
4. ✅ **Matches SuperBoyy** - He uses seconds
5. ✅ **Database efficiency** - Integers are smaller/faster than floats
6. ✅ **No confusion** - 0.1 minute = 6 seconds confusion GONE

---

## 📋 Implementation Plan

### Phase 1: Database Schema Changes

#### Update Tables:

```sql
-- Add new seconds-based columns
ALTER TABLE player_comprehensive_stats
ADD COLUMN time_played_seconds INTEGER DEFAULT 0;

ALTER TABLE sessions
ADD COLUMN actual_time_seconds INTEGER DEFAULT 0;

-- We can keep old time_played_minutes for backward compatibility
-- Or drop it after migration
```

#### Migration Script:

```python
def migrate_to_seconds():
    """Convert all existing time_played_minutes to seconds"""
    conn = sqlite3.connect('etlegacy_production.db')
    c = conn.cursor()
    
    # Update player stats
    c.execute('''
        UPDATE player_comprehensive_stats
        SET time_played_seconds = CAST(time_played_minutes * 60 AS INTEGER)
        WHERE time_played_minutes > 0
    ''')
    
    # Update sessions - parse MM:SS from actual_time
    sessions = c.execute('SELECT session_id, actual_time FROM sessions').fetchall()
    for session_id, actual_time in sessions:
        if ':' in actual_time:
            parts = actual_time.split(':')
            seconds = int(parts[0]) * 60 + int(parts[1])
        else:
            seconds = int(float(actual_time) * 60) if actual_time else 0
        
        c.execute('''
            UPDATE sessions 
            SET actual_time_seconds = ? 
            WHERE session_id = ?
        ''', (seconds, session_id))
    
    conn.commit()
    print("✅ Migrated all times to seconds!")
```

### Phase 2: Parser Changes

#### File: `bot/community_stats_parser.py`

**BEFORE (Decimal Minutes):**
```python
# Parse time to seconds
round_time_seconds = self.parse_time_to_seconds(actual_time)
round_time_minutes = round_time_seconds / 60.0  # Convert to decimal

# Calculate DPM
for player in players:
    damage_given = player.get('damage_given', 0)
    player['dpm'] = damage_given / round_time_minutes
    player['time_played_minutes'] = round_time_minutes
```

**AFTER (Seconds-Based):**
```python
# Parse time to seconds (KEEP AS SECONDS!)
round_time_seconds = self.parse_time_to_seconds(actual_time)

# Calculate DPM using seconds
for player in players:
    damage_given = player.get('damage_given', 0)
    
    # DPM = damage per 60 seconds
    if round_time_seconds > 0:
        player['dpm'] = (damage_given * 60) / round_time_seconds
    else:
        player['dpm'] = 0.0
    
    # Store time in SECONDS (integer!)
    player['time_played_seconds'] = round_time_seconds
    
    # Also store display format for humans
    player['time_display'] = f"{round_time_seconds // 60}:{round_time_seconds % 60:02d}"
```

#### Round 2 Differential Changes:

**BEFORE:**
```python
if key == 'time_played_minutes':
    r2_time = r2_obj.get('time_played_minutes', 0)
    r1_time = r1_obj.get('time_played_minutes', 0)
    differential_player['objective_stats']['time_played_minutes'] = max(0, r2_time - r1_time)
```

**AFTER:**
```python
if key == 'time_played_seconds':
    r2_time = r2_obj.get('time_played_seconds', 0)
    r1_time = r1_obj.get('time_played_seconds', 0)
    differential_seconds = max(0, r2_time - r1_time)
    
    # Store seconds
    differential_player['objective_stats']['time_played_seconds'] = differential_seconds
    
    # Also create display format
    minutes = differential_seconds // 60
    seconds = differential_seconds % 60
    differential_player['time_display'] = f"{minutes}:{seconds:02d}"
```

### Phase 3: Bot Display Changes

#### File: `bot/ultimate_bot.py`

**BEFORE:**
```python
time_played = player['time_played_minutes']  # 3.85
display = f"Time: {time_played:.1f} min"  # "Time: 3.9 min" 🤯
```

**AFTER:**
```python
time_seconds = player['time_played_seconds']  # 231
minutes = time_seconds // 60  # 3
seconds = time_seconds % 60   # 51
display = f"Time: {minutes}:{seconds:02d}"  # "Time: 3:51" ✅

# Alternative: use pre-calculated display format
display = f"Time: {player['time_display']}"  # "Time: 3:51" ✅
```

#### DPM Query Changes:

**BEFORE:**
```sql
SELECT 
    SUM(damage_given) as total_damage,
    SUM(time_played_minutes) as total_minutes,
    SUM(damage_given) / NULLIF(SUM(time_played_minutes), 0) as dpm
FROM player_comprehensive_stats
WHERE player_name = 'vid'
```

**AFTER:**
```sql
SELECT 
    SUM(damage_given) as total_damage,
    SUM(time_played_seconds) as total_seconds,
    (SUM(damage_given) * 60.0) / NULLIF(SUM(time_played_seconds), 0) as dpm
FROM player_comprehensive_stats
WHERE player_name = 'vid'
```

### Phase 4: Discord Display Format

**Create Helper Function:**
```python
def seconds_to_display(seconds: int) -> str:
    """Convert seconds to MM:SS display format"""
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"

def seconds_to_hms(seconds: int) -> str:
    """Convert seconds to H:MM:SS for long times"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"
```

**Usage in Bot:**
```python
# Player stats embed
time_seconds = 14523  # Total playtime
time_display = seconds_to_hms(time_seconds)  # "4:02:03"

embed.add_field(
    name="⏱️ Time Played",
    value=time_display,  # Shows "4:02:03" not "242.05 minutes"
    inline=True
)

# Session stats
round_time = 231  # seconds
round_display = seconds_to_display(round_time)  # "3:51"

embed.add_field(
    name="Round Time",
    value=round_display,  # Shows "3:51" not "3.85 min"
    inline=True
)
```

---

## 🧪 Testing Plan

### Test 1: Parse October 2nd Files
```python
# Test that parser stores seconds correctly
parser = C0RNP0RN3StatsParser()
result = parser.parse_stats_file('local_stats/2025-10-02-211808-etl_adlernest-round-1.txt')

for player in result['players']:
    time_sec = player.get('time_played_seconds')
    assert time_sec == 231, f"Expected 231 seconds, got {time_sec}"
    assert player['time_display'] == "3:51"
    print(f"✅ {player['name']}: {time_sec}s ({player['time_display']})")
```

### Test 2: Round 2 Differential
```python
# Test R2 differential preserves seconds
r1_result = parser.parse_stats_file('.../round-1.txt')
r2_result = parser.parse_stats_file('.../round-2.txt')

r1_player = next(p for p in r1_result['players'] if p['name'] == 'vid')
r2_player = next(p for p in r2_result['players'] if p['name'] == 'vid')

r1_seconds = r1_player['time_played_seconds']  # 231
r2_seconds = r2_player['time_played_seconds']  # Should be ~228

assert r2_seconds > 0, "R2 differential lost time data!"
assert 200 < r2_seconds < 250, f"R2 time looks wrong: {r2_seconds}s"
print(f"✅ R2 differential: {r2_seconds}s ({r2_player['time_display']})")
```

### Test 3: DPM Calculation
```python
# Verify DPM matches SuperBoyy's method
damage = 1328
time_seconds = 231

# Our calculation
dpm = (damage * 60) / time_seconds  # 344.94

# Verify
expected_dpm = 1328 / (231 / 60.0)  # Same as above
assert abs(dpm - expected_dpm) < 0.01

print(f"✅ DPM: {dpm:.2f} (damage: {damage}, time: {time_seconds}s)")
```

### Test 4: Database Query
```sql
-- Verify database has seconds
SELECT 
    player_name,
    time_played_seconds,
    damage_given,
    dpm
FROM player_comprehensive_stats
WHERE session_date = '2025-10-02'
AND time_played_seconds > 0  -- Should have NO zeros after fix!
LIMIT 5;
```

---

## 📊 Expected Results

### Before (Decimal Minutes):
```
vid Round 1:
  Time: 3.85 minutes 🤯
  Damage: 1328
  DPM: 344.94

SuperBoyy Round 1:
  Time: 3.9 minutes 🤯
  Damage: 1328
  DPM: 340.51

Difference: 4.43 DPM (1.3%) ❌
```

### After (Seconds):
```
vid Round 1:
  Time: 231 seconds (3:51) ✅
  Damage: 1328
  DPM: 344.94

SuperBoyy Round 1:
  Time: 234 seconds (3:54) ✅
  Damage: 1328
  DPM: 340.51

Difference: 3 seconds (1.3%) ← CLEAR!
```

**Both values are now CRYSTAL CLEAR:**
- vid uses exact file time: **231 seconds**
- SuperBoyy uses rounded time: **234 seconds**
- Difference: **3 seconds** (not confusing 0.05 minutes!)

---

## 🎯 Rollout Plan

### Step 1: Create Migration Script
- Add time_played_seconds columns
- Convert existing data
- Verify no data loss

### Step 2: Update Parser
- Change to seconds-based calculation
- Test with October 2nd files
- Verify Round 2 differential works

### Step 3: Re-import October 2nd
- Import with new parser
- Verify all times in seconds
- Check DPM calculations

### Step 4: Update Bot
- Change queries to use seconds
- Update display to show MM:SS
- Test all commands

### Step 5: Full Database Re-import
- Import all 3,238 files with new parser
- Verify data integrity
- Deploy to production

---

## ✅ Success Criteria

1. ✅ All times stored as INTEGER seconds
2. ✅ No more decimal minutes confusion
3. ✅ Discord displays MM:SS format (human-readable)
4. ✅ DPM calculations match SuperBoyy's method
5. ✅ Round 2 differential preserves time data
6. ✅ No time = 0 records (except for real 0:00 files)
7. ✅ Community happy with clarity

---

## 🎓 Why This Is Better

### Technical:
- Integers are faster and smaller than floats
- No floating-point rounding errors
- Perfect precision (231 = 231, always)

### User Experience:
- "3:51" is instantly understandable
- "231 seconds" is clear
- "3.85 minutes" confuses everyone

### Compatibility:
- Matches SuperBoyy's method
- Matches in-game display format (MM:SS)
- Works with all existing calculations

---

**Community approved! Let's implement! 🚀**
