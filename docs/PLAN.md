# PLAN — edini vir resnice za tekoči načrt

> Pravilo: ta datoteka se posodobi ob VSAKEM koraku. Nič se ne »dogovori«
> samo v pogovoru. Bereta jo obe seji (in vsak prihodnji model).
> Podrobne raziskovalne zapiske drži lokalno (docs/REPO_BOUNDARY.md);
> tu je samo načrt in pozicija. Repo je javen — brez skrivnosti.
>
> **Sočasnost (več agentov, plan mode):**
> - Plan-mode datoteke (`~/.claude/plans/*.md`) so ZAČASNE in si jih seje
>   DELIJO po slugih — ista datoteka je bila prepisana 3× v dveh dneh
>   (tri različne seje, trije nepovezani načrti). Nikoli niso vir resnice:
>   trajni izid se ob ExitPlanMode PREPIŠE SEM.
> - Ta datoteka se ureja SAMO prek veje+PR (kot vse) — sočasni prepis se
>   pokaže kot git konflikt, ne kot tiha izguba; vsaka verzija je commit.
> - Vsaka delovna proga ima SVOJ razdelek in ureja samo svojega +
>   skupno glavo; razdelki različnih prog se v gitu zlijejo brez konflikta.
> - Vsak razdelek nosi vrstico »Zadnja posodobitev: datum (kdo)«.

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, uploads rezina 2)

## Proga: nova stran (Fable)

### Kje smo

Nova SPA (website/frontend/src/app) — faza 5 ZAKLJUČENA, faza 6 v teku.
Prod ZAMRZNJEN na v1.39.0 (ownerjeva odločitev 2026-08-28); dev soaka;
deploy NI naloga.

| stanje | vrednost |
|---|---|
| izdana verzija (dev) | v1.44.0 (2026-09-02); vlak 1.45.0 = #882 |
| endpoint gap (H1) | **3** (dolg r. 1 zapre `/api/diagnostics`; ostanejo `/api/bets`, `/api/bets/market` = ownerjeva odločitev, `/api/stats/sessions` = z upokojitvijo legacy JS) |
| proximity inventory pending | **0** (#884) |
| zgrajene strani faze 5 | proximity (6 rezin + 8 outcome instrumentov), player profil, team comparison, replay, spider-web SW-1 |
| zgrajene strani faze 6 | availability r. 1 (#887), uploads r. 1 (#888), live (#889, kurzor feeda popravljen po reviewu), greatshot (#890) |
| availability r. 2 (ta veja) | linked formi (settings, kanali prek link-tokena, DELETE), promotions (status+jobs, preview z recipients, schedule), betting (bazen, multiplikator, stava, denarnica; BREZ admin kontrol — owner 2. 9.); fixturi povezane stopnje prek dev sentinela (`scripts/e2e_sentinel_rows.py`) + harness posnetkov |
| uploads r. 2 (ta veja) | upload form (single-shot ≤ 50 MiB z XHR napredkom + cancel; resumable init/PATCH/finalize z 409 resync, HEAD resync, stall guard, abort), delete na detailu (dvostopenjsko); fixturi iz ŽIVEGA kroga s sentinelom (init→PATCH→finalize→detail→DELETE) |
| delovna površina | 2. 9.: 41→4 worktreejev, 400→43 lokalnih vej, #891 mergan; protokol v memory `worktree_cleanup_protocol_2026-09-02.md` |

## Naslednji koraki (vrstni red) — owner 6. 9.: **dolg → faza 7 → pregledni PR**

0. **Dolg r. 1 (6. 9., MERGAN #919)**: keymap 7 rut zares preslikanih (guard:
   zgrajena ruta ne sme nositi `phase-N` — videti pasti na starem keymapu),
   `/replay` → preusmeritev na `/proximity` (edina nezgrajena ruta umaknjena
   iz `routes.data.json`), `/api/diagnostics` kot admin panel na `/admin`
   (anonimni ne pošlje zahteve) → **vrzel endpointov 4 → 3**.
1. **Faza 6 — preostanek**: availability rezina 3 = admin market kontrole
   (`/api/bets/market`, settle) — ownerjeva odločitev, kdaj; `/api/bets` in
   `/api/stats/sessions` se zapreta šele z upokojitvijo legacy js.
3. **Spider-web follow-upi** (3D kamera, belief regions, label placement;
   W6) — premaknjeno ZA paritetno fazo 6: polish ne prehiteva paritete
   (razlog zapisan 2. 9.).
4. **Faza 7**: r. 1 (6. 9., **MERGANA #920**) = `compare` (`/compare/:a?/:b?`, šest
   legacy vrstic iz profilnega endpointa, barva = boljša stran) in `wrapped`
   (`/profile/:id/wrapped`, canvas 1080×1920 v žetonih — brez gradienta,
   radius 0, pravilo pripeto v testu — + dejstva kot besedilo, copy/download);
   obe kot RUTI (dizajn sistem nima modalov), povezavi v glavi profila;
   `PickPlayer` seljen iz Rivalries v `components/`. **O1 zaprta 6. 9.:
   owner (c) → Clips strani NI** (33. zaslon odpade; 32 rut). `/rounds` že
   preusmerjen. Ostane: končni paritetni prelet (SPA, vse rute × 4 viewporti
   × anon/owner — `scripts/audit_website_browser.mjs --app --manifest`), potem
   pregledni PR-ji za ultra (glej točko 5 — rezine; ⛔ `19c61847` je bil hash
   iz stare zgodovine).

2. **Faza 6 r. 3 + popravek merilnika (6. 9., veja `feat/availability-admin-market`, PR #915):**
   admin market kontrole (open / settle / void, `POST /api/bets/market`);
   greatshot sekcije highlights/clips/renders (ruta je `:section?` nosila od
   faze 6, stran ga je ignorirala — brez novega endpointa); rating trendi na
   profilu (`skill/player/{}/form` + `/history`).
   ⛔⛔ **Popravek ekstraktorja:** legacy zajem se je ustavil pri prvi `${`,
   zato je odrezan prefiks (`/api/players`) veljal za pokritega, brž ko nova
   stran kliče karkoli globljega. 29 legacy klicev nosi interpolacijo s
   segmentom za njo. Merodajno število po mergu izpiše
   `pytest tests/integration/test_endpoint_gap.py` — vsaka nova vrstica pride
   z zapisanim razlogom, ne kot tiha zamenjava števila.
   ⚠️ `compare` in `wrapped` iz te veje sta bila ODSTRANJENA: #920 ju je
   mergal medtem, in mainovi različici sta ostali.
5. **Ultra pregled = 20 rezin (6. 9.)**: meja ≤ 8 000 vrstic / 500 datotek na
   pregled, koda od proda 93 k → `scripts/review_slices.sh` (obratna baza:
   `review-base/NN-<območje>` = main z območjem na v1.39.0; glava `review/NN` z
   mainovim drevesom — GitHub zavrne glavo, ki je prednik baze; draft
   PR-ji »review: … — NEVER MERGE«, telesa `docs/review/SLICES.md`, vodnik
   `docs/REVIEW_GUIDE.md`, spiderweb `docs/SPIDERWEB_STATUS.md`). Rez = meritev
   20/20. Vrstni red (owner): 01 proximity+spiderweb+Lua (5 301) → 02 backend
   routerji (6 411) → 03 SPA lib (7 708) 7. 9. opoldne; ostale po dnevih.
   ⛔ po #882 (v1.45.0) `cut --push` znova. Nato triaža najdb (Astra, zanka
   `docs/process/MANDELBROT_RCA.md`) → 1–2 tedna teka na dev → pogovor o
   produkciji. **Astra predaja**: `AGENTS.md`, `docs/prompts/astra_kickoff.md`,
   `docs/AGENT_LOG.md`, `~/.codex/*` (memory `astra_codex_handoff_2026-09-06`).
   **Watchdog proga** (Astra, po triaži): obseg `docs/design/24_WATCHDOG.md`
   (lokalno) — opazovalec + Discord alarmi z dedupom, nikoli zaganjalnik;
   dokaz = simuliran izpad → alarm ≤ 2 min, noč brez izpada → 0 alarmov.
6. **Raziskovalne proge (owner 4. 9.: doc 22 naslednja, pred doc 19 / moments r. 2):**
   - `docs/design/22` (lokalno, **napisan 4. 9.**) — **»digitalni dvojčki« botov**:
     `player_track.path` (200 ms, 74 480 življenj, regularji 28–63 sej/mapo)
     → profil igralca (vozlišča, dwell = nova kemp metrika, tempo); Omni-bot
     0.91 na puranu = en `.way` graf na mapo, per-bot le `OnBotJoin` +
     `bot.SetRoles` + kamp čas + tempo → **»njegovi cilji, njegova kamp mesta,
     njegov tempo«**, ne dobesedna pot; rezine 1–5 v docu; odločitve za ownerja.
     **Rezina 1 izmerjena 5. 9.** (`scripts/backtest_route_distinctiveness.py`,
     veja `feat/bot-twins-route-distinctiveness`): polovica igralca najde
     SVOJO drugo polovico med desetimi v 81 % (@512) / 91 % (@256) proti 10 %
     naključja, kontrola 0–20 %; a »najbližja točka« da 2–6 u → osebnost je
     ČASOVNA UTEŽ, ne kraj; prag sej 25 (pod njim 63 %); dwell 10–22 %, top
     celice skupne (spawn čakanje) → rezina 2 ga izloči. #913 mergan 5. 9.
     **Rezina 2 zgrajena 5. 9.** (veja `feat/bot-twins-camp-profile`): metrika
     »drži položaj« = `GET /storytelling/camp-profile` (tipizirana; hold =
     ≤ 96 u od sidra ≥ 4 s, still = speed < 10 ≥ 3 s; prvih 3 s življenja
     izven SEZNAMA mest; < 60 s živ → `null`, ne 0) + peta plošča vlog na
     Story strani. Izmerjeno pred gradnjo: 90 % počasnih točk so postanki
     < 1,2 s (delež počasnih točk NI kemp → epizodna metrika); obe definiciji
     stabilna lastnost igralca (Spearman polovic +0,61…+0,95). Živ dokaz:
     seja 154 hold 11–18 %, seja 120 16–23 %, hladno 0,9–1,1 s, toplo 3 ms.
     #914 mergan 5. 9. Naslednje: r. 3 (per-bot `.gm` profil iz `top_cells`
     + tempa) — owner je 5. 9. izbral **najprej moments r. 2** (spodaj).
   - **Moments r. 2 (doc 20 §7.2) — MERGANA #916 in DEPLOYANA na puran
     5. 9. 23:16** (sha256 = main, `FH watcher version=6.14`; migracija 082
     na prod ob naslednjem release deployu; odprto: en večer
     `frame_health.log`). Vsebina: Lua v6.14 (`first/last_move_time` na
     `VEHICLE_PROGRESS`, nova sekcija `VEHICLE_DESTROYED` iz `et_Damage`
     veje pred `isValidClient` — izvor g_combat.c:1857 kljuko sproži za vsako
     entiteto), parser + migracija 082 (3 stolpci na `proximity_vehicle_progress`,
     JSONB seznam uničenj, brez nove tabele), detektor `escort_mover` z
     `timestamp_source: "first_move"` in `destroyed_by`. Testi: harness
     `tests/lua/vehicle_tracking_harness.lua` v CI (3 mutacije padle), parser 5,
     escort 13. Runtime: lokalni ET 2.85 (:27961) z boti, 5 rund — dve pasti
     v živo (supply truck se sam odpelje ob 0,6 s → `first_escort_time`;
     goldrush skript tank ob 1,0 s »ubije« prek `G_Damage` → smrt brez
     igralca šteje šele po prvem escortu) in ena o motorju (kljuka teče PRED
     odštetjem zdravja). ⚠️ Kontrakt `destroyed_count`: korpus pred v6.14
     nosi fantomsko +1 na goldrush rundah (popravek = odprta naloga).
   - **Dvojčki r. 3 — zgrajena 6. 9.** (veja `feat/bot-twins-profile-generator`):
     `scripts/build_bot_twin_profiles.py` → `server/omnibot/twins/` (profil na
     bota z `ReactionTime`, `<mapa>_twins.gm` z vlogami + kamp časi na
     njegovih razločevalnih ciljih, tabela imen s `profile=` in pravim
     razredom) + `docs/design/23_TWINS_REPORT.md` (lokalno). 5 dvojčkov,
     43 ciljev; ⚠️ kontrola (premešane seje) preživi ≈ 21 % — pragi iz
     kontrole, številka je v poročilu. Deploy na puran + bot test = owner;
     r. 4 = harness bot proti človeku (+ kontrola proti tujemu profilu).
   - `docs/design/19` (lokalno) — **modularni statsi + per-user pogled**:
     register datasetov + `user_page_layouts` + column picker/sekcije/home
     v 6 rezinah; zajemna stikala ŠELE zadnja in le s coverage zastavico.
   - `docs/design/20` (lokalno) — **match moments: escorting objective +
     ET-specifični detektorji** (Lua zajem → importer → detektor → Story).
   - `docs/design/21` (lokalno) — **runtime v2 / event brain**: owner 3. 9.
     odločil: ena meja domene, LOČENI procesi (bot/web bralca, baza trajni
     cilj); prva rezina = `events` tabela + `pg_notify` iz »runda končana«;
     ⛔ **šele po ultra pregledu** nove strani, ne prej. Brez Redis Streams,
     brez enega procesa.

| ratchet | stanje |
|---|---|
| endpoint gap | ⛔ **16** — merjeno 3, dokler ekstraktor ni bral čez interpolacije (popravek 5. 9.; 16 endpointov je bilo nevidnih). Popravek: 4 → 3 (rezina 3), nato 3 → 19 (korekcija), nato 19 → 16 (faza 7) |
| proximity inventory pending | **0** (#884) |

## Proga: Stats 2.0 — ena stran »Stats / Sessions« (Fable 5.1)

**Zadnja posodobitev:** 2026-09-03 (Fable 5.1, R4 mergan; R5 v PR-ju)

Owner (3. 9.): »Sessions« + »Sessions 2.0« → ENA stran; seznam po datumu in
id-ju s thumbnailom; ob kliku najprej jedrnat summary (basics tabela +
tekstovne nagrade v gibhub slogu), podrobnosti za klikanje do power userja.
Dizajn: `docs/design/18_STATS_2_0_SESSIONS.md` (lokalno). Odločitve: vzdevki
nagrad (tabela v backendu) · Smart Stats = zavihek session strani · ACC =
hits/shots lahkih orožij.

| rezina | obseg | stanje |
|---|---|---|
| R1 | en arhiv `/sessions` z levelshoti, `#id`, BOX, mape, »one half missing«; `/sessions2` redirect; podnav brez podvojitve | #897 merged |
| R2 | backend `GET /stats/session/{id}/basics` + `/awards` (response_model, vrata `/detail` + brez botov, KIS null=not covered, pravila agregacije nagrad z vzdevki, korpusni tek `scripts/audit_session_basics.py`) | **MERGAN** #898 (`ace66e3d`, 3. 9.) |
| R3 | summary: glava z BigScore + trak map z levelshoti + figure; `DataTable` (nov, doc 11) s 17 stolpci in tooltipi (`uk` = useful (legacy), `useless` svoj — owner 3. 9.); nagrade v stavkih; night score + MVP; ostalih 5 panelov za »more ▸«; Playwright thin = seja 80 | **MERGAN** #899 (`965c2928`, 3. 9.) |
| R4 | zavihki Players (21 legacy stolpcev + razširitev na `DataTable`; »Lua Played%« opuščen = kopija Played%) · Rounds (`RoundsTab`, `/rounds` upokojen → `/sessions`) · Teamplay (5 barov sinergije + trade tabela po datumu; `no_data`/`partial_data` = `Absent`) · Story (`SessionStory` kot zavihek; `/story/session/:gsid` → `/session-detail/:gsid/story` prek `PARAM_REDIRECTS`); slovnica zavihkov ENA kopija v `routes.ts`; e2e `session-tabs.spec.ts` (154 + 80, 5 zavihkov) | **MERGAN** #902 (`f3f06cdc`, 3. 9.) |
| R5 | **MERGAN** #903 (`e3b0a70c`, 3. 9.) —  power user: vrstica igralca ▾, KIS details, povezave | — |

Odprto (owner): FSK prag, potrditev vzdevkov, Charts zavihek.

## Proga: match moments (doc 20, lokalno) — Fable 5.1

**Zadnja posodobitev:** 2026-09-06 (Fable 5.1, dvojčki r. 3 v PR-ju)

| rezina | vsebina | stanje |
|---|---|---|
| 1 | `escort_mover` detektor (12.) brez Lua: `proximity_vehicle_progress ⋈ proximity_escort_credit` po 4-ključu + `round_key_filter_sql(alias="vp")`; pragi iz meritve (`ESCORT_MOVER_*` v `base.py`: 1 000 u, delež ≥ 0,25; 3/4/5★ pri 0,25/0,5/0,75); `time_ms` = konec runde (`timestamp_source`); prvi test, ki poganja SQL detektorja (stub); korpus: **19 = 19** (detektor proti SQL, sprejete runde); ⚠️ **v privzetem rezu (10) se ne prikaže v NOBENI seji** (bazeni 50–90 momentov, zvezdice so trda meja) → vidnost = rezina 5 (filter po tipu / svoj panel), ownerjeva odločitev | **MERGAN** #908 (`bd8561e7`, 4. 9.) |
| 2 | Lua: `first/last_move_time` moverja + `et_Damage` pripis uničenja (ownerjev deploy protokol) | — |
| 3 | Lua: zajem escorta NOSILCA (`proximity_carrier_escort`) + migracija + parser | — |
| 4 | detektor escorta nosilca + fixture varovalo »medic ≠ escort« | — |
| 5 | **vidnost (owner 3. 9.)**: `/storytelling/moments?types=escort_mover` (backend filter) + majhen panel »objective escorts« v Story zavihku pod momenti; direktorjev rez nespremenjen; oznake po tipu | **MERGAN** #909 (`6d61805d`, 4. 9.) — `types=` filter + panel `story.escorts` |

## Proga: frame-health v6.13 — watchdog za VSE Lua module + bot test (Fable 5.1)

**Zadnja posodobitev:** 2026-09-03 23:00 (Fable 5.1, v6.13 deployan in izmerjen; proga čaka na pravi večer)

Owner 3. 9.: watcher razširiti na vseh 6 modulov, izboljšati, bot test (~30 min)
za polno obremenitev; RCON `testmode` in deploy za ta PR izrecno predana.

| korak | vsebina | stanje |
|---|---|---|
| 0 | osnovnica: bot test z v6.12 (18:37–19:07, 6 botov, `testmode on/off`) | **izveden**: 2 stalla ≥ 100 ms, 0 ≥ 500, 2 motorjeva hitcha v 30 min — obremenitev z boti strežnika ne muči; `is_bot_round` deluje (komentar na #905) |
| 1 | skupni FH blok (`FH init mod=`, `FM wall mod self top`) v 6 modulih; tracker: `lt`/`paused` na gap vrstici, kapica 300→3000, `init_scan` meritev; `tests/lua/frame_health_modules_harness.lua`; identity test | **MERGAN** #905 (`33126213`) |
| 2 | `scripts/frame_health_report.py` (pripis: Σ self v oknu gapa = naš Lua, ostanek = motor/gostitelj) + test | narejeno |
| 3 | PR, CI, ownerjev merge | **MERGAN** #905 |
| 4 | deploy na prazen puran (scp na ŽIVE poti, map load, `FH init mod=` 6×, sha256 prej/potem; ⛔ nikoli `lua_restart`) | **IZVEDEN 3. 9. 22:2x** — 6/6 sha ujema, 6× `FH init … mod=` + `FH watcher`, motor 6× »loaded into Lua VM«, brez napak |
| 5 | drugi bot test z v6.13 (22:25–22:55) → poročilo; ukrepi v BACKLOG | **IZVEDEN**: 2 gap, 2 `FM` (obe tracker `round_end` 188–224 ms); webhook `sweep` in `init_scan` < 50 ms; 3 motorjevi map-load hitchi; komentar na #905. Naslednje: odčitek pravega igralnega večera |

Osnovnica iz obstoječih logov (report, 2. 9., prazen strežnik): stall 363 s,
naš Lua 16 %, residual (motor/gostitelj) 84 %; 3. 9. do 18:00: 36 s, 22 % / 78 %.

## Proga: lag na puranu + Lua optimizacija (sestrska seja)

**Zadnja posodobitev:** 2026-09-02 (Fable — predaja koordinacije)

Watcher v6.12 ŽIV na puranu (deployan + dokazan 2. 9.). Naslednji večer
igre = meritev (`~/.etlegacy/legacy/proximity/frame_health.log`; zbiralnik
vleče na sambo). Delitev populacij (sestrska seja): A = round-end burst
(naš), B = med pavzo — ⚠️ »ne more biti naša« pokriva SAMO tracker
(levelTime med pavzo zamrzne); webhookov io.popen sweep teče po os.time()
tudi med pavzo in NI izključen. Razsodi meritev prek `self`. Optimizacija bursta: batch write,
šele PO enem večeru self meritev. Sestrska seja koordinira optimizacijo Lua.

## Proga: časovna polja (Opus 5)

**Zadnja posodobitev:** 2026-09-03 (Opus 5 — faza 3 IZVEDENA, proga zaključena)

Dva ločena hrošča v istem deploy oknu (~20. 3. 2026) sta pustila bazo v
stanju, kjer sta obdobji **nezdružljivi**: staro ima engine alive%, a ~2×
napihnjen mrtvi čas (Lua je limbo čas prištevala znova ob vsakem 5-sekundnem
tiku); novo ima pravilen mrtvi čas, a `time_played_percent` je bil od
2026-04 ničla, ker ga aktivna uvozna pot ni pisala. Ker sta komplementarni,
se da vsako obdobje popraviti iz signala drugega.

| faza | kaj | stanje |
|---|---|---|
| 1 | uvozna pot piše `time_played_percent` + parnostno varovalo piscev | ✅ **#885** `f71906ac` |
| 2 | backfill `time_played_percent` iz surovih datotek | ✅ **#886** `fb35e09b`; izveden 2. 9. (+4.666, kontrola 22/22), **ponovljen 3. 9. po restartu bota: 0 rešljivih vrstic — končano** |
| 3 | rekonstrukcija zgodovinskega `time_dead_minutes` iz engine alive% | ✅ **IZVEDENA 3. 9.** — 8.721 vrstic, migracija 081, izvirnik ohranjen v `time_dead_minutes_original`; `dead > played` 80 → 0, `ratio > 100,5` 43 → 0 |
| 4a | per-row varovala v plausibility auditu (4 nova pravila) | ✅ **#892** `75ebdeee` |
| 4b | agregatni razred (»porazdelitev se je premaknila«) | ✅ **#895** `c213346f`, 7 trend pravil |
| 4c | oborožitev namesto utišanja (`Rule.armed_from`) | ✅ **#900** `eea9b617`; po fazi 3 obe dead-time pravili nista več oboroženi (ni več česa izvzeti) |
| 5 | zastareli zapisi, ki so to skrivali | ✅ **#893** `0003e589` |

⭐⭐ **RCA, ki je obseg faze 3 obrnil (3. 9.):** »R2 se je maja 2025 spremenil«
je bila napačna diagnoza. Meja je **datum vpisa**, ne seje: vse vrstice za
2025-01…05 so bile vstavljene 2025-12-20 (bulk uvoz). Primerjava
datoteka ↔ baza ↔ rekonstrukcija (n = 8.369) pokaže, da je **Lua napihnila
enotno ~2,2×** v vseh štirih celicah, uvoznik pa je datoteko prepisal dobesedno
**razen pri bulk R2**, kjer jo je obravnaval kot kumulativo tekme in razdelil
sorazmerno s časom (`× played_R2/(played_R1+played_R2)`, mediana 1,000,
**97,8 %** vrstic znotraj ±10 %). Dve napaki, ki se v mediani skoraj izničita
(1,058) in po vrsticah ne (le 18,2 % znotraj ±10 %).

✅ **Izid rekonstrukcije (3. 9.):** 8.721 vrstic, 26.337 → 12.338 min, mediana
faktorja 1,92. Porazdelitev se čez mejo zdaj ujema v vseh kvartilih
(p25 0,169 / med 0,212 / p75 0,257 proti 0,153 / 0,203 / 0,255 po meji; prej je
bila predmejna mediana 0,365). Preostalih 11 nemogočih vrstic sedi v rundah, ki
jih cevovod že izloča (1× `orphan_r2`, 2× `is_valid = FALSE` bot rundi).

⭐ **Neodvisna potrditev:** agregatno pravilo `pcs_dead_time_share_monthly`,
zgrajeno in umerjeno na pokvarjenih podatkih tri dni prej, je prej javljalo tri
pojasnjene premike (2025-05 +46,5 %, 2026-04 −53,1 %, 2026-05 −41,4 %), zdaj pa
**nobenega** — mesečna serija je ravna 0,19–0,23 čez vseh dvajset mesecev.

⚠️ **Najdba ob strani:** `scripts/db_backup.sh` je tekel kot `website_app`
(ker `website/.env` prepiše `POSTGRES_USER`) in ta ne more brati 7 tabel →
`pg_dump` je odpovedal. Odpovedal je glasno, kar je pravi izid, a razhajanje
med korenskim in website `.env` za administrativna orodja ostaja odprto.

✅ **Bot restartan 3. 9. ob 11:25** (`etlegacy-bot`, dev enota, NOPASSWD;
`etlegacy-web` nedotaknjen): 21 cogov, 98 ukazov, brez napak. Ponovni zagon
backfilla: **0 rešljivih vrstic**; ostane 16 ničelnih v treh rundah
(14 neparsljivih zajemov, 2 vrednosti 101,2 %).

⭐⭐ **Faza 4c: tri »znana« pravila so bila UTIŠANA, kar mutira cel senzor.**
`acknowledged` utiša celo pravilo, torej bi tudi SVEŽA ponovitev iste okvare
padla v isto tišino — natanko tako, kot je pet mesecev minilo prvič. Zato
`Rule.armed_from`: zgodovina se še vedno šteje in prikaže (nov stolpec
»pre-arming«), a izhodne kode in dnevnega alarma ne drži odprtih. Izmerjeno:
`dead > played` 80 vrstic, **nobene po 2026-04-01**; `ratio` 43, nobene po
istem datumu; `tpp = 0` 16, nobene po 2026-09-03. Utišanih pravil: **0**.
Živih kršitev: **0**.

⭐ **Ključna meritev (odklepa fazo 3):** po backfillu `alive_pct_drift` prvič
po 5 mesecih spet deluje — 290 parov, engine 79,3 proti izračunanemu 79,3,
povprečna |razlika| **0,15 o. t.**, le 2 para (0,7 %) nad 2 o. t. To potrjuje
oboje: ALIVE% se premakne zanemarljivo IN formula za staro obdobje drži.

✅ **Backfill ponovljen 3. 9.** po restartu bota; 0 rešljivih vrstic ostane.
Konec-do-konca dokaz, da uvozna pot spet piše `time_played_percent`, pride
šele z naslednjim uvozom (naslednji večer igre) — do tedaj je dokazano le,
da datoteka, ki jo bot poganja, vsebuje stolpec (54 stolpcev v `INSERT`).

⭐⭐ **Razrešeno 3. 9.: »tretja raven« je R2, ne igra.** Ločeno po rundah je
**R1 raven skozi vso predpopravkovo obdobje** (delež mrtvega časa 0,44–0,50),
R2 pa teče pri ~0,22 do 2025-04 in od 2025-05 skoči na R1 raven. Torej
`time_dead_minutes` na R2 vrstici pomeni **eno stvar pred majem 2025 in
drugo po njem** — isti vzorec kot popravek 2026-04, eno rundo globlje.

⭐⭐ **Faza 3 je s tem odločljiva, in odgovor je ločen po rundah:**

| era | runda | n | razred B (baza < 0,9 × rekon) | mediana faktorja |
|---|---|---|---|---|
| zgodnje 2025 | **R1** | 2.708 | **0,15 %** | 2,238 |
| pozno (2025-05..2026-03) | **R1** | 1.724 | **1,28 %** | 2,195 |
| zgodnje 2025 | R2 | 2.596 | **37,1 %** | 1,031 |
| pozno | R2 | 1.693 | 10,0 % | 1,992 |

**R1 = en sam čist mehanizem čez vso ero**, R2 ne. Trije neodvisni razsodniki
(3. 9., razširjeni vzorci):

| razsodnik | pokritost | rekon / razsodnik | baza / razsodnik |
|---|---|---|---|
| izmerjeni dead po popravku (n=4.447, prej 344) | 2026-04→ | R1 **1,0000**, R2 0,9993 | — |
| `round_awards` (endstats.lua, n=126) | 2026-01..03 | R1 **1,0020**, R2 1,0053 | 1,96 / 1,74 |
| `player_track` (proximity, n=888) | 2026-02-11→ | R1 0,9166, R2 0,9335 (metoda vrzeli podceni ~8 %) | 1,94 / 2,00 |

⚠️ **Zunanja razsodnika pokrivata SAMO 2026-01..03** (~2.200 vrstic od 8.700).
Za 2025-01..04 (5.304 vrstic) ni neodvisnega vira — tam stoji rekonstrukcija
na mehanizmu (branje stare Lue) + na tem, da je R1 faktor identičen v obeh
erah (2,238 proti 2,195).

⭐ Kje bi prepis **poslabšal**: proti `player_track` je rekonstrukcija bližja
na **80,7 %** vrstic, baza na 19,3 %; mediana napake pade z **1,125 min na
0,289 min**. Razčlenjeno: pri parih, kjer se kandidata skoraj ne razlikujeta
(≤0,5 min, n=118), je izid vseeno; pri napihnjenih (n=727) rekonstrukcija
zmaga v 83,2 %, pri hudih (n=41) v 97,6 %.

⭐ **Nova najdba 2. 9.:** `revives_given` je 0 na vseh 5.538 vrsticah pred
2025-12 — vsaka vseskozna revive lestvica se tiho začne decembra 2025.

## Proga: SSH monitor / alarmiranje (Opus 5) — PR #923, ODPRT

Sprožil ownerjev alarm na #privat 6. 9.: »Ssh Monitor Failing / 3 consecutive
failures / Error reading SSH protocol banner«.

**Štiri rezine, vse na veji `fix/ssh-monitor-says-what-it-knows`:**

1. `55a0e555` — monitor pove, kar ve: dva vzroka pod enim imenom ločena
   (`[banner/read timed out — remote slow]` proti `[socket closed under the
   read — local]`), `banner_timeout/auth_timeout=45` na vseh petih mestih,
   okrevanje se objavi, proximity dobi glas.
2. `d909fb68` — »consecutive« končno pomeni zaporedne: `STREAK_WINDOW` 30 min
   na **enem** mestu velja za vseh devet ključev (šest jih ni imelo reseta —
   ⚠️ ne sedem od osmih, prešteto je šest od devetih).
3. `7f3dba7a` — Full Jitter razmik pollerjev + **en** ponoven poskus listinga,
   samo za `remote slow`. ⛔ Iskanje je prvo postavko obrnilo iz »zgradi pool«
   v **ne gradi poola**: `connect()` ni thread-safe (paramiko #1904), naše
   operacije tečejo v nitih izvajalca.
4. `443818b7` — nizi preživijo restart (`logs/bot_error_streaks.json`).
   ⛔⛔ Restart ni izgubil le zgodovine, **odložil je naslednji alarm**.
   ⛔⛔ `STREAK_WINDOW` velja tudi ob **branju**, sicer bi trajnost ustvarila
   lažni »Recovered« za izpad, ki je minil pred restartom.
   Datoteka in ne tabela: alarmna pot ne sme viseti na tem, o čemer alarmira;
   brez migracije torej brez prod deploya.

**Stanje: MERGANO** 6. 9. ob 18:02 (`5aca4a76`, squash), z ownerjevim
dovoljenjem. Vseh 8 zahtevanih checkov zeleno; Codacy `fail` s 3 issues ni
zahtevan in je bil identičen že pred rezino 4.

⚠️ **Na dev botu še ne teče.** Ownerjev restart 6. 9. ob 17:17 je bil PRED
mergem in je zagnal `ed0dfe22`, kjer od #923 ni nobene vrstice. Popravki
stopijo v veljavo šele ob naslednjem restartu — ⛔ ownerjeva poteza,
`sudo systemctl restart etlegacy-bot.service` na devu.

**Odprto, izrecno nedokončano:** ena povezava na cikel namesto ena na datoteko
(predelava produkcijske poti, svoja rezina in svoj pogovor).

## Odprte ownerjeve odločitve

- doc 19 (per-user pogled): zajem globalno ali per-server; zgodovina ob
  izklopu (priporočilo: nič retroaktivno); admin UI ali config (config v1);
  anonimni localStorage (odloži).
- doc 20 (match moments): pragi R/T backtest; vir oživljanj (2 tabeli);
  `sub_type` ali nov tip; `proximity_team_cohesion` 1,28 M vrstic brez bralca.
- doc 21 (runtime v2): gostitelj (dev), lastnik deploya (owner) — odprti, a
  nenujni do ultra pregleda.
- puranov cron `0 20 * * * kill etlded` (vrže igralce sredi igre) — pogojni
  kill ali prestavitev.
- `scripts/local_et_setup.sh` P1: produkcijski webhook v lokalnem strežniku.
- hosting ticket, če watcher potrdi populacijo B (host stall).
