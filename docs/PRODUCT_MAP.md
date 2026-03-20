# Slomix Product Map — The Whiteboard

**Version**: 1.0.8 | **Last Updated**: 2026-03-02 | **Audience**: Personal orientation + Onboarding + Future recovery

---

## 🎯 What Is This Product

Slomix is a **Discord bot + website** that turns raw ET:Legacy game statistics into actionable player insights. The bot parses real-time stats from the community's game server, stores them in PostgreSQL, and serves 80+ Discord commands that players use to analyze their performance, track team records, view leaderboards, and understand how they played in the last session. The website provides a full-featured stats portal with analytics dashboards, session tracking, achievement badges, and a highlight clip repository. It's used daily by 30-50 active players and is production-ready, fully tested, and self-healing.

---

## 📡 The Pipeline — How Data Flows

```
    ET:Legacy Game Server                SSH Monitor            Local Bot
    ──────────────────────────────────────────────────────────────────────

    Round Ends (R1 or R2)
         │
         ├─→ [Lua] stats_discord_webhook.lua v1.6.2
         │   (fires HTTP webhook with timing, team data, surrender info)
         │   └─→ Discord webhook POST → bot receives timing data
         │       Stored in: lua_round_teams table
         │
         ├─→ [Lua] c0rnp0rn7.lua v3.0
         │   (writes YYYY-MM-DD-HHMMSS-mapname-round-N.txt)
         │   └─→ SSH: SSH_HOST=puran.hehe.si:48101 (60-second poll)
         │       Downloaded to: local_stats/
         │
         v
    [Python] community_stats_parser.py
    ├─ Parse .txt file (56 fields per player)
    ├─ Detect R1 vs R2 (filename: round-1.txt vs round-2.txt)
    ├─ Match R1+R2 (same timestamp within 45-min window)
    ├─ Calculate R2 differential (cumulative R1+R2 minus R1 = R2 only)
    └─ Team detection (advanced_team_detector.py, historical matching)

         v
    [PostgreSQL] 68 tables
    ├─ rounds, player_comprehensive_stats (56 columns), weapon stats
    ├─ lua_round_teams (webhook timing data)
    ├─ session grouping (60-minute gap rule)
    ├─ player_links (Discord user ↔ GUID mapping)
    └─ proximity, predictions, achievements, greatshot, availability

         v
    [Discord Bot] ultimate_bot.py
    ├─ 18 Cogs × 80+ commands
    ├─ On-demand queries + auto-posting (new round summaries)
    ├─ Session detection via voice channels (VoiceSessionService)
    ├─ Real-time caching (5-min TTL, database_adapter.py)
    └─ Interactive UI (pagination, embeds, buttons)

         v
    [Website] FastAPI backend + 2 frontends
    ├─ 8 routers, 22+ services, PostgreSQL queries
    ├─ Vanilla JS frontend (14 pages, 17 modules)
    ├─ React 19 frontend (10 TSX pages, in development)
    └─ HTTP endpoints: /api/*, /auth/*, /greatshot/*, etc.

    TIMING: Lua fires (~1s) → SSH download (~30-60s) → Parse + store (~5s) → Auto-post to Discord (~2s) = **40-70 seconds end-to-end**
```

---

## 🏢 The 7 Departments — Status at a Glance

| Department | Status | What It Does | Key Files | What To Touch It For |
|-----------|--------|--------------|-----------|---------------------|
| **Stats Pipeline** | ✅ Working | Lua hooks → SSH download → parse → PostgreSQL import | `bot/community_stats_parser.py`, `postgresql_database_manager.py`, `vps_scripts/stats_discord_webhook.lua` | Adding fields, parsing changes, backfill ops |
| **Bot + Commands** | ✅ Working | 18 Cogs delivering 80+ Discord commands across all analytics | `bot/cogs/`, `bot/services/`, 22 service files | New commands, session detection, real-time alerts |
| **Database** | ✅ Working | PostgreSQL 17 (prod) / 14 (dev), 68 tables, 56-column player stats | `tools/schema_postgresql.sql`, `bot/core/database_adapter.py` | Schema changes, new tables, migration rollout |
| **Website Backend** | ✅ Working | FastAPI server, 8 routers, 22+ services, query caching | `website/backend/routers/api.py` (9.4KB — largest), auth, availability, uploads | New API endpoints, performance tuning, route changes |
| **Website Frontend** | ⚠️ In Flux | Vanilla JS (14 pages, production) + React 19 (10 pages, development) | `website/js/` (17 modules), `gemini-website/src/pages/` (10 TSX) | UI/UX improvements, new pages, framework migration |
| **Proximity Analytics** | ⚠️ Waiting | 5 new v5 metrics (spawn timing, team cohesion, crossfire, pushes, Lua trades) | `proximity/`, `bot/services/round_correlation_service.py`, tables added Feb 26 | Lua tracker data, API endpoints, website panels |
| **Greatshot (Highlights)** | ⚠️ Buggy | Demo upload, clip extraction, video storage, sharing | `website/backend/routers/greatshot.py`, services/ | Upload bugs (Download/Share broken), UI redesign |
| **Availability Poll** | ⚠️ Needs UX | Daily player queue system with Discord/Telegram/Signal notifications | `bot/cogs/availability_poll_cog.py` (85KB), `website/backend/routers/availability.py` | Social redesign (avatars, progress bars, animations) |

**Legend**: ✅ = Ready (don't touch unless adding features) | ⚠️ = Known gaps (track but lower priority) | 🔴 = Broken (fix now)

---

## ⚠️ The ETLegacy Update Risk Zone — What Can Break

### Context
Your stats parser depends on two Lua scripts running on the ET:Legacy game server:
- **`c0rnp0rn7.lua` (v3.0)** — generates `.txt` stats files on disk (format: `YYYY-MM-DD-HHMMSS-mapname-round-1.txt`)
- **`stats_discord_webhook.lua` (v1.6.2)** — sends HTTP webhook with timing/team data at round end

These scripts live **on the game server, NOT in your repo**. If ETLegacy changes its Lua API or game event handling, the scripts silently fail and stats stop flowing. This happened to other communities in **November 2025** (LuaJIT upgrade broke bitwise operators — your scripts were patched in Feb 2026).

### Already Patched
✅ **LuaJIT bitwise operators** — Your Lua scripts already use `bit.bor()`, `bit.lshift()` instead of `|`, `<<` operators (fixed 2026-02-19). This is what broke other communities.

### Unassessed Risk
⚠️ **Feb 25, 2026 engine change** — ETLegacy changed `sess.rounds >= 2` condition in `g_session.c`. This affects how cumulative stats are preserved between rounds. **Impact unknown** — may cause R2 stats for players who joined mid-R1 to no longer be cumulative. Investigate if you see any round where "R2 total = R1 total" (impossible under normal differential logic).

### What Breaks If ETLegacy Updates

**CRITICAL BREAK** (Pipeline stops, no stats written):
| Scenario | Impact | How To Detect |
|----------|--------|--------------|
| Lua script filename format changes | Parser fails to detect R2 files, R1/R2 pairing fails | `db_sessions` shows only single-round "matches" |
| Header delimiter changes from `\` to something else | All files rejected as "invalid header format" | Log shows `parse error: invalid header format` on every file |
| TAB field order insertion (new field at positions 5-36) | All stats shifted by 1 position — subtle wrong numbers | No error; careful audit shows: `damage_given` = old `damage_received` value, etc. |
| `c0rnp0rn7.lua` filename format changes | First 40 characters of filename used for R1/R2 matching — fails completely | R1 and R2 files never pair |

**HIGH BREAK** (Data corrupted, wrong numbers):
| Scenario | Impact | How To Detect |
|----------|--------|--------------|
| ET:Legacy changes gamestate enum values (GS_PLAYING, GS_INTERMISSION) | Webhook Lua never detects round end, webhook never fires | `lua_round_teams` table stays empty for new rounds |
| ET:Legacy changes `g_currentRound` semantics (0=R1 instead of 0=R2) | R1 and R2 labels swapped everywhere | First new round after update: R1 stats appear as cumulative |
| ET:Legacy changes weapon ID assignments (new weapon at ID 5, shifts rest down) | All weapon stats misattributed: AR becomes SMG data, etc. | Weapon stats don't match what players remember |
| Lua script stops resetting a "R2-only" field (e.g., `xp` becomes cumulative) | Differential calculation double-counts that field in R2 | New players' R2 xp = huge cumulative number |

**MEDIUM BREAK** (Features degrade gracefully):
| Scenario | Impact | How To Detect |
|----------|--------|--------------|
| ET:Legacy renames `gentity` fields (`pers.connected` → `p.alive`) | Webhook can't read player state, sends empty team arrays | `lua_round_teams.Axis_JSON = "[]"` (empty) |
| ET:Legacy changes `cl_guid` key name in userinfo | Webhook reads empty GUID, player differential fails (reverts to cumulative) | Differential parser detects empty GUID, logs warning |
| ET:Legacy changes `timelimit` cvar behavior | Warmup overcounting bug reappears on R2 restarts | Lua_Playtime shows > actual round time |

### How To Check If An ETLegacy Update Is Safe

**Before updating game server:**
1. Check [ETLegacy GitHub releases](https://github.com/etlegacy/etlegacy/releases) for changes to:
   - `g_session.c`, `g_main.c`, `lua/`, `q_shared.h`
   - Any mention of: weapon IDs, cvars, Lua API, gamestate
2. If any of those files changed, read the full commit message
3. **DO NOT RUSH** — ask in Discord first

**After updating game server (first match):**
1. Run the audit: `python tools/slomix_audit.py pipeline-verify`
2. Watch for:
   - Any round with `score_confidence = "missing"` (header parse failed)
   - Any round where R2 `damage_given` = R1 total (TAB field shift)
   - Any round where `lua_round_teams` is empty but round exists (webhook didn't fire)
3. If something looks wrong, check the bot logs: `bot.log`, `database.log`

---

## 📋 Known Issues — Prioritized

### P1 — Fix When You Next Touch That Area

- **Upload Library: Download button streams video instead of downloading** — File is downloaded to browser memory instead of disk. **Root cause**: `Content-Disposition: inline` in `website/backend/routers/uploads.py:376`. **Fix**: Change to `attachment`. **Effort**: 1 minute.

- **`slomix.fyi` apex domain redirects to wrong place** — No A record, only `www.slomix.fyi` resolves. Users typing `slomix.fyi` get DNS error. **Fix**: Add apex A record to Cloudflare. **Effort**: 2 minutes.

- **`http://www.slomix.fyi` bypasses Cloudflare** — HTTP (not HTTPS) connections go straight to origin. **Why**: Page rule issue. **Fix**: Force HTTPS redirect. **Effort**: 3 minutes.

### P2 — Next Sprint

- **Availability Poll: UI is empty/spreadsheet-like** — Players don't see social cues. Needs: player avatars, animated progress bars, "almost there" notifications, Discord badge display. **Effort**: 4-6 hours (Vanilla JS or React redesign).

- **Prometheus metrics not installed** — Scaffolding exists in `website/backend/metrics.py` and `bot/services/automation/metrics_logger.py` but `prometheus_client` not in `requirements.txt`. Metrics silently no-op. **Fix**: `pip install prometheus_client`. **Effort**: 5 minutes + verify deployment.

- **matplotlib config issue on prod VM** — Systemd sandboxing makes `/opt/slomix/.config` read-only. Workaround: add `MPLCONFIGDIR=/tmp/matplotlib_cache` to `.env` on the VM. **Effort**: 2 minutes (next deploy).

- **Proximity: `proximity_reaction_metric` table empty** — Table exists but no data collected. Waiting for next session with v4.2 tracker on the game server. No action needed yet.

### P3 — Major Feature (Plan Separately)

- **Lua Time Stats Overhaul** — Replace c0rnp0rn's time tracking with new webhook-based per-player stats: spawn count, avg respawn time, longest life, denied playtime. 10-component implementation across Lua, DB schema, bot commands, website. **Effort**: 15-20 hours. **Status**: Designed, not started. **Docs**: `docs/KNOWN_ISSUES.md`.

- **React Frontend (gemini-website) → Production** — React 19 frontend (10 pages) exists and is functional. Currently both Vanilla JS (prod) and React (dev) run in parallel. Plan: Test React in staging, promote to production, retire Vanilla JS. **Effort**: Testing + deployment, 4-8 hours. **Blocker**: None technical, just QA time.

- **Time Dead Anomalies** — 13 player records have `time_dead > time_played` (off by 0.06-2.06 min) due to Lua rounding. Awaiting Lua Time Stats Overhaul to fix the source.

---

## 🎬 What "Done" Looks Like — Product Vision

**For a player:**
- Join voice channel → bot detects session start
- Round ends → 3 seconds later, bot auto-posts a rich embed summarizing the round (kills, deaths, score, team assignments, MVP)
- Command `!stats @player` → instant leaderboard position, K/D, playstyle radar, recent matches, achievement progress
- Command `!compare @playerA @playerB` → detailed duo matchup history
- Website: View all sessions (sortable by date, map, outcome), drill into each round, see player stats overlaid on timelines, achievement badges, seasonal trends

**For the admin:**
- Web dashboard showing: last round import time, total players tracked, database health, webhook status, cache hit rate
- Command `!correlation_status` → checks for data completeness issues (R1 without R2, etc.)
- Command `!pipeline_verify` → validates timestamps, team data, cumulative logic
- Alerts: If SSH download fails 3 times, if webhook hasn't fired in 2 hours, if parser rejects a file

**What's missing today:**
- Lua Time Stats (players see incomplete time data)
- Greatshot sharing (demo upload works, but share button broken)
- Availability Poll social UX (players don't feel engaged)
- Real-time stream stats (stats appear 40-70 seconds after round ends; faster would be better but acceptable)

---

## 🧭 How To Orient Yourself — For Future-You

### "I woke up and remember nothing" — Start here (5 minutes)

1. **Is the bot running?**
   ```bash
   screen -r slomix     # Production VM
   ps aux | grep ultimate_bot.py  # Dev/Samba
   ```
   If running, next step. If not, check `docs/INFRA_HANDOFF_2026-02-18.md` for restart instructions.

2. **Did a round import successfully?**
   ```bash
   # Check the last 10 imports
   tail -100 bot.log | grep "Round imported"

   # Check for errors
   tail -50 errors.log
   ```

3. **Are the Lua webhooks firing?**
   ```bash
   # Check the database
   psql -U etlegacy_user -d etlegacy -c "SELECT COUNT(*), MAX(lua_round_end) FROM lua_round_teams ORDER BY lua_round_end DESC LIMIT 1;"
   ```
   If `lua_round_end` is recent (< 20 min ago), webhooks are working. If not, the game server's `stats_discord_webhook.lua` may be broken.

4. **Check for known errors in logs:**
   ```bash
   grep -i "error\|critical\|exception" bot.log | tail -20
   grep -i "database\|connection" database.log | tail -20
   ```

5. **If all green, you're good.** If something's wrong, go to "Trace a Round" below.

### Trace A Round End-to-End (15 minutes)

This answers: "The bot said it imported a round, but I don't see the stats."

**Start**: Game round ends at timestamp `2026-03-02 15:32:45`

1. **Find the Lua webhook fire in logs:**
   ```bash
   grep "2026-03-02 15:3[2-3]" bot.log | grep webhook
   # Should show: webhook received, payload decoded, team data stored
   ```

2. **Find the SSH file download:**
   ```bash
   grep "2026-03-02 15:3[2-4]" bot.log | grep "Sync\|download\|fetched"
   # Should show: file downloaded, added to queue
   ```

3. **Check the parser output:**
   ```bash
   grep "2026-03-02 15:3[2-5]" bot.log | grep "Parse\|Round imported\|error"
   # Should show: file parsed, 10 players extracted, round stored
   ```

4. **Check database for the round:**
   ```bash
   psql -U etlegacy_user -d etlegacy -c "SELECT round_id, map_name, round_number, created_at FROM rounds WHERE created_at >= '2026-03-02 15:30:00' ORDER BY created_at DESC LIMIT 1;"
   ```

5. **Check if bot posted to Discord:**
   ```bash
   grep "2026-03-02 15:3[2-6]" bot.log | grep "posted\|embed\|discord"
   ```

If any step shows nothing, the next step probably failed. Check `bot.log` for exceptions at that timestamp.

### The 5 Most Important Files

1. **`bot/community_stats_parser.py`** — Parses `.txt` files, detects R1/R2, calculates differentials. **Touch this if**: Adding fields, parsing logic changes, backfilling stats.

2. **`bot/ultimate_bot.py`** — Main bot class, loads Cogs, runs SSH monitor task. **Touch this if**: Changing startup logic, task loop timing, schema validation.

3. **`bot/services/round_publisher_service.py`** — Auto-posts round summaries to Discord. **Touch this if**: Changing embed design, posting logic, timing.

4. **`website/backend/routers/api.py`** — All website stats endpoints. **Touch this if**: Adding new pages, changing API response format, performance tuning.

5. **`tools/schema_postgresql.sql`** — The 68-table database schema. **Touch this if**: Adding tables, new fields, migrations.

### Key Commands To Know

**Bot (Discord):**
```
!help                      # All command categories
!stats @player             # Player stats entry point
!session                   # Last session summary
!leaderboard               # Top 10 players
!correlation_status        # Data completeness check
!pipeline_verify           # Full audit of latest round
```

**Tools (CLI):**
```bash
python tools/slomix_audit.py pipeline-verify     # Check stats pipeline health
python tools/slomix_audit.py round-pairs         # Find broken R1/R2 matches
python tools/slomix_backfill.py endstats         # Backfill missing endstats
python postgresql_database_manager.py            # Interactive DB management
```

**Database (psql):**
```bash
# Check if today's stats are flowing
SELECT COUNT(*) FROM rounds WHERE DATE(created_at) = CURRENT_DATE;

# Find the most recent round
SELECT round_id, map_name, round_number, created_at FROM rounds ORDER BY created_at DESC LIMIT 1;

# Check webhook status
SELECT MAX(lua_round_end), COUNT(*) FROM lua_round_teams WHERE DATE(lua_round_end) = CURRENT_DATE;
```

---

## 📖 Development Conventions — Quick Reference

### Branches
- **NEVER commit to `main` directly** — always use feature branches
- Branch naming: `feature/...`, `fix/...`, `docs/...`
- Example: `git checkout -b fix/upload-download-button`

### Commits
Use [Conventional Commits](https://www.conventionalcommits.org/):
```
<type>(<scope>): <description>

<type>: feat, fix, docs, chore, refactor, test, security, perf
<scope>: bot, website, proximity, greatshot, ci, db, lua
```

Example: `fix(website): correct upload download header in uploads.py:376`

### Database Operations
- **ONLY use `postgresql_database_manager.py`** for schema changes and bulk operations
- **ONLY use `database_adapter.py`** for async queries in Cogs and services
- **NEVER hardcode SQL** — always use parameter placeholders (`?` in asyncpg convention)
- **Read `docs/POSTGRESQL_MIGRATION_INDEX.md`** before running migrations

### The 3 Rules You Will Forget

1. **Use `gaming_session_id`, never date strings** — Sessions span midnight. Use `WHERE gaming_session_id = ?`, not `WHERE DATE(created_at) = ?`.

2. **Group by `player_guid`, never `player_name`** — Players change names. Use `GROUP BY player_guid`, not `GROUP BY player_name`.

3. **Session gap is 60 minutes, not 30** — This is in `bot/core/season_manager.py` and `config.py`. Changing it breaks session grouping.

### Files You Should NOT Edit

- `bot/community_stats_parser.py` — Stable since Jan 2026; touching it risks breaking imports
- `bot/core/database_adapter.py` — Known logging gaps; document before refactoring
- `postgresql_database_manager.py` — 3,173 lines of import logic; change only with full test suite
- ETLegacy Lua scripts — Live on game server, not in repo; coordinate with server admin

---

## 📚 Related Documents

- **`docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md`** — 100-page technical deep-dive into every subsystem
- **`docs/COMMANDS.md`** — All 80+ bot commands with usage examples
- **`docs/CHANGELOG.md`** — Detailed change history since v1.0
- **`docs/KNOWN_ISSUES.md`** — The master list of all open issues and investigations
- **`docs/INFRA_HANDOFF_2026-02-18.md`** — Deployment, server setup, CI/CD pipeline
- **`docs/DATA_PIPELINE.md`** — Complete data flow from game server to Discord
- **`docs/POSTGRESQL_MIGRATION_INDEX.md`** — Database migration reference
- **`docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md`** — Lua script research and LuaJIT patching history

---

## 🎯 Next Steps (In Priority Order)

1. **Read section 4 (ETLegacy Risk)** — Understand what can break and how to detect it
2. **Bookmark the "Trace A Round" section** — You'll use it every time something looks wrong
3. **Run `tools/slomix_audit.py pipeline-verify`** right now — Make sure everything is healthy
4. **If issues found, check `docs/KNOWN_ISSUES.md`** — They may already be documented
5. **Review P1 issues** — Fix them while touching that code next
6. **Consider the dual frontend situation** — React 19 is ready for production; plan the migration

---

**Last updated**: 2026-03-02 | **Maintained by**: You | **Questions?** Check `docs/AI_COMPREHENSIVE_SYSTEM_GUIDE.md`
