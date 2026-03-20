# Changelog

All notable changes to this project will be documented in this file.

This changelog is managed by Release Please using Conventional Commits.

## [1.1.0] - 2026-03-20

### Stats Accuracy Audit
- **fix(api):** R0 match summary rows double-counting kills/damage across 7+ endpoints — 94% inflation fixed
- **fix(api):** `NULLIF(SUM(deaths), 1)` → `NULLIF(SUM(deaths), 0)` in 10 leaderboard KD formulas
- **fix(api):** Accuracy now weighted by shots fired instead of naive per-round average
- **fix(api):** Headshots leaderboard uses `headshot_kills` (actual kills) instead of `headshots` (hit events)
- **fix(api):** `survival_rate` now uses engine TAB[8] alive% (excludes dead + limbo time)
- **fix(api):** `played_pct` capped at 100% (engine vs Lua timer ±1-3 sec per round)
- **fix(bot):** Headshot % formula in `!stats` — was `headshot_kills / weapon_hits`, now `headshot_kills / kills`
- **fix(bot):** `await` on sync methods in `advanced_team_detector.py` — runtime TypeError crash
- **fix(bot):** Achievement help text thresholds now match actual `achievement_system.py` values
- **fix(bot):** `avg_dpm` conditional formatting in Career Overview embed

### alive% / TMP (Time Played Percent)
- **feat(parser):** R2 differential for `time_played_percent` — converts cumulative percentage to R2-only via absolute alive time
- **feat(bot):** `time_played_percent` (TAB[8]) now stored in DB INSERT (column 53→54)
- **feat(api):** Dual-mode alive% — engine value as primary, computed as fallback, with drift detection
- **feat(backfill):** Backfilled 8,799 rows from VPS raw stats files (99.9% coverage)

### FragPotential Hidden
- **refactor(api):** FragPotential removed from API response (kept internally for playstyle classification)
- **refactor(bot):** Session graph FP chart replaced with K/D Ratio; playstyle panel uses DPM instead of FP
- **refactor(website):** SessionDetail shows Damage Efficiency instead of FragPotential

### React 19 Frontend Modernization
- **feat(website):** React 19 + TypeScript 5.9 + Vite 7 + Tailwind CSS v4 + Framer Motion
- **feat(website):** 19 route pages migrated from legacy JS to React (strangler pattern)
- **feat(website):** New components: InfoTip, PlayerLookup, ProximityIntro
- **feat(website):** New pages: ProximityPlayer, ProximityReplay, ProximityTeams

### Proximity v5.0 Teamplay Analytics
- **feat(proximity):** Lua tracker v5.0 — team pushes, trade kills, spawn timing, team cohesion, crossfire
- **feat(bot):** New `proximity_session_score_service.py` for proximity scoring
- **feat(bot):** Proximity cog updates for v5 data

### Parser & Pipeline
- **fix(parser):** `time_played_percent` R2 differential — percentage→absolute time→subtract→reconvert
- **fix(parser):** R0 match summary correctly uses R2 cumulative TAB[8] as match-level alive%

### Cleanup
- **chore:** Removed stale docs/instructions/ and docs/reports/ from repository
- **chore:** Removed obsolete `freshinstall.sh` and `update_bot.sh`

## [1.0.8] - 2026-02-18

- Baseline release marker for automated semver releases.
