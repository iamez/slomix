# HANDOFF — Astra (Codex CLI), 7. 9. 2026

> Tracked copy of the handoff assembled from two Claude sessions on the owner's request. The same text was delivered as `/tmp/slomix-claude-handoff-to-astra-20260907.md`; this copy lives in the repo so a fresh clone carries it. No secrets: credentials and webhook URLs are only in `.env` files.

Sestavljeno na ownerjevo zahtevo iz dveh Claude sej: **Fable** (ta datoteka, del A)
in **sestrska seja »ssh-monitor-pool-backoff-keys«** (del B, priložen, ko prispe).
Brez skrivnosti: gesla, žetoni in webhook URL-ji so SAMO v `.env` datotekah in
lokalnih izključenih datotekah, nikoli tu. To NI dovoljenje za merge, deploy,
restart ali spremembo prioritet — vse to ostaja ownerjeva beseda za vsak PR posebej.

---

## A. Fable (glavna seja dneva 6.–7. 9.)

### A1. Vstopne točke (točne poti)
| kaj | pot |
|---|---|
| kontrakt agenta (Codex ga naloži sam; preveri `codex debug prompt-input "ping"`) | `/home/samba/share/slomix_discord/AGENTS.md`, `website/frontend/AGENTS.md`, globalno `~/.codex/AGENTS.md` |
| pravila repa (dolga oblika) | `docs/CLAUDE.md` (koren `CLAUDE.md` je symlink), `bot/CLAUDE.md`, `bot/{core,cogs,services,automation}/CLAUDE.md`, `website/backend/CLAUDE.md`, `tests/CLAUDE.md`, `docs/WEBSITE_CLAUDE.md`, `docs/PROXIMITY_CLAUDE.md`, `docs/GAMESERVER_CLAUDE.md` |
| kje smo / kaj je naslednje / kako dokazati | `docs/HANDOFF-next.md` (§0 pravila, §1 stanje, §2 koraki, §3 ukazi, §4 odprte odločitve) |
| plan of record / pozicije | `docs/PLAN.md`, `docs/BACKLOG.md` (prva stran = zadnje pozicije) |
| delovna zanka (Mandelbrot + RCA) | `docs/process/MANDELBROT_RCA.md` |
| kickoff prompt | `docs/prompts/astra_kickoff.md` (dolga + kratka oblika) |
| skupni dnevnik spoznanj (repo-side memory za vse agente) | `docs/AGENT_LOG.md` |
| vodnik za pregledovalce (namerne konvencije, znano odprto) | `docs/REVIEW_GUIDE.md`; telesa rezin `docs/review/SLICES.md` |
| spiderweb (pozicijska mreža) status | `docs/SPIDERWEB_STATUS.md`; spec `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` |
| Claude spomin (Fable): kazalo + 330 datotek | `/home/samba/.claude/projects/-home-samba-share-slomix-discord/memory/MEMORY.md` — BERI kazalo, odpri datoteko po potrebi; **nikoli ne kopiraj v repo** (nekatere nosijo gesla) |
| globalna pravila Claude (za razumevanje ownerja) | `/home/samba/.claude/CLAUDE.md` |
| lokalni dizajn dokumenti (NISO v repu, le v tem checkoutu) | `docs/design/00–24` (README pove vrstni red: 16 → 05 → 06 → 08 → 07 → 09 → 11+12); v repu je podmnožica 00/05/06/09/12/17 + README; `docs/design/21_RUNTIME_V2_EVENT_BRAIN.md`, `22`/`23` dvojčki botov, `24_WATCHDOG.md` |
| lokalno, ne v repu | `docs/research/`, `docs/archive/`, `docs/OMNIBOT_PROJECT.md`, `server/omnibot/*` |
| Codex varovala (zunaj repa) | `~/.codex/config.toml` (reasoning high, 2 podagenta, memories), `~/.codex/rules/slomix-guard.rules` (forbidden > allow), `~/.codex/hooks.json` + `~/.codex/hooks/slomix-guard.py` (port `block-git-sweep`; surov stdin v `~/.codex/hooks/last_input.json` — PREVERI obliko po prvi seji) |

### A2. Pravila GitHub / review / deploy (kratko; podrobno v AGENTS.md §1–§3)
- Feature veja + PR (≤ 25 datotek, pre-push hook), Conventional Commits, `git add` po imenih, `git diff --check origin/main...HEAD -- . ':(exclude)*.md'` pred pushem.
- **Nikoli merge brez ownerjevega DA za TA PR**; merge prek `~/slomix-ops/cycle.sh <pr> <veja> "<naslov>" <telo.md>` (čaka CI, 7 min pavze, zavrne vejo za mainom). Ruleset maina je `strict`: vsak merge postavi VSE odprte PR-je v BEHIND → pred vrati `git merge origin/main` + push; **dve seji hkrati = tekma brez zmagovalca → napovej merge drugi seji, počakaj potrditev**. `gh pr checks --json` ne obstaja; CI rollup ima dve obliki.
- Restart/deploy: dev enoti `etlegacy-bot`/`etlegacy-web` (NOPASSWD restart), **tečeta iz `/home/samba/share/slomix-dev-run`** (klon na mainu; od 7. 9. 02:41), NE iz delovne kopije. Deploy na dev = `scripts/dev_deploy.sh` (fetch, `checkout -B main origin/main`, kopija statike iz agentovega drevesa, restart) — restart je ownerjeva domena, sprašuj. Prod (`slomix-vm`, `slomix-bot/-web`, v1.39.0) je **zamrznjen**; ne dotikaj se.
- Ultra pregled: `/code-review ultra <PR#>` sproži OWNER; meja **8 000 vrstic / 500 datotek na tek** → 20 draft PR-jev **#924–#943** (`review-base/NN` → `review/NN`, glava = mainovo drevo), sekani na `71de6b65`; vrstni red #924 (proximity+spiderweb+Lua) → #925 (backend routerji) → #926 (SPA lib). Ponovni rez po vsakem premiku maina: `scripts/review_slices.sh cut --push`. Nikoli mergati teh PR-jev.
- Dokazi: zeleni testi NISO dovolj — runtime dokaz + mutacija varovala, videna pasti (`cmp` po obnovi). Meri dvakrat; hladno/toplo; absent ≠ error.

### A3. Kaj je preverjeno dokončano (6.–7. 9.), vse na mainu, izdaja **v1.45.0** + kasnejši PR-ji
- Nova stran (SPA `website/frontend/src/app`, `/app`): faze 0–7 zgrajene; endpoint gap = **13** (`grep -vcE '^\s*(#|$)' tests/data/endpoint_gap.txt` je razsodnik; 4 vrstice se ne zaprejo z gradnjo).
- #945 proximity endpointi sprejmejo 8-znakovni guid (kolizije prefiksa SAMO boti; resolver `proximity_helpers.resolve_player_guid`; AST varovalo v `tests/unit/test_proximity_guid_prefix.py`).
- #946 diagnostics stanja degradacije v About panelu (`components/DiagnosticsReport.tsx`; ⛔ prej »voice 0 rows« ob `{count:0,error}`); `/api/diagnostics` tipiziran (`exclude_unset`).
- #947 register datasetov (doc 19 r. 1): `website/backend/services/dataset_registry.py` (34 vnosov), `GET /api/datasets`, profilni router izpelje allowlist iz registra; pravila proti VIRU (route keys, `data-parity`, Lua `isFeatureEnabled`, bot `*_ENABLED`).
- #949 **watchdog r. 1**: `scripts/slomix_watchdog.py` + `deploy/systemd/etlegacy-watchdog.{service,timer}` — teče vsakih 5 min iz run dira, vseh 11 preverb `ok` (2. tek 02:46), alarmi na Discord webhook (`WATCHDOG_WEBHOOK_URL` samo v run-dir `.env`).
- #954 About: watchdog zadnji tek (tri stanja) + vrstica registra; `/api/diagnostics.watchdog` aditiven.
- #957 `response_model` za `/proximity/player/{guid}/profile|radar` (gap response_model 217).
- #959 run dir + `scripts/dev_deploy.sh` + enote + `scripts/mint_watchdog_webhook.py`; #960 (vrata tečejo ob pisanju) = guard: bundle starejši od vira → deploy zavrne.
- Sestrini: #923 SSH monitor nizi (datoteka `logs/bot_error_streaks.json`), #948, #950 paramiko filter (813 → 100 vrstic), #952 PLAN gap = 13 z varovalom.

### A4. Kaj čaka (odvisnosti)
| postavka | čaka na |
|---|---|
| SPA bundle `website/static/app` je **13 h starejši od `src/app`** (nihče ni pognal `build:app` od 6. 9. 11:03); run dir streže isti stari bundle | RAM (1,8 GB; Claude seji ~880 MB) → sestra zgradi, ko se seje zaprejo; potem `scripts/dev_deploy.sh` (guard #960 mora prehajati); restart = ownerjev DA |
| paritetni prelet faze 7 (32 rut × 4 viewporti × anon/owner, `scripts/audit_website_browser.mjs --app`) | RAM; zadnji polni tek 6. 9. zjutraj, po #921 NE ponovljen |
| ultra pregledi #924/#925/#926 | owner sproži; Astra = triaža najdb (zanka `MANDELBROT_RCA.md`, oznaka 1–12) |
| #955 (sestra, nagrade runde), #958 (sestra, `--anon-only` prelet), #912 (arena Lua, pavzirano) | ownerjev DA |
| svež venv na servis v run diru (zdaj simbolna na agentov venv) | r. 2 (izolacija paketov) |
| SSH sonde watchdoga na puran (tailer `pgrep`, `ls -t stats/`) | watchdog r. 2 |
| rotacija DB gesla (v `~/.codex/rules/default.rules` in v argv MCP procesa) + rotacija sudo gesla (bilo v pogovoru) | owner |
| migracija 082 na prod; popravek korpusa `destroyed_count`; dvojčki r. 4 (deploy na puran + bot test); doc 19 r. 2 (`user_page_layouts`, column picker); availability/13 vrzeli po HANDOFF §2.6 | owner |

### A5. Ownerjeva prioriteta: »runtime sprememba« in »Python proces, ki spremlja delovanje« — kaj je kaj
- **Watchdog r. 1 (NAREJENO, teče):** zunanji opazovalec `scripts/slomix_watchdog.py` — 9 read-only preverb (systemd enote po `LoadState`, `/health`, DB + povezave, runde proti kadenci `server_status_history`, `/api/live/status`, mtime kolektorja `~/slomix-server-logs`, frame-health stalli, disk+journald, Lua webhook) + sestrina `logs/bot_error_streaks.json`; ravni ok/warn/fail/**unknown**; politika: alarm ob prehodu (web/lua_webhook šele 2× zapored), dedup 1 h, »recovered« enkrat, heartbeat 1×/dan; **nikoli ne restarta** (systemd ima `Restart=always`; ročni zagon zmaga v tekmi za vrata — incident 2026-08-05). Config iz korenskega `.env` prek `dotenv_values` (nikoli `website/.env` — `POSTGRES_USER` past).
- **Watchdog r. 2 (NASLEDNJA KONKRETNA REZINA, priporočeno):** (a) SSH sonde na puran samo read-only (`pgrep -c -f "[l]iveview_tailer"`, `ls -t` v `stats/`), ključ `~/.ssh/etlegacy_bot`, `SSH_*` iz `.env`; (b) `git -C /home/samba/share/slomix-dev-run rev-parse HEAD` proti `/api/build` (»kar teče = kar je na mainu«) + starost bundla proti viru (isti test kot guard v `dev_deploy.sh`); (c) error rate PO DOGODKIH (ne vrsticah — po #950 so številke neprimerljive; `health_check.sh:585` prag 20/24 h je meril 751 → 38); (d) svež venv na servis. Dokaz: `--once --dry-run` + simuliran izpad (glej `docs/PLAN.md` proga »štiri točke«, #949).
- **Runtime v2 / doc 21 (`docs/design/21_RUNTIME_V2_EVENT_BRAIN.md`, lokalno):** DRUGA stvar — ne nadzor, ampak »event brain«: tabela `events` + `pg_notify`, en emitter `round_ended` v `_process_stats_ready_round` (`bot/services/stats_ready_mixin.py:165`) v ISTI transakciji, prvi naročnik = website (invalidacija cachev), stikalo `EVENT_STREAM_ENABLED` (privzeto OFF, shadow). Ownerjeve odločitve 3. 9.: ločeni procesi (bot in web ostaneta), `events`+`pg_notify` prva rezina, **izvedba ŠELE po ultra pregledu** (+ soak). §9 non-goals: brez prepisa bota/FastAPI/React, brez Redis Streams/Kafka, **brez »runtime kot systemd supervisor«**. Merjeno: 0 od 8 incidentov je nastalo zaradi »preveč procesov«; edini dokazan dobitek je invalidacija cachev prek procesov.
- Torej: **watchdog = spremljanje (r. 1 teče, r. 2 naslednje); runtime v2 = arhitektura dogodkov (šele po ultra triaži, na ownerjev DA).** Ne mešaj ju v en PR.

### A6. Nezapisane ideje / pasti, ki jih Astra rabi
- Artefakt ≠ commit: `/api/build` bere commit, bundle je lahko star → guard v `dev_deploy.sh` (#960).
- `openapi.d.ts` je gitignoran in generiran (`npm run typecheck`/`test`/`build:app` ga regenerirajo prek `pre*`; pred golim `npx` poženi `npm run generate:api`; `rm` ni popravek).
- Skriptni reševalec git konfliktov: obdelaj VSE hunke, JSON ni proza (regeneriraj `docs/api/openapi.json` s `scripts/dump_openapi.py`), po reševanju `grep -c '^<<<<<<<'` = 0; `git add -u` + commit sprejmeta markerje.
- Vlak PR-jev, ki pišejo v isti razdelek PLAN/BACKLOG/AGENT_LOG → docs raje v ENEM zadnjem PR-ju; auto-merge PLAN.md je enkrat tiho PODVOJIL blok (#952).
- Preštej številke ob vsakem zapisu (gap 3/16/13 isti dan v istem dokumentu).
- `pkill -f`/`pgrep -f` ujameta lastno lupino; iskanje po vratih `ss -ltnp`, kill po PID.
- Hladen cache po restartu spremeni tudi ŠTEVILO klicev, ki jih merilnik vidi v oknu, ne le čas (sestra, 03:00).
- `mergeStateStatus` zaostaja za resnico (BLOCKED ob zelenih checkih); `gh pr merge --auto` + eno zlitje maina deluje.
- Moj Claude hook `block-git-sweep` blokira Bash ukaze z LITERALOM `git add -A` v besedilu (tudi v testnih primerih) — Codex ima enak hook v `~/.codex/hooks`.
- RAM: 1,8 GB; brez `npm ci`/`vite build`/Playwright, ko tečeta dve Claude/Codex seji; chromium ostanke pobij po PID.

### A7. Zastareli deli, ki jih poznam
- `docs/HANDOFF-next.md` §1 vrstica »#915 odprt« je zastarela (mergan), §2 številke gapa 3/16 (razsodnik je datoteka = 13); §0 pravilo o restartu velja še vedno; §3 ukazi predpostavljajo `:8056` agentov strežnik (RAM!).
- `docs/CLAUDE.md` Redis vrstica popravljena (dev 6.0.16), »Building & Running« nosi run dir od #959; `infrastructure_reference` spomin še omenja `screen -r slomix` (zastarelo: systemd).
- `docs/INFRA_HANDOFF_2026-02-18.md`, `docs/PRODUCTION_AUTOMATION_GUIDE.md` (opisuje datoteke, ki ne obstajajo) — ne zaupaj kot opisu nadzora.

---

## B. Sestrska seja (»ssh-monitor-pool-backoff-keys«) — dobesedno, 7. 9. 03:35

### B1. Trenutno delo, worktreeji, PR-ji
Worktreeji: `slomix-market` (glavni, veja `fix/anon-sweep-needs-no-owner-secret`), `slomix-arena` (`feat/lua-dots-arena`). `slomix_discord` je zdaj samo še vir statike, detached na `71de6b65`.
Odprti PR-ji: **#955** `feat/round-awards-in-the-app` — zapre `/api/rounds/{}/awards` v SPA; z njim gre botovski filter in `DISTINCT` (B5). CI zelen. **#958** `fix/anon-sweep-needs-no-owner-secret` — `--anon-only` je klical `mintOwnerSession()` brezpogojno, zato anonimni prelet ni startal v worktreeju brez `website/.env`. **#912** `feat/lua-dots-arena` — arena Lua, star; ⚠️ vsebuje `force_tapout` in mutacijski skript, ni bil pregledan tedne.
Danes mergano: #923 (SSH monitor, štiri rezine), #948, #950 (paramiko filter), #952 (varovalo za gap v PLAN.md). Vse v v1.45.0.

### B2. Preverjeno dokončano proti temu, kar čaka
Dokazano v živo: #923 r. 4 — `logs/bot_error_streaks.json` nastane ~19 s po zagonu, `written_at` se premika, `boot_time` stoji; alarm ob tretji napaki kljub dvema restartoma (štirje PID-i). #950 — po restartu `errors.log` 0 paramiko vrstic, `bot.log` 24.
Čaka: ⛔ bundle ni zgrajen (`static/app` 6. 9. 11:03, SPA vir 7. 9. 00:23) → gradnja, nato `dev_deploy.sh`, restart = ownerjev DA. ⛔ prelet faze 7 ni dokončan: anonimni manifest (32 rut) in skrajšani prelet (20 rut, vse 200, 0 konzolnih napak) da; celoten (4 viewporti × anon/owner) ne — RAM.

### B3. Plani in odvisnosti
Za fazo 7 je odprt le končni prelet, nato pregledni PR-ji za ultra. Odvisnosti: RAM (~200 MB ob dveh sejah; Playwright 200–300, vite build več) in ownerjev DA za vsak restart. Endpoint gap 13; #955 → 12. Vrstni red preostalih 12 je v `tests/data/endpoint_gap.txt` (v #955): trije mrtvi (`/api/bets` 0 vrstic, `/api/players/{}/awards` 2, `highlights/render` 1 render iz februarja); ⛔ `/api/sessions/{}/graphs` se ne sme kopirati kot je (pot nosi datum, 2 od 3 legacy klicev ne pošljeta `gaming_session_id`, 13 od 176 dni ima več sej).

### B4. Blokade in zastarelo
`docs/HANDOFF-next.md` §3 navaja `:8056` (ni ga več; dev je `:8000`). ⚠️ `/api/rounds/{}/vs-stats` in `/player/{guid}/vs-stats` sta različna endpointa v različnih routerjih; v gap datoteki je le prvi. Nezapisana ideja: `round_awards` ima 282 skupin, kjer sta dva uvoza dala različne odgovore za isto nagrado (runda 9831, 11 min narazen); `DISTINCT` v #955 jih pusti vidne; `docs/KNOWN_ISSUES.md` nosi vprašanja; nihče ni raziskal, kaj je uvoze pognalo.

### B5. Pasti iz meritev 6.–7. 9.
- ⛔⛔ Artefakt ni commit (bundle 13 h star, `/api/build` kaže prav) — guard v #960.
- ⛔⛔ `ls -la <dir>` pove mtime IMENIKA, ne vsebine; pravo orodje `find <dir> -type f -printf '%T@'`.
- ⛔⛔ Hladen cache ne spremeni le časa, ampak koliko klicev merilnik vidi (2 proti 40 v istem oknu).
- ⛔ Merilnik, ki meri prehitro, poroča prazno stran (`/record-book` 350 znakov pri 1 200 ms; prelet čaka `networkidle` + 2 500 ms).
- ⛔ Štej nosilce, ne datotek (`Proximity.test.tsx` pokriva 7 strani prek starša).
- ⛔ Štetje napak po VRSTICAH ni primerljivo čez #950 (`health_check.sh:585` prag 20/24 h: 751 → 38 isti dan); štej dogodke.
- ⛔ `git stash list` PRED `pop` (tuj star stash je naredil konflikte v čistem drevesu).
- ⛔ `grep -c chrom` / `pkill -f` štejeta/ubijeta sebe.

### B6. Osem »NE DELAJ« z razlogi (sestra)
1. ⛔⛔ Ne gradi connection poola za SSH: `paramiko.SSHClient.connect()` ni thread-safe (paramiko #1904), naše SSH operacije tečejo v `run_in_executor` nitih; pool bi determinirano napako zamenjal za nedeterministično. Pomaga razmik med pollerji (Full Jitter, #923).
2. ⛔ Ne dodajaj retryja na `download_file`: ta pot nima zunanjega `asyncio.wait_for`; retry je namenoma le za `[banner/read timed out — remote slow]`.
3. ⛔ Ne »popravljaj« 25 handlerjev, ki vračajo HTTP 200 z `{"status":"error"}` — ownerjeva odločitev 2026-08-30, pripeta s testom.
4. ⛔ Ne gradi UI za mrtve poti (`/api/bets`, `/api/players/{}/awards`, `highlights/render`).
5. ⛔ Ne briši vrstic iz `tests/data/endpoint_gap.txt` za manjšo številko; test preračuna.
6. ⛔ Ne združuj 282 skupin podvojenih nagrad (dva uvoza z različnimi odgovori — neskladje podatkov, ne prikaz).
7. ⛔ Ne poganjaj `npx tsc`/`npx vitest` namesto `npm run typecheck`/`test` (`openapi.d.ts` generirana; zastarela je hujša od manjkajoče).
8. ⛔ Ne meri ničesar takoj po restartu in ne primerjaj s prejšnjo meritvijo (hladen cache); vsaka številka pove hladno/toplo.
⚠️ `/api/players/{}/card` je kompozit (rating + 90-dnevna forma + percentili + arhetip), NI dvojnik zaprtega `/players/{}/memory-card`.

---

## C. Delovni paket za Astro (vrstni red = prioriteta; vsaka postavka = veja + PR ≤ 25 datotek + runtime dokaz + mutacija varovala, videna pasti; ownerjev DA pred vsakim mergem)

### Faza 1 — takoj, brez ownerjevih odločitev
1. **Triaža najdb ultra** (#924 → #925 → #926, ko jih owner požene): vsaka najdba dobi oznako iz `docs/process/MANDELBROT_RCA.md` (1–12), meritev po drugi poti, popravek ALI zavrnitev z meritvijo; en PR na rezino; `docs/REVIEW_GUIDE.md` pove, kaj je namerno.
1b. **Modularnost SPA, rezine 1–8** (`docs/SPA_MODULARITY.md`; owner 7. 9.: stran se bo ful spreminjala): Panel → trojice → GridRow → `lib/format` → DataTable → register 53 panelov → stanje `Hidden` v `ui.tsx` (doc 19 §5, NE `Absent`) → hex sweep; vsaka z ratchetom, seed = izmerjeno, budget pade v istem commitu; ownerjeve vizualne pripombe iz `docs/DESIGN_PUNCHLIST.md` šele SKOZI enoto.
2. **Watchdog r. 2** (`scripts/slomix_watchdog.py`): (a) SSH sonde na puran, samo read-only (`pgrep -c -f "[l]iveview_tailer"`, `ls -t` v `stats/`), `SSH_*` iz korenskega `.env`, `bot/automation/ssh_handler.py` za host-key politiko; (b) »kar teče = kar je na mainu«: `git -C /home/samba/share/slomix-dev-run rev-parse HEAD` proti `/api/build` + starost bundla proti viru (isti test kot guard v `scripts/dev_deploy.sh`); (c) error rate PO DOGODKIH (nikoli po vrsticah); (d) svež venv na servis v run diru (`python3.13 -m venv venv-bot`/`venv-web`, `pip install -r requirements.txt`/`website/requirements.txt`, enote → nove poti, ownerjev `install`). Dokaz: `--once --dry-run`, simuliran izpad (zaprta vrata), noč brez alarmov.
3. **Bundle + deploy**: ko je RAM prost (obe Claude seji zaprti; `free -m` ≥ 800 MB na voljo): `cd website/frontend && npm run build:app` v agentovem drevesu `slomix_discord`, preveri hash bundla in mtime `static/app/app.html` proti zadnjemu commitu `src/app`; `bash scripts/dev_deploy.sh` — **restart le z ownerjevim DA**.
4. **Paritetni prelet faze 7**: `AUDIT_BASE_URL=http://127.0.0.1:8000 node scripts/audit_website_browser.mjs --app --out /tmp/audit` (32 rut × 4 viewporti × anon/owner; `--anon-only` po #958 brez `website/.env`); `networkidle` + 2 500 ms; chromium ostanke pobij po PID; najdbe → rezine; izid v `docs/PLAN.md`.
5. **Endpoint gap 13 → manj** po vrstnem redu in razlogih v `tests/data/endpoint_gap.txt` (sestra, #955): S = `greatshot/{}/crossref`, `stats/player/{}/form`; M = `players/{}/card` (KOMPOZIT, ni memory-card), `rounds/{}/player/{}/details` (legacy modal bere polja, ki jih handler ne vrne — ne prenesi napake); ⛔ `sessions/{}/graphs` NE kopirati kot je (datum v poti, 13 od 176 dni ima več sej); ⛔ `rounds/{}/vs-stats` brez `GROUP BY` → popravi handler prej; mrtve poti (`/api/bets`, `players/{}/awards`, `highlights/render`) brez UI; `uploads/{}/download` je pokrit prek `download_url`.
6. **`response_model` gap 217 → 0** po routerjih, z metodo `docs/…` (memory `response_model_selection_method`: posnetek korpusa + AST + živa meritev; prazen seznam = ne tipiziraj); `tests/data/manual_type_drift.txt` na 0; vsak model = unija posnetih oblik, `exclude_unset` le kjer je odsotnost pomen.
7. **About/admin**: `bot_streaks` prikaz iz `/api/diagnostics.watchdog.levels`; heartbeat ura iz configa (`WATCHDOG_HEARTBEAT_HOUR`); `time`/`pool` sekciji že.

### Faza 2 — po ownerjevih odločitvah (vprašaj z opcijami, ENO odločitev naenkrat, priporočilo označi)
8. **Doc 19 r. 2–3** (`docs/design/19`, lokalno): `user_page_layouts` (nova migracija 083 z `website_app` GRANT v isti datoteki; migracije so nespremenljive), `GET/PATCH /api/preferences/{page}` (`user_id` iz seje prek `middleware/auth_helpers.website_user_id_from_user`, `extra="forbid"`, brez prostega besedila), column picker basics tabele, `Hidden` stanje v `components/ui.tsx` (NE `Absent`; hidden = brez zahteve).
9. **Runtime v2 r. 1** (`docs/design/21`, lokalno): `events` tabela + `pg_notify('round_events', id)`, emitter `round_ended` v `bot/services/stats_ready_mixin.py:_process_stats_ready_round` v ISTI transakciji, website `LISTEN` (asyncpg) → invalidacija `stats_cache`/HTTP cache za sejo, stikalo `EVENT_STREAM_ENABLED` OFF (shadow); meritve pred/po (latenca do Discord posta, `COUNT(events)`/seja = runde, staleness cachev). ⛔ ŠELE po triaži ultra in ownerjevem DA; ⛔ ne »runtime kot supervisor«, ne Redis Streams/Kafka.
10. **Dvojčki r. 4** (`docs/design/22`, `server/omnibot/twins/*`): deploy na puran + harness bot proti človeku — ownerjev deploy; pragi iz kontrole (premešane seje ≈ 21 %).
11. **Korpus `destroyed_count`** (fantomska +1 na goldrush rundah pred Lua v6.14): obseg, backup vrstic, dry-run diff, popravi le z izvornim virom.
12. **Migracija 082 na prod** ob naslednjem release deployu (prod zamrznjen v1.39.0 — owner).
13. **`round_awards` 282 skupin** z različnimi odgovori dveh uvozov (runda 9831, 11 min narazen): RCA, kaj je pognalo dva uvoza; NE združevanje.

### Faza 3 — dolg in kakovost (kadar koli, majhni PR-ji)
14. Docs: `docs/HANDOFF-next.md` §3 `:8056` → `:8000` (run dir); `docs/PRODUCTION_AUTOMATION_GUIDE.md` opisuje neobstoječe datoteke → označi zastarelo; spomin `infrastructure_reference` omenja `screen -r slomix` (zastarelo).
15. TODO/FIXME popis (`bot/`, `website/backend`, `website/frontend/src/app`, `scripts`) → `docs/BACKLOG.md` s prioriteto.
16. INFRA follow-upi (`docs/INFRA_HANDOFF_2026-02-18.md` §5/§6): alert route Prometheus → Discord ali umik `monitoring/`; CSRF/CORS/TLS dokončanje.
17. Logrotate na dev (`deploy/logrotate/slomix.template`; `logs/` v agentovem drevesu 380 MB) — namestitev = owner.
18. Spider-web follow-upi (`docs/SPIDERWEB_STATUS.md`): 3D kamera, belief regions, label placement; prosta pot ostane `unvalidated` do ownerjevega podpisa §8.
19. Preveri v `docs/PLAN.md`: Stats 2.0 R5, doc 20 moments panel, večerni odčitek `frame_health.log` (lag proga), Lua `stats_discord_webhook.lua` sweep izven frame poti (owner deploy).
20. Codex varovala: po prvi seji preveri `~/.codex/hooks/last_input.json` (oblika stdin), popravi `slomix-guard.py`; `~/.codex/rules/slomix-guard.rules` `match/not_match`.

### Merilo za dan preklopa nove strani (doc 09; vse hkrati)
`tests/data/endpoint_gap.txt` prazna (danes 13; 4 se zaprejo le z upokojitvijo legacy JS) · `parity_diff.mjs` čist na 32 rutah × 4 viewporti × anon/owner · e2e zelen oba projekta · canvas pixel-diff (orodja še NI) · openapi posnetek = živa aplikacija · svež igralni večer na dev. Preklop = `build:app` v `scripts/deploy_release.sh` + SPA fallback v `main.py`; legacy ostane na `/legacy/` en cikel; 1–2 tedna soaka pred prod.

---

## D. NE DELAJ (z razlogi)
Sestrinih osem (B6) + Fable:
- ⛔ Ne menjaj veje in ne urejaj v `/home/samba/share/slomix-dev-run` (run dir; deploy le prek `scripts/dev_deploy.sh`); ne menjaj veje v `/home/samba/share/slomix_discord` (primarni worktree; 12 worktreejev kaže vanj; drži ga na `origin/main`) — delaj v svojem `git worktree`.
- ⛔ Ne poganjaj `npm ci`/`vite build`/Playwright, dokler ni RAM prost (1,8 GB stroj; swap udari po botu/webu).
- ⛔ Ne mergaj `review:` PR-jev #924–#943 (pregledna vozila) in ne briši vej `review-base/*`, `review/*`.
- ⛔ Ne ustvarjaj migracije brez `website_app` GRANT-a v isti datoteki (vzorec `migrations/078_*.sql`); ne urejaj merganih migracij.
- ⛔ Ne šteje ERROR vrstic kot mere zdravja (po #950 neprimerljivo); dogodki.
- ⛔ Gesla nikoli v argv (`ps` je javen), v chat ali v tracked datoteke; `sudo -n -l` prej; `.env` beri prek `dotenv_values`, nikoli `website/.env` za admin orodja (`POSTGRES_USER` past).
- ⛔ Ne restartaj/deployaj servisov brez ownerjevega DA za TO dejanje; puran (igralni strežnik) = owner; `lua_restart` nikoli.
- ⛔ Ne zapiraj gap vrstic brez dokaza (živ `/openapi.json` + en resničen klic); ne spreminjaj ratchet proračunov navzgor (`vocabulary` 41, `tokens` 26) — le navzdol v istem commitu.

## E. Kako začeti (Astra, prva ura read-only)
`AGENTS.md` (že naložen) → `docs/HANDOFF-next.md` → `docs/PLAN.md` → `docs/BACKLOG.md` (prva stran) → `docs/process/MANDELBROT_RCA.md` → `docs/REVIEW_GUIDE.md` → `docs/AGENT_LOG.md` → ta datoteka (del C). Nato `git status`, `gh pr list`, `free -m`, `systemctl list-units --all 'etlegacy-*'`, `ss -ltnp`, `bash scripts/health_check.sh`. Ownerju: snapshot ≤ 15 vrstic + 3 predlogi z oceno tveganja + vprašanja z opcijami. Odgovori v slovenščini; koda/commiti angleško.

---

## G. Odgovori Astri (plan-mode vprašanja, 7. 9. 11:15) — vsak z meritvijo, ne s spominom

### G1. Začeto delo BREZ runtime dokaza ali le delno oddano
| kaj | stanje na dev (izmerjeno 11:10) | dokaz |
|---|---|---|
| **SPA spremembe #946 (diagnostics stanja), #954 (watchdog vrstica, register), #921 (faza 7)** | koda na mainu, **NI servirana**: bundle `slomix-dev-run/website/static/app` najnovejša datoteka 6. 9. 11:03, zadnji commit v `src/app` 7. 9. 00:23 (`3fdfd88b`) | `find …/static/app -type f -printf '%TY-%Tm-%Td %TH:%TM'` proti `git log -1 -- website/frontend/src/app`; About panel na `:8000/app` je torej star |
| **watchdog r. 1 — pot alarma na Discord** | nikoli sprožena v živo: `logs/watchdog_state.json` ima `last_alert_at: 0.0` pri vseh 11 ključih; 11/11 `ok`, heartbeat datum 2026-09-07 zapisan (torej ura 09:00 je šla mimo — ali je bil heartbeat POSLAN, iz stanja ni razvidno, preveri kanal) | dokazan je le `--once` cikel + webhook ustvarjen; **simuliran izpad (zaprta vrata → alarm v ≤ 10 min) NI narejen** = prva Astrina meritev v r. 2 |
| **#912 `arena_acc_log`** (sestra) | nameščen, **0 ACC vrstic v živo** (strežnik ugasnjen po namestitvi); offline 48/49 + 32/32 mutacij; CI 11/11 zelen po rebasu (`02880c10`) | manjkajoča meritev = en dvoboj na prižganem testnem strežniku, podpis prek `lua_status` (razsodnik), ne datoteke |
| **#923 SSH monitor r. 1–4** | TEČE iz run dira od 02:57 (`bot_error_streaks.json` piše se, 11:07) — dokaz za obstoj datoteke; **alarm ob tretji napaki v živo po restartu 02:57 ni bil znova viden** (prej dokazan s 4 PID-i v starem drevesu) | `ls -la logs/bot_error_streaks.json` v run diru |
| **`dev_deploy.sh` guard (#960)** | mergan 09:03; run dir je 1 commit ZA mainom (`71de6b65` proti `7ced9435`) — razlika je samo ta skripta, brez runtime učinka; guard je bil preverjen z mutacijo v PR-ju, **ne pa z resničnim deployem** (bundle še ni zgrajen → prvi resnični tek bo exit 3 po načrtu) | `git -C slomix-dev-run rev-parse HEAD` |
| **prelet faze 7** | zadnji polni tek 6. 9. zjutraj, po #921 ni ponovljen (RAM) | — |
| **`round_awards` v SPA (#955)** | odprt; tudi po mergu ostane NEVIDEN, dokler bundle ni zgrajen | — |

### G2. Trditve v #961, ki so zastarele ali v nasprotju z artefakti (popravi ob branju)
- `HANDOFF-astra-inventory.md` §0: »#960 open« → mergan 09:03 (main `7ced9435`). §4 »Restart the dev bot — not one line of #923 is running« → **zastarelo**, bot teče iz run dira na `71de6b65` od 02:57. §4 »Install the timer« → **narejeno** (timer aktiven, teče vsakih 5 min). §4 `[✓/verify] watchdog key + About line` → koda mergana (#954), a NI servirana (G1). §1 »`AUDIT_BASE_URL=…:8056`« → dev je `:8000`.
- `HANDOFF-astra.md` §A3 »#954 About: watchdog zadnji tek« in »#946 diagnostics stanja v About panelu« → mergano, **ne servirano** (bundle). §A4 »#960 vrata tečejo« → mergan.
- §A1 »Codex varovala … hook« → Astrin audit: **oba hooka sta `untrusted` in se preskočita**; guard ne ujame `git -C … add -A` / `reset --hard`; `push origin x --force` (zastavica zadaj) gre skozi rules kot `allow`; `last_input.json` beleži surov vnos (0664). Torej »varovalo« iz predaje trenutno NE deluje — pisna pravila so edina meja.
- §A4 »rotacija DB gesla v `default.rules`« potrjeno: 194 vrstic s `PGPASSWORD=` (audit) — še vedno odprto, owner.

### G3. Ownerjeve odločitve: SPREJETE danes proti ODPRTIM
Sprejete (7. 9.): prod ostane zamrznjen v1.39.0; »zapri odprte PR-je razen Don't merge« (#960 ✓, #958 v vratih, #955, #912 sledita — #912 s sestrinim pridržkom); restarti to noč delegirani Fable (izvedeni 02:57, dovoljenje ni prenosljivo na druge seje); popolna predaja + dokončanje začetega + stabilnost PRED runtime v2, nove funkcije pozneje (Astri, 11:00); **dopolnitev (Astri, 11:30): RAZVOJ runtime v2 se sme začeti po preverbi stabilnosti in zahtevanih pregledih/popravkih; opazovalno obdobje 1–2 tedna velja pred AKTIVACIJO/produkcijo, ne pred izoliranim razvojem** — §C 9 se s tem premakne iz »šele po ownerjevem DA« v »po triaži ultra + stabilnosti, stikalo OFF«.
Odprte (naslov → kje): rotacija sudo gesla (bilo v pogovoru) in DB gesla (`default.rules`, argv MCP) → owner; `build:app` + `dev_deploy.sh` + restart DA → owner; ultra #924/#925/#926 → owner požene; #912 zdaj ali po meritvi ACC → owner; Node 22.22+ na stroju (aktiven 20.20.0, frontend zahteva ≥ 22.22.0, `.nvmrc` 22.13.1) → owner/namestitev; ločeni venv-i za run dir → r. 2 z ownerjevim `install`; ostalo = `HANDOFF-astra-inventory.md` §11 (destroyed_count, FIX 13, doc 19/20/21/22 vprašanja, `denied_playtime`, `full_selfkills`, `vs-stats`, `highlights/render`, `awards` postavitev, cron `kill etlded`, hosting ticket).

### G4. Doc 21 (runtime v2) — predpostavke, ki jih NISEM preveril v kodi
1. »Emitter v ISTI transakciji kot zapis runde«: transakcija obstaja v `postgresql_database_manager.py:1661` (uvoz datoteke; `:1750` obvesti korelacijo PO commitu) — **nisem preveril**, ali bot pot `_process_stats_ready_round` (`bot/services/stats_ready_mixin.py:165`) gre skozi TO metodo ali skozi lastne `execute` klice brez transakcije (v mixinu ni nobenega `transaction`).
2. »Website kot LISTEN naročnik«: v `website/backend` ni nobenega `LISTEN`/`add_listener`; **nisem preveril**, ali websiteov pool (`local_database_adapter.py` ovoj) sploh dovoli namensko trajno povezavo za LISTEN in kako preživi restart PG.
3. »Dedup na `(map, round_number, round_end_unix)`«: `rounds.round_end_unix` ima `DEFAULT 0` (`tools/schema_postgresql.sql:606`) in R0 vrstice se še pišejo → ključ z 0 trka; **nisem izmeril**, koliko vrstic ima 0.
4. »Replay iz `events`«: nisem preveril, da so porabniki idempotentni (Discord post dvakrat = dva posta); doc 21 to predpostavlja.
5. »Latenca ≈ 0 dodana«: ni osnovnice datoteka→Discord post; izmeri PRED rezino.
6. `pg_notify` payload meja 8 000 B in izguba ob odklopu poslušalca (NOTIFY ni trajen) — doc omenja, koda ne obstaja.

### G5. Manjkajoči indeksi / nepotisnjeno / lokalno
- Nepotisnjenih commitov v NOBENEM od 13 worktreejev (izmerjeno `@{u}..HEAD` = 0); 8 scratchpad worktreejev seje Opus (`…/57cfdfc9…/scratchpad/{armed,audit,bkp,diag,stale,tpp,tppbf,…}`) na že merganih vejah, 3 z umazanim drevesom (audit 1, tpp 3, tppbf 1 datoteka) → pobrati/odstraniti po protokolu (`readlink /proc/*/cwd` prej).
- ⛔ `git stash list` v primarnem drevesu: `stash@{0}: WIP on deploy-script-and-docs` (tuj, star) — ne popaj.
- ⚠️ Lokalna datoteka v primarnem drevesu z imenom, ki nosi del **prod webhook URL-ja** (`webhook prod https…txt`, 15. 8., 526 B, v `.git/info/exclude`) → ownerju: premakni izven drevesa; vsebine nisem bral.
- Lokalno, ne v repu (po namenu): `docs/design/00–24` razen podmnožice, `docs/research`, `docs/archive`, `server/omnibot`, `~/.claude/plans/nifty-honking-scroll.md` (načrt te predaje, začasen), Claude spomin `~/.claude/projects/-home-samba-share-slomix-discord/memory/` (kazalo `MEMORY.md` je 31 KB > 24 KB meje → nalaga se le del; ⚠️ za Claude, ne za Codex).
- Codex: `~/.codex/memories/` prazen (asinhrono), hooki untrusted (G2) — to je Astrin audit, potrjujem lastništvo datotek/mode (0664 `hooks.json`, `last_input.json`).

---

## H. Sestrska seja — odgovor na Astrina vprašanja (7. 9. 11:25, dobesedno)

**(1) Začeto brez runtime dokaza ali le delno oddano**
1. ⛔⛔ Nobena SPA sprememba od 6. 9. 11:03 ni vidna na `:8000`. Bundle, ki ga strežnik servira, je `app-BP8nlUYF.js`, najnovejša datoteka v run-dir `static/app` je `2026-09-06 11:03`, zadnji commit v `website/frontend/src/app` na mainu pa `2026-09-07 00:23` (`3fdfd88b`). Vse poznejše SPA delo obstaja v repozitoriju, ne pa v brskalniku.
2. #955 (nagrade rund v SPA): niti mergano niti vidno. Backend del (bot filter, `DISTINCT`) 6 testov, SPA panel 5 — runtime dokaza v brskalniku nima, ker bundla ni.
3. #923 rezine 1–4: dokazano v živo iz run dira (`logs/bot_error_streaks.json` ~19 s po zagonu, `written_at` se premika, `boot_time` stoji; alarm ob tretji napaki čez štiri PID-e).
4. #950 (paramiko filter): po restartu `errors.log` 0 paramiko vrstic, `bot.log` 24 — ⚠️ tistih 24 je `INFO`; filter še ni bil preizkušen na resnični SSH napaki.
5. #958 (`--anon-only`): anonimni manifest prelet čez 32 rut je zapisal `inventory.json`; pred popravkom se ni zagnal.
6. Prelet faze 7: delen (manifest 32 rut + skrajšani prelet 20 rut, vse 200, 0 konzolnih napak); celoten 4 viewporti × anon/owner NI tekel — RAM.

**(2) Nepotisnjeno delo — nič.** `slomix-market` in `slomix-arena`: 0 commitov pred originom, 0 neshranjenih datotek. ⚠️ `git stash list`: `stash@{0}: WIP on deploy-script-and-docs: 339f618 …` — ni njen, ni današnji; nocoj pomotoma popan na čisto drevo → konflikti → `reset --hard`; stash nedotaknjen; naj ga pogleda lastnik.

**(3) Zastarelo v #961**
- ⛔ »`/api/rounds/{}/awards` — depends on owner decision on where« ne drži več: površina je v #955 (`RoundsTable` prop `onSelectRound` je bil brez porabnika; zdaj klik odpre panel z nagradami). Odprto le, ali owner površino potrdi.
- ⚠️ »proof: raw `value` vs nicer form« — pravi razlog za previdnost: `round_awards` ima 1 472 podvojenih (round, award) skupin; 929 identičnih odstrani `DISTINCT`, 282 (dva uvoza, različni odgovori) namenoma ostane; `docs/KNOWN_ISSUES.md`.
- ✅ Drži: gap 13, `endpoint_gap.txt:100`, 94 vrstic komentarjev, #955 → 12 ob mergu.

---

## I. Astrine korekcije (7. 9. 12:10) — preverjene v kodi, dobesedno navedene z dokazom
| Astrina trditev | preverba | posledica |
|---|---|---|
| `scripts/review_slices.sh:109-110` uporablja `git push --force --no-verify` — v nasprotju z AGENTS | **DRŽI** (vrstici 109–110). Namerno: pregledne veje `review-base/*`/`review/*` so vozila (drevo = main, nikoli mergana, ponovni rez po vsakem premiku maina); pre-push kapica 25 datotek bi 500-datotečno vozilo prepovedala. | Astra: ne bo poganjala `cut --push`; njen načrt = nespremenljivi posnetki/nove veje s pravimi pre-push preverbami in ≤ 25 datotek na rezino (⚠️ 93 k vrstic / 25 datotek = precej več kot 20 PR-jev; owner naj izbere med hitrostjo in higieno). Pravilo za AGENTS.md: izjema mora biti ZAPISANA ali skripta spremenjena. |
| Mehanizem sirot v mrtvih urah že uporablja skupni `dead_hours` + `awake_cutoff` (PR #652) | **DRŽI**: `bot/core/dead_hours.py`, `relinker_mixin.py:16,253` (`awake_cutoff(now, _PERMANENT_ORPHAN_AGE_HOURS)`), `monitor_tasks_mixin.py:40`. | Inventar §3 »Dead-hours orphan mechanism — High« je zastarel (KNOWN_ISSUES vnos je pred popravkom); ostane le vprašanje, ali NOVE sirote še nastajajo (meritev, ne mehanizem). |
| »thin« e2e že uporablja sejo 80 | **DRŽI**: `website/frontend/e2e/session-tabs.spec.ts:24` (`{ id: 80, note: 'thin: no KIS, no teams, no proximity' }`). | Inventar §7 »SAMPLES_THIN needs a different session« zastarel. |
| CSRF middleware in dev-requirements v CI že obstajata | **DRŽI**: `website/backend/main.py:52,145` (`csrf_allowed_origins`), `.github/workflows/tests.yml:88,93` (`requirements-dev.txt`). | Inventar §8 (INFRA follow-upi) »CSRF … still open« in »dependency policy« sta vsaj delno zaprta; ostane produkcijska CORS allowlist + TLS vodnik (nepreverjeno). |
| Watchdog: SLA ≤ 2 min ni združljiv s 5-min timerjem + potrditvijo dvakrat | **DRŽI**: timer `OnUnitActiveSec=5min`, `decide()` potrdi dvakrat za web/lua_webhook → najslabši primer ≈ 10 min. | Inventar §4 »alarm within 2 min« → **≤ 10 min**; §C 2 dokaz popravljen. |
| `--dry-run` še vedno piše `WATCHDOG_LAST_FILE` | **DRŽI**: `scripts/slomix_watchdog.py:620-622` (`if not dry_run:` shrani stanje; poročilo se zapiše v obeh primerih). | Namerno (About panel bere zadnje poročilo), a `dry_run: true` v poročilu mora biti viden v UI — preveri `WatchdogLine`. |
| Stanje se shrani PRED dostavo webhooka | **DRŽI**: `:620` (shrani) pred `:626` (pošlji). Neuspela dostava je zabeležena kot »alarmirano« in dedup jo 1 h skrije. | Watchdog r. 2 postavka: shrani `last_alert_at` šele po 2xx; neuspeh dostave = lastna najdba. |
| Kanonična uvozna transakcija je `manager.process_file`, ne STATS_READY | **DRŽI**: `postgresql_database_manager.py:1574` (`process_file`) → `:1661` (`conn.transaction()`); `stats_ready_mixin.py` nima nobenega neposrednega DB klica. | §G4 1 razrešeno: emitter runtime v2 spada v `process_file` transakcijo. Pozne Lua posodobitve (webhook po uvozu) in brskalniški cache rabita ločeno obravnavo. |

---

## J. Modularnost nove strani — ownerjeva zahteva 7. 9. (»stran se bo ful spreminjala«)
Izmerjeno (revizija, dvakrat preverjeni ključni števci): tokeni **dobro** (652/654 velikosti pisave prek `var(--fs-*)`, 30 hex proti 2 086 `var(--)`), besednjak stanj **dobro**, proximity pokritost **dobro** (66/67 endpointov — telemetrija NI minimalna, manjka globina: spider-web sloja 3–4), ponovna raba primitivov **delno** (44 ročnih `gridTemplateColumns` proti 2 `DataTable`, 1 412 inline stilov, 58–62 ročno ponovljenih trojic pending/error/absent — `ProxPanel` to že rešuje, a le za proximity), deklarativna konfiguracija **šibko** (1/38 strani ima stolpce kot podatke; register datasetov ne vodi NOBENEGA piksla; 169/179 panelov ni v registru).
Načrt sanacije = **8 rezin** v `docs/SPA_MODULARITY.md` (Panel → trojice → GridRow → format → DataTable → register 53 panelov → stanje `Hidden` v `ui.tsx` (doc 19 §5, NE `Absent`) → hex sweep), pravila za naprej v `website/frontend/AGENTS.md`, ownerjeve vizualne pripombe v `docs/DESIGN_PUNCHLIST.md`. **V §C se to vrine kot postavka 1b (takoj po triaži ultra, pred endpoint gap)** — ker se bo stran spreminjala, mora vsak popravek videza doseči vse strani prek ene enote.
