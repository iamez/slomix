# Proximity Lua v9 (6.02) — Deploy Runbook (Phase 5.3)

> ⛔⛔⛔ **HARD STOP — REQUIRES EXPLICIT, AWAKE USER APPROVAL.** ⛔⛔⛔
>
> Phase 5.3 touches the **live game server** (SSH writes) and the
> **production database** (migration) — both are irreversible, outward-facing
> actions explicitly gated in the master plan as "never autonomous". A
> blanket "do the whole plan" instruction is **not** approval for a specific
> production deploy. Do not run any step below until the user is awake and
> explicitly approves *this deploy*, step by step.
>
> **Partial execution 2026-05-18 (owner awake + explicit full
> authorization, per-step gated):** runbook steps **5 (prod DB) and 6 (scp
> dormant v6.02)** were executed and verified. Steps **7–9 (map load,
> `ps.viewangles` runtime-validation, enabling `features.shot_fired`)** were
> **intentionally deferred** — owner chose to leave v6.02 **dormant** (the
> safe, reproducible default). See **Execution log** below; the procedure
> sections remain authoritative for a fresh install (for which this deploy
> is genuinely *not started*).

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

## Execution log

### 2026-05-18 — steps 5–6 executed, 7–9 deferred (dormant)

Owner awake, explicit full authorization (Slovenian "vse ti dovolim" — "I
allow you everything", given as a direct reply to the per-step gated "GO
step 3" prompt), priority stated as *practical working + reproducible for a
fresh install*. Executed per-step, gated, with verification at each step.

- **Pre-flight 1 (no drift):** live `proximity_tracker.lua` SHA-256
  `6a49269732bc6aba50678aac68eb424267851ae6f3866f06d306533d916835cf`,
  4308 lines, `version = "6.01"` — **byte-identical to the Phase 5.0
  snapshot**; no out-of-band change.
- **Pre-flight 2 (backup):** live v6.01 saved to
  `docs/reference/live_sync_backups/20260518_150254_pre_v9_deploy/proximity_tracker.lua`
  (SHA verified MATCH). **Note for handoff:** that path is **gitignored**
  (`.gitignore:527`) — the backup is **local-only on the dev host**
  (`samba`, repo working dir), *not committed to the repo*. It is the
  rollback artifact; if a different operator needs it, copy it out-of-band
  (or simply re-pull the live file: a clean v6.01 can also be reconstructed
  from the pre-#328 repo ancestor — SHA `6a49269…835cf`). Rollback safety
  net in place.
- **Step 5 (PROD DB 055): NO-OP — already applied.** `proximity_shot_fired`
  already existed on prod `etlegacy`, schema **byte-perfect** vs
  `migrations/055_add_proximity_shot_fired.sql` (20 columns, 5 indexes incl.
  `uq_psf_identity` UNIQUE, `idx_psf_guid_map_date`, `idx_psf_canonical`,
  `idx_psf_map_date`). Owner `etlegacy_user`; INSERT verified (probe rolled
  back). Re-apply would be idempotent. Prod == repo migration set.
- **Step 6 (deploy dormant v6.02): DONE, verified.** Guarded `scp` —
  pre-overwrite live SHA re-checked == v6.01 `6a49269…835cf` (abort guard
  passed), post-overwrite live SHA ==
  `2c4e38f6ae3cc38f924ed27a35e10ecdf0c2dee2c206382af038e8959d0b6aa1`
  (repo v6.02, 4368 lines, `features.shot_fired = false` line 248 →
  **DORMANT**). live == repo; drift eliminated; **zero behavioural change
  vs v6.01**.
- **Steps 7–9: DEFERRED by owner decision.** Game server was empty
  (`etconsole.log`: single startup `InitGame` + heartbeats only), so
  `ps.viewangles` cannot be runtime-validated (needs real shots). No forced
  map load (runbook: coordinate with user; unnecessary while dormant — the
  dormant v6.02 loads on the next **natural** map change). Owner chose
  **"leave dormant for now"**: the aim heatmap stays empty,
  `features.shot_fired` stays `false`, nothing else changes. Revisit when a
  real/bot session is available to validate the binding before enabling.

**Rollback not needed** — dormant v6.02 is behaviourally identical to v6.01;
the backup above remains the one-command revert if ever required.

---

**Status: PARTIALLY EXECUTED 2026-05-18 — steps 5–6 done & verified;
steps 7–9 intentionally deferred (v6.02 deployed DORMANT,
`features.shot_fired = false`).** Enabling the flag still requires the gated
live `ps.viewangles` validation (steps 7–9) under explicit per-step approval.
For a **fresh install** this production deploy is *not started*; follow the
procedure sections above.
