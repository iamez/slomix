# Lua Timing Drift Investigation Report

**Date**: 2026-02-27
**Status**: Root cause confirmed, fix applied (2026-02-28)
**Severity**: Medium — affects timing debug display, not gameplay data

---

## Executive Summary

Two Slomix bot deployments (samba dev, slomix prod VM) show different "SESSION TIMING DEBUG" output for the same gaming session. The Lua webhook duration values are **identical** on both databases — the divergence is caused by a **race condition in round_id linkage** when the same map is played multiple times in a session.

---

## Problem Statement

Screenshots captured at 12:29pm on 2026-02-27 (`bot1.jpg`, `bot2.jpg`) show session 9973..9995:

| Metric | Bot1 (slomix) | Bot2 (samba) |
|--------|---------------|--------------|
| Rounds with Lua data | 14/16 | 15/16 |
| Surrender fixes | 5 | 6 |
| Total time corrected | 174s | 196s |
| Max timing difference | **343s** | **86s** |
| Missing Lua data | 2 rounds | 1 round |

---

## Root Cause: Race Condition in round_id Linkage

### How Data Flows

1. Game round ends on ET:Legacy server
2. **Lua webhook** fires immediately → Discord embed → bot receives → `_store_lua_round_teams()` → INSERT into `lua_round_teams`
3. **Stats file** written to server → SSH poll (every 60s) → bot downloads → parser → INSERT into `rounds` + `player_comprehensive_stats`
4. Both arrive at roughly the same time (~0-10s apart)

### The Race

When `_store_lua_round_teams()` is called, it resolves `round_id` via `round_linker.py` **at insert time**. The linker queries `SELECT FROM rounds WHERE map_name = ? AND round_number = ? ORDER BY created_at DESC` and picks the closest match by timestamp.

**When the same map is played multiple times in a session** (e.g., 3× te_escape2), multiple rounds share `map_name + round_number`. If the correct round hasn't been imported yet (stats file still in SSH pipeline), the linker falls back to the nearest **existing** round — which is a wrong match from an earlier play of the same map.

### Proof: Timeline Analysis (te_escape2, session 9973..9995)

Three te_escape2 matches were played, producing 6 rounds:

| Round ID | Round# | round_time | Created (samba) | Created (slomix) |
|----------|--------|------------|-----------------|-------------------|
| 9982 | R1 | 222726 | 22:27:36 | 22:27:34 |
| 9983 | R2 | 223318 | 22:33:28 | 22:33:25 |
| 9985 | R1 | 224019 | 22:41:17 | 22:40:44 |
| 9986 | R2 | 224449 | 22:45:17 | 22:45:44 |
| 9988 | R1 | 225059 | 22:51:18 | 22:51:04 |
| 9989 | R2 | 225644 | 22:56:46 | 22:57:44 |

Six Lua webhook events arrived (values identical on both DBs):

| Lua match_id | R# | Duration | Correct round_id |
|---|---|---|---|
| 2026-02-26-222723 | 1 | 719s | 9982 |
| 2026-02-26-223315 | 2 | 267s | 9983 |
| 2026-02-26-224017 | 1 | 377s | 9985 |
| 2026-02-26-224446 | 2 | 204s | 9986 |
| 2026-02-26-225056 | 1 | 324s | 9988 |
| 2026-02-26-225641 | 2 | 303s | 9989 |

### Race Outcome per Host

**Samba (dev)**: Imports rounds faster (~4s before Lua arrives for most rounds)
```
Lua 224017 at 22:41:21 → Round 9985 created 22:41:17 (4s earlier) → EXISTS ✅
Lua 225056 at 22:51:15 → Round 9988 created 22:51:18 (3s later)  → NOT YET ❌ → linked to 9985
```

**Slomix (prod)**: Imports rounds slower (~27s after round_time)
```
Lua 224017 at 22:40:17 → Round 9985 created 22:40:44 (27s later) → NOT YET ❌ → linked to 9982
Lua 224446 at 22:44:46 → Round 9986 created 22:45:44 (58s later) → NOT YET ❌ → linked to 9983
Lua 225056 at 22:51:01 → Round 9988 created 22:51:04 (3s later)  → NOT YET ❌ → linked to 9985
Lua 225641 at 22:56:41 → Round 9989 created 22:57:44 (63s later) → NOT YET ❌ → linked to 9986
```

### Why Wrong Links Persist

`_link_lua_round_teams()` (bot/ultimate_bot.py:1633) runs after stats import and re-links lua records — but only those with `round_id IS NULL` (WHERE clause at line 1664). Records that were already wrongly linked during the race have a non-NULL round_id and are **never corrected**.

---

## Actual round_id Linkage State

### Central DB (samba, 192.168.64.116)

```sql
-- Query: SELECT id, match_id, round_number, actual_duration_seconds, round_id
-- FROM lua_round_teams WHERE map_name = 'te_escape2' AND captured_at >= '2026-02-26 20:00:00'

id  | match_id            | R# | dur | round_id | Correct?
188 | 2026-02-26-222723   | 1  | 719 | 9982     | ✅
190 | 2026-02-26-223315   | 2  | 267 | 9983     | ✅
192 | 2026-02-26-224017   | 1  | 377 | 9985     | ✅
194 | 2026-02-26-224446   | 2  | 204 | 9986     | ✅
196 | 2026-02-26-225056   | 1  | 324 | 9985     | ❌ Should be 9988
198 | 2026-02-26-225641   | 2  | 303 | 9989     | ✅
```

Result: Round 9988 has 0 lua records → shows as "Missing Lua data" in Bot2.
Round 9985 has 2 lua records → LATERAL JOIN picks newest (324s) instead of correct (377s) → "?" diff.

### Slomix Local DB (192.168.64.159)

```sql
id  | match_id            | R# | dur | round_id | Correct?
146 | 2026-02-26-222723   | 1  | 719 | 9982     | ✅
147 | 2026-02-26-223315   | 2  | 267 | 9983     | ✅
148 | 2026-02-26-224017   | 1  | 377 | 9982     | ❌ Should be 9985
149 | 2026-02-26-224446   | 2  | 204 | 9983     | ❌ Should be 9986
150 | 2026-02-26-225056   | 1  | 324 | 9985     | ❌ Should be 9988
151 | 2026-02-26-225641   | 2  | 303 | 9986     | ❌ Should be 9989
```

Result: Round 9982 gets lua 148 (dur=377s, wrong match) → 720s - 377s = **343s** max diff.

---

## Host Infrastructure

| Host | Role | IP | DB Host | DB Password | Code Path | Git HEAD |
|------|------|-----|---------|-------------|-----------|----------|
| samba | Dev | 192.168.64.116 | 192.168.64.116 | etlegacy_secure_2025 | /home/samba/share/slomix_discord | 62624e3 |
| slomix | Prod VM | 192.168.64.159 | localhost | SPCQon2JzLqVqpuXc9CaRNt6LjWKlSGR | /opt/slomix | 8dca0e1 |

- SSH to slomix: `ssh -i ~/.ssh/slomix_vm_ed25519 slomix@192.168.64.159` (alias: `slomix-vm`)
- Slomix is 7 commits behind samba (missing: correlation context, DPM fix)
- Both run separate PostgreSQL databases with the same schema (26-column `lua_round_teams`)

---

## Affected Code Paths

| File | Line | Issue |
|------|------|-------|
| `bot/ultimate_bot.py` | 1633-1706 | `_link_lua_round_teams()` only re-links NULL round_ids |
| `bot/ultimate_bot.py` | 4147-4239 | `_store_lua_round_teams()` resolves round_id at insert time |
| `bot/core/round_linker.py` | 65-249 | `resolve_round_id_with_reason()` picks nearest existing round |
| `bot/services/timing_debug_service.py` | 530-558 | LATERAL JOIN uses `round_id` for matching |

---

## Fix Plan

### 1. Enhance `_link_lua_round_teams()` (bot/ultimate_bot.py:1633)

Add a second pass after the existing NULL-linkage pass that checks for stale linkages where the current round is a closer temporal match than the currently-linked round.

### 2. Create `scripts/relink_lua_round_teams.py`

Backfill script to re-resolve all round_id linkages. Dry-run by default. Run on both databases.

### 3. Deploy to slomix

Push latest code including DPM fix, correlation context, and re-link fix.

### Verification

After backfill:
- Round 9988 should have 1 lua record (dur=324s) — no longer "Missing Lua data"
- Round 9985 should have 1 lua record (dur=377s) — no longer has duplicate linkage
- Timing debug should show 16/16 Lua data, 86s max diff on both hosts

---

## Prevention

The enhanced `_link_lua_round_teams()` will automatically correct stale linkages after every round import. No more dependence on winning the import-vs-webhook race.

---

## References

- Plan file: `/home/samba/.claude/plans/stateless-discovering-jellyfish.md`
- Screenshots: `bot1.jpg`, `bot2.jpg` in repo root
- Related: DPM Bug Fix (`docs/DPM_BUG_FIX_2026_02_27.md`)
- Timing debug service: `bot/services/timing_debug_service.py`
- Round linker: `bot/core/round_linker.py`
