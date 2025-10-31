# 🎯 ANALYTICS ROADMAP - October 5, 2025
**Status**: 📋 PLANNING PHASE  
**Current State**: Bot fully working, 13 leaderboard types complete  
**Next Phase**: Advanced analytics with historical data  

---

## ✅ COMPLETED (Sessions 1-4)

### **Session 1: Critical Fixes** (Oct 4, 21:30)
- ✅ Fixed last_session date query (SUBSTR)
- ✅ Fixed stats command database connection
- ✅ Fixed special_flag column error
- ✅ Added GUID validation for admin linking
- ✅ Bot deployed and tested

### **Session 2: Linking System** (Oct 4, 22:30)
- ✅ Created player_aliases table (48 aliases, 25 GUIDs)
- ✅ Enhanced !link command (3 scenarios: self/GUID/name)
- ✅ Added admin linking (!link @user <GUID>)
- ✅ Added @mention support for !stats
- ✅ Complete documentation

### **Session 3: Leaderboard Enhancement** (Oct 5, 00:30)
- ✅ Added pagination (!lb, !lb 2, !lb dpm 3)
- ✅ Shows 10 players per page with medals (🥇🥈🥉)
- ✅ Added dev badge (👑) for GUID E587CA5F
- ✅ Dynamic footer with page navigation hints

### **Session 4: Support Stats Leaderboards** (Oct 5, 01:30)
- ✅ Added 7 new leaderboard categories:
  - revives (teammates revived)
  - gibs (finishing moves)
  - objectives (completed/destroyed/stolen/returned)
  - efficiency (average rating)
  - teamwork (lowest team damage %)
  - multikills (doubles/triples/quads/mega)
  - grenades (kills + accuracy + AOE effectiveness)
- ✅ Fixed revives bug (times_revived column)
- ✅ Added calculated AOE ratio (hits ÷ kills)
- ✅ Added 🔥 badge for 3.0+ AOE ratio

---

## 🎯 PROPOSED ANALYTICS FEATURES

### **Priority 1: HIGH IMPACT** 🔥

#### **1. Player Chemistry Analytics** 🤝
*"Who plays better together?"*

**Implementation**:
```python
# New command: !chemistry @player1 @player2
# Shows:
- Combined win rate
- Individual performance WITH vs WITHOUT each other
- Best map together
- Total games played together
```

**Database Query**:
```sql
-- Find sessions where both players participated
SELECT s.session_id, s.map_name, s.winner_team,
       p1.player_name as player1, p1.team as team1, p1.dpm as dpm1,
       p2.player_name as player2, p2.team as team2, p2.dpm as dpm2
FROM sessions s
JOIN player_comprehensive_stats p1 ON p1.session_id = s.session_id
JOIN player_comprehensive_stats p2 ON p2.session_id = s.session_id
WHERE p1.player_guid = ? AND p2.player_guid = ?
```

**Output Example**:
```
🤝 Chemistry Report: @vid & @carniee

📊 Together Stats (142 games):
   Same team: 89 games (63%)
   Opposite teams: 53 games (37%)
   
✅ When on SAME team:
   vid: 380 DPM avg (↑40 from solo)
   carniee: 310 DPM avg (↑25 from solo)
   Team win rate: 68%
   
⚔️ When on OPPOSITE teams:
   vid: 365 DPM avg
   carniee: 295 DPM avg
   vid's team wins: 58%
   
🗺️ Best map together: erdenberg_t2 (75% win rate)
```

**Effort**: 3-4 hours

---

#### **2. Rivalry/Nemesis System** ⚔️
*"Who counters who?"*

**Implementation**:
```python
# New command: !rivalry @player1 @player2
# Shows:
- Head-to-head kill advantage
- Win rate when on opposite teams
- Best/worst maps against each other
```

**Database Query**:
```sql
-- Find games where players were on opposite teams
SELECT s.session_id, s.map_name, s.winner_team,
       p1.team as team1, p1.kills as kills1, p1.deaths as deaths1,
       p2.team as team2, p2.kills as kills2, p2.deaths as deaths2
FROM sessions s
JOIN player_comprehensive_stats p1 ON p1.session_id = s.session_id
JOIN player_comprehensive_stats p2 ON p2.session_id = s.session_id
WHERE p1.player_guid = ? AND p2.player_guid = ?
  AND p1.team != p2.team
```

**Output Example**:
```
⚔️ Rivalry: @vid vs @SuperBoyy

📊 Head-to-Head (53 games opposite teams):
   vid's team wins: 31 (58%)
   SuperBoyy's team wins: 22 (42%)
   
💀 Kill Matchup:
   vid: 465 kills, 392 deaths (1.19 K/D)
   SuperBoyy: 441 kills, 378 deaths (1.17 K/D)
   Kill advantage: vid +24
   
🗺️ Map Performance:
   vid dominates: erdenberg (70% win rate)
   SuperBoyy dominates: goldrush (65% win rate)
   Most contested: supply (50/50 split)
   
🔥 Recent Form (last 10 games):
   vid: 7 wins, 3 losses
```

**Effort**: 4-5 hours

---

#### **3. Team Balance Analysis** ⚖️
*"Were teams fair? Who got stacked?"*

**Implementation**:
```python
# New command: !balance <session_id>
# Shows:
- Predicted winner based on DPM history
- Actual winner
- Stack score (skill differential)
```

**Database Query**:
```sql
-- Calculate team skill (average DPM of all players)
SELECT team, 
       AVG(historical_dpm) as avg_skill,
       SUM(historical_dpm) as total_skill,
       COUNT(*) as player_count
FROM (
    SELECT p.team, p.player_guid,
           (SELECT AVG(dpm) FROM player_comprehensive_stats 
            WHERE player_guid = p.player_guid) as historical_dpm
    FROM player_comprehensive_stats p
    WHERE p.session_id = ?
)
GROUP BY team
```

**Output Example**:
```
⚖️ Team Balance Report
Session: 2025-10-02-erdenberg_t2-round-1

🔵 ALLIES (6 players):
   Predicted DPM: 342 avg
   Players: vid (380), carniee (310), olz (325)...
   Total skill: 2,052
   
🔴 AXIS (6 players):
   Predicted DPM: 298 avg
   Players: SuperBoyy (305), endekk (290)...
   Total skill: 1,788
   
📊 Analysis:
   Stack score: +264 (Allies favored)
   Prediction: Allies 68% win chance
   Actual result: Allies won
   ✅ Prediction CORRECT
   
💡 Suggestion for balance:
   Swap vid → Axis would create 50/50 match
```

**Effort**: 5-6 hours

---

### **Priority 2: INSIGHTFUL** 📈

#### **4. Performance Context Analytics** 🎮
*"How does map/time/situation affect performance?"*

**Implementation**:
```python
# New command: !context @player
# Shows:
- Best/worst maps
- Performance when winning vs losing
- Time of day trends (if session_date includes time)
```

**Output Example**:
```
🎮 Performance Context: @vid

🗺️ Map Performance:
   Best: erdenberg_t2 (395 DPM avg, 1.58 K/D)
   Worst: goldrush (285 DPM avg, 1.21 K/D)
   Most played: supply (234 games)
   
📊 Situational Performance:
   When team winning: 410 DPM avg (clutch!)
   When team losing: 305 DPM avg
   Difference: +105 DPM (↑34%)
   
💪 Pressure Player:
   In close games (<50 point diff): 385 DPM
   In blowouts (>200 point diff): 310 DPM
   Performs BETTER under pressure!
```

**Effort**: 4-5 hours

---

#### **5. Trend Analysis** 📈
*"Is someone improving? Who's on fire?"*

**Implementation**:
```python
# New command: !trend @player dpm
# Shows:
- 30-day rolling average
- Recent form (last 10 games)
- Improvement rate
```

**Database Query**:
```sql
-- Get player stats over time
SELECT session_date, dpm, kills, deaths
FROM player_comprehensive_stats
WHERE player_guid = ?
ORDER BY session_date DESC
LIMIT 100
```

**Output Example**:
```
📈 Trend Analysis: @vid - DPM

📊 Current Form:
   Last 10 games: 395 DPM avg (🔥 HOT!)
   Last 30 games: 360 DPM avg
   Overall: 342 DPM avg
   
🚀 Improvement:
   vs 30 days ago: +35 DPM (↑9.7%)
   vs 90 days ago: +58 DPM (↑17%)
   Trend: IMPROVING ✅
   
🏆 Recent Highlights:
   Best game: 543 DPM (2025-10-02)
   5-game streak: 420+ DPM avg
   Current streak: 3 games 400+ DPM
```

**Effort**: 5-6 hours

---

### **Priority 3: FUTURE/EXPERIMENTAL** 🔮

#### **6. Prediction System** 🔮
*"Who will win next game?"*

**Implementation**:
- Machine learning model (scikit-learn)
- Train on historical session data
- Features: player DPM, K/D, map, team composition

**Output Example**:
```
🔮 Match Prediction

🔵 ALLIES: vid, carniee, olz, player4, player5, player6
🔴 AXIS: SuperBoyy, endekk, player7, player8, player9, player10

📊 Prediction:
   Allies win chance: 62%
   Axis win chance: 38%
   
🎯 Key Factors:
   ✅ vid's DPM advantage (+35 over SuperBoyy)
   ⚠️ Axis has more medics (3 vs 2)
   ✅ Allies have better obj players
   
💡 Confidence: 72% (based on 1,456 historical games)
```

**Effort**: 8-10 hours (requires ML setup)

---

#### **7. Social Network Graph** 🕸️
*"Who plays with who?"*

**Implementation**:
- Generate network graph (NetworkX)
- Visualize player relationships
- Detect "core groups"

**Output Example**:
```
🕸️ Player Network

📊 Core Group Detected:
   vid ↔ carniee (142 games together)
   vid ↔ olz (156 games together)
   carniee ↔ olz (128 games together)
   Triangle: 89 games all three
   
👥 Most Frequent Teammates:
   1. vid & olz (156 games)
   2. SuperBoyy & endekk (134 games)
   3. vid & carniee (142 games)
   
🆕 Newcomer Integration:
   newbie123 most plays with: vid (12 games)
   Conclusion: vid is "mentor" for new players
```

**Effort**: 6-8 hours (requires visualization)

---

#### **8. Achievement System** 🏅
*"Unlock milestones and badges"*

**Implementation**:
```python
# Track rare achievements
ACHIEVEMENTS = {
    "triple_crown": "Most kills, damage, AND objectives in one game",
    "pentakill": "5+ kills in 10 seconds",
    "medic_hero": "50+ revives in one game",
    "sniper_god": "90%+ accuracy with 20+ kills",
    "tank": "Survive entire round with 0 deaths"
}
```

**Output Example**:
```
🏅 Achievements: @vid

✅ UNLOCKED (12/50):
   🏆 Triple Crown (3x)
   💀 Kill Leader (42x) 
   🎯 Sharpshooter (8x)
   ⚡ Speed Demon (15x)
   
🔒 LOCKED (38/50):
   🏥 Medic Hero (Progress: 48/50 revives)
   🛡️ Tank (Best: 1 death, need 0)
   🔥 Pentakill (Never achieved)
   
📊 Achievement Score: 240/1000
   Rank: #4 of 25 players
```

**Effort**: 6-8 hours

---

## 📋 IMPLEMENTATION PLAN

### **Phase 1: Quick Wins** (4-6 hours)
1. ✅ Document current state (this file!)
2. 🟡 Player Chemistry (!chemistry)
3. 🟡 Rivalry System (!rivalry)
4. 🟡 Performance Context (!context)

### **Phase 2: Deep Analytics** (8-10 hours)
1. 🟡 Team Balance (!balance)
2. 🟡 Trend Analysis (!trend)
3. 🟡 Session Quality Metrics

### **Phase 3: Advanced Features** (12-15 hours)
1. 🟡 Prediction System (ML)
2. 🟡 Social Network Graph
3. 🟡 Achievement System

---

## 🔧 TECHNICAL NOTES

### **Database Queries Needed**:
1. **Session co-occurrence**: Find all sessions where 2+ players participated
2. **Team membership**: Determine which team each player was on
3. **Historical averages**: Calculate player's typical DPM/K/D for comparison
4. **Win rate tracking**: Track wins when with/against specific players

### **New Tables (Optional)**:
```sql
-- Cache for player relationships (performance optimization)
CREATE TABLE player_relationships (
    player1_guid TEXT,
    player2_guid TEXT,
    games_together INTEGER,
    games_same_team INTEGER,
    games_opposite_team INTEGER,
    win_rate_together REAL,
    last_played_together DATE,
    PRIMARY KEY (player1_guid, player2_guid)
);
```

### **Bot Commands to Add**:
- `!chemistry @player1 @player2` - Chemistry report
- `!rivalry @player1 @player2` - Head-to-head stats
- `!balance <session_id>` - Team balance analysis
- `!context @player` - Performance context
- `!trend @player <stat>` - Trend analysis
- `!predict <team_roster>` - Match prediction
- `!network @player` - Social network
- `!achievements @player` - Achievement progress

---

## 🎯 USER'S FAVORITES (From This Session)

### **LOVE THESE** ❤️:
1. 🤝 Player Chemistry - "Who plays better together"
2. ⚔️ Rivalry System - "Who counters who"
3. 📈 Trend Analysis - "Is someone improving"
4. 🎮 Performance Context - "How does map/situation affect performance"

### **KEEP IN BACKEND** 🗄️:
1. 🔮 Prediction System - Cool but complex
2. 🕸️ Social Network - Interesting but lower priority
3. 🏅 Achievement System - Fun but takes time
4. ⚖️ Team Balance - Useful for admins

---

## 💾 ROLLBACK POINT

**If things go wrong, restore to this state**:

```powershell
# Check current bot status
git status

# See what changed since last known good state
git diff HEAD bot/ultimate_bot.py

# Revert to last commit if needed
git checkout HEAD -- bot/ultimate_bot.py

# Or restore from specific commit
git log --oneline -10
git checkout <commit_hash> -- bot/ultimate_bot.py
```

**Last Known Good State**:
- Bot file: `bot/ultimate_bot.py` (4,184 lines)
- Database: `etlegacy_production.db` (12,414 records, 53 columns)
- Terminal: Bot stopped (can restart anytime)
- Features: 13 leaderboard types, all working

---

## ⚠️ WARNINGS BEFORE IMPLEMENTING

1. **Database Load**: Some queries (chemistry, rivalry) will scan ALL 12,414 records
   - Solution: Add indexes, cache results, limit to recent games
   
2. **Complexity**: Analytics features add ~500-1000 lines of code EACH
   - Solution: Break into separate modules/files
   
3. **Testing**: Each feature needs Discord testing
   - Solution: Test incrementally, one feature at a time
   
4. **Performance**: Some queries may be slow (1-2 seconds)
   - Solution: Add loading messages, optimize queries

---

## 📝 NEXT SESSION CHECKLIST

Before starting implementation:
- [ ] Review this document
- [ ] Confirm which feature to implement
- [ ] Check database is backed up
- [ ] Ensure bot is working (test !lb, !stats)
- [ ] Create new branch in git (if using version control)
- [ ] Set time limit (stop after 2 hours to avoid burnout)

---

**Status**: 📋 READY FOR NEXT SESSION  
**Recommendation**: Start with **Player Chemistry** (!chemistry) - highest impact, moderate complexity  
**Estimated Time**: 3-4 hours for full implementation and testing
