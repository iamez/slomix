# MASTER PLAN — Proximity Page Major Redesign (Map-First · Per-Player · Narrative+Numbers)

> **STEP 0 (executing agent, do first):** copy this file verbatim to
> `docs/PROXIMITY_REDESIGN_MASTER_PLAN.md` in the repo so it lives with the
> codebase, then create a feature branch (NEVER commit to `main`), e.g.
> `feat/proximity-redesign`. This plan file lives outside the repo; the
> `docs/` copy is the canonical executable artifact.

---

## Context — why this work

The `/proximity/` page is currently a **prototype**: it dumps ~10 sections of
metrics whose only purpose so far was to prove the Lua tracker works and the
stats can be tracked. The owner (a pro ET:Legacy player) wants these numbers
**displayed with context and interpretation** — storytelling **with** numbers,
"invisible value" (gravity / space-created / enabler / lurker), describing
*what happened* around events rather than judging plays good/bad.

The flagship gap: the heatmap is **global** (all players combined). The owner
wants a **per-player heatmap** so you can see exactly where each individual
player fights on each map.

Owner's authoritative scope decisions:
1. **Frontend:** build for **BOTH** legacy JS (production: `website/js/proximity.js` + `website/index.html` `#view-proximity`) **AND** React (`website/frontend/src/pages/Proximity.tsx`, canonical future). Python backend serves both.
2. **Heatmap:** multi-perspective per-player with toggle buttons — *kills-from*, *victims-die*, *player-dies*, *presence/movement*.
3. **Lua:** also plan a **separate, isolated, risky** Lua v9 workstream for a *true aim heatmap* (per-shot origin + view angles). Server runs Lua v8+, repo has v6.01 (DESYNC) — must SSH-pull & assess live Lua first; every server-touching step needs **explicit user approval**.
4. **Aggressiveness:** **full** visual redesign — new map-first information architecture, per-player as a central experience.

## Ground-truth corrections (verified — read before executing)

- **A2 (CRITICAL):** `GET /proximity/combat-positions/heatmap` (`website/backend/routers/proximity_positions.py:188-259`) has **NO** per-player GUID filter. The per-player heatmap **cannot** reuse it as-is — a new endpoint is required.
- **A1 (CRITICAL, live latent bug — verified):** `/proximity/hotzones` (`website/backend/routers/proximity_combat.py:166-169`) emits dict keys `x,y,count,kills` (SQL aliases `grid_x/grid_y` are NOT in the output dict). `renderHeatmap` (`website/js/proximity.js`) reads `h.kills` (line 938 — EXISTS) but the calibrated path reads `zone.grid_x`/`zone.grid_y` (lines 952-953 — UNDEFINED → `NaN` → `if (!Number.isFinite) continue`). Net effect: on the 20 **calibrated** maps (`worldBounds` truthy) **every hotzone is skipped and the function `return`s blank at line 971** — it does NOT reach the relative-grid fallback. The fallback (`proximity.js:974-996`) runs only for uncalibrated maps and *also* reads `h.grid_x` (still NaN). The main heatmap is therefore effectively broken everywhere. Confirmed by direct read of both files.
- **A3 (IMPORTANT):** `proximity_kill_outcome` does **not** store death position (dropped at parse: `proximity/parser/parser.py:326-340, 2134-2156`; not in schema `tools/schema_postgresql.sql:2618-2638`). Therefore *"where player dies"* must use `proximity_combat_position.victim_x/y` filtered by `victim_guid` (kills-by-enemy only; world/suicide deaths excluded — caption this in UI).
- Two incompatible heatmap contracts exist: legacy main heatmap = `combat_engagement` / GRID 256 / `{grid_x,grid_y,kills}`; combat panel + React = `proximity_combat_position` / GRID 512 / `{x,y,count}`. **Standardize the flagship on `proximity_combat_position` / 512 / `{x,y,count}`.**
- Lua: repo `proximity/lua/proximity_tracker.lua` is `version = "6.01"` (line 46, 4308 lines total); only stale snapshot is `docs/reference/live_sync_backups/20260219_153221/...`. A **fresh SSH pull is mandatory** before any Lua design. `et_WeaponFire` is at `proximity_tracker.lua:4026` (verified); `et_Damage:3611`, `et_Obituary:3736`. `et_WeaponFire` only counts shots — no origin/angles. **`viewangles` appears NOWHERE in the repo Lua (verified grep)** → its exact ETL 2.83.1 field binding MUST be validated against the live server Lua in Step 5.0; do not assume. Origin-capture precedent exists at `proximity_tracker.lua:589` (`safe_gentity_get(clientNum, "ps.origin")`).

## Verification status (independent re-check done before sign-off)

This plan's load-bearing claims were independently verified against the live tree. Result: **no hallucinated files/functions; A2/A3 confirmed true; helper, React, and proximity.js line refs accurate.** Corrections already folded in above: A1 description sharpened (blank on calibrated maps, not a fallback), Phase 2 simplified (reuse the existing `player_guid`/`player_guid_columns` params of `_build_proximity_where_clause` — A2 is purely "the heatmap endpoint doesn't pass them"), parser citations fixed (`_parse_combat_position_line:2261` ≠ `_import_combat_positions:2459`).

**Frontend-reality flag for the executing agent:** `website/backend/CLAUDE.md` describes the frontend as "React 19 … 25 pages". Do not be misled — `website/backend/main.py:360-361` (`static_dir = website`; `app.mount("/", StaticFiles(directory=static_dir, html=True))`) proves the served production site is the **legacy `website/` dir (legacy JS), NOT `website/frontend/dist`**. Legacy JS is correctness truth; React is the parallel canonical-future stack per the owner's scope decision #1.

---

## Phase 1 — Audit / Bugfix / Review (DO FIRST · gates everything)

Reuse the **Mandelbrot RCA** 3-layer structure from `docs/DEEP_RCA_PROXIMITY_REVIEW.md`. Produce `docs/PROXIMITY_REDESIGN_AUDIT_<YYYY-MM-DD>.md` with a findings table (CRITICAL/IMPORTANT/NIT + top-3).

- **Layer A — contract drift (FE↔API):** diff every proximity fetch in `website/js/proximity.js` and `website/frontend/src/api/client.ts` against router response shapes. Confirm/log A1, and React `HeatmapCanvas` reading `p.team` (`Proximity.tsx:136`) which the endpoint never returns (A4, NIT).
- **Layer B — schema-drift / INSERT coverage:** for every `migrations/*.sql` touching proximity tables, verify a writer exists in `proximity/parser/parser.py` (template: `*_guid_canonical` regression, migrations 035/036, commit `cdb7f51`). Formally document A3.
- **Layer C — code health:** `ruff` scoped to `website/backend/routers/proximity_*.py` + `proximity/parser/parser.py`; flag silent `.catch(()=>{})` in `proximity.js` and the V5 table-count silent-zero (A5, "A5" in the RCA doc).

**Checklist (executing agent fills status):** A1 (fixed via Phase 3), A2 (fixed via Phase 2), A3 (documented; Lua v9 only if world/suicide deaths wanted), A4 (Phase 3), A5 (add logging), A6 256-vs-512 (resolved by A1 fix), A7 verify `proximity/parser/parser.py` is the real `ProximityParserV4` (`git status` clean).

**Gate / verification (PostgreSQL `etlegacy`):**
```
SELECT COUNT(*), COUNT(DISTINCT attacker_guid), COUNT(DISTINCT map_name)
  FROM proximity_combat_position WHERE session_date >= CURRENT_DATE - 30;
SELECT COUNT(*), COUNT(DISTINCT player_guid)
  FROM player_track WHERE session_date >= CURRENT_DATE - 30;
SELECT map_name, COUNT(*) FROM proximity_combat_position GROUP BY 1 ORDER BY 2 DESC LIMIT 20;
```
Cross-check maps against the 20 calibrated in `website/assets/maps/proximity/map_transforms.json`. Phase 2 starts only after the audit doc exists and A1/A2 root causes are confirmed.

## Phase 2 — Backend: consolidated per-player heatmap endpoint

**Decision: NEW endpoint** (do not overload the live `/proximity/combat-positions/heatmap`). Add `GET /proximity/player-heatmap` in `website/backend/routers/proximity_positions.py` (after the existing handler ~`:259`; already wired via `proximity_router.py`).

**Contract:**
```
GET /proximity/player-heatmap
  map_name (REQUIRED, 400 if missing — mirror :203-204)
  mode     (REQUIRED) kills_from | victims_die | player_dies | presence
  player_guid (REQUIRED, accepts 8-char short or 32-char canonical)
  range_days=30, session_date?, round_number?, round_start_unix?, weapon_id?
  grid_size=512 (clamp 128..1024)
→ { status, map_name, mode, grid_size, player_guid, player_name,
    hotzones:[{x,y,count}], total, sampled, coverage? }
```
Response intentionally matches the existing `{x,y,count}` shape so React `HeatmapCanvas` (`Proximity.tsx:98-198`) and the new legacy renderer reuse it.

**SQL per mode** — build WHERE via existing `_build_proximity_where_clause` (`website/backend/routers/proximity_helpers.py:136`). **IMPORTANT (verified): this helper ALREADY accepts `player_guid` + `player_guid_columns` params (helpers.py:143-144, 179-191) with built-in OR-across-columns logic.** Do NOT hand-append `AND attacker_guid=$N`; pass the per-player filter through these params (the existing combat-positions endpoint at `proximity_positions.py:208-210` simply doesn't pass them — that is the entire A2 gap). Only `weapon_id` stays as a manual extra clause. `grid_size` is a clamped int, safe to interpolate (mirror `512.0` at `proximity_positions.py:239`):
- `kills_from`: `FLOOR(attacker_x/{g})`,`FLOOR(attacker_y/{g})` from `proximity_combat_position`; pass `player_guid=<canonical>, player_guid_columns=["attacker_guid"]` `[+ manual AND weapon_id=$M]`.
- `victims_die`: same but `victim_x/victim_y`; still `player_guid_columns=["attacker_guid"]`.
- `player_dies`: `victim_x/victim_y`; `player_guid_columns=["victim_guid"]`; add `"coverage":"kills_only"` (UI captions world/suicide excluded).
- `presence`: `player_track.path` JSONB via `LATERAL jsonb_array_elements(pt.path) WITH ORDINALITY`, filter `pt.player_guid=$N`, **server-side stride downsample**: first `SELECT COALESCE(SUM(sample_count),0) FROM player_track {where} AND player_guid=$N`, `stride=max(1,ceil(total/8000))`, keep rows where `ord % stride = 0`, set `sampled=stride>1`. Never ship raw paths. Recommend (Phase 7 migration, not applied here): `idx_player_track (player_guid,map_name,session_date)`, `idx_proximity_combat_position (attacker_guid,map_name,session_date)` and `(victim_guid,map_name,session_date)`.

**GUID resolution:** reuse `_resolve_name_for_guid` (`proximity_helpers.py:244`), `_load_scoped_guid_name_map` (`:264`), `shared/guid_utils.short_guid`; resolve short→32-char canonical before binding.

**Verify:** `python -c "import website.backend.routers.proximity_positions"`; `python -c "import website.backend.main"`; start `cd website && uvicorn backend.main:app --port 8000`; curl all 4 modes + invalid-param 400s; cross-check `total` vs raw `COUNT(*)`. Add `tests/unit/test_proximity_player_heatmap.py` (param validation, mode routing, stride math, GUID resolution; mock db like sibling proximity tests).

## Phase 3 — Per-player multi-perspective heatmap (BOTH stacks)

**Shared UX:** page-level player autocomplete + map select (intersect `map_transforms.json` keys) + scope selects (reuse existing `#proximity-*-select`) + 4 toggle buttons (`kills_from|victims_die|player_dies|presence`) + intensity slider (reuse `proximityVizState.heatIntensity`) + objective-zone overlay (reuse `drawObjectiveZones` / `objective_zones.json`). Color by mode (amber / rose / blue / cyan-low-alpha). Caption: sample count + scope + `kills_only` note for deaths.

**Legacy (production — truth):** in `website/index.html` `#view-proximity` add a "Player Combat Map" section: `<canvas id="proximity-player-heatmap">` (model on `#proximity-heatmap` wrap ~`index.html:2201-2211`), player `<select>`, 4 `data-pmode` buttons, caption div. In `website/js/proximity.js` add `renderPlayerHeatmap(payload)` modeled on `renderHeatmap` (`:898-997`) **reusing** `ensureMapTransformConfig`/`getMapTransformEntry`/`getWorldBounds`(`:531-541`)/`preloadMapImage`/`worldToCanvasPoint`(`:543-552`)/`worldRadiusToCanvas`(`:554-560`)/`PROXIMITY_GRID_SIZE=512`/`drawObjectiveZones` — but consume the **new `{x,y,count}`** contract (`maxCount=max(count)`, `worldX=(z.x+0.5)*512`). This also fixes A1 for the flagship. Wire via existing scoped-fetch (`proximity.js:1605-1680`); extend `proximityVizState` with selected player + `playerHeatmapMode`.

**React (canonical future):** add `getPlayerHeatmap` to `website/frontend/src/api/client.ts` (model `getCombatHeatmap:238-245`), `usePlayerHeatmap` to `hooks.ts` (model `useCombatHeatmap:471-477`, `enabled:!!mapName&&!!playerGuid`), `PlayerHeatmapPanel` modeled on `CombatHeatmapPanel` (`Proximity.tsx:1003`) reusing `HeatmapCanvas` (`:98-198`); fix A4 (drop `p.team` branch `:136-143` or color by mode). Mount as hero in `Proximity()` render (`:1317`).

**Verify:** legacy via `http://localhost:8000/#/proximity` — all 4 toggles × 2 maps × scoped/unscoped, canvas on calibrated bg, empty-state. React: `cd website/frontend && npx tsc --noEmit` (typecheck only — **NOT** correctness proof; legacy is truth).

## Phase 4 — Full visual redesign / map-first IA (narrative + numbers)

Reframe current 10 sections + storytelling endpoints into a 6-section, map-first, player-centric flow. Player selector is a **page-level** control feeding Hero + Story Strip + Map Context (shared selected-player state).

| New section | From | Endpoints (reuse) | Framing |
|---|---|---|---|
| 1. HERO Player Combat Map (NEW) | Phase 3, full-bleed | `/proximity/player-heatmap` | "Where {player} fights on {map}" — 4 lenses, no verdict |
| 2. Player Story Strip | 8 KPI→5 + storytelling one-liners | `/storytelling/player-narratives`, `/proximity/player/{guid}/radar`, `/storytelling/{gravity,space-created,enabler,lurker-profile}` | sentence per KPI ("pulls 2.3 enemies of attention — top 15%") |
| 3. Map Context | global heatmap (FIX A1) + danger-zones + objective zones | `/proximity/combat-positions/heatmap`, `/danger-zones`, `objective_zones.json` | "this map's blood & objective pull" |
| 4. Engagements & Trades | Combat Events + Trades + event-detail canvas | `/proximity/trades`, `/proximity/events`, kill-lines | narrative trade timeline |
| 5. Roles & Classes | Class Summary + 7 leaderboards → 3 contextual | `/proximity/leaderboards`, storytelling synergy | "who creates space, who finishes" |
| 6. Round Replay / Teams | KEEP routes `#/proximity/round/{id}` & `/teams` | existing | unchanged deep-dive |
| CUT | timeline sparkline, metric-guide modal (→ inline InfoTips), 4 redundant KPIs, 4 redundant leaderboards | — | reduce noise |

**Legacy:** recompose `#view-proximity` (`index.html:~2006-2450`) and `loadProximityView()` (`proximity.js:~1939`) render order into the 6 sections; retire/redirect the broken old `renderHeatmap` main panel to a global `{x,y,count}` call (also closes A1/A6). **React:** recompose render (`Proximity.tsx:1317`) into 6 sections, add a top player context provider; pull narrative copy from `proximity-glossary.ts` (reuse `InfoTip`/`METRICS` pattern `Proximity.tsx:264-267`). Leave `ProximityPlayer/Teams/Replay.tsx` route targets intact.

**Verify:** legacy manual walkthrough (6 sections render, player cascade, no console errors); backend import + curl for every reused endpoint. No React-build gating.

## Phase 5 — Lua v9 true-aim workstream (ISOLATED · RISKY · GATED · parallel to 1–4)

- **5.0 [REQUIRES EXPLICIT USER APPROVAL] — SSH pull & diff FIRST.** Read-only pull (no server writes) per `docs/GAMESERVER_LIVE_LUA_MAP.md`: `ssh -i ~/.ssh/etlegacy_bot -p 48101 et@91.185.207.163 'cat .../legacy/luascripts/proximity_tracker.lua'` → save to `docs/reference/live_sync_backups/<ts>/`. Diff vs repo v6.01; document live `version`, new/changed sections, callback signatures, parser gaps in `docs/PROXIMITY_LUA_V8_DRIFT_<date>.md`. Hard gate: design proceeds only after user reviews the drift doc.
- **5.1 design `et_WeaponFire` enhancement** (`proximity_tracker.lua:4026-4045`): per-shot origin (reuse `safe_gentity_get(clientNum,"ps.origin")` `:589`) + view angles (`ps.viewangles` — **validate exact binding against the live Lua**, no precedent in repo). Emit new `SHOT_FIRED` line `time;guid;weapon;ox;oy;oz;yaw;pitch`, behind config flag + sampling/rate-limit (high frequency). Bump `version`; update `tests/unit/test_proximity_lua_v5_sections_guard.py` & `test_proximity_lua_live_gating_guard.py`.
- **5.2 parser + schema + migration (local only):** `ShotFired` dataclass (model `class KillOutcome` parser.py:326) + `_parse_shot_fired_line` (model `_parse_combat_position_line` **parser.py:2261**) + `_import_shots_fired` (model `_import_combat_positions` **parser.py:2459-2505**) in `proximity/parser/parser.py`; keep `_table_has_column`/`_append_round_link_columns`/`_append_canonical_guid_columns` guards → backward compatible. New table `proximity_shot_fired` (model DDL on `proximity_combat_position` `tools/schema_postgresql.sql:2273+`) + idempotent `migrations/0NN_add_proximity_shot_fired.sql` (035-style) + add to `tools/schema_postgresql.sql`. Backend: extend `/proximity/player-heatmap` with 5th `mode=aim` once data exists.
- **5.3 [REQUIRES EXPLICIT USER APPROVAL] — deploy** (Lua v9 to server + prod migration). Document runbook (`docs/DEPLOYMENT_RUNBOOK.md`, `docs/GAMESERVER_LIVE_LUA_MAP.md`); executing agent **stops and asks**, never deploys autonomously.

**Verify (pre-deploy, local):** parser unit test with synthetic v9 fixture + backward-compat assertion; migration idempotent (apply twice on scratch DB); `python -c "import proximity.parser.parser"`.

## Phase 6 — End-to-end verification (truth = legacy JS + Python import + curl; React build ≠ proof)

1. Imports: `website.backend.main`, `proximity.parser.parser`, `website.backend.routers.proximity_positions`.
2. Curl matrix on `localhost:8000`: `/proximity/player-heatmap` (4 modes × scoped/unscoped × valid/invalid) + every endpoint reused by the 6 sections.
3. Legacy manual: `/#/proximity`, `#/proximity/player/{guid}`, `#/proximity/round/{id}`, `/teams` — all sections, cascade, calibrated backgrounds, no console errors.
4. PostgreSQL validation: row counts + `total`-vs-COUNT cross-checks; presence downsample ≤ raw `SUM(sample_count)`.
5. Tests: `pytest tests/unit -k proximity` minimally (full ~2989-suite if time); add Phase 2 & 5 tests; don't break unrelated tests.
6. **Live-session validation:** final acceptance needs a real session flowing parser→DB→endpoint→legacy page; flag for the owner to validate narrative framing against a known live session/player.

## Phase 7 — Sequencing & gates

Critical path: **1 → 2 → 3 → 4 → 6**. Phase 2 gated on Phase 1 audit doc + A1/A2 confirmed; Phase 3 gated on Phase 2 curl-green. Phase 5.0–5.2 run **fully parallel** to 1–4 (disjoint files: `proximity/lua`, `proximity/parser`, `migrations` vs `website/`); Phase 1 Layer C parallel to A/B. **Hard user-approval stops:** 5.0 (SSH pull) and 5.3 (server deploy + prod migration) — never autonomous. Lua workstream must not block the redesign shipping.

---

## Critical files

- `website/backend/routers/proximity_positions.py` — add `GET /proximity/player-heatmap` (model on existing combat-heatmap `:188-259`).
- `website/js/proximity.js` — add `renderPlayerHeatmap` (reuse `worldToCanvasPoint`/`getWorldBounds`/`renderHeatmap` `:898-997`); recompose `loadProximityView` `:~1939` for new IA; fixes A1.
- `website/index.html` — `#view-proximity` `:~2006-2450`: restructure into 6-section map-first IA + player-heatmap canvas/controls.
- `website/frontend/src/pages/Proximity.tsx` — canonical React redesign; reuse `HeatmapCanvas` `:98-198` + `CombatHeatmapPanel` `:1003`; recompose render `:1317`; fix A4.
- `proximity/parser/parser.py` — Lua v9: `ShotFired` (model `KillOutcome:326`) + `_parse_shot_fired_line` (model `_parse_combat_position_line:2261`) + `_import_shots_fired` (model `_import_combat_positions:2459-2505`); documents A3 (`KillOutcome:326`, `_parse_kill_outcome_line:~2134`).
- Reference (mostly read-only): `website/backend/routers/proximity_helpers.py` (`_build_proximity_where_clause:136`, GUID resolvers `:244/:264`, `ProximityQueryBuilder:25`), `website/assets/maps/proximity/{map_transforms,objective_zones}.json`, `proximity/lua/proximity_tracker.lua:4026` (`et_WeaponFire`) & `:589` (`ps.origin`), `docs/DEEP_RCA_PROXIMITY_REVIEW.md`, `tools/schema_postgresql.sql` (`player_track:1936-1968`, `proximity_combat_position:2271+`, `proximity_kill_outcome:2618+`).

---

## How to launch the executing agent (paste this prompt verbatim)

Open a fresh Claude Code session at repo root `/home/samba/share/slomix_discord` and paste:

```
Execute the proximity redesign master plan.

PLAN: read the full plan at /home/samba/.claude/plans/pozdravljen-rabil-bi-da-jolly-reef.md
(absolute path). It is authoritative and already independently verified — follow it exactly.

STEP 0 (first): copy that plan verbatim to docs/PROXIMITY_REDESIGN_MASTER_PLAN.md, then
create + switch to feature branch feat/proximity-redesign. NEVER commit to main.

EXECUTION RULES
- Follow the 7 phases in plan order. Respect gates: Phase 2 only after the Phase 1 audit
  doc exists and A1/A2 are confirmed; Phase 3 only after Phase 2 curl-smoke passes.
- HARD STOPS — stop and ask the user for explicit approval, never autonomous:
  (a) Phase 5.0 any SSH to the game server (et@...:48101);
  (b) Phase 5.3 any server deploy or production DB migration.
  Also: never restart slomix-bot/slomix-web (or any service) without asking;
  never use `npm run build` as proof of anything.
- Correctness truth = legacy JS rendering + `python -c "import ..."` + curl smoke on
  localhost:8000 + psql validation. React tsc/build is NOT correctness proof.
- Ignore website/backend/CLAUDE.md calling React "the frontend": main.py:360-361 serves
  the legacy website/ dir — that is production. React is the parallel future stack only.
- Verified facts — do NOT re-investigate: A2 = the existing /proximity/combat-positions/
  heatmap simply never passes player_guid/player_guid_columns to
  _build_proximity_where_clause (the helper ALREADY supports them, helpers.py:143-144,
  179-191) → fix is a NEW /proximity/player-heatmap endpoint, not editing the old one.
  A1 = the global heatmap renders BLANK on all 20 calibrated maps (renderHeatmap reads
  grid_x/grid_y which the endpoint does not emit). A3 = proximity_kill_outcome has no
  position columns; use proximity_combat_position.victim_* filtered by victim_guid for
  "where player dies". Lua repo is v6.01 but the server runs v8+ — do NOT edit
  proximity/lua/* before the gated SSH pull.
- Use Explore subagents for Phase-1 audit discovery; reuse the Mandelbrot RCA structure
  in docs/DEEP_RCA_PROXIMITY_REVIEW.md. Use a Plan subagent for sub-phase design.
- Packaging: ONE feature branch, stacked commits per phase, ONE bundled PR at the end
  (no micro-PRs). Conventional Commits, scope `proximity`. Never commit secrets/logs/DB.

ENVIRONMENT
- Backend: cd website && uvicorn backend.main:app --port 8000
- DB: PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy
- Tests: pytest tests/unit -k proximity   (do not break the full ~2989-test suite)
- SSH key (gated use only): ~/.ssh/etlegacy_bot

DELIVERABLES per phase: P1 -> docs/PROXIMITY_REDESIGN_AUDIT_<date>.md; P2 -> new endpoint
+ unit tests; P3 -> per-player heatmap on legacy + React; P4 -> 6-section map-first IA on
both stacks; P5 -> (gated) Lua v8 drift doc + local v9 design; P6 -> verification report.
After each phase, summarize changes + verification output, then continue to the next
non-gated phase.

Begin with STEP 0, then Phase 1.
```
