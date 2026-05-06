# ADR: Canonical round identity for multi-source ingest

**Datum:** 2026-05-06  ·  **Avtor:** iamez + Claude  ·  **Status:** PROPOSED
**Predhodno:** [`docs/RCA_round_linker_architecture.md`](RCA_round_linker_architecture.md)

> **Decision:** Uvesti `round_canonical_id` (trace_id-style stable identifier) na rounds tabel, derived deterministično iz `(round_start_unix, map_name, round_number)`. Vsi 5 ingest entry pointov pišejo z `INSERT ... ON CONFLICT (round_canonical_id) DO UPDATE` (idempotent). Round_linker postane preprost lookup, ne fuzzy matching.

---

## Context (pridobljeno iz RCA + web research)

### 1. Trenutni stanje (RCA recap)

- 5 ingest entry pointov, 4 različni timestamp semantike, 6 fuzzy matching implementacij
- 99.99% recent linkage coverage, ampak strukturni dolg
- Race conditions vodijo k silent drift, ne crash

### 2. Web research findings

| Pattern | Reference | Applicability za nas |
|---|---|---|
| **Idempotent UPSERT** | PostgreSQL `INSERT ON CONFLICT (key) DO UPDATE` | ✅ Direct — naš canonical_id = stable conflict key |
| **OpenTelemetry trace_id** | Spans linked by trace_id, context propagation | ✅ Map: round = trace, source files = spans |
| **Saga pattern** | Long-running multi-step transactions, choreography | ✅ Že imamo (round_correlations) — manjka timeout |
| **UUIDv5 content-addressed** | Same input → same UUID, idempotent by design | ✅ Možna implementacija canonical_id |
| **CS:GO demo single-source** | Valve has 1 demo file = full match | ❌ Ne aplicirano — mi imamo 4 ločenih izvorov |

### 3. Kritičen najdek o source files (preverjeno na ET serverju)

**Vsi non-stats viri NOSIJO canonical `round_start_unix`:**

| File / Source | Canonical timestamp | Lokacija |
|---|---|---|
| Lua webhook payload | `round_start_unix` v meta + `match_id == round_end_unix` | JSON payload |
| Gametime JSON | `round_start_unix` v meta | File content |
| Proximity engagement file | `# round_start_unix=1778015328` v header | File header |
| **Native stats `*-round-N.txt`** | **❌ NI v contentu** | samo filename timestamp |
| Endstats file | filename timestamp ≈ round_end + ε | filename |

**Stats native je edini vir brez canonical timestamp v contentu.** Toda lahko ga **derive-amo**: `round_start_unix = filename_timestamp - actual_duration_seconds` (duration je v file content prva vrstica `5:48 = 348s`).

---

## Decision

### Definition

```python
round_canonical_id = sha256(f"{round_start_unix}:{map_name}:{round_number}").hexdigest()[:16]
```

Primer: `round_start_unix=1776803695, map=te_escape2, round=2` → `round_canonical_id="a3f8b2d1e9c5..."` (16-char hex).

### Properties

- **Stable**: ista kombinacija → isti id, vedno
- **Content-addressed**: samo iz canonical fields, ne iz arrival time
- **Collision-free**: 16-char SHA256 = 64 bits = 1.8×10¹⁹ possible values; collision risk negligible za naš scale
- **Cross-source verifiable**: vsak source ima dovolj info za compute (Lua, proximity, gametime imajo direkt; stats native derive-a iz duration)

### Why not just `round_start_unix`?

- Ne unique sam (2 različni mapi z istim startom — sicer redko, ampak teoretično možno)
- Manjka semantic context (round_number, map)
- Hash je "single key" za UNIQUE constraint, lažje kot composite

### Why hash instead of triple key?

- DB performance: single column UNIQUE index < composite
- Application code: simpler `WHERE round_canonical_id = X` < `WHERE start=X AND map=Y AND rn=Z`
- Forward-compatible: če dodamo polja v future, hash nedotaknjen

---

## Consequences

### Positive

1. **Round_linker postane O(1) lookup**: `SELECT id FROM rounds WHERE round_canonical_id=$1`. Brez fuzzy.
2. **Idempotent ingest**: re-process istega fileea = no-op. 2 fileja za isti round = 1 row.
3. **Eliminate 5/6 fuzzy implementations**: round_correlation, timing_comparison, etc. uporabljajo isti lookup.
4. **Race conditions disappear**: vsi sources convergirajo na isti canonical_id ne glede arrival order.
5. **Audit trail**: `processed_endstats_files` že obstaja — extension za stats / lua / proximity. "Kje smo videli ta canonical_id?" je triv-query.
6. **Test contract clear**: enaka inputa → enak canonical_id. Unit test trivialen.

### Negative

1. **Migration risk**: backfill 660 historic rounds + verifikacija. Med backfill, dual-mode (old fuzzy + new canonical) potreben.
2. **Stats native derive logic**: če `actual_duration_seconds` ne ujema z dejanskim, derived round_start_unix narobe → wrong canonical_id → false split.
3. **Schema change**: nova kolona, UNIQUE constraint, FK update. Pomembno migration.
4. **All 5 ingest sites need update**: stats_import, endstats_pipeline, lua_storage, proximity_parser, gametime_handler. ~5-10 LOC each.
5. **Backward compat**: stara koda kjer pričakuje round_id po fuzzy lookup — naj ostane kot fallback med migration.

### Neutral

- **No external API change**: round_id ostane primary FK. canonical_id je interni alternate key.
- **Performance**: SHA256 compute ms-level. UNIQUE index lookup mikrosekundi. Net win.

---

## Migration phases

### Phase 1 — Schema + backfill (1-2 days, LOW RISK)

1. **Migration**: `ALTER TABLE rounds ADD COLUMN round_canonical_id varchar(64) NULL;`
2. **Backfill script**: compute za vseh 660 historic rounds + UNIQUE constraint deferred
3. **Index**: `CREATE INDEX idx_rounds_canonical_id ON rounds(round_canonical_id);`
4. **Verify**: 100% rounds imajo canonical_id; 0 duplikatov

**Verify SQL**:
```sql
SELECT COUNT(*) AS total, 
       COUNT(round_canonical_id) AS with_canonical,
       COUNT(DISTINCT round_canonical_id) AS unique_canonical
FROM rounds;
-- Pričakovano: total = with_canonical = unique_canonical
```

**Rollback**: `ALTER TABLE rounds DROP COLUMN round_canonical_id;`

### Phase 2 — Ingest write (2-3 days, LOW RISK)

1. **Add canonical_id compute function** v shared library: `bot/core/round_canonical.py`
2. **5 ingest sites pišejo** canonical_id ob INSERT (dual-write z obstoječimi columns):
   - `stats_import_mixin.py`: derive `round_start_unix = filename_ts - duration`, compute id
   - `endstats_pipeline_mixin.py`: lookup obstoječ rounds row z (map, round, ts) + assign
   - `lua_round_storage_mixin.py`: direkt iz payload
   - `proximity/parser/parser.py`: direkt iz header
   - `ultimate_bot.py:_resolve_round_id_for_metadata`: derive iz metadata
3. **Verify**: vse nove rounds imajo canonical_id (Phase 1 backfill + Phase 2 dual-write)

**Verify**: po 24h, query: `SELECT COUNT(*) FROM rounds WHERE created_at > NOW() - INTERVAL '24h' AND round_canonical_id IS NULL` → 0

**Rollback**: revert ingest writes; canonical_id stolpec ostane (no harm).

### Phase 3 — UNIQUE + UPSERT (3-4 days, MEDIUM RISK)

1. **Add UNIQUE constraint**: `ALTER TABLE rounds ADD CONSTRAINT rounds_canonical_id_unique UNIQUE (round_canonical_id);`
2. **Refactor 5 ingest sites** v `INSERT ... ON CONFLICT (round_canonical_id) DO UPDATE`:
   ```sql
   INSERT INTO rounds (canonical_id, match_id, round_start_unix, ...)
   VALUES (...)
   ON CONFLICT (round_canonical_id) DO UPDATE
   SET match_id = COALESCE(EXCLUDED.match_id, rounds.match_id),
       actual_duration_seconds = COALESCE(EXCLUDED.actual_duration_seconds, rounds.actual_duration_seconds),
       ...
   RETURNING id;
   ```
3. **Test**: 2 stats datoteki za isti round → 1 rounds row + obe metadati merged

**Verify**: po week, query rounds duplikatov:
```sql
SELECT round_canonical_id, COUNT(*) FROM rounds GROUP BY 1 HAVING COUNT(*) > 1;
-- Pričakovano: 0 rows
```

**Rollback**: drop UNIQUE constraint; ingest sites tolerate duplicates kot prej.

### Phase 4 — Round_linker simplification (1-2 days, LOW RISK)

1. **New primary path** v `resolve_round_id`:
   ```python
   if canonical_id:
       row = await db.fetch_one("SELECT id FROM rounds WHERE round_canonical_id=$1", (canonical_id,))
       if row: return row[0], {"reason": "canonical_id_match"}
   # FALLBACK: existing fuzzy logic (backward compat)
   ```
2. **Update callsites** da pošljejo canonical_id kjer možno
3. **Monitor**: log canonical_id_match vs fuzzy fallback ratio

**Verify**: 24h log inspection — `canonical_id_match` ratio ≥95%, fuzzy fallback ≤5%

### Phase 5 — Retire fuzzy (3-5 days, LOW RISK after Phase 4 verified)

1. **Deprecate** 5 fuzzy implementations (timing_comparison, endstats internal, etc.) — replace z canonical_id lookup
2. **Round_linker fuzzy** ostane samo kot fallback za pre-canonical historic data
3. **Re-linker** delete (no longer needed — UPSERT handles atomically)
4. **Periodic sweep** delete (UPSERT prevents orphan creation)

**Verify**: tests pass, drift count = 0 v 1 teden

### Phase 6 — Saga timeout (1 day, LOW RISK)

1. **Add timeout** v `round_correlations`: če `created_at < NOW() - INTERVAL '1 hour'` AND `status='pending'` → mark `incomplete` z reason
2. **Alert dashboard**: incomplete count > threshold → Discord notification
3. **Compensating action**: `incomplete` rounds get cleanup script tag → Phase D-style resolved

**Verify**: synthetic test (skip lua webhook) → timeout fires + alert received

---

## Test contract (definirani PRED implementacijo)

```python
# Property: same canonical_id for same canonical fields
def test_canonical_id_deterministic():
    a = compute_canonical_id(round_start=1776803695, map="te_escape2", round=2)
    b = compute_canonical_id(round_start=1776803695, map="te_escape2", round=2)
    assert a == b

# Property: idempotent ingest
async def test_double_ingest_no_duplicate(db):
    await ingest_stats(file1)
    await ingest_stats(file1)  # same file twice
    assert (await db.fetch_val("SELECT COUNT(*) FROM rounds")) == 1

# Property: late arrival merge
async def test_lua_then_stats_merge(db):
    await ingest_lua(payload)
    await ingest_stats(file)  # different timestamp same round
    rows = await db.fetch_all("SELECT * FROM rounds")
    assert len(rows) == 1
    assert rows[0]["has_r1_lua"] and rows[0]["has_r1_stats"]

# Property: race condition resilience
async def test_concurrent_ingest_no_duplicate(db):
    await asyncio.gather(
        ingest_proximity(file),
        ingest_stats(file),
        ingest_lua(payload),
    )
    assert (await db.fetch_val("SELECT COUNT(*) FROM rounds")) == 1

# Property: stats native derive correctness
def test_stats_derive_round_start():
    # Filename: 2026-05-05-225041-et_brewdog-round-1.txt
    # Content first line includes "7:15" actual_duration
    derived_start = derive_round_start_from_stats(file)
    expected = 1778013803  # known from rounds table
    assert abs(derived_start - expected) <= 5  # 5s tolerance
```

---

## Open questions for review

1. **Canonical_id format**: 16-char SHA256 hex vs UUIDv5 vs pure (start, map, rn) composite — kateri?
2. **Stats native derive**: actual_duration je v "M:SS" string format. Robust parser? Edge: pause time, warmup?
3. **Migration window**: 24h dual-mode dovolj, ali rabimo daljši?
4. **Test database**: kjer test? Sandbox kopija prod? Synthetic fixtures?
5. **Coordination z bot/discord upgrades**: Phase 3 menja query semantiko — ali Discord embed renders rabijo update?
6. **Saga timeout duration**: 1h dovolj? Real game session lahko zamuja >1h med Lua ingest in proximity flush?

---

## Reference

- RCA: [`docs/RCA_round_linker_architecture.md`](RCA_round_linker_architecture.md)
- Web research findings (sources at end of session report)
- Lua source: `vps_scripts/stats_discord_webhook.lua` (line 318-321 canonical match_id)
- Proximity tracker: `proximity/lua/proximity_tracker.lua` (header includes round_start_unix)
- ET server SSH: `puran.hehe.si:48101` (et user, key `~/.ssh/etlegacy_bot`)
