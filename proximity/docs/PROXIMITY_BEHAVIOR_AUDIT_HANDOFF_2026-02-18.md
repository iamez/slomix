# Proximity Project Behavior Audit + AI Handoff

**As of:** 2026-02-18  
**Generated:** 2026-02-18 23:28:42 UTC  
**Scope:** `/home/samba/share/slomix_discord` proximity pipeline (Lua tracker, parser, bot ingest, API/UI, runtime files, DB state)

---

## 1. Executive Summary

The proximity pipeline is live and ingesting fresh data in production, including:

- `combat_engagement`
- `player_track`
- `proximity_trade_event`
- `proximity_support_summary`
- `proximity_objective_focus`

The main risk is not "pipeline broken." The main risk is **source-of-truth drift** across:

- repo code/config/docs,
- deployed game-server Lua runtime,
- and user-facing wording ("prototype").

---

## 2. What "Should" Happen

From current proximity docs + code:

- Lua tracker captures movement + combat + heatmaps (+ optional objective focus), writes one round file with sections `ENGAGEMENTS`, `PLAYER_TRACKS`, `KILL_HEATMAP`, `MOVEMENT_HEATMAP`, optional `OBJECTIVE_FOCUS`.
- Parser imports those sections, computes trade events + support uptime, and stores scoped round identity (`session_date`, `round_number`, `round_start_unix`).
- Bot cog scans every 5 minutes for new files and imports deduplicated.
- API serves scoped `/api/proximity/*` data for website view.

Primary implementation refs:

- `proximity/lua/proximity_tracker.lua:54`
- `proximity/lua/proximity_tracker.lua:809`
- `proximity/lua/proximity_tracker.lua:1091`
- `proximity/lua/proximity_tracker.lua:1175`
- `proximity/parser/parser.py:214`
- `proximity/parser/parser.py:627`
- `proximity/parser/parser.py:1114`
- `proximity/parser/parser.py:1174`
- `bot/cogs/proximity_cog.py:296`
- `website/backend/routers/api.py:6598`

---

## 3. What It Actually Does (Observed)

### 3.1 Runtime and Ingestion Health

- Local proximity files present: `52` (`local_proximity`).
- Processed indexes match file count:
  - `local_proximity/.processed_proximity.txt`: 52 lines
  - `local_proximity/.processed_proximity_local.txt`: 52 lines
- Proximity bot ingest is enabled in env:
  - `PROXIMITY_ENABLED=true`
  - `PROXIMITY_AUTO_IMPORT=true`
  - `PROXIMITY_REMOTE_PATH=/home/et/.etlegacy/legacy/proximity`
  - `PROXIMITY_LOCAL_PATH=/home/samba/share/slomix_discord/local_proximity`
  - refs: `.env:143`, `.env:146`, `.env:153`, `.env:154`

### 3.2 Production DB Evidence (read-only queries)

Current row counts:

- `combat_engagement`: `9129`
- `player_track`: `4282`
- `proximity_trade_event`: `4767`
- `proximity_support_summary`: `52`
- `proximity_objective_focus`: `50`

Freshness (max `session_date`):

- all listed proximity tables: `2026-02-18`

### 3.3 Local File Format Evidence

Latest file sampled:

- `local_proximity/2026-02-18-235002-etl_frostbite-round-1_engagements.txt`
- contains `ENGAGEMENTS`, `PLAYER_TRACKS`, `KILL_HEATMAP`, `MOVEMENT_HEATMAP`
- no `OBJECTIVE_FOCUS` in this map sample

Supply sample:

- `local_proximity/2026-02-18-221026-supply-round-1_engagements.txt`
- includes `OBJECTIVE_FOCUS` section with rows (`crane_controls`, `truck_escape`)

### 3.4 Round Normalization Behavior

Parser round normalization source distribution over local files:

- `gametime`: 28 files
- `filename`: 24 files

Header round changed after normalization in 9 files (all from `1 -> 2`, source `gametime`).

This is active behavior, not theoretical.

### 3.5 Sampling Interval Behavior

Observed from real proximity files (local and remote):

- `30` files with `# position_sample_interval=200`
- `22` files with `# position_sample_interval=500`

But repo Lua default currently shows:

- `position_sample_interval = 500` in `proximity/lua/proximity_tracker.lua:54`

Remote console evidence repeatedly logs:

- `Proximity Tracker v4.2`
- `Position sample interval: 200ms`

---

## 4. Should vs Does Matrix

| Area | Should | Does (Observed) | Status |
|---|---|---|---|
| File ingestion loop | 5-minute background scan + import | Active, dedupe indexes updating | OK |
| Core combat/track ingest | Engagements + tracks persisted | Persisted and fresh to 2026-02-18 | OK |
| Trade/support derived metrics | Computed and stored | Persisted (`4767` trade rows, `52` support rows) | OK |
| Objective focus | Optional, depends on objective config | Present but sparse (`50` rows total, map-limited) | PARTIAL |
| Sampling interval consistency | Single canonical config | Mixed 200/500 in output; repo default 500 | DRIFT |
| API readiness messaging | Reflect live state clearly | Uses prototype meta scaffold + ok/ready overrides | PARTIAL |
| Documentation currency | Match v4.2 runtime | Some docs still v1/v3/prototype-first | DRIFT |

---

## 5. Findings (Prioritized)

## F1 - Deployment Drift: Sampling Interval Mismatch
**Severity:** High  
**Impact:** Non-comparable movement/support metrics across rounds; analysis instability.

Evidence:

- Repo: `proximity/lua/proximity_tracker.lua:54` => `500ms`
- Real files: 200ms and 500ms both present
- Remote etconsole repeatedly reports `200ms`

Hypothesis:

- Deployed Lua source differs from repo copy, or runtime cvar/config patching exists outside repo.

---

## F2 - Documentation Drift (Legacy v1/v3 Material)
**Severity:** High  
**Impact:** Operators and downstream AI agents can choose wrong scripts/schema assumptions.

Evidence:

- `docs/PROXIMITY_CLAUDE.md` still references v3 and `gamestats`.
- `PROXIMITY_DEPLOYMENT_GUIDE.md` references v1-era outputs (`*_positions.txt`, `*_combat.txt`) and `gamestats`.
- Current production path and behavior are v4.2-style proximity round files.

---

## F3 - Objective Focus Coverage Is Real but Narrow
**Severity:** Medium  
**Impact:** Objective analytics appear "missing" on many maps.

Evidence:

- `proximity_objective_focus` rows: 50 total.
- By map in DB: `supply=38`, `sw_goldrush_te=12`.
- By objective labels: `tank_breakout=20`, `crane_controls=19`, `truck_escape=11`.

Interpretation:

- Feature works when map objectives are configured.
- Most maps lack objective coordinates in runtime configuration.

---

## F4 - Round Linking Coverage Is Partial
**Severity:** Medium  
**Impact:** Proximity-to-round UI joins (`round_id`, etc.) are incomplete historically.

Evidence:

- Total proximity events linked to `rounds`: `3215 / 9129` (~35.2%).
- Recent dates improve:
  - `2026-02-18`: `1949 / 2415` (~80.7%)
  - `2026-02-16`: `1266 / 2128` (~59.5%)
  - `2026-02-11`: `0 / 3506`

Interpretation:

- Linking logic is timestamp-proximity-based and now works better for newer data.
- Backfill/historical mismatch remains.

---

## F5 - "Prototype" Labeling Is Mixed with Live Operation
**Severity:** Low  
**Impact:** Confusing operator UX and potentially misleading automation prompts.

Evidence:

- API seeds payloads via `_proximity_stub_meta(...)` but many routes return `status=ok` when data exists.
- UI still has prototype fallback messaging paths.

Interpretation:

- Functional, but terminology no longer matches reality.

---

## 6. Confidence

- **High confidence:** ingestion health, table counts, freshness, interval distribution, parser normalization behavior, API route existence.
- **Medium confidence:** exact root cause of 200ms vs 500ms drift (likely deployed-script divergence; not fully pinned to one artifact path yet).

---

## 7. Handoff Tasks for Next AI Agent

## Priority 0
1. Establish canonical sampling interval (200ms vs 500ms) and enforce it.
2. Identify deployed Lua source of truth on game server and sync it to repo.
3. Add a startup self-report row/log artifact including config hash + interval to prevent future silent drift.

## Priority 1
1. Update/remove stale v1/v3 docs and replace with v4.2 operational docs.
2. Add objective coords for top active maps (`te_escape2`, `etl_adlernest`, `etl_sp_delivery`, `et_brewdog`, `etl_frostbite`).
3. Improve historical round-link coverage (backfill matching by map + tighter timestamp heuristics).

## Priority 2
1. Normalize API wording from "prototype" to "live/scoped" where data exists.
2. Add automated drift checks in CI:
   - parse sample files and fail if mixed interval values detected in same deployment window.

---

## 8. Suggested Acceptance Checks

Run after remediation:

1. Verify single interval in latest files.
2. Verify API summary + movers + teamplay + trades endpoints all return `ready=true` for recent session scope.
3. Verify objective focus rows increase on newly configured maps.
4. Verify round-link coverage trends upward on new sessions.

---

## 9. Key Evidence References

Code and docs:

- `proximity/lua/proximity_tracker.lua:54`
- `proximity/lua/proximity_tracker.lua:1175`
- `proximity/parser/parser.py:214`
- `proximity/parser/parser.py:627`
- `bot/cogs/proximity_cog.py:296`
- `website/backend/routers/api.py:6094`
- `website/backend/routers/api.py:6598`
- `website/backend/routers/api.py:6749`
- `website/js/proximity.js:755`
- `website/js/proximity.js:769`
- `docs/PROXIMITY_CLAUDE.md:3`
- `PROXIMITY_DEPLOYMENT_GUIDE.md:61`

Runtime artifacts:

- `local_proximity/2026-02-18-235002-etl_frostbite-round-1_engagements.txt`
- `local_proximity/2026-02-18-221026-supply-round-1_engagements.txt`
- `local_proximity/.processed_proximity.txt`
- `local_proximity/.processed_proximity_local.txt`

---

## 10. Machine-Readable Summary (for Agent Bootstrap)

```json
{
  "audit_date": "2026-02-18",
  "pipeline_live": true,
  "db_counts": {
    "combat_engagement": 9129,
    "player_track": 4282,
    "proximity_trade_event": 4767,
    "proximity_support_summary": 52,
    "proximity_objective_focus": 50
  },
  "freshness_max_session_date": "2026-02-18",
  "sampling_interval_distribution": {
    "200": 30,
    "500": 22
  },
  "objective_focus_by_map": {
    "supply": 38,
    "sw_goldrush_te": 12
  },
  "top_findings": [
    "deployment_drift_sampling_interval",
    "docs_drift_v1_v3_vs_v4_2",
    "objective_coverage_partial",
    "historical_round_link_partial"
  ],
  "recommended_first_action": "pin_and_sync_single_runtime_config_source_of_truth"
}
```

