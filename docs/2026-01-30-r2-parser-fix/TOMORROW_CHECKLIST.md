# Tomorrow's Testing Checklist - 2026-01-31

**Pre-requisite**: Read `reports/MASTER_CODE_REVIEW.md` for full context

---

## ✅ Quick Reference

### Files Modified Tonight
| File | Purpose | Lines Changed |
|------|---------|---------------|
| `bot/community_stats_parser.py` | R2 parser fix | ~40 |
| `vps_scripts/stats_discord_webhook.lua` | Webhook gamestate fix | 2 |
| `postgresql_database_manager.py` | ON CONFLICT + Auto teams | ~140 |
| `bot/services/session_stats_aggregator.py` | Session scoring | ~60 |
| `bot/cogs/last_session_cog.py` | Score integration | ~10 |

### Features Completed
- [x] R2 Parser (12 fields fixed)
- [x] Lua Webhook (GS_PLAYING=0)
- [x] ON CONFLICT (header data update)
- [x] Auto Team Assignment
- [x] Session Score Tracking

---

## 🧪 TESTING PRIORITY ORDER

### Priority 1: Re-import Recent Files (15 min) ⭐⭐⭐⭐⭐

**Goal**: Populate defender_team, winner_team, and auto-create session_teams

**Steps**:
```bash
cd /home/samba/share/slomix_discord
python postgresql_database_manager.py
# Choose option 4 - Fix specific date range
# Start date: 2026-01-27
# End date: 2026-01-30
```

**Expected Console Output**:
```
✓ Imported 2026-01-27-213045-adlernest-round-1.txt: 8 players, 64 weapons [0.45s]
🎯 Round 1 detected, attempting auto-team assignment for 2026-01-27
✅ Auto-assigned teams for session 2026-01-27: Team A (4 defenders) vs Team B (4 attackers)
```

**Verification**:
```sql
-- Check header data populated
SELECT round_date, map_name, round_number, defender_team, winner_team
FROM rounds
WHERE round_date >= '2026-01-27'
ORDER BY round_date, round_time;
-- Should show 1s and 2s, not 0s

-- Check session_teams created
SELECT session_start_date, team_name, array_length(player_guids, 1) as player_count
FROM session_teams
WHERE session_start_date >= '2026-01-27'
ORDER BY session_start_date, team_name;
-- Should show Team A and Team B for each date
```

**Success Criteria**:
- [ ] No errors during import
- [ ] defender_team shows 1 or 2 (not 0)
- [ ] winner_team shows 0, 1, or 2
- [ ] session_teams has entries for each session
- [ ] Console shows "Auto-assigned teams" messages

---

### Priority 2: Test !last_session Display (5 min) ⭐⭐⭐⭐

**Goal**: Verify team names and scores display correctly

**Steps**:
```
In Discord: !last_session
```

**Expected Output**:
```
📊 SESSION SUMMARY - 2026-01-30

Team A vs Team B
Score: 3-2

[Player stats by team]
```

**Verification**:
- [ ] Team names display (not blank)
- [ ] Scores show numbers (not 0-0)
- [ ] Players grouped by team
- [ ] NO WARNING "⚠️ No team rosters available"

---

### Priority 3: Check for Spectators (5 min) ⭐⭐⭐

**Goal**: Verify if spectator players exist in database

**Steps**:
```sql
SELECT COUNT(*), team, MAX(player_name) as example
FROM player_comprehensive_stats
WHERE team NOT IN (1, 2)
GROUP BY team;
```

**Expected**: Empty result (no spectators)

**If Results Found**:
- Apply spectator filter fix from `reports/MASTER_CODE_REVIEW.md`
- Re-import affected sessions

---

### Priority 4: Verify R2 Fields (10 min) ⭐⭐⭐⭐⭐

**Goal**: Confirm 12 R2-only fields are positive (not negative)

**Steps**:
```sql
-- Check for negative values
SELECT COUNT(*) FROM player_comprehensive_stats
WHERE round_number = 2
  AND (headshot_kills < 0
       OR time_dead_minutes < 0
       OR denied_playtime < 0
       OR xp < 0);
-- Should return 0

-- Check SuperBoyy's specific values (known good test case)
SELECT player_name, round_number,
       headshot_kills, time_dead_minutes, denied_playtime
FROM player_comprehensive_stats
WHERE player_guid LIKE 'EDBB5DA9%'
  AND round_date = '2026-01-27'
  AND map_name = 'te_escape2'
ORDER BY round_number;
-- R1: headshot_kills=3, time_dead≈4.4, denied≈106
-- R2: headshot_kills=1, time_dead≈1.6, denied≈105
```

**Success Criteria**:
- [ ] No negative values
- [ ] SuperBoyy R2 values match expected
- [ ] All 12 fields have reasonable values

---

### Priority 5: Wait for Next Game (Live Test) ⭐⭐⭐⭐

**Goal**: Test Lua webhook and auto-assignment with fresh data

**Steps**:
1. Wait for next game session to start
2. After Round 1 completes, check console:
```
✓ Imported 2026-01-31-210000-adlernest-round-1.txt
🎯 Round 1 detected, attempting auto-team assignment for 2026-01-31
✅ Auto-assigned teams for session 2026-01-31: Team A (X defenders) vs Team B (Y attackers)
```

3. After Round 1 OR Round 2, check Discord for webhook:
```
[stats_discord_webhook] Round ended at 1738353600
```

4. After session ends, run `!last_session`:
```
📊 SESSION SUMMARY - 2026-01-31
Team A vs Team B
Score: 1-0
```

**Success Criteria**:
- [ ] Auto-assignment triggers on R1
- [ ] Webhook message appears in Discord
- [ ] Timing comparison shows Lua data (not "NO LUA DATA")
- [ ] !last_session shows teams and scores
- [ ] No errors in console

---

## 🔍 EDGE CASES TO WATCH FOR

### Midnight Crossover (Monitor Naturally)

**Scenario**: Session starts 23:50, ends 00:10

**What to Check**:
```sql
-- Check if both R1 and R2 are in same gaming_session_id
SELECT round_date, round_time, round_number, gaming_session_id
FROM rounds
WHERE map_name = 'affected_map'
ORDER BY round_date, round_time;
-- R1 and R2 should have SAME gaming_session_id

-- Check if teams found
SELECT * FROM session_teams
WHERE session_start_date LIKE '2026-01-31%' OR session_start_date LIKE '2026-02-01%';
-- Should exist for the session date
```

**If Issue Found**: See `reports/MASTER_CODE_REVIEW.md` for fix details

---

## 📊 VALIDATION QUERIES

### Quick Health Check
```sql
-- Sessions with teams assigned
SELECT COUNT(DISTINCT session_start_date)
FROM session_teams
WHERE session_start_date >= '2026-01-27';

-- Rounds with header data
SELECT
    COUNT(*) as total,
    COUNT(CASE WHEN defender_team > 0 THEN 1 END) as has_defender,
    COUNT(CASE WHEN winner_team > 0 THEN 1 END) as has_winner
FROM rounds
WHERE round_date >= '2026-01-27' AND round_number IN (1, 2);

-- R2 records sanity check
SELECT
    COUNT(*) as total_r2,
    COUNT(CASE WHEN headshot_kills >= 0 THEN 1 END) as valid_headshots,
    COUNT(CASE WHEN time_dead_minutes >= 0 THEN 1 END) as valid_time_dead
FROM player_comprehensive_stats
WHERE round_number = 2 AND round_date >= '2026-01-27';
```

**All counts should match (100% valid).**

---

## 🐛 KNOWN ISSUES TO MONITOR

From code review (`reports/MASTER_CODE_REVIEW.md`):

1. **Spectator Players** - May be assigned to Team B if team=0
   - **Check**: Run spectator query (Priority 3)
   - **Impact**: Low (spectators rarely recorded)

2. **Midnight Sessions** - Team lookup may fail across date boundary
   - **Check**: Monitor naturally when it occurs
   - **Impact**: Medium (gaming_session_id should bridge it)

3. **Filename Detection** - Uses string match instead of parsed data
   - **Check**: Verify all R1 files trigger auto-assignment
   - **Impact**: Low (ET:Legacy enforces naming)

---

## ✅ SUCCESS CHECKLIST

After all tests complete:

- [ ] Re-import completed without errors
- [ ] defender_team and winner_team populated (not 0)
- [ ] session_teams entries created for each session
- [ ] !last_session shows team names and scores
- [ ] No "No team rosters available" warning
- [ ] R2 fields all positive (no negatives)
- [ ] SuperBoyy's test case values correct
- [ ] Spectator check returns empty (or fix applied)
- [ ] Live game triggers auto-assignment
- [ ] Lua webhook fires during game
- [ ] Timing comparison shows Lua data

---

## 📁 DOCUMENTATION REFERENCE

| Document | Purpose |
|----------|---------|
| `MASTER_CODE_REVIEW.md` | Complete analysis of all changes |
| `IMPLEMENTATION_SUMMARY.md` | Feature overview |
| `CODE_REVIEW_FINDINGS.md` | Detailed bug analysis |
| `PARSER_FIX_COMPLETE.md` | R2 parser details |
| `LUA_WEBHOOK_FIX.md` | Webhook gamestate fix |
| `EVENING_SESSION_SUMMARY.md` | Tonight's work log |
| `SESSION_REPORT_2026-01-30.md` | Full 14-part session chronicle |

---

## 🚨 IF SOMETHING BREAKS

### Auto-Assignment Not Triggering

**Check**:
1. Console shows "🎯 Round 1 detected"?
   - No → Check filename has "-round-1.txt"
   - Yes → Continue
2. Console shows "attempting auto-team assignment"?
   - No → Check if defender_team is 0 in database
   - Yes → Continue
3. Console shows "✅ Auto-assigned teams"?
   - No → Check error logs, verify players exist

**Quick Fix**: Manually populate session_teams using `!set_teams` command

---

### Scores Show 0-0

**Check**:
```sql
SELECT winner_team, COUNT(*)
FROM rounds
WHERE round_date = '<session_date>' AND round_number IN (1, 2)
GROUP BY winner_team;
```

**If all winner_team = 0**: ON CONFLICT fix didn't populate. Re-import needed.

---

### Negative R2 Values

**Check**:
```sql
SELECT COUNT(*) FROM player_comprehensive_stats
WHERE round_number = 2 AND headshot_kills < 0;
```

**If > 0**: Parser fix didn't apply. Check parser code, re-import.

---

## 💾 BACKUP REMINDER

Before re-import:
```bash
PGPASSWORD='etlegacy_secure_2025' pg_dump -h localhost -U etlegacy_user -d etlegacy > \
  /home/samba/share/slomix_discord/backups/before_team_test_$(date +%Y%m%d_%H%M%S).sql
```

**Why**: Can restore if anything goes wrong.

---

## 🎯 ESTIMATED TIME

| Task | Time | Priority |
|------|------|----------|
| Re-import 2026-01-27 to 2026-01-30 | 15 min | ⭐⭐⭐⭐⭐ |
| Test !last_session | 5 min | ⭐⭐⭐⭐ |
| Spectator check | 5 min | ⭐⭐⭐ |
| R2 validation queries | 10 min | ⭐⭐⭐⭐⭐ |
| Wait for live game | Variable | ⭐⭐⭐⭐ |
| **Total** | **~35 min active** | |

---

**Created**: 2026-01-30 23:55
**Status**: Ready for testing
**Next Steps**: Get some sleep, test tomorrow morning! 😴
