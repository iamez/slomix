# Plan: Review closure + Good Night Engine roadmap

**Zadan:** 2026-07-13 · **Zadnja osvežitev:** 2026-07-13
**Vir:** 20-dnevni pregled (`slomix-review-20dni`) → nadaljevanje v gradnjo.
**Legenda napredka:** ✅ done · 🔜 v teku · ⏳ owner-gated · ☐ todo

---

## Kontekst

20-dnevni pregled je **zaključen** — vse najdbe popravljene, prod zdrav na **1.25.0**
+ Data Trust endpoint (#494) + bot crash-loop fix. Preverjeno da nič ni pozabljeno:
FULL_REVIEW §6 vseh 10 postavk obravnavanih, §8 sprint vse 4 done. Ostaneta samo **2
owner-gated review postavki** + **Good Night Engine vizija** (največji odprt projekt;
Phase 0+1 + Story layer že shipani).

**Owner odločitve (2026-07-13):**
- Betting cutoff = **po 1. mapi** (opcija b).
- Dual-frontend = **najprej analiza** (ne brisanje).
- Good Night = **gradi vse tri rezine** (Story → Map → Fingerprint) sekvenčno.
- Vse novo UI gradi v **legacy JS, NE React** (React migracija = večletni projekt).

**Realnost:** velik del "Good Night" je že shipan — `good_night_service.py` (Index v0),
`storytelling/moments.py` + narrative + momentum, Good Night verdict card + 5-moment strip
na Session Detail, player `archetypes.py` + story kartice. Plan cilja **dejanske vrzeli**.

---

## Track A — Review closure (hitro, ~2 mala PR-ja)

### A1. Betting `closes_at` cutoff = po 1. mapi (§6.4, opcija b) — ✅ KODA DONE, ⏳ merge
- **Datoteka:** `website/backend/services/bets_lifecycle.py::maybe_open_market`.
  Auto-open zdaj izračuna `closes_at` = konec 1. mape (prva dokončana R2 po gaming seji,
  `round_start_unix + actual_duration_seconds`); fallback = `now + BETS_CLOSE_AFTER_MINUTES`
  (default 20) če 1. mapa še ni gotova. `bets_router.py` cutoff že uveljavlja.
- **Testi:** 3 novi unit testi (`test_bets_lifecycle.py`), 25 passed.
- **Stanje:** veja `feat/betting-closes-at-cutoff`, **PR #496 (CLEAN, zelen)** — čaka owner merge-OK.
  (Pillow 12.2.0→12.3.0 bump v istem PR-ju = pip-audit CVE fix, ne moja koda.)

### A2. Dual-frontend reachability analiza (§6.8, "najprej analiza") — ✅ DONE
- **Deliverable:** `docs/DUAL_FRONTEND_REACHABILITY_2026-07-13.md` (poročilo, NE brisanje).
- **Rezultat:** dosegljivost določa `route-registry.js` `mode` — **4 LIVE React** (ProximityPlayer/
  Replay/Teams, SkillRating = edine MODERN route) vs **21 STAGED** (registry mode=LEGACY →
  renderira legacy JS; .tsx obstaja + `route-host.tsx` jih lazy-importa, a se nikoli ne mountajo).
- **Priporočilo:** NE arhiviraj (owner odločil); staged strani = namerno večletno React delo.
  Edina cena = morajo ostati build-clean. Promocija strani = flip `mode` na MODERN (1 vrstica).

### A3. Housekeeping (nizka prioriteta) — ⏳ owner-gated
- `#495` release 1.26.0 — owner: **ne bumpaj verzije še**; pusti odprt.
- 2 stash-a na dev — **owner odloči** keep/commit/drop (NE dotikam se).
- `DROP TABLE storytelling_kill_impact_bak_kis_20260709` po potrjeni stabilnosti (owner).
- sudo geslo rotacija (owner, sam kasneje). VM detached HEAD (kozmetika).

---

## Track B — Good Night Engine (sekvenčno, vsaka rezina svoj mini-projekt)

**Vzorec za VSAKO rezino:** `Phase-0 read-only backtest (dokaži s tabelo) → API endpoint →
friendship-safe UI`. Public surface = "nad svojo formo" ton, ne globalne lestvice.

### B1. Story layer — poglobi (rank 1) — ✅ shipan v PR #499 (čaka merge-OK + tone review)
- **Stanje:** Good Night verdict card + 5-moment strip ŽE na Session Detail. `moments.py`
  ima 11 detektorjev + type-diversity selekcijo (one-per-type, potem po zvezdah).
- **Prvotna ocena (2026-07-13):** "že dobro zgrajen". **Popravek po Phase-0 backtestu
  (2026-07-14, `scripts/backtest_moment_director.py`):** type-diversity JE rešena, a odkrita
  je bila **konkretna rangirna vrzel** — tipičen večer saturira 5★ strop (team_wipe 251 +
  multikill 205 vsi na 5★), zato je edini tie-break bil kronološki → `team_wipe` je skoraj
  vedno vodil, isti igralec je zasedel 2–3 od 5 slotov.
- **Fix (PR #499):** `_select_director_cut` — zvezdice ostanejo primarne, enako-zvezdični
  izenačeni razbiti z (a) kinematično prioriteto tipa (`_TYPE_PRIORITY`, redke odločujoče
  poteze naslavljajo), (b) igralsko razpršitvijo. A/B nad 12 sejami: različnih igralcev v
  top-5 → 5/5 (bilo 3–4), vodilni moment → odločujoče objective/carrier (bilo team_wipe).
  9 novih testov, ruff čist. **Owner tone knob = vrstni red `_TYPE_PRIORITY`.**

### B2. Map Intelligence — "where pushes die" (rank 2) — ✅ ŽE SHIPAN (#437)
- **Ugotovitev 2026-07-13:** NI vrzel. Feature je **live** — commit `23f1849`
  "'Where pushes die' map overlay (slice 2) (#437)" + dedup fix #439.
  - **Endpoint:** `GET /api/proximity/push-deaths/heatmap` (`proximity_positions.py:528`) —
    death pozicije pushajoče ekipe v objective-directed push oknih (`proximity_team_push`) +
    carrier deaths, dedup na cp.id, 512u grid.
  - **UI:** `website/js/proximity.js:3498 renderCombatHeatmap(mapName, 'pushes')` — canvas
    nad map underlay, `perspective='pushes'`, objective_zones.json naložen za zone risanje.
- **Phase-0 backtest** (scratchpad) je neodvisno potrdil signal (top-5 celic 15–36% smrti =
  3–8× nad uniformno) — a produkcijski endpoint je BOLJŠI (push-window + carrier, ne surov victim_xy).
- **Preostala mikro-vrzel (opcijsko, owner tone):** cluster labeling po imenu objekta
  ("Tank Barrier", "Command Post") — trenutno riše zone, ne poimenuje top death clustrov.

### B3. Player Fingerprint — "Player DNA" kartica (rank 3) — ✅ ŽE SHIPAN
- **Ugotovitev 2026-07-13:** NI vrzel. Radar kartice so **live**:
  - **Endpoint:** `GET /api/proximity/player/{guid}/radar` (`proximity_player.py:122`) —
    5 osi (Aggression, Awareness, Teamplay, Timing, Mechanical).
  - **UI:** `session-detail.js:3558` per-player playstyle radar kartice (6 osi Chart.js:
    Aggression/Precision/Survivability/Support/Lethality/Brutality) + `archetypes.py` archetip.
- **Preostala mikro-vrzel (opcijsko):** poenotenje 5-os proximity radar vs 6-os PCS radar v
  eno "DNA" kartico na Profile strani — a to je polish, ne manjkajoča funkcija.

---

## Sekvenca — REVIDIRANA 2026-07-14

**Track B rezine 1–3 (rank 1–3):** B2/B3 že shipani; **B1 Moment Director** je dobil pravo
rangirno izboljšavo (PR #499 mergan — star-tiered director cut + player spread). **Nova stava
zgrajena:**

- **Rank 4 Team Chemistry** — ✅ že shipan (`/storytelling/synergy` + `/proximity/duos`).
- **Rank 5 Spawn Economy** — ✅ že shipan (stagger v player-profile + proximity STOPWATCH panel).
- **Rank 6 Objective Pressure** — 🔨 **ZGRAJEN, PR #501** (čaka merge-OK). "real pressure
  seconds" v0.2: `objective_pressure_service` (3D per-zone + enemy-contest + teammate-support),
  endpoint `/api/proximity/objective-pressure`, Session Detail panel "Objective carriers".
  Phase-0 backtest dokazal signal (KaNii = ponavljajoč skriti objective-igralec). 10 testov.

Zaporedje statusa:
1. ✅ **A1 betting cutoff** (#496 mergan), **A2 dual-frontend** (poročilo), **story maps** (#497 mergan).
2. ✅ **B1 Moment Director** izboljšan+mergan (#499).
3. ✅ **rank 4/5** verificirano že live; **rank 6 Objective Pressure** zgrajen (#501).
4. ☐ **Owner tone-review** #501 (uokvirjanje + empty-pressure prag) + morebiten mikro-polish.
5. Naslednje stave: rank 7 Greatshot Clip Director, rank 9 Life Cards, rank 11 Aim Truth (kasneje).

## Stanje = ZAKLJUČENO (razen owner odločitev)

Ves konkreten kod/analiza-rez tega plana je opravljen. Preostane le **owner-gated**:
merge PR #496 (A1), morebiten tone-review mikro-polish, in Track A3 housekeeping (bump #495,
stashi, drop bak_kis, sudo rotacija). **Nič za avtonomno graditi** — nadaljnja gradnja bi bila
duplikat že shipanih funkcij ali potrebuje owner usmeritev.

**Pravila:** vsaka rezina = ločen bundlan PR. Pred vsakim UI: owner tone review. Vsi
endpointi read-only. **Nikoli merge brez owner OK** (za vsak PR posebej).

## Verification
- **A1:** ✅ `pytest tests/unit/test_bets_lifecycle.py` (25 passed).
- **A2:** poročilo-tabela dosegljivih vs mrtvih strani; owner pregleda.
- **B2/B3:** vsak Phase-0 = read-only skripta (tabela za owner); endpoint smoke (`curl` dev);
  UI pregled na dev. ruff+pytest clean, bundlan PR → CI zelen → owner review/merge.
- **Prod:** nič v tem planu ni prod-deploy; deploy prek deploy_release.sh/git-checkout ko owner želi.

## Out of scope
Owner odločitve še ne dane: dual-frontend dejanski arhiv (po A2), stash usoda, #495 bump timing,
session_lifecycle FIX-4/5 Lua reload, SUPASTATS Excel (čaka file). Good Night rezine rank 4+
(Live Director, Life Cards, Museum, Aim Truth) — kasnejše faze.
