# Session Report — Admin Atlas + Website Reliability
Date: 2026-02-04

This report summarizes the work completed to improve the Admin Atlas experience, expand season data, fix date‑type errors, and align website stats with bot output. It is written as a single “what changed and why” snapshot so we can reference it later when debugging or onboarding.

---

## 1) Admin Atlas UX Improvements

**Goal:** Make the atlas usable for onboarding by making details readable and enabling full‑screen viewing.

Changes:
- Added **Fullscreen mode** to both atlas views.
  - Full System Atlas and Lua Atlas now support a full‑screen overlay.
  - `Esc` exits fullscreen.
  - Added floating **“Exit Fullscreen”** buttons.
- Added **slide‑out details panel** (drawer style).
  - Clicking any node now opens a full‑size ELI5 panel to the right.
  - “Collapse” button hides the drawer.
  - “Details” toggle in the atlas toolbar re‑opens the drawer.
- **Mouse‑wheel zoom disabled** in atlas maps to prevent accidental zoom.
  - Zoom only via `+` / `-` buttons.
- Expanded nodes now span more space for readability (2 columns on large screens).

Files updated:
- `website/index.html`
- `website/js/admin-panel.js`

---

## 1.1) Core Topology Layout (Atlas)

**Goal:** Make the “center of gravity” obvious: game server on the left, database in the middle, bot/website on the right.

Changes:
- Added a **Core Topology** group to the Full System Atlas.
- Custom layout renders the three primary nodes in a single row.
- Added flow lines between the three nodes to reinforce left → center → right.
- Added new detail cards for each core node.

Files updated:
- `website/index.html`
- `website/js/admin-panel.js`

---

## 2) Season & Homepage Data Expansion

**Goal:** Make the homepage season tile meaningful and provide summary stats.

Changes:
- Added `seasons/current/summary` API endpoint with season totals:
  - rounds, players, sessions, maps, kills, active days, average rounds/day, top map.
- Expanded `seasons/current` endpoint:
  - start date, end date, next season name + start date.
- Added richer **season leaders** (kills, DPM, XP, gibs, objectives, time alive/dead).
- Expanded the **Current Season** box on homepage:
  - Start/end, next season, season totals, top map, activity summary.

Files updated:
- `website/backend/routers/api.py`
- `website/js/season-stats.js`
- `website/js/sessions.js`
- `website/index.html`
- `website/js/app.js`

---

## 2.1) Current Season Panel Default Expanded

**Goal:** Show season data without needing to click expand.

Change:
- Season details panel now renders **expanded by default**.

File updated:
- `website/index.html`

---

## 3) Overview Stats & Date‑Type Fixes

**Goal:** Fix `asyncpg` errors caused by passing `date` objects into text fields.

Fixes:
- Converted date parameters to **string format (`YYYY-MM-DD`)** in:
  - `/stats/overview`
  - `/stats/leaderboard`
  - `/stats/quick-leaders`
  - `/seasons/current/leaders`
- Normalized `rounds_since` / `rounds_latest` values to date strings to prevent UI confusion.

Impact:
- Prevents `TypeError: expected str, got date`.
- Fixes homepage load issues and missing stats.

Files updated:
- `website/backend/routers/api.py`

Note:
- The web service must be restarted after deployment to pick up these changes.

---

## 3.1) Parameter Binding Safety (AsyncPG)

**Goal:** Avoid asyncpg type mismatches without breaking timestamp inserts.

Change:
- Removed blanket date → string normalization in the PostgreSQL adapter.
- Instead, date filters are now explicit in SQL (`SUBSTR(... )` + `::text`)
  so the DB driver receives the correct parameter type.

Impact:
- Prevents `expected str, got date` **and** avoids new `toordinal` errors
  when inserting timestamps (monitoring services).

File updated:
- `bot/core/database_adapter.py`

---

## 3.2) Date Comparisons Standardized (Text Columns)

**Goal:** Avoid asyncpg type errors when `round_date`/`session_date` are stored as TEXT.

Change:
- Replaced date‑range checks with **string‑safe** comparisons:
  `SUBSTR(round_date, 1, 10) >= CAST($1 AS TEXT)` and `<= CAST($2 AS TEXT)`.
- Applied the same pattern across overview, activity calendar, current season summary,
  season leaders, leaderboard, and quick‑leaders queries.

Impact:
- Fixes “no data” in season widgets when `round_date` includes a time suffix.
- Eliminates asyncpg date casting errors for TEXT date columns.

Impact:
- Fixes errors like `str object has no attribute toordinal` and ensures date filtering works with TEXT columns.

File updated:
- `website/backend/routers/api.py`

---

## 3.3) Activity History Queries (Timestamp Cast)

**Goal:** Fix server/voice activity history endpoints that passed timestamps as strings.

Change:
- Added `CAST($1 AS TIMESTAMP)` in:
  - `/server-activity/history`
  - `/voice-activity/history`

Impact:
- Prevents `expected a datetime.date or datetime.datetime instance, got 'str'`
  in activity history queries.

File updated:
- `website/backend/routers/api.py`

---

## 3.4) Monitoring Service Wiring (Populate History)

**Goal:** Ensure server/voice activity history actually gets recorded.

Changes:
- Added monitoring config keys:
  - `MONITORING_ENABLED`
  - `SERVER_HOST`, `SERVER_PORT`
  - `MONITORING_SERVER_INTERVAL_SECONDS` (default 300)
  - `MONITORING_VOICE_INTERVAL_SECONDS` (default 60)
- Started `MonitoringService` on bot startup (`on_ready`).
- Separated monitoring loops for server and voice so their intervals can differ.
- Added immediate snapshot on start so history appears quickly after restart.

Impact:
- Historical activity should begin populating as soon as the bot runs.

Files updated:
- `bot/config.py`
- `bot/services/monitoring_service.py`
- `bot/ultimate_bot.py`

---

## 3.5) Session Map Thumbnails (Fallback Text)

**Goal:** Avoid the generic “flower” thumbnail when a map has no asset.

Change:
- Map breakdown cards now show a readable text badge when a map SVG is missing
  instead of the generic placeholder.

File updated:
- `website/js/sessions.js`

---

## 3.6) Quick Leaders Date Casting + Session Fallbacks

**Goal:** Fix `toordinal` / date‑type errors and ensure quick leaders work even when `rounds` joins fail.

Changes:
- Quick leaders now compare dates using `CAST(SUBSTR(... ) AS DATE)` and pass actual `date` params.
- Added **session_id‑only fallback** for DPM/session to avoid dependency on `rounds` table joins.
- Kept session_date fallback for XP when `round_date` isn’t available.

Impact:
- Eliminates `xp_query_failed` / `dpm_query_failed` errors on homepage.
- Restores Quick Leaders even when only session‑level data exists.

File updated:
- `website/backend/routers/api.py`

---

## 3.7) Overview Stats — Legacy Column Fallbacks

**Goal:** Prevent homepage totals from going to zero when `round_date` or `rounds` table is missing.

Changes:
- Added fallback checks that use `session_date` in `player_comprehensive_stats` if `round_date` is missing.
- Added `sessions` table fallback if `rounds` table is not present.

Impact:
- Prevents `0` totals caused by schema differences across environments.
- Keeps homepage overview numbers populated after restarts or schema drift.

File updated:
- `website/backend/routers/api.py`

---

## 3.8) Overview + Season Summary — Sessions Table Fallback When Rounds Are Empty

**Goal:** Avoid “all zero” stats when the `rounds` table exists but is empty, while data lives in `sessions`.

Changes:
- `stats/overview` now checks for `sessions` table if `rounds` exists but is empty.
- `seasons/current/summary` now retries using `sessions` when round counts are zero.
- `activity-calendar` now falls back to `sessions` if round-based activity returns no rows.

Impact:
- Restores homepage + season widgets even with mixed schema deployments.

File updated:
- `website/backend/routers/api.py`

---

## 3.9) Season Leaders — Session Date Fallback

**Goal:** Populate season leader tiles even when `round_date` is missing but `session_date` exists.

Changes:
- Reworked season‑leader queries to retry using `session_date` when all leader queries return empty.
- Preserves existing `round_date` behavior when data is present.

Impact:
- Season leaders now populate in older schemas that only track `session_date`.

File updated:
- `website/backend/routers/api.py`

---

## 4.1) Admin Atlas — Guided Flow Steps (Onboarding)

**Goal:** Make the full atlas easier to understand for non‑coders by highlighting the core data path in order.

Changes:
- Added **Guided Flow** chips (1–6) that spotlight the end‑to‑end pipeline:
  players → Lua → files → ingest/parse → PostgreSQL → Discord/Website.
- Clicking a step dims everything else and highlights the relevant nodes + flow lines.
- The story panel updates with ELI5 copy for each step.

Files updated:
- `website/index.html`
- `website/js/admin-panel.js`

---

## 4.2) Admin Atlas — Flow View + Group Controls + Legend

**Goal:** Reduce atlas overwhelm and make the data pipeline visible at a glance.

Changes:
- Added a **Flow** tab that filters to the core data pipeline groups only.
- Added **Group Controls** (Collapse All, Expand Flow, Expand All).
- Added a **legend** explaining line colors (core, stats, awards, webhook, timing, web, ops).
- Auto‑fit after tab/preset changes for easier navigation.

Files updated:
- `website/index.html`
- `website/js/admin-panel.js`

---

## 5.1) Homepage Quick Leaders — Empty Result Fallbacks

**Goal:** Prevent blank “Top XP / Top DPM” widgets when `round_date` joins are empty.

Changes:
- Quick leaders now **retry** with `session_date` if initial queries return zero rows.
- DPM/session now retries with a **session_id‑only** aggregation if round joins fail or return empty.

Impact:
- Quick Leaders should populate even when the schema only has `session_date` or missing round IDs.

File updated:
- `website/backend/routers/api.py`

---

## 5.2) Homepage Stat Cards — Clarity + Emphasis

**Goal:** Make the home stat row easier to scan and highlight “most active” players.

Changes:
- Added `stat-card` styling for consistent spacing and typography.
- Added emphasis styles for **Most Active (All‑time / 14d)** cards.
- Kept “Since <date>” and 14‑day sublabels tighter and clearer.

Files updated:
- `website/index.html`

---

## 5.3) Monitoring History — Auto-Create Tables

**Goal:** Ensure server/voice history tables exist so monitoring writes do not fail silently.

Changes:
- Monitoring service now auto‑creates `server_status_history` and `voice_status_history` if missing.
- Adds indexes on `recorded_at` for efficient history queries.

Impact:
- History recording will start working immediately after bot restart, even on fresh DBs.

File updated:
- `bot/services/monitoring_service.py`

---

## 4) Maps & Weapons UI Upgrade (Foundational)

**Goal:** Make Maps/Weapons pages readable and useful for non‑coders.

Changes:
- Maps page now uses `/stats/maps` (richer data) and shows:
  - Most played, fastest avg, longest avg, and nade‑spam highlights.
  - New sort controls (most played, fastest, longest, last played, nade spam).
  - Per‑map cards with avg time, last played, unique players, DPM, and explosives.
- Weapons page now includes:
  - Hall of Fame panel (top player per iconic weapon).
  - Period toggles (all‑time/season/30d/7d).
  - Category filtering (rifles/smgs/heavy/sidearms).

Files updated:
- `website/backend/routers/api.py`
- `website/index.html`
- `website/js/matches.js`

---

## 5) Recent Matches UX (Session Grouping)

**Goal:** Make it obvious which rounds belong to the same session.

Changes:
- Added `gaming_session_id` to recent match payload.
- Added session‑colored dot + label in the Recent Matches widget.

Files updated:
- `website/backend/services/website_session_data_service.py`
- `website/js/leaderboard.js`

---

## 5.1) Recent Matches Fallback Details

**Goal:** Show useful info even when score data is missing.

Changes:
- Added winner + duration fallback line when `score_display` isn’t available.

File updated:
- `website/js/leaderboard.js`

---

## 6) Sessions List — Legal Rounds Only

**Goal:** Ensure sessions list uses only valid R1/R2 rounds.

Changes:
- `GET /sessions` now filters to `round_number IN (1,2)` and legal status.
- Session date uses `SUBSTR(round_date, 1, 10)` to avoid time suffix parsing errors.

File updated:
- `website/backend/routers/api.py`

---

## 6.1) Sessions Cards — Missing Round Indicator

**Goal:** Make incomplete sessions obvious (e.g., missing R2).

Changes:
- Added “Missing Round” badge when session has an odd number of rounds.
- Added Session ID badge for quick grouping.

File updated:
- `website/js/sessions.js`

---

## 4) Home Page “Most Active Players”

**Goal:** Move most‑active players to the top row for fast visibility.

Changes:
- Added **Most Active (All‑time)** and **Most Active (14d)** widgets in the top stats row.
- Data driven by `/stats/overview` endpoint.

Files updated:
- `website/index.html`
- `website/js/app.js`

---

## 5) Quick Leaders (Homepage)

**Goal:** Make quick leaders show the correct data and avoid duplicate names.

Changes:
- Added `guid` to leaderboard and quick‑leaders responses.
- Homepage now uses GUID when present, reducing duplicates.
- Quick leaders now show:
  - **Top XP (last 7 days)**
  - **Top DPM per session (last 7 days)**
- Error list added for API debugging.

Files updated:
- `website/backend/routers/api.py`
- `website/js/leaderboard.js`

---

## 6) Alias / Player Identity Unification

**Goal:** One GUID = one player, even if they changed names.

Changes:
- Leaderboards group by GUID.
- Player profile endpoints resolve to GUID when possible.
- Charts and recent matches use GUIDs instead of names.

Files updated:
- `website/backend/routers/api.py`
- `website/js/player-profile.js`

---

## 7) Session Scoring Improvements

**Goal:** Match the bot’s `!last_session` scoring logic and surface warnings.

Changes:
- Added scoring helper used by `/stats/last-session`.
- Added `/stats/session-score/{date}` endpoint for non‑latest sessions.
- Included scoring, team rosters, and warnings in `/sessions/{date}` and `get_session_details`.
- Added scoring warnings and debug payload.

Files updated:
- `website/backend/routers/api.py`

---

## 8) Admin Documentation Additions

**Goal:** Make the project onboardable even for non‑coders.

Changes:
- Added/expanded Admin Atlas details and narrative storytelling.
- Expanded development story timeline, system walk‑through, and ELI5 labels.

Files updated:
- `website/js/admin-panel.js`
- `website/index.html`

---

## Known Follow‑Ups

Items that still require attention:
1. **Restart web service** after backend changes (needed for new endpoints and date‑fixes).
2. **Time dead / time denied** values still need investigation (raw Lua values vs processed).
3. **Alias system** may still need manual linking cleanup for players like “squaze”.
4. **Recent matches**: ensure only legal rounds + include score display everywhere.
5. **Quick leaders** validation: confirm 7‑day DPM is per session (not per round).

---

## File Inventory (Major Touchpoints)

Backend:
- `website/backend/routers/api.py`
- `website/backend/services/website_session_data_service.py`

Frontend:
- `website/index.html`
- `website/js/app.js`
- `website/js/admin-panel.js`
- `website/js/season-stats.js`
- `website/js/leaderboard.js`
- `website/js/player-profile.js`
- `website/js/sessions.js`

---

## Quick Summary (TL;DR)

- Admin Atlas now supports **fullscreen + slide‑out details**.
- Homepage season info is **richer + expandable**.
- Date‑type errors fixed (string dates now passed to queries).
- Quick leaders / leaderboards are **GUID‑aware** to avoid duplicates.
- New endpoints added to align website with bot scoring.

---

## 9) Display Name Unification + History Indicators

**Goal:** Reduce duplicate player names and make activity history status obvious.

Changes:
- Enhanced `resolve_display_name` to prefer `player_links.display_name`, then aliases, then latest stats.
- Applied display name resolution to:
  - Overview “Most Active” (all‑time + 14d)
  - Leaderboards
  - Quick Leaders
  - Season Leaders
  - Weapons Hall of Fame
- Aligned homepage + session filters to include `round_status = 'substitution'` as legal.
- Added “History: collecting / N samples” indicators for server + voice activity charts.
- Hardened overview + season summary queries with safer fallbacks (no full-zero UI if one query fails).
- Widened Admin Atlas layout and highlighted core topology center node.
- Recent matches now tolerate missing `round_id` in stats by falling back to round_date/map/round_number joins.
- Quick Leaders now retries with schema fallbacks (session_date + round_date joins) instead of failing hard.
- Quick Leaders suppresses error banners when fallback succeeds.
- Atlas details panel now expands wider in fullscreen for easier reading.
- Admin Atlas auto‑status now updates core topology nodes (game server, postgres, bot/web) and fixes live-status mapping.

Files updated:
- `website/backend/routers/api.py`
- `website/index.html`
- `website/js/live-status.js`
