# HANDOFF — 2026-09-06 (Fable 5.1 → naslednji agent)

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

## 2. Naslednji koraki (vrstni red, owner 6. 9.: dolg → faza 7 → pregledni PR)
1. **Ta veja (`docs/phase7-sweep`) → PR → ownerjev merge.**
2. **Pregledni PR za ultra**: ultra pregleduje PR, ne repozitorija → odpri PR z
   bazo `19c61847` (merge commit #802 = začetek nove strani) in glavo `main`;
   **nikoli mergati**. Prej ownerjeva odločitev o `docs/design` (commit
   podmnožice 00/05/06/09/12/17 ali lokalni `/code-review`). Ultra sproži
   OWNER (`/code-review ultra <PR#>`); agent ga ne more.
3. Popravki iz pregleda → 1–2 tedna soaka na dev → pogovor o produkciji
   (preklop `build:app` v deploy skripti; migracija 082 na prod).
4. Vzporedno po ownerjevi izbiri: dvojčki r. 4 (rabi puran bot test), doc 19
   r. 1 (register datasetov + tipiziran `GET /api/datasets`), popravek korpusa
   `destroyed_count`, proximity endpointi s sprejemom 8-znakovnega guida (10
   endpointov), availability r. 3 (admin kontrole trga).

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
- `docs/design` za ultra: commit podmnožice ali lokalni pregled.
- Popravek korpusa `destroyed_count` — da/ne.
- Dvojčki: deploy `server/omnibot/twins/*` na puran + bot test (r. 4).
- Availability r. 3 (admin kontrole trga) — kdaj. Doc 19 — kdaj.

## 5. Sestrska seja
Dela v ločenem worktreeju `/home/samba/share/slomix-arena` (1v1 arena Lua,
veja `feat/lua-dots-arena`, pavzirana). Nikoli ne deli delovnega drevesa z
drugo sejo (worktree).
