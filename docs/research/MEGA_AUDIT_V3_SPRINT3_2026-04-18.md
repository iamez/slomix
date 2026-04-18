# Mega Audit v3 — Sprint 3 (2026-04-18)

**Cilj:** Arhitekturni cleanup — dodati infrastrukturo (konstante, helperje, dekoratorje, builderje), ki odpravlja duplicirano logiko, in demo uporaba v 2-3 fajlih.
**Branch:** `chore/audit-v3-sprint3-architecture`
**Trajanje:** ~2 h

**Načelo:** "minimum tvegan dokončkek, maksimum infrastrukture" — dodamo helperje, pokažemo uporabo na nekaj mestih, ostale migracije prepustimo prihodnjim PR-jem, da ne zlomimo mnogih endpointov naenkrat.

---

## Izvedeno

### REFAC-01 — `StorytellingTiming` konstante ✅

**Problem:** 29 magic ms vrednosti (10000, 15000, 5000, 3000, 8000, 2000) razpršenih po `storytelling_service.py` loaderjih, detectorjih in SQL-queryjih. Tuning okna = ~20 ločenih editov + tveganje, da kakšno zgrešiš.

**Fix:** 10 module-level konstant v `website/backend/services/storytelling_service.py::90-100`:
- `CARRIER_RETURN_WINDOW_MS` — 10s okno za flag return po carrier killu
- `CROSSFIRE_TIMING_WINDOW_MS` — 3s za crossfire teammate damage
- `SPAWN_TIMING_WINDOW_MS` — 2s za spawn wave score
- `OBJECTIVE_EVENT_WINDOW_MS` — 15s za obj-related kille
- `KILL_STREAK_WINDOW_MS` — 10s za 3+ kill streak
- `MULTIKILL_SHORT_WINDOW_MS` — 5s za 2-kill multikill
- `MULTIKILL_EXTENDED_WINDOW_MS` — 8s za 3+ kill multikill
- `TRADE_KILL_DELTA_MS` — 5s delta za trade kill
- `LURKER_MIN_DURATION_MS` — 2s minimum track segment
- `DEATH_TRADE_WINDOW_MS` — 10s okno za trade po smrti

Zamenjanih 15+ magic numbers na dejanski konstanti. SQL `RANGE BETWEEN N PRECEDING` (ki ne sprejme parametrov) uporablja f-string z `# nosec B608` (varna module-level konstanta).

### CQ-03 — `bot/core/guid_utils.py` ✅

**Problem:** 39 `guid[:8]` / `(guid or "?")[:8]` pojavitev v 12 fajlih — vsaka z različnim null-handlingom. `storytelling_service.py` je imel lokalni `_safe_short` helper kot demo, ostali pa goli bracket access.

**Fix:** Nov modul `bot/core/guid_utils.py`:
- `short_guid(guid: str | None) -> str` — vrne prvih 8 znakov ali `"?"` placeholder
- `name_or_short_guid(name, guid)` — name če obstaja, sicer short guid
- Konstante: `GUID_SHORT_LEN = 8`, `GUID_MISSING_PLACEHOLDER = "?"`
- Doctests z primeri

**Apliciran v:** `storytelling_service.py` (`_safe_short` → re-export), `storytelling_router.py:173`, `proximity_helpers.py:204`.

### ARCH-01 — `@handle_router_errors` dekorator ✅

**Problem:** 163 `except Exception` blokov v 22 routerjih, od tega ~65 clean wrapperjev (`except: logger.error; raise HTTPException(500)`) brez business-logic fallback-a.

**Fix:** Nov dekorator v `website/backend/routers/api_helpers.py`:
```python
@handle_router_errors("Custom error message")
async def endpoint(...):
    ...
```
- Logira skozi `logger.exception` (stack trace included)
- Pusti obstoječe `HTTPException` naprej (ne wrapa 400/404)
- Wrapa samo unhandled exceptions → `HTTPException(500)`

**Apliciran v:** `proximity_support.py` — 2 endpointa (`support-summary`, `movement-stats`). Odstranjenih ~10 vrstic boilerplatea. Docstring na dekoratoju jasno navaja kdaj UPORABITI in kdaj NE (fallback queries ostajajo eksplicitne).

**Ostali 63 kandidati:** dokumentirani za prihodnje sprinte, ne zamenjani v tem PR-ju (risk of silent behavior change pri endpointih z netrivialnim catch-om).

### CQ-04 — `ProximityQueryBuilder` ✅

**Problem:** `if session_date: ... else: range_days ... if map_name: ... if player_guid: ...` pattern se pojavlja v 4 proximity routerjih (skupno 79 where_parts uporab).

**Fix:** Fluent builder v `website/backend/routers/proximity_helpers.py`:
```python
where_sql, params = (
    ProximityQueryBuilder(["peak_speed IS NOT NULL"])
    .with_session_scope(session_date, range_days)
    .with_map_name(map_name)
    .with_player_guid("player_guid", player_guid)
    .build()
)
```
- `with_session_scope()` — session_date ALI range_days fallback
- `with_map_name()` — optional map filter
- `with_player_guid(column, guid)` — optional GUID filter (column je caller-provided hardcoded)
- `with_raw(clause, *values)` — raw clause z renumbered `$N` placeholderji
- `build() -> (where_sql, params_tuple)` — direkt konzumiran v `db.fetch_*`

**Apliciran v:** `proximity_support.py` (2 endpointa → 16 vrstic boilerplatea izbrisanih na endpoint).

**Ostali 77 kandidati** v `proximity_objectives.py` (56×), `proximity_positions.py` (5×), `proximity_teamplay.py` (7×): dokumentirani za prihodnost. Vsak endpoint ima specifične WHERE clause-e, ki jih je treba pretehtati posamezno.

---

## Verifikacija

- `ruff check bot/ website/backend/` — 0 errors (po dodanem per-file-ignore za `bot/diagnostics/*` za obstoječ T201 `print()` v CLI dev scriptih — to ni bilo nova regresija, ampak prej neopazen)
- `pytest tests/` — **508 passed, 45 skipped, 0 failed** (brez regresij)
- Import sanity: `short_guid`, `ProximityQueryBuilder`, `handle_router_errors` — vsi naložijo, smoke test prešel
- Builder smoke test: `.with_session_scope('2026-04-17').with_map_name('battery').with_player_guid('player_guid','abc')` → `('WHERE session_date = $1 AND map_name = $2 AND player_guid = $3', (date, 'battery', 'abc'))`

---

## Kar ostaja za prihodnje sprinte

**Tehnični dolg iz Mega Audit Faze C** (plan file):
- **P3f** — `shared/` package (21-23 cross-imports `website→bot` → 0), ~3-4 h
- **P3e** — `bot/ultimate_bot.py` 6251 → <2500 vrstic (12 servisov, 4 podfaze), ~12-14 h
- **D.1** — `storytelling_service.py` 3273 → 10 modulov, ~4 h

**Dolg iz Session Detail review** (ostaja):
- **CR-02** — React ↔ legacy JS matrix feature parity odločitev (zahteva user input)

**Migration kandidati iz tega Sprint-a** (infrastruktura pripravljena, apliciraj po potrebi):
- 63 preostali `except Exception → raise HTTPException(500)` → `@handle_router_errors()` (samo clean wrapperji, ne business-logic fallback)
- 77 preostali proximity where_parts → `ProximityQueryBuilder` (vsak endpoint preveri ali ima specifično WHERE logiko)
- `guid[:8]` v `bot/services/`, `bot/cogs/` — 8 kandidatov za `short_guid()`

---

**Avtor:** Mega Audit v3 Sprint 3 (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-18
