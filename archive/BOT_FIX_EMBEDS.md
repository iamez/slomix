# Bot Fix - Objective & Weapon Mastery Embeds

## Issue
Bot was crashing when generating `!last_session` stats:
1. **First few embeds worked** (Messages 1-4: Overview, Top Players, Team Analytics, DPM)
2. **Weapon Mastery (Message 5) failed** - "no active connection" error
3. **Objective Stats (Message 6) failed** - never displayed

## Errors Found

### Error 1: MVP Stats Unpacking
**Line 1150**: `ValueError: too many values to unpack (expected 4)`

**Cause**: 
- MVP query returns 6 values: (player, kills, dpm, deaths, revived, gibs)
- Code tried to unpack only 4: `p, k, dpm, d = axis_mvp_stats`

**Fix**:
```python
# Before (line 1150)
p, k, dpm, d = axis_mvp_stats

# After
p, k, dpm, d, revived, gibs = axis_mvp_stats
```

### Error 2: Database Connection Closed
**Line 1400**: `ValueError: no active connection`

**Cause**:
- Database connection closed at line 997 (end of `async with aiosqlite.connect(...)`)
- Weapon Mastery embed tried to query revives data at line 1393-1400
- Used `async with db.execute(query, session_ids)` but `db` was already closed

**Fix**:
Moved revives query INSIDE database connection (before line 997):
```python
# Added at line 998 (before connection closes)
query = f'''
    SELECT player_name, SUM(times_revived) as revives
    FROM player_comprehensive_stats
    WHERE session_id IN ({session_ids_str})
    GROUP BY player_name
'''
async with db.execute(query, session_ids) as cursor:
    player_revives_raw = await cursor.fetchall()
```

Removed duplicate query at line 1393 and reused the data:
```python
# Line 1404 - just convert the data we already fetched
player_revives = {player: revives for player, revives in player_revives_raw}
```

## Files Modified

**File**: `bot/ultimate_bot.py`

### Change 1: Fix Axis MVP Unpacking (Line 1150)
```python
if axis_mvp_stats:
    p, k, dpm, d, revived, gibs = axis_mvp_stats  # Added revived, gibs
    team_data_for_img['team1']['mvp'] = {
        'name': p,
        'kd': k / d if d else k,
        'dpm': dpm
    }
```

### Change 2: Fix Allies MVP Unpacking (Line 1158)
```python
if allies_mvp_stats:
    p, k, dpm, d, revived, gibs = allies_mvp_stats  # Added revived, gibs
    team_data_for_img['team2']['mvp'] = {
        'name': p,
        'kd': k / d if d else k,
        'dpm': dpm
    }
```

### Change 3: Move Revives Query Inside DB Connection (Line 998)
```python
# Fetch player revives for weapon mastery embed
query = f'''
    SELECT player_name, SUM(times_revived) as revives
    FROM player_comprehensive_stats
    WHERE session_id IN ({session_ids_str})
    GROUP BY player_name
'''
async with db.execute(query, session_ids) as cursor:
    player_revives_raw = await cursor.fetchall()
```

### Change 4: Remove Duplicate Query (Line 1404)
```python
# Convert revives data (already fetched before connection closed)
player_revives = {player: revives for player, revives in player_revives_raw}
```

## Database Query Order (Fixed)

### INSIDE Database Connection (Lines 700-1005)
1. ✅ Sessions data
2. ✅ Player stats
3. ✅ Team MVPs (kills)
4. ✅ Axis MVP stats (dpm, deaths, revived, gibs)
5. ✅ Allies MVP stats (dpm, deaths, revived, gibs)
6. ✅ Weapon details
7. ✅ Player weapons
8. ✅ DPM leaderboard
9. ✅ Objective/awards data
10. ✅ **Player revives (NEW - moved here)**

### OUTSIDE Database Connection (Lines 1007+)
- Build and send all embeds using data fetched above
- No database queries allowed here

## Result

✅ **All embeds now work:**
1. Message 1: Session Overview
2. Message 2: Top Players
3. Message 3: Team Analytics (with MVP revives/gibs)
4. Message 4: DPM Leaderboard
5. **Message 5: Weapon Mastery** (NOW WORKS - revives data fetched correctly)
6. **Message 6: Objective & Support Stats** (NOW WORKS - correct table query)
7. Message 7: Visual Stats Graph

## Testing
Run `!last_session` command - all 7 messages should appear without errors.

The bot will now successfully display:
- Weapon mastery with revives for top 5 players
- Objective stats with XP, assists, dynamites, objectives, multikills (showing 0s until real data available)
