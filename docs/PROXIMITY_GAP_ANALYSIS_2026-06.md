# Proximity Gap Analysis — Imamo vs Želimo vs Vrzel (2026-06-21)

> **Namen:** strukturiran, z dokazi podprt pregled, kam vložiti naslednjo energijo v proximity.
> **Metoda:** 3 Explore agenti (koda/vizija/frontend) + živa validacija — DB row-counti, probe živih
> endpointov (FastAPI :8000), grep frontend fetch-grafa. Vsaka trditev "imamo/skrito" je podprta z
> dokazom, ne le obstojem kode.
>
> **⚠️ Caveat (dev vs prod):** Vsi DB/endpoint dokazi so iz **dev instance** (PG14 na samba,
> backend :8000). Dev baza je **sveža do danes (2026-06-21)** in bogata (vse žive tabele do 06-20/06-21),
> zato je signal "ima podatke / je prazno" zanesljiv. Absolutni volumni se od produkcije (PG17,
> slomix.fyi) lahko razlikujejo; kjer to šteje, je posebej označeno.

---

## 1. IMAMO — živo, z dokazi

### Cevovod (Lua → parser → DB → API → UI)
- **Lua v6.10** (`proximity/lua/proximity_tracker.lua`): v4 tracking + v5 teamplay + v6 objective intel — vse ON.
- **Parser** (`proximity/parser/parser.py`, ProximityParserV4): vse žive sekcije, idempotenten, guid_canonical=UPPER.
- **Backend**: `proximity_router.py` + 13 sub-routerjev + `storytelling_router.py` = **81 endpointov** (potrjeno iz žive OpenAPI sheme), vsi pod `/api`. **Noben probani endpoint ni pokvarjen.**
- **Storytelling** je modulariziran v paket `website/backend/services/storytelling/` (kis.py, archetypes.py, win_contribution.py, advanced_metrics.py, kis_shadow.py) — ni več en 109KB monolit.
- **Frontend (dvojni)**: legacy `website/js/proximity.js` (212KB) + `story.js` (76KB) + `session-detail.js` = produkcijski "vse"; React `Proximity.tsx`/`Story.tsx`/`ProximityReplay.tsx`/`ProximityPlayer.tsx`/`ProximityTeams.tsx` = moderni kuriran podmnožica.
- **Discord**: `bot/cogs/proximity_cog.py` (+4 mixini): !pse !pco !pxa !ppu !ptl !pca !pck !pcd + ingestion/relinker background.

### DB resničnost — exact COUNT(*) (dev, sveže do 06-20/06-21)
| Tabela | Vrstic | Orphan (round_id NULL) | Zadnji session |
|---|---:|---:|---|
| proximity_team_cohesion | 708.354 | 21.170 (~3%) | 2026-06-20 |
| proximity_shot_fired | **308.881** | 23.840 (**7,7%**) | 2026-06-20 |
| proximity_hit_region | 217.940 | 682 | 2026-06-20 |
| proximity_reaction_metric | 77.997 | 244 | 2026-06-20 |
| proximity_team_push | 60.534 | 161 | 2026-06-20 |
| proximity_trade_event | 48.632 | — | — |
| proximity_spawn_timing | 30.138 | 127 | 2026-06-21 |
| proximity_combat_position | 26.737 | — | — |
| proximity_kill_outcome | **26.352** | 123 | 2026-06-20 |
| storytelling_kill_impact | 20.836 | 0 | 2026-06-14 |
| proximity_focus_fire | 19.759 | — | — |
| proximity_weapon_accuracy | 17.742 | — | — |
| proximity_crossfire_opportunity | 10.609 | 52 | 2026-06-20 |
| proximity_revive / lua_trade_kill / objective_focus / construction / objective_run / carrier_* / escort / vehicle / support | 66–5.761 | nizko | tekoče |
| **proximity_hit_region_summary** | **0** | — | edina res prazna živa tabela |

### Validacija živih endpointov (probe z realnim scope)
- **Storytelling invisible-value VSI delujejo in vračajo realne podatke** (na obremenjeni seji 2026-03-25): `gravity` (3539B), `space-created` (1617B), `enabler` (380B), `lurker-profile` (901B), `useless-defense-deaths` (341B), `win-contribution` (26.716B, z MVP), `synergy` (701B). → **Popravek**: agent #1 jih ni naštel med endpointi; v resnici **obstajajo in so polni**.
- **Objective intel (8) vsi 200 + podatki**: carrier-events/kills/returns, vehicle-progress, construction-events, objective-runs, escort-credits, objective-focus.
- **Round-specific (3) vsi 200 + bogati**: round/{id}/timeline (157KB), /tracks (2,1MB, 125 igralcev), /team-comparison.
- **v7-status** 200 ok; **player-aim** zahteva map_name; **trades/player-stats** 200 ready.

---

## 2. ŽELIMO — vizija + dejanski status (validirano)

| Vizija (vir) | Status | Dokaz |
|---|---|---|
| **Invisible value** (gravity/space/enabler/lurker) — severnica `user_vision_invisible_value` | ✅ **SHIPPED** | 4 endpointi delujejo + polni; surface-ani v legacy IN React (`hooks.ts`: story-gravity/space/enabler/lurker) |
| **Storytelling s številkami** (KIS, archetypes, momenti, momentum, synergy, win-contribution) | ✅ SHIPPED | `storytelling/` paket; vsi endpointi živi |
| **BOX (Oksii stopwatch)** | ✅ SHIPPED | `/storytelling/box-score`, box_scoring_service |
| **ET Rating v2** (15 metrik, vklj. kill_permanence/KPR) | ✅ SHIPPED | KPR=3 kodne datoteke; skill_rating_service |
| **Map heatmaps** (death/combat) + replay tracks + player journey | ✅ DELNO SHIPPED | heatmap render v proximity.js IN Proximity.tsx; `assets/maps/proximity/map_transforms.json` obstaja; round/tracks 2,1MB |
| **shot_fired / aim analytics** | ✅ ŽIVO (ne dormant) | 308k vrstic čez 11 dni od 2026-05-18; `/player-aim` deluje |
| **KILL_OUTCOME** (memory: "0 data, PMF_LIMBO bug") | ✅ **REŠENO** (memory STALE) | 26.352 vrstic čez 28 dni do 2026-06-20 |
| **KROGT / EIS / MER / TDS** (smart scoring) | 🔴 **DESIGN-ONLY** | **0 kodnih datotek** za vsako |
| **UTRO** (Stiba) | ⚪ Raziskan, delne reference | UTRO=4 datoteke (ne adopt-an kot rating) |
| **v7 capture** (aim_lock/spawn_select/skill_snapshot/comm_events) | 🟡 **DORMANT** (cevovod dokazan) | vse 4 tabele imajo podatke **samo iz 2026-06-10** (v7-probe); flagi OFF |
| **comm_events** (agent: "ET API tega ne izpostavi") | 🟡 vprašljivo blocked | probe je 2026-06-10 dejansko zapisal **96 vrstic** → cevovod nekaj ujame |
| **Map viz suite** (spawn-route, chokepoint, objective-flow, push-arrows) | 🔴 večinoma NE | le heatmap+journey shipped; ostalo vizija |
| **Map-based fireteam tracking** | ❌ BLOCKED | ET:Legacy 2.83.1 Lua API ne izpostavi |

---

## 3. VRZEL — 4 koši

### Koš A — SURFACE (zgrajeno + podatki + endpoint dela; le ni prikazano) — **najcenejše**
1. **`useless-defense-deaths`** — **edini res nikjer prikazan** endpoint (dela, vrača metriko; 0 fetchov v legacy IN React). Točno olympus/superboyy želja.
2. **React parity gap (NI user-facing — razrešeno 2026-06-22)** — naslednje je v legacy, a NI v React:
   objective intel ×8, competitive suite, player-journey, v7-status, del teamplay leaderboardov.
   **A**: `website/js/route-registry.js` pokaže, da je glavni `proximity` view `mode=LEGACY` in `story`
   `mode=LEGACY` — torej **uporabniki to ŽE VIDIJO** v kanonični legacy plošči (`proximity.js` ima polne
   render-funkcije: renderCarrierIntel/VehicleProgress/ObjectiveRuns/Focus, loadCompetitivePanel,
   loadPlayerJourney/drawJourneyLife). Le modern pod-strani (`proximity-player/replay/teams`,
   `skill-rating`) so MODERN/React. → React parity **ni quick win**: terja owner-run Vite build
   (committed `website/static/modern/`, zadnjič 2026-03-31), kar `feedback_no_react_build` odsvetuje.
3. **Legacy parity gap (obratno)** — `round/{id}/timeline|tracks|team-comparison` so v React (ProximityReplay), a NE v legacy.

> **Razrešeno**: kanonična proximity/story površina = **LEGACY JS** (route-registry mode=LEGACY).
> `feedback_no_react_build` ("legacy JS = produkcija") drži za te poti; React modern je prebildан paket
> za pod-strani. Surface-delo gre torej v legacy `proximity.js`/`story.js` (takoj v živo, brez builda).

### Koš B — ACTIVATE (dormant flag; rabi validacijo + vklop)
- **v7 zajem**: aim_lock / spawn_select / skill_snapshot / comm_events — cevovod **dokazan** (06-10 probe je napolnil tabele + endpoint v7-status dela). Manjka: vklop flagov na puranu (po validaciji) + UI. Prioriteta (memory): aim_lock > comm_events > spawn_select > skill_snapshot.
- **shot_fired** je že živ na dev; potrditi prod stanje (memory: "enabled na puranu, OFF v repo").

### Koš C — BUILD (zasnovano, rabi novo kodo)
- **KROGT / EIS / MER / TDS** — 0 kodnih datotek. Rabijo Lua v5.1 sekcije (KILL_OUTCOME state-machine — **ki zdaj DELA**, REVIVE/GIB context) + service + endpointi. KILL_OUTCOME ni več blocker → ta smer je odklenjena.
- **Map viz suite** — spawn-route analiza, chokepoint detection, objective-flow, push-arrows, cohesion krogi. Podatki SO v DB (team_cohesion 708k, combat_position, objective_run), infra (`map_transforms.json`, worldToCanvas) obstaja.
- **Data-quality**: shot_fired 7,7% orphan (23.840 NULL round_id) + team_cohesion ~3% — relinker dohitevanje / preiskava.

### Koš D — BLOCKED (engine limit)
- **fireteam tracking** — ni v ET:Legacy 2.83.1 Lua API.
- **comm_events** — delno: probe je ujel 96 vrstic, a polna voice/chat telemetrija verjetno omejena; potrditi obseg preden se obljubi.

---

## 4. PRIORITIZACIJA (value × cost)

| # | Ukrep | Koš | Value (invisible-value severnica) | Cost | Opomba |
|---|---|---|---|---|---|
| 1 | **Surface `useless-defense-deaths`** v UI | A | Visok (direktna user-želja) | **Zelo nizek** | endpoint že vrača; le panel/fetch |
| 2 | **React: objective intel + competitive + journey paket** | A | Visok | Srednji | čisti porting, backend gotov; PRVO potrdi kanonično površino |
| 3 | **v7 aim_lock aktivacija + aim UI** | B | Visok | Srednji | cevovod dokazan; rabi flag-flip (owner) + validacijo + panel |
| 4 | **Map viz: spawn-route + chokepoint overlay** | C | Visok (vizualni storytelling) | Visok | podatki+infra obstajajo; nova render plast |
| 5 | **KROGT/EIS/MER/TDS** (zdaj odklenjeno) | C | Srednji-visok | Visok | Lua v5.1 + service; KILL_OUTCOME ni več blocker |
| 6 | **Orphan round_id sanacija** (shot_fired 7,7%) | C | Srednji (kakovost) | Nizek-srednji | relinker / preiskava |
| — | comm_events / fireteam | D | — | — | engine limit; ne obljubljati |

**Top 3 hitri zmagovalci** (vse "Surface", podatki že tam): #1 useless-defense-deaths, #2 React objective-intel/competitive parity, #3 v7 aim aktivacija.

---

## 5. Odprta vprašanja / popravki memorija

1. **Kanonična površina (React vs legacy)?** — odloča celoten Koš A. Potrebna uporabnikova potrditev.
2. **kill_outcome_investigation.md je STALE** — trdi "0 data / PMF_LIMBO bug"; dev ima 26.352 vrstic do 06-20. → posodobiti memory (rešeno).
3. **v7 "dormant" potrjen, a cevovod dela** — tabele polne le iz 06-10 probe. comm_events trditev "ni API" delno ovržena (96 vrstic). → preveriti dejanski obseg na produkciji.
4. **F1 (killer_reinf)**: NE "vedno 0 pred fixom" — dev ima 18.950 pozitivnih pred 2026-06-10 (verjetno re-parsano). Odprto le: ali prod zgodovinske vrstice rabijo backfill?
5. **Prod potrditev**: ta analiza je dev-side. Pred vlaganjem v Koš B/C potrditi enaka stanja na slomix_vm (PG17), zlasti shot_fired prod-flag in v7 prod-praznost.

---

## Dodatek — v7 aim_lock aktivacijski runbook (2026-06-22)

**Readiness (vse potrjeno):** Lua implementacija `proximity_tracker.lua:1101–1204` (flag `aim_lock = false`
na vrstici **267**); parser `proximity/parser/parser.py` (`_parse_aim_lock_line`, `_import_aim_locks`,
sekcija `# AIM_LOCK`); DB `proximity_aim_lock` (obstaja, 377 probe vrstic iz 06-10); endpoint
`/api/proximity/v7-status` (poroča capability). **Manjka:** aim_lock-specifičen data-endpoint +
**UI panel (nikjer)** — aim analytics trenutno teče na `shot_fired`, ne na aim_lock.

**Aktivacija (OWNER, na puranu — config sprememba + full map reload, NE `lua_restart`):**
1. Na puranu uredi ŽIVI Lua (fs_homepath prevlada): `~/.etlegacy/legacy/luascripts/proximity_tracker.lua`,
   `features.aim_lock = false` → `true` (+ po želji `shot_fired`, `spawn_select`).
2. **Full map reload** (npr. `map <ime>` prek rcon ali naravni map-change) — NIKOLI `lua_restart`
   (c0rnp0rn8 crasha — glej [[feedback_lua_restart]]).
3. Po prvi pravi rundi preveri: etconsole `[PROX ...] AIM_LOCK ...`, nato `SELECT count(*) FROM
   proximity_aim_lock WHERE session_date >= <danes>` → > 0 in zvezno (ne le 06-10).
4. Repo-side (neobvezno, za ponovljivost): flip `proximity_tracker.lua:267` `aim_lock = true`, da se
   ob naslednjem overlayu/deployu ohrani. Trenutno je namenoma dormant.

**Po vklopu (BUILD, ko podatki tečejo):** aim_lock data-endpoint + UI panel (kdo "lockira" tarče,
kako dolgo, na kakšni razdalji) — sklene zanko med shot-fired in pravimi tarčami.

## Reference
- DB: `mcp__db__query` proti etlegacy@samba (PG14); endpointi: `http://localhost:8000/api/...` (OpenAPI 81 poti).
- Koda: `proximity/lua/proximity_tracker.lua`, `proximity/parser/parser.py`,
  `website/backend/routers/proximity_*.py` (13) + `storytelling_router.py`,
  `website/backend/services/storytelling/`, `skill_rating_service.py`, `box_scoring_service.py`.
- Frontend: `website/js/{proximity,story,session-detail}.js`, `website/frontend/src/{pages,api}/`.
- Vizija: memory `proximity_evolution_masterplan`, `user_vision_invisible_value`, `smart_scoring_design`,
  `proximity_map_viz_vision`, `proximity_vision_sweep_2026-06-10`; docs `PROXIMITY_REDESIGN_MASTER_PLAN`,
  `PROXIMITY_E2E_AUDIT_2026-06-10`, `LUA_V7_CAPTURE_RESEARCH_2026-06`, `ANALYTICS_BENCHMARK_2026-06`.
