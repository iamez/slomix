# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> najprej TUKAJ zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

- (Fable 5.1, 2026-09-09, zvečer) **PREDAJA PRED DOPUSTOM**: `docs/HANDOFF-fable-2026-09-09.md`
  (owner odsoten ~3 mesece; vnaprejšnji DA je veljal le za to sejo). Mergano danes:
  #1001–#1011, #1013 (ledger + spider web + bot brez reakcij); dev deployan po
  vsakem vlaku. Odprto brez ownerja: #956 (1.46.0), Astrini #1012/#979/#969/
  #966/#965/#964/#962, review #924–#943/#967 (NEVER MERGE).
- (Fable 5.1, 2026-09-09, 10:30) Owner: »ko vse končaš … celoten spiderweb
  do konca avtonomno«. MERGANO: #1001 (kartica + stenska ura), #1002 (story;
  13 Codex niti). V VLAKU: #1003 → #1004 (12 Codex niti popravljenih), nato
  build + dev deploy. SPIDER WEB (proga v `docs/PLAN.md`): #1005 SW-2 scena
  (SVG, kamera, regije prepričanj, `?t=&pov=`; 9 Codex niti), #1006 SW-3
  vidna linija kot oracle diagnostika (stacked; 10 niti; ledger `/web` 0),
  SW-4 sloj 4 = §8 harness na veji `feat/spider-web-layer4-harness`
  (`services/layer4_family.py`, `scripts/spiderweb_layer4_family.py`);
  zbiralnik teče čez 901 rund. ⛔ Vsi trije čakajo DA za merge. Naslednje:
  tabela §8.5 + manifest → STATUS/PLAN → PR; ena AskUserQuestion za DA; dev
  deploy + živ dokaz spider weba (`/app/spider-web/round/11344?t=120000`).
- (Fable 5.1, 2026-09-08, 22:00) Avtonomni popoldan (owner: »kar nadaljuj, čim
  več«). MERGANO: #992 (merilnik meri po endpointu; unread 517 → 789 je
  popravek instrumenta, ne strani), #987 R3a, #993 R4b. V VLAKU (DA dan):
  #988 R3b → #989 R3c → #990 R3d → #991 R4a → #994 R5 → #995 R4c, nato build +
  dev deploy. ODPRTO BREZ DA: #996 R6 (živi reducer obdrži pozicije in zadnje
  uboje), #997 R6b (mini zemljevid na živi strani, naložen na #996).
  ⛔ Skok (pravilo): owner je vprašal za ENG% z gibhub.gg → raziskano, ne
  zgrajeno: bojni ENG% je DPM v drugi enoti (r 0,74–0,96), s štirimi kanali
  (revivi, objektivi, streli) pa se odklopi (r −0,75 / 0,62 / −0,47) in
  postane metrika AKTIVNOSTI; doc lokalno
  `docs/research/ENG_PCT_RESEARCH_2026-09-08.md` §6, odločitev ownerja.
  Naslednje: R7 higiena (community.js, keymap »Charts« → session.graphs,
  »Map Distribution« odločitev), ENG% kanali le z DA, kill-impact/greatshot/
  proximity/event ostanki merilnika.
- (Fable 5.1, 2026-09-08, 12:05) Vlak zaključen: #980 (live glava; 11 Codex
  niti + drift tipov popravljeni), #981 (profil: name history, gathers,
  combat timing), #982 (story role boards s številkami), #983 (skill
  formula uteži) MERGANI; merilnik podatkovnih točk `unread` 563 → 543;
  rezine pregleda ponovno izrezane; SPA zgrajena in DEPLOYANA na dev
  (`/api/build` `5b7cfbcf`, servirani bundle nosi »last imported«,
  »players on for«, »database says«). Odprti PR-ji: #985 ticker (stavki
  dogodkov, zloženi dvojčki; cherry-pick na main), #986 profil long tail
  (unread 556 → 532), #984 ta docs PR. Vsi trije čakajo ownerjev DA.
- (Fable 5.1, 2026-09-08, 10:20) Owner: »aim/advanced razišči z Mandelbrot +
  RCA, shrani v docs, odloži, gremo naprej« — NAREJENO, nič implementirano.
  Vzrok je I/O, ne CPU: EXPLAIN ANALYZE flick/spread poizvedbe (9,6 s) bere
  17 212 razpršenih heap strani `proximity_shot_fired` za enega igralca ob
  `shared_buffers` 128 MB; `advanced` teče čez celo `combat_engagement` zaradi
  `LEFT(target_guid, 8)`; cache 077 `player_aim_summary` nima proizvajalca
  (5 vrstic, zadnje so moji probi). Poti A–F + priporočilo v `KNOWN_ISSUES`
  in HANDOFF-astra §C 14; polna sled lokalno
  `docs/research/PROFILE_AIM_ADVANCED_RCA_2026-09-08.md`. Ob istem koraku so
  štiri agentska poročila popisa podatkovnih točk (stari React / legacy /
  zaledje / UX kot obiskovalec: 166 izgubljenih točk po nivojih, DPM 20,9 %
  razhajanje ponderirano proti neponderiranemu, `.js.map` javno) shranjena v
  lokalni `docs/research/DATAPOINT_AUDIT_2026-09-07.md`; agenti zaprti.
  Odprto po vrsti: #980 (drift tipov + 11 niti), #981 vrata, veji
  `feat/live-ticker-reads-its-events` in `feat/profile-long-tail` za PR.
- (Fable 5.1, 2026-09-07, 22:05) Owner: »poglej live mode kot obiskovalec«
  — pregledano med živo igro na produkciji (legacy `#/live`, v1.39.0):
  deset vrzeli (L1–L10) in osem rezin v LOKALNEM
  `docs/research/LIVE_VIEW_VISITOR_REVIEW_2026-09-07.md`. Bistvo: ni vrstice
  »kaj se je pravkar zgodilo« (zadnja runda, zmagovalec, čas); ni stopwatch
  konteksta (limit, čas za premagati, kdo napada); »session 4m« je ura
  strežnika, ne večera; `prev gammajump` je jump mapa; K/D v rosterju je
  kumulativa od povezave brez oznake; momentum/hold krivulji brez osi;
  feed podvaja POPUP+DYNAMITE in MAP+LIVE_MAP; mrtve stave sredi strani.
  Ni narobe: časi rund so IZMERJENI (210 s = 3:30, dva polna holda).
  Popravki gredo na SPA `LivePage.tsx` (prod zamrznjen); predpogoj je
  replay živega toka na devu (tailer cilja prod). Posnetek toka in stanja z
  nocojšnje igre: `scratchpad/live-feed-2026-09-07.json` (lokalno).
- (Fable 5.1, 2026-09-07, 21:45) Owner: »je vse pripravljeno na tekme, Lua
  na puranu?« — izmerjeno med živo igro (6 ljudi na etl_adlernest): Lua na
  puranu = repo za vse žive module (le arena modul brez #912; oboroži se
  samo na areni); runda 213018 uvožena 7 s po nastanku datoteke; tailer za
  živi pogled teče in pošilja na www.slomix.fyi (prod). ⚠️ Watchdog `live:
  warn` je na devu LAŽEN: dev nima vira živega toka (tailer cilja prod) →
  watchdog r. 2: preverba mora vedeti, kdo je cilj tailerja, ali biti na
  devu izklopljena. `KNOWN_ISSUES` »Lua drift High« označen kot rešen.
  Vlak: #971, #973 mergana; #974, #972 v vratih; lokalno pripravljena veja
  `feat/profile-rounds-series` (gap 10 → 9 po #974).
- (Fable 5.1, 2026-09-07, 19:30) Owner: »dokončaj novo stran« + DA za gradnjo,
  dev deploy, Chromium prelet in kodo. NAREJENO: `npm run build:app` v
  worktreeju `slomix-fable` (main `e91875cf`), `DEV_SRC_DIR=…/slomix-fable
  scripts/dev_deploy.sh` → run dir `e91875cf`, servirani bundle
  `app-Bv4wOtcy.js` = zgrajeni (prvič od 6. 9. 11:03 je SPA na `:8000` enak
  mainu), bot prijavljen 19:24. `static/modern` guard je pravilno preskočil
  (worktree brez legacy bundla). V TEKU: anonimni prelet 32 rut (`--app
  --anon-only`); owner prelet rabi `website/.env` → iz primarnega drevesa.
  PRELET (anon, 32 rut × 4 pogledi = 128, `:8000`, bundle `e91875cf`, hladen
  strežnik 5 min po restartu): **0 padlih**, 16 opomb: greatshot ×8 = 401 za
  anonimnega (načrtovano stanje); admin/compare/proximity-player na 1920 =
  `page.goto` 30 s timeout na HLADNEM backbonu (prvi obisk po restartu;
  1440/768/390 iste rute čiste); dvojni klici `/api/stats/overview` ×2–3 na
  admin in profil ×2 na compare (dedup kandidat); prelivanje 20–32 px na
  telefonu 390 za `retro-viz` (sidra) in `proximity` (svg). Mediana
  nalaganja 2,5 s; owner prelet NI tekel (`website/.env` je le v primarnem
  drevesu). Izid: `scratchpad/audit-anon/results.json` (lokalno).
  PR #970: `components/Panel.tsx` (modularnost rezina 1) + ratchet
  `panels.test.ts` (61) + profil »form by session« → endpoint gap **11**.
  OWNER PRELET (prijavljen sentinel, isti bundle, 128 preverb, 21:20): **0
  padlih**, 7 opomb — greatshot 401 izginejo; `admin` ruta na VSEH štirih
  pogledih `page.goto` 30 s timeout z dvojnima klicema `/api/stats/overview`
  in `/api/system/overview` (kandidat: polling brez `networkidle` ali počasen
  endpoint za neadminskega prijavljenega uporabnika — preveri `refetchInterval`
  in odziv obeh endpointov za `website_user_id = -1`); `proximity` 1920 hladen
  timeout (40 s), prelivanje 20–32 px na 390 (retro-viz sidra, proximity svg)
  kot pri anonimnem. Mediana nalaganja 2,65 s. Izid `scratchpad/audit-owner/`.
  R0 NAJDBA (glej `docs/KNOWN_ISSUES.md` »R0 summary rows counted again«):
  `stats/player/{}/form|rounds` in `skill_router._form_rows` so sešteli R0
  vrstice → DPM serija ~30 % previsoka; popravki v #970 + veja
  `fix/skill-form-skips-r0`; razred (api_helpers, season_awards, auth,
  session_matrix, greatshot_crossref brez filtra) čaka per-query audit.
  NASLEDNJE: PR-ji po mergu #970: `feat/panel-slice-2` (ratchet 61 → 49),
  `fix/skill-form-skips-r0`, `feat/greatshot-crossref-panel` (gap 11 → 10);
  potem `stats/player/{}/rounds` (S), dedup dvojnih klicev, admin timeout.
  ⚠️ Ultra na #924 do 19:20 ni oddal ničesar (0 pregledov); rezin ne sekam,
  dokler owner ne potrdi, da pregled ni v teku.
- (Fable 5.1, 2026-09-07, 13:10) SEJA ZAKLJUČENA na ownerjevo zahtevo. Stanje: #960,
  #958, #955 mergani; #912 mergan 12:30 pod ownerjevim DA za nabor (»zapri odprte PR-je
  razen Don't merge«, 03:40) — ⚠️ pogodba hoče DA na številko PR-ja; ownerju
  poročano posebej s sestrinim pridržkom (`arena_acc_log` neizmerjen v živo); #961 (predaja Astri + modularnost SPA) čaka
  ownerjev DA. Po mergu #912: `scripts/review_slices.sh cut --push` (rezine
  #924–#943 na novi main) — če seja ugasne prej, to naredi Astra ali owner.
  Astra vstopi prek `AGENTS.md` §4 → `docs/HANDOFF-astra.md` §E (prva ura) → §C.
  Bundle NI zgrajen (owner: pozneje); sudo/DB geslo rotacija = owner.
- (Fable 5.1, 2026-09-07, 04:30) Predaja projekta Astri: `docs/HANDOFF-astra.md`
  (§A Fable, §B sestra dobesedno, §C delovni paket 1–20, §D ne delaj, §E prva
  ura) + `docs/HANDOFF-astra-inventory.md` (inventar po območjih, §11 ownerjeve
  odločitve); kopija v `/tmp/slomix-claude-handoff-to-astra-20260907.md`. Owner
  DA: zapri odprte PR-je razen `review:` → #960 mergan, #958 v vratih, nato
  #955, #912 (sestrin pridržek: `arena_acc_log` neizmerjen v živo). Odprto za
  ownerja: rotacija sudo + DB gesla; `build:app` + `dev_deploy.sh` restart;
  ultra #924/#925/#926 opoldne.
- (Fable 5.1, 2026-09-06, 19:50) Proga (1) watchdog r. 1 narejena (veja
  `feat/watchdog-r1`, PR). Vse štiri proge dneva imajo PR: #945 (guid, v
  vratih), #946 (diagnostics, čaka rebase po #945), #947 (datasets), watchdog.
  Owner: webhook URL + namestitev timerja. Zvečer #882 → `review_slices.sh cut
  --push`. Astra jutri: triaža ultra najdb (#924–#926) po `astra_kickoff.md`.
- (Fable 5.1, 2026-09-06, 19:10) Proga (4) doc 19 r. 1 narejena (veja
  `feat/dataset-registry-r1`, PR). Odprto iz nje: vrstica »N datasets« na About
  panelu po mergu #946; `docs/design/19` status vrstica (lokalno). Naslednje:
  (1) watchdog r. 1 (`scripts/slomix_watchdog.py`, obseg doc 24). PR-ji #945,
  #946 v vratih (ownerjev DA za oba). Zvečer #882 → `review_slices.sh cut --push`.
- (Fable 5.1, 2026-09-06, 18:20) Proga (3) diagnostics narejena (veja
  `feat/about-diagnostics-degraded`, PR); dolg za #911 zaprt. Proga (2) guid
  prefiks = PR #945. Naslednje: (4) doc 19 r. 1 register datasetov, potem (1)
  watchdog r. 1. Zvečer #882 → `review_slices.sh cut --push`.
- (Fable 5.1, 2026-09-06, 17:30) Proga (2) guid prefiks narejena (veja
  `feat/proximity-guid-prefix`, PR). Naslednje po planu: (3) About diagnostics
  stanja degradacije (#911 prenos), (4) doc 19 r. 1, (1) watchdog r. 1. Zvečer:
  #882 → `review_slices.sh cut --push`. ⚠️ Sestra dela #923 (SSH monitor nizi):
  svetoval datoteko `logs/bot_error_streaks.json`, ne migracijo; watchdog jo bo bral.
- (Fable 5.1, 2026-09-06, 14:45) Ultra + Astra pripravljena (veja
  `docs/ultra-ready`): ultra meja 8 000 vrstic → 20 rezin
  (`scripts/review_slices.sh`, rez = meritev 20/20); `19c61847` NI prednik
  maina (stara zgodovina) → veja izbrisana; #915 mergan (dve podpičji: CodeQL
  nit + osirotela vrstica 532, sestrin `index(token)+4`), #911 zaprt kot
  dvojnik #919 — **prenos v About panel še odprt**: stanja degradacije
  (tabela brez štetja = razlog, prazen časovni blok = poizvedba ni tekla,
  padla monitoring tabela = unavailable, 401 proti 403) + fixture
  `api_diagnostics_degraded.json` na veji `feat/diagnostics-on-the-new-surface`.
  ComparePage `played` = več igranja zmaga (owner). Prelet SPA po #921 NI
  ponovljen (RAM 329 MB). Naslednje: PR → ownerjev merge → `cut --push` +
  `prs` (20 draft PR-jev) → zvečer #882 → `cut --push` znova. Opomba:
  `scripts/codex_audit_prompt.md` je untracked dvojnik
  `docs/prompts/codex_audit_prompt.md` (run_codex_audit.sh bere prvega).
- (Fable 5.1, 2026-09-06, 11:30) Prelet: 1. tek 256 preverb (najdbe v PR #921),
  2. tek 108 čistih in merilnik padel ob timeoutu `admin` (popravljeno), 3. tek
  PREKINJEN — RAM 1,8 GB, na voljo 196 MB; owner: razen `:8000` nič ne streže.
  Ponovi prelet, ko je RAM prost: `HANDOFF-next.md` §3 (moj uvicorn :8056 +
  `audit_website_browser.mjs --app`). ⛔ prelet požene chromium (240 MB
  ostankov) — po njem preveri `ps` in pobij po PID (ne `pkill -f`).
- (Fable 5.1, 2026-09-06, prelet) Najdbe končnega paritetnega preleta SPA
  (manifest 32 rut): (1) ⛔ **»proximity →« s seje je vodil v »ni zajema« za
  VSAKEGA igralca** — povezava je nosila 8-znakovni guid, proximity endpointi
  primerjajo polni 32-znakovni (`combat_engagement.target_guid = $1`); Absent
  je veljaven render, zato ga prelet »renders without errors« ni ujel →
  popravek: drilldown vzame polni guid iz KIS seznama; vzorci preleta/e2e na
  polni guid. (2) audit/e2e vzorci niso zapolnili `:id`/`:a?`/`:b?` (strani
  za igralce »id«/»a«/»b«; e2e vzorci so se izgubili pri rebase #920) →
  popravljeno. (3) `session.teams`, `record-book.hof`, `session.players`
  niso na privzetem zavihku/podatkih 154 — zavihki, ne napake. Odprto:
  proximity endpointi bi lahko sprejeli 8-znakovni prefiks (10 endpointov,
  ločen PR, če owner hoče).
- (Fable 5.1, 2026-09-06, jutro) #919 in #920 MERGANA; O1 = (c) Clips strani ni.
  Teče končni paritetni prelet SPA na :8056 (izid v PLAN, ko se konča).
  Naslednje: pregledni PR #802→main za ultra (ownerjeva odločitev: commit
  podmnožice docs/design ali lokalni pregled) → soak → produkcija (preklop =
  `build:app` v `deploy_release.sh`).
- (Fable 5.1, 2026-09-06, noč) Faza 7 r. 1 (compare + wrapped) zgrajena na
  veji `feat/site-phase7-compare-wrapped` (od dolga r. 1, #919 — ta je v CI
  padel na Python job: preveri). Odprto v fazi 7: clips (O1), končni prelet.
- (Fable 5.1, 2026-09-06) SKOK: owner → »dokončajva novo stran« (dolg → faza
  7 → pregledni PR). Doc 19 (per-user pogled) pavziran v plan modu, ničesar
  napisanega. Dolg r. 1 (veja `feat/site-debt-keymap-replay-diagnostics`):
  keymap, `/replay`, `/api/diagnostics` panel. ⚠️ E2E rig NIMA adminskega
  nivoja: admin = env allowlist Discord id-jev (`_configured_admin_ids`),
  sentinel id −1 ga ne prestane → adminski prikaz je dokazan v vitestu s
  posnetkom, narejenim kot pravi admin; Playwright dokaže le vrata (prijavljen
  ne-admin brez panela in brez zahteve). Naslednje: faza 7 (compare, wrapped;
  clips čaka O1), pregledni PR #802→main za ultra.
- (Fable 5.1, 2026-09-06) Dvojčki r. 3 zgrajena (generator + 11 testov, 7
  mutacij padlo, tek čez 6 map). ⚠️ Kontrola NE pade na nič: premešane seje
  preživijo ≈ 21 % (14/67) razločevalnih ciljev — s 7 regularji je skupinsko
  povprečje šumna osnovnica. Možni naslednji koraki: z-score proti razpršenosti
  drugih igralcev, ali več sej; do takrat poročilo tiska kontrolo ob vsakem
  teku. Odprto: `botnames` je bral `DB_*` env (ni v `.env`) → vedno fallback
  imena (popravljeno s `POSTGRES_*` rezervo, a živa tabela na puranu je še
  fallback); `carniee` ima 2 guida; Olympus = olz (isti igralec, dva bota).
- (Fable 5.1, 2026-09-05, 23:20) #916 MERGAN in v6.14 DEPLOYAN na puran
  (dokazano). Odprto: (1) en večer `frame_health.log` na puranu brez novega
  `self` stroška; (2) migracija 082 na prod ob release deployu; (3) popravek
  korpusa `destroyed_count` (fantomska +1 na goldrush rundah pred v6.14) —
  ownerjeva odločitev; (4) naslednja proga: dvojčki r. 3 ali doc 19.
- (Fable 5.1, 2026-09-05, pozno) Moments r. 2 — dve živi pasti iz lokalnega ET:
  (a) supply truck se sam odpelje pri 0,6 s → `first_move_time` ni čas escorta
  → dodana `first/last_escort_time` (premik z igralcem na/ob vozilu), detektor
  bere te; (b) goldrush tank začne POKVARJEN → poll je vsako rundo štel
  »uničenje« ob 1,2 s brez napadalca → smrt iz polla šteje šele, ko je vozilo kdo ESCORTIRAL (`first_escort_time > 0`); dve prejšnji vrati sta v živo padli (»po prvem premiku«: tank se skriptno premakne ob 0,6 s; »ne zaupaj init scanu«: poll ga JE prebral živega ob 0,7 s, skript ga pokvari ob 1,2 s);
  ⚠️ **kontrakt `destroyed_count` se spremeni** (korpus pred v6.14 nosi
  fantomsko 1 na vsaki goldrush rundi — detektorjev »destroyed 1×« je bil
  lažen; popravek korpusa = ločena naloga, če owner hoče).
- (Fable 5.1, 2026-09-05, večer) SKOK na moments r. 2 (ownerjeva izbira po
  #914, ki je mergan): veja `feat/moments-mover-times`; Lua v6.14 + parser +
  migracija 082 (na devu aplicirana kot `etlegacy_user` — ⚠️ `apply_migrations.py`
  iz `website/.env` pobere `website_app` in pade z »must be owner«; obvod
  `POSTGRES_USER=… POSTGRES_PASSWORD=…`) + detektor. Lokalni ET: `local_et.sh
  deploy` pade na scp (ključ ni v et-jevem authorized_keys) → kopija prek
  `sudo -n -u et tmux -S …-285.sock run-shell "cp /tmp/x.lua …"` (sestra),
  nato `map` load in `lua_status` SHA1 = `sha1sum` datoteke. Pred-obstoječi
  ruff DTZ001/DTZ007 v `parser.py:713/1579` nista moja (enako na mainu).
- (Fable 5.1, 2026-09-05, popoldne) Doc 22 rezina 2 zgrajena (camp-profile +
  peta plošča vlog), PR odprt z veje `feat/bot-twins-camp-profile`; #913 mergan.
  Odprto: e2e `session 154 · players tab renders` je enkrat padel v vzporednem
  teku (locator ni bil viden v 10 s) in prešel sam ter v ponovitvi — flaky pod
  obremenitvijo, ni vezan na to spremembo; `RoleBoard` kaže top 5 → igralci s
  `hold_pct: null` se filtrirajo, a plošča ne pove, koliko jih je izpustila
  (majhna vrzel besednjaka; ob r. 3). Rate limit 5/min na camp-profile enak
  lurkerju — šest zaporednih poizvedb iz enega IP-ja da 429 (izmerjeno).
- (Fable 5.1, 2026-09-05) Doc 22 rezina 1 IZMERJENA (7 map × mreži 512/256 +
  identifikacija; 13 min + 5 min + 1 min tekov): osebnost poti obstaja
  (identifikacija 81–91 % proti 10 %), je časovna utež in ne kraj, prag 25
  sej; PR odprt na veji `feat/bot-twins-route-distinctiveness`. Odprto za
  rezino 2: dwell mora izločiti spawn čakanje (top celica je pri vseh ista);
  NP pot je krajevno utežena (unikatne 32 u točke) — v poročilu imenovano.
- (Fable 5.1, 2026-09-04, PAVZA zaradi limitov) Ostal sem pri doc 22 rezini 1:
  skripta + testi na veji `feat/bot-twins-route-distinctiveness` (commitano,
  potisnjeno, BREZ PR-ja), korpusni tek še brez številk → glej
  `docs/HANDOFF-next.md`.
- (Opus 5, 2026-09-05, 11:30) **SKOK: ownerjeva nova prošnja** — boti na
  dots_arena naj bodo samo medic/fieldops (drugi razredi se ne premikajo), naj
  strejfajo levo-desno in dodgajo; + raziskava izvorne kode ET:Legacy: **zakaj
  ni hitsounda**, čeprav je crosshair na tarči (prvih nekaj headshotov da zvok,
  potem tišina), ali gre za neregistrirane strele (owner ocenjuje 30–60 %) in
  ali te ob zadetku »vrže« strele vstran; + ločeni research docsi »kako postati
  unkillable v ET/Legacy«.
  **KJE SEM OSTAL:** PR #912 (`feat/lua-dots-arena`, 15 commitov, CI zelen,
  `OPEN CLEAN`). P0/P1/P2 zaprti, zadnji commit `67785c84` je bratova najdba
  (self-frag mora šteti — `mod`, ne identiteta). 39 primerov harnessa, 17
  mutacij v `scripts/mutate_dots_arena.sh`, 6.227 testov.
  ⏳ **TEČEJO TRIJE MOJI AGENTI** (napadalni pregled, pregled današnjega diffa,
  pregled testov samih) — izsledke je treba pobrati in obdelati, preden se PR
  šteje za pregledan.
  ⛔ **Kode ni pregledal nihče** (Copilot in Codex sta zadela kvoto) → owner naj
  požene `/code-review ultra`, preden gre paket neznancem.
  ⛔ Odprto brez meritve: `/team s` ko si ŽIV, `sv_maxclients` v živo, rotacija
  loga v živo, gledalčev gate in cooldown v živo, `arena_symmetric` proti
  človeku, paket v pk3, dva človeka hkrati.

- (Opus 5, 2026-09-05, 01:15) **Arena: trioosni pregled + popravki P0/P1** —
  `2b21828a` na `feat/lua-dots-arena` (PR #912). Tri visoke, vse dosegljive z
  navadno igro:
  ⛔⛔ **`/team s` sredi dvoboja je prinesel točko IN usmrtil nasprotnika** —
  motor ubije 55 vrstic pred prepisom moštva (`g_cmds.c:1589` proti `:1644`),
  zato je roster ob obituaryju še vedno 2. Dokazano v živo.
  ⛔⛔ **Ni bilo `et_ClientDisconnect`** — `ClientDisconnect` nikoli ne kliče
  `player_die`; preživeli je ostal ranjen, naslednji je dobil poln bazen.
  ⭐ Odhajajoči ob hooku ŠE ŠTEJE (hook `:3585`, `CON_DISCONNECTED` `:3723`).
  ⛔⛔ **`forced[cn]` je bil zapah brez izteka** — `G_Damage` sme ne narediti
  nič (warmup, intermission, godmode, noclip) in tega ne pove; naslednja prava
  smrt je bila požrta, ščit pa že odvzet.
  ⛔⛔ **Paket, ki smo ga poslali, je bil hujši:** 11 od 12 cvarov, ki jih naš
  README imenuje gumbe, je bilo `setl` → `arena_1v1 0` po naših navodilih
  odklopi cel config. In `g_customConfig` je `CVAR_ARCHIVE`: en glas naredi
  arena ruleset TRAJEN (vse mape, čez restart procesa), s samo Field Ops
  razredom in ustavljeno rotacijo. Zdaj dokumentirano v vseh treh jezikih.
  ⭐ **Dve moji lastni regresiji, ki ju je ujel šele živi tek:** prvi popravek
  `/team s` je pokvaril `/kill` (točka in reset sta dve odločitvi), povrnitev
  `arena_hp` pa je brisala vrednost, ki jo je admin nastavil med mapama.
  ⭐ Harness stub je bil **brezpogojno smrtonosen** — zato so bile vse poti
  brez obituaryja nevidne po zasnovi. Zdaj zna zavrniti.
  30 primerov, 31 mutacij, 6.225 testov. Puran ima popravljeno različico,
  config ostaja `.off`. **P2 (dovoljenja za ukaze, meje `arena_kill`, ime v
  ukaznem nizu, rotacija loga, verzija paketa, oblika configa, mutacije v
  repo) ni narejen** — glej `~/.claude/plans/distributed-inventing-fox.md`.

- (Opus 5, 2026-09-04, 14:35) **Arena kot deljiv paket** — `7efaa491` na
  `feat/lua-dots-arena` (PR #912). `vps_scripts/dots_arena/` = config
  (izpeljanka `legacy1.config` brez `sv_cvar` omejitev) + trijezični README
  (EN/FR/SL). Preverjeno v živo: config se naloži, modul se oboroži, na tuji
  mapi miruje in `g_forcerespawn` se povrne.
  ⛔⛔ **Ob tem najden pravi hrošč: `CS_SERVERINFO` je ob PRVEM `map` PRAZEN**
  (dolžina 0), zato gate na imenu mape ni nikoli deloval ob svežem nalaganju.
  Modul se je oboroževal LE zato, ker `G_configSet` ob vsakem configu pošlje
  `map_restart` in je dev strežnik vedno imel `g_customConfig`. Popravljeno:
  bere se cvar `mapname`, configstring ostane rezerva. Primer 22 + 2 mutaciji.
  ⛔⛔ Za vsak prihodnji config: `G_ConfigCheckLocked` teče **vsak frame** in
  odklopi config, brž ko se kak `setl` cvar spremeni → `arena_hp` mora biti
  `set`. Pinnano z `tests/unit/test_dots_arena_config_contract.py`.
  ⛔ `lua_modules` v configu **prepiše** ves seznam modulov (6 → 1, izmerjeno).
  Odprto: ključ za `et` še vedno ni nameščen (obvod `tmux run-shell`).

- (Opus 5, 2026-09-04, 13:40) **Arena 1v1 IZMERJENA na 2.84** — `871e92c5` na
  `feat/lua-dots-arena` (PR #912, čaka ownerjev merge, NIČ deployanega).
  45 min dvobojev z dvema botoma po raziskavi izvorne kode.
  ✅ strelivo **9999/9999 pri ~100 spawnih**, ob koncu dvoboja pade le za
  izstreljene naboje (najslabše `9999/9949`); ✅ sprint **20000** = natanko
  `SPRINTTIME`; ✅ preset **250 HP = mediana 6 s** (n=13); ✅ `STAT_MAX_HEALTH`
  ostane 100; ✅ veriga modulov nedotaknjena, 0 Lua napak.
  ⛔ **Simetrija orožij**: zapis prime (50/50 potrjenih takoj po zapisu),
  orožje pa obstane le **2 od 25** — Omnibot si svoje vzame nazaj. Ni vihar
  (1,53/s vklopljeno proti 1,03/s kontrola = ~1,5× osnovnice, ker odgovarja
  bot prek `Cmd_Team_f`/`G_SetClientWeapons`), dvoboji tečejo normalno →
  privzeto izklopljeno, ne umaknjeno.
  ⛔⛔ **Za naslednjič:** `G_Damage` je med warmupom TIHI NIČ
  (`g_combat.c:1445`) — reset se ne zgodi in ne javi ničesar; zadetek >190
  postavi zdravje na −176 **ne glede na bazen** (`g_combat.c:1931`).
  ⛔⛔ **Rata iz nezaključenega okna ni rata**: objavil sem 1,52/s iz odčitka
  50 s v 95-sekundno okno, končni izid 1,03/s → commit amendan.
  ⛔ **Deploy na testni strežnik ne dela**: `scp` do `et@127.0.0.1` javi
  `Permission denied (publickey)`; obvod je NOPASSWD `tmux ... run-shell`
  (owner odobril 4. 9.) prek staging datoteke v `/tmp` (et ne more brati
  `/home/samba`). Trajni popravek: dodati javni ključ v `et`-jev
  `authorized_keys`.
  ⛔ `local_et.sh start` zažene strežnik tudi, če je deploy odpovedal → **pred
  vsako meritvijo `cmp` med repo datoteko in nameščeno**.
  Odprto: klientska polovica 16-bitnega polja streliva in vezavi
  `/vampiric`/`/arenahp` z boti nista merljivi.

- (Opus 5, 2026-09-04, 03:30) **1v1 arena Lua: testna baterija KONČANA**, PR #912
  (`feat/lua-dots-arena`, čaka ownerjev merge, NIČ deployanega). Šest časovno
  omejenih testov na lokalnem **2.84** z dvema botoma. Deluje: prisilni reset
  33/33, poravnava ščitov, lifesteal točno 50 %, meja `arena_vamp_hp` na enoto,
  stikalo šele ob naslednjem spawnu, veriga modulov nedotaknjena.
  ⛔ **Privzetek vampiric pool 1000 → 500**: krivulja dolžine dvoboja NI
  linearna (300 HP = mediana 7 s, 500 = 14 s, 1000 = **en dvoboj v 120 s**) —
  1000 je natanko »fights take forever« odpoved, dosežena pri 50 %, ne 100 %.
  ⛔ **Izsiljevanje orožja UMAKNJENO** v dokumentiran stub: Axis boti so kljub
  temu spawnali s Kar98, `ClientUserinfoChanged` vihar ~1 Hz, bota sta se
  nehala pobijati (246 lifesteal dogodkov, ENA smrt v 2 min). Odstranitev
  orožja, ki ga klient DRŽI, sproži `EV_WEAPONSWITCHED` (`g_lua.c:1163`).
  **Odprto:** vezava `/vampiric` kot klientskega ukaza ni bila izmerjena (boti
  ne pošiljajo lastnih ukazov, ufw blokira človeka z LAN-a) — semantika je
  izmerjena skozi `arena_vamp_toggle`, ki gre po isti `vamp_pending` poti.
  ⚠️ Na namestitvi **2.85** je `stats_discord_webhook.lua` zastarel in konča
  `et_Obituary` z `return 0` → `live_events.lua` tam ne dobi obituaryjev; na
  2.84 je v redu. **Ali je puran v istem stanju, NI preverjeno.**
  ⛔ `luac` na tem stroju je Lua **5.1** — sintaksa se preverja z `luac5.4`.

- (Fable 5.1, 2026-09-04) Match moments r. 1 (#908) in r. 5 (#909) MERGANI; watchdog
  v6.13 deployan; owner: naslednja **doc 22 (digitalni dvojčki botov)** —
  raziskava teče (agent + puran read-only), nato `docs/design/22`; potem doc 19
  ali moments r. 2 po ownerjevem vrstnem redu.
- (Fable 5.1, 2026-09-03, 22:30) SKOK 4 zaključen: v6.13 mergan (#905)
  in deployan na puran (dokazano), osnovnica bot testa izmerjena, drugi bot
  test z v6.13 teče (22:25–22:55) → poročilo + ukrepi v BACKLOG. #903 (R5)
  mergan (`e3b0a70c`), Stats 2.0 R1–R5 KONČAN. Nato nazaj: doc 19/20 po
  ownerjevem vrstnem redu, doc 21 po ultra pregledu, BACKLOG dolg
  (`db_backup.sh` vloga — javiti sestri pred dotikom).
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

- (4. 9., moments r. 5) `/storytelling/moments` je zdaj unija oblik (opcijski `types` v odgovoru) in še brez `response_model` (`response_model_gap.txt:208`) — kandidat za tipizacijo skupaj z `StoryMoment` (top-level `kills[]`/`victims` pri multikill/team_wipe niso v vmesniku).
- (3. 9., moments r. 1) ⚠️ **tank na sw_goldrush_te: `total_distance` < 1 000 u v 112 od 128 rund** — meritev premika tanka (`sampleVehiclePositions`, `r.currentOrigin` za script_mover?) je vprašljiva; truck je normalen (p50 8 612 u). Preveriti v Lua (polje izvora, `MAX_SANE_MOVE`), preden se tank šteje za »ne premika se«.
- (3. 9., moments r. 1) **moments nima besednjaka »not covered«**: `[]` pomeni tudi »proximity ni zajet«; coverage iz manifesta `vehicle_tracking` (`round_web_service.py:635`) bi dala `status: unavailable` po `_probe_unavailable` vzorcu — sprememba routerja + Story panel.
- (3. 9., moments r. 1) **direktorjev rez skrije 3★ escort** pri bogatih sejah (154: bazen 91, limit 10/50) — po dizajnu; če owner hoče escort vedno viden, rabi svoj panel/filter po tipu (rezina 5), ne dvig zvezdic.
- (3. 9., sestrska seja; **REŠENO #906**, 4. 9.: vloga se izbere namerno, `BACKUP_DB_USER` → korenski `.env`) ~~`scripts/db_backup.sh` pokvarjen~~: teče kot `website_app`, ker `website/.env` prepiše `POSTGRES_USER` iz korenskega `.env`; ta vloga ne sme brati 7 tabel (`voice_members`, `team_pool`, `proximity_reaction_metric`, `processed_endstats_files`, `matchup_history`, `achievement_notification_ledger`, `player_identity_links`) → `pg_dump` »permission denied«. Obvod: `POSTGRES_USER=etlegacy_user POSTGRES_PASSWORD=… bash scripts/db_backup.sh`. Popravek = administrativna orodja berejo LE korenski `.env` (ali izrecen `--role`); še ni dodeljeno — javiti sestri pred dotikom.
- (3. 9., #904) `time_dead_minutes` za vrstice pred 2026-03-24 je rekonstruiran (8 721 vrstic; izvirnik v `time_dead_minutes_original`, zastavica `time_dead_reconstructed`) → Players zavihek `dead min` in `alive %` za stare seje zdaj kažejo druge številke; tooltip bi lahko omenil zastavico (R6 ideja).
- (3. 9., FH v6.13, test 2) **round-end burst trackerja izmerjen 188–224 ms z boti** (`FM top=round_end`) — z ljudmi (~3 000 vrstic) pričakovano več; batch write (`PLAN_LUA_PERF` A2) je prvi ukrep, zdaj z instrumentom pred/po.
- (3. 9., FH v6.13, test 2) webhook `sweep` v 30 min NI presegel 50 ms → ni glavni osumljenec; 9 s `self` ob 0 igralcih (2. 9.) ostaja nepojasnjen, ob ponovitvi ga `FM top=` poimenuje.
- (3. 9., FH v6.13) **`stats_discord_webhook.lua` `pending_retry_sweep` = fork+exec (`os.execute mkdir`, `io.popen find`) vsakih 60 s na igralni niti, po `os.time()` (teče med pavzo in ob 0 igralcih)** — od v6.13 merjeno kot `FM … mod=stats_discord_webhook top=sweep:<ms>`; če se potrdi, sweep preseliti izven frame poti (redkeje, ali ob koncu runde) — sprememba webhooka, ownerjev deploy.
- (3. 9., FH v6.13) tracker `scanVehicleEntities`+`scanObjectiveEntities` = 2×960 `pcall(gentity_get)` ob map loadu — merjeno kot `top=init_scan`; če sekunde, razdeliti sken na več framov.
- (3. 9., FH v6.13) `is_bot_round` zgodovinsko nikoli true (`postgresql_database_manager.py:2246`) — po bot testu preveriti runde z današnjim datumom.
- (3. 9., stats 2.0 R5) **Head-to-head za igralca** (koga je ubil / kdo ga je ubil iz `/storytelling/kill-matrix`) odložen — owner izbral obseg brez njega; matrix je že naložen v Story zavihku, vrstica bi ga le filtrirala.
- (3. 9., R5) **`best-lives` brez coverage zastavice**: `lives: []` ne loči »nezajeto« od »nihče ni dosegel minimuma« — razširjena vrstica to pove z besedilom; prava rešitev je zastavica v odgovoru (backend).
- (3. 9., R5) **KIS details rabi 32-znakovni guid** (`killer_guid = $5`, `storytelling_router.py:400`); stran ga dobi prek `kill-impact` seznama (limit 50) — seja z več kot 50 točkovanimi igralci bi za 51. pokazala »no scored kills«. Danes nemogoče (≤ 12 igralcev), a je meja v kodi imenovana.
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

## 2026-09-05 popoldne — faza 6 r. 3 + popravek merilnika (PR #915)

**Narejeno:**
- availability rezina 3: admin market kontrole (open / settle / void), gap 4 → 3
- ⛔⛔ popravek ekstraktorja: gap merjen **3, resnica 19** — 16 endpointov je
  bilo nevidnih, ker se je zajem ustavil pri prvi `${` in odrezan prefiks
  velja za pokritega. Vsak od 16 preverjen dvakrat (živ openapi + odsotnost
  klica v `src/app`).

**⚠️ ČAKA OWNERJEVO ODLOČITEV (vprašano, brez odgovora):** ali graditi
wrapped/compare (2 od 16), ali najprej zapolniti štiri luknje na profilni
strani (`players/{}/awards`, `players/{}/card`, `skill/player/{}/form`,
`skill/player/{}/history`, `stats/player/{}/form`, `stats/player/{}/rounds`),
ki jih je merilnik skrival in zaradi katerih je ta stran tanjša od številke.

**Odprto zraven:**
- `/api/greatshot/{}/crossref` in `/highlights/render` — greatshot stran ne
  pozna sekcij `clips`/`renders`, legacy ima štiri hube, nova stran ignorira
  `:section` param (ruta ga ima).
- `/api/rounds/{}/player/{}/details`, `/api/rounds/{}/awards`,
  `/api/rounds/{}/vs-stats`, `/api/player/{}/vs-stats` — matches.js in
  session-detail.js.
- `/api/sessions/{}/graphs` — Landing.tsx v komentarju že priznava, da ni
  migriran.
- `/api/uploads/{}/download`.
- ⚠️ V glavnem worktreeju delata dve drugi seji (`opus-backend`, `sonet`) na
  moments/doc 22 — njihovega drevesa se ne dotikam, delam v
  `/home/samba/share/slomix-market`.
- ⛔ #911 (diagnostics), #912 (arena), #882 (release 1.45.0) čakajo ownerja.

## 2026-09-06 — pozicija pred restartom seje (posodobitev Claude CLI)

**Veja `feat/availability-admin-market`, PR #915, 9 commitov, vse potisnjeno.**
Gap **4 → 3 → 19 (korekcija) → 16**.

Narejeno v tem bloku:
1. availability rezina 3 (admin market: open / settle / void)
2. ⛔⛔ popravek ekstraktorja: 16 endpointov je bilo nevidnih, ker se je zajem
   ustavil pri prvi `${`; odrezan prefiks velja za pokritega
3. greatshot: sekcije highlights / clips / renders (ruta je param nosila od
   faze 6, stran ga je ignorirala); brez novega endpointa
4. wrapped kot STRAN (`/wrapped/:guid`) — konvencija modal→stran iz `design/12`
5. compare kot STRAN (`/compare?a=&b=`), z eno namerno razliko: playtime ni
   tekma (legacy da 🏆 tistemu, ki je igral MANJ)
6. rating trendi na profilu (`your form` + `rating over time`)

**Preostali gap (16), po razredih:**
- profil: `players/{}/card`, `players/{}/memory-card`, `stats/player/{}/form`
  (DPM/KD serija, drug graf od skill/form)
- runde: `rounds/{}/awards`, `rounds/{}/vs-stats`, `rounds/{}/player/{}/details`,
  `player/{}/vs-stats`
- greatshot: `{}/crossref`, `{}/highlights/render` (oboje na demo strani)
- drugo: `sessions/{}/graphs` (Landing.tsx to v komentarju že priznava),
  `uploads/{}/download`
- ne zaprejo se z gradnjo: `/api/bets`, `/api/stats/sessions` (šele ob
  upokojitvi legacy js), `/api/diagnostics` (#911)

**⚠️ Okolje po čiščenju 6. 9.:** ET strežnik USTAVLJEN, uvicorn `:8056`
ustavljen (bil sosedov e2e), 240 MB chromium ostankov pobitih. **Teče samo
`:8000`** (preview, `/app/` → 200). Stroj ima 1,8 GB RAM; dve Claude seji sta
skupaj ~900 MB.

**⚠️ Sočasne seje:** `opus-backend` in `sonet` delata v glavnem worktreeju
(`/home/samba/share/slomix_discord`) — PR #921, paritetni prelet. Njihovega
drevesa se ne dotikam; jaz delam v `/home/samba/share/slomix-market`.

**Čaka ownerja:** merge #911, #912, #915, #921, #882; ⛔ `/code-review ultra`
pred deljenjem arena paketa; odločitev, kateri razred iz gapa naprej.
## 2026-09-05 — arena PR #912, odprto po pregledu testov

Pregledni agent za testno zbirko je našel 22 postavk. Popravljene so 4
(zastareli vzorci mutacij → `fail`, `re.search` → `findall`, `setl "ime"` v
narekovajih, prazna datoteka prestane preverbo oklepajev) in ločeni skladišči
zdravja v stubu. **Odprto ostaja:**

- ⛔ mutacijska baterija nima izhodiščnega zagona: če harness pade iz
  nepovezanega razloga, VSAKA mutacija poroča »ujeta«. Popravek: pred zanko
  poženi harness enkrat in prekini, če ne vrne 0.
- primer 20 je votel (`arena_symmetric 0` se preverja, ko `duel_pool` sploh ni
  postavljen → `arena_loadout` se ne kliče). Zraven razkriva vedenje:
  `arena_symmetric 1` ne naredi nič, kadar sta `arena_hp` in `arena_vamp` 0 —
  kar je natanko to, kar nastavi priloženi config.
- primer 20 prva polovica prehaja na puščenem stanju iz primera 19; vzorec
  `et_InitGame` PRED nastavitvijo cvarov se ponovi na 6 mestih.
- stub `trap_SendServerCommand` zavrže naslovnika → zasebna zavrnitev bi lahko
  postala broadcast in noben test ne bi padel.
- stub `gentity_set` sprejme pisanje v `pers.connected` in
  `pers.playerStats.selfkills`, ki sta v motorju READONLY (g_lua.c:1248/:1283).
- `ps.stats` je modeliran samo pri indeksu 0; `STAT_MAX_HEALTH`/`STAT_SPRINTTIME`
  sta deklarirana, a neodgovorjena → `et_Obituary` ju v offline teku bere kot nil.
- štiri vstopna varovala v `et_Damage` niso posamično pripeta (odstrani eno in
  zbirka je zelena); `active`/`enabled()` vrata so testirana na 2 od 5 hookov.
- vsi privzetki vampirica so neizmerjeni (primer 10 pusti cvare postavljene).
- `arena_ammo 0`, `arena_nofatigue 0`, `arena_1v1_log 0` — nobenega primera.
- README pogodba ne opazi IZGINOTJA cele jezikovne tabele (množica ne loči
  odsotnosti od soglasja; rabi `Counter(rows)[ime] == 3`).
- `arena_1v1_map` je dokumentiran, a ga nobena pogodba ne doseže: `armed_map()`
  uporablja `trap_Cvar_Get` in dobesedni fallback, ne `cvar_num`.
- ⛔ B-1: ujemanje imena mape je podniz → `dots_arena_v2` oboroži modul.
- ⛔ NIHČE ni pregledal PR #912 (Copilot in Codex brez kvote). Pred deljenjem
  paketa tujcem naj owner požene `/code-review ultra`.

**Neizmerjeno v živo:** `/team s` med življenjem, `sv_maxclients` (latched),
rotacija loga, gledalska vrata in cooldown, `arena_symmetric` proti človeku,
paket v pk3, dva človeka hkrati — in NOVO: `arena_instant_tapout` v živo.

## 2026-09-05 13:50 — arena PAVZIRANA (owner ugasnil testni strežnik)

Kje sem ostal: PR #912, 22 commitov, CI zelen, **delovno drevo čisto**.

**Dokazano v živo danes** (2.84, podpisi prek `lua_status`):
- `force_tapout`: 20 vrstic, 9 zanje; čas ležanja igralca mediana 1,0 s → 0,0 s,
  max 23,0 s → 0,0 s; ščiti 25 ms narazen. Prvi TAPOUT 13:09:58.
- ⛔ Odkrito ob tem: strežnik je tekel 11,5 ure in bil **10 ur starejši od
  popravka** — »ne dela« je pomenilo »ni naloženo«. Razsodnik je bil
  `lua_status` podpis (`G_SHA1(code)` ob nalaganju, g_lua.c:2597), ne datoteka.

**Nameščeno, a NEIZMERJENO:** `arena_acc_log` (podpis 0CCBE140 naložen ob
13:47, owner je nato ugasnil strežnik → **0 ACC vrstic v živo**). Instrument
je offline pokrit (primera 48/49, mutacije 32/32), runtime dokaza NIMA.

**Ownerjev nedokončan eksperiment:** tapanje proti full auto, v blokih po ~15
dvobojev z oznako v chatu; hipoteza je, da acc naraste, a odloči šele
zadetkov-na-sekundo.

**Odprto ostaja** vse iz vnosa 2026-09-05 zgoraj (22 postavk pregleda testne
zbirke, od tega 5 popravljenih) + ⛔ PR-ja ni pregledal nihče.

⚠️ Pytest je v enem teku danes javil 1 padec, ponovni tek 6227 passed —
neidentificirana nestabilnost, ne moja sprememba. Ob naslednjem padcu ujemi ime.
