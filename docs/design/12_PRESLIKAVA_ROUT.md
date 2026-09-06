# Preslikava rout — vsaka od 33 rout na dizajnerske vzorce

**Datum:** 24. 8. 2026 · **Status:** lokalno, netrackano
**Podlaga:** tabela A iz `07_PARITETNI_POPIS` (31 rout + landing + clips) ×
besednjak iz `11_KOMPONENTNI_POPIS`. »Prototip« = neposredna predloga obstaja;
»izpeljava« = sestavi se iz vzorcev po pravilu P3.

Legenda vzorcev: DT=DataTable, KPI=KpiTile vrsta, SH=SectionHead, MC=MapCanvas,
MS=MapStrip, ER=ExpandableRow, SP=SparkSvg, Δ=DeltaCell, ▂=BarCell.

| # | route | faza | predloga | vzorci + posebnosti |
|---|---|---|---|---|
| L | `landing` (novo) | 1 | **prototip** `landing.dc.html` | hero naslov + live panel (StatusDot, mini SP), »last night« povzetek z BigScore, 4× KPI, 4 vstopne kartice (SH + lasnica v barvi sekcije), recent evenings DT, quick leaders DT, CTA pas |
| 21 | `admin` → About | 1 | **prototip** `about.dc.html` | prozni bloki (max-width ~44em), PipelineList, »six checks« mreža, 5 surfaces stolpci, števke KPI — ⚠️ brati v živo `round_number IN (1,2)` brez botov (O6), SidePanel »this build« (`/api/build`) + health vrstice (`/api/system/overview`), diagnostika = obstoječih 14 sond kot DT |
| 28 | `system` | 1 | izpeljava | DT sond (ime, status StatusDot, vrednost Mono, čas) + KPI vrha; vir `/api/system/overview`; `no-store` (memory: system_overview_page) |
| 29 | `smart-stats-diag` | 1 | izpeljava | DT pokritosti (`/api/diagnostics/storytelling-completeness`) + EmptyState razlogi |
| 1 | `home` | 2 | **prototip** `home-i-full` (projekt) | live+voice pas, BigScore hero, KPI, SP kpm, 3× aktivnost (SP + MapDist ▂) s Chip preklopnikom, sezona (progress ▂ + leaders), latest games, quick leaders, availability čipi, iskalnik, earlier evenings, standing figures — 1:1 pariteta s 13 legacy nalagalniki (07 §B.5) |
| 2 | `sessions` | 2 | izpeljava (landing »recent evenings« razširjen) | DT sej: datum, rd, pl, score Mono; filter Chip; klik → session-detail |
| 30 | `sessions2` | 2 | izpeljava | kot sessions + BOX score stolpci (pravi BOX iz #757) |
| 3 | `leaderboards` | 2 | izpeljava (landing »leading this week«) | več DT blokov s SH + Chip obdobje; Δ proti lastnemu povprečju |
| 4 | `maps` | 2 | izpeljava | MS vrh + DT map (levelshot sličica, plays, winrate po strani z allies/axis ▂) + **objective records** sekcija (`/records/maps/segments`, 07 §B.6) |
| 6 | `weapons` | 2 | izpeljava | DT orožij + `by_player` prek ER; hit-regions kasneje na profilu |
| 5 | `form` | 2 | izpeljava | DT igralčeve forme + SP trend na vrstico (Δ os) |
| 11 | `awards` | 2 | izpeljava | DT nagrad po kategorijah; sezona zavihek |
| 8/9/22 | `record-book` (vsrka records + hall-of-fame) | 2 | izpeljava | Tabs (Records / Hall of Fame / **Season** — 07 §B.6), vsak DT; hash aliasa `#/records`,`#/hall-of-fame` → `?tab=` (shim, dokazano v 13) |
| 23 | `retro-viz` | 2 | izpeljava | obstoječa vizualizacija prenešena v MC posodo; podatkovno na pariteti (07 §B.6) |
| 7 | `profile` | 3 | izpeljava (največja) | glava igralca (identity strip, aliasi), 5 zavihkov kot legacy `_PF_TABS`; 22 endpointov: DT-ji (maps/weapons/relationships/nick history/career), hit-regions **body SVG** (prenos `_bodySvg:1256`), **aim rose** (MC brez podlage), rating SP, memory/competitive/reactions kartice → vrstice s SH; zapisovalni tokovi identitete v fazi 6 |
| 26 | `story` | 3 | izpeljava | narativni bloki (prozni stil About) + KIS Breakdown DT + details modal→**stran** (formula panel), momentum SP, Comp Skill board DT, coverage note EmptyState; izbirnik dvoumne seje |
| 25 | `rivalries` | 3 | izpeljava | DT lestvica + H2H pogled (PairBar) — legacy 558 vrstic je edini vir (React je škrbina) |
| 24 | `skill-rating` | 3 | prekritje | obstoječa ŽIVA React stran prepiše videz v besednjak (edina že MODERN med statskimi) |
| 31 | `session-detail` | 4 | **prototip** `session-detail.dc.html` | Scoreboard glava, Tabs ×4, KPI, SP kpm, maps DT (levelshoti + side ikone + fullhold/surrender), teams DT z detailed preklopom, **players DT 22 stolpcev** (vsi tooltipi iz prototipa — so pravilni), teamplay PairBar ×5, telemetry povzetek + links; + 7 panelov, ki jih prototip nima (07 §B.1: data trust, good night, verdicts, moments, objective pressure, life cards, MVP glasovanje) → vrstični paneli s SH po P3; `warnings`/`debug.counted` ob score (golo »3:2« laže) |
| 10 | `live` | 6 | izpeljava | landing live panel razširjen: StatusDot glava, feed DT (polling iz `hooks.ts` uglasitev), live ladder; warmup okno NI hrošč (memory) |
| 12 | `proximity` | 5 | **prototip** `proximity.dc.html` · ⚠️ obvezno ob fazi 5: `17_PROXIMITY_POPIS` (91 poti, razredi A–D, O9) | scope Chip vrstica (session→map→round), data-completeness pas (⚠️ + orphani — resnica, 02 §4), roster DT z Δ in ▂, ER → 6 pod-sekcij (MC poti s hitrostno rampo — pasovi izpeljani, O7; fights DT; reaction windows; cover DT; crossfire DT; per-map ▂ + composite SP); + 42 legacy panelov, ki jih prototip ne riše → vrstični paneli (seznam v 07 §B.2) |
| 13 | `proximity-player` | 5 | prekritje | ŽIVA React stran → besednjak |
| 14 | `proximity-replay` | 5 | prekritje + `replay.js` prenos | engine/projection modula iz 08; barve kot vbrizgana konfiguracija |
| 15 | `proximity-teams` | 5 | prekritje | PairBar jezik |
| 27 | `replay` | 5 | izpeljava | MC + Timeline scrubber (spiderweb vzorec) + event DT |
| — | `spiderweb` (novo, spec) | 5 | **prototip** `spiderweb.dc.html` (projekt) | točka pogleda Chip (Team A/B/World), MC web, Timeline scrubber, SidePanel clock (značka = razsodba backenda: VALIDATED/UNVALIDATED/…, popravek 25. 8.), SNAPSHOT INTEGRITY (tri-stanja), gaps EmptyState, edges DT, »what team A could know«, 4 sloji footer — VSE po `SPIDERWEB_UI_DATA_CONTRACT` (kaj stran NE sme trditi) |
| 18 | `uploads` | 6 | **prototip** `uploads.dc.html` | Dropzone, Chip filtri s števci, DT datotek, SidePanel allowlist (živ iz validatorjev) + »where things go« + TagCloud; resumable uploader prenos (08) + AbortSignal |
| 19 | `upload-detail` | 6 | izpeljava | glava datoteke + video predvajalnik (legacy modal → stran), DT metapodatkov |
| 16 | `greatshot` | 6 | izpeljava | DT demov + status pipeline (PipelineList vzorec) |
| 17 | `greatshot-demo` | 6 | izpeljava | poročilo: KPI + highlights DT + render statusi |
| 20 | `availability` | 6 | **prototip** `availability.dc.html` | velika števka `n/6` + segmentni trak, StatusSelector, poimenski stolpci po statusih, DayCards teden, MiniCalendar, PrefRow ×4, planning room panel (LOCKED stanje; auto-open = O2); ⚠️ NI prenos — novo delo po legacy stanjskem avtomatu (08) |
| C | `clips` (novo) | 7 | **prototip** `clips.dc.html` | predvajalnik + up next + mreža 4× + filtri; blokira O1 (javnost) + backend (poster/plays/transcode — 02 §5) |

## Pokritost

- **Prototip neposredno:** 8 rout (landing, about, home, session-detail,
  proximity, spiderweb, uploads, availability) + clips (čaka O1).
- **Prekritje žive React strani:** 4 (skill-rating, proximity-player/replay/teams).
- **Izpeljava iz besednjaka:** 20 rout — nobena ne rabi novega vizualnega
  izuma; vse so DT/KPI/SP/MC kombinacije. To je operacionalizacija P3.
