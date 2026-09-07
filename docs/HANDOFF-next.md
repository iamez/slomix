# HANDOFF — 2026-09-06 (Fable 5.1 → naslednji agent)

> **Current handoff override — 2026-09-07, Astra.** Start with the "Astra
> execution ledger" in `docs/PLAN.md`; the sections below are a historical
> snapshot, not the current queue. #955 and #912 are merged at `4f653c01`;
> #961 merged as `28662f04`; its Claude handoff evidence is now included.
> Merge, build, active service and runtime proof are separate states.
> Do NOT run the old review `cut --push`: it uses forbidden push options.
> Do NOT treat old server/browser commands as permission to start them.
> Watchdog exists; delivery/retry proof is still required. Keep its 5-minute
> cadence/two-failure policy unless explicitly changed, not a <=2-minute SLA.
> Raw Codex hook input logging must be removed, not validated by logging
> more real commands. Private Claude memory stays private.
> Runtime starts with `round_stats_imported` in the canonical PG transaction,
> NOT `round_ended` in the Discord mixin. Stability before development;
> 1–2 week observation before activation, not before development.

Vstopna točka za avtonomnega agenta. Vir resnice za načrt je `docs/PLAN.md`,
pozicije in odprte stvari so v `docs/BACKLOG.md`; ta datoteka pove, KJE smo,
KAJ je naslednje in KAKO se dela (pravila + dokazi). Dizajn nove strani je v
`docs/design/` (lokalno; beri `README.md` → 16 → 05 → 06 → 08 → 07 → 09 → 11+12).

## 0. Kako se dela v tem repu (trda pravila)
- Feature veja + PR; **nikoli merge brez ownerjevega dovoljenja za TA PR**;
  merge prek `~/slomix-ops/cycle.sh <pr> <veja> "<naslov>" <telo.md>` (čaka CI,
  7 min pavze, zavrne vejo za mainom → prej `git merge origin/main`).
- `git add` po IMENIH (pre-push zavrne > 25 datotek čez vse commite pusha in
  `git add -A`); pred pushem `git diff --check origin/main...HEAD -- . ':(exclude)*.md'`
  (CI whitespace gate pade na prazno vrstico na koncu datoteke, brez pytest
  izpisa — Python job konča s kodo 2).
- Zeleni testi NISO dovolj: vsaka rezina rabi runtime dokaz (endpoint/stran/log)
  in vsaj eno mutacijo varovala, ki je bila VIDENA pasti (`cmp` po obnovi).
- Dev servisi tečejo iz `/home/samba/share/slomix-dev-run` (klon na mainu, od
  7. 9.), NE iz tega drevesa; deploy na dev = `scripts/dev_deploy.sh`
  (restart je NOPASSWD). Enote: `deploy/systemd/`. Watchdog timer teče iz
  istega imenika; webhook je v run-dir `.env` (`WATCHDOG_WEBHOOK_URL`).
- Nikoli restart/deploy servisov (`etlegacy-*`/`slomix-*`) brez ownerja; dev
  strežnik agenta je `nohup ./venv/bin/python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8056`
  (pid prek `ss -ltnp | grep :8056`, nikoli `pgrep -f`; zagon traja > 10 s).
  Dev `:8000` restarta owner. Puran (igralni strežnik) deploy = owner ali
  izrecna predaja; nikoli `lua_restart`.
- Lokalne datoteke, ki NISO v repu (gitignore): `docs/design/00–23`,
  `docs/OMNIBOT_PROJECT.md`, `server/omnibot/*`, `docs/archive`, `docs/research`.
  Agent v TEM checkoutu jih vidi; svež klon ne.
- Slovenščina v pogovoru z ownerjem; koda, komentarji in commiti angleško.
- Ownerju postavljaj konkretna vprašanja z opcijami, eno odločitev naenkrat.

## 1. Kje smo (verificirano 6. 9.)

### Nova spletna stran (SPA `website/frontend/src/app`, servirana na `/app`)
| kaj | stanje |
|---|---|
| faze 0–6 | zgrajene (32 rut v `routes.data.json`, vse `built`) |
| dolg r. 1 (#919, mergan) | keymap 7 rut resničen + guard (zgrajena ruta ne sme imeti `phase-N`), `/replay` → `/proximity`, `/api/diagnostics` admin panel na `/admin`; **vrzel endpointov 3** (`/api/bets`, `/api/bets/market` = ownerjeva odločitev; `/api/stats/sessions` = z upokojitvijo legacy JS) |
| faza 7 r. 1 (#920, mergan) | `compare` (`/compare/:a?/:b?`) in `wrapped` (`/profile/:id/wrapped`) kot ruti; **O1 zaprta: Clips strani NI** |
| faza 6 r. 3 + faza 7 r. 2 (#915, **mergan 6. 9. 14:40**) | availability admin market (open/settle/void); greatshot sekcije highlights/clips/renders (ruta je `:section?` nosila od faze 6, stran ga je ignorirala — brez novega endpointa); profil: rating trendi (`skill/…/form` + `/history`), serije po metriki (podatek je bil ŽE na strani, le nihče ga ni risal), memory card; `PlayerDrilldown` 6. instrument = dueli seje. ⚠️ `compare`/`wrapped` iz te veje ODSTRANJENA — #920 ju je mergal medtem |
| ⛔⛔ vrzel endpointov | **3 → 13, in to je KOREKCIJA, ne novo delo.** Legacy ekstraktor se je ustavil pri prvi `${`, zato je odrezan prefiks (`/api/players`) veljal za pokritega, brž ko nova stran kliče karkoli globljega — 29 legacy klicev nosi interpolacijo s segmentom za njo. Popravljeno v `test_route_contract._FE_FULL_PATH_RE`; vsaka vrstica v `tests/data/endpoint_gap.txt` ima zdaj zapisan razlog. #915 je od 15 zaprl dve (`bets/market`, `skill/…/form`+`/history`) in nato še tri (memory-card, player vs-stats) |
| končni paritetni prelet | veja `docs/phase7-sweep`: `scripts/audit_website_browser.mjs --app` čez 32 rut × 4 viewporti × anon/owner (256 preverb). Prava napaka: **»proximity →« s seje je nosil 8-znakovni guid → vsak skok na »ni zajema«** (popravljeno + e2e dokaz v tej veji); popravljeni audit/e2e vzorci (`:id/:a?/:b?/:guid`) in SPA-zavedna zaznava praznih pogledov; `admin` networkidle timeout kot owner = stran polla (artefakt merilnika); greatshot anon 401 = načrtovano stanje. Drugi tek z vsemi popravki: izid v `docs/PLAN.md`. |
| prod | **zamrznjen v1.39.0**; SPA na prod NI; preklop = `build:app` v `scripts/deploy_release.sh` (ownerjev dan); pred tem ultra pregled + 1–2 tedna soaka |

### Raziskovalne proge (vse mergane)
- Doc 22 dvojčki: r. 1 #913 (osebnost poti = časovna utež), r. 2 #914
  (camp-profile, peta plošča vlog), r. 3 #918 (generator
  `scripts/build_bot_twin_profiles.py` → `server/omnibot/twins/`, poročilo
  `docs/design/23`; kontrola s premešanimi sejami preživi ≈ 21 % — pragi iz
  kontrole). **Rezina 4 (harness bot proti človeku) rabi ownerjev deploy
  dvojčkov na puran + bot test.**
- Moments r. 2 #916: Lua v6.14 **deployan na puran** 5. 9.; migracija 082 na
  dev DA, na prod ob naslednjem release deployu; odprto: en večer
  `frame_health.log` brez novega `self` stroška; popravek korpusa
  `destroyed_count` (fantomska +1 na goldrush rundah pred v6.14) — owner.
- Doc 19 (per-user pogled): plan mode odprt in prekinjen, nič napisanega.
- Lokalni ET test strežnik (2.85, :27961): deploy Lua prek `sudo -n -u et tmux
  -S /home/et/.et-console-285.sock run-shell "cp /tmp/x.lua …"`, map load,
  `lua_status` SHA1 = `sha1sum`; po testu `scripts/local_et.sh -v 2.85.0 stop`.

## 2. Naslednji koraki (vrstni red, owner 6. 9.: ultra rezine → Astra)
1. ~~`docs/phase7-sweep`~~ = #921 mergan; ~~#915~~ mergan; #911 zaprt (dvojnik
   #919; razlike v BACKLOG); #912 ostane sestri; #882 (release 1.45.0) owner
   merga zadnjega → tag v1.45.0 = glava pregledov.
2. **Ultra pregled = 20 rezin, ne en PR.** Ultra sprejme ≤ 8 000 spremenjenih
   vrstic in ≤ 500 datotek na pregled (dokumentirano); koda od proda
   (v1.39.0) je 93 k vrstic. `scripts/review_slices.sh measure|cut --push|prs`
   seka veje `review-base/NN-<območje>` (= main z območjem vrnjenim na
   v1.39.0) in `review/NN-<območje>` (drevo = main, starš = baza; GitHub
   zavrne PR, katerega glava je prednik baze) in odpre draft PR-je (telesa v
   `docs/review/SLICES.md`, vodnik `docs/REVIEW_GUIDE.md`); **nikoli
   mergati**. ⛔ Ob vsakem premiku maina (#882!) `cut --push` znova. Owner
   požene `/code-review ultra <PR#>` (7. 9. opoldne) po vrsti: **#924** (01
   proximity+spiderweb+Lua) → **#925** (02 backend routerji) → **#926** (03 SPA
   lib); ostali #927–#943 po dnevih (odprti 6. 9. kot draft). ⛔ Stara baza `19c61847` je bila hash iz PRE-prepisne zgodovine
   (pravi #802 merge = `87a7063d`); veja izbrisana.
3. **Astra (Codex CLI, od 7. 9.)**: **predaja celotnega projekta = `docs/HANDOFF-astra.md` (§C delovni paket, §D ne delaj) + `docs/HANDOFF-astra-inventory.md`** (7. 9.); vstop = `AGENTS.md` (Codex ga naloži sam;
   preveri s `codex debug prompt-input "ping"`), kickoff
   `docs/prompts/astra_kickoff.md`, zanka `docs/process/MANDELBROT_RCA.md`,
   dnevnik `docs/AGENT_LOG.md`. Vrstni red (owner): triaža najdb ultra →
   odprte rezine (§2.5, §4) → watchdog r. 2 (r. 1 = `scripts/slomix_watchdog.py`
   + `deploy/systemd/etlegacy-watchdog.timer`, 6. 9.; r. 2 = SSH sonde na
   puran, `watchdog` ključ v `/api/diagnostics`, vrstica na About) → runtime
   v2 r. 1 (doc 21 §8) šele na ownerjev DA. Štiri proge 6. 9. popoldne: guid
   prefiks #945, diagnostics stanja #946, register datasetov #947, watchdog —
   podrobnosti v `docs/PLAN.md` »Proga: štiri točke do Astre«. Zunaj repa: `~/.codex/config.toml`, `~/.codex/AGENTS.md`,
   `~/.codex/rules/slomix-guard.rules`, `~/.codex/hooks.json` + hooka
   (`slomix-guard.py`: port `block-git-sweep`; surov stdin v
   `~/.codex/hooks/last_input.json` — obliko preveri po prvi seji).
4. Popravki iz pregleda → 1–2 tedna soaka na dev → pogovor o produkciji
   (preklop `build:app` v deploy skripti; migracija 082 na prod).
5. Vzporedno po ownerjevi izbiri: dvojčki r. 4 (rabi puran bot test), doc 19
   r. 1 (register datasetov + tipiziran `GET /api/datasets`), popravek korpusa
   `destroyed_count`, ~~proximity endpointi s sprejemom 8-znakovnega guida~~ = narejeno 6. 9. (resolver v `proximity_helpers.resolve_player_guid`, 17 handlerjev + AST varovalo). ~~availability r. 3~~ = narejena v #915.
6. **Preostalih 13 vrzeli, po izmerjenem trudu** (raziskave 6. 9.; podrobnosti
   in pasti so v komentarjih `tests/data/endpoint_gap.txt`):
   - `players/{}/card` (M) — arhetip + 90-dnevni form; ⚠️ njegovi percentili
     NISO percentili ET komponent (drug bazen, drugo okno — izmerjeno);
     dobesedni port FUT kartice bi trčil ob tipografski dizajn.
   - `rounds/{}/player/{}/details` (M) — objectives in sprees niso nikjer;
     ⚠️ `matches.js:970` bere polji, ki ju handler NE vrne (`combat.useful_kills`,
     `w.weapon_name`) — legacy modal že izpisuje `undefined`, ne prenesi napake.
   - `rounds/{}/awards` (S, blokirano na odločitvi o mestu — površine za
     posamezno rundo še ni; surov `value`, `session_awards_service` zna lepše).
   - `greatshot/{}/crossref` (S) — GET, auth+lastništvo, 23 analiziranih demotov.
   - `stats/player/{}/form` (S–M) — DPM/KD serija je že narisana iz
     `skill/…/form`; ta endpoint ima le datume, rounds/sejo, `avg_dpm`, `trend`.
   - `sessions/{}/graphs` (**L**) — osem osi `playstyle` + `dpm_timeline` ne
     obstajata nikjer; ni grafičnega primitiva (edini precedens `RetroViz.tsx`);
     ⚠️ šteje `round_number IN (1,2)`, Stats 2.0 pa `counts_toward_totals` —
     številke se NE bodo ujemale, panel mora povedati, katera vrata je uporabil.
   - ⛔⛔ `rounds/{}/vs-stats` — **NE migriraj**: handler nima `GROUP BY` in
     zavrže `subject_guid` (18 vrstic za 6 igralcev na rundi 11425). Popravi
     handler ali izbriši vrstico ob upokojitvi `matches.js`.
   - ⛔⛔ `greatshot/{}/highlights/render` — POST; renderer na tem stroju NI
     konfiguriran (ni ffmpeg, ni `GREATSHOT_RENDER_COMMAND`); `greatshot_renders`
     ima ENO vrstico ever, `failed`, ob 622 highlightih. Gumb bi vedno dal
     `queued → failed` — ownerjeva odločitev, ne samoumevna gradnja.
   - `uploads/{}/download` — **funkcionalno že pokrit** prek `download_url`
     (`UploadsPage.tsx:325`); vrstica ostane, ker literala v `src/app` ni.
     Res manjkata: gumb za prenos na kartici seznama in inline predvajalnik.
   - `/api/bets`, `/api/stats/sessions` — zapre ju šele upokojitev legacy JS.

## 3. Kako preveriti stanje (agent to lahko požene sam)
```bash
# ratcheti in guardi (Python), frontend testi, lint
venv/bin/python -m pytest tests/unit/test_parity_keymap.py tests/integration/test_endpoint_gap.py tests/integration/test_route_contract.py -q
(cd website/frontend && npm run typecheck && npx vitest run)
bash scripts/lint-js.sh
# živ dev strežnik + e2e (owner projekt NI admin — rig nima admin nivoja)
(cd website/frontend && npm run build:app)
nohup ./venv/bin/python -m uvicorn website.backend.main:app --host 0.0.0.0 --port 8056 > /tmp/uvicorn8056.log 2>&1 &
(cd website/frontend && SMOKE_BASE_URL=http://127.0.0.1:8056 npx playwright test --project=anon && SMOKE_BASE_URL=http://127.0.0.1:8056 npx playwright test --project=owner)
# paritetni prelet (manifest ~2 min, celoten ~25 min); rezultat <out>/results.json
AUDIT_BASE_URL=http://127.0.0.1:8056 node scripts/audit_website_browser.mjs --app --manifest --out /tmp/audit
AUDIT_BASE_URL=http://127.0.0.1:8056 node scripts/audit_website_browser.mjs --app --out /tmp/audit_full
```
Branje preleta: `deadState` = prazen pogled; `consoleErrors` s 401/404 preveri
proti namenu strani (greatshot anon 401 je stanje, ne napaka); `navigation
failed … Timeout` na `admin` je networkidle proti pollingu. Absent panel je
VELJAVEN render — prelet »renders without errors« ne ujame strani, ki vedno
pravi »ni podatkov« (zato je vzorčni guid v preletu polni, 32-znakovni).

## 4. Odprte ownerjeve odločitve
- ~~`docs/design` za ultra~~: podmnožica 00/05/06/09/12/17 + README commitana 6. 9.
- Po uvajanju Astre (O-3): rotacija DB gesla (194 vrstic v `~/.codex/rules/default.rules` ga nosi), čiščenje `default.rules` (`ssh`, `systemctl restart`), ali `.codex/rules`+`hooks.json` v javni repo.
- Watchdog oblika (O-2): samostojna skripta + systemd timer (priporočeno) ali oživitev `HealthMonitor`.
- Popravek korpusa `destroyed_count` — da/ne.
- Dvojčki: deploy `server/omnibot/twins/*` na puran + bot test (r. 4).
- Availability r. 3 (admin kontrole trga) — kdaj. Doc 19 — kdaj.

## 5. Sestrska seja
Dela v ločenem worktreeju `/home/samba/share/slomix-arena` (1v1 arena Lua,
veja `feat/lua-dots-arena`, pavzirana). Nikoli ne deli delovnega drevesa z
drugo sejo (worktree).
