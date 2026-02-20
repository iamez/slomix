# OmniBot Project Documentation

**Version**: 1.0
**Last Updated**: 2026-02-15
**Status**: DRY RUN PLAN (No server changes made)
**Objective**: Enable OmniBot AI-controlled players on ET:Legacy server for stats pipeline testing

---

## 1. Project Overview & Goals

### Why OmniBot?

The Slomix Discord bot's stats pipeline is designed to ingest real player match data from ET:Legacy. However, testing new features requires human participation, which is:

- **Time-intensive**: Recruiting players for controlled test sessions
- **Unreliable**: Player availability unpredictable
- **Hard to replicate**: Difficult to test specific edge cases consistently

**OmniBot solves this** by providing AI-controlled opponents that:

- Generate realistic match statistics (kills, deaths, captures, assists, etc.)
- Can be spawned/despawned on demand for testing
- Play autonomously without human input
- Produce data compatible with our stats pipeline

### Acceptance Criteria

- [ ] OmniBot spawns 6-8 bots on demand without server crashes
- [ ] Bot games produce valid match data in PostgreSQL
- [ ] Stats parser correctly processes bot game data
- [ ] Discord commands can filter/analyze bot game stats
- [ ] Bot-only scrim mode works on target maps
- [ ] Lua webhook handles bot entities without crashes
- [ ] Server can be rolled back to bot-disabled state within 5 minutes

---

## 2. CRITICAL SAFETY - The g_filterBan Incident

### What Happened (Feb 3-4, 2026)

An initial OmniBot enablement attempt resulted in **complete server lockdown**:

1. **Configuration**: Set `g_filterBan 0` (blacklist mode) with empty `g_banIPs`
2. **Behavior**: ET:Legacy interprets this as "exclude ALL players from server"
3. **Result**: Everyone, including the admin, got "excluded from server 0" error
4. **Impact**: 24+ hours of server downtime to restore via SSH access

### Root Cause

In ET:Legacy's filter ban system:
- `g_filterBan 0` = **Blacklist mode** (reject players in ban list)
- `g_filterBan 1` = **Whitelist mode** (accept only whitelisted players)
- Empty `g_banIPs` with mode 0 = "ban everything"

This is not intuitive and led to accidental total server exclusion.

### Prevention Checklist (MANDATORY)

- [ ] **Before doing ANYTHING else**: Verify current server.cfg has `g_filterBan 1` (whitelist mode)
- [ ] **Before touching config**: Take SSH backup: `cp /path/to/server.cfg /path/to/server.cfg.backup-$(date +%s)`
- [ ] **Before enabling bots**: Have SSH access verified and ready
- [ ] **Test sequence**: Enable bots, wait 30 seconds, connect as admin from known location
- [ ] **Kill switch**: Know exact RCON commands to disable bots immediately
- [ ] **Documentation**: Keep this incident report accessible during any future changes

### Fix Applied

Changed configuration to:
```
g_filterBan 1
g_banIPs ""
```

Result: Server functions normally, bots spawn without issues, players can connect freely.

### Lessons Learned

- **Always test on staging first** (or with minimal player impact time window)
- **Have SSH access ready** before making breaking changes
- **Verify config in server.cfg directly** via SSH, don't assume RCON changes persist
- **Test connectivity immediately** after any filter ban changes
- **Document the exact cvar state** before and after changes

---

## 3. Current Infrastructure Inventory

### What's Already Built

All these components exist in the repo and are ready to use:

#### A. Bot Names Configuration
- **File**: `/home/samba/share/slomix_discord/server/omnibot/et_botnames_ext.gm`
- **Current Bots** (11 total):
  - Axis (6): SuperBoyy, KomandantVarga, lagger, wajs, vid, olz
  - Allied (5): Olympus, carniee, bronze, endekk, Proner2026
- **Bot Prefix**: `^o[BOT]^7` (orange prefix in-game)
- **Overflow**: ExtraOne, ExtraTwo, ExtraThree (fallback if primary names depleted)
- **Class Distribution**: All 5 classes (Covert Ops, Engineer, Field Ops, Medic, Soldier) assigned per team

#### B. Map Rotation for Bot Games
- **File**: `/home/samba/share/slomix_discord/server/omnibot/bot_scrim_mapcycle.cfg`
- **Maps** (11 in cycle):
  1. etl_adlernest
  2. supply
  3. etl_sp_delivery
  4. te_escape2 (appears 2x in rotation)
  5. sw_goldrush_te
  6. et_brewdog
  7. etl_frostbite
  8. erdenberg_t2
  9. braundorf_b4
- **Mode**: Stopwatch (default ET:Legacy competitive mode)

#### C. Python Control Scripts
1. **omnibot_toggle.py** - Enable/disable OmniBot via RCON
   - Usage: `python scripts/omnibot_toggle.py on --min 6 --max 8`
   - Usage: `python scripts/omnibot_toggle.py off`
   - Requires: RCON_HOST, RCON_PORT, RCON_PASSWORD in .env

2. **bot_scrim_mode.py** - 3v3 bot-only scrim mode (6 bots, no BotsPerHuman)
   - Usage: `python scripts/bot_scrim_mode.py on`
   - Usage: `python scripts/bot_scrim_mode.py on --auto-ready`
   - Requires: Same RCON credentials

3. **generate_omnibot_botnames.py** - Generate fresh bot names from recent player DB
   - Queries `player_aliases` table for last 24 player names
   - Generates balanced class distribution across teams
   - Usage: `python scripts/generate_omnibot_botnames.py --limit 24 --prefix "^o[BOT]^7"`

#### D. Server Configuration (Current State)
- **Server**: puran.hehe.si (ET:Legacy v2.83.1-x86_64)
- **RCON Port**: 27960 (default)
- **Current Status**: `omnibot_enable 0` (DISABLED)
- **OmniBot Binaries**: Located at `/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/`

#### E. Known Lua Webhook Integration
- **File**: `vps_scripts/stats_discord_webhook.lua` (v1.6.0)
- **Status**: Fixed for bot entity crashes (safe_gentity_get wrapper with pcall)
- **Previous Issue**: Script crashed with "tried to get invalid gentity field pers.connected" when bots present
- **Fix Applied**: Safe entity getter prevents crashes on bot entities with missing fields

---

## 4. Prerequisites Checklist

### Network & Access

- [ ] SSH access to puran.hehe.si verified and working
- [ ] RCON credentials in .env: `RCON_HOST`, `RCON_PORT`, `RCON_PASSWORD`
- [ ] RCON password tested with simple command: `rcon "status"`
- [ ] PostgreSQL connection working: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DATABASE`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

### Server Configuration (CRITICAL)

- [ ] Via SSH, verify `/home/et/etlegacy*/et-linux.sh` uses correct server.cfg
- [ ] Verify `g_filterBan 1` is set in server.cfg
- [ ] Verify `g_banIPs ""` (empty) in server.cfg
- [ ] Verify `omnibot_enable 0` in server.cfg (currently disabled)
- [ ] Verify max player slots allow for 6-8 bots + expected humans
- [ ] Backup existing server.cfg before any changes

### Code & Environment

- [ ] Python 3.8+ available locally
- [ ] `.env` file exists with all RCON/POSTGRES credentials
- [ ] `requirements.txt` dependencies installed locally
- [ ] Git branch is clean or changes committed
- [ ] Database has `player_aliases` table (for bot name generation)

### Testing Environment

- [ ] Test machine can reach puran.hehe.si on port 27960
- [ ] ET:Legacy client installed on test machine
- [ ] Discord bot running and accessible for testing commands
- [ ] PostgreSQL accessible from local machine for query testing

### Documentation

- [ ] This document reviewed and understood
- [ ] SSH terminal window open and ready
- [ ] RCON commands reference available (see Section 9)
- [ ] Rollback procedure reviewed (Section 8)

---

## 5. Waypoint Map Compatibility

### What Are Waypoints?

Waypoints are navigation files (`.way` or `.nav` files) that teach OmniBot where to move on a map:
- Doors, corridors, sniping spots, objectives
- How to navigate around obstacles
- Team-specific spawn points and strategies

**Without waypoints**: Bots move randomly and accomplish little.
**With waypoints**: Bots play naturally and competitively.

### Map Status by Bot Scrim Rotation

| Map | Waypoints | Status | Notes |
|-----|-----------|--------|-------|
| **supply** | ✓ Good | READY | Excellent waypoint coverage, competitive classic map |
| **te_escape2** | ✓ Good | READY | Well-supported, Stopwatch friendly |
| **sw_goldrush_te** | ✓ Good | READY | Custom but fully waypointed |
| **etl_sp_delivery** | Partial | CAUTION | May have nav gaps on some objectives |
| **etl_adlernest** | ✗ Limited | RISK | Few/outdated waypoints, bots wander |
| **et_brewdog** | ✗ Limited | RISK | Waypoints may be incomplete or outdated |
| **etl_frostbite** | ✗ Limited | RISK | Limited waypoint coverage reported |
| **erdenberg_t2** | ✗ Limited | RISK | Waypoint availability unclear |
| **braundorf_b4** | ? Unknown | UNKNOWN | No clear information available |

### Recommendation for First Test Run

**Start with safe maps only**:
1. supply (best)
2. te_escape2 (excellent)
3. sw_goldrush_te (well-tested custom map)

Avoid maps with RISK/UNKNOWN status until waypoints verified via:
- Direct server testing (spawn bots, observe behavior)
- ET:Legacy/OmniBot documentation
- Community feedback

### How to Check Waypoints on Server

Via SSH, look for nav files in OmniBot directory:
```bash
find /home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot -name "*.way" -o -name "*.nav" | sort
# Check if specific map names appear
```

Alternatively, enable OmniBot on supply, spawn 2 bots, and observe:
- Do they move purposefully or randomly?
- Do they capture objectives?
- Do they get stuck in geometry?

---

## 6. Step-by-Step Enablement Plan (DRY RUN)

**This is what we WOULD do if we were going live. No actual server changes will be made.**

### Phase 1: Pre-Flight Verification (Estimated: 10 minutes)

1. **SSH into server**
   ```bash
   ssh et@puran.hehe.si
   ```

2. **Backup current server.cfg**
   ```bash
   cp /path/to/server.cfg /path/to/server.cfg.backup-$(date +%s)
   ```

3. **Verify g_filterBan state** (CRITICAL)
   ```bash
   grep "g_filterBan\|g_banIPs" /path/to/server.cfg
   # Expected output:
   # seta g_filterBan "1"
   # seta g_banIPs ""
   ```

4. **Verify omnibot_enable status**
   ```bash
   grep "omnibot_enable" /path/to/server.cfg
   # Expected: seta omnibot_enable "0"
   ```

5. **Check available player slots**
   ```bash
   grep "sv_maxclients\|g_maxGameClients" /path/to/server.cfg
   # Ensure at least 16+ (8 bots + 8 humans)
   ```

6. **Log current server status locally**
   ```bash
   # From dev machine:
   python scripts/omnibot_toggle.py off  # Verify current state
   ```

### Phase 2: Initial Bot Enablement (Estimated: 5 minutes)

7. **Enable bots with minimum count (SAFE START)**
   ```bash
   python scripts/omnibot_toggle.py on --min 2 --max 2
   ```
   - This spawns exactly 2 bots for testing
   - Easier to monitor, less resource impact
   - If this fails, revert immediately

8. **Wait 30 seconds for server to stabilize**

9. **Test connectivity as admin**
   - Open ET:Legacy client
   - Connect to puran.hehe.si
   - Verify you can join and see the 2 bots in-game
   - Check that bots have proper names (^o[BOT]^7 prefix)

10. **Check server console (via SSH)**
    ```bash
    tail -f /path/to/etlegacy.log
    # Look for errors like:
    # - "SV_GetUserinfo: bad index" (Lua crash)
    # - "Omni-bot Error" (bot initialization failure)
    # - "Parse error" (config syntax issue)
    ```

### Phase 3: Ramp to Full Capacity (Estimated: 5 minutes)

11. **Gradually increase bot count**
    ```bash
    # If 2 bots stable, try 4:
    python scripts/omnibot_toggle.py on --min 4 --max 4
    # Wait 30 sec, test

    # If 4 bots stable, go to target 6:
    python scripts/omnibot_toggle.py on --min 6 --max 8
    # Now we have dynamic 6-8 bots for better gameplay
    ```

12. **Test on safe map (supply)**
    ```bash
    # Via RCON:
    map supply
    # Wait for map to load
    # Observe bots playing naturally
    ```

13. **Monitor for Lua webhook issues**
    - Watch server logs for entity-related errors
    - If crashes occur, disable and revert to Phase 2

### Phase 4: Integration Testing (Estimated: 15 minutes)

14. **Generate fresh bot names from DB** (optional, good practice)
    ```bash
    python scripts/generate_omnibot_botnames.py --limit 24
    # This pulls recent player names and creates dynamic bot roster
    # Restart server for changes to take effect
    ```

15. **Run actual bot games**
    - Play 2-3 matches with bots
    - Monitor stats inserts into PostgreSQL
    - Check `player_stats` table for bot entries

16. **Test stats commands in Discord**
    - `/stats supply` (should include bot games)
    - `/leaderboard` (should show bot players separately if needed)
    - `/last-session` (should show bot game stats)

### Phase 5: Production State (Estimated: 5 minutes)

17. **Finalize configuration**
    ```bash
    python scripts/omnibot_toggle.py on --min 6 --max 8
    # OR for scrim mode:
    python scripts/bot_scrim_mode.py on
    ```

18. **Persist settings to server.cfg** (if keeping bots enabled long-term)
    ```bash
    # SSH into server
    # Add to server.cfg:
    set omnibot_enable 1
    set bot MinBots 6
    set bot MaxBots 8
    set bot BalanceTeams 1
    set bot BotTeam -1
    ```

19. **Restart server to apply persisted config**
    ```bash
    # Via RCON or systemctl:
    systemctl restart etlegacy-bot
    ```

20. **Final verification**
    - Test human player connection
    - Run diagnostic queries on bot game data
    - Confirm stats pipeline processes bot data correctly

---

## 7. Testing Plan (Start Small, Scale Gradually)

### Test Iteration 1: Minimal (2 Bots, 1 Map)

**Goal**: Verify server doesn't crash, Lua webhook is safe.

- **Setup**: 2 bots on supply map
- **Duration**: 2 matches (~20 minutes)
- **Monitoring**:
  - Server logs for crashes
  - Bots visible in-game
  - Server remains responsive
  - No "excluded from server" errors
- **Success Criteria**:
  - All bots stay connected
  - Server doesn't crash
  - Lua webhook handles bots without error
  - Server is accessible to humans

### Test Iteration 2: Moderate (4 Bots, 3 Maps)

**Goal**: Test map rotation, verify bot AI works on multiple maps, generate stats.

- **Setup**: 4 bots rotating through supply, te_escape2, sw_goldrush_te
- **Duration**: 4-6 matches (~45 minutes)
- **Monitoring**:
  - Server stability under light load
  - Bot behavior on different maps
  - Stats generation in PostgreSQL
  - Bot name variety and realism
- **Success Criteria**:
  - No server crashes
  - Bots play intelligently (capture objectives, not just wander)
  - Each match generates valid records in `player_stats`
  - Stats parser correctly identifies bot games
- **Database Queries**:
  ```sql
  -- Check bot games were inserted
  SELECT COUNT(*) FROM player_stats
  WHERE player_name LIKE '%[BOT]%' AND timestamp > NOW() - INTERVAL '1 hour';

  -- Check for parse errors
  SELECT COUNT(*) FROM player_stats
  WHERE player_name = 'unknown' OR player_guid IS NULL;
  ```

### Test Iteration 3: Full Capacity (6-8 Bots, Full Rotation)

**Goal**: Simulate production load, verify scalability, test scrim mode.

- **Setup**: 6-8 bots cycling through all 11 maps in bot_scrim_mapcycle
- **Duration**: 1-2 hours (continuous cycling)
- **Monitoring**:
  - Server CPU/memory under load
  - Stability over extended session
  - Lua webhook reliability with full player count
  - Map rotation works correctly
  - RCON responsiveness
- **Success Criteria**:
  - Server remains stable for 1+ hour
  - No performance degradation
  - All maps in rotation work
  - 20+ matches generate valid stats
  - Discord commands respond normally
  - Stats can be queried and displayed without lag

### Test Iteration 4: Hybrid (Humans + Bots)

**Goal**: Verify humans and bots coexist, stats correctly distinguish them.

- **Setup**: 4-6 bots with 2-4 human players
- **Duration**: 3-4 matches (~30 minutes)
- **Monitoring**:
  - Team balance (humans vs bots)
  - Stats accuracy (kills, deaths, captures)
  - Discord bot performance during mixed games
  - Player engagement with bot opponents
- **Success Criteria**:
  - Bots balanced across teams with humans
  - Stats distinguish humans from bots (or are correctly mixed)
  - No lag or crashes with mixed populations
  - Game is playable and enjoyable

### Rollback Thresholds

If ANY of these occur during testing, **immediately disable bots**:

- [ ] Server crash or restart loop
- [ ] "excluded from server" error appears
- [ ] Lua webhook crashes with entity errors
- [ ] Stats database becomes corrupted
- [ ] RCON becomes unresponsive
- [ ] Server CPU/memory usage > 90%
- [ ] Player connection timeout (humans can't join)
- [ ] Bot names not appearing in-game
- [ ] Game is unplayable (extreme lag)

**Immediate action**:
```bash
python scripts/omnibot_toggle.py off
# Wait 10 seconds for bots to despawn
# Test connectivity
```

---

## 8. Rollback Procedure (Emergency Recovery)

### Quick Kill Switch (< 1 minute)

If something goes wrong during testing:

```bash
# From local dev machine:
python scripts/omnibot_toggle.py off

# This executes:
# 1. bot MinBots -1
# 2. bot MaxBots -1
# 3. bot BotTeam -1
# 4. set omnibot_enable 0
```

**Verification**:
```bash
# Test connection
connect puran.hehe.si

# Via SSH, check status
grep "omnibot_enable" /path/to/server.cfg
# Should show: seta omnibot_enable "0"
```

### Manual SSH Rollback (If RCON Fails)

If RCON becomes unresponsive, SSH into the server:

```bash
ssh et@puran.hehe.si

# Option A: Edit server.cfg directly
nano /path/to/server.cfg
# Find these lines and change:
# seta omnibot_enable "1" → "0"
# seta bot MinBots "6" → "-1"
# seta bot MaxBots "8" → "-1"

# Option B: Restart server with original config
systemctl restart etlegacy-bot

# Wait 30 seconds
# Verify bots are gone
rcon "status" # Should show 0 bots
```

### Full Server Reset (Nuclear Option)

If the server is completely broken:

```bash
# SSH into server
ssh et@puran.hehe.si

# Restore from backup
cp /path/to/server.cfg.backup-* /path/to/server.cfg

# Restart
systemctl restart etlegacy-bot

# Verify connectivity from local machine
connect puran.hehe.si
```

### Recovery Checklist

After rollback:

- [ ] Can connect to server as human player
- [ ] No "excluded from server" error
- [ ] Server responds to RCON commands
- [ ] Database remains intact (no corruption)
- [ ] Check logs for any errors: `tail -50 /path/to/etlegacy.log`
- [ ] Run integrity check on stats table (see Phase 4, step 15)

---

## 9. Stats Integration Notes

### How Bot Games Enter the Pipeline

1. **OmniBot plays a match** (R1, then R2 after match ends)
2. **ET:Legacy dumps stats files** to `/home/et/etlegacy*/stats/` (e.g., `statsXXXXXX_R1.txt`)
3. **SSH monitor or manual trigger** reads files via Python/ET:Legacy parsing
4. **community_stats_parser.py** processes R1 + R2, handles R2 differential
5. **Stats inserted into PostgreSQL** `player_stats` table
6. **Discord bot queries table** and displays stats in commands

### Identifying Bot Games in Data

Bot stats rows will have:

```sql
SELECT * FROM player_stats
WHERE player_name LIKE '%[BOT]%'
LIMIT 5;

-- Result example:
-- player_name: ^o[BOT]^7SuperBoyy
-- player_guid: (some OmniBot GUID)
-- kills: 18
-- deaths: 12
-- captures: 2
-- etc.
```

### Filtering Bot Games from Leaderboards

If you want human-only leaderboards:

```sql
WHERE player_name NOT LIKE '%[BOT]%'
```

If you want to track bots separately:

```sql
WHERE player_name LIKE '%[BOT]%'
```

### Stats Pipeline Validation

After running bot games, verify:

1. **New rows inserted**:
   ```sql
   SELECT COUNT(*) FROM player_stats
   WHERE timestamp > NOW() - INTERVAL '2 hours'
   AND player_name LIKE '%[BOT]%';
   -- Should return > 0 if games ran
   ```

2. **No parser errors**:
   ```sql
   SELECT * FROM player_stats
   WHERE player_name = 'unknown' OR player_guid IS NULL
   LIMIT 10;
   -- Should return 0 rows if parser is healthy
   ```

3. **Round matching works**:
   ```sql
   SELECT
     gaming_session_id,
     COUNT(*) as match_count,
     SUM(kills) as total_kills
   FROM player_stats
   WHERE timestamp > NOW() - INTERVAL '2 hours'
   AND player_name LIKE '%[BOT]%'
   GROUP BY gaming_session_id;
   -- Should show reasonable numbers
   ```

4. **Discord commands work**:
   - Run `/leaderboard supply` - bot names should appear
   - Run `/last-session` - should show bot game stats
   - Run `/stats [botname]` - should display individual bot stats

### Known Parser Considerations

- **R2 Differential**: Parser automatically subtracts R1 from R2 stats (bot kills will show R2 - R1)
- **Bot GUIDs**: OmniBot assigns consistent GUIDs; same bot should have same GUID across games
- **Name Changes**: If you regenerate bot names mid-testing, old names won't match new entries (separate historical records)
- **Session Grouping**: Bots in same match should have same `gaming_session_id` and `timestamp`

---

## 10. Known Issues & Risks

### Issue: Waypoints Gaps on Some Maps

**Maps Affected**: etl_adlernest, et_brewdog, etl_frostbite, erdenberg_t2, braundorf_b4

**Symptoms**:
- Bots spawn but stand idle
- Bots move in straight lines, not around obstacles
- Bots ignore objectives (flags, dynamite)
- Bots get stuck in geometry

**Mitigation**:
- Start testing with supply + te_escape2 only
- Create waypoints for other maps (advanced, requires community tools)
- Use test results to prioritize which maps to improve

**Resolution**:
- Contact ET:Legacy community for updated waypoint files
- Generate waypoints manually using OmniBot's navigation editor
- Consider limiting bot games to well-waypointed maps permanently

---

### Issue: Lua Webhook Crash with Bots

**Symptoms**: Server crashes with message like:
```
SV_GetUserinfo: bad index 1022
tried to get invalid gentity field pers.connected
```

**Root Cause**: Lua script iterates over player entities and accesses fields that don't exist for bot entities (e.g., `pers.connected`).

**Status**: **FIXED in v1.6.0** of stats_discord_webhook.lua

**Fix Applied**: Wrapped entity field access in safe_gentity_get() function with pcall error handling:
```lua
function safe_gentity_get(entity, field)
  local ok, result = pcall(function() return entity[field] end)
  if ok then return result else return nil end
end
```

**Verification**: Check that vps_scripts/stats_discord_webhook.lua includes the safe_gentity_get wrapper.

---

### Issue: Memory/Performance with Too Many Bots

**Symptoms**:
- Server CPU usage spikes to 100%
- Human player movement becomes choppy/laggy
- RCON commands timeout
- Server becomes unresponsive

**Cause**: Each bot runs pathfinding, aim, team logic. 8 bots = significant CPU.

**Mitigation**:
- Start with 2-4 bots for testing
- Monitor `top` command on server: `top -p $(pidof etl)`
- If CPU > 80%, reduce bot count

**Thresholds**:
- 2 bots: Safe, minimal impact
- 4 bots: Low impact, suitable for extended testing
- 6-8 bots: Production target, requires monitoring
- 10+ bots: Not recommended without dedicated server

---

### Issue: Bot Name Collisions

**Symptoms**:
- Two bots spawn with the same name
- Player list shows duplicates
- Stats confuse which bot is which

**Cause**: If bot name list is incomplete or fallback is triggered too early.

**Mitigation**:
- Ensure et_botnames_ext.gm has at least 10 unique names per team
- Run generate_omnibot_botnames.py before long test sessions
- Check overflow ExtraBots list for diversity

**Resolution**:
```bash
python scripts/generate_omnibot_botnames.py --limit 50 --prefix "^o[BOT]^7"
# Pulls more names from DB, reduces collision risk
```

---

### Issue: g_filterBan Misconfiguration (Again)

**Symptoms**: "excluded from server 0" error when connecting

**Cause**: Someone changes g_filterBan incorrectly (again)

**Mitigation**:
- Test connectivity immediately after any server.cfg change
- Keep this document visible during work
- Add verification step to any CI/CD pipeline

**Resolution**:
```bash
# Via SSH:
grep "g_filterBan" /path/to/server.cfg
# Fix: must be seta g_filterBan "1"
```

---

### Issue: RCON Credentials Wrong in .env

**Symptoms**: `omnibot_toggle.py` reports connection timeout or auth error

**Cause**: RCON_PASSWORD doesn't match server.cfg, or RCON_HOST is unreachable

**Mitigation**:
- Test RCON manually before running scripts: `python -c "from scripts.omnibot_toggle import send_rcon; print(send_rcon(...))"`
- Keep RCON_PASSWORD in sync between .env and server.cfg
- Verify network connectivity to RCON_HOST:RCON_PORT

**Resolution**:
```bash
# SSH into server, check RCON config
grep "rconPassword" /path/to/server.cfg
# Update .env to match
# Test manually
```

---

### Issue: Bot Games Don't Generate Stats

**Symptoms**: Bots play matches but no rows appear in player_stats table

**Cause**:
- Stats file not generated (bots played but file wasn't dumped)
- Parser not running (SSH monitor disabled or not triggering)
- Database insert failing silently

**Mitigation**:
- Ensure SSH monitor is active: `systemctl status endstats_monitor`
- Check that stats files are being created: `ls -lah /home/et/etlegacy*/stats/`
- Verify parser runs on stats file: Check bot logs for parser execution
- Check database for insert errors: Query error logs

**Resolution**:
```bash
# Manually trigger stats parsing if SSH monitor is slow
python community_stats_parser.py --file /home/et/etlegacy*/stats/statsXXXXXX_R1.txt

# Verify insertion
SELECT COUNT(*) FROM player_stats WHERE player_name LIKE '%[BOT]%';
```

---

## 11. Open Questions

These questions should be resolved before full production deployment:

### Q1: Should bot games be counted in human leaderboards?

**Options**:
- A. Include bots in leaderboards (simpler, fewer code changes)
- B. Exclude bots from public leaderboards (more realistic, requires WHERE clause updates)
- C. Separate leaderboards for humans vs. bots

**Decision Needed**: [ ] Choose option A / B / C

**Impact**: Affects 15+ commands that query leaderboard stats

---

### Q2: How should we tag bot game sessions?

**Options**:
- A. Use gaming_session_id to identify bot games (complex query logic)
- B. Add a "is_bot_game" column to player_stats (schema change)
- C. Use player_name prefix to identify (fragile, depends on naming)

**Decision Needed**: [ ] Choose option A / B / C

**Impact**: Makes filtering bot games easier in Discord commands

---

### Q3: Should we keep bots enabled permanently or enable only during testing?

**Options**:
- A. Permanent: Bots always online, generate continuous test data
- B. On-demand: Enable via command when testing, disable otherwise
- C. Scheduled: Enable during designated test windows (e.g., Friday 10am)

**Decision Needed**: [ ] Choose option A / B / C

**Impact**:
- A: More data for testing, but server always has bots
- B: Cleaner production, but requires manual enablement
- C: Scheduled, predictable, but limited testing windows

---

### Q4: What's the plan for waypoint improvements?

**Current State**: Some maps lack good waypoints, bots wander.

**Options**:
- A. Use only supply + te_escape2 (limited)
- B. Generate waypoints using community tools
- C. Request waypoints from ET:Legacy community
- D. Accept limited bot behavior on some maps (pragmatic)

**Decision Needed**: [ ] Choose option A / B / C / D

**Impact**: Determines which maps can support realistic bot gameplay

---

### Q5: How do we validate stats data quality from bot games?

**Current State**: Assuming parser produces correct output.

**Questions**:
- Are bot kills realistic (not 0 or 100)?
- Do captures match map objectives?
- Do assist counts make sense?
- Are there obvious data anomalies?

**Decision Needed**: [ ] Set up automated validation queries

**Impact**: Prevents bad data from polluting leaderboards

---

## 12. Quick Reference: RCON Commands

### Bot Control Commands

Enable bots (6-8 in rotation):
```
set omnibot_enable 1
bot MinBots 6
bot MaxBots 8
bot BalanceTeams 1
bot BotTeam -1
bot HumanTeam 1
bot BotsPerHuman 3
```

Disable bots:
```
bot MinBots -1
bot MaxBots -1
bot BotTeam -1
set omnibot_enable 0
```

Scrim mode (6v6 bots, no humans):
```
set omnibot_enable 1
bot MinBots 6
bot MaxBots 6
bot BotsPerHuman 0
set match_readypercent 0
set match_minplayers 0
```

### Map Control

Load supply:
```
map supply
```

Cycle next map:
```
vstr nextmap
```

Load scrim rotation:
```
exec bot_scrim_mapcycle.cfg
vstr scrim_d1
```

### Server Status

Check current state:
```
status
```

Check omnibot status:
```
set omnibot_enable
bot MinBots
bot MaxBots
```

### Admin Commands

Ready all players (for scrim):
```
ref allready
```

Restart round (without changing map):
```
map_restart 0
```

---

## 13. File Reference

| File | Purpose | Location |
|------|---------|----------|
| et_botnames_ext.gm | Bot name config (11 bots, class distribution) | server/omnibot/et_botnames_ext.gm |
| bot_scrim_mapcycle.cfg | Map rotation (11 maps, Stopwatch) | server/omnibot/bot_scrim_mapcycle.cfg |
| omnibot_toggle.py | Enable/disable bots via RCON | scripts/omnibot_toggle.py |
| bot_scrim_mode.py | 3v3 bot-only scrim mode | scripts/bot_scrim_mode.py |
| generate_omnibot_botnames.py | Generate bot names from DB | scripts/generate_omnibot_botnames.py |
| community_stats_parser.py | Parse stats files (R1/R2 differential) | community_stats_parser.py |
| stats_discord_webhook.lua | Real-time stats webhook (v1.6.0 with safe_gentity_get) | vps_scripts/stats_discord_webhook.lua |
| server.cfg | Game server config (g_filterBan, omnibot_enable) | /home/et/etlegacy*/server.cfg |

---

## 14. Success Criteria Checklist

### Must Have (Blocking)

- [ ] Server doesn't crash when enabling bots
- [ ] No "excluded from server" errors
- [ ] Lua webhook handles bots without crashing
- [ ] Bots spawn and are visible in-game
- [ ] Human players can connect and play with bots
- [ ] Bot games generate valid stats in PostgreSQL
- [ ] Stats parser correctly processes bot data
- [ ] Rollback procedure works (can disable bots quickly)

### Should Have (Recommended)

- [ ] Bots play intelligently on primary maps (supply, te_escape2)
- [ ] Bot names are realistic and varied
- [ ] Server remains stable for 1+ hour continuous play
- [ ] Discord stats commands work with bot game data
- [ ] Waypoint coverage verified for bot scrim rotation

### Nice to Have (Optimization)

- [ ] Bots also function well on secondary maps
- [ ] Performance optimized (minimal CPU impact)
- [ ] Bot games tagged/separated from human games in DB
- [ ] Automated validation of bot game data quality
- [ ] Public leaderboard decision made (include vs. exclude bots)

---

## 15. Contact & Escalation

### If Something Goes Wrong

1. **First**: Review Section 8 (Rollback Procedure)
2. **Second**: Check Section 10 (Known Issues) for your specific symptom
3. **Third**: Consult server logs: `tail -100 /path/to/etlegacy.log`
4. **Fourth**: Disable bots immediately (Section 8, Quick Kill Switch)
5. **Fifth**: File bug report with:
   - Exact error message
   - Timestamp of incident
   - Bot count at time of issue
   - Current map
   - Relevant server logs
   - Database state if applicable

### Resources

- ET:Legacy Documentation: https://github.com/etlegacy/etlegacy (see Lua/OmniBot sections)
- OmniBot Framework: [Embedded in ET:Legacy v2.76+]
- CLAUDE.md: See CRITICAL RULES section
- AI_COMPREHENSIVE_SYSTEM_GUIDE.md: See data pipeline section

---

## Appendix A: OmniBot Configuration Reference

### et_botnames_ext.gm Structure

```gamemonkey
// Team tables with loadout configs
AxisBots = {
  "BotName" = { class=CLASS.SOLDIER, weapon=0, profile="" }
}
AlliedBots = { ... }

// Prefix added to all bot names
BotPrefix = "^o[BOT]^7"

// Overflow if primary names exhausted
ExtraBots = { "ExtraOne", "ExtraTwo", ... }

// Called when OmniBot needs to spawn a new player
OnBotAutoJoin() {
  // Returns { class, team, name }
}
```

### Server.cfg OmniBot Settings

```cfg
// Enable/disable OmniBot entirely
seta omnibot_enable "0"

// Minimum bots to maintain
set bot MinBots "6"

// Maximum bots allowed
set bot MaxBots "8"

// Auto-balance teams
set bot BalanceTeams "1"

// -1: bots fill both teams, 1: axis only, 2: allies only
set bot BotTeam "-1"

// Which human team is preferred
set bot HumanTeam "1"

// Humans per bot ratio (3 = 3 humans per bot, 0 = no limit)
set bot BotsPerHuman "3"

// Path to OmniBot installation
set omnibot_path "/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot"
```

---

## Appendix B: Example Test Session Log

```
[14:30:00] Starting OmniBot enablement test
[14:30:15] SSH verified to puran.hehe.si
[14:30:30] Verified g_filterBan 1 in server.cfg
[14:30:45] Backup created: server.cfg.backup-1707979845
[14:31:00] Executing: python scripts/omnibot_toggle.py on --min 2 --max 2
[14:31:05] [RCON] set omnibot_enable 1
[14:31:06] [RCON] bot MinBots 2
[14:31:07] [RCON] bot MaxBots 2
[14:31:10] SUCCESS: Bot commands sent
[14:31:30] Connected to server as human player
[14:31:35] Verified: 2 bots visible (^o[BOT]^7SuperBoyy, ^o[BOT]^7carniee)
[14:31:40] No server crash detected
[14:31:45] Checked server logs: No Lua errors
[14:32:00] Map loaded: supply (bots moving to objectives)
[14:32:15] Running: SELECT COUNT(*) FROM player_stats WHERE timestamp > NOW() - INTERVAL '5 min'
[14:32:16] Result: 12 rows (bot stats inserted successfully)
[14:32:30] Test PASSED: Ready to scale to 4 bots
[14:33:00] Executed: python scripts/omnibot_toggle.py on --min 4 --max 4
[14:33:15] Verified: 4 bots visible, server stable
[14:35:00] Match completed, 24 new bot stat rows inserted
[14:35:15] All tests PASSED: OmniBot working as expected
```

---

## Document Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-15 | Initial comprehensive documentation (DRY RUN) |

---

**Status**: READY FOR TESTING (When authorized)
**Last Reviewed**: 2026-02-15
**Next Review Date**: Upon first actual test run
