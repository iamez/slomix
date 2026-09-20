# HANDOFF — Fable 5.1, 9. 9. 2026 (owner odsoten ~3 mesece)

Pisano ob koncu zadnje Fable seje pred ownerjevim dopustom (naročnina Claude poteče;
nadaljevanje ~december 2026). Vir resnice za načrt ostaja `docs/PLAN.md`, pozicije
`docs/BACKLOG.md` (»Trenutna pozicija« = zadnje stanje), stanje mreže
`docs/SPIDERWEB_STATUS.md`. Ta datoteka pove, KJE smo, KAJ je bilo narejeno in preverjeno,
KAJ čaka in v katerem vrstnem redu, ter katere pasti so stale največ. Prejšnje predaje:
`docs/HANDOFF-next.md` (6. 9.), `docs/HANDOFF-fable.md` (2. 9.), `docs/HANDOFF-astra.md` (7. 9., Astra/Codex).

⛔ Ta datoteka NI dovoljenje. Vnaprejšnji DA, ki ga je owner dal 9. 9. zvečer, je veljal
SAMO za sejo 9./10. 9. 2026 (merge PR-jev te seje prek vlaka, dev deploy). Ob vrnitvi
vprašaj znova za vsak PR, restart in deploy. Prod (`slomix-*` na VM) je zamrznjen na
**v1.39.0** (ownerjeva odločitev 28. 8.) — deploy na prod NI naloga.

---

## 0. Trda pravila (nespremenjena; podrobno `AGENTS.md`, `docs/CLAUDE.md`)

- Feature veja + PR ≤ 25 datotek; Conventional Commits; `git add` po imenih; brez skrivnosti/logov/backupov;
  `docs/research/` in `docs/design/` sta LOKALNA (nista v repu).
- **Nikoli merge brez ownerjevega DA za TA PR.** Merge prek `~/slomix-ops/cycle.sh <pr> <veja> "<naslov>" <telo.md>`
  (čaka CI, Codex niti = 0, zavrne vejo za mainom). Vlaki so v scratchpadu te seje (`train*.sh`) — vzorec:
  `run_one` = PATCH base=main → worktree → `git merge origin/main` → generirane datoteke regeneriraj
  (`docs/parity/datapoints.json`, `datapoints_unread_baseline.txt`, `docs/api/openapi.json`),
  **`docs/parity/datapoint_decisions.json` združi kot UNIJO** (theirs ga izgubi) → ledger test → push → cycle.sh.
- Restart/deploy le prek `scripts/dev_deploy.sh` (dev enoti `etlegacy-bot`/`etlegacy-web`, tečeta iz
  `/home/samba/share/slomix-dev-run`); pred buildom preveri `git status --short` v `slomix-fable`
  (neizsledena datoteka je 9. 9. tiho blokirala `checkout -B main` in vlak je deployal STAR bundle).
- Dokaz = runtime, ne testi: po deployu `/api/build` + nizi v serviranem bundlu + endpoint z znanimi vrednostmi.
- Codex (Codacy-podoben) pregleduje vsak PR: niti so praviloma upravičene; odgovori s hashem popravka in razreši nit.
  Niti P1 »`.toFixed` v pages/« → uporabi `decimals()`/`megabytes()`/`figure()` iz `components/ui.tsx`.

## 1. Kje smo (verificirano 9. 9. 2026 zvečer)

| stvar | stanje |
|---|---|
| main | glej `git log -1 origin/main`; dev `/api/build` = isti hash po zadnjem vlaku |
| dev spletna stran | `http://127.0.0.1:8000/app` (SPA), legacy `/`; `scripts/health_check.sh` |
| spider web | ZAKLJUČEN 9. 9.: SW-2 scena (#1005), SW-3 vidna linija kot oracle diagnostika (#1006), SW-4 sloj 4 po §8 (#1007); `docs/SPIDERWEB_STATUS.md` nosi tabelo §8.5 — **nič ne gre na stran** |
| merilnik podatkovnih točk (`docs/parity/datapoints.json` unread) | 583 (7. 9.) → 420 (po spider webu) → **238** po #1008–#1011 (dev `84dd5d46`, 9. 9. 17:12); ratchet: `tests/unit/test_datapoint_ledger.py`; instrument `scripts/datapoint_ledger.py` (scope po klicateljih; type-union literali niso klici; »dead: no caller« = vse vrstice nepokrite) |
| endpoint gap (H1) | **8** (`tests/data/endpoint_gap.txt`; PLAN kvota mora biti enaka — `test_plan_quotes_the_measured_gap`) |
| bot (dev) | `SUPASTATS_REACTIONS_ENABLED=false` (#1013): preverba Supovega lista + DM tečeta, reakcij v kanalu ni |
| izdaja | vlak release-please **#956 (1.46.0)** je odprt in NI mergan — owner odloči ob vrnitvi |
| Astra (Codex CLI) | njeni PR-ji **#1012, #979, #969, #966, #965, #964, #962** so odprti in NEDOTAKNJENI (ownerjevo navodilo 9. 9.: »razen Astrinega runtime-a«); `~/.codex` prav tako |
| review PR-ji #924–#943, #967 | »NEVER MERGE« — rezine za ultra pregled; `scripts/review_slices.sh cut --push` jih znova izreže iz maina |

## 2. Kaj je bilo narejeno 8.–9. 9. (vse mergano, dev deployan)

- **Dolg nazaj, merilnik podatkovnih točk** (owner 7. 9.: »capture everything«): R0 instrument (#992 scope po endpointu),
  R1 live/tonight, R2 profil, R3 drilldowni (rounds player details, match box score, matrika igralec×mapa, session graphs
  po gsid), R4 »fetched and dropped« (story, proximity, greatshot, uploads, overview, datasets, kill-impact), R5 DB brez
  porabnika (surrender/pavze/limiti v `/rounds`), R6 živi reducer (pozicije, zadnji uboji, mini zemljevid), kartica igralca
  + stenska ura (#1001), story obseg (#1002), #1003/#1004, nato #1008 (tier-4 odločitve), #1009 (proximity igralec),
  #1010 (proximity po datumu), #1011 (greatshot/Home/diagnostika). Vsak PR: fixture iz deva, page test, ledger v istem commitu.
- **Spider web do konca** (owner 9. 9. 00:10, avtonomno): platno → SVG s tokeni (`lib/spiderWeb.ts` + 48 prenesenih testov,
  `components/SpiderWebScene.tsx`), `?t=&pov=` v URL, POV po igralcu; `services/line_of_sight.py` (W6 tracer, 99,92 %),
  `edges[].line_of_sight` samo v world POV; `services/layer4_family.py` (§8: mediana znotraj runde, kronološki bloki
  70/30, bootstrap po blokih, max-T, manifest s hashem, prag 10 blokov/30 rund) + `scripts/spiderweb_layer4_family.py`
  (zbiralnik 901 rund = 95 min; nabor lokalno `docs/research/spiderweb_layer4_rows_2026-09-09.jsonl`).
  Rezultat: kontrola dpm prestane, šum pade; `moving_share` prestane aritmetiko, a je stran napada (deli izid);
  `push_into_wave_share` prestane, a je oracle ura (P6); ostalo pade. Manifest `docs/spiderweb/layer4_family_manifest.json`.
- **Bot**: supastats reakcije izklopljene s stikalom (#1013).
- Raziskave (lokalno, `docs/research/`): `DATAPOINT_AUDIT_2026-09-07.md`, `PROFILE_AIM_ADVANCED_RCA_2026-09-08.md`
  (poti A–F), `ENG_PCT_RESEARCH_2026-09-08.md` (§6: ENG% = DPM v preobleki brez support kanalov),
  `SPIDERWEB_LAYER4_FAMILY_2026-09-09.md`.

## 3. Kaj čaka — vrstni red za vrnitev (vsaka postavka = veja + PR ≤ 25 datotek + runtime dokaz)

### 3a. Ownerjeve odločitve (vprašaj z opcijami, ENO naenkrat)
1. **Izdaja 1.46.0** (#956): mergati ali ne; prod ostane v1.39.0, dokler owner ne reče drugače (nova stran soaka na devu).
2. **Profil `aim`/`advanced`** (17 vrstic ledgerja): pot B+E takoj (expression index na `LEFT(guid,8)` + `work_mem`),
   A = `CLUSTER proximity_shot_fired` kot ops eksperiment, C = proizvajalec cachea 077 — glej RCA doc; SPA teh sekcij namerno ne zahteva.
3. **ENG%** (gibhub.gg): graditi ali ne; če da, kanali ločeno, ne utež; doc §6 ima testirano napoved.
4. **Sloj 4 sledi**: recipient-clock verzija »push into wave« (§6.3; oracle verzija je pokazala −0,116 na potrditvi), in
   stran napada per runda (`lua_round_teams`/W5) za »moving«. Brez tega nič ne ships.
5. **Meshi**: 12 map izmerjenih, neobjavljenih (»premalo rund za bajte«); `etl_supply` nima BSP v etmain.
6. Doc 19 nivoji prikaza (kaj skriti), `.js.map` javno serviran, OG/meta + per-page title, rotacija sudo/DB gesla
   (geslo je bilo v chatu 2. 9.), `robots.txt`/sitemap.
7. Astrini odprti PR-ji (#1012 runtime events journal, #979 artifact preflight, #969 node pin, #966 review snapshots,
   #965/#962 watchdog, #964 ledger docs) — ownerjev pregled; ni jih pregledal Fable.

### 3b. Merilnik — kaj ostane nepokrito in kje (po #1011; poženi `python scripts/datapoint_ledger.py` in preštej)
- `players/{}/profile` aim/advanced (17) — odločitev 2; `availability/promotion-preferences` (7) — posnetek veje Z vrstico
  (`encryption_reason`) manjka; `storytelling/scopes` (8) — mrtev picker, hook ostane zaradi H1/inventarja (ownerjevo O9);
  `stats/last-session unassigned_players.time_dead_seconds_raw` (surova nepokrita vrednost, brez površine);
  `proximity/round/{}/timeline` ostanki; `competitive/*`; `greatshot metadata.rounds` podrobnosti; `diagnostics/*`.
- Pravilo: vrstica se zapre s KLICEM + IZRISOM + TESTOM; odločitev (`datapoint_decisions.json`) le z razlogom, ki ga
  recenzent lahko preveri (»iterated«, »alias«, »podvaja«); prefiks `<endpoint> <sub>.*` velja le za pod-objekt.

### 3c. Spletna stran — ostanek dolga nazaj (iz DATAPOINT_AUDIT B3)
P0: og/meta + document.title; hladna pečina proximity/skill (skeleton + timeout ali predizračun); iskalnik v navigaciji.
P1: mobile (tabela igralcev 1 400 px), filtri v URL (le 3 od 63 strani), pravi 404, route splitting (990 KB en chunk).
P2: a11y (div mreže brez ARIA), CSV izvoz, kontakt/zasebnost, `system`/`diag` pod About.
Dan preklopa nove strani: merilo v `docs/HANDOFF-astra.md` (zadnji razdelek).

### 3d. Ostalo iz BACKLOG/KNOWN_ISSUES (nespremenjeno)
Streli (`shot_fired`) so na puranu vklopljeni od 26. 8. (v6.11); lag populaciji A/B; `round_awards` podvojene vrstice;
watchdog; `full_selfkills` clamp; W4b navigacijski graf (raziskava); C1–C7 Lua zajemi (ownerjeva vrata).

## 4. Kako preveriti stanje (agent to lahko požene sam)
```bash
cd /home/samba/share/slomix-fable && git fetch -q origin && git checkout -q -B main origin/main
scripts/health_check.sh                                  # enote, /api/build, DB
python scripts/datapoint_ledger.py --check               # ledger je ažuren
python -m pytest tests/unit/test_datapoint_ledger.py tests/integration/test_endpoint_gap.py -q
curl -s http://127.0.0.1:8000/api/build                   # dev revizija
curl -s 'http://127.0.0.1:8000/api/replay/round/11344/web?t=120000' | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["line_of_sight"]["pairs_traced"], d["line_of_sight"]["exposure"])'
python scripts/spiderweb_layer4_family.py analyse --rows docs/research/spiderweb_layer4_rows_2026-09-09.jsonl --out-md /tmp/l4.md --out-manifest /tmp/l4.json   # reproducira tabelo §8 (lokalni nabor)
```
Bundle nosi novo sceno, če `grep -c "line of sight (oracle)" website/static/app/assets/app-*.js` v `slomix-dev-run` vrne 1.

## 5. Pasti, ki so 8.–9. 9. stale največ (vse tudi v Claude memory)
- **Vlak je zgradil in deployal STARO drevo** — neizsledena datoteka je blokirala checkout; log je pisal »build ok«.
  Dokaz »nizov v bundlu« ga je ujel. Preveri `git status --short` in `git log -1` v build drevesu pred buildom.
- **`pkill -f <vzorec>` ubije lastno lupino** (exit 144), če se vzorec pojavi še kje v ukazni vrstici; ubil je tudi sosednji vlak.
  Ubijaj po PID iz ločenega `ps`. Dva vlaka hkrati = tekma pri strogem rulesetu → vedno EN vlak z vsemi PR-ji.
- **`datapoint_decisions.json` ni generiran**: `--theirs` izgubi odločitve veje → unija. Prefiks `.*` velja za pod-objekt.
- **Stacked veje po squashu**: `git merge origin/main` konflikta na identični vsebini → koda `--ours`, generirano regeneriraj,
  `PLAN.md` vzemi z maina in vstavi le svojo vrstico (gap kvota!). »Obdrži obe strani« podvoji skupni rep (`}`) — typecheck
  kot LASTEN ukaz z lastnim exit statusom pred pushem, ne v subshellu z `echo`.
- Ledger laže v obe smeri: isto IME polja iz drugega endpointa v istem uvoznem zaprtju = lažna pokritost (avg_distance,
  created_at); endpoint brez klicatelja ne sme šteti kot »fully read«; type-union literali niso klici.
- Sloj 4: pri 4 potrditvenih blokih je bootstrap dal »ships« — prag 10 blokov/30 rund; simultani interval = unija s posamičnim.
- `known_enemy_count` skoraj nikoli ni 0 (obituary imenuje, ne postavi) → »slep« = brez POSTAVLJIVEGA prepričanja.
- Vzorčni testi na CI: platno/scene testi rabijo `{ timeout: 20000 }`; padli so na 5 s pri obremenjenem runnerju.

## 6. Ad hoc spremembe izven plana (ta seja)
- `/api/replay/round/{id}/web` limit 10 → 60/min (nudge gumbi); `services/line_of_sight.py` bere `ETMAIN_DIR`
  (privzeto `/home/samba/share/etmain`; brez drevesa = »no geometry«, ne 0).
- `WEAPON_NAMES` preseljen iz ProximityPlayerPage v `lib/weapons.ts`; `lib/utcStamp.ts`, `lib/roundTime.ts`,
  `ui.decimals()`, `ui.megabytes()` — skupni formatterji (pravilo brez `.toFixed` v pages/).
- `narrative.py top_trait` je null brez izmerjenih plošč; `movement.py` ohrani NULL; `proximity_journey.py` imenuje
  neuspeh objective poizvedbe in bere pravi tip smrti; `proximity_events` detajl nosi `round_duration_seconds`;
  `proximity_objectives` nošenja kronološko po `round_start_unix`.
