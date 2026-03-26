# Deep Root Cause Analysis — Audit Plan

> **Metodologija**: 5 Whys + Fault Tree + Ishikawa kategorije
> **Generiran**: 2026-03-26
> **Viri**: Codebase scan (23 najdb, 20+ datotek), Log analiza (13 issues, 6 logov), RCA research

---

## Prioritiziran seznam (CRITICAL -> LOW)

### TIER 1: CRITICAL — Aktivna izguba podatkov ali broken features

| # | Issue | Lokacija | Status |
|---|-------|----------|--------|
| C1 | ~~Filesystem corruption `local_proximity/`~~ — active dir works (92 files, write OK), `local_proximity_broken/` has 3 corrupted inodes | `local_proximity/` dir | **RESOLVED** (prod OK) |
| C2 | ~~Promise.allSettled brez error checkinga (app.js)~~ — now logs rejected promises with console.error | `website/js/app.js:736` | **FIXED** |
| C3 | ~~Promise.allSettled brez error checkinga (session-detail.js)~~ — .value access now guarded with fulfilled check | `website/js/session-detail.js:675,1839` | **FIXED** |

#### C1: Filesystem corruption `local_proximity/`
**5 Whys**:
1. Zakaj proximity data ne prihaja? → SSH download faila z errno 117
2. Zakaj errno 117? → Filesystem inode corruption na direktoriju
3. Zakaj corruption? → Unclean shutdown (power outage 2026-03-25)
4. Zakaj ni self-healing? → ext4 ne popravi corruption brez fsck
5. Zakaj bot ne detecta in alertne? → Ni filesystem health checka

**Fix**: `mv local_proximity local_proximity_broken2 && mkdir local_proximity`
**Preventiva**: Dodaj filesystem write test v bot startup health check

#### C2: app.js critical startup loads
**5 Whys**:
1. Zakaj se stran naloži brez podatkov? → Promise.allSettled požre rejection
2. Zakaj se ne preveri rejection? → Noben `.status === 'rejected'` check
3. Zakaj allSettled namesto Promise.all? → Da en failure ne uniči vseh
4. Zakaj ni kompromisa? → Manjka error reporting za failed critical loads
5. Root cause: **Missing error boundary za critical vs optional loads**

**Fix**: Razdeli v `Promise.all(critical)` + `Promise.allSettled(optional)`, ali dodaj rejection logging

---

### TIER 2: HIGH — Degradirana funkcionalnost

| # | Issue | Lokacija | Status |
|---|-------|----------|--------|
| H1 | ~~Proximity date type bug (7 endpointov)~~ | `proximity_router.py` v6 endpoints | **FIXED danes** |
| H2 | ~~Endstats infinite retry loop~~ | `bot/ultimate_bot.py` polling path | **FIXED danes** |
| H3 | ~~Round linker mass failures~~ — was 329, now 14 (9 abandoned, 5 recent) | `bot/core/round_linker.py` | **CLEANED** |
| H4 | ~~session_teams privilege error~~ — GRANT DELETE,INSERT,UPDATE,SELECT executed | `sessions_router.py`, DB permissions | **FIXED** |
| H5 | ~~stats_webhook_notify race condition~~ — `_in_flight` set z atomic check-and-claim pod `_state_lock` | `vps_scripts/stats_webhook_notify.py:174-180` | **FIXED** |

#### H3: Round linker 329 failures
**5 Whys**:
1. Zakaj 329 rund nima endstats? → Round linker ne najde match v 45-min window
2. Zakaj ne najde? → `best_diff_s=518918` = kandidati so 6 dni stari
3. Zakaj stari kandidati? → Endstats pride za rundo ki je bila bot-only (ni v rounds tabeli)
4. Zakaj bot-only runda ni v rounds? → c0rnp0rn8.lua preskoči bote brez weapon activity → header-only stats file → `is_file_processed` bug označi kot success
5. Root cause: **Celotna veriga od broken waypoints do phantom processed_files** (fiksano danes, ampak 329 starih rund ostane unresolved)

**Fix**: Cleanup script ki za unresolved endstats z `best_diff_s > 86400` označi kot abandoned

#### H4: session_teams privileges
**5 Whys**:
1. Zakaj team detection ne deluje? → All players v Team B, none v Team A
2. Zakaj? → Team seeding da Team1=0, Team2=2 players
3. Zakaj je seed napačen? → Cache v session_teams ni posodobljen
4. Zakaj ni posodobljen? → website_app nima DELETE privilege na session_teams
5. Root cause: **Table ownership mismatch** — session_teams owned by etlegacy_user

**Fix**: `GRANT DELETE, INSERT, UPDATE ON session_teams TO website_app;`

---

### TIER 3: MEDIUM — Tihe napake, resource waste

| # | Issue | Lokacija | Status |
|---|-------|----------|--------|
| M1 | ~~Website restart loop~~ — uvicorn now runs WITHOUT --reload (verified). Historical issue, no longer active. | systemd service config | **RESOLVED** |
| M2 | ~~Discord API rate limit crash loop~~ — discord.py 2.3.2 has built-in exponential backoff. 1,727 failures were from external restart script, not bot logic. | `bot/ultimate_bot.py` reconnect logic | **NOT A CODE BUG** (operational) |
| M3 | ~~R2 differential OMNIBOT0 fallback~~ — already fixed in parser (line 1298-1300: name-hash unique GUID). 72 events are pre-fix legacy data. | `bot/community_stats_parser.py` | **ALREADY FIXED** |
| M4 | ~~FK constraint violations round_correlations~~ — 104 both-null + 46 r1-null are expected incomplete matches (not FK violations). Service works correctly. | `bot/services/round_correlation_service.py` | **NOT A BUG** |
| M5 | ~~Fallback query masking (auth.py)~~ — 4 handlers now log warnings | `website/backend/routers/auth.py:499,645` | **FIXED** |
| M6 | ~~Session player stats empty fallback~~ — 2 handlers now log warnings | `website/backend/routers/sessions_router.py:191` | **FIXED** |
| M7 | ~~_table_column_exists vrne False za VSE exception tipe~~ | `proximity_router.py:116-132` | **FIXED** (A1 fix — now logs warning) |
| M8 | ~~Tag insertion tihe napake~~ — now tracks + returns failed tags | `website/backend/routers/uploads.py:176` | **FIXED** |
| M9 | ~~reprocess_missing_endstats marks success BEFORE validation~~ | `scripts/reprocess_missing_endstats.py:163` | **FALSE POSITIVE** — mark is AFTER all INSERTs |
| M10 | ~~Growing unimported file backlog~~ — 333 = 216 endstats (separate pipeline) + 117 weapon stats (ignored by design). **0 regular stats unprocessed.** | `local_stats/` | **FALSE POSITIVE** |

---

### TIER 4: LOW — Code smells, minor issues

| # | Issue | Lokacija |
|---|-------|----------|
| L1 | ~~Timezone parsing silent UTC fallback~~ | `availability.py:118` — **FIXED** (added logger.warning) |
| L2 | ~~JSON parsing silent None return~~ | `proximity_router.py:465` — **FIXED** (A3 fix) |
| L3 | ~~Session cache brez TTL/invalidation~~ — 5-min TTL dodano | `session-detail.js:671` — **FIXED** |
| L4 | ~~OSError silent pass v greatshot_store~~ | `greatshot_store.py:53` — **FIXED** (added logger.warning) |
| L5 | Missing synergy_analytics module (vsak startup) | NOT A BUG — module exists, warning is expected |
| L6 | ~~`!last_session` 16s za nekatere userje~~ — query je 0.4ms z obstoječimi indexi, ni problem | Query performance — **NOT A BUG** |

---

## Execution Plan

### Faza 1: Immediate Fixes (30 min)
- [ ] **C1**: Fix filesystem corruption (`mv` + `mkdir`)
- [ ] **H4**: Grant permissions na session_teams
- [ ] **M1**: Preveri ali website teče z `--reload` in odstrani

### Faza 2: Error Masking Audit Script (avtomatizirano)
Grep-based scan za 6 kategorij error masking patternov:

```bash
# Kategorija A: Silent exception swallowing
rg "except.*:$" --type py -A1 | grep -E "pass$|continue$"
rg "except Exception" --type py -A2 | grep -E "return \[\]|return \{\}|return None|return False"

# Kategorija B: Fallback/default masking
rg "or \[\]|or \{\}|or \"\"| or 0| or None" --type py
rg "COALESCE" --type sql

# Kategorija C: Async fire-and-forget
rg "create_task" --type py | grep -v "await"
rg "allSettled" --type js -A3 | grep -v "rejected\|status.*===\|reason"

# Kategorija D: Type coercion
rg "params\.append\(session_date\)" --type py  # string vs date
rg "== " --type ts  # loose equality

# Kategorija E: DB query masking
rg "except.*:" --type py -A1 -B3 | grep -B4 "return \[\]" | grep "fetch"

# Kategorija F: Config masking
rg "os\.getenv\(" --type py | grep -v "raise\|assert\|if not"
```

### Faza 3: Fault Tree za kritične data paths (manualno)
Za vsak critical path naredi fault tree:

1. **Stats Pipeline**: SSH poll → download → parse → DB insert → rounds table → session assignment
2. **Endstats Pipeline**: SSH poll → download → round linkage → DB insert → processed_endstats_files
3. **Proximity Pipeline**: SSH poll → download → parse → 19 tabel → API → frontend
4. **Auth Flow**: Discord OAuth → callback → user_player_links → session
5. **Team Detection**: Round data → team seeding → session_teams cache → API → frontend

Za vsak hop: Kaj se zgodi ob failure? Ali se logira? Ali se propagira?

### Faza 4: Canary Queries (scheduled)
Periodični integrity checki:

```sql
-- Vsaka runda mora imeti gaming_session_id
SELECT COUNT(*) FROM rounds WHERE gaming_session_id IS NULL AND round_date > CURRENT_DATE - 7;

-- Processed files z success=TRUE morajo imeti player data
SELECT COUNT(*) FROM processed_files pf
WHERE pf.success = TRUE AND pf.processed_at > CURRENT_DATE - 7
AND NOT EXISTS (SELECT 1 FROM player_comprehensive_stats WHERE round_date = LEFT(pf.filename, 10));

-- Endstats z round_id=NULL (stuck)
SELECT COUNT(*) FROM processed_endstats_files WHERE round_id IS NULL AND success = TRUE AND processed_at > CURRENT_DATE - 7;

-- session_teams freshness
SELECT MAX(created_at) FROM session_teams;
```

### Faza 5: Structural Improvements (dolgorocno)
- [ ] `mypy --strict` na critical Python modulih
- [ ] Error boundary v JS (critical vs optional loads)
- [ ] Structured logging s correlation IDs
- [ ] Exponential backoff na vseh retry loopih
- [ ] `_build_proximity_where_clause` za VSE proximity endpointe (eliminiraj copy-paste)

---

## Ishikawa kategorije (za tracking)

| Kategorija | Najdb | Primeri |
|-----------|-------|---------|
| **Code** | 11 | Copy-paste WHERE, missing null checks, silent pass |
| **Data** | 5 | String→date coercion, OMNIBOT0 shared GUID, phantom processed_files |
| **Infrastructure** | 3 | Filesystem corruption, connection pool, --reload loop |
| **Configuration** | 2 | Table permissions, missing module |
| **Process** | 2 | No max retry, no startup health check |
| **Dependencies** | 0 | (none found) |

**Dominant kategorija: Code (48%)** — glavni vir bugov je error swallowing in copy-paste koda.

---

## Ze popravljeno danes (2026-03-26)

| Issue | Fix |
|-------|-----|
| ~~H1: Proximity date type bug~~ | `_parse_iso_date()` na vseh 7 mestih |
| ~~H2: Endstats infinite retry~~ | Max 5 attempts + DB marking |
| ~~is_file_processed false positive~~ | `AND success = TRUE` |
| ~~361 phantom DB entries~~ | Batch UPDATE na success=FALSE |
| ~~Revives endpoint~~ | `created_at` date filtering |
| ~~Sessions KeyError~~ | `.get()` z defaults |
| ~~Game server mapcycle~~ | Removed broken waypoint maps |
| ~~Composite endpoint~~ | 31 req → 2-3 req (90% reduction) |
| ~~A1: _table_column_exists silent~~ | Added `logger.warning` with table/column names |
| ~~A2: _load_scoped_guid_name_map silent~~ | Upgraded to `logger.error` with context |
| ~~A3: _parse_json_field silent None~~ | Added `logger.warning` for corrupted JSON |
| ~~A5/M7: v5 table count except:0~~ | Added `logger.warning` with table name |
| ~~B4: Track query silent None~~ | Added `logger.warning` for failed query |
| ~~E1: Engagement query silent empty~~ | Added `logger.error` before fallback response |
| ~~E2: Session scope query silent empty~~ | Added `logger.error` before fallback response |
| ~~C1-C2: .catch(() => {}) in proximity.js~~ | Replaced 4 instances with `console.warn` |
| ~~S1: Parser file overwritten~~ | `git checkout HEAD -- proximity/parser/parser.py` |
| ~~P2: rating_class never populated~~ | `get_tier()` + server-side tier in `compute_and_store_ratings` |
| ~~P3: History never tracked~~ | `player_skill_history` now written on each recalc |
| ~~P6: No history API~~ | `GET /api/skill/player/{id}/history` with session/map drill-down |
| ~~P4: No confidence indicator~~ | `confidence = min(1.0, games_rated/30)` in API response |
| Migration 030 | Added session_date, map_name, scope to player_skill_history |
| Skill rating recalc | 40 players rated, tiers assigned, history populated |
