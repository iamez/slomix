# 🧪 FIVEEYES Complete Testing Guide

## What We Built - Complete Week 2

### ✅ Files Created (Total: ~2,000 lines)

**Core System:**
- `analytics/config.py` (137 lines) - Configuration with feature flags
- `analytics/synergy_detector.py` (505 lines) - Core algorithm (Week 1)
- `analytics/__init__.py` - Package initialization

**Discord Integration:**
- `bot/cogs/synergy_analytics.py` (700+ lines) - Complete Discord cog
- `bot/cogs/__init__.py` - Cog package initialization
- `bot/ultimate_bot.py` - Modified to load cog

**Configuration & Testing:**
- `fiveeyes_config.json` (24 lines) - Default config
- `test_fiveeyes.py` (94 lines) - Pre-flight tests
- `tools/migrations/001_create_player_synergies.py` (240 lines) - Database migration

**Documentation:**
- `FIVEEYES_QUICKSTART.md` - Quick start guide
- `FIVEEYES_WEEK2_DAY2_COMPLETE.md` - Implementation docs
- `READY_TO_TEST.md` - Testing guide
- `FIVEEYES_TESTING_GUIDE.md` - This file

---

## 🎮 Complete Command Reference

### User Commands (4 Total)

#### 1. `!synergy` (+ aliases: `!chemistry`, `!duo`)
**Cooldown:** 5 seconds per user

**Usage:**
```
!synergy @Player1 @Player2
!synergy edo .wjs
!chemistry SuperBoyy Dudl<3
```

**What it does:**
- Shows duo chemistry analysis
- Performance boost when together vs apart
- Synergy score with confidence level
- Beautiful embed with ratings

**Expected output:**
```
⚔️ Player Synergy: edo + .wjs
Overall Rating: 🔥 Excellent

📊 Games Together: 14 games on same team
📈 Performance Boost: +50.9%
💯 Synergy Score: 0.204
🎯 Confidence: 28%

📝 Analysis: These players perform significantly better together! 🎯
```

**Error cases:**
- Not enough games together (<10)
- Player not found
- Feature disabled
- Cooldown active

---

#### 2. `!best_duos` (+ aliases: `!top_duos`, `!best_pairs`)
**Cooldown:** 10 seconds per channel

**Usage:**
```
!best_duos          # Top 10
!best_duos 20       # Top 20
!top_duos 5         # Top 5
```

**What it does:**
- Lists top player pairs by synergy score
- Shows games played, performance boost
- Color-coded ratings (Excellent/Good/Positive)

**Expected output:**
```
🏆 Top 10 Player Duos

1. edo + .wjs
   🔥 Excellent
   Synergy: 0.204 | Games: 14 | Perf Boost: +50.9%
   Confidence: 28%

2. Imb3cil + Dudl<3
   🔥 Excellent
   Synergy: 0.153 | Games: 22 | Perf Boost: +38.3%
   Confidence: 44%

...

💡 Higher synergy = better performance together
```

**Error cases:**
- No synergies in database
- Invalid limit (<1 or >50)
- Feature disabled

---

#### 3. `!team_builder` (+ aliases: `!balance_teams`, `!suggest_teams`)
**Cooldown:** 15 seconds per channel

**Usage:**
```
!team_builder @P1 @P2 @P3 @P4 @P5 @P6
!balance_teams edo .wjs SuperBoyy Dudl<3 Imb3cil Ciril
```

**What it does:**
- Analyzes ALL possible team splits
- Calculates synergy for each team
- Finds most balanced split
- Shows combination count

**Expected output:**
```
🎮 Optimized Team Split
Balanced teams based on synergy analysis

🔵 Team A (Synergy: 0.156)
• edo
• Dudl<3
• Imb3cil

🔴 Team B (Synergy: 0.142)
• .wjs
• SuperBoyy
• Ciril

⚖️ Balance Rating
🟢 Excellent balance!
91.0%

✅ Analyzed 20 possible splits
```

**Algorithm:**
- For 6 players: C(6,3) = 20 combinations
- For 8 players: C(8,4) = 70 combinations
- Calculates synergy for each split
- Finds split with most similar team synergies

**Error cases:**
- < 4 players provided
- > 12 players provided (configurable)
- Players not found
- Feature disabled

---

#### 4. `!player_impact` (+ aliases: `!teammates`, `!partners`)
**Cooldown:** 10 seconds per user

**Usage:**
```
!player_impact              # Your stats
!player_impact @SuperBoyy   # Someone else
!teammates edo              # By name
```

**What it does:**
- Shows all teammates for a player
- Best 5 partners (highest synergy)
- Worst 5 partners (if >5 total)
- Average synergy & partner count

**Expected output:**
```
🤝 Player Impact: edo
Teammate chemistry analysis (8 partners)

🏆 Best Teammates
1. 🔥 .wjs
   Synergy: 0.204 | 14 games
2. 🔥 SmetarskiProner
   Synergy: 0.147 | 12 games
3. ✅ aLive
   Synergy: 0.089 | 16 games
...

📉 Challenging Partnerships
1. PlayerX
   Synergy: 0.012 | 11 games
...

📊 Average Synergy: 0.093
👥 Unique Partners: 8

💡 Based on games with 10+ matches together
```

**Error cases:**
- No partners found (<10 games with anyone)
- Player not found
- Feature disabled

---

## 🔧 Admin Commands (3 Total)

#### 1. `!fiveeyes_enable`
**Permission:** Administrator only

**Usage:**
```
!fiveeyes_enable
```

**What it does:**
- Enables synergy analytics system
- Updates config file
- Makes all commands available

**Expected output:**
```
✅ FIVEEYES synergy analytics enabled!
```

---

#### 2. `!fiveeyes_disable`
**Permission:** Administrator only

**Usage:**
```
!fiveeyes_disable
```

**What it does:**
- Disables synergy analytics system
- Updates config file
- Hides all commands (except admin commands)

**Expected output:**
```
⚠️ FIVEEYES synergy analytics disabled.
```

---

#### 3. `!recalculate_synergies`
**Permission:** Administrator only

**Usage:**
```
!recalculate_synergies
```

**What it does:**
- Recalculates ALL player synergies
- Clears cache
- Takes 3-5 minutes for 300 pairs

**Expected output:**
```
🔄 Starting synergy recalculation... This may take a few minutes.
[...wait 3-5 minutes...]
✅ Recalculated 109 player synergies successfully!
```

---

## 🧪 Testing Scenarios

### Test 1: Fresh Start (Disabled by Default)

**Steps:**
1. Start bot normally
2. Try `!synergy edo .wjs`

**Expected:**
```
🔒 Synergy analytics is currently disabled.
Contact an admin to enable this feature.
```

**Status:** ✅ Should work

---

### Test 2: Enable System

**Steps:**
1. Run `!fiveeyes_enable` (as admin)
2. Try `!synergy edo .wjs` again

**Expected:**
```
✅ FIVEEYES synergy analytics enabled!

[Then synergy embed appears]
```

**Status:** ✅ Should work

---

### Test 3: Valid Synergy Query

**Steps:**
1. `!synergy edo .wjs` (known good pair)

**Expected:**
- Beautiful embed
- 🔥 Excellent rating
- 14 games together
- 0.204 synergy score
- Performance boost data

**Status:** ✅ Should work (data exists)

---

### Test 4: Insufficient Data

**Steps:**
1. `!synergy PlayerWithNoGames AnotherNewPlayer`

**Expected:**
```
📊 Insufficient data for [players]
These players need at least 10 games together on the same team...
```

**Status:** ✅ Should work

---

### Test 5: Player Not Found

**Steps:**
1. `!synergy NonExistentPlayer123 edo`

**Expected:**
```
❌ Please mention or name exactly 2 players.
**Usage:** `!synergy @Player1 @Player2`
```

**Status:** ✅ Should work

---

### Test 6: Best Duos

**Steps:**
1. `!best_duos`
2. `!best_duos 20`

**Expected:**
- List of 10 (or 20) top pairs
- Sorted by synergy score
- All with games/boost/confidence data

**Status:** ✅ Should work (109 synergies in DB)

---

### Test 7: Team Builder (6 players)

**Steps:**
1. `!team_builder edo .wjs SuperBoyy Dudl<3 Imb3cil Ciril`

**Expected:**
- Two teams of 3
- Synergy scores for each team
- Balance rating
- "Analyzed 20 possible splits"

**Status:** ✅ Should work

---

### Test 8: Team Builder (4 players)

**Steps:**
1. `!team_builder edo .wjs SuperBoyy Dudl<3`

**Expected:**
- Two teams of 2
- Synergy scores
- "Analyzed 6 possible splits"

**Status:** ✅ Should work

---

### Test 9: Team Builder (Too Few)

**Steps:**
1. `!team_builder edo .wjs`

**Expected:**
```
❌ Need at least 4 players for team balancing.
**Usage:** `!team_builder @P1 @P2 @P3 @P4 @P5 @P6`
```

**Status:** ✅ Should work

---

### Test 10: Player Impact

**Steps:**
1. `!player_impact edo`

**Expected:**
- List of edo's partners
- Best 5 teammates
- Average synergy
- Partner count

**Status:** ✅ Should work (edo has 8 partners)

---

### Test 11: Cooldown Test

**Steps:**
1. `!synergy edo .wjs`
2. Immediately: `!synergy edo .wjs` again

**Expected:**
```
[First command works]
[Second command shows cooldown error from Discord]
```

**Status:** ✅ Should work (5s cooldown)

---

### Test 12: Disable System

**Steps:**
1. `!fiveeyes_disable` (as admin)
2. Try `!synergy edo .wjs`

**Expected:**
```
⚠️ FIVEEYES synergy analytics disabled.

[Then:]
🔒 Synergy analytics is currently disabled...
```

**Status:** ✅ Should work

---

### Test 13: Recalculate Synergies

**Steps:**
1. `!recalculate_synergies` (as admin)
2. Wait 3-5 minutes

**Expected:**
```
🔄 Starting synergy recalculation...
[...wait...]
✅ Recalculated 109 player synergies successfully!
```

**Status:** ✅ Should work

---

### Test 14: Error Handling (Bot Stays Up)

**Steps:**
1. Cause an error (e.g., corrupt database query)
2. Check if bot crashes

**Expected:**
- Error caught by cog
- User sees friendly message
- Bot continues running
- Other commands still work

**Status:** ✅ Should work (error isolation)

---

## 🐛 Known Issues / Edge Cases

### 1. Player Name Matching
**Issue:** Partial name matches might find wrong player

**Workaround:** Use @mentions for accuracy

**Fix:** Improve `_get_player_guid()` to show matches if ambiguous

---

### 2. Team Builder with Odd Numbers
**Issue:** One team gets extra player

**Expected:** Working as designed - larger team gets analyzed

**Status:** Not a bug

---

### 3. No Win Tracking Yet
**Issue:** Win rate shows 0% (team_won column missing)

**Expected:** Phase 2 or future enhancement

**Status:** Known limitation

---

### 4. Cache Not Implemented Fully
**Issue:** Every query hits database

**Expected:** Config says `cache_results: true` but not implemented

**Status:** Performance optimization for future

---

### 5. Background Recalculation
**Issue:** `auto_recalculate: false` by default

**Expected:** Admin can enable in config or run manually

**Status:** Working as designed (safety first)

---

## 📊 Performance Expectations

| Command | Expected Time | Database Queries |
|---------|--------------|------------------|
| `!synergy` | 200-500ms | 1 |
| `!best_duos` | 300-800ms | 1 |
| `!team_builder` (6) | 1-3 seconds | 20 (C(6,3) combinations) |
| `!team_builder` (8) | 3-5 seconds | 70 (C(8,4) combinations) |
| `!player_impact` | 500ms-1s | 1 |
| `!recalculate_synergies` | 3-5 minutes | 300 pairs |

---

## 🔍 Troubleshooting

### Bot Won't Start
**Symptom:** Bot crashes on startup

**Check:**
1. `fiveeyes_config.json` exists
2. `bot/cogs/synergy_analytics.py` has no syntax errors
3. `analytics/config.py` imports correctly

**Fix:**
```python
# Temporarily disable cog loading
# Comment out this line in bot/ultimate_bot.py:
# await self.load_extension('bot.cogs.synergy_analytics')
```

---

### Commands Not Showing
**Symptom:** Commands don't appear in Discord

**Check:**
1. Is analytics enabled? (`!fiveeyes_enable`)
2. Does bot have proper permissions?
3. Is cog loaded? (check bot logs)

**Fix:**
```
!fiveeyes_enable
```

---

### "No synergies found"
**Symptom:** Commands return empty results

**Check:**
1. Database has synergies: `SELECT COUNT(*) FROM player_synergies`
2. Should be 109 records

**Fix:**
```
!recalculate_synergies
```

---

### Cooldown Errors
**Symptom:** "Command is on cooldown"

**Expected:** Working as designed

**Cooldowns:**
- `!synergy`: 5s per user
- `!best_duos`: 10s per channel
- `!team_builder`: 15s per channel
- `!player_impact`: 10s per user

**Fix:** Wait for cooldown or ask admin to reset

---

## 📝 Testing Checklist

### Pre-Flight (Before Discord Testing)
- [x] Run `python test_fiveeyes.py`
- [x] All pre-flight checks pass
- [x] Config file created
- [x] Cog imports successfully
- [x] Database has 109 synergies

### Basic Functionality
- [ ] Bot starts successfully
- [ ] Cog loads without errors
- [ ] `!fiveeyes_enable` works
- [ ] `!synergy` returns valid data
- [ ] `!best_duos` shows top 10
- [ ] `!team_builder` suggests teams
- [ ] `!player_impact` shows partners
- [ ] `!fiveeyes_disable` works

### Error Handling
- [ ] Disabled state shows proper message
- [ ] Invalid players handled gracefully
- [ ] Insufficient data handled
- [ ] Cooldowns work
- [ ] Bot doesn't crash on errors

### Performance
- [ ] `!synergy` responds in <1s
- [ ] `!best_duos` responds in <2s
- [ ] `!team_builder` responds in <5s
- [ ] Cooldowns prevent spam

### Admin Functions
- [ ] `!fiveeyes_enable` works (admin only)
- [ ] `!fiveeyes_disable` works (admin only)
- [ ] `!recalculate_synergies` works (admin only)
- [ ] Non-admins can't use admin commands

---

## 🎉 Week 2 Complete!

**Total Implementation:**
- ✅ Week 1: Database + Core Algorithm (505 lines)
- ✅ Week 2: Discord Integration (700+ lines)
- ✅ Configuration System (137 lines)
- ✅ Testing Infrastructure (94 lines)
- ✅ Documentation (1000+ lines)

**Grand Total: ~2,500 lines of production code + docs**

**Time Investment:** ~12-15 hours of development

**What You Have:**
- Complete synergy detection system
- 4 user commands
- 3 admin commands
- Safe error handling
- Feature flags
- Command cooldowns
- Comprehensive testing guide

---

## 🚀 Next Steps

### Immediate (Now)
1. Start bot: `python bot/ultimate_bot.py`
2. Enable: `!fiveeyes_enable`
3. Test: `!synergy edo .wjs`
4. Test: `!best_duos`
5. Test: `!team_builder` with 6 players
6. Test: `!player_impact edo`

### Short Term (This Week)
- Gather community feedback
- Note which features are used most
- Check performance in production
- Monitor for errors

### Long Term (Week 3+)
- Tune synergy thresholds based on feedback
- Add caching for better performance
- Implement win tracking
- Consider Phase 2 (role normalization)

---

**Ready to test!** 🎯

Start your bot and let's see those synergy scores in action! 🔥
