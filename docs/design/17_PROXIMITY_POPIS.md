# Proximity popis — da v novi strani NIČ ne izpade

**Datum:** 24. 8. 2026 · **Status:** lokalno, netrackano · **EN vir resnice za fazo 5**
**Metoda:** strojni ekstraktor (4 vzorci klicev: `scopedUrl('…')`, `` scopedUrl(`…`) ``,
`${API_BASE}/…`, dobesedni `/api/…`) čez `website/js/*.js` + `frontend/src/**` ×
živa openapi spec × korpus; **vsaka sporna vrstica ročno preverjena** (dve lažni
siroti ujeti in razrešeni: `trades/player-stats` → session-detail.js:2360,
`event/{id}` → notacija `:id`). Artefakta: `slomix-archive/design_research_2026-08-24/
proximity_inventory.{py,json}` (strojno berljiv popis s file:line dokazi za vseh 91 poti).

## 0. ⛔ Hitrostna omejitev, izmerjena 29. 8. 2026 — vpliva na ZASNOVO strani

`/api/proximity/players` je hrbtenica cele strani (5 klicev na izris v
`website/js/proximity.js`) in je **hudo občutljiv na širino obsega**:

| klic | hladno | toplo |
|---|---|---|
| `range_days=30` | **1,4 s** | 19 ms |
| `range_days=365` | **12,7 s** | 8 ms |
| `session_date=2026-08-27` | 38 ms | — |

Brat je isti endpoint izmeril na **18,8 s** hladno pri 30 dneh (in 496 ms
toplo); moja meritev je bila milejša, oblika pa ista. Razlika je skoraj
gotovo stanje predpomnilnika (aplikacijski `stats_cache`, 5 min TTL, plus PG
buffri) — **ne nasprotujoča si meritev, ampak dva odčitka iste krivulje**.

⛔ **Posledica za novo stran:** hrbtenice nikoli ne kliči neomejeno in šele
nato zoži. Prvi izris mora imeti obseg (session_date ali kratek
`range_days`), sicer je prvi vtis strani **več sekund praznega okvirja** — in
to je stanje, ki ga uporabnik vidi najpogosteje, ker je predpomnilnik ob
prvem obisku dneva vedno hladen.

⚠️ Za merjenje: **drugi klic ni meritev** — 8 ms pri 365 dneh je predpomnilnik,
ne poizvedba. Meri hladno, ali pa povej, da meriš toplo.

---

## 1. Sprava — kje lahko kaj izpade in kako je pokrito

**91 poti v živi spec** (67 proximity + 22 storytelling + 3 replay*, glej §5):

| Razred | Št. | Kaj je | Varovalo, da ne izpade |
|---|---|---|---|
| **A — legacy kaže** | 80 (62 prox + 18 story) | paneli današnje strani; loaderji dokumentirani v 07 §B.2/B.3 in v `proximity_inventory.json` (file:line) | `endpoint_gap.txt` (H1) + `inventory.json` (H2) + `data-parity` ključi; cilj = route iz 12 |
| **B — samo React** | 4 | `hit-regions/by-weapon`, `player/{guid}/profile`, `player/{guid}/radar`, `round/{id}/team-comparison` (žive MODERN route) | v 12 vodene kot »prekritje« (faza 5); dodati jih v `endpoint_gap` seznam kot obvezne |
| **C — sirota (backend zna, NIHČE ne kaže)** | 7 | spodaj, §2 | **ownerjeva odločitev O9** — nič ne ostane tiho |
| **D — spider-web** | `/api/replay/round/{id}/web` + POV | ✅ **MERGANO** (#800, main `a8bf2ca5`, 24. 8.) → dejansko razred A: `website/js/spider-web.js` ga kliče; vrstica `/api/replay/round` dodana v endpoint_gap (PR #802) | §4; follow-up PR prinese data-parity + barve + scenarijski test |

Presek proti 07: vse poti, omenjene v 07, so v popisu (edina razlika je notacijska).
Frontend površina proximity.js danes: **5.174 vrstic, 76 render/draw/load funkcij,
10 lestvičnih zavihkov** (`LB_TABS`, proximity.js:4352): Power Rating, Spawn Timing,
Crossfire, Trade Kills, Reactions, Survivors, Movement, Focus Fire, KROGT, Comp Skill.
Vseh 10 mora v novo lestvično sekcijo (12 → route `proximity`, vzorec Tabs+DT).

## 2. Razred C — 7 potrjenih sirot (vse žive, 200)

> ✅ **O9 ODLOČENO (owner, 24. 8.): po priporočilu** — pokaži `kill-matrix`,
> `win-contribution/formula`, `movement`; namerno opusti `dashboard` + 3× replay
> dvojnike. Stolpec »Priporočilo« spodaj je s tem postal sklep.

| Pot | Velikost | Kaj je (iz korpusa) | Priporočilo |
|---|---|---|---|
| `/api/proximity/dashboard` | **445 KB** | mega-agregat iz zgodnje dobe; vse njegove dele danes strežejo posamični endpointi | **namerno opusti** (zapiši v popis kot opuščeno) |
| `/api/replay/round/{id}/timeline` | 185 KB | replay časovnica (replay_router); frontend namesto tega kliče `/api/proximity/round/{id}/timeline` | opusti ALI konsolidiraj ob fazi 5 — dvojnik proximity poti |
| `/api/replay/round/{id}/positions` | 60 B | lege ob t (predhodnik spiderweb `/web`) | opusti — `/web` (sloj 1) je nadgradnja |
| `/api/replay/round/{id}/paths` | 84 B | poti v oknu | opusti — isto |
| `/api/storytelling/kill-matrix` | 4,5 KB | matrika kdo-koga (killer×victim) za sejo | **pokaži** — poceni, sodi na session-detail/story (vzorec DT) |
| `/api/storytelling/movement` | 2,2 KB | gibalni povzetek na igralca | pokaži na `story`/`profile` ali opusti — vsebinsko prekriva prox movement zavihek |
| `/api/storytelling/win-contribution/formula` | 1,9 KB | razlaga PWC formule (sorodnik že prikazane `/storytelling/formula`) | **pokaži** — transparentnost formul je hišna vrednota (#769) |

## 3. Kontrolni seznam za fazo 5 (prevzem = vse kljukice)

1. Vseh **80 A-poti** ima panel v novi strani (route po 12; podrobni paneli v 07
   §B.2 s file:line loaderji — kljuka se v `proximity_inventory.json`).
2. Vse **4 B-poti** prekrite (React strani preoblečene v besednjak 11).
3. Vseh **10 LB_TABS** poimensko prisotnih.
4. **O9 odločitve** izvršene (pokaži/opusti — nič neodločenega).
5. Spider-web route registrirana v `routes.ts` (+ hash oblika, če jo bot dobi).
6. Canvas pixel-diff 3 runde × 3 mape zelen (09); `objectives.ts`/`project.ts`
   vitest proti korpusu (faza 0).
7. Presek `proximity_inventory.json` proti implementiranim `data-parity` ključem
   = prazen (skript, ne roka).
8. Podatkovne opombe za UI: poti obstajajo za ~905 rund / ~11 map (»za to mapo
   poti ni« ≠ prazno platno); `shot_fired` ugasnjen od 11. 8. (kanal gunfire
   prazen za nove runde — EmptyState z razlogom).

## 4. Spider-web (razred D) — koordinacija

✅ #800 mergan (24. 8.); čiste funkcije IZVOŽENE (`project`, `beliefRegions`, `isTeamPov`, `horizonOf`, `edgeStyle`…) + `spider-web.d.ts` — prepis importa, ne lušči. Deep-scan čuvaj: koordinate nikjer razen v regijah prepričanj; `find_position_floor` jamči, da središče prihaja iz dogodka (test `test_the_position_never_comes_from_the_future`). Za novo stran velja: route + payload
polja (`players/edges/gaps/clock/capture_policy/information_state`) vsako na svoj
panel po prototipu `spiderweb.dc.html` in `SPIDERWEb_UI_DATA_CONTRACT`; moja
recenzija (24. 8.) je pogoj: pod `pov=team:*` **edges z resničnimi razdaljami do
nasprotnikov ne smejo v payload** — deep-scan test brez puščanja. Barve/besedišče
že usklajeni (allies `#8bb0d6`/axis `#d1857c`, »LOS available«; značka ure = razsodba backenda — glej popravek pogodbe §5, 25. 8.).

**✅ #804 mergan (`ad98d5eb`, 25. 8.) — prototip je IZRISAN V CELOTI.** Za prepis:
- **paritetni ključi (5)**: `spider-web.pov-toggle` · `web-canvas` · `timeline` ·
  `clock` · `snapshot-integrity` — vsi na obstoječih panelih.
- `THEME` razširjen: `floorLow`/`floorHigh` (talna rampa v paleti) + `mixHex`/
  `alphaHex` — oba padata na DVE mesti (`#8084b` canvas tiho zavrže).
- **Ura ima PET stanj**: VALIDATED · UNVALIDATED · **FAILED** · INCONSISTENT ·
  UNAVAILABLE. FAILED ni šibkejši UNVALIDATED — pristanki obstajajo in odmik
  OVRŽEJO. (Pogodba §5 govori o štirih — pri prepisu vzemi teh pet.)
- odsoten manifest → 24 zastavic privzeto `unknown` (prazna škatla je prej brala
  kot »ni česa poročati«); `pass_ratio` vedno z imenovalcem
  (`100 % (21/21 pristankov, 54 opazovanj)`); `overlap_conflicts` = ŠTEVILO
  IGRALCEV, ne prekrivajočih življenj.
- ⛔ **ODPRTA POSTAVKA A6**: manifest nosi samo `zastavica → stanje` — brez
  razporeda, intervala, pravila integracije in verzije (preverjeno v bazi).
  Panel vrzel IMENUJE; polnjenje sodi na stran zajema (tracker + parser), ne
  na frontend. V novi SPA ostane poimenovana vrzel, dokler zajem ne da podatkov.

⚠️ Past za gradbenega agenta v ločenem worktree-ju: po vsakem rebasu, ki
prinese nove npm odvisnosti, je `npm ci` OBVEZEN — zastarel `node_modules`
naredi typecheck lažno zelen/rdeč (bratova seja se je ujela dvakrat).

⚠️ **POV luknje v `/web` payloadu → PR #807** (25. 8.): pod `pov=team:*` so
uhajali `nearest_teammate_separation`, `clock` (nasprotnikova faza) IN
drugorendni kanal — `resolve_expiry` je bral nasprotnikovo uro, zato so
verjetja potekla točno ob nasprotnikovem valu (46/449 → 10/449). #807 vse
tri zapre; payload pogodba se spremeni:
- **ura pod team POV**: nasprotnikov vnos vsebuje **SAMO** `status:
  "unknown_to_this_pov"`, `reason` in `interval_ms` (§6.3 ga šteje za
  znanega) — ALLOWLIST, ne denylist: #807 je pokazal, da je denylist
  (»odstrani fazna polja«) prepustil celo validacijsko diagnostiko
  (landing_clusters, spawn_callbacks …) in s tem nasprotnikove valove. Značka = **WITHHELD**. ⭐ To NI šesto stanje kakovosti
  meritve, ampak DRUGA OS (meja pogleda) — prepis naj jo modelira ločeno od
  VALIDATED/UNVALIDATED/FAILED/INCONSISTENT/UNAVAILABLE, sicer switch čez
  kakovostna stanja WITHHELD napačno prebere.
- `velocity_max_dt_ms` ožičen (router param; privzeto interval manifesta × 2;
  brez manifesta BREZ meje — objavljeno v payloadu, null = brez meje).
- separation filtriran po `withheld_by_pov`.
- rekurzivni deep-scan test (`_mentions_of`: zadržan guid kot ključ ALI
  vrednost kjerkoli razen withheld_by_pov/information_state) — nova stran ga
  podeduje kot pogodbo; + mutacijsko dokazana trditev na ravni payloada.
- vstop: replay stran linka spider-web prek `getRouteHash` (prej brez poti).
- ⭐ po Codexu na #807 (`ac36f347`): neznana ekipa (`pov=team:NOBODY`,
  preimenovana stran, tipkarska) je prej padla ODPRTO v oracle — zdaj
  zadrži VSE (0 igralcev, 6 zadržanih, obe uri unknown_to_this_pov). Prepis
  mora podedovati fail-closed vejo. ⚠️ `state.tMs` je modulski in je
  preživel menjavo runde — React stran naj čas veže na rundo, `pov` pa je
  nastavitev pogleda in preživi. ⚠️ past za teste: legacy `fetchJSON` ima
  modulski predpomnilnik — štetje fetchov ne dokazuje ničesar; trdi na
  IZRISU.

## 5. ⚠️ Zadržek posnetka: dev backend teče od 19. 8.

`etlegacy-web` je bil nazadnje zagnan **19. 8. 00:47** — živa spec in korpus torej
NE vsebujeta endpointov, merganih po tem (`/api/replay/round/{id}/web` iz #792,
sloji 2–3 polja iz #795/#796/#799 so na main, a ne v tekočem procesu; delovno
drevo te seje je na starejši veji in jih tudi nima — `round_web_service.py`
obstaja na `origin/main`). **Po naslednjem restartu servisa** (ownerjeva domena)
je treba openapi posnetek + korpus za družino replay/spiderweb obnoviti —
ena vrstica v `record_api_corpus` postopku (14).
