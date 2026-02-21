# Known Issues

---

## Planned: Lua Time Stats Overhaul (Feb 20, 2026) - Major Feature

**Summary**: Add comprehensive per-player time tracking to `stats_discord_webhook.lua`, replacing reliance on the c0rnp0rn Lua's buggy time stats. This is a multi-component upgrade covering **all time-related metrics**.

**Background**:
- `c0rnp0rn-testluawithtimetracking.lua` tracks `death_time_total` and `topshots[i][16]` (denied playtime) but has a **surrender timing bug** — surrender rounds report full map timelimit instead of actual duration.
- `stats_discord_webhook.lua` already has accurate round timing (real-time hooks, pause-aware, surrender-correct) but currently only outputs round-level metadata, not per-player time stats.
- The webhook's timing data is currently **debug-only** — not consumed by the bot or website.
- Goal: move **all** time tracking into the webhook Lua so we have a single, accurate, pause-aware source of truth.

**New Per-Player Time Stats to Track**:

| Stat | Field | Description |
|------|-------|-------------|
| Time Played | `time_played_ms` | Total time the player was in the round (from first spawn to round end, minus disconnects) |
| Time Alive | `time_alive_ms` | Time spent alive and active (time_played - time_dead) |
| Time Dead | `time_dead_ms` | Total time spent dead waiting to respawn (pause-aware) |
| Denied Playtime | `denied_play_time_ms` | Total enemy play time denied by this player's kills (pause-aware) |
| Time in Pause (while dead) | `pause_while_dead_ms` | Pause time that overlapped with being dead (subtracted from dead time) |
| Spawn Count | `spawn_count` | Number of times the player spawned this round |
| Death Count (timed) | `death_count` | Number of deaths with timing data (for avg respawn time calculation) |
| Avg Respawn Time | `avg_respawn_ms` | Average time between death and next spawn |
| Longest Life | `longest_life_ms` | Longest single alive streak |
| Longest Death | `longest_death_ms` | Longest single dead streak (longest wait for respawn) |

**New Round-Level Time Stats**:

| Stat | Field | Description |
|------|-------|-------------|
| Round Duration | `round_duration_ms` | Actual round playtime (surrender-correct, pause-subtracted) |
| Round Start | `round_start_unix` | Unix timestamp of round start (already tracked) |
| Round End | `round_end_unix` | Unix timestamp of round end (already tracked) |
| Total Pause Time | `total_pause_ms` | Total pause duration during round (already tracked) |
| Pause Count | `pause_count` | Number of pauses (already tracked) |
| Pause Events | `pause_events[]` | Array of {start, end, duration} per pause (already tracked) |
| Warmup Duration | `warmup_ms` | Warmup phase duration (already tracked) |
| End Reason | `end_reason` | `objective` / `surrender` / `time_expired` (already tracked) |

**Lua Implementation Details**:
- **On spawn** (`et_ClientSpawn`): Record spawn timestamp. If player was dead, finalize dead time (minus pause overlap) and credit killer with denied playtime. Track spawn count and alive streak start.
- **On death** (`et_Obituary` / kill hook): Record death timestamp and killer ID. Finalize alive streak (for longest life). Increment death count.
- **On pause start/end**: For each currently-dead player, track pause overlap so it can be subtracted from their dead time.
- **On disconnect/team change**: Finalize any in-progress alive or dead time.
- **On round end**: Finalize all in-progress timers. Calculate averages. Write file + send webhook.
- **All times use `os.time()` (Unix seconds) for real-world accuracy**, not game tick timers.

**Output: `-timestats.txt` File Format** (written to `gamestats/`):
```
# timestats v1.0
# map: supply
# round: 1
# round_start_unix: 1740000000
# round_end_unix: 1740001200
# round_duration_ms: 1185000
# total_pause_ms: 15000
# pause_count: 1
# warmup_ms: 5000
# end_reason: objective
# GUID	Name	Team	TimePlayedMS	TimeAliveMS	TimeDeadMS	DeniedPlaytimeMS	PauseWhileDeadMS	SpawnCount	DeathCount	AvgRespawnMS	LongestLifeMS	LongestDeathMS
ABC123DEF456	Player1	1	1185000	953000	232000	45000	0	8	7	33142	180000	42000
789GHI012JKL	Player2	2	1185000	870000	315000	12000	15000	11	10	31500	120000	55000
```

**Implementation Plan**:

| Step | Component | Description |
|------|-----------|-------------|
| 1 | **Lua** (`stats_discord_webhook.lua`) | Add all per-player time tracking (spawn/death/alive/dead/denied/pause-overlap/streaks) |
| 2 | **Lua** (file output) | Write `-timestats.txt` files to `gamestats/` as local backup |
| 3 | **Lua** (webhook) | Include full per-player time data in existing webhook JSON payload |
| 4 | **Database** | Add new columns to `player_comprehensive_stats`: `time_played_ms`, `time_alive_ms`, `time_dead_ms`, `denied_playtime_ms`, `spawn_count`, `avg_respawn_ms`, `longest_life_ms`, `longest_death_ms` |
| 5 | **Bot parser** | Add `TimeStatsParser` to read `-timestats.txt` files |
| 6 | **Bot webhook handler** | Extract time data from webhook payload (instant path) |
| 7 | **Bot SSH monitor** | Pick up `-timestats.txt` files as fallback |
| 8 | **Bot commands/graphs** | Update `SessionGraphGenerator` and relevant Cogs to display new time stats |
| 9 | **Website backend** | Update FastAPI endpoints to expose new time stats in JSON |
| 10 | **Website frontend** | Update Chart.js visualizations to include new time stats |

**Why This Is "Better" Than c0rnp0rn's Approach**:
- Real Unix timestamps instead of game tick timers
- Correct surrender handling (actual playtime, not timelimit)
- Per-pause event tracking subtracted from dead time per player
- Tracks alive streaks, respawn averages, longest life/death — stats c0rnp0rn doesn't have
- Dual delivery: local file backup + instant webhook
- SSH fallback if webhook fails
- Single source of truth for all time data

**Existing Pipeline Files That Need Modification**:

| File | What Changes | Why |
|------|-------------|-----|
| **VPS: Lua Scripts** | | |
| `vps_scripts/stats_discord_webhook.lua` | Add spawn/death/alive/dead/denied tracking per player, write `-timestats.txt`, include time data in webhook JSON | Core new functionality — this becomes the single source of truth for all time stats |
| `c0rnp0rn3.lua` (game server) | No changes needed | Keeps generating stats files as before; time fields from it will be superseded by webhook data |
| **Database** | | |
| `tools/schema_postgresql.sql` | Add new columns: `time_played_ms`, `time_alive_ms`, `time_dead_ms`, `denied_playtime_ms`, `spawn_count`, `avg_respawn_ms`, `longest_life_ms`, `longest_death_ms` to `player_comprehensive_stats` | Store the new time stats |
| `postgresql_database_manager.py` | Update INSERT/import queries to include new columns; update schema validation (53→61 columns) | Import pipeline must handle new fields |
| **Bot: Parser & Import** | | |
| `bot/community_stats_parser.py` | Add `TimeStatsParser` class or method to parse `-timestats.txt` files | New file format needs a dedicated parser |
| `bot/ultimate_bot.py` | Update `endstats_monitor` task loop to also look for `-timestats.txt` files; merge time data with main stats import | Orchestration — must pick up new files alongside existing stats files |
| `bot/automation/file_tracker.py` | Add `-timestats.txt` to tracked file patterns; update duplicate detection | SSH monitor must recognize and pull the new file type |
| `bot/automation/ssh_handler.py` | Update file download patterns to include `-timestats.txt` | SSH fallback path for new files |
| `bot/core/database_adapter.py` | Update any hardcoded column lists if present; ensure new columns work with async queries | Abstraction layer must support new fields |
| **Bot: Commands & Display** | | |
| `bot/services/session_graph_generator.py` | Update queries and graph generation to use new time fields (time_alive, longest_life, avg_respawn, etc.) | Graphs should show the new accurate time stats |
| `bot/cogs/stats_cog.py` | Update `!stats`, `!compare` to include new time metrics | Player stats commands should expose new data |
| `bot/cogs/last_session_cog.py` | Update session summary to show new time breakdown | Session view should use accurate time data |
| `bot/cogs/session_cog.py` | Update session queries to include new time columns | Session detail commands |
| `bot/cogs/leaderboard_cog.py` | Add leaderboards for new metrics (longest life, most denied playtime, etc.) | New leaderboard categories |
| `bot/core/frag_potential.py` | Update `FragPotentialCalculator` to use accurate time_alive from webhook instead of calculated value | More accurate FragPotential with real alive time |
| **Website: Backend** | | |
| `website/backend/routers/api.py` | Update round/session/player endpoints to return new time fields | API must expose new data to frontend |
| `website/backend/services/` | Update any stats aggregation services to include new columns | Backend logic |
| **Website: Frontend** | | |
| `website/js/retro-viz.js` | Add new Chart.js panels for time breakdown (alive/dead/denied) | Round visualizer should show new time charts |
| `website/js/sessions.js` | Update session views to display new time stats | Session pages |
| `website/js/player-profile.js` | Add time stats to player profile view | Player profile page |
| `website/js/compare.js` | Add new time metrics to player comparison | Comparison charts |

**Backward Compatibility Notes**:
- Old stats files (without `-timestats.txt`) will continue to work — bot falls back to existing c0rnp0rn time fields
- New columns should default to `NULL` so existing records aren't affected
- Webhook handler should gracefully handle missing time data (bot was offline, webhook failed)
- `-timestats.txt` and webhook provide the same data — bot should prefer webhook (instant) and use file as fallback

**Status**: Not started — planning phase

---

## Website UI Bugs (Feb 20, 2026) - Medium Priority

### Availability Page - UI/UX Overhaul Needed

**Issue**: The Daily Availability page concept is solid but the UI feels empty and uninviting. Even with 2 players queued, the page looks deserted. Specific problems:

1. **Day cards are too small and sparse** — The "Upcoming days" cards (Sun, Mon, Tue) show tiny text with `Looking: 0, Available: 0, Maybe: 0, Not playing: 0` in a cramped box. There's no visual weight or energy — just lonely zeros.
2. **No sense of momentum** — When 2 people are "Maybe" for today, it should feel like something is building. Instead, the "2 responses" label is buried, and the `Maybe: 2` box doesn't stand out enough. There's no excitement or call to action.
3. **Calendar section is barren** — The "Open calendar" button leads to a secondary view, but the inline calendar preview shows nothing. It's dead space.
4. **"Current queue" feels disconnected** — Shows "Queue is empty" and "Planning locked" with no context why. The threshold display (`Waiting for Looking threshold: 0/5`) is functional but not motivating.
5. **Status buttons lack feedback** — After clicking "Maybe", the button highlights but there's no animated confirmation, no "You're in!" moment.
6. **Notification Settings cramped at bottom** — Settings for Discord/Telegram/Signal notifications feel like an afterthought tacked onto the page.

**The core problem**: The page is designed for data display (how many, which status) but not for social engagement (who's looking, are we close to a game, should I jump in?). It needs to feel like a lobby, not a spreadsheet.

**Ideas for improvement**:
- Larger, more prominent player count displays with visual indicators (progress bars toward threshold, color-coded urgency)
- Show player names/avatars for each status (not just counts) — "carniel and Zlatorog are Maybe" is more compelling than "Maybe: 2"
- Animated transitions when someone changes status
- "Almost there!" notifications when queue is 1 player short
- Consolidate day view — today/tomorrow should be the hero, upcoming days secondary
- Make the queue threshold visual (e.g., 2/5 progress ring instead of text)

**Status**: Open — design rethink needed

### Greatshot - Broken

**Issue**: Greatshot feature is not working. Cannot upload demos or use the greatshot pipeline.
**Expected**: Should be able to upload `.dm_84` demo files, process them, and generate greatshot clips.
**Status**: Open

### Demo Upload - Broken

**Issue**: Cannot upload demo files (`.dm_84`) through the website.
**Expected**: Demo upload form should accept files and store them for processing.
**Status**: Open

### Clickable Cards / Expandable Boxes - Broken Across Multiple Views

**Issue**: Many interactive cards, boxes, and expandable sections across the website that should show more info, expand details, or navigate to a new page are not responding to clicks. This affects multiple views — not just Sessions.
**Expected**: Clicking cards/boxes should expand them, show detailed info, or navigate to the relevant detail page.
**Status**: Open — likely a shared JS event handler or routing issue

### Sessions View - Unclickable Sessions

**Issue**: Session cards/rows in the Sessions view are not clickable. Cannot navigate to session detail.
**Expected**: Clicking a session should open the session detail view.
**Investigation**: Code looks correct — cards render with `onclick="toggleSession('...')"` and `window.toggleSession` is exposed. May need browser DevTools debugging. One edge case: two sessions sharing the same date (e.g., sessions 87 & 85 both on 2026-02-06) create duplicate DOM IDs, which could cause weird behavior.
**Status**: Open

### Upload Library - "Watch" Button Broken

**Issue**: Clicking the "Watch" button on an uploaded clip does nothing.
**Expected**: Should open an inline video player or navigate to a watch page.
**Investigation**: Code looks correct — calls `window.openVideoPlayer()` which creates a modal with a `<video>` element. Should work. Needs browser DevTools debugging.
**Status**: Open

### Upload Library - "Download" Streams Instead of Downloading

**Issue**: Clicking the "Download" button on a clip opens it fullscreen as a streaming video instead of triggering a file download.
**Expected**: Should prompt a browser file download (`Content-Disposition: attachment`).
**Root Cause**: Backend's download endpoint serves MP4s with `Content-Disposition: inline` (line 376 in `uploads.py`), which tells the browser to play it rather than download. Non-video files correctly use `Content-Disposition: attachment`.
**Fix**: Add a `?force_download=true` query param or add the `download` attribute to the `<a>` tag.
**Status**: Open — root cause identified

### Upload Library - "Share" Opens Video Player

**Issue**: Clicking "Share" on a clip shows a popup with an embedded video player.
**Expected**: Should copy share URL to clipboard or show share options.
**Investigation**: Not a bug by design — the "Share" button navigates to `#/uploads/{id}`, which is the upload detail page. For videos, the detail page includes an embedded video player + metadata + copy-link button. Consider UX change: "Share" could directly copy the link instead.
**Status**: Open — design decision needed

---

## Proximity - Spawn Reaction Time Inflated (Feb 20, 2026) - Fixed

**Issue**: Spawn reaction times showed 2-6 seconds for players who actually react in 50-300ms.
**Root Cause**: Lua tracker recorded `first_move_time` during warmup. Pre-round spawns had negative `spawn_time_ms`, so `first_move - spawn_time` spanned the zero boundary and inflated values by 4-6 seconds.
**Fix**:
- Lua: `et_ClientSpawn` gated on `gamestate == 0` (PLAYING only)
- Lua: `first_move_time` detection requires `gamestate == 0` and `spawn_time >= 0`
- API: Added `spawn_time_ms >= 0` filter to exclude pre-existing bad data

**Status**: Fixed (pending deploy of Lua to game server + code sync to VM)

---

## Time Dead Anomalies (Dec 16, 2025) - Low Priority

**Issue**: 13 player records show `time_dead_minutes > time_played_minutes` by small margins (0.06 to 2.06 minutes).

**Investigation**:
- Parser correctly uses round duration for stopwatch mode (design intent)
- DPM calculations are correct (confirmed by user)
- Database rebuild reduced corruption from 43 records (100+ min errors) to 13 records (0.06-2.06 min errors)
- Field mappings verified correct: `tab_fields[22]` = time_played, `[25]` = time_dead_ratio, `[26]` = time_dead_minutes

**Possible Causes**:
1. Rounding differences between Lua (`roundNum(value, 1)`) and Python (`int(minutes * 60)`)
2. Edge cases: players joining mid-round or disconnecting
3. Potential Lua bug in `death_time_total` accumulation
4. Acceptable tolerance given system complexity

**Status**: Unsolved — low priority. System works well enough for production use.
**Reference**: Investigation documented in `/home/samba/.claude/plans/sorted-wandering-horizon.md`
**Note**: The planned Lua Time Stats Overhaul (above) may resolve this by providing more accurate dead time data directly from the webhook.

---

## VM Migration — Remaining Items (Feb 20, 2026) - Medium Priority

Full migration report: [docs/VM_MIGRATION_REPORT_2026-02-20.md](VM_MIGRATION_REPORT_2026-02-20.md)

9 issues were hit and resolved during migration. These items from the report's "Remaining Items" section are still open:

| Item | Priority | Notes |
|------|----------|-------|
| **Samba bot duplication** | Medium | Both Samba and VM bots respond to Discord commands (double replies on `!ping`). Stop Samba bot or use different token. |
| **GitHub branch sync** | Medium | `feat/availability-multichannel-notifications` branch is way ahead of `main`. Needs merge/rebase. |
| **Prometheus monitoring** | Medium | Code scaffolding exists but `prometheus_client` not installed — uses noop counters. |
| **HTTP → HTTPS redirect** | Low | `http://www.slomix.fyi` still hits Samba directly (bypasses Cloudflare). Shut down Samba web or configure redirect. |
| **`slomix.fyi` apex domain** | Low | No A record — only `www.slomix.fyi` resolves. Could add CNAME flattening in Cloudflare. |
| **matplotlib config** | Low | `/opt/slomix/.config` is read-only due to systemd sandboxing. Add `MPLCONFIGDIR=/tmp/matplotlib_cache` to `.env`. |

---

## Website Debugging Audit Results (Feb 20, 2026)

### API Health: ALL GREEN

| Endpoint | Status |
|----------|--------|
| `/api/status` | Online, DB ok |
| `/health` | Ok |
| `/api/stats/overview` | 1034 rounds, 10 players, 90 sessions |
| `/api/sessions` | Returns session list correctly |
| `/api/uploads` | Returns 3 uploads (covie.mp4, etconfig.cfg, decayflag.mp4) |
| `/api/proximity/scopes` | 7 sessions with scope data |
| `/api/proximity/summary` | 9129 engagements, 51 rounds |
| `/api/hall-of-fame` | Full categories data |
| `/auth/me` | 401 (expected, not logged in) |
| `/auth/link/status` | Correct unauthenticated response |

### API Issue

**`/api/proximity/reactions`** returns `{"status":"prototype","ready":false}` — reports "Proximity pipeline not connected" even though other proximity endpoints work fine. Likely a feature flag or missing table.