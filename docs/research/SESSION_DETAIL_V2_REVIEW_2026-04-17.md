# Session Detail 2.0 Matrix — Code Review (2026-04-17)

**Kontekst:** 7 uncommited datotek, ~988 dodanih vrstic. Cilj: pregled **novo napisane kode** (ne starega codebase-a).

**Pregled vsebine:**
- `bot/cogs/proximity_cog.py` (+1)
- `bot/services/round_correlation_service.py` (+12)
- `bot/services/stopwatch_scoring_service.py` (+62)
- `website/backend/routers/sessions_router.py` (+302) — `build_team_matrix`
- `website/frontend/src/api/types.ts` (+65) — nove interfaces
- `website/frontend/src/pages/SessionDetail.tsx` (+86) — `ScoringBanner` + uporaba
- `website/frontend/src/components/PlayerMatchMatrix.tsx` (267 novih, nov fajl)
- `website/js/session-detail.js` (+481) — legacy rendering

---

## Status fiksov (2026-04-17)

| ID | Status |
|---|---|
| CR-01 | ✅ **FIXED**: `sessions_router.py` uvozi `strip_et_colors` in ga kliče na `player_name` (vrstica 237) |
| CR-01b | ✅ **FIXED**: "longest wins" zamenjan s "prvi non-empty wins" (kraj name oscillation) |
| CR-03 | ✅ **FIXED**: `build_round_side_to_team_mapping` sprejme `team_a_name` / `team_b_name` kot kwargs, caller pošlje canonical iz `scoring_payload` |
| CR-02 | ⏳ Ostaja za Sprint 2 (dual rendering — feature parity ali cut) |
| CR-04 | ⏳ Sprint 3 (extract `SessionMatrixService`) |
| CR-05 | ⏳ Sprint 3 (`UTILITY_WEAPONS` v `et_constants.py`) |
| CR-06 | ⏳ `localStorage` key unify |
| CR-07 | ⏳ Unit testi za matrix |
| CR-09 | ⏳ DOM re-render opt (nizka prioriteta) |

Ruff + pytest: 0 errors, 496 passed.

---

## 🔴 Kritično (pred merge) — originalne najdbe

### CR-01 — `player_name` ne stripa ET color kod na backendu
**Kje:** `sessions_router.py::build_team_matrix` — `rosters_dict[key]["player_name"] = player_name` (raw iz DB)

**Problem:** Backend pošlje ime `^1Dmon^7` direktno v JSON. Frontend (React `{player.player_name}`) auto-escape-a HTML ampak **ne stripa barvnih kod** → uporabnik vidi `^1Dmon^7`. Legacy JS `session-detail.js` uporablja `escapeHtml(name)` (prav tako ne strip). Ni XSS (React/escapeHtml to pokrijeta), ampak **UX regresija**.

**Dodatni bug — "longest name wins":**
```python
elif player_name and len(player_name) > len(rosters_dict[key]["player_name"]):
    rosters_dict[key]["player_name"] = player_name
```
Color kodirana verzija (`^1Dmon^7` = 9 znakov) **vedno premaga čisto** (`Dmon` = 4). Torej izbira je deterministično najslabša.

**Fix:** Backend uvozi `strip_et_colors` (obstaja v `website/backend/utils/et_constants.py`) in kliče pred shranjevanjem. `storytelling_router.py` in `replay_service.py` to že delata — konsistenca.

```python
from website.backend.utils.et_constants import strip_et_colors
# ...
player_name = strip_et_colors(row[2] or "")  # čist na boundary
```

---

### CR-02 — Legacy JS ↔ React feature drift (dual rendering)
**Kje:** `session-detail.js::_renderTeamMatrixSection` vs `PlayerMatchMatrix.tsx`

| Feature | Legacy JS | React |
|---|---|---|
| Metrike | **7** (dpm, kd, damage, revives, hs_pct, accuracy, assists) | **3** (dpm, kd, damage) |
| Heatmap | ✅ `_heatmapClass` median-relativ | ❌ |
| Drill-down | ✅ `_renderMatrixDrillRow` | ❌ |
| MVP star ★ | ✅ | ❌ |
| Substitute ⚠ badge | ✅ | ❌ |
| Sort po stolpcu | ✅ `sdSortMatrix` | ❌ (fiksen po metric total) |
| localStorage key | `sd-matrix-metric` | `session-matrix-metric` |

**Dve ločeni implementaciji z različnim feature-setom pomenita:**
1. Uporabnik dobi različno funkcionalnost glede na kateri frontend je naložen.
2. `localStorage` key mismatch → nastavitve se ne delijo (React vs legacy).
3. Bug fix v enem ne popravi drugega — permanent technical debt.

**Glede na memory `feedback_no_react_build.md`**: "legacy JS je produkcija". Torej React je "nice-to-have" ampak *not canonical*.

**Priporočilo — ena izmed:**
1. **Ozka pot:** React ujame feature parity (dodati 4 metrike, heatmap, drill-down). Usklajena `localStorage` ključa.
2. **Cut React:** Za ta komponent React ne obstaja v produkciji. Odstrani `PlayerMatchMatrix.tsx` in `ScoringBanner` matrix-related dele; pusti samo legacy. SessionDetail.tsx razbremenimo.
3. **Accept drift:** Dokumentiraj v fajlih (top-of-file komentar) da so razlike namerne, lastna TODO.

---

### CR-03 — Tip varnost: `team_names[0]` dict order predpostavka
**Kje:** `stopwatch_scoring_service.py::build_round_side_to_team_mapping`

```python
team_names = list(team_rosters.keys())
team_a_name, team_b_name = team_names[0], team_names[1]
```

**Problem:** Python 3.7+ zagotavlja **insertion order** v dict, ampak dokument NE zagotavlja, da `get_hardcoded_teams` vrne Team A **vedno prvi**. Če:
- `session_data_service.py::get_hardcoded_teams` zgradi dict iz `for team_name, data in ...` v vrstnem redu sortirano po `team_name` alphabetically → `team_names[0]` = "Axis" (če je to ime), ne "Team A".
- Subsequent klicev s cached map vrsta ohrani order, ampak **prvi klic** po resync lahko vrne v drugačnem redu.

Posledica: `side1_favors_a = (s1_a - s1_b) + (s2_b - s2_a)` se izračuna za **napačno stran**, mapping `{1: 'team_a_name', 2: 'team_b_name'}` je obrnjen → **matrix prikaže igralce pod napačnim timom**.

**Fix:** Eksplicitno branje iz `scoring_payload.team_a_name` / `team_b_name` (ki sta *canonical* iz upstream):
```python
# Caller (build_team_matrix) že ima:
team_a_name = scoring_payload.get("team_a_name") or team_names[0]
team_b_name = scoring_payload.get("team_b_name") or team_names[1]
# Prenesi v build_round_side_to_team_mapping kot argumente.
```

---

## 🟡 Srednje (priporočljivo)

### CR-04 — `build_team_matrix` je 300-line god function
**Kje:** `sessions_router.py:127-409`

Funkcija ima 4 interne helperje (`_empty_cell`, `_finalize_cell`, `_sum_cells`, `_aggregate`) in tri odgovornosti:
1. SQL load player × round stats (en query, OK)
2. Aggregation per player × map
3. Assembly v team rosters + map list + aggregates

**Predlog:** Extract v `website/backend/services/session_matrix_service.py`:
```
class SessionMatrixService:
    def __init__(self, db, scoring_service): ...
    async def compute(self, round_ids, matches, scoring_payload, hardcoded_teams) -> dict: ...
    
    def _empty_cell(self, map_idx): ...
    def _finalize_cell(self, cell): ...
    def _sum_cells(self, cells): ...
    def _aggregate_roster(self, roster): ...
```
Router postane 5 vrstic: `return await SessionMatrixService(db, scoring_service).compute(...)`.

### CR-05 — Hardcoded utility weapons list v SQL
**Kje:** `sessions_router.py::build_team_matrix` subquery:
```sql
WHERE weapon_name NOT IN (
    'WS_GRENADE', 'WS_SYRINGE', 'WS_DYNAMITE',
    'WS_AIRSTRIKE', 'WS_ARTILLERY', 'WS_SATCHEL', 'WS_LANDMINE'
)
```
Ta seznam se verjetno ponovi drugje (prejšnji audit je odkril 6+ mest). Kandidati:
- `website/backend/utils/et_constants.py::UTILITY_WEAPONS: frozenset[str]`
- V query: `WHERE weapon_name NOT IN ({utility_weapons_sql})` (build SQL z `$2, $3, ...` placeholderji iz parametra)

### CR-06 — Dva localStorage ključa za isti state
**Kje:** `PlayerMatchMatrix.tsx` STORAGE_KEY = `'session-matrix-metric'`, `session-detail.js` = `'sd-matrix-metric'`.

Zdaj vsak komponent ima svoj preferenčni metric. User menja v legacy, React ne ve. Povezano s CR-02 (feature drift). Fix: ena konvencija (priporočam React-jev `'session-matrix-metric'` — bolj opisen).

### CR-07 — `build_team_matrix` nima testov
Funkcija z 300+ vrsticami in netrivialno agregacijsko logiko pomeni:
- Side-to-team majority vote → edge case (tie breaks skipped)
- Substitution detection (isti GUID v obeh timih)
- Division by zero v DPM/KD/accuracy
- Empty `round_ids`, empty `hardcoded_teams`

**Priporočilo:** `tests/unit/test_session_matrix.py` z `FakeDB` pattern (kot `test_storytelling_service.py`):
- `test_matrix_empty_rounds` → `{"available": False, "reason": "no_rounds"}`
- `test_matrix_no_teams` → `{"available": False, "reason": "no_teams"}`
- `test_matrix_side_swap_r1_r2` — R1 team_a side=1, R2 team_a side=2 (stopwatch swap) → mapping pravilen za oba
- `test_matrix_substitute` — player v obeh rosters, cells razdeljeni
- `test_matrix_color_codes` — po fix-u za CR-01

### CR-08 — `sessions_router.py` endpointi brez auth decoratorja
Povezano z prejšnjim auditom SEC-06. Nov endpoint `/stats/session/{gaming_session_id}/detail` ostaja `Depends(get_db)` samo. Verzija stats-u je po design javna (per `website/backend/CLAUDE.md`), vendar `team_matrix` potencialno razkriva persistent team imena — preveri ali to tvori informacijski leak, če imajo teami sensitive imena (npr. clan tag).

### CR-09 — Legacy JS `_renderSummaryTab` re-render celega taba na sort/drill toggle
**Kje:** `sdSortMatrix`, `sdToggleMatrixDrill`, `sdSetMatrixMetric` — vsi kličejo `_renderSummaryTab(true)`.

Pri 20 igralcih × 7 mapah je to ~140 cells DOM re-render. Manjši session OK, ampak pri velikih session:
- Layout thrashing
- Scroll pozicija izgubljena

**Optimizacija (če bo potrebno):** Bolj granularen DOM update — samo `#sd-team-matrix` innerHTML, ne ves tab.

---

## 🟢 Pohvale (kar je dobro narejeno)

1. **`round_correlation_service.py`**: zamenjava hardcoded `f"{match_id}:{map_name}"` z `_find_nearby_correlation_id` + `_resolve_correlation_id` je čist fix za R1/R2 match_id drift pri servis restartih. Dobro.
2. **`build_round_side_to_team_mapping`**: algoritem majority vote s tie-break-skip je robusten. Dokumentacija odlična (docstring s trade-off-i).
3. **`types.ts`**: Consistent naming (`SessionTeamMatrixCell`, `SessionTeamMatrixPlayer`, `SessionTeamMatrixMap`, `SessionTeamMatrixAggregates`). Nullable polja pravilno označena.
4. **Division-by-zero guardovi**: `if time_played > 0`, `if deaths > 0`, `if shots > 0`, `if hits > 0`, `if rf_count > 0` — povsod.
5. **`PlayerMatchMatrix.tsx`**: React hooks (useMemo, useEffect) pravilno uporabljeni. `localStorage` safe guard (`typeof window === 'undefined'`).
6. **`# nosec B608`** komentarji v SQL f-stringih so opravičeni (placeholderji parametri), ni SQL injection.
7. **Error handling**: `build_team_matrix` exception → `{"available": False, "reason": "error"}` z log warning. Graceful degradation.
8. **Accessibility**: `title=` tooltip v React, `escapeHtml(tooltip)` v legacy JS.

---

## Prioritiziran plan popravkov

### Sprint 1.5 — Takojšnji fixi (< 2 h)
| Prio | Fix | Datoteka | Čas |
|---|---|---|---|
| 🔴 | **CR-01**: `strip_et_colors` na `player_name` v backendu | `sessions_router.py` | 15 min |
| 🔴 | **CR-01b**: "longest name wins" bug → canonical ime izbrati po drugem kriteriju (npr. lexicographic na stripped imenih) | `sessions_router.py` | 10 min |
| 🔴 | **CR-03**: Prenesi `team_a_name` / `team_b_name` v `build_round_side_to_team_mapping` kot argumenta | `stopwatch_scoring_service.py` + `sessions_router.py` | 20 min |
| 🟡 | **CR-06**: Uskladi localStorage key (`session-matrix-metric`) | `session-detail.js` | 5 min |

### Sprint 2 — Feature parity ALI cut (1-3 h)
| Prio | Fix | Datoteka | Čas |
|---|---|---|---|
| 🟡 | **CR-02**: Odločitev — feature parity ALI cut React komponenta | `PlayerMatchMatrix.tsx` | 2-3 h |

### Sprint 3 — Strukturni (4-6 h)
| Prio | Fix | Datoteka | Čas |
|---|---|---|---|
| 🟡 | **CR-04**: Extract `SessionMatrixService` | nov `session_matrix_service.py` | 2 h |
| 🟡 | **CR-05**: `UTILITY_WEAPONS` v `et_constants.py` + refactor subquery | `et_constants.py`, `sessions_router.py`, ostale | 1 h |
| 🟡 | **CR-07**: Unit testi za `SessionMatrixService` | `tests/unit/test_session_matrix_service.py` | 3 h |

### Upoštevano (brez takojšnjega fix-a)
- **CR-08**: Auth na `/api/stats/*` — design choice (public)
- **CR-09**: DOM re-render optimizacija — premature optimization, počakaj če userji tarnajo

---

## Sklep

Koda je **v produkciji ready** samo po fiksu **CR-01, CR-01b, CR-03** (3 bugov, ~45 min). Ostali (CR-02 do CR-09) so improvemnti, ne blockers.

**Dual rendering (CR-02) je glavni dolg** — ena implementacija z dvojnim feature-setom je classic vibe-coding anti-pattern. V naslednjem sprintu ena odločitev (parity ali cut) osvobodi 300+ vrstic duplicirane logike.

**Pozitivno:** arhitektura matrix ključnih konceptov (substitution detection, stopwatch side swap, majority vote team assignment) je **robustna**. Nova funkcionalnost je dobro zmišljena — samo implementacija ima tri popravljive površinske bugov.

---

**Avtor:** Mega Audit v3 Sprint 1 — Session Detail 2.0 review (Claude Opus 4.7, 1M context)
**Datum:** 2026-04-17
