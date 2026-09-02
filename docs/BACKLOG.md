# BACKLOG — kje sem ostal + kaj se je spremenilo ad hoc

> Pravilo za skoke: ko uporabnik vpraša nekaj IZVEN trenutnega taska,
> najprej TUKAJ zapiši, kje si ostal; po fixu se vrni in vpiši, kaj si
> spremenil — tudi če si kaj pokvaril. Commit po vsakem zaključenem
> koraku, ne na koncu dneva.

## Trenutna pozicija

- (Fable, 2026-09-02) SKOK: rekonstrukcija izgubljenih planov iz sejnih
  transkriptov — IZVEDENO: 56 skupin / 200 različic / 121 editov v
  `~/claude-plan-recovery/` (lokalno, INDEX.md; 41 skupin je obstajalo samo
  v transkriptih). Skript: scratchpad `recover_plans.py` (samo bere,
  idempotenten). Nič pokvarjeno. Vrnjen na rezino »player dodatki«.
- (Fable, 2026-09-02) #881 v merge ciklu; naslednja rezina: player dodatki
  (4 poti). Ni prekinjenih skokov.

## Tehnični dolg / ideje (nikjer drugje zapisane)

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
