# MASTER PLAN — Session-lifecycle & data-integrity fixes

> **Status:** ✅ FAZA B izvedena · FAZA C:
> - ✅ **FIX-1 + FIX-2 + FIX-3 → PR #350 MERGED** (read-time data-integrity)
> - 🔵 **FIX-4 + FIX-5 → PR #352 OPEN** (Lua proximity re-ankr + weapon; owner reload pending)
> - 🔵 **FIX-6 → PR #354 OPEN** (idle watchdog, dry-run default; RCON team-blocker RESOLVED —
>   empty-count + inactivity cvars, no team needed; map supply full load, 45min)
> - ❌ **FIX-7 DROPPED** (2026-06-02, RCA): "22 mislinkov" je večinoma lažni pozitiv —
>   `rounds.round_start_unix` (stats-file čas) vs `lua.round_start_unix` (Lua round-start)
>   sta različni časovni sidri → >180s drift je PRIČAKOVAN za pravilne povezave. Genuino
>   fixable le ~6 (4 exact + 2 closer), večinoma bot-test dan, timing-display impact.
>   16/22 pravilno povezanih. ROI slab + churn-tveganje → NE gradimo re-linkerja.
> - ✅ **FIX-8 → PR #356 MERGED** (c0rnp0rn8 reinf offset %8 clamp; owner reload pending)
> - 🔵 **FIX-9 + L2 → PR #358 OPEN** (fallback logging + rose guard — last polish)
>
> **✅ AUDIT REMEDIACIJA ZAKLJUČENA.** Vse najdbe iz AUDIT-a naslovljene:
> FM4, RCA-1, RCA-2, M1, FM6, FIX-8, FIX-9, L2. FIX-7 dropped (RCA: time-source drift,
> ne mislink). Odprto le še: owner Lua deploy (#352/#356 full map reload), opcijski
> server cvari za FM2.
> **Diagnoza/zakaj:** `docs/AUDIT_2026-05-29.md` (§1-7). Ta doc = **kaj/kako/izvedljivost**.
> **Proces:** FAZA A (plan) → **FAZA B (feasibility audit proti živi kodi)** → FAZA C (koda).
> NE pišemo kode dokler vsak fix ni označen **GREEN** v FAZI B.

## Globalne omejitve (veljajo za VSE fixe v TEM planu)
- ❌ **Brez backfilla** zgodovinskih podatkov (odločitev uporabnika za session-lifecycle fixe iz tega plana; ni repo-wide pravilo — ločeni, izrecno owner-gated backfilli, npr. `scripts/backfill_killer_reinf.py`, imajo svojo odločitev). Vse forward-only / read-time.
- ❌ **Brez `map_restart`/`lua_restart`** — vedno poln `map <ime>` load ([[feedback_lua_restart]]).
- ❌ **Brez restarta storitev** brez vprašanja ([[feedback_no_service_restart]]).
- ✅ Produkcija = **legacy JS** (`website/js/`), NE React build ([[feedback_no_react_build]]).
- ✅ Lua deploy: potrdi **sha256 živa==repo** + patch **homepath PRED basepath**.
- ✅ Feature branch, NE main; **diff pokazati uporabniku PRED commitom**; bundle related v en PR.

---

## REGISTER FIXOV

Vsak fix: `ID · prioriteta · severity · target · sprememba · Feasibility(PENDING/GREEN/YELLOW/RED) · deps · test · rollback`.

### P0 — takoj uporabniško vidno, brez DB mutacije, brez ops odločitev

#### FIX-1 · FM4 orphan R2 izločitev iz leaderboardov/records
- **Severity:** High · **Root:** AUDIT §4 FM4, §6 (reuse round_correlations)
- **Problem:** 46 orphan R2 (291 PCS vrstic, +23% kills) v leaderboard agregatih; parser
  `community_stats_parser.py:541-548` shrani kumulativne R2 kot rundo brez differentiala.
- **Feasibility:** 🔴→🟢 RAZREŠENO 2026-06-01 (definicija potrjena s psql). Prvotni
  korelacijski filter (adversar) bi bil nepopoln; **session-based definicija je zmagovalka.**
- **DEFINITIVNA SPREMEMBA (read-time, brez flaga/backfilla):** izloči R2 brez R1 v ISTI seji+mapi.
  Verificirano: zajame natanko **35 pravih orphanov** (= 34 korelacijskih + 1 nekoreliran),
  **0 napačnih pozitivov**, spoštuje multi-match (best-of-3), neodvisno od korelacijske pokritosti:
  ```sql
  AND NOT (r.round_number = 2 AND NOT EXISTS (
    SELECT 1 FROM rounds r1
    WHERE r1.round_number = 1 AND r1.map_name = r.map_name
      AND r1.gaming_session_id = r.gaming_session_id))
  ```
  (Boljše od korelacijske `r1_round_id IS NULL` (34, spregleda 1, odvisna od 659/827 pokritosti)
  IN od per-day hevristike (46, prelahka).)
- **Targeti (potrjeni FAZA B):** 87 mest / 13 datotek (`leaderboard_cog.py`, `records_*.py`,
  `sessions_router.py`, `players_router.py`, `stats_cog.py`, `session_cog.py`, ...).
  **OBVEZNO shared helper** (`_ROUND_FILTER_NO_ORPHAN` v `records_helpers.py` + bot util),
  ne 87 inline kopij. records_overview.py že ima `_ROUND_FILTER` vzorec za posnemati.
- **Deps:** shared helper najprej · **Test:** kills leaderboard delta za znani orphan dan
  (2026-03-25); regression da multi-match dnevi OSTANEJO · **Rollback:** revert helper

#### FIX-2 · RCA-1 time_dead LEAST cap v round_publisher
- **Severity:** High · **Root:** AUDIT §3 RCA-1, §5
- **Problem:** `round_publisher_service.py:308/515/599` bere/prikaže time_dead RAW → Discord
  round-post (3000+) kaže `dead%>8000%`, negativen alive.
- **Sprememba:** `LEAST(COALESCE(time_dead_minutes,0)*60, time_played_seconds)` v players_query
  (vrstica 304-315); + diagnostics konsistenca. Interim do "Lua Time Stats Overhaul".
- **Targeti (PREVERI):** `bot/services/round_publisher_service.py:304-334,490-599`
- **Feasibility:** PENDING
- **Deps:** none · **Test:** publish round s prizadeto rundo → dead% sane, alive≥0 · **Rollback:** revert query

### P1 — leaderboard correctness + Lua (test server + sha256 gate)

#### FIX-3 · RCA-1 LEAST cap v preostalih bralcih
- **Severity:** Medium · **Targeti (PREVERI):** `sessions_router.py` (raw_dead, survival_rate),
  `records_seasons.py`, `records_matches.py`. (`frag_potential.py`, session_stats_aggregator,
  session_graph_generator ŽE capajo — potrdi.)
- **Sprememba:** isti LEAST vzorec; survival_rate `MAX(0, MIN(100, ...))`.
- **Feasibility:** PENDING · **Deps:** FIX-2 (konsistenca) · **Test:** API before/after

#### FIX-4 · RCA-2 proximity start_time re-ankr / warmup exclude
- **Severity:** Medium · **Root:** AUDIT §3 RCA-2
- **Sprememba:** v `proximity_tracker.lua` et_RunFrame round-start (vrstica 3570) re-ankraj
  `tracker.round.start_time = levelTime` (ali warmup-exclude v et_InitGame). Lua 6.02, contract enak.
- **Targeti (PREVERI):** `proximity/lua/proximity_tracker.lua:3464,3570`; sha256 živa==repo.
- **Feasibility:** PENDING · **Deps:** Lua deploy gate · **Test:** test server, gametime sane po warmup
- **Rollback:** revert vrstice + owner map load

#### FIX-5 · M1 Lua weapon coercion
- **Severity:** Medium · **Root:** AUDIT §M1
- **Sprememba:** `proximity_tracker.lua:4108` → `weapon = tonumber(weapon) or 0,`
- **Feasibility:** PENDING · **Deps:** isti Lua deploy kot FIX-4 (en reload) · **Test:** SHOT_FIRED z robnim weapon

### P2 — operativna preprečitev (koren FM1/FM2/FM4)

#### FIX-6 · Idle-server watchdog (bot-side) + server cvars
- **Severity:** Medium (ops) · **Root:** AUDIT §4 FM1/FM2, §5
- **Sprememba:** razširi `monitor_tasks_mixin` (ali nov mixin): RCON `status` ~5min; štej
  **samo team 1/2** (izloči spectatorje → pokrije FM2 "pozabi disconnectat"); če 0 aktivnih
  & idle>prag & ni voice → izda **poln `map <ime>` load (npr. supply), NE map_restart**;
  grace-period + Discord alert. Server cvars `g_spectatorInactivity`/`g_inactivity`.
- **Targeti (PREVERI):** `bot/services/monitor_tasks_mixin.py` (live_status_updater že kliče
  RCON status/30s — reuse), `bot/cogs/server_control.py`/`scripts/slomix_rcon.py` (RCON send).
- **Feasibility:** PENDING · **Deps:** ops odločitve (prag, vedno-supply vs rotacija, cvar vrednosti)
- **Test:** dry-run (log-only) preden dejansko izda map load · **Rollback:** disable task flag

### P3 — nizko / diagnostic-first

#### FIX-7 · lua_round_teams residualni mislink (DIAGNOSTIC-FIRST)
- **Severity:** Low · **Root:** AUDIT §7, [[lua_timing_drift_investigation]]
- **Korak 1 (read-only):** potrdi, da je 22 zapisov z >180s drift res mislink (vs benigni
  warmup/pause offset). ŠELE potem popravek.
- **Korak 2 (če potrjeno):** razširi re-link/stale-correction na `lua_round_teams` (vzorec
  `round_id != resolved`, kot proximity relinker) ALI periodic >180s-drift sweep. Multi-match guard!
- **Feasibility:** PENDING · **Deps:** diagnostic najprej

#### FIX-8 · FSK re-visit + c0rnp0rn8 clamp bug
- **Severity:** Low · **Root:** [[full_selfkills_investigation_pending]] (re-visit due jun 2026)
- **Sprememba:** (a) FSK metric semantics (held-back proposal) — le če reports persist;
  (b) latentni `c0rnp0rn8.lua:201-202 bit.rshift` brez `% 8` clamp (proximity_tracker:1423 ga ima).
- **Feasibility:** PENDING · **Deps:** zberi z FIX-4/5 (en Lua reload) · **Test:** clamp guard

#### FIX-9 (opcijsko) · L2/L3 housekeeping
- Proximity.tsx `hz.rose` guard (React = NI deployan → zelo nizko); par `except Exception`
  brez konteksta (records_awards.py:213, proximity_events.py). Severity: Low.

---

## FAZA B — Feasibility audit (per-fix preverba proti živi kodi)

Za VSAK fix odgovori (read-only, brez sprememb):
1. **Target obstaja?** — cited file:line še obstaja in se ujema? (grep/read)
2. **Integracija čista?** — shared helper ali scattered? Koliko mest se dotakne?
3. **Skriti consumerji/deps?** — kdo še bere isto pot/query?
4. **Testi?** — kateri testi pokrivajo to pot? Bo sprememba kaj zlomila?
5. **Schema/migracija?** — potrebna DDL? (cilj: ne; read-time only)
6. **Reverzibilno?** — rollback jasen?
7. **Tveganje × vpliv** → končni verdict: **GREEN / YELLOW (potrebuje prilagoditev) / RED (blokiran)**

**Izhod FAZE B:** vsak FIX dobi Feasibility status + morebitne prilagoditve. Predlog: izvedi z
vzporednimi agenti (1 na fix) + adversarna verifikacija, nato ročna potrditev ključnih.

### ✅ REZULTATI FAZE B (2026-06-01, 12-agent workflow + adversarna preverba P0)

| FIX | Verdict | Scattered | Schema | Reverz. | READY? | Ključna ugotovitev / prilagoditev |
|-----|---------|-----------|--------|---------|--------|-----------------------------------|
| FIX-1 FM4 | 🔴 **RED** | 87 mest / 13 datotek | NE | DA | ❌ | Adversar: prvotni filter (`r1_round_id IS NOT NULL`) bi **izbrisal 96% R2** (793 R2 NI v round_correlations, a so veljavni). Pravilno: izloči SAMO 34 potrjenih orphanov: `AND NOT (round_number=2 AND round_id IN (SELECT r2_round_id FROM round_correlations WHERE r1_round_id IS NULL))`. + shared helper za 87 mest. |
| FIX-2 RCA-1 round_publisher | 🟡 **YELLOW** | 8 mest / 1 dat (+ session_view_handlers:989) | NE | DA | ⚠️ | Adversar: prvotni SQL je rabil `time_played_seconds`, ki ga query NIMA (le `time_played_minutes`) → crash. Pravilno: `LEAST(time_dead_minutes, time_played_minutes)` (oba v min) ALI python `min(time_dead, time_played)` (vrstica 528). + vključi vzporedni bug v `session_view_handlers:989`. |
| FIX-3 RCA-1 ostali | 🟡 YELLOW | 6 datotek | NE | DA | ⚠️ | survival_rate rabi `MAX(0, MIN(100, ...))` guard (sessions_router:887-889). frag_potential/session_stats_aggregator/session_graph_generator ŽE capajo. |
| FIX-4 RCA-2 proximity re-ankr | 🟢 **GREEN** | 1 mesto | NE | DA | ✅ | Targeti potrjeni (3464/3570/739/1523). Lua 6.02 contract ohranjen. sha256 gate. |
| FIX-5 M1 weapon | 🟢 **GREEN** | 1 mesto | NE | DA | ✅ | Trivialno, defenzivno. Bundle z FIX-4 (en Lua reload). |
| FIX-6 idle watchdog | 🟡 YELLOW | nov task | morda audit tabela | — | ❌ | **BLOKER:** RCON `status` NE da team info → "štej team 1/2" ne deluje kot načrtovano. Rabi drug RCON ukaz / drugačno "active" detekcijo. Je feature proposal, ne le fix. |
| FIX-7 lua_round_teams mislink | 🟡 YELLOW | 3 datoteke | NE | DA | ⚠️ | Diagnostic POTRJEN: vseh 22 je PRAVI mislink (drift 199-1500s vs warmup+pause max 29s), 5 post-2026-05-06. relinker NE pokriva lua_round_teams. Odloči pristop (A: extend mixin / B: nov task / C: extend relinker). |
| FIX-8 c0rnp0rn8 clamp | 🔴 **RED** | 2 datoteki | NE | DA | ❌ | Pravi math bug (`bit.rshift` brez `% 8` na c0rnp0rn8.lua:187-188/192; proximity_tracker:1437 ga ima). Dotika reinf calc → previdno, popraviti PRED deployem. |
| FIX-9 housekeeping | 🟢 **GREEN** | 3 mesta | NE | DA | ✅ | Logging = pure win; Proximity.tsx rose guard opcijski (React ni deployan). |

**Povzetek:** 3 GREEN (FIX-4, 5, 9 — READY za FAZO C) · 4 YELLOW (FIX-1*, 2, 3, 6, 7 — rabijo prilagoditev) · 2 RED (FIX-1, 8 — rabijo popravek pred kodo).
**Proces se je izkazal:** adversarna preverba je ujela 2 nevarna buga v P0 predlogih (FIX-1 bi izgubil 96% R2, FIX-2 bi crashnal) — PREDEN smo napisali kodo.

## FAZA C — Implementacija
Šele GREEN fixi. Vrstni red: P0 → P1 (Lua bundle: FIX-4/5/8 en reload) → P2 → P3.
Feature branch per sveženj, diff pred commitom, en bundled PR per sveženj.

## Verifikacija (po implementaciji)
- `python3 -m py_compile` + import check; `pytest tests/ -q` relevantnih; `ruff check` = 0.
- DB: read-only before/after canary (brez mutacij).
- Lua: test server + sha256 živa==repo + homepath; owner map load (NE lua_restart).
- Frontend: vizualno prek **legacy JS** poti.

## Odprta ops vprašanja (za P2)
- Idle prag (60 min?), reload target (vedno `map supply` vs rotacija), `g_spectatorInactivity` (300-600s?).
