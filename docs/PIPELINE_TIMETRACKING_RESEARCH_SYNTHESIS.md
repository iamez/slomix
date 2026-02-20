# Pipeline Time-Tracking Research Synthesis

> **Date:** 2026-02-20
> **Scope:** Consolidation of all existing research on time-tracking pipeline changes, c0rnp0rn Lua replacement, webhook ingestion, and timing field accuracy
> **Status:** Research synthesis - no code changes

---

## 1. What We Already Researched

### 1.1 Existing Documentation (Chronological)

| Doc | Path | Date | Key Content |
|-----|------|------|-------------|
| Webhook Triage | `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md` | Feb 11 | STATS_READY pipeline topology; 4-leg architecture; first live triage (partial pass) |
| Closeout Plan | `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md` | Feb 11 | 8 workstreams (WS0-WS7), 43 tasks, hard execution rules |
| Execution Runbook | `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md` | Feb 12 | Critical path ordering; WS1 gate definition; parameter packing fix |
| Closeout Report | `docs/TWO_WEEK_CLOSEOUT_REPORT_2026-02-16.md` | Feb 16 | All 43/43 tasks done; WS1 gate passed; 7 pipeline legs operational |
| Timing Data Sources | `docs/reference/TIMING_DATA_SOURCES.md` | Living | Three timing sources mapped (stats file, webhook, filename); DB column reference |
| Pipeline Deep Dive | `docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md` | Feb 18 | Missing R2 investigation; deprecated service overlap; bot hardening patches |
| R2 Missing Root Cause | `docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md` | Feb 18 | **Root cause: Lua `string.format` crash on fractional R2 timelimit** |
| Live Pipeline Audit | `docs/reports/LIVE_PIPELINE_AUDIT_2026-02-18.md` | Feb 18 | 7-leg audit; vNext state machine; dual ingestion with race protection |
| Timing Shadow | `docs/TIMING_SHADOW_HANDOFF_2026-02-18.md` | Feb 18 | Dual OLD/NEW timing display; `SessionTimingShadowService`; coverage tracking |
| c0rnp0rn7 Report | `docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md` | Feb 19 | LuaJIT compatibility patches; 5+2 locations; post-patch clean scan |
| Live Monitor Mission | `docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md` | Feb 18 | 14-day monitoring window (Feb 18 - Mar 3); escalation matrix |
| Stats Formula Research | `docs/STATS_FORMULA_RESEARCH.md` | Feb 20 | Headshot %, time_played_seconds, FragPotential, website formula divergence |
| Known Issues - Lua Overhaul | `docs/KNOWN_ISSUES.md` (section 1) | Feb 20 | Planned per-player time tracking in webhook Lua; 10-step implementation plan |
| Deep Dive Audit | `docs/DEEP_DIVE_AUDIT_2026-02-20.md` | Feb 20 | Cross-verified formula bugs; website UI status; security posture |

### 1.2 Research on `c0rnp0rn-testluawithtimetracking.lua`

This file (`843 lines`) sits at repo root. It is the **original developer's version** with time-tracking additions but **without** the LuaJIT compatibility patches that were applied to `c0rnp0rn7.lua` (`916 lines`).

**What the test file adds compared to the base c0rnp0rn:**

| Feature | Variable/Code | Location |
|---------|---------------|----------|
| Round start timestamp | `roundStart = et.trap_Milliseconds()` | `et_RunFrame` line 443-444 |
| Round end timestamp | `roundEnd = et.trap_Milliseconds()` | `et_RunFrame` line 393 |
| Pause start tracking | `pausedTime[1] = et.trap_Milliseconds()` | `et_RunFrame` line 481 |
| Pause end tracking | `pausedTime[2] = et.trap_Milliseconds()` | `et_RunFrame` line 496 |
| Cumulative pause time | `pausedTime[3] = (pausedTime[3] or 0) + pausedTime[2] - pausedTime[1]` | `et_RunFrame` line 497 |
| **Stats header field 9** | `roundEnd - roundStart - (pausedTime[3] or 0)` | `SaveStats` line 351 |

**Key output change:** The stats file header gains a **9th field** = actual playtime in milliseconds (pause-subtracted, round-boundary-accurate).

**What the test file is MISSING** (present in c0rnp0rn7.lua):

| Feature | Why It's Missing |
|---------|-----------------|
| `bit.rshift()` / `bit.bor()` / `bit.band()` / `bit.lshift()` | Uses Lua 5.3 operators (`>>`, `<<`, `\|`, `&`) - **NOT LuaJIT compatible** |
| `ensure_bit_compat()` fallback | No runtime bit library detection |
| `ensure_max_clients()` safety | Direct `tonumber(et.trap_Cvar_Get("sv_maxClients"))` without nil safety |
| `to_int()` safe conversion | Missing integer clamping utility |

---

## 2. Key Decisions Already Made

### 2.1 Pipeline Architecture (from Closeout Plan + Runbook)

- **7 pipeline legs** are operational and must remain so
- **Dual ingestion** (webhook + SSH polling) is by design and both must converge on same schema
- **WS1 gate** = STATS_READY webhook -> bot -> `lua_round_teams` DB persistence for R1+R2
- **WS2/WS3 blocked on WS1** = Cannot improve display until data truth is proven
- **`round_id`-based joins** replaced fragile `match_id + round_number` joins

### 2.2 Validation Gates (from Runbook + Closeout)

| Gate | Criterion | Status |
|------|-----------|--------|
| WS1 | Two fresh R1+R2 rounds with Lua persistence | PASSED (Feb 16) |
| WS1B | Cross-source correlation for same round | PASSED |
| Timing Shadow | OLD vs NEW dual display for 2 weeks before cutover | IN PROGRESS |
| R2 Timelimit Fix | No `string.format` crash on fractional timelimit | NOT YET DEPLOYED |

### 2.3 Evidence Requirements (from Runbook)

Every pipeline change must close with:
1. Code/config change
2. Runtime proof (log + DB/API)
3. Tracker/doc update

### 2.4 Backward Compatibility Strategy (from KNOWN_ISSUES.md)

- Old stats files (without new header field 9) must continue to work
- New DB columns default to NULL so existing records unaffected
- Bot should prefer webhook (instant) and use stats file as fallback
- Dual timing display (`SHOW_TIMING_DUAL=true`) runs old and new in parallel

---

## 3. Identified Invariants for Timing Fields

### 3.1 Stats File Header Format

**Current (c0rnp0rn7.lua):** 8 fields
```
servername\mapname\config\round\defenderteam\winnerteam\timelimit\nextTimeLimit
```

**New (c0rnp0rn-testluawithtimetracking.lua):** 9 fields
```
servername\mapname\config\round\defenderteam\winnerteam\timelimit\nextTimeLimit\actualPlaytimeMs
```

**Field 9** = `roundEnd - roundStart - pausedTime[3]` in milliseconds

### 3.2 Per-Player Time Fields (in stats file body)

| TAB Index | Field | Unit | Source |
|-----------|-------|------|--------|
| 22 | `time_played_minutes` | float (min) | `(tp/1000)/60` where `tp = timeAxis + timeAllies` |
| 24 | `time_dead_ratio` | float (%) | `(death_time_total / tp) * 100` |
| 25 | `time_dead_minutes` | float (min) | `death_time_total / 60000` |

### 3.3 Webhook Timing Fields (from `stats_discord_webhook.lua` v1.6.1)

| Field | Type | Meaning |
|-------|------|---------|
| `Lua_Playtime` | seconds | Actual play time (pause-subtracted) |
| `Lua_RoundStart` | unix ts | When GS_PLAYING began |
| `Lua_RoundEnd` | unix ts | When GS_INTERMISSION began |
| `Lua_Warmup` | seconds | Pre-round warmup |
| `Lua_Pauses` | count + seconds | Cumulative pause info |
| `Lua_Pauses_JSON` | JSON array | Per-pause `{start, end, sec}` |

### 3.4 Duration Invariant

For any valid round:
```
actual_duration_seconds = round_end_unix - round_start_unix - total_pause_seconds
```

This MUST hold within the webhook's own data. Cross-source comparison (webhook vs stats file) may differ due to clock source differences (`os.time()` vs `et.trap_Milliseconds()`).

### 3.5 Unit Invariants

| Source | Clock | Unit | Notes |
|--------|-------|------|-------|
| c0rnp0rn (stats file) | `et.trap_Milliseconds()` | Game engine ms | Resets on map load; NOT wall-clock |
| webhook | `os.time()` | Unix seconds | Wall-clock; reliable across map loads |
| Stats header field 9 (new) | `et.trap_Milliseconds()` | Game engine ms | Same source as c0rnp0rn per-player time |

---

## 4. Risks and Mitigations Already Described

### 4.1 R2 Webhook Crash (CRITICAL, UNRESOLVED)

**Risk:** `stats_discord_webhook.lua:830` crashes on fractional R2 timelimit using `%d` formatting.
**Impact:** All R2 webhook data lost for that round (no `STATS_READY`, no gametime file, no `lua_round_teams` row).
**Mitigation documented:** Replace `%d` with `math.floor()` wrapping; wrap payload in `pcall`; reset `send_in_progress` in all exit paths.
**Status:** Fix plan written (`docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md`), **NOT YET DEPLOYED**.

### 4.2 LuaJIT Compatibility

**Risk:** The test file uses Lua 5.3 operators that won't work on LuaJIT builds.
**Mitigation:** c0rnp0rn7.lua already has working `bit.*` patches. Must be cherry-picked into any new version.
**Status:** Patches documented and verified clean (`docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md`).

### 4.3 Stats File Header Field Count Change

**Risk:** Parser expects 8 header fields; new Lua writes 9. If parser strictly validates field count, it will reject new files.
**Mitigation:** Parser already handles this - field 9 is parsed when present (`actual_playtime_seconds`), ignored when absent.
**Verification needed:** Confirm parser code at `community_stats_parser.py` handles both 8-field and 9-field headers.

### 4.4 Deprecated Service Overlap

**Risk:** `et-stats-webhook.service` still enabled on game server, causing duplicate triggers.
**Mitigation:** Must be disabled (`systemctl disable --now et-stats-webhook.service`).
**Status:** Documented in Pipeline Deep Dive; mentioned as preflight check in Live Monitor Mission.

### 4.5 Dual Clock Source Divergence

**Risk:** Stats file uses `et.trap_Milliseconds()` (game engine time), webhook uses `os.time()` (wall clock). These can diverge during pauses, map loads, and server stutters.
**Mitigation:** Don't compare across sources for exact equality. Use each source's data self-consistently. Prefer webhook for round-level timing; use stats file for per-player time.

---

## 5. Open Questions That Remain

| # | Question | Context | How to Verify |
|---|----------|---------|---------------|
| 1 | **Is the R2 timelimit crash fix deployed?** | `LUA_R2_MISSING_ROOT_CAUSE` doc describes the fix but doesn't confirm deployment | Check deployed Lua on game server for `math.floor` wrapping on timelimit |
| 2 | **Does the parser handle 9-field headers?** | New Lua adds field 9 to header; parser must not reject it | Read `community_stats_parser.py` header parsing logic |
| 3 | **What's the status of `SHOW_TIMING_DUAL`?** | Shadow timing was enabled Feb 18 with 2-week window | Check `.env` on VM for current flag value; check if cutover happened |
| 4 | **Are the LuaJIT patches in the test file?** | Test file uses Lua 5.3 operators; needs `bit.*` patches before deployment | Confirmed: NOT patched. Must merge from c0rnp0rn7.lua |
| 5 | **Is `et-stats-webhook.service` disabled?** | Documented as required; unknown if actually done | SSH to game server and check systemctl status |
| 6 | **How many R2 rounds are still missing Lua data?** | Live monitor mission runs Feb 18 - Mar 3 | Query `lua_round_teams` for recent R2 coverage rate |
| 7 | **Should the new Lua also write per-player time to the header?** | KNOWN_ISSUES.md plans per-player time in webhook; should stats file also carry it? | Design decision: webhook-only vs dual output |
| 8 | **What happens to existing `time_played_seconds` when field 9 is available?** | Parser currently sets `time_played_seconds = round_time_seconds` from header for all players | Parser should prefer field 9 when present (more accurate) |

---

*This document consolidates all prior research. See companion docs:*
- *Gap Analysis: `docs/PIPELINE_TIMETRACKING_GAP_ANALYSIS.md`*
- *Next Steps Plan: `docs/PIPELINE_TIMETRACKING_NEXT_STEPS_PLAN.md`*
