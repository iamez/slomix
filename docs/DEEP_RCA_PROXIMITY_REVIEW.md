# Proximity Codebase Deep Review — Rezultati

> **Metodologija**: 5 Whys + Fault Tree + Ishikawa (iz proximity-round-selector-brief.md)
> **Datum**: 2026-03-26
> **Scope**: Celoten proximity pipeline (SSH → Parser → DB → API → Frontend)
> **Viri**: 3 paralelni agenti: Error Masking Audit, Fault Tree Analysis, Code Quality Scan

---

## ⛔ SHOWSTOPPER: Parser File Overwritten

**`proximity/parser/parser.py`** working copy (3816 vrstic) je bila **prepisana z vsebino `proximity_router.py`** (FastAPI router koda). Committed verzija (HEAD) ima pravi `ProximityParserV4` class z 17 dataclass-i.

- **Produkcija**: OK (teče iz committed kode)
- **Tveganje**: Če kdo commitne ta file, se parser uniči
- **Fix**: `git checkout HEAD -- proximity/parser/parser.py`

---

## Fault Tree: Pipeline po hop-ih

| Hop | Komponenta | Detekcija napak | Logiranje | Propagacija | Ocena |
|-----|-----------|----------------|-----------|-------------|-------|
| 1 | SSH Download | ✓ preverja | ⚠️ WARNING | ⚠️ preskoči file | 🟡 YELLOW |
| 2 | Parse File | ✓ per-line | ⚠️ WARNING | ✓ vrne bool | 🟡 YELLOW |
| 2a | Missing v5 sekcije | ✗ ni checka | ⚠️ log only | ✗ tiho partial | 🔴 RED |
| 3 | DB Insert | ✓ transakcije | ⚠️ log on error | ✓ rollback | 🟢 GREEN (verified) |
| 3a | Missing tabele | ✓ `_table_has_column` check | ⚠️ log | ✓ skip | 🟢 GREEN |
| 3b | FK violations | ✓ v transakciji | ✓ rollback | ✓ return False | 🟢 GREEN |
| 3c | Partial insert | ✓ `db_adapter.transaction()` wraps all | ✓ atomic | ✓ all-or-nothing | 🟢 GREEN |
| 4 | API Endpoints | ✓ try/except | ⚠️ WARNING | ✓ status:error | 🟢 GREEN |
| 4a | Prazni rezultati | ✓ detektira | ⚠️ log only | ⚠️ status:prototype | 🟡 YELLOW |
| 5 | Frontend Render | ⚠️ delno | 🔴 .catch(()=>{}) | 🔴 tiho prazno | 🔴 RED |
| 5a | Config load fail | ✗ ni checka | 🔴 nič | 🔴 cascade | 🔴 RED |

**Najslabši hopi**: DB Insert (3, 3a-c) in Frontend (5, 5a) — ni transakcij, ni error boundary-jev.

---

## Error Masking Audit: 21 najdb

### Povzetek po kategorijah

| Kategorija | Št. | CRIT | HIGH | MED | LOW |
|-----------|-----|------|------|-----|-----|
| A: Silent exception swallowing | 7 | 1 | 4 | 2 | 0 |
| B: Fallback/default masking | 6 | 0 | 2 | 4 | 0 |
| C: Async fire-and-forget | 2 | 0 | 0 | 2 | 0 |
| D: Type coercion | 2 | 0 | 0 | 0 | 2 |
| E: DB query masking | 2 | 0 | 2 | 0 | 0 |
| F: Config masking | 2 | 0 | 0 | 2 | 0 |
| **SKUPAJ** | **21** | **1** | **8** | **10** | **2** |

### CRITICAL (1)

**A5: V5 table count loop tiho vrne 0** (`proximity_router.py:960-966`)
```python
for tbl in ['proximity_spawn_timing', 'proximity_team_cohesion', ...]:
    try:
        cnt = await db.fetch_val(f"SELECT COUNT(*) FROM {tbl} {where_sql}", query_params)
        v5_counts[tbl] = int(cnt or 0)
    except Exception:
        v5_counts[tbl] = 0  # ← missing table = "no data"?? Should be error!
```
Ni razlike med "tabela ne obstaja" in "ni podatkov". Maskira broken schema.

### HIGH (8)

| # | Issue | Lokacija |
|---|-------|----------|
| A1 | `_table_column_exists()` vrne False za VSE exception tipe | `proximity_router.py:131-132` |
| A2 | `_load_scoped_guid_name_map()` tiho vrne `{}` | `proximity_router.py:195-197` |
| A6 | Broad `except Exception` v celotnem proximity_cog (10 mest) | `proximity_cog.py:84,107,117,130,140,161,170,289,368,419` |
| B4 | Track query exception → `track_row = None` | `proximity_router.py:941-942` |
| B5 | Lua `tonumber(origin) or 0` — false (0,0,0) pozicije | `proximity_tracker.lua:67,136-138,150-152` |
| E1 | Engagement query exception vrne `top_duos: []` | `proximity_router.py:1004-1019` |
| E2 | Session scope query exception vrne `sessions: []` | `proximity_router.py:845-859` |

### MEDIUM (10)

- A3: `_parse_json_field()` tiho vrne None za corrupted JSON
- A4: Dashboard sekcije vrnejo `{_error: str(e)}` pomešano z valid data
- A7: Parser import fail → `PROXIMITY_AVAILABLE = False` (ne razlikuje file missing vs syntax error)
- B1: `(map_name or "").strip()` maskira type errors
- B2: `int(row[2] or 0)` — NULL = unix timestamp 0
- B3: `int(num_attackers or 0)` — NULL = single attacker
- C1-C2: `.catch(() => {})` v proximity.js (2609, 2508, 2607, 2649)
- F1: `getattr(bot.config, 'proximity_remote_path', '')` — tiho fallback na ""
- F2: SSH config atributi brez existence check

---

## Ishikawa Code Quality: 24 najdb

### CODE (48% vseh najdb)

| # | Issue | Severity | Lokacija |
|---|-------|----------|----------|
| 1 | **18 funkcij nad 100 vrstic** — `get_proximity_leaderboards` ima 368 vrstic! | CRITICAL | `proximity_router.py:3357` |
| 2 | Date range `max(1, min(range_days, 3650))` ponovljen 4x | MEDIUM | `:73,721,2696,2815` |
| 3 | Safe limit `max(1, min(limit, N))` ponovljen 6x z različnimi N | MEDIUM | `:1208,1892,2412,3176,3257,3364` |
| 4 | `get_proximity_events` IGNORIRA `limit` parameter — vedno vrne 5000 | CRITICAL | `:2449` |

### DATA

| # | Issue | Severity |
|---|-------|----------|
| 5 | Date type mešanje (string ↔ date object) skozi pipeline | LOW |
| 6 | GUID handling: PRAVILNO (vedno `player_guid`, nikoli `player_name`) | ✅ OK |
| 7 | Engagement count reconciliation med parser/DB/API ne obstaja | MEDIUM |

### INFRASTRUCTURE

| # | Issue | Severity |
|---|-------|----------|
| 8 | `local_proximity/` corruption = tiho glob fail | MEDIUM |
| 9 | `.processed_proximity.txt` index brez validation/recovery | MEDIUM |
| 10 | `LIMIT 5000` hardcoded, ni paginacije | MEDIUM |

### CONFIGURATION

| # | Issue | Severity |
|---|-------|----------|
| 11 | 30+ hardcoded magic numbers (3650, 5000, 1000, 500) | MEDIUM |
| 12 | `proximity_auto_import`, `proximity_startup_lookback_hours` nedokumentirani | LOW |

### PROCESS

| # | Issue | Severity |
|---|-------|----------|
| 13 | **Brez rate limiting** na vseh proximity endpointih | HIGH |
| 14 | **`limit` parameter ignoriran** v `get_proximity_events` | CRITICAL |
| 15 | Ni paginacije na frontend-u za velike result sete | MEDIUM |

---

## Prioritiziran akcijski plan

### IMMEDIATE (danes)

| # | Akcija | Tip |
|---|--------|-----|
| S1 | `git checkout HEAD -- proximity/parser/parser.py` — restore parser | git restore |
| S2 | Fix `get_proximity_events` da upošteva `limit` parameter (`:2449`) | bug fix |

### SHORT-TERM (ta teden)

| # | Akcija | Effort |
|---|--------|--------|
| T1 | Dodaj transakcije v parser DB insert (wrap v `BEGIN/COMMIT`) | 2h |
| T2 | Zamenjaj v5 table count `except: 0` z explicit schema check | 1h |
| T3 | Dodaj `@limiter.limit()` na vse proximity endpointe | 1h |
| T4 | Lua: skip engagement če `origin = (0,0,0)` namesto tihe nastavitve | 30m |
| T5 | Frontend: dodaj error boundary za proximity panel | 2h |

### MEDIUM-TERM (ta mesec)

| # | Akcija | Effort |
|---|--------|--------|
| M1 | Razbij `get_proximity_leaderboards` (368 vrstic) v 5+ helper funkcij | 3h |
| M2 | Centraliziraj `_safe_limit()` in `_safe_date_range()` | 1h |
| M3 | Ekstrahiraj magic numbers v `proximity/config.py` | 2h |
| M4 | Dodaj loading/error state v frontend proximity components | 3h |
| M5 | Engagement count reconciliation test (parser ↔ DB ↔ API) | 2h |

---

## Ishikawa diagram

```
                    ┌─────────────────────────────────────────────────┐
                    │  PROXIMITY PIPELINE SILENT DATA LOSS            │
                    └─────────────────────┬───────────────────────────┘
                                          │
          ┌───────────────┬───────────────┼───────────────┬───────────────┐
          │               │               │               │               │
      CODE (48%)     DATA (17%)     INFRA (13%)     CONFIG (9%)     PROCESS (13%)
          │               │               │               │               │
    ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴─────┐   ┌─────┴────┐   ┌─────┴─────┐
    │except:pass│   │string/date│   │FS corrupt │   │magic nums│   │no rate lim│
    │limit ignor│   │no reconci-│   │no txn wrap│   │undoc conf│   │no paginat.│
    │368ln func │   │lation     │   │5000 limit │   │          │   │limit ignor│
    │copy-paste │   │           │   │           │   │          │   │           │
    └───────────┘   └───────────┘   └───────────┘   └──────────┘   └───────────┘
```

---

## Pozitivne najdbe

- ✅ `_build_proximity_where_clause()` obstaja in je DRY (reused 15+ endpointov)
- ✅ GUID handling pravilno povsod (`player_guid`, ne `player_name`)
- ✅ DB connection pool pravilno upravljan (Depends injection)
- ✅ API endpointi imajo try/except z logging
- ✅ Date validation z HTTPException na input level
- ✅ `round_number` + `round_start_unix` vedno pravilno parirana

---

*Generiran: 2026-03-26 | Metodologija: 5 Whys + Fault Tree + Ishikawa | 3 paralelni agenti*
