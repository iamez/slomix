# RCA: Correlation orphan duplicates + Diag SQL bug
**Datum:** 2026-05-05  ·  **Avtor:** Claude (Opus 4.7) + iamez  ·  **Metodologija:** Mandelbrot RCA v2.0

## TL;DR
"Smart Stats — Diag" stran je za 2026-04-21 prikazala `correlation_ratio = 50% (9/18)` z opozorilom "match metrike nepopolne". Razišanje razkrije **dva ločena bug-a**:

1. **Bug A — Diag SQL halucinacija (moj endpoint).** Šteje correlation rows namesto distinct rounds-ov. Realno: 18/18 rounds-ov je koreliranih. **Fix: 1 SQL line, gotovo.**
2. **Bug B — Proximity orphan correlation rows.** R2 proximity event ustvari **nov** `round_correlations` row namesto da bi se zlil v obstoječega. Za 2026-04-21 je 8 takih orphan-ov (status=`pending`, samo `has_rN_proximity=t`). Niso "škodljivi" za KIS (proximity_kill_outcome je linked čez `round_id`), so pa **šum** v diagnostiki in pokvarijo `completeness_pct`.

---

## Phase 0 — Discovery

**Symptom:** Diag stran prikaže "9/18 koreliranih" za 2026-04-21.

**Cross-source match_id pregled za en match (`etl_adlernest`):**

| Source | match_id | Round | Pomen |
|--------|----------|-------|-------|
| `lua_round_teams` | `2026-04-21-212114` | 1 | Lua dump po R1 (timestamp R1 round start) |
| `lua_round_teams` | `2026-04-21-212607` | 2 | Lua dump po R2 (timestamp R2 round start) |
| `rounds` (stats) | `2026-04-21-212117` | 1 | Stats file timestamp (~3s po Lua) |
| `rounds` (stats) | `2026-04-21-212117` | 2 | Stats file timestamp (isti kot R1) |
| `rounds` (summary) | `2026-04-21-212610` | 0 | Endstats summary timestamp |
| `round_correlations` | `2026-04-21-212114` | — | **complete** — pravilno združen |
| `round_correlations` | `2026-04-21-212607` | — | **pending** — orphan, samo R2 proximity |

**Quantitative:** 9 complete + 8 pending orphan = 17 correlation rows za en dan, dejansko 9 unikatnih match-ov.

## Phase 1 — Dependency Mapping

```
ET server  →  Lua tracker (dumps R1, R2 separately)         →  match_id_R1, match_id_R2
           →  Stats files (R1, R2)                          →  match_id_stats
           →  Proximity engagements (per round file)        →  match_id_proximity (== Lua round timestamp)
                                                                       ↓
                                                       round_correlation_service
                                                                       ↓
                                                       _find_nearby_correlation_id  (merge logic)
                                                                       ↓
                                                       round_correlations (1 row per logical match)
```

**Merge strategije** (`round_correlation_service.py:223-319`):
1. **Strategy 1 — Timestamp proximity ±30s.** Za R1 Lua vs R1 stats (~2-3s razlika).
2. **Strategy 2 — Semantic R2.** `round_number=2` + obstaja correlation z R1 + `has_r2_lua_teams=FALSE` + diff 30-900s.

## Phase 2 — Contract Extraction

**Pričakovan kontrakt `round_correlations`:**
- **Invariant:** 1 row = 1 logičen match (R1+R2 par)
- **Postcondition po vseh event-ih:** `has_r1_*` + `has_r2_*` flag-i ≥ 80% true, `status='complete'`

**Dejansko stanje za 2026-04-21:**
- 9 rows ujema kontrakt ✅
- 8 rows krši invariant — duplikati istega logičnega matcha ❌

## Phase 3 — Mandelbrot Zoom (12-point checklist na merge logiki)

| # | Check | Stanje |
|---|---|---|
| 1 | Correctness | ❌ R2 proximity → orphan |
| 2 | Edge cases | ❌ "R2 lua already arrived before R2 proximity" ni handled |
| 3 | Security | ✅ |
| 4 | Error masking | ⚠️ `_find_nearby_correlation_id` requeste z None brez warninga |
| 5 | Performance | ✅ ORDER BY created_at LIMIT 20 |
| 6 | Types | ✅ |
| 7 | Imports | ✅ |
| 8 | Patterns | ⚠️ "round_id-based linkage" namesto match_id timestamp matching bi bil bolj robust |
| 9 | Concurrency | ✅ `_correlation_lock` |
| 10 | Contract | ❌ "1 row per match" invariant kršen |
| 11 | Duplication | ❌ pending duplikati v tabeli |
| 12 | Failure mode | ❌ silent failure (no orphan detection in service) |

## Phase 4 — RCA 5 Whys (Bug B — Orphan Correlations)

1. **Zakaj 8 orphan correlation rows za 2026-04-21?**
   → Proximity event za R2 ne najde obstoječega correlation row-a in ustvari novega.

2. **Zakaj ne najde?**
   → `_find_nearby_correlation_id(match_id='212607', round_number=2)` vrne `None`.

3. **Zakaj None?**
   → **Strategy 1** (±30s timestamp): proximity match_id timestamp je 293s+ pozno (R2 round start), izven okna.
   → **Strategy 2** (semantic R2): zahteva `has_r2_lua_teams=FALSE`. Lua R2 prispe **pred** proximity R2 (običajen vrstni red: Lua → stats → proximity), zato je flag že `TRUE`.

4. **Zakaj proximity timestamp ni `212114` (kot Lua R1/stats)?**
   → Proximity tracker zapiše datoteko `2026-04-21-212607-etl_adlernest-round-2_engagements.txt` kjer je timestamp = **R2 round start unix**, ne **match start unix**. Filename pattern (`bot/cogs/proximity_mixins/ingestion_mixin.py:103-114`) ekstrahira `match_id` iz prvih 4 segmentov filename-a.

5. **Zakaj naming convention divergira?**
   → Zgodovinsko: proximity je bil dodan kasneje (Feb 2026), vsak round svoj file. Ni bil usklajen z R1-as-match-start konvencijo iz Lua/stats sistema. Eden od dveh sistemov (proximity ali round_correlations) bi se moral prilagoditi drugemu.

## Phase 4b — Ishikawa diagram

```
                         ORPHAN PENDING CORRELATIONS
                                    │
        ┌───────────────────┬───────┴───────┬──────────────────┐
        │                   │               │                  │
   match_id naming    merge strategies   event ordering   no cleanup job
   inconsistency     ne pokrijejo všeh   (Lua-R2 prej     (no orphan
   (proximity        primerov            kot prox-R2)     detection sweeper)
   = round start)    (samo 2 strategi-                    
                     ji za 4 možne                        
                     vire)                                 
```

## Phase 4c — Fault Tree (kaj bi se moglo zgoditi da pride do orphan-a)

```
ORPHAN_PENDING_ROW_CREATED
├── proximity_event_arrives_with_unmerged_match_id (NUJEN)
│   └── filename_uses_round_start_ts_not_match_start_ts (TRUE)
└── _find_nearby_correlation_id_returns_None (NUJEN)
    ├── strategy_1_fails (timestamp_diff > 30s)
    │   └── prox_match_id is round-start, not match-start (TRUE for R2)
    └── strategy_2_fails (semantic_R2_unavailable)
        └── has_r2_lua_teams already TRUE before prox arrives (USUAL ORDER)
```

## Phase 5 — Fix + Verify

### Fix A — Diag SQL bug (urgent, 1 line)

**File:** `website/backend/routers/diagnostics_router.py` (vrstica ~679)

```diff
-COUNT(DISTINCT rc.id) AS rounds_correlated
+COUNT(DISTINCT r.id) FILTER (WHERE rc.id IS NOT NULL) AS rounds_correlated
```

**Status:** ✅ Pripravljeno v repozitoriju, čaka na restart `etlegacy-web`.

**Verify (canary po restartu):**
```bash
curl -s "http://localhost:8000/api/diagnostics/storytelling-completeness?session_date=2026-04-21" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(f\"correlation_ratio={d['correlation_ratio']}, expected ~1.0\")"
```
Pričakovano: `correlation_ratio = 1.0` (18/18). Warning "rounds-ov nekoreliranih" izgine.

### Fix B — Strategy 3: round_id-based merge (resnični fix)

**Idea:** Ko proximity event prispe, **najprej preveri ali obstaja ujemajoč round v `rounds` tabeli s podobnim `round_start_unix`** (±15 min). Če da, vzemi njegov `r1_round_id` ali `r2_round_id` in najdi correlation_id čez to.

**File:** `bot/services/round_correlation_service.py:_find_nearby_correlation_id` — dodaj Strategy 3 pred return None.

**Pseudokod:**
```python
# Strategy 3: round_id linkage (canonical, ne timestamp guessing)
# Pridobi proximity timestamp, najdi rounds.id v ±900s, nato correlation čez (r1|r2)_round_id.
target_unix = int(target_dt.timestamp())
round_match = await self.db.fetch_one(
    """SELECT r.id
       FROM rounds r
       WHERE r.map_name = ?
         AND r.round_number = ?
         AND ABS(r.round_start_unix - ?) <= 900
       ORDER BY ABS(r.round_start_unix - ?) ASC
       LIMIT 1""",
    (map_name, round_number, target_unix, target_unix),
)
if round_match:
    rid = round_match[0]
    cid_row = await self.db.fetch_one(
        """SELECT correlation_id FROM round_correlations
           WHERE r1_round_id = ? OR r2_round_id = ? LIMIT 1""",
        (rid, rid),
    )
    if cid_row:
        return cid_row[0]
```

**Trade-off:** zahteva da je `round_id` že povezan na proximity payload. Moramo preveriti ali `proximity_cog._notify_correlation` lahko zagotovi round_id, ali pa je to predaleč v pipeline-u.

**Alternativa B':** Razširi Strategy 1 window-seconds = 900 ko `round_number == 2` (ker je R2 vedno 30-900s po R1). To je ena vrstica — lažji prvi korak.

### Fix C — Cleanup obstoječih orphan-ov

```sql
-- Pregled orphan-ov (samo proximity flag, brez ostalih flagov, brez round_id-jev)
SELECT id, correlation_id, match_id, map_name, status, completeness_pct, created_at
FROM round_correlations
WHERE status = 'pending'
  AND r1_round_id IS NULL AND r2_round_id IS NULL
  AND completeness_pct < 30
  AND (has_r1_proximity OR has_r2_proximity)
  AND NOT (has_r1_stats OR has_r2_stats OR has_r1_lua_teams OR has_r2_lua_teams);
```

Po validaciji s sub-set-om, izbrišemo. **Ne zdaj** — najprej Fix B, da se ne pojavljajo novi.

---

## Verifikacijska metrika (post-fix)

| Metrika | Pred | Cilj po Fix A | Cilj po Fix B+C |
|---|---|---|---|
| Diag UI: `correlation_ratio` za 2026-04-21 | 0.5 | 1.0 | 1.0 |
| `round_correlations` rows za 2026-04-21 | 17 | 17 | 9 |
| Pending orphan rows celokupno | TBD | TBD | 0 |
| Smart Stats UI completeness warning | šum | clean | clean |

## Open questions

1. Ali je Fix B' (samo razširitev window-a na 900s pri R2) dovolj, ali rabi pravo Strategy 3?
2. Ali obstaja background task ki periodično čisti orphan-e (`round_correlation_service` "schema preflight" je ob zagonu, ne periodic)?
3. Ali je proximity Lua tracker (`vps_scripts/proximity_tracker.lua` v6.01) možnost preimenovanja file pattern-a tako da uporablja R1 match_id za R2 file? **Verjetno ne** — preprosto popravi backend-side.

## Reference

- `bot/services/round_correlation_service.py:223-319` — merge logika
- `bot/cogs/proximity_mixins/ingestion_mixin.py:103-114` — filename → match_id parsing
- `website/backend/routers/diagnostics_router.py:675-687` — moj diag SQL (popravljen)
- Memory: `mandelbrot_rca_v2.md` (37 dni stara, metodologija velja)

---

# Phase 6 — Deep Mandelbrot Zoom (User-requested second pass)

## Globalni obseg (vse zgodovine, ne samo 2026-04-21)

| Metrika | Vrednost |
|---|---|
| Total `round_correlations` rows | 900 |
| Status `complete` | 712 (79%) |
| Status `pending` | **104 (11.6%)** |
| Pending brez `r1/r2_round_id` (orphan) | **104** ← isti |
| Logičnih matchov (date+map) z **>1** correlation row | **168 (33% od ~533 unikatnih)** |
| Najhujši primer | **9 correlation rows za 1 match** |

**Distribucija duplikatov:**

| Rows / match | Št. matchov | Skupaj rows |
|---|---|---|
| 1 (zdravo) | 465 | 465 |
| 2 | 97 | 194 |
| 3 | 55 | 165 |
| 4 | 10 | 40 |
| 5 | 3 | 15 |
| 6 | 2 | 12 |
| **9** | **1** | 9 |

## Časovna regresija — TO NI design problem, TO JE REGRESIJA

| Teden | Total | Pending | Pending % |
|---|---|---|---|
| 2026-03-02 (in prej) | 679 | 0 | **0%** |
| 2026-03-16 | 14 | 0 | 0% |
| 2026-03-23 | 39 | 7 | 17.9% ⚠️ |
| 2026-03-30 | 46 | 30 | **65.2%** 🔴 |
| 2026-04-06 | 67 | 42 | **62.7%** 🔴 |
| 2026-04-13 | 35 | 17 | 48.6% |
| 2026-04-20 | 17 | 8 | 47.1% |

**Pred 2026-03-23: 0% pending. Po: 47-65%.** To je čista regresija, ne arhitekturni problem.

## Dva ločena bug-a, ne en

| Bug | Tip orphan | Čas | Komitov triger | Status |
|---|---|---|---|---|
| **B1** | `lua_only` (Lua arrival ne najde stats merge) | 2026-03-25 → 2026-04-09 (33 cases) | Verjetno `83bfd1e` (proximity v6.01 + bot GUID fix) | ✅ izginilo po `25166fe` (April 1 — Lua/stats merge fix) |
| **B2** | `proximity_only` (proximity arrival ne najde merge) | 2026-04-03 → **danes** (71 cases) | **`f701ee8` (April 3 — `feat(bot): add proximity tracking to round correlation system`)** | 🔴 še **aktivno** |

## Smoking gun komiti

```
f701ee8  2026-04-03  feat(bot): add proximity tracking to round correlation system
13d44b1  2026-04-01  fix: R2 correlation semantic merge + GUID prefix matching
25166fe  2026-04-01  fix(bot): correlation merge for Lua/stats match_id mismatch
83bfd1e  2026-03-25  feat(proximity): v6.01 objective intelligence + bot GUID fix
```

**Causal chain:**
1. `83bfd1e` (Mar 25) prinesel proximity v6.01 z drugačnim filename/timestamp pattern. Pri istem update-u verjetno spremembe v Lua dump timing → match_id divergence Lua vs stats.
2. `25166fe` (Apr 1) dodal `_find_nearby_correlation_id` z **30s window** za fix Lua/stats divergence (uspešno za Lua R1, ampak premajhen window za R2).
3. `13d44b1` (Apr 1) dodal Strategy 2 (semantic R2). Reši Lua R2 orphane.
4. `f701ee8` (Apr 3) dodal `on_proximity_imported`, ki uporablja **isti** `_find_nearby_correlation_id` (30s) — ampak proximity R2 prispe **več minut po R1 match start**, in Strategy 2 ne deluje za proximity (zahteva `has_r2_lua_teams=FALSE`, ampak Lua R2 vedno pride pred proximity R2).

**Regresija je v `f701ee8`** — proximity callback je bil dodan brez upoštevanja da:
- Proximity timestamps niso usklajeni z Lua/stats timestamps (≠2-3s divergenca, ampak 5+ min)
- Strategy 2 za R2 ne pomaga proximity-ju zaradi event ordering-a

## Pattern C — adjacent timestamp pari (3-9s)

10 najbližjih primerov par (pending+complete v <30s window):

```
5407 (Lua only, 142424) + 5409 (Stats, 142427) — gap 3s, MAP frostbite
5527 (Lua only, 230241) + 5528 (Stats+Lua, 230244) — gap 3s, MAP brewdog
5705 (Lua+Prox, 221352) + 5706 (Stats+Lua, 221355) — gap 9s, MAP escape2
... ...
```

Tukaj je situacija različna: **timestamps v 30s window-u**, Strategy 1 **bi morala** delati. Ampak **vsak par ima 2 ločena correlation rows** vendar manj kot 30s razlike.

Verifikacija logike `_find_nearby_correlation_id` (ročno):
```
target = 142427 → datetime 14:24:27
candidate (5407) = 142424 → datetime 14:24:24
diff = 3s ≤ 30s
has_round = None (5407 nima r1_round_id)
best_id = None (first iter)
condition `has_round or best_id is None` → True
best_id = '2026-03-29-142424:etl_frostbite'
return → bi moral merge v 5407
```

**Logika je pravilna, ampak v praksi se ne zgodi.** Možne hipoteze:
- **H1 (race)**: Bot restart med 5407 in 5409 ustvarjanjem (lock ne preživi restart).
- **H2 (ordering)**: 5409 ustvarjen **PRED** 5407 (asyncpg ne committa v thread order). Fork v event loop-u.
- **H3 (multi-process)**: Lua webhook handler (HTTP) in stats file_tracker tečeta v **različnih procesih** in ne delita lock-a. Treba potrditi: ali gre `correlation_service.on_lua_teams_stored` čez webhook handler v drugi process, ali samo signal v isti bot process.
- **H4**: `LIMIT 20` filter — 5407 je 1. v redu (sveže), bi se moral najti, ampak možno da je 5409 nastal **pred** 5407 zaradi vrstnega reda (DB created_at=14:24:32 vs 14:24:35 ne lažeta, 5407 je prvi).

**Najpevejša hipoteza**: H3 — lua_round_storage_mixin teče v drugem context-u kot file_tracker. Glej:
- `bot/services/lua_round_storage_mixin.py:459` kliče `on_lua_teams_stored` (verjetno iz HTTP webhook handler-ja — async).
- `bot/ultimate_bot.py:1734` kliče `on_gametime_processed` (iz parsing pipeline-a).
- `bot/cogs/proximity_mixins/ingestion_mixin.py:114` kliče `on_proximity_imported` (iz file scan pipeline-a).

Vse so znotraj iste bot procesa — **lock _bi moral_ delovati**. Zato H1 ali H2 verjetnejši.

## Dodatni nivo zoom: zakaj `_correlation_lock` ne pomaga

Kod ima `async with self._correlation_lock:` znotraj vsakega `on_*` handler-ja. Lock je `asyncio.Lock()` instance, single-bot scope.

**Možnost ki nisem pokril:** sam `_upsert_correlation` izvede:
```python
INSERT INTO ... ON CONFLICT (correlation_id) DO NOTHING
UPDATE ... WHERE correlation_id = ?
```

**Če dva `on_*` handler-ja serializirata pravilno**, drugemu mora `_find_nearby` videti prvi-ev INSERT. Ampak: asyncpg uporablja **connection pool**. Različni `db.execute` klici lahko hodijo skozi različne connections. **Brez explicitne transakcije**, drugi connection lahko ne vidi neuncommitted prvi-evega writa.

**Hypothesis H5 — zelo verjetna:** `_correlation_lock` zaščita ASYNC sequence znotraj enega Python event loop-a, ampak DB writes preko različnih connections IZ POOL-a se ne committajo atomarno. Drugi handler vstopi v lock, zažene `_find_nearby` na svoj connection, NE VIDI še-ne-committed INSERT prvega handler-ja → vrne None → ustvari nov correlation row.

To pojasni **vse 3 vzorce** (Lua/stats 3-9s gap, proximity vs Lua/stats 5+min gap, multi-row matches).

**Edina pot k pravilnosti**: ali enkapsulirati vse `on_*` operacije v EKSPLICITNO transakcijo, ali pa uporabljati DB-level UNIQUE constraint + retry, namesto in-memory lock.

## Globlji predlog Fix B'' (replaces B' / B / C)

**Strategija — preusmeritev iz time-window matching na canonical round_id linkage**:

1. **Phase 1 — Razširitev Strategy 1 na 600s ZA SAMO `on_proximity_imported`** (lažji prvi korak):
   - 1-line edit: `await self._find_nearby_correlation_id(match_id, map_name, round_number, window_seconds=600)` v on_proximity_imported.
   - Predicat: bo zmanjšalo proximity orphane na blizu 0 (večina je v <600s window).
   - Risk: false-positive merge (npr. dva back-to-back match-a istega map-a). Zelo redko.

2. **Phase 2 — Strategy 3 (round_id linkage)** v `_find_nearby_correlation_id`:
   - Preden vrne None, poskusi: poišči `rounds.id` z najbližjim `round_start_unix` za isti map+round_number, in najdi correlation čez `r1_round_id`/`r2_round_id`.
   - Robust: uporablja DB-canonical round_id namesto string match_id timestamp.
   - Cilj: trajno pokrije **vse vire** (Lua, stats, proximity, gametime, endstats) brez timestamp guessing.

3. **Phase 3 — Connection consistency (najgloblji fix)**:
   - Wrap ves `on_*` v `BEGIN; ... COMMIT;` SQL transakcijo (eksplicitno acquire one connection from pool, run all reads + writes on it).
   - To bi moralo ujeti adjacent timestamp pattern (3-9s gap).

4. **Phase 4 — Cleanup script**:
   - Identificiraj orphan grupe (isti map, isti dan, gap < 30 min, nekateri pending z `r1/r2_round_id IS NULL`).
   - Premerge flag-i v complete row, izbriši orphan-e.
   - Test na sandbox kopiji baze najprej.

5. **Phase 5 — Periodic sweep**:
   - Background task v `RoundCorrelationService` ki vsako uro skenira pending+orphan rows starejše od 1h in jih ali merge ali briše.

## Posodobljena verifikacijska metrika

| Metrika | Pred | Po Fix A | Po Fix B''-1 | Po Fix B''-2 | Po Fix B''-3 |
|---|---|---|---|---|---|
| Diag UI ratio (2026-04-21) | 0.5 | 1.0 | 1.0 | 1.0 | 1.0 |
| Total pending | 104 | 104 | ~30 | ~5 | 0 (po cleanup) |
| Multi-row matches | 168 | 168 | ~80 | ~10 | 0 |
| Novi orphan-i / teden | ~10 | ~10 | ~2 | 0 | 0 |
| 9-row outlier | 1 | 1 | 1 | 0 | 0 |

## Priporočilo (action items)

| # | Akcija | Velikost | Risk | Status |
|---|---|---|---|---|
| 1 | Fix A — diag SQL `COUNT(DISTINCT r.id) FILTER (...)` | 1 line | none | ✅ pripravljeno, čaka restart |
| 2 | Fix B''-1 — `window_seconds=600` v `on_proximity_imported` | 1 line | nizko | predlagam |
| 3 | Strategy 3 (round_id linkage) | ~30 lines | nizko (additional strategy, brez breaking) | predlagam |
| 4 | Connection-level transaction wrap v `_upsert_correlation` | ~10 lines | srednje (potrebuje regression test) | po review-ju |
| 5 | Cleanup script za obstoječe 168 dup matchov | ~50 lines + careful SQL | srednje (data deletion) | po Phase 1-3 |
| 6 | Periodic sweep task | ~40 lines | nizko | po Phase 1-4 |

## Reference (deep dive)

- Smoking-gun commit: `f701ee8` (2026-04-03)
- Pre-regresija commit: `25166fe` (2026-04-01) — uvedel 30s window
- `bot/services/round_correlation_service.py:411-435` — `on_proximity_imported`
- `bot/services/round_correlation_service.py:493-538` — `_upsert_correlation` (no explicit transaction)
- DB konstraint: `round_correlations_correlation_id_key` UNIQUE (not r1_round_id+r2_round_id together)
