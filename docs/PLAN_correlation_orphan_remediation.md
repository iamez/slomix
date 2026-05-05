# Execution plan: Correlation orphan remediation

**Owner:** iamez  ·  **Created:** 2026-05-05  ·  **RCA:** [`docs/RCA_2026-04-21_correlation_orphans.md`](RCA_2026-04-21_correlation_orphans.md)

> **Namen tega dokumenta:** Self-contained playbook za izhod iz "prototype" faze problema z `round_correlations` tabele. Plan mora preživeti outage — če bot crash-a, če baza pade, če session se prekine, lahko kdorkoli (ali future-Claude) nadaljuje od **trenutne Phase**, brez dodatnega konteksta.
>
> **Problem v eni vrstici:** 168 logičnih matchov (33%) ima >1 correlation row, 104 pending orphan-i (11.6%), regresija od 2026-04-03 (commit `f701ee8`).
>
> **Preden začneš:** preberi RCA dokument. Razumi razliko med [Bug A](#bug-a-resolved) (rešen) in Bug B (več-faznji fix v tem planu).

---

## TL;DR Phase plan

| Fáza | Naloga | LOC | Risk | Outage potencial | Verify | Rollback |
|---|---|---|---|---|---|---|
| **A** | Deploy diag SQL fix | 1 | Z | Brez | curl + UI | git revert |
| **B** | Window 600s + Strategy 3 | ~30 | Z | Brez | unit + canary | git revert |
| **C** | Transaction wrap `_upsert_correlation` | ~10 | S | Bot crash če bug | regression test | git revert |
| **D** | Cleanup 168 dup grupe | ~50 SQL | S | **Data loss če bug** | snapshot diff | restore from backup |
| **E** | Periodic sweep task | ~40 | Z | Brez | observe 24h | disable feature flag |

**Prerekvizit za vsako fázo:** prejšnja je verificirana in stabilna **min. 24h** v produkciji.

**Risk legend:** Z=nizek, S=srednji, V=visok.

---

## Stanje danes (2026-05-05)

```bash
# Snapshot pred začetkom — preglej preden začneš katerokoli fázo
PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy <<'SQL'
SELECT
    'snapshot' AS marker,
    NOW() AS taken_at,
    (SELECT COUNT(*) FROM round_correlations) AS total_rows,
    (SELECT COUNT(*) FROM round_correlations WHERE status='pending') AS pending,
    (SELECT COUNT(*) FROM round_correlations
       WHERE status='pending' AND r1_round_id IS NULL AND r2_round_id IS NULL) AS orphans,
    (SELECT COUNT(*) FROM (
        SELECT SUBSTRING(match_id FROM 1 FOR 10) AS d, map_name, COUNT(*) AS c
        FROM round_correlations GROUP BY 1,2 HAVING COUNT(*) > 1
    ) x) AS multi_row_matches;
SQL
```

**Pričakovano (baseline):**
- total_rows ≈ 900
- pending ≈ 104
- orphans ≈ 104
- multi_row_matches ≈ 168

Če se vrednosti **dramatično razlikujejo**, nekdo je že delal cleanup ali se je nekaj zlomilo. **Ne nadaljuj brez razumevanja.**

---

## Bug A — RESOLVED (Phase 0)

**Diag SQL bug** v `website/backend/routers/diagnostics_router.py`. Štel correlation rows namesto distinct rounds-ov.

**Status:** ✅ Popravek je v repo-ju (vrstica ~679: `COUNT(DISTINCT r.id) FILTER (WHERE rc.id IS NOT NULL)`). **Aktivacija** zahteva `sudo systemctl restart etlegacy-web`.

**Verify po restartu:**
```bash
curl -s "http://localhost:8000/api/diagnostics/storytelling-completeness?session_date=2026-04-21" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['correlation_ratio'])"
# Pričakovano: 1.0
```

---

## Phase A — Deploy diag fix (immediate)

**Cilj:** Diag stran v UI prikaže pravilne številke za vse pretekle datume.

### Precondition
- [ ] Repo branch je `main`, working tree čist (ali je commit pripravljen).
- [ ] `etlegacy-web` service obstaja in je aktiven (`systemctl is-active etlegacy-web`).

### Steps
1. (Že done) Edit `website/backend/routers/diagnostics_router.py`: spremenil `COUNT(DISTINCT rc.id)` v `COUNT(DISTINCT r.id) FILTER (WHERE rc.id IS NOT NULL)`.
2. Commit: `fix(diag): correct rounds_correlated count in storytelling-completeness endpoint`.
3. **User action:** `sudo systemctl restart etlegacy-web`.
4. (Po restartu) syntax/log check: `journalctl -u etlegacy-web -n 20 --no-pager` — naj ne bo Python traceback-a.

### Verify
```bash
# Canary 1: endpoint vrne 200 + correlation_ratio=1.0 za znan kompleten dan
curl -sS "http://localhost:8000/api/diagnostics/storytelling-completeness?session_date=2026-04-21" \
  | python3 -m json.tool | head -20
# Canary 2: UI #/smart-stats-diag prikaže "OK — brez opozoril" za 2026-04-21
```

### Rollback
```bash
# Revert commit + restart. Diag stran bo prikazovala stare (napačne) številke,
# ampak ne bo crash-ala.
git revert HEAD
sudo systemctl restart etlegacy-web
```

### Outage runbook
- **Endpoint 500**: preglej `journalctl -u etlegacy-web -f`, najdi traceback. Najpogostejša napaka: typo v SQL. Revert.
- **Endpoint 404**: restart ni uspel. `systemctl status etlegacy-web`.
- **`{detail: "An internal error occurred"}`**: glej log za `ERROR | api.diagnostics`. Revert in repro lokalno.

---

## Phase B — Window 600s + Strategy 3 (preventive)

**Cilj:** Ustaviti **nove** orphan-e. Po tej fazi naj se nove orphan rows ne pojavljajo.

### Predicate test (pred fixom — pridobi baseline)
```bash
PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -tA -c "
SELECT COUNT(*) FROM round_correlations
WHERE created_at > NOW() - INTERVAL '7 days'
  AND status='pending' AND r1_round_id IS NULL"
# Zabeleži vrednost X (predvideno ~10).
```

### Implementation

**File:** `bot/services/round_correlation_service.py`

**Change 1 — `on_proximity_imported`** (line ~411):
```python
# Pred:
existing_cid = await self._find_nearby_correlation_id(match_id, map_name, round_number)
# Po:
existing_cid = await self._find_nearby_correlation_id(
    match_id, map_name, round_number, window_seconds=600
)
```

**Change 2 — Strategy 3** v `_find_nearby_correlation_id` (vstavi pred `return None` na koncu):
```python
# Strategy 3: round_id linkage (canonical, neodvisno od match_id timestamp)
# Najdi rounds.id z najbližjim round_start_unix za isti map+round_number,
# nato correlation čez (r1|r2)_round_id.
try:
    target_unix = int(target_dt.timestamp())
    round_match = await self.db.fetch_one(
        """SELECT id FROM rounds
           WHERE map_name = ?
             AND round_number = ?
             AND round_start_unix IS NOT NULL
             AND ABS(round_start_unix - ?) <= 1800
           ORDER BY ABS(round_start_unix - ?) ASC
           LIMIT 1""",
        (map_name, round_number, target_unix, target_unix),
    )
    if round_match:
        rid = round_match[0] if isinstance(round_match, (list, tuple)) else round_match.get('id')
        col = f"r{round_number}_round_id"
        cid_row = await self.db.fetch_one(
            f"""SELECT correlation_id FROM round_correlations
                WHERE {col} = ? LIMIT 1""",
            (rid,),
        )
        if cid_row:
            cid = cid_row[0] if isinstance(cid_row, (list, tuple)) else cid_row.get('correlation_id')
            logger.info(
                "[CORRELATION] Merging %s:%s into %s (strategy=round_id, rid=%d)",
                match_id, map_name, cid, rid,
            )
            return cid
except Exception as e:
    logger.debug(f"[CORRELATION] Strategy 3 failed: {e}")
```

### Pre-deploy unit tests (NEW file `tests/test_correlation_merge.py`)
```python
# Pseudo-test struktura — implementiraj s pytest + asyncpg fixtures
async def test_proximity_r2_merges_via_round_id():
    """Strategy 3: proximity R2 z drugačnim match_id se merge v obstoječ correlation."""
    # Setup: rounds row z round_start_unix=T, complete correlation s r2_round_id
    # Action: on_proximity_imported(match_id=T+300s, round_number=2)
    # Assert: ni nov correlation row, complete row dobi has_r2_proximity=TRUE

async def test_strategy_1_window_600_for_proximity():
    """Window=600 omogoči proximity merge tudi pri 5-min razliki."""
    # Setup: complete correlation z match_id=T
    # Action: on_proximity_imported(match_id=T+450s)
    # Assert: merge v obstoječi correlation_id

async def test_strategy_3_does_not_break_existing_lua_stats_merge():
    """Regresijski test: Lua/stats 3s merge še vedno deluje preko Strategy 1."""
```

### Steps
1. Implementiraj Change 1 + 2.
2. Napiši unit teste (vsaj 3).
3. Commit: `fix(correlation): widen proximity window + add round_id-based merge strategy`.
4. **User action:** `sudo systemctl restart etlegacy-bot`.
5. Spremlja log 30 min: `journalctl -u etlegacy-bot -f | grep -E '\[CORRELATION\].*strategy=round_id'`. Naj se pojavlja.

### Verify (24h po deploy)
```bash
# Canary: orphan rate /day
PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy -tA -c "
SELECT created_at::date AS day,
       COUNT(*) FILTER (WHERE status='pending' AND r1_round_id IS NULL) AS new_orphans
FROM round_correlations
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY day ORDER BY day DESC"
# Pričakovano: orphan-i v zadnjih 24h ≈ 0
```

### Rollback
```bash
git revert <phase_b_commit>
sudo systemctl restart etlegacy-bot
```
Bug se vrne, ampak ne škoduje obstoječim podatkom.

### Outage runbook
- **Bot ne starta**: import error v `round_correlation_service.py`. `systemctl status etlegacy-bot` pokaže traceback.
- **Bot starta, ampak crash pri prvem proximity event**: revert, raziskuj v sandboxu.
- **Strategy 3 daje napačen merge** (npr. dva back-to-back match-a istega map-a → premerge): pojav v logu kot `[CORRELATION] Merging ... strategy=round_id` z napačnim `correlation_id`. **Detection:** primerjaj `rounds.round_start_unix` med dvema match-ema za isti dan/map. Če gap < 30 min, je risk. Ublažitev: zožaj `ABS(round_start_unix - ?) <= 1800` na 600.
- **Hot rollback**: feature flag prek env var `CORRELATION_USE_STRATEGY_3=false` (TODO: implementiraj flag pred deploy-em).

---

## Phase C — Transaction wrap `_upsert_correlation`

**Cilj:** Reši **adjacent timestamp** orphan pattern (10+ primerov 3-9s gap-ov, ki bi morali merge-at preko Strategy 1, ampak ne).

**Hipoteza:** `_correlation_lock` zaščita ASYNC sequence znotraj enega Python event loopa, ampak `db.execute(INSERT)` + naslednji `db.fetch_one(SELECT)` lahko hodita skozi različne connection-e iz asyncpg pool-a. Drugi handler ne vidi neuncommitted INSERT prvega → ustvari nov row.

### Implementation

**File:** `bot/services/round_correlation_service.py`

```python
# Trenutno: vsak db.execute() je svoj transaction (autocommit).
# Cilj: wrap _find_nearby + INSERT + UPDATE v ENO connection / transakcijo.

async def _upsert_correlation(self, ...):
    async with self.db.acquire() as conn:    # NEW: acquire single connection
        async with conn.transaction():        # NEW: explicit BEGIN
            # _find_nearby uporablja conn (NE self.db)
            # INSERT uporablja conn
            # UPDATE uporablja conn
            # _recalculate_completeness uporablja conn
```

**Caveat:** treba refactorirati `self.db.execute / fetch_one` klice znotraj na variant ki sprejme `conn`. Ali pa: dodaj `_find_nearby_correlation_id` parametar `conn`, in spremeni vse SQL klice da ga uporabljajo.

**Test plan:**
1. Lokalno: simuliraj 2 sočasno prispevena event (`asyncio.gather(on_lua_teams_stored(...), on_round_imported(...))`).
2. Verify: samo 1 correlation row nastane.

### Steps
1. Implementiraj refactor.
2. Unit + integration test (sočasni event-i).
3. Commit: `fix(correlation): atomic upsert via explicit DB transaction`.
4. **User action:** `sudo systemctl restart etlegacy-bot`.

### Verify (7 dni po deploy)
```sql
-- Adjacent timestamp pari NE smejo več nastajati po deploy datumu
SELECT a.id, b.id, EXTRACT(EPOCH FROM (b.created_at - a.created_at))::int AS gap
FROM round_correlations a JOIN round_correlations b
  ON a.map_name = b.map_name
 AND ABS(EXTRACT(EPOCH FROM (b.created_at - a.created_at))) < 30
 AND a.id < b.id
WHERE a.status='pending' AND b.status='complete'
  AND a.match_id != b.match_id
  AND a.created_at > 'YYYY-MM-DD'  -- deploy datum
ORDER BY a.created_at DESC;
-- Pričakovano: 0 vrstic.
```

### Rollback
`git revert` + restart. Vrne na pred-tx stanje.

### Outage runbook
- **Bot crash s "connection pool exhausted"**: nove tx implementacija ne sprošča connection-ov. Revert.
- **Performance regresija**: tx je dlje držana — če `_recalculate_completeness` blokira pool, drugi callbacki čakajo. Mitigation: pre-compute completeness IZVEN tx, samo flag set v tx.

---

## Phase D — Cleanup obstoječih 168 dup grupe

**Cilj:** Pokoncati 168 dup correlation grupe. Po tej fazi naj bo `multi_row_matches = 0`.

### ⚠️ Critical preconditions
- [ ] **Phase B deploy ≥ 24h v produkciji, brez novih orphan-ov v zadnjih 24h.**
- [ ] **Snapshot baze**: `pg_dump -t round_correlations -t storytelling_kill_impact -t proximity_kill_outcome > backup_$(date +%Y%m%d).sql`
- [ ] **Sandbox kopija** za test:
  ```bash
  PGPASSWORD="etlegacy_secure_2025" createdb -h 127.0.0.1 -U etlegacy_user etlegacy_sandbox
  pg_restore --clean -h 127.0.0.1 -U etlegacy_user -d etlegacy_sandbox backup_*.sql
  ```
- [ ] User je explicit potrdil: "yes, run cleanup".

### Implementation

**File:** `tools/cleanup_correlation_duplicates.py` (NEW)

```python
#!/usr/bin/env python3
"""
Identificira dup correlation grupe (isti map+day, gap <30min)
in jih merge-a v complete row + briše orphan-e.

DRY-RUN by default. Pass --apply za actual writes.
"""
# Pseudo:
# 1. Najdi grupe (date, map) z >1 correlation row.
# 2. Za vsako grupo:
#    a. Identificiraj "canonical" row (status=complete + ima r1+r2_round_id).
#       Če več complete-ov: vzemi najstarejšega (najmanjši id).
#       Če nobeden ni complete: SKIP (manual review).
#    b. Za vsak ne-canonical row:
#       - Merge flag-e v canonical: `has_rN_proximity OR= ne_canonical.has_rN_proximity`,
#         enako za vse has_* flage.
#       - Recalculate `completeness_pct` in `status` na canonical.
#       - Foreign-key reassign: če kakšen drug stolpec referencira ne-canonical
#         correlation_id, posodobi (potrebno: preverim FK shemo).
#       - DELETE ne-canonical row.
# 3. Print summary: X groups merged, Y orphans deleted.
```

**Pre-flight FK check:**
```sql
-- Iskali smo katere tabele referencirajo round_correlations.correlation_id
SELECT
    tc.table_name, kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu USING (constraint_name)
WHERE tc.constraint_type = 'FOREIGN KEY'
  AND kcu.column_name LIKE '%correlation%';
```

**Naj NE briše**, če:
- Manjka canonical (vsi orphan-i).
- Najdejo se "razbeli" rows (Strategy 1 false positive — gap >30min).
- Več kot 5 rows v eni grupi (suspect 9-row outlier — ročna analiza).

### Steps
1. Napiši `tools/cleanup_correlation_duplicates.py` z `--dry-run` default.
2. Run dry-run na produkciji: `python3 tools/cleanup_correlation_duplicates.py --dry-run > cleanup_plan.txt`.
3. Diff `cleanup_plan.txt` ročno — izberi 5 random grup, preveri SQL action je smiselna.
4. Run dry-run na sandbox: `python3 tools/cleanup_correlation_duplicates.py --apply --db etlegacy_sandbox`.
5. Po sandbox uspehu, run na prod: `python3 tools/cleanup_correlation_duplicates.py --apply`.
6. Diff po-state: `multi_row_matches` mora biti ≈ 0, KIS+Smart Stats številke nespremenjene.

### Verify
```sql
-- Po cleanup-u
SELECT
    (SELECT COUNT(*) FROM round_correlations) AS total_after,
    (SELECT COUNT(*) FROM (
        SELECT SUBSTRING(match_id FROM 1 FOR 10) AS d, map_name, COUNT(*) AS c
        FROM round_correlations GROUP BY 1,2 HAVING COUNT(*) > 1
    ) x) AS multi_after;
-- Pričakovano: total ≈ 533 (= 900 - 168 dup pruned), multi = 0.

-- Critical: KIS suma za znano dan se NE spremeni
SELECT ROUND(SUM(total_impact)::numeric, 2)
FROM storytelling_kill_impact
WHERE session_date = '2026-04-21';
-- Pričakovano: 2108.01 (isto kot pred cleanup-om)
```

### Rollback
```bash
# CRITICAL: cleanup je destruktiven, revert preko file edit-a NE deluje!
PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy < backup_YYYYMMDD.sql
# Rollback obnovi pre-cleanup stanje.
```

### Outage runbook
- **Skript briše napačne rows**: takoj `sudo systemctl stop etlegacy-bot etlegacy-web` da preprečimo dodatno korupcijo, restoraj iz backup-a.
- **FK violation med DELETE**: skript ima bug, ne izčisti referencing rows prej. Revert iz backup-a, fix skript.
- **KIS sume se spremenijo po cleanup-u**: `storytelling_kill_impact.session_date` IS canonical, NE referencira `correlation_id`. Če se spremeni, nekaj je narobe — RESTORE.

---

## Phase E — Periodic sweep (self-healing)

**Cilj:** V primeru da se pojavi nov orphan (zaradi novega event vira ali edge case-a), sistem ga sam preverja in skuša merge-at, namesto da raste v tihem ozadju.

### Implementation

**File:** `bot/services/round_correlation_service.py`

```python
async def periodic_orphan_sweep(self):
    """Each hour: scan pending+orphan rows older than 1h, try late merge.
    Run via discord.ext.tasks.loop or asyncio task started in initialize()."""
    while True:
        try:
            orphans = await self.db.fetch_all("""
                SELECT correlation_id, match_id, map_name
                FROM round_correlations
                WHERE status='pending'
                  AND r1_round_id IS NULL AND r2_round_id IS NULL
                  AND created_at < NOW() - INTERVAL '1 hour'
                LIMIT 50
            """)
            for row in orphans:
                cid, mid, mn = row[0], row[1], row[2]
                async with self._correlation_lock:
                    target = await self._find_nearby_correlation_id(mid, mn, 0, window_seconds=1800)
                    if target and target != cid:
                        # Late merge: copy flags, delete orphan
                        await self._merge_orphan(cid, target)
                        logger.info(f"[SWEEP] Late-merged orphan {cid} into {target}")
        except Exception as e:
            logger.error(f"[SWEEP] Failed: {e}")
        await asyncio.sleep(3600)  # 1h cadence
```

**Feature flag** (env): `CORRELATION_PERIODIC_SWEEP=true|false` (default true po Phase D).

### Steps
1. Implementiraj `periodic_orphan_sweep` + `_merge_orphan` helper.
2. Test lokalno: ustvari sintetičen orphan, počakaj 1h (ali skrajšaj sleep za test), preveri da se merge-a.
3. Commit: `feat(correlation): periodic orphan sweep task`.
4. **User action:** `sudo systemctl restart etlegacy-bot`.

### Verify (1 teden po deploy)
```sql
-- Orphan-i ne smejo akumulirati
SELECT COUNT(*) FROM round_correlations
WHERE status='pending' AND r1_round_id IS NULL
  AND created_at < NOW() - INTERVAL '24 hours';
-- Pričakovano: ≈ 0
```

### Rollback
Disable feature flag: `export CORRELATION_PERIODIC_SWEEP=false` + restart.

### Outage runbook
- **Sweep popušča DB**: `LIMIT 50` per cadence omeji blast radius. Če še zmeraj problem, postavi flag false.
- **Sweep daje napačne merge-e**: glej log-e za `[SWEEP] Late-merged`, primerjaj merged correlation_id vs orphan match_id. Če suspekten, disable flag.

---

## Globalni outage matrika

| Symptom | Verjetna faza | Action |
|---|---|---|
| Bot ne starta po deploy | B / C / E | `journalctl -u etlegacy-bot -n 50`; revert zadnji commit; restart |
| Web 500 na diag endpointu | A | Revert; preglej tracback v `journalctl -u etlegacy-web` |
| Smart Stats UI prikazuje napačno KIS sumo | D (cleanup šel narobe) | RESTORE iz backup-a; **ne nadaljuj** dokler ni razumeti |
| `round_correlations` rows raste hitreje kot pred fix-om | B / C | Možen merge logic infinite loop; preglej log; revert |
| Diag UI pokaže `correlation_ratio` < 1.0 za znan kompleten dan | A or B regresija | Preveri SQL v endpointu vs spec; revert |
| Discord bot spamiranje "[CORRELATION] error" | B / C / E | Disable feature flag (če implementirano); ali revert |

## Kontakt + escalation

- Primary: iamez (samba@samba.local user)
- Logs: `journalctl -u etlegacy-bot -u etlegacy-web -f`
- DB: `PGPASSWORD="etlegacy_secure_2025" psql -h 127.0.0.1 -U etlegacy_user -d etlegacy`
- Backup location: `/home/samba/share/slomix_discord/backups/`
- Service control: `sudo systemctl {start|stop|restart|status} etlegacy-{bot|web}`

## Doc lifecycle

- **Update tega dokumenta po vsaki fázi** — popravi "Status" v glavnem table-u, doda observation.
- **Ko je vse 5 faz done**, premakni v `docs/archive/` z naslovom `RESOLVED_correlation_orphan_remediation.md`.
- Linkaj v `docs/CHANGELOG.md` ko phase D+E mergeni.
