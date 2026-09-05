# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> najprej TUKAJ zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

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
