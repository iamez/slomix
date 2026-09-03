# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> najprej TUKAJ zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

- (Fable 5.1, 2026-09-03, 12:15) SKOK 3 (ownerjeva ideja, `screenshots/vision.jpg`,
  `vision1.jpg`): **centralni runtime / »event brain«** — en Python proces na
  Linux strežniku spremlja igralni strežnik in iz ENEGA toka dogodkov streže
  website, Discord bot, statistiko in live prikaz (»Slomix runtime v2«; ChatGPT
  dela vzporedni deep research z Redis Streams). Ownerjevo navodilo: ChatGPT-ju
  NE verjeti, vse kot hipoteze, sam raziskati, nato plan mode z vprašanji →
  `docs/design/21` (lokalno). IZVEDBA KASNEJE; Stats 2.0 ostaja prva naloga.
- (Fable 5.1, 2026-09-03, 10:55) SKOK 2 (ownerjeva prošnja): raziskati
  **match moment detektorje** — obstoječih 11 (team wipe, multikill, kill
  streak, carrier chain, focus survival, push success, trade chain, objective
  secured/denied/run, multi-revive; vsak s per-kill razčlenitvijo) razširiti z
  **escorting objective** (soigralec nosi flag/docs/obj; ali si ob trucku/tanku,
  ko se premika A→B) in kar še ET/ETL slog igre ponudi; vir = etlegacy source
  + Lua API dokumentacija → plan mode → zapis v docs; IZVEDBA KASNEJE.
- (Fable 5.1, 2026-09-03, 10:45) SKOK (ownerjeva prošnja): raziskati idejo
  **modularnih statsov s per-user pogledom** — vsak dataset/stat se lahko
  vklopi/izklopi za ZAJEM in za PRIKAZ; prijavljen uporabnik si nastavi
  filtre/privzeti pogled (home: le par stvari, stats 2.0: vse); spletna
  raziskava (kako to delajo drugi, varnost, performance) → plan mode → zapis.
  Ostal sem pri: R2 (#898) dobiva `useful_kills` (UK = useful, ownerjeva
  odločitev); R3 (#899) čaka: stolpec `useless` + `uk`=useful, Codacy/Copilot
  popravki (DataTable aria-label, MapStrip parjenje po imenu mape). Oba PR-ja
  še čakata sestrski signal za merge (#886→#892→#893→#895).
- (Fable 5.1, 2026-09-03) SKOK: owner prosi za nov dizajnerski načrt
  »stats 2.0 aka sessions/stats« → napisan `docs/design/18_STATS_2_0_SESSIONS.md`
  (lokalno), rezine R1–R5. Ostal sem pri: #896 (uploads r. 2) v merge ciklu;
  po mergu: pull main, `git branch -d feat/app-uploads-slice-2`.
- (Fable, 2026-09-02) SKOK: rekonstrukcija izgubljenih planov iz sejnih
  transkriptov — IZVEDENO: 56 skupin / 200 različic / 121 editov v
  `~/claude-plan-recovery/` (lokalno, INDEX.md; 41 skupin je obstajalo samo
  v transkriptih). Skript: scratchpad `recover_plans.py` (samo bere,
  idempotenten). Nič pokvarjeno. Vrnjen na rezino »player dodatki«.
- (Fable, 2026-09-02) #881 v merge ciklu; naslednja rezina: player dodatki
  (4 poti). Ni prekinjenih skokov.

## Tehnični dolg / ideje (nikjer drugje zapisane)

- (3. 9., stats 2.0 R4) **`/detail` brez `response_model`** — Players zavihek bere 8 polj, ki jih TS vmesnik prej ni poznal (`self_kills`, `useful_kills`, `full_selfkills`, `time_dead_minutes`, `denied_playtime`, `alive_pct_drift`, `played_pct`, `played_pct_lua`); drift checker jih ne vidi, dokler handler nima modela (rabi posnetek 154 + 80 v `_RECORDED` in črtanje iz `response_model_gap.txt`).
- (3. 9., R4) **`played_pct_lua` je kopija `played_pct`** (`sessions_router.py:2298`) — legacy »Lua Played%« je bil fikcija; nova stran ga ne riše. Če owner hoče pravi TAB[8], rabi svoj stolpec v `session_player_sql`.
- (3. 9., R4) **`headshot_kills`** ni več v Players tabeli (bil je pod istim `hs` kot head-hit %); če ga kdo pogreša, gre kot svoj stolpec `hs kills`.
- (3. 9., R4) **Teamplay čez polnoč**: `/proximity/trades/player-stats` je keyed po `session_date`; seja z dvema datumoma pokaže le prvega (Meta pove). Rešitev = `gaming_session_id` parameter na endpointu (backend).
- (3. 9., R4) **Sinergija `no_data`/`partial_data` vrne `groups: {}`** (seja 80) — stari Story panel bi na taki noči crashal; zdaj `Absent`. Tip `StorySynergy` je unija z opcijskimi polji.
- (3. 9., R4) `api_storytelling_scopes.json` fixture je osirotel (lupina `/story` je umrla); `useStoryScopes` nima porabnika v app → kandidat za brisanje ob naslednjem čiščenju.
- (3. 9., stats 2.0) **Legacy tooltip »Useful Kills: kills on armed enemies (excludes selfkills and teamkills)« je napačen** — pisec (`c0rnp0rn8.lua:679`, `topshots[15]`) šteje kill, pri katerem ima žrtev pred sabo ≥ polovico limbo časa. Nova stran pove resnico; legacy `website/js/session-detail.js:2484`, `matches.js:986`, `player-profile.js:1186` in bot `community_stats_parser.py:369` (`UK`) še nosijo staro besedilo → popraviti ob naslednjem dotiku legacy strani.
- (3. 9., stats 2.0 — doc 18, lokalno) **FSK prag** (−2 s → /2) čaka ownerjevo
  odločitev; **TAB[8] `time_played_percent` je 0 v ~35 % vrstic vsak mesec**
  (stalna luknja, ne od aprila — vzrok neznan); **medpacki/ammo packi niso
  zajeti** (gibhub »Pillow Fort«); `sessions_router` ACC (lahka orožja) ≠
  `pcs.accuracy` (vsa orožja) — stran imenuje, katero; `endstats_aggregator`
  sešteva tudi K/D in accuracy čez runde (za sejni roll-up rabi `best`).
- (3. 9., R3) `/stats/session/{id}/detail` vrže stran `warnings` iz
  `build_session_scoring` (drugi element terke) → session glava ne more
  pokazati »Lua header winner missing: used time fallback« (doc 12 vrstica 31
  zahteva). `/basics` ali `/detail` naj ju vrne. `MapStrip` pari
  `detail.matches` in `scoring.maps` po indeksu — ko se seznama razlikujeta
  (map ni v scoringu), naj se pari po `match_id`.
- (3. 9., R3) Playwright `SAMPLES_THIN` sessionId 151 → 80; 151 (0 štetih
  rund) ostane pokrit v `SessionDetail.test.tsx` kratkih oblikah (mvp/verdicts/
  good-night fixturi `api_session_151_*`), ne v preletu.
- (3. 9., R2 korpus) **`denied_playtime` iz 2025 supastats backfilla je pokvarjen**:
  jan–maj 2025 ~50 s na uboj (max 18 880 s v rundi 107 s), od dec 2025 ~8 s;
  352/5 538 vrstic 2025 ima denied > 2× igranje, 2026 le 8. Ista doba kot
  pokvarjen `bullets_fired`. `/basics` take vrstice označi (`denied_pct` null,
  `coverage.denied_suspect_players`); podatek ostane, kot je — popravek je
  ownerjeva odločitev (rez po datumu ali ponovni backfill).
- (3. 9., R2 korpus) 14 sej (83, 99–102, 104, 107, 123, 127, 128, 145–147, 151)
  nima nobene štete runde (vse neveljavne/botovske) → `/detail`, `/basics`,
  `/awards` 404; 73 sej (pred junijem 2026) nima `round_awards` → samo trije
  računani; KIS le v 45/139 sejah; 65 vrstic igralcev brez ekipe (subi).
- (3. 9., R2) `/stats/session/{id}/detail` še vedno BREZ `response_model`
  (`response_model_gap.txt` vrstica); `/basics` ga ima — ob R4 /detail
  tipizirati ali upokojiti. `endstats_aggregator._format_value` (bot) izpiše
  `Least time dead`/`Full respawn king` (odstotek) kot m:ss in sešteva K/D —
  bot naj prevzame `session_awards_service.AWARD_RULES`. `endstats_parser`:
  `Quickest multikill` numeric = število ubojev, čas ostane le v tekstu
  (drugi regex je mrtva koda); `Tank/Meatshield` numeric NULL (parsira se
  v servisu). Playwright »thin« vzorec seja 151 je od #855 (vrata) 404 —
  ni več tanka, ampak prazna; e2e SAMPLES_THIN rabi drugo sejo.
- (3. 9., R1) `/api/sessions.maps_played` je abecedno urejen → thumbnail vrstice
  je abecedno prva mapa, ne prva igrana; R2 naj `SessionSummary` doda vrstni
  red igranja (ali `first_map`), response_model.
- (3. 9.) `routes.ts:52` grammar `SESSION_DETAIL_TABS` ima `teamplay/charts`,
  stran pa `summary/players/rounds` — legacy `#/session-detail/154/teamplay`
  pade na summary; R4 ga uskladi.
- (3. 9., uploads r. 2) **poster capture** (.mp4 → JPEG prek canvasa,
  `uploads.js:300-336`) za single-shot pot; **resume čez reload** (HEAD +
  localStorage identiteta datoteke — legacy nima); filtriranje po
  kategoriji/oznakah na seznamu (rezina 1 ga je izpustila, PR #888).
- (3. 9.) **resumable router handlerji nimajo testov**: 0 testov v `tests/`
  kliče `init_resumable_upload`/`resumable_patch`/`finalize_resumable_upload`/
  `abort_resumable_upload`; le store (`test_upload_store_resumable.py`).
  `test_uploads_slice2_fixtures.py` pokrije init/finalize/delete oblike,
  ne PATCH/HEAD.
- (3. 9.) `docs/UPLOAD_SECURITY.md` §3.6 zastarel (trdi, da admin ne more
  brisati; `delete_upload` admin gate obstaja); `delete_upload` brez
  `_require_valid_upload_id` → napačen id vrne 404, ne 400.
- (2. 9., availability r. 2) **response-model round: availability + bets** —
  24 handlerjev brez `response_model`, openapi brez shem → ročni tipi v
  `types.ts` so pripeti le s harness posnetki
  (`tests/unit/test_availability_slice2_fixtures.py`). Isti vzorec kot
  #812/#820/#830; ownerjeva odločitev 2. 9.: ločen PR.
- (2. 9.) **admin market kontrole** (`POST /api/bets/market`, `…/settle`) —
  izpuščene iz rezine 2 po ownerjevi odločitvi; gap vrstici `/api/bets` in
  `/api/bets/market` ostaneta (komentar v `endpoint_gap.txt`).
- (2. 9.) `scripts/record_api_corpus.py:mint_owner_cookie` kuje cookie s
  TRDO KODIRANIM realnim Discord id-jem (»corpus-recorder«); `--sentinel`
  (rezina 2) je pot brez identitete — ownerjeva pot bi šla prek E2E_OWNER_*.
- (2. 9., živ Playwright na :8056 med rezino 2) `app-routes` anon: greatshot
  demo/clips stran kliče zaščiteno pot anonimno → 401 v konzoli (stran iz
  #890); proximity/proximity-player `page.goto` presežeta 30 s `networkidle`
  (hladna hrbtenica, memory `second_call_is_not_a_measurement`); spider-web
  thin-data. Nič od tega ni v rezini 2 (diff se teh strani ne dotakne) —
  vsak zasluži svojo vrstico, ne tišine.
- (2. 9.) `bets_router.get_current_market`: `my_bet.payout` gre skozi `int()`
  in ob `None` TIHO vrže `my_bet` na `null` (except TypeError). Stolpec je
  NOT NULL DEFAULT 0, zato danes ne sproži — a tip laže, če se shema kdaj
  sprosti.
- `bets/wallet` 500 za avtenticirano sejo BREZ users vrstice (2. 9.: sentinel
  ima zdaj vrstico prek `scripts/e2e_sentinel_rows.py`, hrošč za izbrisane
  uporabnike ostaja) (FK na
  user_points ob auto-create; izmerjeno s sentinelom −1). Pravi uporabniki
  ob OAuth vrstico dobijo; krhkost velja za izbrisane/sentinel uporabnike —
  handler naj FK ujame in vrne prazen wallet ali 403.

- round-end burst: batch write (table.concat → ~64 KB kosi) namesto 8400
  posamičnih trap_FS_Write; PREJ en večer self meritev z v6.12.
- tracker mikro: cache `sv_maxclients` (isValidClient ga bere ob vsakem
  klicu); združi dve cohesion zanki (isti pari, ista razdalja dvakrat).
- webhook pending_retry_sweep: io.popen find vsakih 60 s tudi ob praznem
  bufferju — gate za fork.
- replay stran: playback canvas je imenovan follow-up (paritetna tarča ga
  ni imela); kill-outcomes `events` seznam (80 KB) se ne izrisuje.
- spider-web: information_state/beliefs se še ne izrisujejo; mesh za
  etl_supply ne obstaja (BSP ni izvožen).
- weapon-accuracy `weapon_breakdown` se napolni le pod player_guid filtrom
  — player rezina naj ga pokaže.
- lokalna past: generirani `src/api/generated/openapi.d.ts` je bil 2×
  zastarel ob typechecku → pred meritvijo `rm` (ali dodaj v pretypecheck).
- `.claude_session` (SessionEnd hook) je v gitignore; po izpadu `--resume`.

## Prenosljive najdbe (sestrska seja, 2. 9. — ownerjeva prošnja za zapis)

- ⭐⭐ **Vzorec »eno ime, dve meritvi«** — 7× v enem dnevu (hitch A/B, dve
  uri z odmikom 2553 ms, TRIJE števci assistov, PLAYED%=LUA PLAYED%,
  DENIED je čas odvzet nasprotnikom, time_played_seconds ob reconnectu,
  kill_assists kumulativa/per-round). Recept: diskriminator, ki ga izpolni
  samo ena razlaga, pognan čez KORPUS (npr. monotonost: R2<R1 v 59 % parov
  dokaže per-round).
- ⛔ Assistov NE podeljuje motor: `TAB[12]` = `topshots[3]` iz NAŠE
  `vps_scripts/c0rnp0rn8.lua:701-741` (MOD filter, okno 1500 ms). Naša
  lastna števca se ne strinjata: endstats `topshots[29]` proti TAB[12]
  na 1005 rundah 40 razlik (±1).
- ⛔ Merilni pasti etconsole: časovne oznake so DESNO poravnane
  (`grep '^[0-9]+ Hitch'` vrne 1/18); motor javi hitch šele pri >500 ms
  (65/71 round-end burstov je NEVIDNIH, ne odsotnih).
- 🔎 **TAB[8] `time_played_percent` = 0 pri 37,9 % vrstic** (5.363/14.163,
  nobena NULL) kljub pravilnemu parsanju → neposreden vhod v ALIVE% na
  strani (`sessions_router.py:2115-2131`). Vzrok neznan — kdor se dotika
  ALIVE%, mora to vedeti.
- ⛔ `docs/GAMESERVER_LIVE_LUA_MAP.md:74` in `deployed_lua/README.md`
  navajata 4 module; živih je 6.
