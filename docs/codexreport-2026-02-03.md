# Codex Report - 2026-02-03

## Context
You want `stats_discord_webhook.lua` to also write a timing file per round into a new `/gametimes/` folder, similar to the stats files produced by `c0rnp0rn7.lua`, while still sending the Discord webhook. You also shared Discord output showing **NO LUA DATA**, indicating the webhook data is not being stored or matched.

Project maturity notes:
- The bot is a working prototype (active development ~3+ months) with a primary data flow that already works.
- Website and proximity are early prototypes and out of scope for full system testing.

## Work Completed in This Workspace
Changes have already been applied locally (not yet validated in production). These updates were logged for later revert and reference.

### Change Log Document
- `docs/SESSION_2026-02-03_CHANGELOG_LOCAL.md`

### Files Modified (Local)
- `bot/core/team_manager.py`
- `bot/services/session_data_service.py`
- `bot/services/stopwatch_scoring_service.py`
- `bot/ultimate_bot.py`
- `vps_scripts/stats_discord_webhook.lua`

### Summary of Local Code Changes
- **Team tracking**: Added `session_teams` safety checks, handled missing columns gracefully, ignored spectators/unknown teams, and seeded teams from earliest true R1 by timestamp.
- **Scoring**: `StopwatchScoringService` now uses independent round scoring (attackers success = +1, fullhold = defenders +1), with safer R1/R2 pairing by timestamp.
- **Round metadata**: Round inserts include `defender_team`, `winner_team`, `round_outcome` if columns exist; R2 inherits missing header data from the latest R1 of the same map/session.
- **Lua webhook**: Safer gamestate fallbacks, version bumped to 1.4.3.
- **Website prototypes**: Added a Proximity prototype view, SPA API contract, and a per-view prototype banner system. Added backend proximity endpoints that return safe placeholder data until the pipeline is connected.

## Observed Symptoms (from your Discord logs)
- Timing Debug shows:
  - Stats File present with 5:25 duration
  - Lua webhook section reports: **No Lua data available**
- Timing Comparison embed reports:
  - Status: **NO LUA DATA**
  - “Webhook may not have fired or data not stored”

## Plan: Add /gametimes/ Timing Files (no code changes yet)

### Goals
- Create a lightweight timing-only file per round
- Store alongside gamestats, but in `/gametimes/`
- Use the same filename pattern as stats files for easy pairing

### File Naming Convention
- `gametimes/YYYY-MM-DD-HHMMSS-mapname-round-N-timing.txt`
- Example:
  - `gametimes/2026-02-02-234827-etl_adlernest-round-2-timing.txt`

### File Contents (single line or JSON)
Minimum keys:
- `round_start_unix`
- `round_end_unix`
- `lua_playtime_seconds`
- `warmup_seconds`
- `pause_count`
- `total_pause_seconds`
- `winner_team`
- `defender_team`
- `end_reason`

Example (key=value line):
```
round_start_unix=1738554800 round_end_unix=1738555125 playtime=325 warmup=12 pauses=0 pause_seconds=0 winner=2 defender=1 end_reason=objective
```

Example (JSON line):
```
{"round_start_unix":1738554800,"round_end_unix":1738555125,"playtime":325,"warmup":12,"pause_count":0,"pause_seconds":0,"winner":2,"defender":1,"end_reason":"objective"}
```

### Write Location
- Create a new folder on the game server:
  - `/home/et/.etlegacy/legacy/gametimes/` (or wherever `gamestats/` lives)
- The Lua script writes relative to ET filesystem:
  - `gametimes/...` (just like `gamestats/...`)

### Implementation Outline (Lua)
- At round end (same place the webhook is sent):
  1. Build file name with `os.date('%Y-%m-%d-%H%M%S-') .. mapname .. '-round-' .. round`.
  2. Open file with `et.trap_FS_FOpenFile` in write mode.
  3. Write a single line with timing metadata.
  4. Close file.

Pseudo-flow:
```
local filename = string.format("gametimes\\%s%s-round-%d-timing.txt", os.date('%Y-%m-%d-%H%M%S-'), mapname, round)
local fd, len = et.trap_FS_FOpenFile(filename, et.FS_WRITE)
if fd then
  et.trap_FS_Write(line, string.len(line), fd)
  et.trap_FS_FCloseFile(fd)
end
```

### Notes / Risks
- Folder must exist, or `FS_FOpenFile` may fail. Create it once on the server.
- `os.execute("mkdir -p ...")` is not always safe/available; better to pre-create folder.

## Plan: Troubleshoot “NO LUA DATA” (no code changes yet)

### 1) Confirm the Lua script is actually firing
- Server console should show:
  - `[stats_discord_webhook] Round ended at ...`
  - `[stats_discord_webhook] Sent round notification ...`

### 2) Confirm Discord webhook messages are arriving
- In the webhook channel, look for raw **STATS_READY** posts.
- If none appear, likely `curl` failed or webhook URL wrong.

### 3) Confirm bot is receiving & storing Lua data
- Check bot logs for:
  - `STATS_READY` received
  - `Stored Lua round data` messages

### 4) Confirm DB contains lua_round_teams rows
- Query latest rows by `captured_at DESC`.

### 5) Check load order on server
- `lua_modules` should include:
  - `team-lock.lua` → `c0rnp0rn7.lua` → `endstats.lua` → `stats_discord_webhook.lua`

### 6) Verify gamestate constants
- `stats_discord_webhook.lua` must detect intermission properly. If no “Round ended” logs, this is likely the culprit.

## Next Step (if you want)
- I can draft the exact Lua patch (write-only plan) for `/gametimes/` logging and a short deployment checklist, without changing any code.

## Update: SPA Prototype Controls (2026-02-03)
These items were added after the initial report for a cleaner prototype experience:
- Backend proximity endpoints now exist as FastAPI stubs that return `status`, `ready`, and safe placeholders.
- Frontend now supports a prototype banner per view using `data-prototype` and `data-prototype-slot`.
- Proximity UI now respects `ready` status and displays a prototype state message when the API is not ready.

## Session Scoring Reality Check (2026-02-02)
Using local `local_stats/2026-02-02-*` files (no database access), a time‑based map winner calculation matches Superboyy’s result:

- **Map winners (time comparison)**: TeamB 7 maps, TeamA 4 maps
- **Why bot shows 11:11**: current independent round scoring gives 1 point per successful attack per round → 11 maps × 2 rounds = 22 points → 11–11 tie when both attackers succeed in every map.

**TeamA/TeamB definition**
- TeamA = the roster on side 1 in the earliest R1 for the session (`2026-02-02-211352-etl_adlernest-round-1.txt`).
- TeamB = the roster on side 2 in that same file.
- Superboyy’s red/blue mapping can be matched once we know which side his colors correspond to.

**Color mapping from Superboyy’s sheet (2026-02-02)**
- **Blue team**: `vid`, `SuperBoyy`, `vektor`
- **Red team**: `bronze`, `endekk`, `oly`
- Earliest R1 side mapping shows **TeamA = Blue** and **TeamB = Red** for this session.

**Map-by-map winners (time comparison)**
- `etl_adlernest`: TeamB
- `supply`: TeamA
- `etl_sp_delivery`: TeamB
- `te_escape2` (first play): TeamB
- `te_escape2` (second play): TeamB
- `sw_goldrush_te`: TeamA
- `et_brewdog`: TeamA
- `etl_frostbite`: TeamB
- `erdenberg_t2`: TeamA
- `braundorf_b4`: TeamB
- `etl_adlernest` (second play): TeamB

**Applied change**
- Updated stopwatch scoring to **map‑winner by time** (Superboyy‑style).
- Tie‑break: equal completion times go to Round 1 attackers.
- Added a fallback that infers R1 defender side from `winner_team` + time when header values look stale.
- Scoring now prefers **R2 header `winner_team` (side winner)** for map winner; time comparison is fallback.
- Added scoring debug output per map (winner side, team sides, source).
- Added `!last_session debug` to surface scoring source and side mapping.
- Round 2 parser now retains `winner_team` from header to support header-based scoring.
- Fixed indentation error in `bot/core/achievement_system.py` that prevented bot startup.

**Header sanity check (2026‑02‑02 raw stats)**
- The header fields are parsed exactly as written by `c0rnp0rn7.lua`.
- Raw header shows `defenderteam = 1` in both R1 and R2, even though player sides swap.
- This indicates the **raw header itself** is static for defender team (not a parser error).

**Postgres backfill (2026‑02‑03)**
- Applied `migrations/006_add_full_selfkills.sql` to add `full_selfkills` to `player_comprehensive_stats`.
- Ran `scripts/backfill_full_selfkills.py` (Postgres) to populate existing rounds.
- Re-ran backfill for last 12 weeks only (cutoff 2025‑11‑11) using `/tmp/backfill_12w` to reduce noise.

**Missing Round 1 audit (last 12 weeks)**
- Found 225 Round 2 files missing matching Round 1 in `local_stats`.
- Checked server gamestats at `/home/et/.etlegacy/legacy/gamestats`; none of the missing Round 1 files exist there either.

**Missing rounds audit (last 3 weeks)**
- Missing R2 (R1 present): 48 maps.
- Missing R1 (R2 present): 47 maps.
- Server gamestats check: none of those missing files exist on server.
 - Addendum: those counts were based on strict timestamp pairing (same match_id).
 - Using actual pairing logic (same map, R1 before R2 within 45 minutes):
   - R2 without matching R1: 1 file (`2026-01-15-232241-sw_goldrush_te-round-2.txt`)
   - R1 without matching R2: 2 files (`2026-01-13-000542-te_escape2-round-1.txt`, `2026-01-15-232658-et_brewdog-round-1.txt`)

**Pairing audit helper**
- Added `scripts/audit_round_pairs.py` to audit missing rounds using parser pairing logic (avoids false missing due to timestamp mismatch).

**Round linking fix**
- Added `bot/core/round_linker.py` to resolve `round_id` using map + round + time window.
- Added `migrations/007_add_round_id_to_lua_round_teams.sql` and store `round_id` for Lua rows.
- Lua metadata override now uses round_linker instead of match_id.
- Timing debug/comparison now prefers direct `round_id` match when available.
- Added `scripts/backfill_lua_round_ids.py` to link existing Lua rows.
 - Applied migration + ran backfill on Postgres (scanned 1, updated 0).

**Endstats pagination (2026‑02‑03)**
- Replaced the single “Session Awards” embed with paginated endstats output.
- Map View (default): one page per map, showing Round 1 + Round 2 awards.
- Round View (toggle): one page per round with expanded awards.
- Added `bot/core/endstats_pagination_view.py` with first/prev/next/last + map/round toggle buttons.

**Endstats backfill helper (2026‑02‑03)**
- Added `scripts/backfill_endstats.py` to import local endstats files into Postgres without posting to Discord.
- Uses `processed_endstats_files` for dedupe and skips rounds that already have awards.

**Endstats monitor fix (2026‑02‑03)**
- Endstats SSH monitor now uses `processed_endstats_files` for dedupe instead of FileTracker, so existing local files still get processed.
- Applies the same startup lookback window to avoid very old endstats on restart.

**Endstats audit + backfill (2026‑02‑03)**
- Added `!endstats_audit` command for quick coverage checks of the latest session.
- Ran endstats backfill for 2026‑02‑02: files_processed=17, awards_inserted=450, vs_inserted=306, skipped_processed=1, skipped_existing=1.

**Live outputs (2026‑02‑03)**
- Live achievements now post after each successful round import.
- Endstats pagination output no longer includes VS stats (awards-only display).

**Live round posting fix (2026‑02‑03)**
- Postgres import now resolves `round_id` after parsing so live round posts are not skipped.

**Session graphs (2026‑02‑03)**
- Implemented `!session <date> graphs` using the same graph generator as `!last_session`.
