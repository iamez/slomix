# Mega Audit v3 — Sprint 2.5 (2026-04-17)

**Cilj:** Matrix cleanup — odpraviti dolg iz PR #79 (CR-04, CR-05, CR-07 iz review dokumenta).
**Branch:** `chore/audit-v3-sprint2.5-matrix-cleanup`
**Trajanje:** ~2 h

---

## Izvedeno

### CR-05 — `UTILITY_WEAPONS_EXCLUDED_FROM_ACC` konstanta ✅

**Problem:** Hardcoded seznam `('WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE', 'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE')` v SQL subquery v `sessions_router.py::build_team_matrix`. Enaka logika se po pričakovanjih ponovi v `records_weapons`, `proximity_scoring` in drugih leaderboard endpointih.

**Fix:** `frozenset[str]` konstanta v `website/backend/utils/et_constants.py::UTILITY_WEAPONS_EXCLUDED_FROM_ACC`. Dokumentirano zakaj jo izključujemo (splash/utility weapons brez smiselnih shots). Na voljo za kasnejši refactor drugih mest.

### CR-04 — Extract `SessionMatrixService` ✅

**Problem:** `sessions_router.py` je imel **300-vrstično god funkcijo** `build_team_matrix` z 4 internimi helperji (`_empty_cell`, `_finalize_cell`, `_sum_cells`, `_aggregate`). Težko testirati izolirano, težko ponovno uporabiti, router nosi poslovno logiko.

**Fix:** Nov modul `website/backend/services/session_matrix_service.py` z:
- `SessionMatrixService.compute(round_ids, matches, scoring_payload, hardcoded_teams) -> dict` — glavna API metoda
- `extract_team_rosters(hardcoded_teams)` — normalizator shape-a `get_hardcoded_teams()`
- Module-level helperji: `_empty_cell`, `_finalize_cell`, `_sum_cells`, `_aggregate_roster`
- Ponotranji helperji: `_fetch_stats`, `_ingest_rows`, `_finalize_rosters`, `_split_by_team`, `_build_maps_list`

SQL query zdaj uporablja `UTILITY_WEAPONS_EXCLUDED_FROM_ACC` konstanto prek `?` placeholderjev (namesto inline hardcoded seznama). Adapter translatira `?` → `$N` za PostgreSQL.

**Router pred/potem:**
- `sessions_router.py::build_team_matrix` + `_extract_team_rosters`: **289 vrstic** → 0 (odstranjeno)
- `sessions_router.py::get_stats_session_detail`: klic `await build_team_matrix(...)` → `await SessionMatrixService(db, scoring_service).compute(...)`
- Router velikost: 1944 → **1655 vrstic** (-15 %)

### CR-07 — Unit testi za matrix ✅

**Nov fajl:** `tests/unit/test_session_matrix_service.py` z 12 testi, brez žive DB (FakeDB pattern).

**Pokritost:**
1. `extract_team_rosters` normalization: None, `{guids: [...]}` dict, `[{guid: ...}]` list, `[str]` list
2. `compute()` degenerate inputs: empty rounds → `no_rounds`, no teams → `no_teams`, single team → `no_teams`
3. **Stopwatch swap + substitution** (happy path): R1 sides 1/2, R2 sides swap, player v obeh timih → dvojna pojavitev v rosters
4. **ET color code strip**: `^1Dmon^7` → `Dmon`
5. **Tri-format side normalization**: string `'1'`/`'2'` sprejeta (legacy data ne drop-ana)
6. **Division-by-zero safety**: `time_played=0` → DPM=0, `deaths=0` → KD=kills, `shots=0` → accuracy=0
7. `side_mapping_failed` pot: ko vse strani so unknown

**Rezultat:** 12/12 pass. Celotna test suite: **508 pass, 45 skip** (prej 496 pass — +12 novih brez regresij).

---

## Verifikacija

- `ruff check bot/ website/backend/` — 0 errors
- `pytest tests/` — 508 passed, 45 skipped, 0 failed
- Import sanity: `SessionMatrixService`, `extract_team_rosters`, `UTILITY_WEAPONS_EXCLUDED_FROM_ACC`
- `SessionMatrixService.compute` signature: `(self, round_ids: list[int], matches: list[dict], scoring_payload: dict, hardcoded_teams: dict | None) -> dict`

---

## Kar ostaja iz Session Detail review

**CR-02 — dual rendering** (React 3 metrike vs legacy JS 7 + heatmap + drill-down): **deferred** — zahteva user decision (parity vs cut). V memoriji `feedback_no_react_build.md`: "legacy JS je produkcija". Predlog za prihodnje: če legacy ostaja canonical, odstranimo `PlayerMatchMatrix.tsx` in simplifyamo `SessionDetail.tsx`. Če gremo v prihodnje React-only, dopolnimo feature parity. **Sprint 2.5 tega ne rešuje.**

**CR-09 — DOM re-render optimizacija** v legacy JS (laggy pri 20+ igralcih × 7 map): **deferred** — premature optimization, počakati če userji tarnajo.

---

## Kar se odpira za Sprint 3 (arhitektura)

Po tem sprintu je teren čistejši za:

- **ARCH-01** — `@handle_router_errors` dekorator za 22 routerjev (duplicirana `try/except HTTPException` logika)
- **CQ-03** — `bot/core/guid_utils.py::normalize_guid()` za 3 stile GUID normalizacije
- **CQ-04** — `ProximityQueryBuilder` fluent API za WHERE clause v 7 proximity routerjih
- **REFAC-01** — `StorytellingTiming` constants class (magic numbers 10000, 3000, 15000, 5000 ms)

---

**Avtor:** Mega Audit v3 Sprint 2.5 (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-17
