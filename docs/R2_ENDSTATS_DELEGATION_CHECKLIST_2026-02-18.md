# R2 Endstats Delegation Checklist (2026-02-18)

Purpose: Assign fix work to multiple agents without re-investigation.

Primary incident report: `docs/R2_ENDSTATS_ACHIEVEMENTS_INVESTIGATION_2026-02-18.md`  
Related Lua timing incident: `docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md`

## Workstream 1: `endstats.lua` Upstream Generation

Owner: Lua/game-server agent  
Priority: P0

### Scope

Files:
- `endstats.lua`

### Tasks

1. Make filename generation round-stable (one filename per round), not per `send_table()` call.
2. Ensure awards + VS rows append into the same file for that round.
3. Harden round-end trigger logic:
- avoid brittle exact text matching for exit conditions
- add logging for `kendofmap`, `tblcount`, `endplayerscnt`, `eomap_done`, and `topshots_f(-2)` execution.
4. Verify R2 surrender flow still writes endstats output.

### Definition of Done

1. For one map session (R1 + R2), server `gamestats` contains exactly:
- one `round-1-endstats.txt`
- one `round-2-endstats.txt`
2. No split files like `...215111...` + `...215112...` for same round.
3. R2 `-endstats.txt` exists for surrender endings and objective endings.

## Workstream 2: Bot Retry/Dedupe Pipeline

Owner: Bot ingestion agent  
Priority: P0

### Scope

Files:
- `bot/ultimate_bot.py`
- optional helper updates in endstats pipeline modules if needed

### Tasks

1. Fix webhook retry progression so unresolved rounds can advance beyond attempt 1.
2. Remove retry self-block caused by active task marker + re-schedule call pattern.
3. Add same-round quality selection:
- if multiple endstats filenames resolve to same `round_id`, prefer richer payload (awards count, VS count, bytes, or explicit score).
4. Preserve idempotency and avoid duplicate Discord posts.
5. Add explicit logs when a poorer duplicate is rejected in favor of better candidate.

### Definition of Done

1. Logs show retry progression (`1/5 -> 2/5 -> ...`) when unresolved persists.
2. Richer file wins for duplicate same-round filenames.
3. Final DB state for duplicate case reflects richer file:
- `round_awards` and `round_vs_stats` match rich input.
4. Exactly one successful published endstats embed per round.

## Workstream 3: QA/Validation + Ops Guardrails

Owner: QA/ops agent  
Priority: P1

### Scope

Validation scripts/checks and runtime monitoring additions.

### Tasks

1. Execute live validation scenarios:
- stopwatch R1/R2 objective finish
- stopwatch R1/R2 surrender finish
- back-to-back rounds where endstats arrives before stats file
2. Verify Discord posting order and content quality for R1/R2.
3. Add alert/check for:
- Round 2 stats posted but no Round 2 endstats within threshold
- duplicate endstats filenames for same map+round
- stored R2 endstats with `0 awards` in active sessions.

### Definition of Done

1. Validation report with scenario outcomes and timestamps.
2. Alerts/checks documented and runnable.
3. No false positives in at least one full session run.

## Cross-Agent Coordination Rules

1. Workstream 1 (Lua) and Workstream 2 (bot) can run in parallel.
2. QA starts after at least one of:
- Lua fix merged to server script path
- bot pipeline fix merged locally.
3. If both change behavior, re-run full validation once together.

## Acceptance Criteria (Global)

1. `etl_adlernest`-style split output no longer causes missing achievements in R2.
2. `supply`-style R2 surrender produces a valid R2 endstats file and post.
3. DB for R2 rounds has non-zero awards where expected from source file.
4. Discord R2 endstats embed contains achievements/awards, not VS-only empty-award output.

## Quick Assignment Copy Block

### Agent A (Lua)

Own `endstats.lua` atomic-per-round output and surrender-safe generation path.

### Agent B (Bot)

Own retry progression + same-round duplicate-quality resolution in `bot/ultimate_bot.py`.

### Agent C (QA/Ops)

Own live scenario validation and post-fix alerting/monitoring checks.
