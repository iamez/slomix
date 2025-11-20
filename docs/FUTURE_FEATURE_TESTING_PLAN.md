# Future Feature Branch - Testing Plan

**Created:** November 20, 2025
**Branch:** `future-feature`
**Status:** Merged, ready for testing
**GitHub:** https://github.com/iamez/slomix/tree/future-feature

---

## 🎯 What We're Doing

We had 3 separate feature branches that were developed independently. We've now merged them all into a single `future-feature` branch to test together before merging to main.

---

## 📦 What's in the future-feature Branch

### Feature 1: Logging Improvements (Branch 3)
**Files Changed:** Logging configuration across bot
**What it does:**
- Adds tiered logging levels: QUIET, NORMAL, VERBOSE
- Better console output formatting
- Cleaner error messages
- No database changes needed

**Commands:** None (automatic system improvement)

---

### Feature 2: Server Update Command (Branch 1)
**Files Added:**
- Updates to `bot/cogs/server_control.py`

**What it does:**
- `!et_update` command for updating ET:Legacy server
- Downloads new snapshots
- Automatic rollback on failure
- Uploads pk3 file to Discord
- No database changes needed

**Commands:**
- `!et_update` (also: `!update_server`, `!etlegacy_update`)

---

### Feature 3: Engagement Features (Branch 2)
**Files Added:**
- `bot/cogs/mvp_cog.py` - MVP voting commands
- `bot/cogs/title_cog.py` - Title management
- `bot/cogs/live_cog.py` - Live match updates
- `bot/cogs/recap_cog.py` - Session recaps
- `bot/cogs/player_insights_cog.py` - Advanced analytics
- `bot/services/mvp_voting_service.py` - MVP backend
- `bot/services/title_system.py` - Title backend
- `bot/services/rare_achievements_service.py` - Achievement detection

**What it does:**
- **MVP Voting System**: Community votes for session MVP
- **Title/Badge System**: 20+ unlockable titles (Sharpshooter, Medic, Legend, etc.)
- **Rare Achievements**: Auto-detects exceptional performances and posts alerts
- **Live Updates**: Real-time match status
- **Session Recaps**: Detailed post-session summaries

**Database Requirements:**
- Needs 2 new tables: `mvp_votes`, `player_titles`
- Migration script: `migrations/001_engagement_features.sql`

**New Commands:**
- MVP voting commands (automatic after sessions)
- Title management commands
- Live match tracking
- Player insights and analytics

---

## 🗄️ Database Migration Required

**File:** `/migrations/001_engagement_features.sql`

**Tables to Create:**
1. `mvp_votes` - Stores MVP voting results
2. `player_titles` - Tracks unlocked and equipped player titles

**Run migration:**
```bash
PGPASSWORD='etlegacy_secure_2025' psql -h localhost -U etlegacy_user -d etlegacy -f migrations/001_engagement_features.sql
```

**Or manually:**
```sql
-- Connect to database
psql -h localhost -U etlegacy_user -d etlegacy

-- Run the migration
\i migrations/001_engagement_features.sql

-- Verify tables created
\dt mvp_votes
\dt player_titles
```

---

## ✅ Testing Checklist

### Pre-Testing Setup
- [ ] Pull latest `future-feature` branch from GitHub
- [ ] Run database migration script (see above)
- [ ] Verify tables created: `SELECT * FROM mvp_votes LIMIT 1;`
- [ ] Backup production database first!

### Test 1: Bot Startup
- [ ] Start bot: `python -m bot.ultimate_bot`
- [ ] Check for errors in startup logs
- [ ] Verify all cogs loaded successfully
- [ ] Check logging improvements are working

### Test 2: Logging System
- [ ] Check console output is cleaner
- [ ] Test different log levels if configurable
- [ ] Verify file logging still works

### Test 3: Server Update Command (if applicable)
- [ ] Run `!et_update` command
- [ ] Verify it attempts server update
- [ ] Check rollback works on failure
- [ ] Test pk3 upload to Discord

### Test 4: Engagement Features

#### MVP Voting
- [ ] Complete a gaming session
- [ ] Check if MVP voting appears automatically
- [ ] Test voting with Discord buttons
- [ ] Verify results are stored in database
- [ ] Check `mvp_votes` table has data

#### Title System
- [ ] Check existing player titles: `SELECT * FROM player_titles;`
- [ ] Play some games to trigger title unlocks
- [ ] Test title equip/unequip commands
- [ ] Verify titles display in stats

#### Rare Achievements
- [ ] Play rounds and watch for rare achievement alerts
- [ ] Test exceptional performance detection
- [ ] Verify alerts post to correct channel

#### Live Updates & Recaps
- [ ] Test live match tracking during games
- [ ] Check session recap at end of session
- [ ] Verify player insights commands work

### Test 5: Compatibility
- [ ] Verify old commands still work (`!stats`, `!leaderboard`, etc.)
- [ ] Check no conflicts between new features
- [ ] Test session start/end automation
- [ ] Verify SSH monitoring still works

### Test 6: Database Integrity
- [ ] Check no duplicate entries in new tables
- [ ] Verify foreign key relationships work
- [ ] Test that old data is unaffected
- [ ] Run `!database_info` command

---

## 🐛 Known Issues / Notes

1. **Database Migration**: Must be run before bot can use engagement features
2. **Placeholder Translation**: Database adapter automatically converts `?` to `$1, $2` for PostgreSQL
3. **Branch Compatibility**: All 3 features are independent and don't conflict
4. **Merge Conflict**: Only one conflict during merge (COMMANDS.md location) - already resolved

---

## 📊 Merge Commits in future-feature

```
832b803 - Add database schema for engagement features
65a051c - Merge server update command (Branch 1)
[commit] - Merge logging improvements (Branch 3)
[commit] - Merge engagement features (Branch 2)
```

---

## 🚀 After Testing

Once all tests pass:

1. **Create Pull Request:**
   ```bash
   # On GitHub:
   https://github.com/iamez/slomix/pull/new/future-feature
   ```

2. **Review PR** - Check all changes look good

3. **Merge to main:**
   ```bash
   git checkout main
   git merge future-feature
   git push origin main
   ```

4. **Tag release:**
   ```bash
   git tag -a v1.1.0 -m "Release 1.1: Engagement Features"
   git push origin v1.1.0
   ```

5. **Clean up branches:**
   ```bash
   # Delete old feature branches
   git branch -d future-feature
   git push origin --delete claude/add-server-update-bot-019p5VT6ABqShqVjM9JsR7Mc
   git push origin --delete claude/brainstorm-bot-features-01Rhg9mkFpZtacvfyZZhysBB
   git push origin --delete claude/improve-logging-console-01Gv4FGdpszGGZvcK4WRdoo1
   ```

---

## 🎮 Feature Highlights

### MVP Voting
- Automatically triggers after gaming sessions
- 5-minute voting window
- Interactive Discord buttons
- Results stored permanently
- Can check MVP history per player

### Player Titles (20+ Available)
**Combat Titles:**
- 🎯 Sharpshooter (35%+ headshot rate)
- 💀 Fragger (2.0+ K/D)
- ⚡ God Mode (3.0+ K/D)
- 👁️ Deadeye (50%+ headshot rate)

**Support Titles:**
- ⚕️ Medic (3+ revives/game)
- 🛡️ Guardian (5+ revives/game)

**Milestone Titles:**
- 🎖️ Veteran (100 games)
- 👑 Legend (500 games)
- 🌟 Immortal (1000 games)

**Special Titles:**
- 🏆 MVP (win MVP vote)
- 👑 Champion (5 MVP wins)
- 🗡️ Knife Master (5%+ knife kills)

### Rare Achievement Alerts
Automatically detects and announces:
- 🔥 40+ kills in a round
- 🎯 95%+ accuracy
- 💥 80%+ headshot rate
- 👑 Flawless victories (no deaths)
- 🌟 10+ K/D ratio
- 📈 Personal records broken

---

## 📝 Session Summary

**What we did today:**
1. ✅ Created `future-feature` branch from main
2. ✅ Merged 3 feature branches successfully
3. ✅ Resolved merge conflicts
4. ✅ Created database migration script
5. ✅ Updated documentation
6. ✅ Pushed to GitHub

**Branch Policy Reminder:**
- 🚨 NEVER commit directly to main
- ✅ Always use feature branches
- ✅ Test before merging
- ✅ Follow CONTRIBUTING.md guidelines

---

**Next Session:** Run through testing checklist and merge to main if all tests pass!

Good night! 😴
