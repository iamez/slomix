# Local Changes Log - 2026-02-03

This document records code changes already applied in this workspace on February 3, 2026. The intent is to document what changed so we can revert later if needed.

**Summary**
- Team tracking now ignores spectators and handles session_teams schema variability safely.
- Team detection seeds from earliest true Round 1 by timestamp instead of round_id.
- Stopwatch scoring logic now uses **map‑winner by time** (Superboyy‑aligned) to avoid 11:11 ties.
- Round pairing order for stopwatch scoring uses round_date + round_time for reliability with repeated maps.
- R2 defender/winner data is inherited from closest R1 when missing, during import.
- stats_discord_webhook.lua uses safer gamestate fallbacks and bumps version.
- Session management and achievement queries now use the PostgreSQL db_adapter (SQLite removed from runtime path).
- Endstats output now uses paginated embeds (Map view + Round view) with navigation buttons.
- Website last-session widget now uses team-aware scoring (map wins), shows uncounted maps, and renders a map breakdown aligned with bot logic.
- Website last-session API now exposes team rosters + per-player stats and validation checks for UI grouping.
- Added map thumbnail assets + Axis/Allies icons for visual map breakdowns on the website.
- Added additional chart widgets for team comparison, player scatter, time alive/dead, and damage in/out.
- Added more charts: DPM timeline, top-player radar, damage efficiency, selfkill heatmap, and team utility mix.

**Files Changed**
- bot/core/team_manager.py
- bot/core/endstats_pagination_view.py
- bot/services/session_data_service.py
- bot/services/stopwatch_scoring_service.py
- bot/ultimate_bot.py
- vps_scripts/stats_discord_webhook.lua
- website/index.html
- website/js/app.js
- website/js/proximity.js
- website/README.md
- docs/SL0MIX_SPA_API_CONTRACT_2026-02-03.md
- docs/codexreport-2026-02-03.md
- docs/codexreport-2026-02-03_full-audit.md
- scripts/smoke_pipeline.py
- scripts/smoke_team_consistency.py
- scripts/system_smoke_tests.sh
- bot/services/timing_comparison_service.py
- bot/services/timing_debug_service.py
- bot/services/round_publisher_service.py
- bot/community_stats_parser.py
- tests/unit/test_stats_parser.py
- bot/services/session_graph_generator.py
- bot/cogs/last_session_cog.py
- docs/SCORING_NOTE_2026-02-03.md
- bot/services/session_stats_aggregator.py
- bot/services/session_embed_builder.py
- postgresql_database_manager.py
- bot/schema.sql
- database/create_unified_database.py
- migrations/006_add_full_selfkills.sql
- bot/services/session_view_handlers.py
- scripts/backfill_full_selfkills.py
- bot/core/achievement_system.py
- bot/cogs/session_management_cog.py
- website/backend/routers/api.py
- website/js/sessions.js
- website/assets/maps/map_generic.svg
- website/assets/maps/supply.svg
- website/assets/maps/etl_adlernest.svg
- website/assets/maps/etl_sp_delivery.svg
- website/assets/maps/etl_battery.svg
- website/assets/maps/etl_oasis.svg
- website/assets/maps/etl_frostbite.svg
- website/assets/maps/etl_goldrush.svg
- website/assets/maps/etl_brewdog.svg
- website/assets/maps/etl_erdenberg.svg
- website/assets/maps/etl_bradendorf.svg
- website/assets/maps/etl_escape2.svg
- website/assets/icons/axis.svg
- website/assets/icons/allies.svg

**Details By File**
- bot/core/team_manager.py
  - Added session_teams table safety check and cached column discovery.
  - Insert and update logic now adapts if gaming_session_id or color columns are absent.
  - Spectator and unknown team values are ignored in team updates.
  - Team seeding prefers earliest true R1 by timestamp (round_date + round_time).

- bot/services/session_data_service.py
  - session_teams lookup now matches dates by SUBSTR(session_start_date, 1, 10).
  - If session_teams missing, auto-detect via TeamManager before falling back.

- bot/services/stopwatch_scoring_service.py
  - calculate_map_score now uses **map‑winner by time** (1 point per map to winner).
  - Tie‑break: equal completion times go to Round 1 attackers.
  - Added fallback to infer `defender_team` from `winner_team` + time when header looks stale.
  - Map winners now prefer R2 `winner_team` from header (time-based fallback).
  - Added scoring debug fields + log line per map (winner side, team sides, source).
  - Round pairing order uses round_date and round_time instead of map_name ordering.
  - Team side mapping now uses all R1 players and safer fallback logic.

- bot/cogs/team_cog.py
  - Session score now uses team-aware map scoring with session round IDs (fixes side-swap errors).
  - Map breakdown now reads team-aware points when available.

- bot/cogs/last_session_cog.py
  - Added `!last_session debug` view showing per-map scoring source and side mapping.

- bot/ultimate_bot.py
  - Round insert now includes defender_team, winner_team, and round_outcome if columns exist.
  - If R2 header data missing, inherits defender/winner from latest R1 in same gaming_session.
  - Added cached discovery of rounds table columns for safe inserts.

- vps_scripts/stats_discord_webhook.lua
  - Version bumped to 1.4.3.
  - GS_WARMUP fallback set to -1 to avoid playing-state collision.
  - GS_INTERMISSION fallback added (3) if constant missing.

- docs/codexreport-2026-02-03.md
  - Added project maturity notes (bot working prototype, website/proximity early prototypes).

- docs/codexreport-2026-02-03_full-audit.md
  - Added explicit project maturity notes.
  - Clarified webhook-triggered stats download flow.
  - Explicitly noted time accuracy as the key tension affecting stats correctness.
  - Recorded accepted risk regarding repo-contained SSH/public key access.

- scripts/smoke_pipeline.py
  - New smoke test to parse a real R1/R2 stats pair and compute stopwatch scoring.
  - Added sys.path injection for reliable local imports.

- scripts/smoke_team_consistency.py
  - New read-only SQLite team consistency check by session_date.

- scripts/system_smoke_tests.sh
  - New system smoke test runner (parsing, endstats, security checks, optional DB checks).

- bot/ultimate_bot.py
  - Webhook-triggered stats file matching now prefers the file closest in time to Lua round_end_unix.
  - Added warnings when closest match is far from webhook timestamp to catch mismatches.

- bot/services/timing_comparison_service.py
  - More robust round datetime parsing (supports multiple stored formats).
  - Lua matching now prefers round_end_unix/round_start_unix over captured_at to reduce timezone/match drift.

- bot/services/timing_debug_service.py
  - Replaced match_id join with fuzzy Lua matching using map/round/time window.
  - Added resilient datetime parsing and match confidence indicator in debug output.

- bot/community_stats_parser.py
  - parse_time_to_seconds now supports decimal minutes (e.g., "20.00" → 1200s).
  - Round 2 parser now keeps `winner_team` from header for map‑winner scoring.

- bot/services/stopwatch_scoring_service.py
  - parse_time_to_seconds now supports decimal minutes for correct scoring on mixed formats.

- bot/services/timing_comparison_service.py
  - _parse_time_to_seconds now supports decimal minutes for accurate stats duration parsing.

- bot/services/timing_debug_service.py
  - _parse_time_to_seconds now supports decimal minutes for accurate stats duration parsing.

- bot/services/round_publisher_service.py
  - Uses Lua override metadata to display corrected playtime in public embeds.

- tests/unit/test_stats_parser.py
  - Added test cases for decimal minute parsing ("20.00", "5.25").

- bot/services/session_graph_generator.py
  - Added Useful Kills (UK) and Self Kills to the Advanced Metrics graphs.
  - Expanded Advanced Metrics layout to 3x2 to keep existing metrics.

- bot/cogs/last_session_cog.py
  - Updated Advanced Metrics embed description to include new graph metrics.
  - Replaced cumulative endstats summary with paginated endstats embeds.
  - Added Map/Round endstats page builders with per-round awards (awards-only display).
  - Added `!endstats_audit` command to summarize endstats coverage for the latest session.
  - Removed VS stats from endstats pagination output (awards-only display).

- bot/core/endstats_pagination_view.py
  - New Discord UI view for endstats pagination (first/prev/next/last + map/round toggle).
  - Adds per-page footer metadata (view mode + page counter) and author-only interactions.
  - Added interaction response fallback to avoid Unknown interaction (404) on slow or repeated clicks.

- bot/cogs/matchup_cog.py
  - Removed `h2h` alias to avoid command registration conflict with team head-to-head.

- docs/SCORING_NOTE_2026-02-03.md
  - Documented suspected stopwatch scoring rule mismatch (map-win scoring).
  - Included proposed change and revert guidance (no code changes applied yet).

- bot/services/session_stats_aggregator.py
  - Aggregates self_kills and full_selfkills (full_selfkills optional if column exists).
  - Added helper to detect presence of full_selfkills column.

- bot/services/session_embed_builder.py
  - Adds SK and FSK counts to the !last_session overview player lines.
  - Adds footer note when FSK is unavailable due to missing column.

- bot/services/session_graph_generator.py
  - Adds full_selfkills to graphs (grouped with self_kills in Advanced Metrics).

- bot/cogs/last_session_cog.py
  - Updated graph description to mention Full Selfkills.
  - Passes FSK availability to session overview embed.

- bot/services/session_view_handlers.py
  - Added column detection helper for optional FSK column.
  - Added SK/FSK to combat and support views.

- scripts/backfill_full_selfkills.py
  - New backfill script to populate full_selfkills from stats files.

- scripts/backfill_endstats.py
  - New DB-only backfill script for endstats (round_awards + round_vs_stats).
  - Skips files already tracked in processed_endstats_files and avoids duplicates.

- docs/PLAN_FASTDL_ASSIST_2026-02-03.md
  - Updated to Discord-attachment approach (no hosting/ports).

- docs/MISSION_LIVE_SESSION_2026-02-03.md
  - Live session checklist for logs, Discord outputs, and restart steps.

**Runs (2026-02-03)**
- Backfill endstats for 2026-02-02: files_processed=17, awards_inserted=450, vs_inserted=306,
  skipped_processed=1, skipped_existing=1, rounds_missing=0, parse_failed=0

- bot/core/achievement_system.py
  - Switched achievement queries to use db_adapter (PostgreSQL path) instead of aiosqlite.
  - Uses ensure_player_name_alias for compatibility without SQLite connections.

- website/backend/routers/api.py
  - `/api/stats/last-session` now returns a `scoring` payload from `StopwatchScoringService`.
  - Uses session_teams rosters to map sides to persistent teams.
  - Includes map-level `counted` and `note` fields for R1-only maps.

- website/js/sessions.js
  - Last Session widget now prefers `scoring` payload over Allies/Axis.
  - Session score card shows team names and uncounted map note.
  - Round outcomes chart uses team map wins + ties + uncounted.
  - Adds Map Breakdown list aligned with team-aware scoring and times.
  - Adds team roster panels grouped by team with per-player session stats.
  - Displays stat check warnings (kill/death mismatch, unassigned players).
  - Adds additional chart widgets (team comparison, player scatter, time alive/dead, damage given/received).

- website/assets/maps/*.svg
  - Added placeholder map thumbnails for key ETL maps plus a generic fallback.

- website/assets/icons/*.svg
  - Added lightweight Axis/Allies-style UI icons (visual only).

- website/backend/routers/api.py
  - `/api/stats/last-session` now returns `teams`, `unassigned_players`, and `stats_checks`.
  - Fixed indentation error in achievement milestone checks (bot startup crash).

- bot/cogs/session_management_cog.py
  - Switched session_start insert to use db_adapter (PostgreSQL) with RETURNING id.
  - Insert now targets rounds.round_date/round_time/round_status (Postgres schema columns).
  - Removed direct SQLite connection usage from session control commands.

- bot/ultimate_bot.py
  - Added webhook endstats retry scheduling to fix "round not found" race.
  - Keeps in-memory lock and retries round linking with exponential backoff.
  - Centralized endstats storage/publish logic to reduce duplication.
  - Endstats monitor now bypasses FileTracker for endstats and uses processed_endstats_files for dedupe.
  - Added startup lookback check for endstats processing (prevents very old backfill on restart).
  - Added live achievement posting after successful round import.
  - Postgres import now resolves round_id after parsing so live round posting can work.

- bot/cogs/session_cog.py
  - Implemented `!session <date> graphs` using SessionGraphGenerator (previously stubbed).

- vps_scripts/stats_discord_webhook.lua
  - Replaced gentity `pers.cl_guid` reads with userinfo-based GUID lookup.
  - Prevents runtime errors on round end and surrender vote tracking.
  - Uploaded to server: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`.

- website/index.html
  - Added Proximity navigation and prototype view section.
  - Marked Home and Proximity views as prototypes with banner metadata.
  - Added prototype banner slots for dynamic rendering.

- website/js/app.js
  - Wired Proximity view to view router and loader.
  - Added per-view prototype banner system driven by `data-prototype` attributes.

- website/js/proximity.js
  - New prototype module to render proximity placeholders and optional API data.
  - Honors `ready` status from proximity API and displays a prototype message when not ready.

- website/README.md
  - Documented Proximity prototype view and API endpoints as prototype stubs.

- docs/SL0MIX_SPA_API_CONTRACT_2026-02-03.md
  - New SPA API contract and feature map with proximity endpoints.
  - Expanded proximity endpoints to include `status`, `ready`, and `message` fields.

- website/backend/routers/api.py
  - Added prototype proximity endpoints (`/proximity/*`) returning safe placeholder payloads.
  - Introduced consistent `status`, `ready`, and `message` fields for prototype readiness.

- docs/codexreport-2026-02-03.md
  - Added follow-up notes on prototype banner system and proximity API stubs.
  - Logged the 2026-02-02 session map-winner analysis (TeamB 7 vs TeamA 4).
  - Recorded Superboyy color mapping for 2026-02-02 (TeamA=Blue, TeamB=Red).
  - Added header sanity check: defenderteam stays 1 in raw files even when players swap sides.

**Server Observations (Read-Only)**
- Config load: `legacy3.config` includes `luascripts/stats_discord_webhook.lua` in `lua_modules`.
- Other configs (legacy1/legacy6/etc.) do NOT include the webhook module.
- Server log errors prior to patch:
  - `et_RunFrame error ... tried to get invalid gentity field "pers.cl_guid"`
- Reload confirmation (user-provided): Lua modules loaded, including `stats_discord_webhook.lua`.

- postgresql_database_manager.py
  - Added full_selfkills column to schema and migrations.
  - Inserts full_selfkills into player_comprehensive_stats.

- bot/schema.sql
  - Added full_selfkills column to player_comprehensive_stats.

- database/create_unified_database.py
  - Added full_selfkills column to player_comprehensive_stats.

- migrations/006_add_full_selfkills.sql
  - New migration to add full_selfkills to player_comprehensive_stats.
  - Applied on Postgres (2026-02-03): `ALTER TABLE` + comment added.

- scripts/backfill_full_selfkills.py
  - Ran on Postgres (2026-02-03) with `PYTHONPATH=. python3 ... --db-type postgres`.
  - Result: Files processed 114, rows updated 726, rounds missing 3857.
  - Many historical `round-2` files lacked matching round-1, so backfill skipped those rounds.
  - Re-ran for last 12 weeks only (cutoff 2025-11-11) using `/tmp/backfill_12w`.
  - Result: Files processed 114, rows updated 726, rounds missing 340.
  - Still saw some missing Round 1 warnings for a few Round 2 files.

- Missing Round 1 audit (2026-02-03)
  - Local last-12-weeks scan: 225 Round 2 files missing matching Round 1 in `local_stats`.
  - Server gamestats listing (`/home/et/.etlegacy/legacy/gamestats`) checked for those Round 1 filenames.
  - Result: 0 found on server; all 225 still missing remotely.

- Missing rounds audit (last 3 weeks, cutoff 2026-01-13)
  - Missing R2 (R1 present, R2 missing): 48 maps.
  - Missing R1 (R2 present, R1 missing): 47 maps.
  - Server gamestats check: 0 of the missing R1/R2 files were found on server.
  - Lists saved:
    - `/tmp/missing_r2_3w.txt`
    - `/tmp/missing_r1_3w.txt`
    - `/tmp/missing_r2_3w_present_on_remote.txt`
    - `/tmp/missing_r1_3w_present_on_remote.txt`

**Additional Fixes (2026-02-03)**
- Website graphs now join by `round_id` and accept `gaming_session_id` to avoid multi-session date mixing.
- Website last-session now filters matches by `session_ids` and returns `gaming_session_id`.
- Website recent matches now map teams via session_teams when available (round_id-based).
- Awards list `days` filter uses parameterized interval.
- LinkCog now supports feature-flagged `!select` in-memory cache (off by default).
- Voice session auto-summary supports optional embed generation (off by default).
- TeamManager map performance implemented behind feature flag (off by default).
- PredictionEngine can optionally resolve H2H winners from session_results (env flag).
- Drafted secrets centralization plan: `docs/SECRETS_CENTRALIZATION_PLAN_2026-02-03.md` (no behavior changes).
- Added Lua reference comparison doc: `docs/LUA_REF_SCRIPT_COMPARISON_2026-02-03.md`.
- Updated `stats_discord_webhook.lua` with Oksii-inspired delivery: temp-file curl, retries, gametimes fallback, and de-dupe guard (v1.5.0).
- Gametimes fallback payload now includes `server_ip`, `server_port`, and `match_id` metadata.
- Added hardening plan doc: `docs/LUA_WEBHOOK_HARDENING_PLAN_2026-02-03.md`.
  - Addendum: those counts were based on strict timestamp pairing (same match_id).
  - Using the actual pairing logic (same map, R1 before R2 within 45 minutes):
    - R2 without matching R1: 1 file
      - `2026-01-15-232241-sw_goldrush_te-round-2.txt`
    - R1 without matching R2: 2 files
      - `2026-01-13-000542-te_escape2-round-1.txt`
      - `2026-01-15-232658-et_brewdog-round-1.txt`

- scripts/audit_round_pairs.py
  - New helper that audits missing R1/R2 using the SAME pairing logic as the parser.
  - Avoids false "missing" reports from strict timestamp matching.

- bot/core/round_linker.py
  - Shared resolver to link external metadata (Lua, endstats, proximity) to rounds via time proximity.
  - Prevents timestamp mismatch issues when R1/R2 times differ.

- migrations/007_add_round_id_to_lua_round_teams.sql
  - Adds `round_id` column + index to `lua_round_teams` for reliable joins.
  - Applied on Postgres (2026-02-03): `ALTER TABLE` + index + comment.

- bot/ultimate_bot.py
  - Lua metadata override now resolves round_id via round_linker instead of match_id.
  - Stores `round_id` in `lua_round_teams` when possible; updates later when stats import completes.
  - Adds `_link_lua_round_teams` to attach lua rows to rounds after import.

- bot/services/timing_debug_service.py
  - Prefers direct `round_id` match for Lua data when available.

- bot/services/timing_comparison_service.py
  - Prefers direct `round_id` match for Lua data when available.

- scripts/backfill_lua_round_ids.py
  - New backfill helper to populate `lua_round_teams.round_id` for existing rows.
  - Ran on Postgres (2026-02-03): scanned=1, updated=0.

- bot/core/achievement_system.py
  - Fixed player_links lookup to use `player_guid` + `player_name` (Postgres schema).
  - Resolves `UndefinedColumnError: et_name does not exist`.

- vps_scripts/stats_discord_webhook.lua
  - Added intermission-flag round end detection (mirrors c0rnp0rn7.lua).
  - Adds fallback round-start detection in `et_RunFrame` to avoid missing transitions.
  - Deployed to game server: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua` (2026-02-03).

- bot/services/stopwatch_scoring_service.py
  - Added safeguards: unscored maps when team-side inference is ambiguous.
  - Added explicit "R1 only (not counted)" map entries when only Round 1 exists.
  - Added `counted` + `note` metadata for map breakdown display.

- bot/services/session_embed_builder.py
  - Shows uncounted maps in map breakdown with a clear note (e.g., R1 only).

- bot/cogs/last_session_cog.py
  - Scoring debug now shows `counted` + `note` per map for transparency.
  - Fixed team_rosters extraction to handle session_teams dict format (`guids` list).

- bot/automation/ssh_handler.py
  - `list_remote_files` now supports extension filtering for gametimes JSON ingestion.

- bot/config.py
  - Added gametimes configuration (`GAMETIMES_ENABLED`, `REMOTE_GAMETIMES_PATH`, `LOCAL_GAMETIMES_PATH`,
    `GAMETIMES_STARTUP_LOOKBACK_HOURS`).

- bot/ultimate_bot.py
  - Added gametimes index tracking (local `.processed_gametimes.txt`).
  - Added gametimes ingestion pipeline: parse JSON payload, store Lua metadata, and trigger stats fetch.
  - Refactored Lua embed parsing into reusable helpers (shared by Discord webhook and gametimes fallback).
  - Added extra gametimes logging (counts + per-file download + stats fetch triggers).

- scripts/backfill_gametimes.py
  - New helper to backfill local gametimes JSON files into `lua_round_teams`.

- .env
  - Added gametimes ingestion config (enabled + remote/local paths).

- Ops
  - Created `/home/et/.etlegacy/legacy/gametimes` on the game server (2026-02-03).
  - Backfill attempted locally; no gametime files present yet.
  - Removed outdated Lua script copy: `/home/et/.etlegacy/legacy/luascripts/stats_discord_webhook.lua`.
  - Verified live server now loads `stats_discord_webhook.lua` v1.5.1 on map change.

- Proximity prototype
  - Created `proximity/sample_engagements.txt` via `proximity/test_standalone.py --create-sample`.
  - Ran parse-only test to verify parser output (1 engagement, 2 tracks).
  - Enabled proximity ingestion in `.env` and added remote/local paths.
  - Adjusted `PROXIMITY_REMOTE_PATH` to match install output dir: `/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity`.
  - Proximity Lua: added map/round refresh fallback, output guard delay support, log gating, and objective stats reset.
  - Proximity Lua now refreshes map/round on round start to prevent empty map/round in logs.
  - Proximity Cog: auto-import now respects `PROXIMITY_AUTO_IMPORT`; manual scan bypasses.
  - Deployed updated proximity_tracker.lua to game server (v4.2).
  - Verified server deployment: `/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity_tracker.lua` header shows v4.2.
  - Created Postgres backup: `backups/proximity_preinsert_2026-02-04.dump`.
  - Verified proximity tables exist in Postgres.
  - Added `proximity_objective_focus` table and parser import.
  - Added ProximityCog SSH fetch of `_engagements.txt` files into `local_proximity`.
  - Parser now accepts optional `round_start_unix` / `round_end_unix` header fields.
  - Added optional `OBJECTIVE_FOCUS` section parsing (safe to ignore if absent).
  - Updated proximity output format docs with new header fields + optional section.
  - Updated proximity Lua to v4.2 with:
    - output guard + optional delay
    - unix round timestamps in header
    - string length hardening
    - team-aware GUID/name cache
    - optional objective focus aggregation
    - normalized output_dir and resolved-path logging
  - Deployed `proximity_tracker.lua` to server and wired into `legacy3.config`.
  - Created `/home/et/.etlegacy/legacy/proximity` output dir on server.
  - Created `/home/et/etlegacy-v2.83.1-x86_64/legacy/proximity` output dir on server (matches resolved path).
  - Added `proximity_objective_focus` table to `proximity/schema/schema.sql` to keep schema in sync.
  - Added round_start_unix / round_end_unix columns + new unique constraints to proximity schema (migration file added).
  - Parser now conditionally inserts round_start_unix / round_end_unix when columns exist.
  - Added objective coordinates for supply, sw_goldrush_te, and bremen_b3 from Oksii config.
  - Uploaded updated `proximity_tracker.lua` (objective configs + radius update) to server install path.
  - Added placeholder objective entries for etl_adlernest, etl_sp_delivery, and radar (Lua config).
  - Added `proximity/objective_coords_template.json` + `scripts/objective_coords_to_lua.py` helper.
  - Added proximity migration file: `proximity/schema/migrations/2026-02-04_round_start_unix.sql`.
  - Applied proximity migration on Postgres (round_start_unix columns + new unique constraints).
  - Re-uploaded `proximity_tracker.lua` after adding map placeholders.
  - Added `proximity/map_rotation.txt` from server rotation.
  - Added `scripts/sync_objective_placeholders.py` to sync map rotation into template.
  - Synced objective template to include all rotation maps.
  - Added `scripts/update_proximity_objectives_from_json.py` to rebuild Lua objectives block.
  - Added Lua init objective config summary (count + missing preview).
  - Added `!proximity_objectives` command (admin) to show configured vs missing maps.
  - Added `scripts/rcon_command.py` helper and attempted `lua_restart` (timed out).
  - Added Omni-bot config template `docs/OMNIBOT_CONFIG.cfg` and deployed to server.
  - Added `scripts/omnibot_toggle.py` to enable/disable bots via RCON.
  - Added bot-only round labeling: `is_bot_round`, `bot_player_count`, `human_player_count`.
  - Added migration `migrations/008_add_bot_round_flags.sql` and applied to Postgres.
  - Parser now detects Omni-bot names via `[BOT]` prefix (override via `BOT_NAME_REGEX`).
  - Added verification helper script: `scripts/verify_proximity_schema.py`.

- vps_scripts/stats_discord_webhook.lua
  - Reduced Discord embed size (removed human-readable team fields and WarmupEnd, shortened description).
  - Bumped Lua webhook footer version to `v1.5.1`.
  - Deployed to server: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua` (2026-02-03).

**Rationale**
- Team splits were inconsistent because spectators or unknown team values were being treated as valid teams.
- Seeding from earliest round_id can mis-seed when import order differs from actual play order.
- Stopwatch scoring logic was mismatched with docs/TEAM_AND_SCORING.md guidance.
- Round pairing needed to be time-ordered for repeated maps in a session.
- R2 header data in stats files can be missing, which breaks scoring unless inherited.
- Lua gamestate constants are inconsistent across ET:Legacy builds, so fallbacks help reliability.

**Revert Guidance**
- If using git, check the current status first with `git status`.
- To revert a specific file, use `git restore <path>`.
- Files to consider for revert are listed in the Files Changed section above.

**Notes**
- Database migration 006 was applied to Postgres to add `full_selfkills`.
- Postgres backfill ran from local_stats; see counts above.
- These updates were applied locally in this workspace and to the Postgres DB.
