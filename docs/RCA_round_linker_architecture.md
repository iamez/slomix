# RCA: Round-linker architecture deep dive

**Datum:** 2026-05-06  ·  **Avtor:** iamez + Claude  ·  **Metodologija:** Mandelbrot RCA v2.0
**Status:** 🔍 INVESTIGATION ONLY — brez sprememb

> **Namen:** Preden gremo "global" z round-linker refactoringom, razumeti **kaj točno delamo**, kakšne so omejitve trenutnega designa in kateri strain points čakajo blow up. Po tem dokumentu sledi web-research o tem, kako podobne probleme rešujejo drugi (event sourcing, distributed tracing, idempotent ingest), in šele potem implementacijski plan.

---

## TL;DR

Trenutni round-linker je **stateless funkcija (`resolve_round_id`)** ki za dano `(map, round_number, target_dt)` vrne najbližji `rounds.id` po `round_start_unix` ali fuzzy match po datumu. Sistem **deluje za 99% trenutnih primerov**, ampak ima **strukturalno akumulacijo dolgov** v 3 dimenzijah:

1. **Multi-source ingest brez canonical match_id** — 5 entry pointov z 4 različnimi timestampi za isti logični round
2. **6 ločenih fuzzy matching implementacij** — vsaka divergirajoča
3. **No claim/idempotency system** — race conditions vodijo k drift, ne crash

Naš trenutni "patch on patch" pristop (Strategy 1, Strategy 2, Strategy 3, semantic merge, periodic sweep) prikriva **arhitekturni dolg**. Cilj tega dokumenta je: razumeti dolg, raziskati kako drugi rešujejo, in plan-irati clean rewrite.

---

## Phase 0 — Discovery (kaj imamo)

### Tabele s `round_id` stolpcem

**33 tabel** ima `round_id` FK na `rounds.id`. Glavne kategorije:

| Kategorija | Tabele |
|---|---|
| **Canonical** | `rounds`, `lua_round_teams` |
| **Player stats** | `player_comprehensive_stats`, `weapon_comprehensive_stats`, `lua_spawn_stats`, `player_skill_history` |
| **Proximity (20 tabel)** | `proximity_kill_outcome`, `proximity_combat_position`, `proximity_carrier_event`, `proximity_carrier_kill`, `proximity_objective_run`, `proximity_construction_event`, `proximity_team_push`, `proximity_crossfire_opportunity`, `proximity_team_cohesion`, `proximity_spawn_timing`, `proximity_reaction_metric`, `proximity_lua_trade_kill`, `proximity_revive`, `proximity_weapon_accuracy`, `proximity_focus_fire`, `proximity_hit_region`, `proximity_objective_focus`, `proximity_support_summary`, `proximity_carrier_return`, `proximity_escort_credit`, `proximity_trade_event`, `proximity_vehicle_progress` |
| **Combat events** | `combat_engagement`, `player_track` |
| **Match metadata** | `round_assembly_events`, `round_awards`, `round_vs_stats` |
| **System** | `processed_endstats_files` |

### Trenutni linkage status (recent days)

| Tabela | Total (od 2026-04-01) | NULL round_id | Coverage |
|---|---|---|---|
| proximity_team_cohesion | 193,295 | 0 | 100% |
| proximity_kill_outcome | 7,450 | 0 | 100% |
| proximity_team_push | 18,576 | 0 | 100% |
| proximity_combat_position | 7,454 | 0 | 100% |
| proximity_reaction_metric | 19,978 | 1 | 99.99% |
| **Vse ostale tabele** | various | 0 | 100% |

**99.99%+ recent coverage.** Sistem dela. Ampak…

### Pipeline strain points (kaj prihaja)

```
ET Game Server (puran.hehe.si)
│
├─ Stats files                   filename: YYYY-MM-DD-HHMMSS-MAP-round-N.txt
│  └─→ stats_import_mixin       → INSERT rounds (creates round_id)
│                                 → on_round_imported(match_id_stats)
│
├─ Endstats files                filename: YYYY-MM-DD-HHMMSS-MAP-round-N-endstats.txt
│  └─→ endstats_pipeline_mixin  → resolve_round_id()  → on_endstats_processed(match_id_es)
│                                  ↑ ima "duplicate_richer_selected" logiko
│
├─ Lua webhook (HTTP push)       payload: {match_id_lua, round_number, axis_players, allies_players}
│  ├─→ lua_round_storage_mixin  → INSERT lua_round_teams → resolve_round_id() → on_lua_teams_stored
│  └─→ ultimate_bot              → on_gametime_processed(match_id_gt)
│
└─ Proximity engagements         filename: YYYY-MM-DD-HHMMSS-MAP-round-N_engagements.txt
   └─→ proximity/parser/parser   → resolve_round_id() → INSERT proximity_kill_outcome
                                                     → on_proximity_imported(match_id_prox)
                                                       (filename match_id, NE round_start_unix)
```

**5 ingest entry pointov, 4 različni `match_id` semantike:**

- `match_id_stats` = filename timestamp = **R1 round-start** + 0-3s parser delay
- `match_id_es` = endstats filename timestamp = **round-end** + flush delay
- `match_id_lua` = Lua dump timestamp = **R1/R2 round-start** + 1-2s
- `match_id_prox` = proximity filename timestamp = **round-end** flush
- `match_id_gt` = gametime payload timestamp

**Dejansko opažanje za 2026-05-05 etl_adlernest R1 match:**
- Lua arrived: 19:25:23 UTC
- Proximity linked: 19:25:29 UTC (6s po Lua)
- Stats arrived: 19:25:19 UTC (lokalno v rounds.created_at — TZ heterogeneity!)
- (TZ problem: rounds.created_at = local CEST naive, lua.captured_at = UTC tz-aware)

---

## Phase 1 — Dependency mapping (kdo kliče koga)

### `resolve_round_id` callsites

```
bot/core/round_linker.py: resolve_round_id (canonical)
├─ bot/ultimate_bot.py:1147           — _resolve_round_id_for_metadata (orchestrator)
│   ├─ stats_import (line 1046)
│   └─ endstats post-processing (line 1396)
├─ bot/services/lua_round_storage_mixin.py:254, 499  — Lua dump linkage
├─ bot/services/endstats_pipeline_mixin.py:449       — endstats linkage
├─ bot/cogs/proximity_mixins/relinker_mixin.py:64    — periodic 5-min retry
└─ proximity/parser/parser.py:979                    — proximity ingest
```

**6 callsites.** Vsak z **različnim** `window_minutes`:
- Round_linker default: **45 min**
- Proximity parser: **45 min** (env-configurable 1-180)
- Re-linker: **120 min** (2 hours!)

Ni dokumentacije *zakaj* posamezne vrednosti.

### Fuzzy matching code duplication

**6 ločenih implementacij "find nearest round/correlation":**

| Subsistem | Funkcija | Logika |
|---|---|---|
| 1. Round linker | `resolve_round_id_with_reason` | Exact unix → fuzzy nearest by `round_start_unix` ±45min |
| 2. Correlation service | `_find_nearby_correlation_id` | Strategy 1 (timestamp ±30/600s) + Strategy 2 (semantic R2) + Strategy 3 (round_id linkage) |
| 3. Timing comparison | `round-number-relaxed fallback` | Different fuzzy logic, low confidence flag |
| 4. Endstats pipeline mixin | internal duplicate-richer detection | Per-round file deduplication |
| 5. Timing debug service | timing_debug fuzzy | Debug-only |
| 6. Team management cog | team-level fuzzy | Player→team assignment |

Bug fix v 1 ne propagira v ostale. **Ko je popravljen Strategy 3 (back-to-back race), enak bug ostaja v drugih 5.**

---

## Phase 2 — Contract extraction

### Trenutni implicit kontrakt `resolve_round_id`

**Input:**
- `map_name: str` (required)
- `round_number: int` (required, 1 or 2)
- `target_dt: datetime | None` (optional but typically set)
- `round_date: str | None` (optional fallback)
- `round_time: str | None` (optional fallback)
- `window_minutes: int = 45`

**Output:**
- `Tuple[round_id: int | None, diag: dict]`

**Implicit preconditions:**
- `rounds` tabela vsebuje kandidate s pravilnim `(map, round_number)`
- `round_start_unix` je accurate (kar ni vedno res — drift)
- target_dt timezone consistent s candidate timestamps

**Postconditions:**
- Vrne najbližjega round_id within window, ali None
- **NI guarantee da round_id še ni linked drugje** — vsak callsite lahko isti round_id "claim-a"
- **NI guarantee da bo isti input vrnil isti output** če `rounds` tabela med call-i raste

### Manjkajoči kontrakti

1. **Idempotency**: nedefinirana. V praksi ni idempotent, ker rounds tabela se spreminja.
2. **Reverse exclusivity**: en round_id ↔ N source-files (intencionalno), ampak NI claim system za "kateri file je prvi". Zato race conditions vodijo k mismatched assignments.
3. **Timezone semantics**: `target_dt` mora biti naive-local. Druge tabele uporabljajo UTC-aware. **Mixed throughout codebase.**
4. **Failure semantics**: kaj if multiple equal-distance candidates? Trenutno: prvi v ORDER BY (nedefinirano).
5. **Multi-stats-file semantics**: če 2 stats datoteki za isti logični round prispete (lua_restart, retry, glitch), ustvarita 2 rounds rows? Endstats pipeline ima `duplicate_richer_selected` logiko, ampak **stats import nima**. Preverjeno: 8 dni z ≥3 te_escape2 R1 rounds (legit best-of-3, ne file dups), ampak ne raziskan korner case.

---

## Phase 3 — Mandelbrot Zoom (12-point checklist)

| # | Check | Status | Detail |
|---|---|---|---|
| 1 | **Correctness** | ⚠️ | Race condition: proximity prej kot stats → wrong round_id linked. Periodic sweep fix-a, ampak kvariji-by-design. |
| 2 | **Edge cases** | ⚠️ | Multi-match days (best-of-3) handled, ampak: lua_restart, surrender mid-round, post-round overflow (411 kills out of round duration) niso explicit-no testirani. |
| 3 | **Security** | ✅ | Parameterized queries, no SQL injection. |
| 4 | **Error masking** | ⚠️ | `except Exception: logger.debug(...)` v `_find_nearby_correlation_id` (line 318). `except Exception: logger.warning(Re-linker error)` v relinker. |
| 5 | **Performance** | ⚠️ | Re-linker UNION-a 20 tabel × 2 (NULL + mismatch) = 40 sub-queries vsako 5 min. LIMIT 50. **Pri scale ≥1000 rounds/day, performance bottleneck.** |
| 6 | **Types** | ❌ | GUID heterogeneity (8-char vs 32-char). Timestamp heterogeneity (local naive vs UTC aware). kill_time v ms vs round_dur v s. |
| 7 | **Imports** | ⚠️ | round_linker re-imported v vsak callsite (5 različnih) — no centralization. |
| 8 | **Patterns** | ❌ | Multiple sources of truth: `round_start_unix`, `match_id`, `round_date+round_time`. Linker primerja samo prvo, ampak callsite-i podajajo različne. |
| 9 | **Concurrency** | ⚠️ | round_linker je stateless — no race v sami funkciji. Ampak: TX boundaries niso eksplicitne (vsak `db.execute` autocommit). Pri DB connection pool, drugi handler može videti partial state. |
| 10 | **Contract compliance** | ❌ | "1 round_id per source per round" invariant kršen pri race conditions. |
| 11 | **Code duplication** | ❌ | 6 ločenih fuzzy matching implementacij. Bug-fix divergence guaranteed. |
| 12 | **Failure modes** | ❌ | Silent: orphan accumulation, false-merge, drift. Brez alarmiranja, samo log warnings. |

---

## Phase 4 — RCA (kaj je root cause)

### 5 Whys

1. **Zakaj imamo 6 fuzzy matching implementacij?**
   → Ker vsak subsistem (proximity, lua, stats, endstats, timing comparison) je bil dodan inkrementalno. Nikoli ni bil refactor v centralizirano abstrakcijo.

2. **Zakaj inkrementalno brez refactor?**
   → Hobby projekt, "make it work" pristop. Plus: round_linker je *eden* funkcija, ampak callsite-i v ingest pipelines so prenehali kompozicijsko izhajati.

3. **Zakaj race conditions vodijo k mismatched round_ids namesto k crash?**
   → Ker round_linker je "best effort" — vrne najboljši match brez claim/exclusivity. Failure mode je silent drift, ne explicit error.

4. **Zakaj silent drift?**
   → Nismo imeli observability infrastructure: drift count, mismatch alarmi. To delamo zdaj (sanity check tool, periodic sweep).

5. **Zakaj smo na "patch v patch" v Strategy 1/2/3 rather kot rewrite?**
   → Bottom-up evolution, ker vsaka iteracija reševala posamezen edge case (R2 timing, back-to-back match, etc.). Brez **kanoničnega match_id** ne moremo zares rewrite-at — vsak vir ima svoj.

### Ishikawa diagram

```
                 ROUND-LINKER ARCHITECTURE DEBT
                           │
   ┌───────────────────┬───┴───────────┬──────────────────────┐
   │                   │               │                      │
Multi-source        Code            No claim             Implicit
match_id          duplication       exclusivity          contracts
divergence        (6 fuzzies)
   │                   │               │                      │
   ├ Stats ts          ├ round_linker  ├ no idempotency       ├ TZ ambiguity
   ├ Lua ts            ├ correlation   ├ no transactions      ├ GUID format
   ├ Endstats ts       ├ timing_comp   ├ best-effort path     ├ no test contract
   ├ Proximity ts      ├ endstats_pip  └ silent drift          └ window-min undocumented
   ├ Gametime ts       ├ timing_debug
   └ R0 summary ts     └ team_mgmt
```

### Fault tree (kaj se zgodi pri race)

```
ROUND-LINK MISMATCH
├── Race condition: proximity arrival BEFORE stats arrival (NUJEN)
│   └── proximity_kill_outcome.round_start_unix = canonical (correct)
│       BUT rounds tabela še ne vsebuje matching round
└── round_linker called BEFORE rounds row exists (NUJEN)
    └── linker returns nearest existing round (wrong match in back-to-back)
        └── Re-linker (5-min cron) eventually retry-ja
            └── PHASE F: only retries if mismatch detected (now in place)
                └── KIS calculation may have used wrong round briefly
```

---

## Phase 5 — Inventory of "what works", "what hurts", "what scares"

### What works ✅

- Stateless `resolve_round_id` is testable (1 test file: `tests/unit/test_round_linker_reasons.py`)
- Exact unix match priority (line 293) is correct & deterministic
- Re-linker periodic retry (5 min cron) catches transient race conditions
- Diag UI proves end-to-end correctness for current day
- 99.99% recent linkage coverage

### What hurts ⚠️

- 6 fuzzy matching subsystems = bug-fix divergence
- Window minutes inconsistent (45/120/env)
- Multi-source match_id ambiguity (4 different timestamp semantics)
- TZ heterogeneity (naive local vs UTC aware mixed)
- GUID format heterogeneity (8 vs 32 chars)
- Periodic sweep is workaround, not root fix

### What scares 🔴

- **No "canonical match_id"**: when ET server changes Lua dump format, all 6 fuzzies need updating
- **No claim system**: 2 stats files for same round → 2 rounds rows → all derived linkage diverges
- **Silent failure mode**: drift accumulates without alerting — caught only by manual investigation (kot zdaj)
- **Performance ceiling**: re-linker UNION-a 40 sub-queries per 5min. At 1000+ rounds/day, this becomes O(N²)
- **Test coverage thin**: 1 test file za core logic; 0 tests za 6 fuzzy variants

---

## Phase 6 — Web research questions (next step)

Before architecting fix, research:

1. **Event sourcing patterns**: how do streaming systems (Kafka, EventStore, Pulsar) handle "multiple sources for same logical event"?
2. **Idempotent ingestion**: dedup at boundary vs reconcile after — which is preferred?
3. **CRDT / conflict resolution**: when 2 sources disagree on a fact, what's the merge strategy?
4. **Distributed tracing**: how does Jaeger/Zipkin link spans from different services into one trace?
5. **Game telemetry pipelines**: Counter-Strike (HLTV demos), Dota 2, League — they all have "multi-source per match" problem. How?
6. **Database "merge" patterns**: PostgreSQL `INSERT ... ON CONFLICT DO UPDATE` (we use), but for multi-table multi-source?
7. **Saga / orchestration patterns**: when a "round" is a long-running process with multiple finalizers (R1 stats, R2 stats, endstats, lua, proximity), should it be a saga?

Konkretni search queries za web:
- "event sourcing multiple sources idempotent ingestion"
- "telemetry pipeline log correlation game server"
- "ingestion pipeline match_id merge conflicting sources"
- "match data model esports analytics counter strike valve"
- "distributed event correlation trace_id span_id"
- "PostgreSQL upsert multiple sources idempotent saga"

---

## Phase 7 — Architecture options (preview, before research)

### Option A — Status quo with hardening

- Keep stateless round_linker, add explicit claim system (lock per round_id)
- Centralize all 6 fuzzy implementations in 1 module
- Add structured TZ contract (all UTC-aware internally)
- Add explicit idempotency keys per source

**Pros:** incremental, no breaking. **Cons:** still patches accumulating.

### Option B — Canonical match_id + saga orchestration

- Define `canonical_match_id` (probably from Lua R1 timestamp, or game server hash)
- All 6 sources publish their data tagged with canonical_match_id
- Saga orchestrator waits for all 5 sources before finalizing round_correlations
- round_id remains FK, but linkage happens via canonical_match_id

**Pros:** clean architecture, eliminates fuzzy. **Cons:** ET server side needs canonical match_id propagation (needs Lua mod work).

### Option C — Event-sourced reconciliation

- All 5 sources publish events to append-only log (rounds_event_log)
- Materialized views compute current state (rounds, round_correlations, derived)
- Replay log to reconcile drift; deterministic by definition

**Pros:** auditable, scalable, testable. **Cons:** big rewrite, replay infrastructure.

### Option D — CRDT-style merge

- Each source produces a "round candidate" with fields it knows
- Merge function combines candidates (latest-wins for overlapping fields, OR for boolean flags)
- Drift becomes a tunable convergence delay

**Pros:** robust to out-of-order. **Cons:** complex semantics, hard to debug.

---

## Plan (after web research)

1. **Web research** — kako drugi rešujejo (1 day, structured findings doc)
2. **Architecture decision record (ADR)** — pick option (or hybrid), document rationale
3. **Migration design** — incremental path from current 6-fuzzy state to chosen architecture
4. **Test contract definition** — what invariants must hold; write tests FIRST
5. **Implementation in phases** — each phase deployed + verified before next
6. **Old fuzzy retirement** — gradual deprecation, not big-bang
7. **Production observability** — drift dashboard, alarm thresholds, sweep dry-run mode

**Estimated effort:** 2-4 weeks (depending on architecture choice).

---

## Reference

- Current correlation orphan resolution: `docs/RCA_2026-04-21_correlation_orphans.md` + `docs/PLAN_correlation_orphan_remediation.md`
- Round linker source: `bot/core/round_linker.py`
- Re-linker mixin: `bot/cogs/proximity_mixins/relinker_mixin.py`
- Correlation service: `bot/services/round_correlation_service.py`
- Tests: `tests/unit/test_round_linker_reasons.py`
- Sanity check tool: `tools/website_sanity_check.py`
- Cleanup tool: `tools/cleanup_correlation_duplicates.py`

## Open questions for next session

1. Ali ima ET server (puran.hehe.si) Lua mod source dostop? Če da, lahko dodamo `canonical_match_id` na server-side?
2. Kakšen je actual round/day load expected? (Affects which option scales.)
3. Ali smo OK z migration period kjer 2 systemi tečeta paralelno (old fuzzy + new event-sourced)?
4. Kateri kontrakti so MUST-HAVE (hard invariant) vs NICE-TO-HAVE?
