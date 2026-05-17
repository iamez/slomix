# Proximity Lua v9 (6.02) — Deploy Runbook (Phase 5.3)

> ⛔⛔⛔ **HARD STOP — REQUIRES EXPLICIT, AWAKE USER APPROVAL.** ⛔⛔⛔
>
> This runbook is **documentation only**. It was prepared autonomously but
> **NOT executed**. Phase 5.3 touches the **live game server** (SSH writes)
> and the **production database** (migration) — both are irreversible,
> outward-facing actions explicitly gated in the master plan as "never
> autonomous". A blanket "do the whole plan" instruction is **not** approval
> for a specific production deploy. Do not run any step below until the user
> is awake and explicitly approves *this deploy*, step by step.

## Why this is gated (state today)

- Repo `main` ships Lua **v6.02** with the v9 true-aim `SHOT_FIRED` section
  **dormant** (`features.shot_fired = false`) + parser/schema/migration 055
  already merged, backward-compatible. Production behaviour is **unchanged**.
- The live server runs **v6.01** (Phase 5.0 drift report: byte-identical to
  the pre-#328 repo; SHA-256 `6a49269…835cf`). Deploying v6.02 + enabling the
  flag is what activates per-shot capture.
- **Unproven risk:** `ps.viewangles` ETL 2.83.1 field binding has **no
  precedent** in live or repo Lua (Phase 5.0 grep clean). It **must be
  runtime-validated on the server** before trusting yaw/pitch output. This
  alone is why 5.1/5.2 shipped dormant and 5.3 is gated.

## Coordinates (from existing docs — do not re-derive)

- SSH: `et@91.185.207.163:48101`, key `~/.ssh/etlegacy_bot` (Phase 5.0 doc)
- Live Lua: `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`
- Runtime log: `/home/et/.etlegacy/legacy/etconsole.log`
- Repo Lua (v6.02): `proximity/lua/proximity_tracker.lua`
- Prod migration: `migrations/055_add_proximity_shot_fired.sql` (idempotent)
- Prod services: `slomix-web` / `slomix-bot` (per infra memory)
- Design ref: `docs/PROXIMITY_LUA_V9_DESIGN_2026-05-16.md`

## Pre-flight (safe, read-only — still ask before SSH)

1. Re-confirm no live drift since 5.0: read-only `cat` the live Lua over SSH,
   `sha256sum`, diff vs repo v6.01 ancestor. Abort if it differs from the
   5.0 snapshot (someone changed the server out of band).
2. Back up the live Lua to `docs/reference/live_sync_backups/<ts>/`.
3. On a **scratch** DB, apply `055` twice — confirm idempotent, confirm
   `proximity_shot_fired` schema matches `tools/schema_postgresql.sql`.
4. Confirm the bot/parser handles a v6.02 file with `SHOT_FIRED` absent
   (dormant) AND present (synthetic fixture) — already covered by
   `tests/unit/test_proximity_shot_fired_parser.py`; re-run.

## Deploy (GATED — each step needs the user's explicit go)

5. **[PROD DB]** Apply `055` to production (`etlegacy`): copy to a path
   `postgres` can read (`/tmp`), apply as the documented multi-owner
   migration; verify `proximity_shot_fired` exists, grants correct.
6. **[SERVER WRITE]** `scp` repo v6.02 `proximity_tracker.lua` over the live
   file (backup taken in step 2). **Keep `features.shot_fired = false`** for
   the first deploy — ship the code dormant, verify zero behavioural change
   and that v6.02 parses clean end-to-end on a real round.
7. **Map reload** to load new Lua — **full map load, NEVER `lua_restart`**
   (per `feedback_lua_restart`: `lua_restart` crashes c0rnp0rn8). Coordinate
   with the user; do not restart anything autonomously.
8. **Runtime-validate `ps.viewangles`** on the server: temporarily, on a
   controlled test, enable `features.shot_fired` and inspect a few
   `SHOT_FIRED` lines in `etconsole.log` — confirm yaw/pitch are sane
   (−180..180 / −90..90, move when the player turns). If the binding is
   wrong, **disable the flag, keep v6.02 dormant, fix the binding, repeat**.
9. Only after 8 is clean: enable `features.shot_fired = true` (with the
   configured `shot_fired_sample_rate`) and monitor volume/log size +
   `proximity_shot_fired` ingest for one real session.

## Rollback

- Lua: `scp` the step-2 backup back over the live file + full map load.
- Flag-only issue: set `features.shot_fired = false` (no redeploy needed) +
  map load.
- DB: `055` is additive (new table only) — no destructive rollback needed;
  drop `proximity_shot_fired` only if explicitly required.

## Acceptance

A real session flows parser→DB→endpoint with `SHOT_FIRED` populating
`proximity_shot_fired`, `/proximity/player-heatmap?mode=aim` returns
non-empty for an active player, yaw/pitch sane, no etconsole errors, no
log/volume blowup. Owner validates the aim heatmap visually.

---

**Status: NOT STARTED — awaiting explicit awake-user approval per step.**
Nothing in this runbook has been executed.
