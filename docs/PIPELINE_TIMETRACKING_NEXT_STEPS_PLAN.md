# Pipeline Time-Tracking Next Steps Plan

> **Date:** 2026-02-20
> **Scope:** Phased rollout plan for time-tracking pipeline improvements
> **Status:** Plan only - no code changes made, no migrations executed
> **Prerequisites:** Read `PIPELINE_TIMETRACKING_RESEARCH_SYNTHESIS.md` and `PIPELINE_TIMETRACKING_GAP_ANALYSIS.md` first

---

## Phased Rollout Plan

### Phase 0: Operational Cleanup (No Code Changes)

**Goal:** Remove known noise sources and verify baseline before any code deployment.

| Step | Action | Verify | Rollback |
|------|--------|--------|----------|
| 0.1 | Disable `et-stats-webhook.service` on game server | `systemctl is-active et-stats-webhook.service` returns `inactive` | `systemctl enable --now et-stats-webhook.service` |
| 0.2 | Ensure single `log_monitor.sh` process | `pgrep -fc log_monitor.sh` returns `1` | Restart from cron |
| 0.3 | Verify current Lua versions on game server | `grep -n "version" /home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/*.lua` | N/A (read-only) |
| 0.4 | Snapshot current `lua_round_teams` coverage for R1/R2 | SQL: `SELECT round_number, COUNT(*) FROM lua_round_teams GROUP BY round_number` | N/A (read-only) |
| 0.5 | Check `SHOW_TIMING_DUAL` flag status on VM | `grep SHOW_TIMING_DUAL /opt/slomix/.env` | N/A (read-only) |

**Gate:** All 5 steps verified before proceeding to Phase 1.

---

### Phase 1: Fix R2 Webhook Crash (Lua Change - Webhook Only)

**Goal:** Fix the `string.format` crash on fractional R2 timelimit that causes all R2 webhook data loss.

**Why first:** This is the single highest-impact fix. Without it, ~50% of rounds (all R2s with fractional timelimit) lose webhook metadata. Every subsequent improvement depends on this data existing.

| Step | Action | File | Details |
|------|--------|------|---------|
| 1.1 | Wrap timelimit in `math.floor()` before `%d` formatting | `vps_scripts/stats_discord_webhook.lua:830` | `math.floor(time_limit + 0.5)` or use `%s` with `tostring(math.floor(...))` |
| 1.2 | Wrap `send_webhook()` payload construction in `pcall` | `vps_scripts/stats_discord_webhook.lua:~780-931` | Ensure `send_in_progress = false` in all exit paths (success and failure) |
| 1.3 | Add guardrail log before payload format | `vps_scripts/stats_discord_webhook.lua:~829` | `et.G_Print("[stats_discord_webhook] timelimit=" .. tostring(time_limit) .. " type=" .. type(time_limit))` |
| 1.4 | On payload build failure, still attempt gametime fallback write | After `pcall` catch block | Write sanitized metadata to `gametime-*.json` even if Discord webhook fails |

**Deployment:**
```bash
# 1. Sync fixed webhook Lua to game server
scp -P 48101 -i ~/.ssh/etlegacy_bot vps_scripts/stats_discord_webhook.lua et@puran.hehe.si:/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/

# 2. Lua hot-reloads on next map change (no server restart needed)
```

**Validation:**
```bash
# After next live stopwatch R1/R2 pair:
# 1. No format errors in server console
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "grep -n 'bad argument' /home/et/.etlegacy/legacy/etconsole.log | tail -5"
# Expected: no new lines

# 2. STATS_READY for both R1 and R2
grep "STATS_READY" logs/webhook.log | tail -10
# Expected: entries for both round 1 and round 2

# 3. lua_round_teams has R2 rows
PGPASSWORD='...' psql -h localhost -U etlegacy_user -d etlegacy \
  -c "SELECT round_number, COUNT(*) FROM lua_round_teams WHERE captured_at > NOW() - INTERVAL '1 day' GROUP BY round_number"
# Expected: both round_number=1 and round_number=2 have rows
```

**Rollback:** Restore previous `stats_discord_webhook.lua` from `deployed_lua/legacy/luascripts/` backup.

**Gate:** At least 1 complete R1+R2 pair with both `lua_round_teams` rows persisted.

---

### Phase 2: Merge c0rnp0rn Time Tracking + LuaJIT Patches

**Goal:** Create a production-ready stats Lua that combines time-tracking features from the test file with LuaJIT compatibility from c0rnp0rn7.

**What gets merged:**

| From `c0rnp0rn-testluawithtimetracking.lua` | From `c0rnp0rn7.lua` |
|----------------------------------------------|----------------------|
| `roundStart`, `roundEnd`, `pausedTime` variables | `ensure_bit_compat()` function |
| `roundStart = et.trap_Milliseconds()` in et_RunFrame | `bit.rshift()`, `bit.bor()`, `bit.band()`, `bit.lshift()` calls |
| `roundEnd = et.trap_Milliseconds()` on intermission | `ensure_max_clients()` safety wrapper |
| `pausedTime[1,2,3]` tracking in pause detection | `to_int()` utility function |
| Header field 9 = `roundEnd-roundStart-(pausedTime[3] or 0)` | `fallback_band()`, `fallback_bor()` functions |

**Result file:** Single `c0rnp0rn3.lua` (or whatever naming the developer prefers) with both feature sets.

**Verification:**
```bash
# 1. LuaJIT compatibility scan (must return no findings)
tmpdir=$(mktemp -d)
cp merged_c0rnp0rn.lua "$tmpdir/"
python3 /tmp/check-etl-luajit-incompatibilities --root "$tmpdir"

# 2. Parse test with 9-field header
python3 -c "
from bot.community_stats_parser import CommunityStatsParser
parser = CommunityStatsParser()
# Create a test file with 9-field header and verify parsing
"
```

**Gate:** Clean LuaJIT scan + parser successfully reads 9-field header.

---

### Phase 3: Parser Enhancement for Field 9

**Goal:** Use the new header field 9 (actual playtime in ms) when available for more accurate round duration.

| Step | Action | File:Line | Details |
|------|--------|-----------|---------|
| 3.1 | Verify parser already extracts field 9 | `community_stats_parser.py:~963` | It does: `actual_playtime_seconds` variable |
| 3.2 | Use field 9 for `round_time_seconds` when present | `community_stats_parser.py:~973-980` | `if actual_playtime_seconds: round_time_seconds = int(actual_playtime_seconds)` (already implemented) |
| 3.3 | Add logging when field 9 is used vs header fallback | After line 980 | `logger.debug(f"Round time source: {'field9' if actual_playtime_seconds else 'header'}")` |

**Backward Compatibility:**
- 8-field headers (old Lua) continue to work (existing fallback path)
- 9-field headers (new Lua) use the more accurate value
- No historical data recalculation needed

**Gate:** One round parsed with field 9 source logged; no regression on existing stats files.

---

### Phase 4: Deploy Merged Lua to Game Server

**Goal:** Replace `c0rnp0rn7.lua` with merged version on game server.

**Deployment checklist:**
1. Backup current deployed version: `cp c0rnp0rn7.lua c0rnp0rn7.lua.bak`
2. Deploy merged file
3. Wait for map change (Lua hot-reloads)
4. Verify stats file written with 9 fields in header
5. Verify parser processes new file correctly
6. Verify no LuaJIT errors in server console

**Validation:**
```bash
# Check latest stats file has 9-field header
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "ls -lt /home/et/.etlegacy/legacy/gamestats/*.txt | head -1"
# Then read header and count backslash-separated fields

# Check bot parsed it successfully
grep "Round time source" logs/bot.log | tail -5
```

**Rollback:** Restore backup `c0rnp0rn7.lua.bak`.

---

### Phase 5: Evaluate Timing Shadow Cutover

**Goal:** Decide whether to switch from dual OLD/NEW timing to NEW-only.

**Decision criteria:**
- Lua coverage rate for recent sessions (target: >80% of rounds have `lua_spawn_stats` data)
- Shadow diff magnitude (are OLD and NEW values substantially different?)
- No formatting regressions in Discord embeds
- `!last_session_debug` shows acceptable deltas

**If coverage is sufficient:** Set `SHOW_TIMING_DUAL=false`, restart bot, monitor for 1 session.
**If coverage is low:** Keep dual display, investigate coverage gaps.

---

### Phase 6: Website Formula Alignment (Independent)

**Goal:** Fix website formulas to match bot. This is independent of the Lua changes but should happen during this window.

| Fix | Current Formula | Correct Formula | File:Line |
|-----|----------------|-----------------|-----------|
| FragPotential | `(kills + assists*0.5) / time_min * 10` | `(damage_given / time_alive_sec) * 60` | `api.py:4896-4897` |
| Survival Rate | `min(100, avg_death_time / 60 * 10)` | `100 - (time_dead_min / time_played_min * 100)` | `api.py:4908-4909` |
| Damage Efficiency | `dmg_given / (dmg_given + dmg_recv) * 100` | `dmg_given / max(1, dmg_recv)` | `api.py:4900-4903` |

---

## Backward Compatibility Strategy

### Option A: Transparent Upgrade (Recommended)

- New Lua writes 9-field header; parser already handles both 8 and 9 fields
- No schema migration needed (field 9 is consumed at parse time, not stored separately)
- Old stats files in `local_stats/` continue to parse correctly
- Webhook changes (Phase 1) are backward-compatible (same payload schema)

### Option B: Versioned Stats Format

- Add a `stats_version` field to header (e.g., `v2` for 9-field)
- Parser branches on version for field extraction
- More explicit but unnecessary given current parser flexibility

**Recommendation:** Option A. The parser already handles the optional 9th field. No version flag needed.

---

## DB Migration Outline

### Required Migrations: NONE for Phases 1-4

The existing schema (`lua_round_teams`, `lua_spawn_stats`, `player_comprehensive_stats`) already has all needed columns. The improvements are:
- Better data quality (R2 webhook data no longer lost)
- Better round duration accuracy (field 9 from stats file header)
- No new columns needed

### Future Migration (If Per-Player Time Overhaul Proceeds)

If Phase 6+ adds per-player time fields to the webhook (per KNOWN_ISSUES.md plan):

**Forward migration (outline):**
```sql
-- Add per-player time columns to player_comprehensive_stats
ALTER TABLE player_comprehensive_stats ADD COLUMN IF NOT EXISTS time_alive_seconds INTEGER;
ALTER TABLE player_comprehensive_stats ADD COLUMN IF NOT EXISTS avg_respawn_seconds FLOAT;
ALTER TABLE player_comprehensive_stats ADD COLUMN IF NOT EXISTS longest_life_seconds INTEGER;
ALTER TABLE player_comprehensive_stats ADD COLUMN IF NOT EXISTS longest_death_seconds INTEGER;
-- All default NULL for backward compatibility
```

**Rollback migration:**
```sql
ALTER TABLE player_comprehensive_stats DROP COLUMN IF EXISTS time_alive_seconds;
ALTER TABLE player_comprehensive_stats DROP COLUMN IF EXISTS avg_respawn_seconds;
ALTER TABLE player_comprehensive_stats DROP COLUMN IF EXISTS longest_life_seconds;
ALTER TABLE player_comprehensive_stats DROP COLUMN IF EXISTS longest_death_seconds;
```

**DO NOT RUN THESE** - outline only for future planning.

---

## Validation Runbook Outline (Commands to Run Later)

### Pre-Deployment Baseline
```bash
# Capture current state
PGPASSWORD='...' psql -h localhost -U etlegacy_user -d etlegacy -c "
  SELECT 'lua_round_teams' AS tbl, COUNT(*) FROM lua_round_teams
  UNION ALL
  SELECT 'lua_spawn_stats', COUNT(*) FROM lua_spawn_stats
  UNION ALL
  SELECT 'rounds', COUNT(*) FROM rounds WHERE round_date >= '2026-02-20'
"
```

### Post-Phase-1 (Webhook Fix)
```bash
# After 1 live session with R1+R2:
PGPASSWORD='...' psql -h localhost -U etlegacy_user -d etlegacy -c "
  SELECT r.id, r.map_name, r.round_number,
         COALESCE(l.id::text, 'MISSING') AS lua_id,
         COALESCE(l.actual_duration_seconds::text, 'NULL') AS lua_duration
  FROM rounds r
  LEFT JOIN lua_round_teams l ON l.round_id = r.id
  WHERE r.round_date >= CURRENT_DATE
  ORDER BY r.id DESC LIMIT 20
"
# Expected: Both R1 and R2 rows have non-NULL lua_id
```

### Post-Phase-4 (New Stats Lua Deployed)
```bash
# Verify 9-field header in latest stats file
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "head -1 \$(ls -t /home/et/.etlegacy/legacy/gamestats/*.txt | head -1)"
# Expected: 9 backslash-delimited fields (last = milliseconds number)

# Verify parser accepted it
grep -E "actual_playtime|Round time source" logs/bot.log | tail -10
```

---

## Test Plan Outline

### Golden Payload Test
1. Create a synthetic 9-field stats file header
2. Parse with `CommunityStatsParser`
3. Assert `actual_playtime_seconds` is extracted
4. Assert `round_time_seconds` uses field 9 value when present
5. Assert `round_time_seconds` falls back to field 8 when field 9 absent

### Timing Invariant Tests
1. For any round with webhook data: `abs(actual_duration_seconds - (round_end_unix - round_start_unix - total_pause_seconds)) < 2`
2. For any player: `time_dead_minutes * 60 <= time_played_seconds`
3. For any round: `time_played_seconds > 0`

### Integration Proof
1. Play one live R1+R2 pair after all Lua changes deployed
2. Verify `lua_round_teams` has rows for both rounds
3. Verify `lua_spawn_stats` has per-player rows
4. Verify `!last_session` shows accurate timing (no `NO LUA DATA`)
5. Verify website `/api/sessions` returns timing data
6. Verify timing shadow deltas are small for Lua-covered rounds

---

## Execution Phase TODO Checklist

After this plan is reviewed and approved, execute in this order:

- [ ] **Phase 0.1:** SSH to game server, disable `et-stats-webhook.service`
- [ ] **Phase 0.2:** Verify single `log_monitor.sh` process
- [ ] **Phase 0.3:** Snapshot current Lua versions and `lua_round_teams` counts
- [ ] **Phase 0.4:** Verify `SHOW_TIMING_DUAL` status on VM
- [ ] **Phase 1.1:** Fix `%d` crash in `stats_discord_webhook.lua`
- [ ] **Phase 1.2:** Add `pcall` wrapping in `send_webhook()`
- [ ] **Phase 1.3:** Deploy fixed webhook Lua to game server
- [ ] **Phase 1.4:** Validate on next live R1/R2 pair
- [ ] **Phase 2.1:** Merge time-tracking + LuaJIT patches into single c0rnp0rn file
- [ ] **Phase 2.2:** Run LuaJIT compatibility scan on merged file
- [ ] **Phase 2.3:** Test parser with 9-field header sample
- [ ] **Phase 3.1:** Add parser logging for field 9 usage
- [ ] **Phase 4.1:** Deploy merged c0rnp0rn to game server
- [ ] **Phase 4.2:** Validate 9-field header in fresh stats file
- [ ] **Phase 4.3:** Validate parser processes it correctly
- [ ] **Phase 5.1:** Review timing shadow coverage metrics
- [ ] **Phase 5.2:** Make cutover decision (NEW-only or keep dual)
- [ ] **Phase 6.1:** Fix website FragPotential, Survival Rate, Damage Efficiency formulas
- [ ] **Phase 6.2:** Fix headshot leaderboard mixed-units bug

**STOP HERE. Do not execute until plan is reviewed.**

---

*See companion docs:*
- *Research Synthesis: `docs/PIPELINE_TIMETRACKING_RESEARCH_SYNTHESIS.md`*
- *Gap Analysis: `docs/PIPELINE_TIMETRACKING_GAP_ANALYSIS.md`*
