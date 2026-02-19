# AI Handoff: Home Graphs + Availability + retro_viz (2026-02-18)

## Status
- Scope requested in prompt is implemented in code.
- One validation gap remains: `tests/unit/test_availability_router.py` is skipped locally due missing `httpx` runtime dependency.
- No DB schema migration was required.

## What Was Changed

### 1) Home: Map Distribution empty chart
#### Root cause found
- Data exists in DB for 14/30/90 windows.
- The chart could render as a silent blank in frontend states; map key quality (path-like names/extensions) also caused messy grouping.

#### Implemented changes
- Backend map key normalization and stable aggregation:
  - `website/backend/routers/api.py`
  - Added `_normalize_map_name(...)`
  - Clean map names (`maps/...`, backslashes, `.bsp/.pk3/.arena`, blanks)
  - Return sorted `map_distribution` object
- Frontend explicit map chart states:
  - `website/js/app.js`
  - Added map state machine: `loading`, `ready`, `empty`, `error`
  - Empty copy now explicit: `No data yet. No rounds recorded in this period.`
  - Error copy now explicit: `Could not load map distribution right now.`

#### Tests
- `tests/unit/test_stats_trends_map_distribution.py`
  - schema contract + normalization merge behavior
  - empty map behavior returns `{}` (not crash)

---

### 2) Availability: cannot start poll / set availability
#### Root cause found
- `daily_polls` table is empty in the target DB (`0` rows), so page correctly shows no poll.
- Existing design is automation-first (Discord poll cog), but UI had no robust fallback flow.

#### Implemented changes
- Added backend availability router with usable fallback flow:
  - `website/backend/routers/availability.py`
  - `GET /api/availability/access` -> auth/admin flags
  - `POST /api/availability/create-today` -> admin-only idempotent create
  - `GET /api/availability/my-responses` -> today/tomorrow user state
  - `POST /api/availability/respond` -> upsert response; auto-create today/tomorrow poll if missing
- Added/updated frontend availability UX:
  - `website/js/availability.js`
  - `Create Today (Fallback)` admin action
  - today/tomorrow response controls for logged-in users
  - explicit load/empty/error/retry states
  - immediate refresh of today/history/my-response after writes
- Added Availability view elements:
  - `website/index.html`

#### Tests
- `tests/unit/test_availability_router.py`
  - admin gating
  - idempotent create-today behavior
  - auto-create + upsert response behavior for tomorrow

---

### 3) retro_viz: remove Round 0 from Combat Overview UX
#### Root cause found
- `round_number=0` rows are intentionally stored as match summaries and leaked into recent-round picker.

#### Implemented changes
- Backend:
  - `website/backend/routers/api.py`
  - `/rounds/recent` now excludes round 0 (`WHERE r.round_number > 0`)
  - Added `round_label` serialization (`R1`, `R2`, `Match Summary`, `R?`)
- Frontend:
  - `website/js/retro-viz.js`
  - Defensive filter to skip round 0 in picker payload
  - Use `round_label` where available
  - If round 0 is loaded directly, show `Match Summary` instead of `R0`

#### Tests
- `tests/unit/test_retro_viz_round_filtering.py`
  - verifies round-0 SQL exclusion for recent list
  - verifies direct round-0 payload label is `Match Summary`

## DB Findings Captured During Validation
- Last 90d rounds:
  - total `488`
  - round 1/2: `351`
  - round 0: `137`
  - round 1/2 with map names: `351`
- Map data exists in all home windows:
  - 14d: `40` rounds (1/2), `6` distinct maps
  - 30d: `137` rounds (1/2), `9` distinct maps
  - 90d: `351` rounds (1/2), `12` distinct maps
- Availability:
  - `daily_polls` total rows: `0`
- Overall rounds:
  - total `1697`
  - round 0 rows `538`
  - round 1/2 rows `1159`

## Commands Run (targeted)
- `pytest -q tests/unit/test_stats_trends_map_distribution.py tests/unit/test_retro_viz_round_filtering.py tests/unit/test_availability_router.py`
  - result: `5 passed, 1 skipped`
  - skip reason: missing `httpx`
- `node --check website/js/app.js`
- `node --check website/js/availability.js`
- `node --check website/js/retro-viz.js`
- `python3 -m py_compile website/backend/routers/api.py website/backend/routers/availability.py`

## Risks / Follow-ups For Next Agent
1. Availability admin config
- Admin fallback depends on env values:
  - `WEBSITE_ADMIN_DISCORD_IDS` or `ADMIN_DISCORD_IDS` or `OWNER_USER_ID`
- If none are set, nobody can use create-today fallback.
- Patch option: document/env-wire in `website/.env.example` and startup warning log if admin set is empty.

2. Automation still disabled by config in many environments
- Poll scheduler (bot cog) may not post if `AVAILABILITY_POLL_ENABLED` and channel config are unset.
- Patch option: add a health endpoint/admin panel indicator showing scheduler config + last poll date.

3. Map alias consolidation
- Normalization strips path/extensions only; semantic aliases remain (`supply` vs `etl_supply`).
- Patch option: add optional alias map (config table or static dict) before chart aggregation.

4. Round 0 technical debt not removed at source
- UI/API now avoid confusion, but round 0 generation still exists in ingestion.
- Patch option: move match-summary rows to dedicated summary table or mark with explicit type column and separate endpoints.

5. Test dependency gap
- Install `httpx` in local/CI test env to execute availability router tests rather than skip.

## Suggested Next-Agent Checklist
1. Run `pip install httpx itsdangerous` in test env and re-run `pytest -q tests/unit/test_availability_router.py`.
2. Do manual UI pass:
   - Home -> Community Insights -> 14/30/90 map chart
   - Availability -> create today (admin), respond today/tomorrow, refresh persistence
   - Retro Viz -> confirm no `R0` in picker
3. Split focused commit(s) if needed (worktree has broad unrelated changes).

