# HANDOFF — Fable 5.1 in Opus 5, 9.–10. 9. 2026 (owner odsoten ~3 mesece)

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

## 1. Kje smo (verificirano 10. 9. 2026 zjutraj)

| stvar | stanje |
|---|---|
| main | glej `git log -1 origin/main`; dev `/api/build` = isti hash po zadnjem vlaku |
| dev spletna stran | `http://127.0.0.1:8000/app` (SPA), legacy `/`; `scripts/health_check.sh` |
| spider web | ZAKLJUČEN 9. 9.: SW-2 scena (#1005), SW-3 vidna linija kot oracle diagnostika (#1006), SW-4 sloj 4 po §8 (#1007); `docs/SPIDERWEB_STATUS.md` nosi tabelo §8.5 — **nič ne gre na stran** |
| merilnik podatkovnih točk (`docs/parity/datapoints.json` unread) | 583 (7. 9.) → 420 (po spider webu) → 238 (#1008–#1011) → **92 na mainu 10. 9.**, in **79** ko se #1028 merga; ratchet: `tests/unit/test_datapoint_ledger.py`; instrument `scripts/datapoint_ledger.py` (scope po klicateljih; type-union literali niso klici; »dead: no caller« = vse vrstice nepokrite). Preostanek je opisan v §3b. |
| endpoint gap (H1) | **8** (`tests/data/endpoint_gap.txt`; PLAN kvota mora biti enaka — `test_plan_quotes_the_measured_gap`) |
| bot (dev) | `SUPASTATS_REACTIONS_ENABLED=false` (#1013): preverba Supovega lista + DM tečeta, reakcij v kanalu ni |
| izdaja | vlak release-please **#956 (1.46.0)** je odprt in NI mergan — owner odloči ob vrnitvi |
| Astra (Codex CLI) | njeni PR-ji **#1012, #979, #969, #966, #965, #964, #962** so odprti in NEDOTAKNJENI (ownerjevo navodilo 9. 9.: »razen Astrinega runtime-a«); `~/.codex` prav tako |
| review PR-ji #924–#943, #967 | »NEVER MERGE« — rezine za ultra pregled; `scripts/review_slices.sh cut --push` jih znova izreže iz maina |
| nova stran, dolg nazaj (pregled B3) | **P0 zaprt**: og/meta + `document.title` (#1017), `robots.txt`, iskalnik v navigaciji (#1021), `Pending` šteje sekunde in pove, zakaj je prva poizvedba počasna (#1019). **P1 zaprt razen filtrov v URL**: route splitting 1 104 → 205 KB (#1018), lepljiv prvi stolpec (#1020), pravi 404 (#1021). **P2 v teku**: `SectionHead` = `<h2>` (#1022), tabele dobijo ARIA vloge (#1029). |
| prijava | `/auth/login?next=` vrne obiskovalca na isto `/app` stran (#1023); sprejme le pot pod `/app`, sicer stara privzeta pot |

## 2. Kaj je bilo narejeno 8.–10. 9. (vse mergano, dev deployan)

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

- **10. 9. (Opus 5 nadaljuje isto progo).** Dolg nazaj s pregleda B3 in merilnik naprej:
  - **#1017** glava SPA (description, og:*, twitter:card, theme-color), naslov zavihka na ruto (`lib/pageTitle.ts`), `/robots.txt`.
  - **#1018** route-level code splitting: vstopni chunk **1 104 KB → 205 KB**, 44 chunkov, vsaka stran svoj.
  - **#1019** `Pending` po 3 s šteje sekunde, po 15 s pove, da prva poizvedba okna računa iz tabel (~20 s) in da so naslednje hipne.
  - **#1020** široka tabela pripne prvi stolpec (telefon ve, čigava je vrstica pri stolpcu 18).
  - **#1021** iskalnik igralcev v glavi (ista komponenta kot Home; Enter vzame prvi zadetek) + prava stran **404** (prej »phase 0 · not built yet«).
  - **#1022** `SectionHead` je `<h2>` — oris strani ni več en sam h1.
  - **#1023** `Connect ID` se vrne na `/app` stran, s katere je šel (`?next=`, sprejme le pot pod `/app`).
  - **#1024/#1025/#1026/#1028** merilnik, svežnji H–K: profil (zastava, discord, twitch, ura šprinta, delitev zadetkov po orožju, izhodiščni DPM), retro-viz (asisti, samomori, xp), proximity obseg, »kdaj je bila ocena narejena« in ocena tiste noči, uteži moverjev, aktivni dnevi sezone, ura strežnika in vzorčevalnikov, kdo je v voice, razredi v smrtnih conah, orožja na linijah ubojev, obe strani celice hotzone, viri zajema.
  - **#1029** tabele dobijo vloge (`table`/`row`/`columnheader`/`cell`); `aria-sort` gre z gumba na glavo stolpca.
  - Popravki, ki niso feature: `test_layer4_family` je bil **neponovljiv** (`hash()` na nizih je randomiziran po procesu → pade ~1 od 10 tekov na CI; dokazano pri `PYTHONHASHSEED=43`, popravljeno s `zlib.crc32`); test »lives cutoff« odmontira vsako drevo, ker so štiri žive strani presegle 40 s na CI.

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

### 3b. Merilnik — kaj ostane nepokrito (92 vrstic na mainu 10. 9., 79 po #1028)
Skupine, po velikosti:
- `players/{}/profile` **aim/advanced (10 vrstic)** — odločitev 2; SPA teh sekcij namerno ne zahteva (8–46 s hladno).
  Odločeno v `datapoint_decisions.json`, ne pozabljeno.
- `availability/promotion-preferences` (7) — telegram/signal/šifriranje/tihe ure; owner tier 4 (2 uporabnika), odločeno.
- `storytelling/scopes` (8) — mrtev picker; hook ostane zaradi H1/inventarja (ownerjev O9).
- proximity ostanek: `competitive/*`, `escort-credits`, `objective-focus`, `revives`, `spawn-timing`,
  `vehicle-progress`, `aim-lock`. ⚠️ **NISO sirote** — to sem najprej narobe sklepal. Klicani so prek GENERIČNIH
  hookov (`useProxInstrument`, `useCompetitive`, `useIntel`), ki dobijo pot kot argument v enovrstični arrow
  funkciji, zato jih iskanje »endpoint v telesu hooka« ne najde. Vsak ima svojo stran (Instruments, Competitive,
  ObjectiveIntel); nebrana so posamezna POLJA in se zaprejo z izrisom, kot vsi prejšnji svežnji — sveženj L
  (#1033) je zaprl 15 od njih.
- posamezniki: `player/{player_name}/matches` (legacy pot), `uploads/resumable/{}/finalize`, `stats/session/{}/detail
  team_matrix.rounds_detail`, `diagnostics database.tests`, `status service`, `hall-of-fame` ostanki.
- Pravilo (nespremenjeno): vrstica se zapre s KLICEM + IZRISOM + TESTOM; odločitev le z razlogom, ki ga recenzent
  lahko preveri (»iterated«, »alias«, »duplicate«, »tier 4«); prefiks `<endpoint> <sub>.*` velja le za pod-objekt.
  ⚠️ Dvakrat v tej seji je bila »nova vrstica« v resnici **ista meritev pod drugim imenom** (dodge reaction na radarju
  = `avg_dodge_ms` iz movementa; `category_weights` = `categories[].weight_in_overall`). Preveri IZVOR, ne imena.

### 3c. Spletna stran — kaj od dolga nazaj še ostane (pregled B3)
Zaprto 9.–10. 9.: og/meta + naslov zavihka, `robots.txt`, iskalnik v navigaciji, hladna pečina (pošten napis, ne
predizračun — glej odločitev 2), mobile prvi stolpec, pravi 404, route splitting, `SectionHead` = h2, ARIA vloge tabel.
Ostane:
- **P1 filtri v URL**: samo `RecordBook`, `Rivalries` in `WrappedPage` držijo stanje v naslovu; ostalih ~60 strani ne
  (izbrani stat na lestvici, obdobje orožij, datum/mapa/runda proximity, zavihki sej). Deljiv pogled = ena poteza za
  vsako stran: `useSearchParams` namesto `useState`, privzetek ostane privzetek (brez parametra v naslovu).
- **P2**: CSV/JSON izvoz; kontakt in zasebnost v nogi; `system`/`diag` pod About; izmerjen kontrast
  `--color-text-500/600`; fokusni obroč in past tipkovnice (rabi Playwright, ownerjev OK za Chromium).
- **Odprto vprašanje brez odgovora**: prvi obisk hladnega cache okna še vedno plača 6–26 s na proximity/skill.
  #1019 to zdaj POVE, ne pospeši. Pospešek je odločitev 2 (poti B+E takoj, A kot ops poskus, C proizvajalec cachea).

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

### 5b. Pasti, ki so stale 10. 9.
- ⛔⛔ **`hash()` na nizih ni seme.** `random.Random(hash((a, b)))` je bral po procesu randomiziran hash: isti commit
  je lokalno prestal in na CI padel (~1 tek od 10). Dokaz je bil `PYTHONHASHSEED=43`, ne ugibanje. Če test rabi
  ponovljivo naključje, uporabi `zlib.crc32` ali fiksno celo število.
- ⛔ **ARIA vloga na kontroli ji vzame njeno vlogo.** `role="columnheader"` na `<button>` je gumb prenehal biti gumb;
  trije obstoječi testi so to ujeli takoj. Vloga glave stolpca OVIJE kontrolo.
- ⛔ **Vlak obstane, dokler niti niso RAZREŠENE, ne popravljene.** `cycle.sh` šteje neresolvane niti; po popravku jih
  je treba zapreti (`resolveReviewThread`), sicer PR čaka v nedogled.
- ⛔ **»Nobena stran ga ne kliče« je bila napačna meritev.** Iskal sem endpoint v telesu hooka; devet proximity
  poti je klicanih prek generičnih hookov, ki pot dobijo kot ARGUMENT (`useProxInstrument('/api/...', d)`), in
  enovrstična arrow funkcija ni imela telesa, ki bi ga regex našel. Meri po IMENU hooka in njegovih klicateljih,
  ali pa preprosto grepaj pot čez `lib/` — in preveri, preden zapišeš »sirota« v predajo.
- ⛔ **Odstranitev enega izrisa lahko odpre DVE vrstici ledgerja**: skener veže na ime polja, zato je `total_samples`
  v eni vrstici pokrival dva endpointa (escort-credits in objective-focus).
- ⛔ **Isti CI job pade zaradi apt zrcala** (`luac5.4: command not found`, exit 127) — to ni naša koda; `gh run rerun`.
- ⚠️ Štiri žive strani v enem testu presežejo 40 s na CI; odmontiraj vsako drevo, preden zgradiš naslednje.

## 6. Ad hoc spremembe izven plana (ta seja)
- `/api/replay/round/{id}/web` limit 10 → 60/min (nudge gumbi); `services/line_of_sight.py` bere `ETMAIN_DIR`
  (privzeto `/home/samba/share/etmain`; brez drevesa = »no geometry«, ne 0).
- `WEAPON_NAMES` preseljen iz ProximityPlayerPage v `lib/weapons.ts`; `lib/utcStamp.ts`, `lib/roundTime.ts`,
  `ui.decimals()`, `ui.megabytes()` — skupni formatterji (pravilo brez `.toFixed` v pages/).
- `narrative.py top_trait` je null brez izmerjenih plošč; `movement.py` ohrani NULL; `proximity_journey.py` imenuje
  neuspeh objective poizvedbe in bere pravi tip smrti; `proximity_events` detajl nosi `round_duration_seconds`;
  `proximity_objectives` nošenja kronološko po `round_start_unix`.

### 6b. Ad hoc 10. 9.
- `PlayerSearch` je nova skupna komponenta (Home + glava + 404); Home je izgubil svojo kopijo iskalnika.
- `NotFound` je prava stran: imenuje pot, ponudi domov/seje/lestvice in iskalnik.
- `auth.py` ima `_safe_next_path()` — dovoli LE isto-izvorno pot pod `/app` (brez `//`, `\\`, sheme, gostitelja,
  krmilnih znakov, ≤ 512 znakov). Testi pokrivajo 13 primerov sprejmi/zavrni in cel obhod prijave.
- `docs/parity/datapoint_decisions.json` je zrasel na ~66 vnosov; vsak nosi razlog, ki ga je mogoče preveriti.
- Nога strani zdaj kaže povezavo na `/welcome` (prej ni bila dosegljiva od nikoder).

---

**Zadnja meritev te seje:** main `7850dbc9` + PR-ji #1021, #1025, #1026, #1028, #1029 v vlaku 43;
merilnik 92 → 79; dev se po vsakem vlaku zgradi in deploya prek `scripts/dev_deploy.sh`.
Prod ostaja **v1.39.0** in ni bil dotaknjen.
