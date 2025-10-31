# 🐛 TEAM SCORING ISSUE - October 5, 2025

## 🎯 THE PROBLEM

### **What We Discovered**:
Bot's `!last_session` command treats **Axis vs Allies** as the teams, but in Stopwatch mode:
- Players swap between Axis/Allies every round
- The **actual teams** stay consistent (e.g., Team A: SuperBoyy/qmr/SmetarskiProner)

### **Evidence from October 2nd Session**:

**Current Bot Output** (WRONG):
```
🔵 sWat Roster: ALL 6 PLAYERS
🔴 maDdogs Roster: (empty)

🔴 maDdogs MVP: vid (2.0 K/D)
🔵 sWat MVP: vid (1.0 K/D)
```

**Vid appears as MVP on BOTH teams!** 😂

**Team Swaps Shown**:
- Everyone shows as swapping: 🔵(11r) → 🔴(11r)
- This is just normal Stopwatch role swapping, not actual team changes

---

## 🔍 ROOT CAUSE ANALYSIS

### **Current Bot Logic** (Incorrect):
1. Bot reads Round 1 file
2. Sees: Allies = team "1", Axis = team "2"
3. Assumes these are the "teams" to track
4. Round 2: Teams swap roles (normal Stopwatch behavior)
5. Bot thinks: "Oh, everyone swapped teams!"
6. Result: All stats get mixed up

### **Actual Game Logic** (Correct):
1. **Hardcoded Team A**: SuperBoyy, qmr, SmetarskiProner
2. **Hardcoded Team B**: vid, endekk, .olz
3. Round 1: Team A plays as Allies, Team B plays as Axis
4. Round 2: Team A plays as Axis, Team B plays as Allies
5. Team composition **never changes** - only their in-game roles swap

---

## 📊 DATA FROM OUR ANALYSIS

### **October 2nd Session - ACTUAL Teams**:

**Team A (SuperBoyy, qmr, SmetarskiProner)**:
- Record: **8 Wins - 2 Losses (80% win rate)**
- Played as Allies: 10 matches
- Played as Axis: 10 matches
- Stayed together ALL SESSION (no real swaps)

**Team B (vid, endekk, .olz)**:
- Record: **2 Wins - 8 Losses (20% win rate)**
- Played as Allies: 10 matches
- Played as Axis: 10 matches
- Stayed together ALL SESSION (no real swaps)

---

## 🎯 WHAT NEEDS TO BE FIXED

### **Issue #1: Team Identification**
**Current**: Uses Axis/Allies from game
**Should**: Use hardcoded teams based on Round 1 roster

### **Issue #2: Team Names**
**Current**: "maDdogs" vs "sWat" (doesn't match reality)
**Should**: Use actual team compositions or custom names

### **Issue #3: MVP Calculation**
**Current**: Calculates MVP per Axis/Allies team
**Should**: Calculate MVP per hardcoded team

### **Issue #4: Team Swap Detection**
**Current**: Shows everyone swapping every round
**Should**: Only show actual mid-session substitutions

### **Issue #5: Team Stats Aggregation**
**Current**: Aggregates by Axis/Allies
**Should**: Aggregate by hardcoded teams across all rounds

---

## 🛠️ PROPOSED SOLUTION

### **Phase 1: Add Team Detection to Parser**
Modify `bot/community_stats_parser.py` or `tools/simple_bulk_import.py`:
1. Read first Round 1 file of session
2. Extract Allies roster → Team A
3. Extract Axis roster → Team B
4. Store team compositions in database

### **Phase 2: Create Session Teams Table**
```sql
CREATE TABLE session_teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_start_date TEXT,  -- First round timestamp
    team_name TEXT,            -- "Team A" or "Team B" (or custom)
    player_guids TEXT,         -- JSON array: ["D8423F90", "7B84BE88", ...]
    player_names TEXT,         -- JSON array: ["vid", "endekk", "olz"]
    UNIQUE(session_start_date, team_name)
);
```

### **Phase 3: Update Bot Commands**
Modify `bot/ultimate_bot.py`:

#### **`!last_session` Changes**:
1. Query `session_teams` table for team rosters
2. Calculate stats per hardcoded team (not Axis/Allies)
3. Determine team MVP correctly
4. Show actual team swaps (if any occurred mid-session)

#### **New Command: `!team_stats <date>`**:
```
!team_stats 2025-10-02
```
Shows:
- Team compositions
- Win/loss records
- Individual player stats within team context
- Match-by-match breakdown

---

## 🧪 TEST CASES

### **Test Case 1: October 2nd Session**
**Expected Output**:
```
🏆 Session Summary: 2025-10-02

Team A: SuperBoyy, qmr, SmetarskiProner
Record: 8W - 2L (80%)
Team MVP: SuperBoyy (stats)

Team B: vid, endekk, .olz
Record: 2W - 8L (20%)
Team MVP: vid (stats)

✅ No mid-session player swaps
```

### **Test Case 2: Session with Actual Swaps**
**Expected Output**:
```
Team A: player1, player2, player3
Team B: player4, player5, player6

⚠️ Mid-Session Swap Detected:
• player3 moved to Team B after Map 5
• player6 moved to Team A after Map 5

Final Rosters:
Team A: player1, player2, player6
Team B: player4, player5, player3
```

---

## 📋 IMPLEMENTATION CHECKLIST

### **Step 1: Data Collection** (1 hour)
- [ ] Create `session_teams` table
- [ ] Write script to populate from historical data
- [ ] Validate October 2nd data

### **Step 2: Parser Updates** (2 hours)
- [ ] Modify import script to detect team rosters
- [ ] Auto-populate `session_teams` on import
- [ ] Handle multi-map sessions

### **Step 3: Bot Command Updates** (3 hours)
- [ ] Update `!last_session` to use hardcoded teams
- [ ] Fix MVP calculation
- [ ] Fix team swap detection
- [ ] Update embed formatting

### **Step 4: Testing** (1 hour)
- [ ] Test with October 2nd data
- [ ] Verify team stats accuracy
- [ ] Check MVP correctness
- [ ] Test with bot in Discord

### **Step 5: Documentation** (30 min)
- [ ] Update `BOT_COMPLETE_GUIDE.md`
- [ ] Document team tracking system
- [ ] Add troubleshooting guide

---

## 🎯 SUCCESS CRITERIA

✅ Vid appears as MVP only for his actual team
✅ Team compositions correctly identified
✅ No false "swap" warnings for Stopwatch role changes
✅ Win/loss records match reality (Team A: 8-2, Team B: 2-8)
✅ Team stats aggregate correctly across all rounds

---

## ⏱️ ESTIMATED EFFORT

**Total**: ~7.5 hours
- Data Collection: 1 hour
- Parser Updates: 2 hours
- Bot Updates: 3 hours
- Testing: 1 hour
- Documentation: 0.5 hours

---

## 🚨 RISKS & CONSIDERATIONS

### **Risk #1: Ambiguous Team Detection**
**Problem**: What if players join mid-session?
**Solution**: Use first complete round (6 players) as baseline

### **Risk #2: Unbalanced Teams**
**Problem**: What if it's 4v2 or 5v3?
**Solution**: Track actual roster sizes, no assumptions

### **Risk #3: Multiple Sessions Per Day**
**Problem**: How to differentiate sessions?
**Solution**: Use first round timestamp as session ID

### **Risk #4: Custom Team Names**
**Problem**: Users want "Clan A" vs "Clan B" names
**Solution**: Add `team_custom_name` column, allow manual naming

---

## 📝 NOTES

- Scripts created today (`track_team_scoring.py`, `track_player_swaps.py`) are proof-of-concept
- They successfully identified the team compositions
- Now we need to integrate this logic into the bot
- October 2nd data is perfect test case (clean 3v3, no subs)

---

## 🎉 BONUS FEATURES (Future)

Once core system works:
- [ ] `!session_leaderboard` - All-time team records
- [ ] `!rivalry <date>` - Head-to-head stats between teams
- [ ] `!player_chemistry` - Who plays best together
- [ ] `!team_history <players>` - Track specific roster over time
