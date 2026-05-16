# Proximity Lua v9 True-Aim — Phase 5.1/5.2 Design (LOCAL, implemented)

**Date:** 2026-05-16 · **Branch:** `feat/proximity-redesign`
**Gate status:** 5.0 done (no drift). 5.1/5.2 implemented LOCAL-ONLY. **5.3 (server deploy + prod migration) remains an un-started HARD STOP.**

## What "true-aim" adds
Per-shot **shooter origin + view angles** (where someone *aimed from*, not just where engagements resolved). Enables an `aim` heatmap lens distinct from `kills_from`/`presence`.

## 5.1 — Lua (`proximity/lua/proximity_tracker.lua`)
- `version` `6.01 → 6.02` (additive; on-wire version, not literally "9" — avoids confusing version/live-gating logic. "v9" is the workstream name).
- New `features.shot_fired = false` — **DEFAULT OFF**. Production behaviour is byte-unchanged until explicitly enabled. This is the core backward-compat guarantee.
- `config.shot_fired_sample_rate = 1` — emit every Nth shot (rate-limit; `et_WeaponFire` is high-frequency).
- `et_WeaponFire` (after the existing shot counter, never before it): when `isFeatureEnabled("shot_fired")` and sample gate passes, capture `ps.origin` (proven precedent, `getPlayerPos`/line ~589) and `ps.viewangles`, append `{time,guid,weapon,ox,oy,oz,yaw,pitch}` to `tracker.shot_fired`.
- New `# SHOT_FIRED` output section (gated `isFeatureEnabled("shot_fired") and #tracker.shot_fired>0`); `tracker.shot_fired`/`shot_fired_seq` reset with the other per-round buffers.
- ⚠️ **`ps.viewangles` binding is UNPROVEN from static code** — absent everywhere in repo+live Lua (Phase 5.0). Guarded defensively (nil / non-3-tuple → `0,0`, never errors, never blocks the shot-count path). **MUST be runtime-validated on a live server before 5.3 deploy** (fire a shot, confirm `yaw/pitch` are sane, not constant-zero).

## 5.2 — Parser / schema / backend (local, backward-compatible)
- `ShotFired` dataclass + `_parse_shot_fired_line` (`time;guid;weapon;ox;oy;oz;yaw;pitch`; float→int origin coercion; short/garbage lines skipped, no raise) + `_import_shots_fired` (guarded by `_table_has_column('proximity_shot_fired','guid')` → **no-op if table absent**; reuses `_append_round_link_columns` / `_append_canonical_guid_columns`; `ON CONFLICT DO NOTHING`). Section dispatch + reset + stats wired like `combat_positions`.
- `migrations/055_add_proximity_shot_fired.sql` — idempotent (035-style: `CREATE TABLE/INDEX IF NOT EXISTS`, `DO $$ … duplicate_object` PK guard). Verified: applied **twice** on the dev DB clean (apply#1 rc0, apply#2 rc0 NOTICE-only), 20 cols / 5 idx. Mirrored into `tools/schema_postgresql.sql` (schema/migration kept in sync — the audit's whole theme).
- Backend: `mode=aim` added to `/proximity/player-heatmap` (`proximity_shot_fired` / `origin_x,origin_y` / `guid`) — handled by the existing combat branch. Verified graceful: `status ok, 0 zones, total 0` (empty until deploy), other modes unregressed (`kills_from` still 204), invalid still 400.

## Tests
- `tests/unit/test_proximity_shot_fired_parser.py` — field mapping, float coercion, malformed-skip, **backward-compat (no section → empty list, combat lines don't leak)**.
- `tests/unit/test_proximity_player_heatmap.py` — `mode=aim` routing assertion added.
- `tests/unit/test_proximity_lua_v5_sections_guard.py` — `SHOT_FIRED` guard added (header present, feature-gated, default-OFF). All green (`luac -p` OK; 24 passed / 3 pre-existing skips).

## 5.3 — DEPLOY RUNBOOK (⛔ HARD STOP — requires explicit user approval, NOT autonomous)
Do **not** run any of this without the owner explicitly approving each server-touching step (`docs/DEPLOYMENT_RUNBOOK.md`, `docs/GAMESERVER_LIVE_LUA_MAP.md`):
1. **Runtime-validate `ps.viewangles`** first (read-only test on the live server / a scratch instance) — confirm the binding before shipping the emitter.
2. Apply `migrations/055` to **prod** DB (idempotent; empty table — zero data risk).
3. Deploy Lua `6.02` to `et@…:48101` `…/legacy/luascripts/proximity_tracker.lua` (full map load, **never `lua_restart`** per `feedback_lua_restart`). `features.shot_fired` stays **false** at deploy.
4. Enable `features.shot_fired = true` (+ tune `shot_fired_sample_rate`) only after a controlled test session; watch file size / parser ingest.
5. Validate parser→DB→`/proximity/player-heatmap?mode=aim` on a real session; then surface the `aim` lens in the legacy + React UIs (currently backend-only by design).

Until step 1 is owner-approved and done, v9 ships **dormant**: code present, feature OFF, table empty, zero production impact.
