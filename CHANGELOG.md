# Changelog

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [1.1.0] - 2026-03-20

### Stats Accuracy Audit
- **fix(api):** R0 match summary rows double-counting kills/damage across 7+ endpoints — 94% inflation fixed
- **fix(api):** KD leaderboard: `NULLIF(deaths, 1)` → `CASE WHEN deaths > 0` — undefeated players no longer disappear
- **fix(api):** Accuracy now weighted by shots fired instead of naive per-round average
- **fix(api):** Headshots leaderboard uses `headshot_kills` (actual kills) instead of `headshots` (hit events)
- **fix(api):** `survival_rate` now uses engine TAB[8] alive% (excludes dead + limbo time)
- **fix(api):** `played_pct` capped at 100% (engine vs Lua timer ±1-3 sec per round)
- **fix(api):** weapon_stats CTE on `/stats/maps` now excludes R0 rows
- **fix(bot):** Headshot % formula in `!stats` — was `headshot_kills / weapon_hits`, now `headshot_kills / kills`
- **fix(bot):** `await` on sync methods in `advanced_team_detector.py` — runtime TypeError crash
- **fix(bot):** Achievement help text thresholds now match actual `achievement_system.py` values
- **fix(bot):** `avg_dpm` f-string format crash in Career Overview embed

### alive% / TMP (Time Played Percent)
- **feat(parser):** R2 differential for `time_played_percent` — converts cumulative percentage to R2-only via absolute alive time
- **feat(bot):** `time_played_percent` (TAB[8]) now stored in DB INSERT (57 columns)
- **feat(api):** Dual-mode alive% — engine value as primary, computed as fallback, with drift detection
- **feat(backfill):** Backfilled 8,799 rows from VPS raw stats files (99.9% coverage)

### FragPotential Hidden
- **refactor(api):** FragPotential removed from user-facing displays (kept internally for aggression model)
- **refactor(bot):** Session graph FP chart replaced with K/D Ratio; playstyle panel uses DPM
- **refactor(website):** SessionDetail shows Damage Efficiency instead of FragPotential

### React 19 Frontend Modernization
- **feat(website):** React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS v4 + Framer Motion
- **feat(website):** 19 route pages migrated from legacy JS to React (strangler pattern, 71% code reduction)
- **feat(website):** Game assets extracted from ET:Legacy pk3 files — 121 PNGs (weapons, classes, medals, ranks, levelshots)
- **feat(website):** New components: InfoTip, PlayerLookup, ProximityIntro
- **feat(website):** New pages: ProximityPlayer, ProximityReplay, ProximityTeams
- **feat(website):** Bridge layer: `modern-route-host.js` + `route-registry.js` for vanilla↔React coexistence

### Proximity v5.0 Teamplay Analytics
- **feat(proximity):** Lua tracker v5.0 with 5 new teamplay systems:
  - Spawn Timing (`proximity_spawn_timing` table, `!pse` command)
  - Team Cohesion (`proximity_team_cohesion` table, `!pco` command, Canvas timeline)
  - Crossfire Opportunities (`proximity_crossfire_opportunity` table, `!pxa` command)
  - Team Pushes (`proximity_team_push` table, `!ppu` command)
  - Trade Kills (`proximity_lua_trade_kill` table, `!ptl` command)
- **feat(bot):** New `proximity_session_score_service.py` — composite session scoring
- **fix(proximity):** 8 Lua bug fixes: team-damage filter, crossfire dedup, LOS mask, cache, teamkill filter, round_start_unix fallback, engagement timeout, cohesion guard
- **fix(proximity):** Focus-fire score credits attackers (coordinators) not victims
- **fix(proximity):** Roster seed includes both targets AND attackers

### Parser & Pipeline
- **fix(parser):** `time_played_percent` R2 differential — percentage→absolute time→subtract→reconvert
- **fix(parser):** R0 match summary correctly uses R2 cumulative TAB[8] as match-level alive%
- **fix(parser):** R2_ONLY_FIELDS audit — timing reconciliation for repeated maps

### Legacy JS Fixes
- **fix(website):** Session detail date path now resolves session ID before loading detail
- **fix(website):** Proximity scoped requests fall back to map_name/round_number when round_start_unix missing
- **fix(website):** `played_pct_lua` field added for frontend compatibility

### Tests
- **fix(tests):** Resolved all 53 pre-existing test failures across 22 files
- **test:** 313 tests passing, 45 skipped, 0 failures

### Cleanup
- **chore:** Removed 33 stale docs from `docs/instructions/` and `docs/reports/`
- **chore:** Removed obsolete `freshinstall.sh` and `update_bot.sh`
- **ci:** Excluded `website/assets/` from large file check (game levelshots are legitimate >500KB)

---

## [1.0.8] - 2026-02-27

### Round Correlation System
- **feat(bot):** Round correlation service (live mode) — tracks data completeness for each match (R1+R2)
  - New table: `round_correlations` (23 columns, 8 completeness boolean flags)
  - Admin command: `!correlation_status`
  - Config: `CORRELATION_ENABLED`, `CORRELATION_DRY_RUN`, `CORRELATION_WRITE_ERROR_THRESHOLD`
  - Schema preflight check and circuit breaker on write errors
- **fix(db):** Critical match_id generation fix — `filename.replace('.txt', '')` produced unique IDs per round (485 orphan R1s). Changed to extract shared `{date}-{time}` prefix.

### Round Linkage Anomaly Detection
- **feat(bot):** `round_linkage_anomaly_service.py` — detects linkage drift across lua_round_teams, rounds, round_correlations
- **feat(api):** `GET /diagnostics/round-linkage` — thresholded anomaly report
- **fix(bot):** Lua round linkage race condition — added second pass detecting stale linkages when closer match imported later

### Proximity Objective Coordinates
- **feat(proximity):** Template-driven objective coords for 8 high-impact maps
- **feat(ci):** WS11 Objective Coordinate Gate — prevents regressions on map coverage
- **feat(ci):** WS12 Single Trigger Path Enforcement — canonical webhook trigger flow

### Website Fixes
- **fix(api):** Round JOIN fragility — replaced composite key fallback with direct `round_id` JOIN
- **fix(api):** Hardened 3 silent error handlers with logging
- **fix(website):** Chart.js crash prevention with `hasChartJs()` guards and visible fallback text

### Scripts/Tools Consolidation
- **refactor:** 5 unified CLI tools replacing scattered scripts (68% file reduction)
  - `slomix_backfill.py`, `slomix_audit.py`, `slomix_rcon.py`, `slomix_proximity.py`, `slomix_retro.py`
- **fix:** 3 bugs found and fixed during consolidation

---

## [1.0.7] - 2026-02-22

### Greatshot Highlight Enrichment
- **feat(greatshot):** Enriched highlight metadata — kill sequences, weapon breakdowns, timing rhythm
- **feat(greatshot):** Player match stats attached to each highlight
- **feat(greatshot):** Database cross-reference — auto-match demos to rounds (confidence scoring)
- **feat(greatshot):** Scout-friendly UI — kill sequences, weapon badges, DB crossref panel
- **feat(greatshot):** New service: `greatshot_crossref.py`

---

## [1.0.6] - 2026-02-07

### Greatshot Demo Pipeline
- **feat(greatshot):** Upload `.dm_84` demos, auto-analyze with highlight detection
- **feat(greatshot):** Multi-kill, killing spree, quick headshot chain detectors
- **feat(greatshot):** Clip extraction via UDT_cutter at exact timestamps
- **feat(greatshot):** 4 new tables: `greatshot_demos`, `greatshot_analysis`, `greatshot_highlights`, `greatshot_renders`
- **feat(greatshot):** UDT parser built from source with ET:Legacy protocol 84 support

### Player Analytics
- **feat(bot):** `!consistency`, `!map_stats`, `!playstyle`, `!awards`, `!fatigue` commands
- **feat(bot):** `!matchup A vs B`, `!duo_perf`, `!nemesis` — lineup analytics with confidence scoring
- **feat(bot):** Map-based stopwatch scoring — session scores count MAP wins (not rounds)
- **feat(bot):** Real-time team tracking — teams grow dynamically (3v3 → 4v4 → 6v6)

### Website SPA Overhaul
- **feat(website):** Sessions, matches, profiles, leaderboards, admin, proximity, season stats pages
- **feat(bot):** Server control cog — RCON, status, map management

### Lua Webhook v1.6.0
- **feat(lua):** Spawn/death tracking, safe gentity access (crash fix)
- **feat(proximity):** Proximity Tracker v3 — crossfire detection, trade kill support

---

## [1.0.5] - 2026-01-25

- **feat(lua):** Webhook v1.3.0 — pause event timestamps, warmup end tracking, timing legend
- **feat(lua):** Webhook v1.2.0 — warmup phase tracking

## [1.0.4] - 2026-01-22

- **feat(lua):** Real-time round notifications (~3s after round end vs 60s SSH polling)
- **feat(lua):** `lua_round_teams` table — team composition, pause tracking, surrender timing fix
- **fix(lua):** R2 webhook rejection — `round_number=0` was incorrectly rejected

## [1.0.3] - 2026-01-14

- **feat(bot):** EndStats processing — 7 award categories, VS stats tracking
- **feat(bot):** Discord follow-up embeds with awards
- **feat(db):** 3 new tables: `round_awards`, `round_vs_stats`, `processed_endstats_files`

---

## Version Summary

| Version | Date | Highlights |
|---------|------|------------|
| **1.1.0** | 2026-03-20 | Stats audit (R0 fix, 14 bugs), React 19 (19 routes), Proximity v5 (5 systems), alive% engine value |
| **1.0.8** | 2026-02-27 | Round correlation, match_id fix, linkage anomaly detection, objective coords |
| **1.0.7** | 2026-02-22 | Greatshot highlight enrichment, database cross-reference |
| **1.0.6** | 2026-02-07 | Greatshot demo pipeline, player analytics, matchup system, website SPA |
| **1.0.5** | 2026-01-25 | Lua webhook pause/warmup tracking |
| **1.0.4** | 2026-01-22 | Real-time Lua webhook, surrender timing fix |
| **1.0.3** | 2026-01-14 | EndStats awards, VS stats, Discord follow-ups |
