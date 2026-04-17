# Changelog

> Historical long-form notes. Canonical release changelog: `../CHANGELOG.md`.

All notable changes to Slomix are documented here.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Security — Sprint 2 (2026-04-17, Mega Audit v3)
- **`dependencies.py`**: new `require_admin_user` FastAPI dependency that reuses existing `WEBSITE_ADMIN_DISCORD_IDS` / `ADMIN_DISCORD_IDS` / `OWNER_USER_ID` env vars for consistent admin gating (matches `availability.py` and `planning.py`). Raises 401 on missing session, 403 on non-admin session.
- **`diagnostics_router.py`**: 10 of 11 endpoints now require admin session (`/diagnostics`, `/diagnostics/lua-webhook`, `/diagnostics/round-linkage`, `/diagnostics/time-audit`, `/diagnostics/spawn-audit`, `/monitoring/status`, `/live-status`, `/server-activity/history`, `/voice-activity/history`, `/voice-activity/current`). `/status` stays public as a health check.
- **`api_helpers.py::resolve_display_name` + `batch_resolve_display_names`**: strip ET color codes from every resolved name — covers 10+ consumer routers (records_awards, records_player, proximity_*, greatshot_topshots, etc.) in one change.
- **`auth.py` OAuth callback**: Discord ID is now masked at INFO log level (`discord_id=1234****`); full ID + username moves to DEBUG only to reduce PII exposure in production logs.
- Full report: `docs/research/MEGA_AUDIT_V3_SPRINT2_2026-04-17.md`.

### Session Detail 2.0 matrix — review fixes (2026-04-17, Mega Audit v3 Sprint 1.5)
- **`sessions_router.py::build_team_matrix`**: `strip_et_colors()` now applied to `player_name` before JSON output — fixes UX bug where names rendered with raw `^1`, `^3` color codes (CR-01).
- **`sessions_router.py::build_team_matrix`**: name selection logic changed from "longest string wins" (which always picked color-coded version) to "first non-empty wins" — stable across aliases after strip (CR-01b).
- **`stopwatch_scoring_service.py::build_round_side_to_team_mapping`**: now accepts optional `team_a_name` + `team_b_name` kwargs so caller can pass canonical names from `scoring_payload` instead of relying on dict-order heuristic; `build_team_matrix` updated to pass them (CR-03 — prevents swapped team assignment when dict insertion order ≠ expected order).
- Full review in `docs/research/SESSION_DETAIL_V2_REVIEW_2026-04-17.md` (9 findings, 3 fixed, 6 deferred to Sprint 2+).

### Performance — Storytelling parallelization (2026-04-17, Mega Audit v3 Sprint 1)
- **`storytelling_service.py`**: 7 context loaders in `compute_session_kis` now run in parallel via `asyncio.gather` (was sequential `await` chain). Expected -500 ms per call.
- **`storytelling_service.py`**: 11 moment detectors in `detect_moments` now run in parallel via `asyncio.gather(return_exceptions=True)`. Per-detector error logging preserved. Expected -1.5 s per call.
- **Total impact**: ~-2 s response time on `/storytelling/kill-impact/*` and `/storytelling/moments/*` endpoints.

### Security — Date validation
- **`storytelling_router._parse_date`**: now rejects dates outside `[2020-01-01, today]` with HTTP 400 (prevents DoS via large-interval queries).

### Docs
- **`CLAUDE.md`**: version bumped 1.1.2 → 1.4.2 (sync with `.release-please-manifest.json`).
- **`docs/research/MEGA_AUDIT_V3_SPRINT1_2026-04-17.md`**: full Sprint 1 report with findings, verifications, and remaining work.

## [1.7.0] — 2026-04-01: Live Session Audit & Website Data Quality

**Live pipeline audit during 3v3 session + Mandelbrot RCA on every change. 11 commits, website data quality fixes.**

#### Bot — Pipeline Resilience
- **Round linker fallback**: `_link_lua_round_teams` falls back to `round_date+round_time` when Lua metadata missing (bot restart no longer orphans lua_round_teams entries)
- **Correlation merge**: Lua webhook + stats file correlations merged via ±30s timestamp proximity (was creating 3 entries per match)
- **R2 semantic merge**: R2 Lua events matched to existing R1 correlation by round-number awareness (30-900s window), eliminating 53% orphan rate
- **Dead cog disabled**: Removed synergy_analytics load attempt (`analytics` package never existed, was logging warning on every restart)
- **Manual backfill**: lua_round_teams 473→10209, 475→10210 linked + enriched with Lua metadata

#### Website — Proximity Page
- **ET color codes**: `stripEtColors()` added to all 10 v6 render functions (carrier, engineer, objective-runs, flag-returns, escort, lua-trades, spawn-timing)
- **prox_scores dashboard**: fixed `request` parameter missing from dashboard dispatcher

#### Website — Session Stats (Session 2.0)
- **Useful Kills / Self Kills / Full Self Kills**: 3 new columns in Players tab (UK/SK/FSK with tooltips) + 2 new charts (Useful Kills ladder + SK/FSK grouped bar)
- **Session detail endpoint**: added `useful_kills` + `full_selfkills` to `/api/stats/session/{id}/detail` query and response (was returning 0)
- **Graphs endpoint**: added `full_selfkills` to SELECT + aggregation + response
- **DPM graph fix**: session graphs aggregate by `player_guid` not `player_name` — fixes name-change mid-session split (e.g. qmr → #allbad*QMAR)

#### Website — Weapon Stats
- **Accuracy formula**: `SUM(hits)/SUM(shots)*100` replaces broken `AVG(accuracy)` across 3 queries (syringe showed 65.9% instead of correct 83.3%)
- **Deaths column**: added `SUM(deaths)` to session weapon mastery endpoint + response
- **Death-only weapons**: `HAVING` expanded to `SUM(deaths) > 0` — shows weapons you were killed by but never fired
- **session_date filter**: weapon mastery endpoint was silently ignoring `session_date` parameter
- **GUID matching**: `LEFT(player_guid, 8)` prefix match handles both 8-char legacy and 32-char canonical GUIDs

#### Website — Records/Seasons
- **Dead SQLite fallback removed**: -165 lines of `sessions` table + `session_date` column queries that caused 17+ errors per page load
- **team_damage fix**: column renamed `team_damage` → `team_damage_given`
- **Dead identical fallback removed**: `fallback_team_dmg` was identical copy of `team_dmg_query`

---

## [1.6.0] — 2026-03-30: Mandelbrot RCA v2.0 Audit, Oksii Adoption & God File Splits

**Full P0-P3 vibe coding audit, Oksii stats adoption (KIS v2 + BOX scoring), storytelling improvements, and 2 god file decompositions — 18 commits, 240 files, 476 tests passing.**

*18 commits across bot, website, proximity, Lua, parser, and test suites. Ruff 0 errors, 101 new unit tests.*

#### Mandelbrot RCA v2.0 Audit — Code Quality
- **Ruff expansion**: 8 rule sets (E/F/W/I/UP/B/S/T20/SIM/C4), 2257→0 errors with auto-fix and per-file ignores
- **Silent exceptions audit**: 23 `except: pass` + 5 silent returns replaced with `logger.debug()`/`logger.warning()` and `exc_info=True`
- **print→logger**: All production `print()` calls replaced with structured logging
- **pytest-asyncio**: Version fixed (1.3.0→0.24.0)
- **mypy**: Configuration added (non-blocking, informative baseline)
- **Shared constants**: Extracted `KILL_MOD_NAMES`, `_strip_et_colors()`, `_weapon_name()` → `website/backend/utils/et_constants.py`
- **Memory leak fix**: `_compute_locks` unbounded dict → `BoundedLockDict` (max 64, LRU eviction)

#### Oksii Adoption — Lua + Parser + KIS v2
- **Lua v6.01**: New `countAlivePerTeam()` function, combat positions extended with `killer_health`, `axis_alive`, `allies_alive`; spawn timing extended with `killer_reinf`, `victim_reinf`
- **Parser**: Backward-compatible `len(parts) > N` checks for new CSV columns, `_table_has_column` DB guards before INSERT
- **KIS v2 multipliers**: Health (1.3x at <30HP), alive (dynamic threshold based on player count), reinf (relative to interval)
- **KIS soft cap**: `5.0 + (raw - 5.0) * 0.25` prevents inflation (range 1.0-~8.5, was unbounded at 19.19)
- **DB migration 033**: New columns on `proximity_combat_position`, `proximity_spawn_timing`, `storytelling_kill_impact` + new `session_round_scores` table

#### BOX Scoring Service — NEW
- **Oksii-style stopwatch scoring** (`box_scoring_service.py`, 268 lines): +2 map win, +1 double fullhold, provisional R1 scoring
- **On-demand API**: Session-based BOX score calculation with round-by-round breakdown

#### Storytelling Improvements — Legacy Website
- **Narrative section**: Auto-generated session summary with MVP, archetype, defining moment
- **Momentum chart**: Chart.js per-round Axis vs Allies scoring curves
- **KIS breakdown fix**: Proportional distribution instead of heuristic — numbers now sum correctly
- **Player info row**: DPM, denied playtime/min, dead% added to player cards
- **Oksii multiplier badges**: Clutch, Solo, Outnum, Deny badges on story player cards

#### God File Decompositions
- **proximity_router.py**: 5,515→35 lines (thin aggregator + 13 sub-routers, max 709 lines each)
- **records_router.py**: 3,172→27 lines (thin aggregator + 9 sub-routers, max 751 lines each)

#### Testing
- **101 new unit tests**: Storytelling service (51), skill rating (28), BOX scoring (22)
- **Total**: 476 passing, 45 skipped, 0 failed
- **End-to-end verified**: Bots generated 33 rounds, 2781 combat positions with Oksii data (99.8% coverage)

#### Bug Fixes
- **Round linker timezone**: UTC vs local naive datetime caused 7200s offset on CEST server — broke 45-min match window
- **Revives endpoint**: `session_date` column doesn't exist → `created_at`
- **Kill-outcomes LIMIT**: f-string SQL → parameterized query
- **Kill-outcomes types**: Missing `int | None` annotations caused FastAPI to skip validation
- **Storytelling synergy key**: `synergy.get("teams")` → `synergy.get("groups")` (key mismatch)
- **Storytelling router import**: Broken import fixed (storytelling_service)
- **NULL objective times**: Filter `if r[2] and r[2] > 0` prevents crash on incomplete data

---

## [1.5.0] — 2026-03-28: Round Replay Timeline, Momentum Chart & Codacy Zero

**Visual round analysis with event replay, momentum tracking, session narratives, expanded moment detectors, and full Codacy compliance — 53 commits, 58 issues resolved to zero.**

*53 commits across website frontend/backend, bot services, and legacy JS modules. CI: 9/9 checks green (lint, tests, CodeQL, Docker, Codacy).*

#### Round Replay Timeline — NEW
- **Dual-pane viewer** (`/#/replay`): Event feed on the left, 2D map canvas on the right, synchronized scrubber bar for frame-by-frame navigation
- **Player positions**: Sourced from `player_track.path` JSONB at 200ms precision — real-time player dots on map overlay
- **420+ events per round**: Kills, deaths, revives, objectives, team actions rendered on interactive timeline
- **2D map canvas**: ET:Legacy map backgrounds with player position markers and event annotations
- **3 API endpoints**: Round event feed, player track positions, round metadata

#### Momentum Chart — NEW
- **30-second window momentum**: Rolling window scoring with 0.85 exponential decay factor
- **Canvas 2D dual-line chart**: Axis vs Allies momentum curves rendered on HTML5 Canvas
- **Per-round tabs**: Navigate between rounds within a session to compare momentum shifts

#### Session Narrative — NEW
- **Auto-generated paragraph**: Summarizes MVP, player archetype, defining moment, and team synergy comparison for each session
- **Data-driven storytelling**: Pulls from KIS, archetypes, moments, and synergy scores to compose coherent match narratives

#### Moment Detectors Expanded (11 total, was 5)
- **New detectors**: Team wipe (5★), multikill (2-5★ scaled), objective secured, objective denied, objective run, multi-revive
- **Objective-focused moments**: Carrier interception chains, contested engineer builds, dynamite defuses
- **Rich kill-by-kill context**: Each moment includes weapon names (35-weapon mapping), timestamps, duration, and player display names

#### Code Quality — Codacy 58 → 0 (Mandelbrot Audit)
- **22 CRITICAL XSS**: ALL `innerHTML` assignments replaced with DOM API (`createElement` + `textContent`) across `story.js`, `rivalries.js`, `replay.js`
- **12 HIGH TypeScript**: Non-null assertions replaced with guard checks, optional chains added, void arrow returns fixed, object bracket injection prevented
- **7 SQL injection**: ALL f-string SQL eliminated — replaced with pre-built query dictionaries and column whitelists
- **Protocol stubs**: Added missing protocol handler stubs
- **Stack trace exposure**: Health check endpoints no longer leak stack traces to clients
- **URL redirect validation**: Added origin validation on redirect endpoints
- **Insecure randomness**: Replaced `Math.random()` with `crypto.getRandomValues()` where security-relevant
- **Zero suppressions**: Every issue resolved properly — no `// eslint-disable` or `# noqa` workarounds
- **CI**: 9/9 checks green (lint, tests, CodeQL, Docker build, Codacy quality gate)

#### Data Truth Verification
- **KIS push_multiplier**: Deflated from 99.8% → 11.9% after quality-gating (was over-counting non-push kills as push kills)
- **Synergy groups**: Fixed for stopwatch team swaps — synergy now correctly tracks players through side changes
- **Headshot% formula**: Confirmed corrected to `hs_hits / total_hits` (fix from v1.4.0)

#### Bug Fixes
- **MomentumChart non-null assertion → guard check**: Prevented crash when chart data is null during initial render
- **Rivalries double /api/api/ prefix**: Fixed URL construction that produced broken API calls
- **Narrative gaming_session_id query**: Fixed query pulling session ID from wrong table
- **PUSH_MULTIPLIER import removed**: Cleaned up after quality-gating made the constant unused
- **gaming_sessions diagnostic query restored**: Re-added diagnostic query lost during `--ours` merge resolution

---

## [1.4.0] — 2026-03-27: Player Rivalries, Win Contribution & Smart Stats Phase 2

**Full esports analytics upgrade: head-to-head rivalry engine, per-round win contribution scoring, 11 match moment detectors with rich context, 9 server-side archetypes, and 35-weapon name mapping.**

*Multiple commits. New: rivalries cog + service, win contribution engine, Smart Stats Phase 2 moment detectors, weapon name mapping, archetype formula v2.*

#### Player Rivalries System — NEW
- **H2H stats engine**: Complete head-to-head record between any two players — kills, deaths, KD, accuracy, DPM per pairing
- **Classification**: Nemesis (losing badly), Prey (winning handily), Rival (closely contested) — based on win rate and encounter count
- **Weapon breakdown**: Per-rivalry weapon usage breakdown for each player in the matchup
- **Per-map drill-down**: H2H breakdown split by map played
- **Rivalry leaderboard**: Top rivalry pairs sorted by total encounters
- **New page `/#/rivalries`**: Full rivalry dashboard with pair lookup, leaderboard, and H2H detail view
- **Bug fixes**: GROUP BY clause fix in rivalries SQL; player encounter threshold adjusted for competitive play

#### Win Contribution (PWC / WIS / WAA) — NEW
- **Per-Round Win Contribution (PWC)**: 5-component formula — kills, damage dealt, objectives secured, revives given, survival time
- **Dynamic weight redistribution**: When a round has zero objectives, objective component weight redistributes automatically to kills and damage proportionally
- **Win Impact Score (WIS)**: avg(PWC in won rounds) − avg(PWC in lost rounds) — surfaces who actually shifts match outcomes
- **Win Absolute Average (WAA)**: Cross-session baseline for fair WIS comparison
- **MVP detection**: Highest WIS player flagged as session MVP per round set
- **Stacked bar visualization**: Per-component breakdown for every player in every round

#### Smart Stats Phase 2 — Match Moments & Archetypes
- **11 moment detectors** (up from 5 in Phase 1):
  - *Existing (enhanced)*: kill streak, trade chain, focus fire survival, team push success, carrier chain
  - *New*: team wipe, multikill, objective secured, objective denied, objective run, multi-revive
- **Rich moment context**: Each moment includes per-kill breakdown with weapon names, precise timestamps, duration, and player GUIDs resolved to display names
- **Moment type diversity**: Score cap per moment type prevents single-category crowding in the timeline
- **9 Player Archetypes v2**: Formula updated to use DPM + denied_time + headshot% + KD + trade rate + revive count (was KIS + combat position); relative thresholds for competitive server populations
- **35-weapon name mapping**: Full ET:Legacy weapon ID→name lookup (Thompson, MP40, Sten, Panzerfaust, Panzer, Flamethrower, Mortar, Luger, Colt, etc.) applied across all moment and archetype displays

#### Bug Fixes
- **Headshot% formula**: Corrected to `hs_hits / total_hits` (was `hs_kills / kills` — significantly different for spray weapons)
- **GUID mismatch**: Resolved 8-char vs 32-char GUID inconsistency across rivalries service, archetype service, and win contribution engine
- **ET color code stripping**: Applied `^N` color code regex strip to all player name displays in rivalries and archetypes
- **Rivalries SQL GROUP BY**: Fixed GROUP BY clause that caused query error on multi-round aggregation
- **Rivalries threshold**: Player encounter minimum adjusted to surface meaningful competitive pairs

---

## [1.3.0] — 2026-03-27: Smart Storytelling Stats, Mandelbrot Audit & 45-Finding Resolution

**Smart competitive narratives powered by contextual kill scoring, player archetypes, and team synergy — plus a full-stack Mandelbrot audit with 100% finding resolution.**

*Multiple commits across 35+ files. 4 parallel Sonnet audit teams reviewed 32 changed files line-by-line.*

#### Smart Storytelling Stats (Phase 1+2) — LIVE
- **Kill Impact Score (KIS) engine**: Contextual kill scoring with 7 multipliers — carrier kills (3-5x), push kills (2x), crossfire assists (1.5x), spawn timing efficiency (1-2x), outcome weight (gib/revive/tap-out), class bonus (medic/engineer), distance factor
- **Match Moments**: 5 detectors — kill streaks (3+ rapid kills), carrier interception chains (objective denial sequences), focus fire survival (surviving concentrated enemy fire), team push success (coordinated advances), trade kill chains (revenge kills within window)
- **Player Archetypes**: 9 server-side types with full data access (KIS + stats + proximity + combat position) — Pressure Engine, Medic Anchor, Silent Assassin, Objective Demon, Trade Specialist, Support Fortress, Flanker, All-Rounder, Wildcard
- **Team Synergy Score**: 5-axis per-faction comparison — crossfire rate, trade coverage, cohesion quality, push success rate, medic bonds
- **Legacy `/#/story` page**: Cinematic hero section, player story cards with archetype badges, match moment timeline, KIS breakdown bars with multiplier visualization, team synergy radar panel
- **Backend**: `storytelling_kill_impact` DB table, 4 API endpoints, storytelling service with full proximity/stats data pipeline

#### Mandelbrot RCA Audit — 45 Findings, 45 Resolved
- **Audit scope**: 4 parallel Sonnet teams reviewed all 32 changed files line-by-line across bot, website, proximity, and infrastructure
- **Findings**: 2 CRITICAL, 11 HIGH, 16 MEDIUM, 16 LOW — all resolved across 3 fix commits
- **CRITICAL**: Re-linker referenced non-existent columns (`proximity_revive`, `proximity_weapon_accuracy`); N+1 INSERT loop in storytelling import
- **HIGH**: TOCTOU race condition in session processing (→ per-session `asyncio.Lock`); rate limiter blind to `X-Forwarded-For` behind proxy; leaderboard `round_number` filtering disabled; missing error propagation in 6 service methods
- **MEDIUM/LOW**: 21 code quality improvements — unused imports, missing type hints, inconsistent error handling, docstring gaps

#### Additional Post-Audit Fixes
- **Re-linker column cleanup**: Removed `proximity_revive` + `proximity_weapon_accuracy` from re-linker table list (columns don't exist in schema)
- **N+1 INSERT → executemany batch**: Storytelling kill impact inserts batched for performance
- **TOCTOU race condition**: Per-session `asyncio.Lock` prevents concurrent processing of same session
- **Rate limiter proxy awareness**: `X-Forwarded-For` header parsing for accurate client IP behind reverse proxy
- **Leaderboard round filtering**: `round_number` filter parameter now functional in leaderboard queries
- **21 LOW/INFO code quality improvements**: Resolved across bot, website, and proximity modules

---

## [1.2.0] — 2026-03-26: Deep RCA Audit, Proximity Pipeline Overhaul & Website Redesign

**Mandelbrot-depth root cause analysis across the entire stack — 26 fixes, proximity pipeline redesign, and website overhaul.**

*8 commits, 25+ files modified, ~800 lines changed. 17/21 tasks completed across 4 parallel agent teams.*

#### Infrastructure Recovery
- **Power outage filesystem recovery**: Recovered from corrupted `.git` objects caused by power failure
- **Branch merge reconciliation**: Merged 17 divergent commits (9 local RCA audit + 8 remote Codacy/XSS fixes)
- **Orphan branch cleanup**: Cleaned up 4 orphaned feature branches

#### Proximity Pipeline Redesign
- **STATS_READY webhook trigger**: Proximity import now fires on STATS_READY event instead of independent polling — eliminates 60% of historical linkage failures
- **Re-linker background task**: New periodic task fixes NULL `round_id` references across 22 proximity tables
- **Polling reduction**: Fallback polling reduced from 5min to 2min
- **Root cause**: Two independent polling loops with no coordination (identified via Mandelbrot-depth RCA)

#### Proximity Website — Complete Overhaul
- **Default scope auto-selection**: First visit auto-selects last round (was showing empty state)
- **Leaderboard scoping**: ALL 7 categories (Damage, KD, Efficiency, Headshots, Revives, Accuracy, Alive%) now respect session/map/round selection
- **HTML render bug fixes**: Fixed double-escape in 3 panels (Focus Fire, Objective Focus, Weapon Accuracy)
- **Crossfire GUID→name resolution**: LATERAL JOIN replaces raw GUIDs with player names
- **Metric tooltips**: Added explanatory tooltips for Focus Fire, Objective Focus, Combat Positions
- **Support Uptime rename**: "Support Uptime" → "Teammate Combat Support" (was incorrectly labeled medic-specific)
- **Scope UX improvements**: Range buttons hidden when scope active, scope indicator badge displayed
- **React Proximity.tsx scope fix**: KillOutcomes, HitRegions, HeadshotRates panels now pass scope params correctly

#### Bug Fixes
- **!last_session graph crash**: `Decimal * float` TypeError — applied 16 float conversions across graph generation
- **Round correlation FK cascade**: Pre-validate FK references before insert; boolean completeness flags set independently
- **Upload Library MP4 download**: Now forces `Content-Disposition: attachment` (was streaming inline)
- **Skill Rating optimization**: Merged dual `GROUP BY` query in `compute_all_ratings` into single pass (~50% less DB load)
- **API rate limiting**: Added slowapi rate limits on 3 heavy proximity endpoints
- **Import column compatibility**: Fixed re-linker column name compatibility with schema changes

#### Research & Design
- **ET:Legacy competitive mechanics reference**: Game mechanics documentation for analytics context
- **Lua (0,0,0) position audit**: Audited all proximity data — 0 bad rows found (latent risk documented)
- **Kill Outcomes verification**: 4,503 rows across 54 rounds confirmed healthy
- **Session 103 pipeline trace**: Full 21-round pipeline verification — all clean

---

### Fixed — 2026-03-26: Deep RCA Audit (Mandelbrot-depth root cause analysis)

Full report: `docs/DEEP_RCA_AUDIT_RESULTS_2026-03-26.md`

#### CRITICAL fixes
- **Proximity.tsx corruption**: File was overwritten with Python coverage HTML; restored from `8bf2f6e`
- **Endstats infinite retry loop**: Added max 5 attempts + DB marking; fixed `success=TRUE` filter in dedup check
- **Phantom processed_files**: 361 entries with `success=TRUE` that were header-only; batch corrected
- **Promise.allSettled masking**: Added rejection logging in `app.js` and `session-detail.js`
- **file_tracker.py DB error masking**: `_is_in_processed_files_table` and `_session_exists_in_db` returned False on DB error with only DEBUG logging → upgraded to WARNING

#### HIGH fixes
- **Proximity date type bug**: 7 v6 endpoints crashed with asyncpg DataError; added `_parse_iso_date()` at all 11 locations
- **session_teams GRANT**: `website_app` lacked DELETE/INSERT/UPDATE on `session_teams`; GRANT executed
- **Webhook race condition**: Added `_in_flight` set with atomic check-and-claim under `_state_lock` in `stats_webhook_notify.py`
- **Team manager silent deserialization failure**: Added warning log for JSON parse errors in `team_manager.py:148`
- **`_is_admin` silent demotion**: Added warning log for DB errors in `availability.py` and `planning.py`

#### MEDIUM fixes (20+)
- Error masking audit: 20+ silent `except: pass/return []` patterns fixed with proper logging
- `proximity_router.py`: Added logging for `_table_column_exists`, `_load_scoped_guid_name_map`, `_parse_json_field`, v5 table counts
- `proximity.js`: Replaced 4 empty `.catch(() => {})` with `console.warn`
- `session-detail.js`: Added 5-minute TTL to overview cache
- `ultimate_bot.py`: Pass `error_msg` to `mark_processed` (was always NULL)
- `round_linkage_anomaly_service.py`: Narrowed bare `except Exception` to specific types

#### Performance
- **Composite dashboard endpoint**: `GET /proximity/dashboard?sections=all` reduces 31 HTTP requests to 2-3 (90% reduction, ~467ms total)

#### Infrastructure
- Round linker cleanup: 329 → 14 unresolved (315 marked abandoned)
- `!last_session` query verified at 0.4ms with existing indexes

### Added — 2026-03-24: Kill Outcomes, Hit Regions, Combat Heatmaps & Movement Analytics

#### Kill Outcome Tracking (Feature 1 — requires Lua deploy)
- **Lua**: Replaced broken `pollKillOutcomes()` PMF_LIMBO polling with event-driven state machine
  - Gib detection via `body_damage >= 175` in `et_Damage`
  - Tap-out detection via `et_ClientSpawn(revived=0)`
  - Revive detection via existing `et_ClientSpawn(revived=1)`
  - Stale cleanup throttled to every 5s (was per-frame)
- **API**: `GET /proximity/kill-outcomes` — outcome distribution + recent events
- **API**: `GET /proximity/kill-outcomes/player-stats` — Kill Permanence Rate (KPR) leaderboard
- **Frontend**: KillOutcomesPanel — outcome bars (gibbed/revived/tapped_out), KPR leaderboard, Most Revived

#### Hit Region Tracking (Feature 2 — requires Lua deploy)
- **Lua**: Full 4-region delta detection (HEAD/ARMS/BODY/LEGS) in `et_Damage` via `pers.playerStats.hitRegions` comparison, 5000-entry cap
- **Parser**: `HitRegionEvent` dataclass + `_parse_hit_region_line()` + `_import_hit_regions()`
- **DB**: Migration #025 — `proximity_hit_region` (per-event) + `proximity_hit_region_summary` (aggregate with computed `headshot_pct`)
- **API**: `GET /proximity/hit-regions` — per-player region breakdown
- **API**: `GET /proximity/hit-regions/by-weapon` — per-weapon breakdown for a player
- **API**: `GET /proximity/hit-regions/headshot-rates` — headshot % leaderboard (min 50 hits)
- **Frontend**: HitRegionsPanel — region distribution bars, headshot leaderboard, most active shooters

#### Combat Position Heatmaps (Feature 3 — requires Lua deploy)
- **Lua**: Captures killer + victim xyz positions on every kill in `et_Obituary` with team, class, weapon, MOD
- **Parser**: `CombatPosition` dataclass (18 fields) + `_parse_combat_position_line()` + `_import_combat_positions()`
- **DB**: Migration #026 — `proximity_combat_position` with UNIQUE constraint and 7 indexes
- **API**: `GET /proximity/combat-positions/heatmap` — grid-binned hotzone data with kills/deaths perspective toggle
- **API**: `GET /proximity/combat-positions/kill-lines` — attacker→victim coordinate pairs for map overlay
- **API**: `GET /proximity/combat-positions/danger-zones` — top death hotspots with class breakdown
- **Frontend**: CombatHeatmapPanel — canvas heatmap with kills/deaths toggle, kill line overlay, map name input

#### Movement Analytics (Phase A — works with existing data, no Lua changes)
- **Parser**: 6 new `@property` on `PlayerTrack`: `peak_speed`, `stance_standing_sec`, `stance_crouching_sec`, `stance_prone_sec`, `sprint_sec`, `post_spawn_distance`
- **DB**: Migration #027 — 6 new columns on `player_track`
- **Backfill**: `scripts/backfill_player_track_metrics.py` — computed metrics for 13,457 existing tracks from JSONB path data
- **API**: `GET /proximity/movement-stats` — per-player aggregated movement analytics (stance, speed, distance, sprint)
- **Frontend**: MovementStatsPanel — stance distribution bar, biggest movers, speed/sprint leaderboards, post-spawn rush ranking

#### Infrastructure
- **Lua**: Feature flags for all 3 new features (`kill_outcome_tracking`, `hit_region_tracking`, `combat_positions`) — individually toggleable
- **Frontend**: Fixed pre-existing TS error — added missing `times_focused`, `avg_attackers`, `avg_damage` fields to `ProximityLeaderboardEntry`
- **Documentation**: `docs/OKSII_COMPARISON_REPORT.md` — comparison with Oksii's game-stats-web.lua, Phase A-D implementation roadmap

### Fixed — 2026-02-28

- **Lua round_id Linkage Race Condition** — Fixed a race condition where `_link_lua_round_teams()` would permanently link Lua webhook data to the wrong round when the same map was played multiple times in a session:
  - Root cause: Lua webhook arrives before stats file import completes; linker picks nearest *existing* round of same map+round_number, which is wrong when replayed maps exist
  - Added second pass to `_link_lua_round_teams()` that detects and corrects stale linkages when a closer-matching round is imported later
  - Created `scripts/relink_lua_round_teams.py` backfill script (dry-run by default)
  - Backfilled both samba (1 fix) and slomix (4 fixes) databases for session 9973..9995
  - Investigation report: `docs/LUA_TIMING_DRIFT_INVESTIGATION_2026-02-27.md`
- **Website round JOIN fragility** — Replaced composite key fallback `(round_date, map_name, round_number)` with direct `round_id` JOIN in player stats endpoint (`api.py:3263`)
- **Website silent error handlers** — Added logging to 3 bare `except: return {}` handlers in `api.py` (resolve_alias_guid_map, resolve_name_guid_map, _load_scoped_guid_name_map)
- **Chart.js crash prevention** — Added `hasChartJs()` guards to `retro-viz.js` (4 chart functions) and `player-profile.js` (2 chart functions) that would throw `ReferenceError` if Chart.js was missing
- **Chart.js user feedback** — Added visible "Charts unavailable" fallback text in `sessions.js` canvas slots instead of silent empty canvases

### Changed — 2026-02-26

- **Round Correlation Live Rollout Guardrails** — Correlation service is now config-driven with safe live rollout behavior:
  - New config flags: `CORRELATION_ENABLED`, `CORRELATION_DRY_RUN`, `CORRELATION_REQUIRE_SCHEMA_CHECK`, `CORRELATION_WRITE_ERROR_THRESHOLD`
  - Default requested mode moved to live (`CORRELATION_DRY_RUN=false`) with automatic fallback to dry-run if guardrails fail
  - Schema preflight verifies `round_correlations` columns before enabling writes
  - Circuit breaker auto-disables live writes after repeated DB write errors
  - `!correlation_status` now shows requested/effective mode, preflight state, write error counter, and guardrail reason
- **Round/Match Linkage Anomaly Checks** — Added thresholded diagnostics for linkage drift across `lua_round_teams`, `rounds`, and `round_correlations`:
  - New service: `bot/services/round_linkage_anomaly_service.py`
  - New API endpoint: `GET /diagnostics/round-linkage`
  - New read-only script: `scripts/check_round_linkage_anomalies.py` (optional `--fail-on-breach` for gates/alerts)
  - New focused tests for service and endpoint payload contract
- **Proximity Objective Coordinates (Top-Played Batch)** — Filled objective coordinates for high-impact maps first and regenerated downstream outputs from the shared template source:
  - Updated template coverage for `te_escape2`, `etl_adlernest`, `supply`, `etl_sp_delivery`, `sw_goldrush_te`, `erdenberg_t2`, `braundorf_b4`, `etl_ice`
  - Regenerated Lua objective table (`proximity/lua/proximity_tracker.lua`) from `proximity/objective_coords_template.json`
  - Regenerated web objective zones (`website/assets/maps/proximity/objective_zones.json`)
- **WS11 Objective Coordinate Gate** — Added explicit static + runtime guardrails to block top-map coverage regressions:
  - New gate script: `scripts/proximity_objective_coords_gate.py`
  - New runtime DB wrapper: `scripts/check_ws11_objective_coords_gate.sh`
  - New gate config: `proximity/objective_coords_gate_config.json` (static guard list + runtime allowlist)
  - New focused tests: `tests/unit/test_proximity_objective_coords_gate.py`
- **W12 Single Trigger Path Enforcement** — Enforced canonical webhook trigger flow to avoid duplicate producer paths:
  - New config: `WEBHOOK_TRIGGER_MODE` (`stats_ready_only` default; legacy modes explicit)
  - Webhook handler now gates legacy filename triggers when strict mode is active
  - Startup webhook security validation now blocks `WS_ENABLED=true` in strict mode
  - New ops gate script: `scripts/check_ws12_single_trigger_path.sh` (local policy + optional remote deprecated-service/process checks)
  - Added config loading/validation tests for trigger mode behavior

### Added — 2026-02-24

- **Proximity v5 Teamplay Pipeline** — Full-stack implementation of 5 new teamplay analytics systems from `proximity_tracker_v5.lua`:
  - **Spawn Timing**: Per-kill spawn wave efficiency scoring (table: `proximity_spawn_timing`, command: `!pse`, API: `/proximity/spawn-timing`)
  - **Team Cohesion**: Periodic team shape snapshots with centroid, dispersion, buddy pairs (table: `proximity_team_cohesion`, command: `!pco`, API: `/proximity/cohesion`)
  - **Crossfire Opportunities**: LOS-verified crossfire angle detection with execution tracking (table: `proximity_crossfire_opportunity`, command: `!pxa`, API: `/proximity/crossfire-angles`)
  - **Team Pushes**: Coordinated team movement detection with objective orientation (table: `proximity_team_push`, command: `!ppu`, API: `/proximity/pushes`)
  - **Lua Trade Kills**: Server-side trade kill detection with reaction timing (table: `proximity_lua_trade_kill`, command: `!ptl`, API: `/proximity/lua-trades`)
  - Parser: 5 new dataclasses, parse methods, and import methods in `ProximityParserV4` (backward compatible with v4 files)
  - Migration: `migrations/013_add_proximity_v5_teamplay.sql` (5 tables with indexes)
  - Website: 5 new HTML panels, 7 JS render functions including Canvas cohesion timeline
  - Lua review: 8 bug fixes applied to `proximity_tracker_v5.lua` (team-damage filter, crossfire dedup, LOS mask, cache fix, teamkill filter, round_start_unix fallback, engagement timeout, cohesion guard)

### Added — 2026-02-22

- **Round Correlation System** — Event-driven service that tracks data completeness for each match (R1+R2). Correlates stats files, Lua webhook data, gametime files, and endstats into a single `round_correlations` row per match with 8 boolean flags and completeness percentage.
  - New table: `round_correlations` (23 columns, 8 completeness flags, status tracking)
  - New service: `bot/services/round_correlation_service.py` (270 lines, UPSERT pattern)
  - 5 hooks wired into existing import paths (4 in `ultimate_bot.py`, 1 in `postgresql_database_manager.py`)
  - Admin command: `!correlation_status` shows pending/partial/complete counts and recent correlations
  - **Starts in DRY-RUN mode** — logs events but does not write to DB. Flip `dry_run=False` after verification week.
  - Schema: `tools/schema_postgresql.sql` updated with table definition and indexes

- **ET:Legacy Server Research Document** — `docs/ET_LEGACY_SERVER_RESEARCH.md` (~500 lines) covering stopwatch mode internals, Lua stats generation (`c0rnp0rn7.lua` v3.0), `g_currentRound` inversion (engine 1=R1/0=R2, Lua inverts for filenames), R2 cumulative stats behavior, 3-second save delay, webhook vs stats file timing, and complete round lifecycle timeline. Sourced from ET:Legacy GitHub, Lua API docs, and local codebase analysis.

### Fixed — 2026-02-22

- **CRITICAL: match_id generation inconsistency** — `postgresql_database_manager.py:2112` used `filename.replace('.txt', '')` as match_id, producing unique IDs per round (e.g. `2026-02-20-235813-erdenberg_t2-round-1`). R1 and R2 of the same match never shared a match_id. Only 122/1767 rounds had correct R1+R2 pairs (485 orphan R1s, 477 orphan R2s). Fixed to extract `{date}-{time}` format (e.g. `2026-02-20-235813`) shared by R1+R2, matching the working logic in `ultimate_bot.py:1744-1755`. R2 uses R1's timestamp via `r1_filename` from the parser.

- **Completeness weight comment mismatch** — `round_correlation_service.py:219` comment said endstats weighed 5% each but code correctly used 10% each (total 100%). Fixed comment to match code: R1/R2 stats 25% each, lua 10% each, gametime 5% each, endstats 10% each = 100%.

- **Gametime hook timezone documentation** — `ultimate_bot.py:4059` uses `fromtimestamp()` (local time) to reconstruct match_id from `round_end_unix`. This is correct because stats file names use Lua's `os.date()` which also uses local time on the game server. Added clarifying comment to prevent future "fix" to UTC that would break correlation matching.

### Added — 2026-02-20

- **Super-Prompt Master Guide** — `docs/SUPER_PROMPT_2026-02-20.md` (~970 lines) synthesized from 51 docs, verified against codebase using 5 parallel agents. Caught and corrected 5 documentation errors before they could cause damage (Lua pcall exists, send_in_progress resets properly, parser field 9 already implemented, endstats line numbers off by +78, greatshot skill_rating already handled).

- **Production VM SRE Audit** — `docs/VM_AUDIT_REPORT_2026-02-20.md` — full audit of production VM (192.168.64.159) using 5 parallel agents. Key discoveries: PostgreSQL v17 (docs said v14), 67 tables (docs said 41), Redis running but undocumented, VM built Feb 19. Overall grade: B.

### Changed — 2026-02-20

- **VM Configuration Tuning** — Applied 6 production changes:
  - Added `PRODUCTION_CHANNEL_ID` to .env
  - Increased web service memory limits (512M→768M MemoryMax, 384M→640M MemoryHigh)
  - Increased `etlegacy_user` connection limit (20→30, shared by bot+web)
  - Increased `website_readonly` connection limit (10→20)
  - Added logrotate configuration (daily, 14 rotations, compressed, 10M max)
  - Verified all 5 services boot-enabled

### Fixed — 2026-02-16

- **R2 Lua Webhook Rejection** — `bot/ultimate_bot.py:3637` rejected all R2 webhook data because `round_metadata.get("round_number", 0) == 0` treated `round_number=0` as invalid. In ET:Legacy stopwatch mode, `g_currentRound=0` means R2, so `round_number=0` is a valid value. Changed guard to `round_metadata.get("round_number", -1) < 0`. DB evidence: `lua_round_teams` had 13 rows total, 11 R1, 0 R2.
- **Non-existent column references in round timing** — `bot/ultimate_bot.py:1459` referenced `round_time_seconds` and `time_limit_seconds` which do not exist in the `rounds` table. Fixed to `actual_duration_seconds` and `time_limit` respectively (WS1-006 related).

### Recovered

- **Restored deleted planning docs** — Two critical execution-tracking documents were recovered from git history (deleted in commit `1c0ab8e` during Feb 15 cleanup):
  - `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md` — Live gameplay monitoring protocol
  - `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md` — Sprint execution order with gates

### Added

- **Website Redesign — Analytics-First Platform**
  - **Component System** — Reusable UI components (`website/js/components.js`): PageHeader, KpiTile, ChartCard, TableCard, PodiumCard, ExpandableList, EmptyState, LoadingSkeleton
  - **Filter System** — Shared filter logic with URL sync (`website/js/filters.js`): GlobalFilterBar, period options (All Time, Season, 7d/14d/30d/90d, Custom), shareable URLs
  - **Hall of Fame Page** — 12 metric categories (Most Active, Wins, Damage, Kills, Revives, XP, Assists, Deaths, Selfkills, Full Selfkills, Consecutive Games, DPM) with podium display, expandable rankings, and time filters (`website/js/hall-of-fame.js`)
  - **Hall of Fame API** — `GET /api/hall-of-fame` with period filtering, 12 aggregate queries grouped by player_guid
  - **Trends API** — `GET /api/stats/trends` with time-series data for rounds, active players, kills, and map distribution
  - **Round Visualizer** — Interactive Chart.js round analytics replacing the static PNG gallery (`website/js/retro-viz.js`): 6 panels (Match Summary, Combat Radar, Top Fraggers, Damage Heatmap, Support Performance, Time Distribution), round picker dropdown, click-to-expand lightbox
  - **Round Viz API** — `GET /api/rounds/{id}/viz` returns full player stats for a round; `GET /api/rounds/recent` returns recent rounds for the picker
  - **Retro Viz Gallery (legacy)** — `GET /api/retro-viz/gallery` still available for PNG files
  - **Landing Page Insights** — New insights charts strip (rounds/day, active players/day, map distribution) with 14d/30d/90d toggle
  - **Retro Viz Teaser** — Teaser card on home page linking to gallery

### Changed

- **Navigation** — Removed standalone Sessions button from top-level nav (still accessible in Stats dropdown); added Hall of Fame as top-level nav item; added Retro Viz to Stats dropdown
- **Landing Page KPI Tiles** — Restyled to 3x2 grid with glass-panel cards, monospace numbers, colored accent borders
- **Landing Page Hero** — Updated tagline to "Track every frag, analyze every round, celebrate every victory"

- **Upload Library** — Community file sharing for configs (.cfg, .hud), archives (.zip, .rar), and clips (.mp4, .avi, .mkv)
  - OWASP-compliant file validation: extension allowlists, magic byte verification, size limits, SHA256 hashing
  - UUID-based storage outside web root with streaming upload and cleanup on failure
  - Browse/search/filter by category and tags, paginated results
  - Safe download headers (X-Content-Type-Options, CSP, X-Frame-Options), inline playback for MP4
  - Rate limit: 10 uploads/hour per user
  - Soft-delete (owner only)
  - Migration: `website/migrations/003_upload_library.sql` (uploads + upload_tags tables)
  - Backend: `website/backend/routers/uploads.py`, `website/backend/services/upload_store.py`, `website/backend/services/upload_validators.py`
  - Frontend: `website/js/uploads.js`, upload view in index.html

- **Daily Availability Poll + Notifications** — Discord daily "Who can play tonight?" system
  - Automated daily poll posting with ✅❌❔ reactions at configurable CET time
  - Reaction tracking via `on_raw_reaction_add/remove` (survives bot restarts)
  - Threshold notification: DMs opted-in players when YES count reaches N
  - Game-time reminders at configurable CET times (default 20:45, 21:00)
  - Per-user notification preferences via `!poll_notify` command and website UI
  - Website availability page with today's poll, response list, and history chart
  - Migration: `website/migrations/004_daily_availability_poll.sql` (daily_polls + poll_responses + poll_reminder_preferences)
  - Bot cog: `bot/cogs/availability_poll_cog.py`
  - Backend: `website/backend/routers/availability.py`
  - Frontend: `website/js/availability.js`, availability view in index.html

### Fixed

- **Discord login broken** — `https_only=True` in SessionMiddleware prevented cookies over HTTP; made configurable via `SESSION_HTTPS_ONLY` env var (defaults to false)
- **Admin panel hidden behind login** — Renamed to "System Overview", moved to public nav bar (visible without auth)
- **Voice monitoring lag** — Reduced voice recording interval from 60s to 300s, frontend live polling from 10s to 60s, live status refresh from 30s to 300s

### Docs

- **Upload Security Threat Model** — `docs/UPLOAD_SECURITY.md` with 5 attack surfaces, 15 existing mitigations documented with file references, 6 gaps identified, 30+ red-team test cases
- Slimmed `docs/CLAUDE.md` from 894 to ~186 lines; moved fix history here and known issues to `docs/KNOWN_ISSUES.md`
- Fixed factual drift: table count (7→36), cog count (14→20), core modules (12→18), Lua version (v1.3.0→v1.6.0), command count (63→80+), system status version (1.0.1→1.0.6)

---

## Detailed Fix History (Dec 2025)

### Fixed - Dec 14-17, 2025

- **Duplicate Player Entries in Rankings** - Player "olympus" appeared twice due to `GROUP BY player_guid, player_name`. Fixed to `GROUP BY player_guid` with `MAX(player_name)`. Files: session_stats_aggregator.py, session_graph_generator.py, session_view_handlers.py, session_data_service.py
- **Stats Command UnboundLocalError** - `!stats` crashed because `embed` variable was only created in cache MISS path. Fixed in leaderboard_cog.py
- **Find Player SQL Syntax Error** - `{ph}` placeholder instead of `?` in link_cog.py
- **Impossible Time Dead Values** - Players showing dead longer than played. Capped `time_dead` at `time_played` using `LEAST()` in SQL
- **Webhook Notification Security Hardening** (commit 3f15b1a)
- **Leaderboard Pagination & Session Graphs** - Fixed pagination, changed Denied Playtime graph to percentage
- **Incomplete local_stats Sync** - Added 7-day lookback window + `!sync_historical` command to prevent data loss during bot downtime

### Fixed - Dec 1, 2025

- **SSHMonitor Race Condition** - Disabled SSHMonitor auto-start; endstats_monitor now handles SSH + DB import + Discord posting as unified system
- **Channel Checks Silent Ignore** - Changed `is_public_channel()` / `is_admin_channel()` to silently return False
- **on_message Channel Filtering** - Uses `public_channels` as fallback when `bot_command_channels` not configured
- **Website Security Fixes** - HTML corruption, duplicate functions, SQL injection protection

### Fixed - Nov 2025

- **Gaming Session Detection Bug** - Use `WHERE round_id IN (session_ids_list)` instead of date filters
- **Player Duplication Bug** - Always `GROUP BY player_guid`, never by player_name
- **Duplicate Detection Bug** - Added `round_time` to duplicate check (not just map_name + round_number)
- **30-Minute vs 60-Minute Gap** - Changed all instances to 60 minutes

### Added - Nov 19, 2025

- **Achievement System** - Badge emojis for lifetime achievements. Files: player_badge_service.py, achievements_cog.py

---

### Added - Greatshot Enhancements

- **Cross-reference Phase 2-5** - Dramatically improved demo-to-stats matching
  - Multi-round matching: Handle R1+R2 in one demo file
  - Filename date extraction: Filter candidates by YYYY-MM-DD in filename
  - Player overlap validation: +20 confidence for 80%+ roster match
  - Stats comparison validation: Detect wrong matches via kill counts
  - **Result:** Match rate improved from 10-20% → 80-90%

- **Topshots API endpoints** - Leaderboards across all analyzed demos
  - `GET /api/greatshot/topshots/kills` - Demos with most total kills
  - `GET /api/greatshot/topshots/players` - Best individual performances
  - `GET /api/greatshot/topshots/accuracy` - Highest accuracy (min 10 kills)
  - `GET /api/greatshot/topshots/damage` - Most damage dealt
  - `GET /api/greatshot/topshots/multikills` - Best multi-kill highlights
  - Files: `website/backend/routers/greatshot_topshots.py`

### Changed - Greatshot

- **Cross-reference duration tolerance** - Increased from 5s to 30s
  - Accounts for warmup time in demos
  - Approximate tolerance: 15s → 60s
  - File: `website/backend/services/greatshot_crossref.py`

---

## [1.0.9] - 2026-02-08

### Security Fixes

- **CRITICAL: Added admin permission decorators** - Server control commands now require admin channel
  - `rcon`, `map_add`, `map_change`, `map_delete`, `kick`, `say` commands protected
  - File: `bot/cogs/server_control.py`

- **CRITICAL: Fixed file integrity verification crash** - Runtime AttributeError on every file check
  - Changed `tuple.get()` to index access `[0]`
  - File: `bot/automation/file_tracker.py`

- **HIGH: Fixed player GUID grouping** - Eliminated duplicate player entries in leaderboards
  - Changed 14 SQL queries from `GROUP BY player_name` to `GROUP BY player_guid`
  - Each player now appears once regardless of name changes
  - Files: `bot/cogs/leaderboard_cog.py`, `bot/services/session_view_handlers.py`

- **HIGH: Fixed XSS in website onclick handlers** - JavaScript context injection vulnerability
  - Changed `escapeHtml()` to `escapeJsString()` in 6 onclick attributes
  - Files: `website/js/awards.js`, `website/js/greatshot.js`

- **MEDIUM: Fixed SSH resource leak** - Connections not closed on exceptions
  - Added try/finally blocks to ensure cleanup
  - File: `bot/automation/ssh_handler.py`

- **MEDIUM: Sanitized error messages** - Database details no longer leaked to Discord
  - Added `sanitize_error_message()` to 8 error handlers
  - Files: `bot/cogs/matchup_cog.py`, `bot/cogs/analytics_cog.py`

- **MEDIUM: Fixed SQL limit injection** - Unvalidated limit parameter
  - Added validation (1-1000 range) with ValueError on invalid input
  - File: `bot/services/session_stats_aggregator.py`

### Added

- **Secrets management system** - Password rotation and generation tool
  - New tool: `tools/secrets_manager.py`
  - Generate passwords in format: `thunder-mountain-eagle1337`
  - Rotate database passwords, Discord tokens, SSH keys
  - Audit codebase for hardcoded secrets
  - Documentation: `docs/SECRETS_MANAGEMENT.md`
  - **Status**: Ready to use, NOT activated (passwords unchanged)

- **Security audit documentation**
  - Complete fix report: `docs/SECURITY_FIXES_2026-02-08.md`
  - Lists all 9 critical/high fixes applied
  - Testing recommendations and deployment checklist

### Changed

- **Admin channel configuration** - Added documentation to `.env.example`
  - Production: 822036093775249438
  - Bot-dev: 1424620551300710511, 1424620499975274496

### Fixed

- **Orphaned error log statement** - Removed misleading "Failed to post map summary" message
  - File: `bot/ultimate_bot.py` line 2284

### Documentation

- Added comprehensive security audit report
- Added secrets management usage guide
- Updated .env.example with admin channel IDs

---

## [1.0.8] - 2026-02-08

### Added

- **Greatshot highlight metadata enrichment** - Richer fragmovie scout data
  - Kill sequences with victim, weapon, headshot per kill
  - Victims list, weapons_used dict, headshot_weapons dict
  - Kill timing rhythm: kill_gaps_ms, avg_kill_gap_ms, fastest_kill_gap_ms
  - Attacker match stats (kills, deaths, KDR, damage, accuracy) on each highlight
  - New file: `greatshot/highlights/detectors.py` with 3 enrichment helpers

- **Player stats extraction from demos** - Match-level performance data
  - Extract player_stats from UDT matchStats.playerStats
  - Fallback to timeline-derived kills/deaths when UDT data unavailable
  - player_stats field added to AnalysisResult output
  - Files: `greatshot/scanner/api.py`, `greatshot/contracts/types.py`

- **Database cross-reference system** - Match demos to ET:Legacy stats rounds
  - NEW: `website/backend/services/greatshot_crossref.py`
  - Match by map (exact), duration (±5s), winner, scores
  - Confidence scoring: 30% map + 30% duration + 20% winner + 20% scores
  - Auto-crossref after analysis, store matched_round_id in metadata_json
  - Enrich with 16-field player stats from player_comprehensive_stats
  - Side-by-side comparison (demo kills vs DB kills/deaths/KDR/DPM)
  - GET /api/greatshot/{demo_id}/crossref endpoint
  - Files: `website/backend/routers/greatshot.py`, `website/backend/services/greatshot_jobs.py`

- **Frontend highlight detail expansion** - Rich scout-friendly UI
  - Kill sequence display (timestamp, victim, weapon, HS indicator)
  - Weapon badges with headshot weapon highlighting
  - Kill rhythm visualization (avg/fastest gap stats)
  - Attacker's overall match stats display
  - Database crossref panel: matched round, confidence, stats comparison table
  - Files: `website/js/greatshot.js`, `website/index.html`

- **Enhanced text reports** - Richer highlight metadata in reports
  - Show victims, weapons, kill rhythm in highlight listings
  - Player stats summary section (top 16 by kills)
  - File: `greatshot/scanner/report.py`

### Changed

- Highlight detection now passes player_stats for attacker_stats enrichment
- AnalysisResult.to_dict() now includes player_stats when available
- Greatshot jobs auto-crossref demos with ≥50% confidence

---

## [1.0.6] - 2026-02-07

### Added

- **Player analytics commands** - `!consistency`, `!map_stats`, `!playstyle`, `!awards`, `!fatigue`
  - New files: `bot/cogs/analytics_cog.py`, `bot/services/player_analytics_service.py`

- **Matchup analytics system** - `!matchup A vs B`, `!duo_perf`, `!nemesis`
  - Lineup vs lineup historical stats with confidence levels
  - Auto-records matchups when session results are saved
  - New files: `bot/cogs/matchup_cog.py`, `bot/services/matchup_analytics_service.py`
  - Database: `matchup_history` table with JSONB player stats

- **Map-based stopwatch scoring**
  - Session scores now count MAP wins, not round wins
  - `StopwatchScoringService.calculate_session_scores_with_teams()` for proper team-to-winner mapping
  - Full map breakdown with timing in `!last_session` embed
  - Tie handling: double fullhold = 1-1 (both teams defended)

- **Real-time team tracking**
  - Teams created on R1 import, updated as players join subsequent rounds
  - Supports 3v3 -> 4v4 -> 6v6 growth with correct team assignment
  - `gaming_session_id` column added to `session_teams` table

- **Lua webhook v1.6.0** - spawn/death tracking, safe gentity access (crash fix)
- **Proximity tracker v3** - crossfire detection, trade kill support
- **Endstats pagination view** - paginated round awards display
- **Round linker** - cross-references R1/R2 data with Lua webhook data
- **Server control cog** - RCON, server status, map management, player list
- **Website SPA overhaul** - sessions, matches, player profiles, leaderboards, admin panel, badges, proximity, season stats pages

### Fixed

- **Time dead calculation** - R2 `time_dead_ratio` was calculated against cumulative time; now uses `time_dead_minutes` directly (fixed ~15 min/session undercount)
- **GROUP BY player_name** in `player_analytics_service.py` - changed to `GROUP BY player_guid` with `MAX(player_name)` to prevent duplicate entries on name changes
- **Division by zero guard** in `matchup_analytics_service.py` - empty match list check before averaging
- **Surrender timing** - Lua webhook captures actual played time instead of full map duration from stats files

### Changed

- Lua webhook fields use `Lua_` prefix to distinguish from stats file data
- Website auth improvements and live-status updates
- API router and service layer updates for website

---

## [1.0.5] - 2026-01-25

### Added

- **Lua webhook v1.3.0** - pause event timestamps (`Lua_Pauses_JSON`), warmup end timestamp (`Lua_WarmupEnd`), timing legend in Discord embed
  - Database: `lua_pause_events` JSONB column

- **Lua webhook v1.2.0** - warmup phase tracking (`Lua_Warmup`, `Lua_WarmupStart`)
  - Database: `lua_warmup_seconds`, `lua_warmup_start_unix` columns

- **ET:Legacy server optimization** - CPU affinity, UDP buffer tuning

---

## [1.0.4] - 2026-01-22

### Added

- **Lua webhook real-time stats** - instant round notification from game server (~3s vs 60s SSH polling)
  - `stats_discord_webhook.lua` v1.1.0 on game server
  - Captures accurate timing, winner, team composition at round end
  - `lua_round_teams` table for cross-reference with stats file data
  - Debug timing logs comparing stats file vs Lua timing

### Fixed

- **Surrender timing bug** - stats files show full map duration on surrender; Lua captures actual played time
- **SSHHandler method name** - `list_files` -> `list_remote_files` in webhook file fetch

---

## [1.0.3] - 2026-01-14

### Added

- **EndStats processing** - parses `-endstats.txt` files for round awards and player VS stats
- **7 award categories** - Combat, Deaths & Mayhem, Skills, Weapons, Teamwork, Objectives, Timing
- **VS stats tracking** - player-vs-player kill/death records per round
- **Discord follow-up embeds** - awards posted automatically after round stats
- **3 new tables** - `round_awards`, `round_vs_stats`, `processed_endstats_files`

---

## [1.0.2] - 2025-12-04

### Added

- **WebSocket real-time push** - VPS notifies bot instantly when new stats files are written
- **Voice session logging** - track player voice channel activity
- **Round publisher service** - auto-post rich Discord embeds with all player stats after each round
- **Team suggestion commands** - `!suggest_teams`, `!balance_teams` for AI-powered team balancing

### Fixed

- SQL nosec comment appearing inside query string causing PostgreSQL syntax errors
- Command alias conflicts between team_builder and synergy_analytics cogs
- 12 queries using `{placeholders}` in regular strings instead of f-strings
- `kill_thie` -> `kill_thief` typo in session_embed_builder.py

---

## [1.0.1] - 2025-12-01

### Fixed

- **SSHMonitor race condition** - two monitoring systems competed for files, causing live Discord posting to fail. Disabled SSHMonitor auto-start; `endstats_monitor` now handles SSH + DB import + Discord posting as single system.
- **Channel permission checks** - silently return `False` instead of raising exceptions and sending error messages
- **on_message channel filtering** - uses `public_channels` config as fallback when `bot_command_channels` not set
- **Website HTML corruption** - fixed malformed document structure in `index.html`
- **Website JS duplicate functions** - fixed duplicate `loadLeaderboard()` declarations
- **Website SQL injection** - added `escape_like_pattern()` to API router

---

## [1.0.0] - 2025-11-20

### Added

- Achievement badge system (medic, engineer, sharpshooter, rambo, objective specialist)
- Custom display name system for linked Discord accounts
- Exact value labels on performance graphs
- Auto-posting shows all players with comprehensive stats

### Fixed

- Critical bug in `!list_players` command
- Codacy static analysis warnings

---

## [0.9.0] - 2025-11-18

Major production release. Migrated from SQLite to PostgreSQL.

### Added

- **6-layer data validation** - file integrity, duplicate prevention, schema validation, cross-field checks, transaction safety, DB constraints
- **Full automation** - SSH monitoring, auto-download, auto-import, auto-post
- **Voice-conditional SSH monitoring** - only checks when players in voice channels
- **Gaming session grouping** - 60-minute gap detection
- **Round 2 differential calculation** - subtracts R1 from cumulative R2 stats
- **PostgreSQL migration** - from SQLite to PostgreSQL 14
- **AI match predictions** - 4-factor algorithm (H2H, form, map performance, substitutions)
- **11 leaderboard categories** - K/D, DPM, accuracy, headshots, efficiency, etc.
- **Interactive account linking** - react with emojis to link Discord to game stats
- **Connection pooling** - asyncpg for high-performance async queries
- **TTL-based caching** - 5-minute cache for query results

### Fixed

- DPM calculations now use actual playtime instead of round duration
- Leaderboard queries properly filter R0 warmup rounds
- SSH monitor only checks last 24h on startup (not all historical files)
- Rate limiting, shell injection prevention, database SSL support

---

## [0.1.0] - 2025-10-15

### Added

- Initial release with basic Discord bot functionality
- SQLite database support
- Manual stats file import
- Player statistics commands (`!stats`, `!compare`)
- Basic leaderboard system
- Round and session tracking
- 53+ statistics tracked per player per round
