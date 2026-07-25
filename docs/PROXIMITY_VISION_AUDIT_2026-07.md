# Proximity Vision Audit — kaj zajemamo vs. kaj vizija zahteva

**Status:** analiza + PREDLOG. Nič implementirano brez ownerjevega GO.
**Datum:** 2026-07-25 · **Spremljajoča dokumenta:** `AUDIT_DATA_CORRECTNESS_2026-07-25.md`, `DESIGN_SKILL_PASSPORT_2026-07.md`

---

## 1. Vizija (ownerjeve besede, 2026-07-25)

> "Zamisli si server brez statistike — nič se ne traka, ko fantje odigrajo, ostane le v spominu igralcev. S proximity bi rad dosegel, da **se za vsak moment sproži telemetrija/timing, da se vidi kje je vsak igralec in kaj dela v tem momentu**. ET:L stopwatch je zakomplicirana igra in **vsaka mapa ima drugačen objective** — naš sistem mora vedeti za vsak gib igralca in **koliko je bil ta gib/odločitev dober/dobra**. Za objective gledava vsak kill…"

Vizijo razbijem na tri zahteve:

| # | Zahteva | Kratko |
|---|---------|--------|
| **V1** | Za vsak moment vemo, kje je vsak igralec in kaj dela | *popolna telemetrija* |
| **V2** | Sistem pozna objective vsake mape in njene faze | *razumevanje igre* |
| **V3** | Za vsak gib/odločitev vemo, koliko je bila dobra | *ocena odločitev* |

---

## 2. Verdikt po zahtevah

### V1 — popolna telemetrija: **✅ DOSEŽENO za pozicijo/stanje** (ena vrzel: zvezna smer pogleda)

Lua `proximity_tracker.lua` vzorči **vsakih 200 ms** in za vsak vzorec zapiše:

```
time, x, y, z, health, speed, weapon, stance, sprint, event
```

To ni "približno kje je igralec" — to je **kje je, s koliko življenja, s katerim orožjem, v kateri drži, ali sprinta in kaj se mu je ravno zgodilo.**

**Ena prava vrzel (popravljeno po reviewu): smer pogleda.** Pot NE vsebuje viewangles, zato iz nje ni mogoče ločiti igralca, ki pravilno drži choke, od tistega, ki na istem mestu gleda stran. Za odločitveno oceno (DQL) je to pomembna razlika. Viewangles obstajajo, a le **dogodkovno**: `SHOT_FIRED` (ob strelu) in `AIM_LOCK` (ko je križec na sovražniku) — torej vemo, kam je gledal, kadar je streljal ali koga sledil, ne pa med zatišjem.

V1 je torej **dosežen za pozicijo/stanje, ne pa za neprekinjeno orientacijo.** Če se izkaže, da DQL rabi zvezno smer pogleda, je to edina postavka v tem dokumentu, ki bi zahtevala Lua spremembo (dodatno polje v vzorcu poti).

V bazi (`player_track.path`, JSONB): **57.311 poti, 223 MB.** Ena runda etl_adlernest R2 (272 s) da 50 poti in v isti datoteki še:

| Sekcija | Vrstic v tej rundi | Kaj je |
|---------|-------------------|--------|
| SHOT_FIRED | 1491 | vsak posamezen strel z origin+viewangles |
| TEAM_COHESION | 879 | razpršenost ekipe vsakih 500 ms |
| HIT_REGIONS | 385 | kam je zadel (glava/telo/noge) |
| ENGAGEMENTS / REACTION_METRICS | 111 / 111 | vsak spopad + reakcijski časi |
| AIM_LOCK | 94 | vsako sledenje križca po sovražniku |
| TEAM_PUSHES | 81 | koordinirani pritiski |
| SPAWN_TIMING / KILL_OUTCOME / COMBAT_POSITIONS | 37 / 37 / 37 | vsak kill s spawn kontekstom in pozicijo |
| CROSSFIRE_OPPORTUNITIES | 13 | geometrija križnega ognja |
| OBJECTIVE_RUNS / CONSTRUCTION / REVIVES / TRADE_KILLS / CARRIER | 4 / 5 / 8 / 5 / 1 | objective delo |

**22 sekcij, ~3.400 zapisov na eno 4-minutno rundo.** Zajem NI vrzel.

### V2 — razumevanje objectivov: **⚠️ POLOVIČNO**

`objective_zones.json`: **14 map, 72 objektivov**, tipi `objective` / `command_post` / `escort` — vsak s koordinato in radijem. Uporablja se za KIS `is_objective_area` (v4).

**Vrzeli:**

1. **Manjkajoča mapa, ki jo največ igramo po te_escape2:** `et_brewdog` (45 rund v zadnjih sejah) **nima definicij**. Vsak kill na brewdogu tako šteje kot "ne pri objectivu", kar sistematsko podceni delo na tej mapi.
2. **Zone so točke z radijem, ne faze.** Sistem ve *"tu je dinamit"*, ne ve pa *"ta objective je trenutno aktiven / že padel / še ni dosegljiv"*. V stopwatchu je isti prostor v 2. minuti nepomemben in v 6. odločilen — te razlike ne poznamo.
3. **Ni pojma napadalec/branilec po fazi.** Imamo `defender_team` na rundi, nimamo pa "kaj je bil cilj v tem trenutku".

### V3 — ocena odločitev: **❌ NAJVEČJA VRZEL — a bližje, kot izgleda**

Trenutno ocenjujemo **izide** (kill je vreden X), skoraj nič pa **odločitev** (ali je bilo pametno tja iti).

Izjema, ki dokazuje, da je izvedljivo: `OBJECTIVE_RUNS` že **zdaj** zapisuje za vsako inženirsko akcijo:

```
action_type=dynamite_plant, approach_time_ms=29800, approach_distance=6627,
beeline_distance=2696, path_efficiency=0.407, enemies_nearby=2,
nearby_teammates=0, run_type=contested_solo, self_kills=0, team_kills=0
```

Kontekstna polja (`enemies_nearby`, `nearby_teammates`, `run_type`, `escort_guids`) **so** pravi gradniki ocene odločitve. Toda dve stvari, ki sta se pokazali šele ob ownerjevem ugovoru (2026-07-25) in ju je treba povedati naravnost:

**(a) To NI "inženirska" tabela, ki bi jo bilo treba le posplošiti — je tabela, ki pokriva napačno manjšino.**
`proximity_objective_run` pozna samo štiri akcije, vse inženirske: `dynamite_plant` (1.058), `objective_destroyed` (656), `construction_complete` (643), `dynamite_defuse` (152). Nošenje dokumentov/zastave je v ločeni tabeli `proximity_carrier_event`, kjer so nosilci **69,4 % MEDIC**, 18,6 % ENGINEER, 9,6 % COVERTOPS. In ravno ta tabela nima nobenega konteksta:

| Polje | objective_run (inženir) | carrier_event (69 % medici) |
|---|---|---|
| `enemies_nearby` / `nearby_teammates` | ✅ | ❌ |
| `run_type`, `escort_guids` | ✅ | ❌ |
| geometrija (distance/beeline/efficiency) | ✅ | ✅ — **samo to** |

Bogat kontekst torej pokriva manjšinski del objective dela. Prva naloga ni "posplošiti z inženirja", ampak **carrier_event izenačiti z objective_run**.

**(b) `path_efficiency` ni ocena odločitve — je merilo ravnosti in kaže v napačno smer.** Formula je `beeline / dejanska_pot` (Lua vrstica 2862). Izmerjeno na naši bazi:

| run_type | n | povp. path_efficiency |
|---|---|---|
| contested_solo (najtežje) | 471 | **0,585 — najvišja** |
| unopposed | 1.106 | 0,554 |
| assisted | 583 | 0,526 |
| team_effort (usklajeno) | 242 | **0,468 — skoraj najnižja** |

Učinkovitost tudi **raste** s številom sovražnikov v bližini (0 → 0,532; 1 → 0,556; 2+ → 0,571), pri nosilcih pa je **ubit (0,501) nad secural (0,489)**. Standardni odkloni (0,19–0,23) presegajo razlike med skupinami. Metrika nagrajuje tek naravnost skozi nevarnost in kaznuje kritje, čakanje na soigralce in flank — v ET-ju najboljša pot pogosto **ni** najbolj ravna.

**(c) Neuspehov sploh ne beležimo:** `approach_killed` = 0 vrstic, `run_type='denied'` = 0, `killer_guid` prazen pri vseh 2.509 zapisih. Vidimo samo uspele akcije, torej iz te tabele ni mogoče primerjati dobre odločitve s slabo (survivorship bias).

Vhodni podatki za pravo oceno **obstajajo** (`player_track.path` z zdravjem/hitrostjo/držo, pozicije vseh igralcev v vsakem trenutku, kill heatmap); **faza runde pa NE** — ločena vrzel pri DQL-3.

---

## 2a. Revizija obstoječih metrik — kateri številkam sploh smemo verjeti

Ownerjev ugovor na `path_efficiency` ("nima duše, samo matematika") je sprožil sistematski test **vseh** proximity metrik po istem merilu: *ali metrika kaže v smer, ki jo trdi, glede na težavnost oz. uspeh — in ali sploh loči skupine?* Vse spodaj je izmerjeno na naši produkcijski bazi.

| Metrika | Test | Rezultat | Kje se uporablja |
|---------|------|----------|------------------|
| `spawn_timing_score` | vs dejansko odvzet čas | ✅ **ZDRAVA** — monotono 3,2 → 9,2 → 15,5 → 21,2 s | KIS spawn multiplier, spawn leaderboard |
| `push_quality` | vs uboji v 5 s oknu | 🔴 **OBRNJENA** — <0,5 → 0,90 killov; 0,9–1,2 → 0,60; 1,2+ → 0,43 | **KIS push multiplier (prag 0,9)** |
| `dodge_reaction_ms` | vs pobeg iz spopada | 🔴 **OBRNJENA** — <300 ms → 22 % pobegov; 1000+ ms → 65,7 % | **prox_score "awareness" (nižje = bolje)** |
| `path_efficiency` | vs težavnost in izid | 🔴 **OBRNJENA** — glej §V3 | prikaz objective runs |
| `efficiency` (carrier) | vs izid nošenja | 🔴 **OBRNJENA** — ubit 0,501 > secural 0,489 > izgubil 0,465 | prikaz carrier eventov |
| `angular_separation` | vs izvedba crossfira | 🟠 **BREZ SIGNALA** — 30–60°/60–90°/90+ vsi ~25–26 %; loči le <30° (58,7 %), kar pa ni pravi crossfire | **crossfire leaderboard rangira po njej** |
| `return_fire_ms` | vs pobeg iz spopada | 🟠 **BREZ SIGNALA** — 40,1 / 34,9 / 36,8 / 41,5 % (U-oblika) | **prox_score "mechanical" os** |
| `gravity` | ali meri pozornost ali volumen | 🟠 **ZAMEŠANA** — r=0,897 s št. spopadov, r=0,724 s smrtmi | predlagan vhod za LURK os |
| cohesion `dispersion` | "zbita ekipa = bolje" | 🟠 **NEPODPRTO** — surova razlika (47,8 % vs 55,9 %) je večinoma napadalec/branilec; znotraj vlog ostane le +2 do +5 t. v korist **razpršenih** | cohesion panel, teamplay |

**Od devetih testiranih metrik je nesporno zdrava ena.**

### Dva ŽIVA scoring defekta (ne le prikaz)

1. **KIS push multiplier stoji na obrnjeni metriki.** `PUSH_QUALITY_THRESHOLD = 0,9` zajame ravno pas z **najmanj** uboji. Vzrok je v formuli: `push_quality = poravnanost × (hitrost/300)` je največja, ko cela ekipa sprinta v isto smer — kar se zgodi ob **odsotnosti stika** (tek iz spawna). Ob dejanskem stiku se hitrost zmanjša in ekipa razprši → "nizka kvaliteta". KIS torej ojača uboje med nemotenim sprintom. (Formula je tudi neomejena: max 2,16, 4.124 od 84.309 vrstic nad 1,0.)

2. **prox_score "awareness" os se sama s sabo bori.** Sestavljena je iz `escape_rate` (pravilna smer) in `100 − dodge_ms/50` (obrnjena smer) — polovica osi vleče proti drugi. "mechanical" os stoji na `return_fire_ms`, ki nima signala.

### Poštena omejitev teh testov

To so **korelacijski** testi in nekateri imajo verjetne zmede: pri `dodge_reaction` je prisotna selekcija (kdor umre hitro, sploh ne utegne "dodgeati"), pri `push_quality` se nemoteni sprinti dogajajo zgodaj v rundi. Sklep pa od mehanizma ni odvisen: **metrika, ki se uporablja kot "več = bolje" in empirično kaže v drugo smer, je pokvarjena v tej uporabi**, ne glede na vzrok.

---

## 3. Predlog: Decision Quality Layer (DQL)

Trije gradniki, vsak samostojno uporaben. **DQL-1 in DQL-2 ne zahtevata sprememb Lua** — računata se iz obstoječih poti. **DQL-3 je izjema** in rabi dodaten vir faznega stanja (glej tam).

### DQL-1 — Kontekst giba (temelj)

Za vsak 200 ms vzorec izračunamo (offline, ob importu):
- razdalja do najbližjega objectiva in ali se mu **približuje ali oddaljuje**;
- št. soigralcev/sovražnikov v radiju (že imamo pozicije vseh);
- ali je sam (`isolation`) — ownerjeva lurk os;
- ali je v znanem chokepointu (izpeljemo iz movement heatmap gostote);
- **izpostavljenost v tistem trenutku** — ali je bil v vidnem polju/dosegu znanih pozicij nasprotnikov, in kako smrtonosna je bila ta celica po zgodovinskem kill heatmapu.

**Zadnja postavka je odgovor na `path_efficiency`.** Namesto *"kako ravno je šel"* merimo *"koliko nevarnosti je pot vsebovala glede na to, kje so bili takrat nasprotniki"*. Ista pot je lahko odlična ali samomorilska, odvisno od trenutka — ravnost tega ne ve, izpostavljenost pa. Daljša pot skozi varno območje se tako pravilno oceni bolje od kratke skozi ogenj.

Rezultat: iz "kje je" dobimo **"v kakšni situaciji je"**.

### DQL-2 — Ocena odločitve

Za vsak **dogodek** (kill, smrt, plant, revive, push) primerjamo kontekst tik pred njim s tem, kar se je zgodilo po njem:

| Odločitev | Dobra, če… | Slaba, če… |
|-----------|-----------|-----------|
| Push naprej | ekipa sledi (cohesion pade < X), pridobiš prostor/objective | greš sam, umreš, ekipa izgubi prostor (že merimo kot useless-defense) |
| Zadrževanje / lurk | ustvariš priložnost soigralcem (enabler/gravity) | pasivnost brez učinka |
| Sacrifice | umreš, a ekipa v naslednjih N sekundah napreduje **in je napredek povezan s tvojo smrtjo** (glej spodaj) | umreš brez posledice |
| Objective run | pot se je izogibala takratni nevarnosti, prihod pri zdravju, timing usklajen z ekipo | šel skozi znano nevarno cono brez podpore in kritja |

Ownerjev "sacrifice, ki nastavi priložnost" postane **merljiv** — a ne naivno.

**Zakaj golo časovno okno ne zadošča (popravljeno po reviewu):** pravilo *"smrt + napredek ekipe v N sekundah = sacrifice"* bi nagradilo vsako smrt, ki ji slučajno sledi napredek — tudi če je bila na drugem koncu mape ali če je ekipa napredovala povsem neodvisno. Igralec bi lahko "nabiral" točke z brezveznim umiranjem ob pravem času.

Zato mora sacrifice zahtevati **vzročne dokaze**, ne le sosledje. Vsi so izračunljivi iz obstoječih podatkov:

| Dokaz | Kako ga preverimo |
|-------|-------------------|
| **Prostorska povezanost** | napredek se je zgodil tam, kjer si umrl (ali na poti, ki jo je tvoja smrt odprla) — imamo pozicije obojih |
| **Odvzeta pozornost** | nasprotniki, ki so te ubili/streljali vate, so bili v tistem oknu zasedeni s tabo namesto z branjenjem — imamo `gravity`, `focus_fire`, aim-lock ciljanje |
| **Nasprotna baza (counterfactual)** | primerjava s podobnimi situacijami BREZ smrti: če ekipa enako pogosto napreduje tudi brez nje, smrt ni bila vzrok |
| **Izključitev trivialnih smrti** | selfkill, fall damage, smrt v mrtvem času ali daleč od vsakega objectiva se ne štejejo |

Šele ko so ti pogoji izpolnjeni, se smrt označi kot sacrifice. Brez tega je metrika izigravanju odprta in bi ownerja (ki *dejansko* igra tako) postavila v isti koš z nekom, ki samo pogosto umira.

### DQL-3 — Fazna zavest (rabi V2 dopolnitev — in NOV vir)

**Pomembna omejitev (popravljeno po reviewu):** `player_track.path` vsebuje samo polja iz §V1 — **nima** pojma o fazi ali o tem, kateri objective je trenutno aktiven. Za razliko od DQL-1 in DQL-2 ta gradnik torej **ni** izračunljiv zgolj iz obstoječih poti.

Faze bi izpeljali iz dogodkovnih tabel (`OBJECTIVE_RUNS`, `CONSTRUCTION_EVENTS`, carrier), a to da le **časovne žige dokončanih akcij**, ne stanja igre. Na mapah s **sekvenčnimi, opcijskimi ali vzporednimi** objectivi (goldrush: tank → banka → dokumenti; supply: več poti) iz tega ni mogoče zanesljivo sklepati, kaj je bilo v danem trenutku *aktivno* in kaj *še nedosegljivo*.

Zato DQL-3 potrebuje **enega od dveh** dodatnih virov — to je odločitev, ki jo mora owner sprejeti, preden se karkoli začne:

| Možnost | Kaj pomeni | Cena |
|---------|-----------|------|
| **A. Ročni fazni model per mapa** | za vsako mapo zapišemo graf odvisnosti objectivov (kaj odklene kaj) in fazo izpeljemo iz že zajetih dogodkov | brez Lua sprememb; delo je v definicijah (14+ map) |
| **B. Lua doda stanje objectivov** | tracker periodično zapiše stanje vsakega objectiva (aktiven/zaklenjen/opravljen) | najbolj zanesljivo, a **zahteva Lua spremembo + redeploy na puran** — kar sicer nikjer drugje ne rabimo |

Dokler ta odločitev ne pade, DQL-3 ostaja **odložen**. DQL-1 od njega ni odvisen.

**DQL-2 pa je delno odvisen (popravljeno po reviewu):** ocene, ki vsebujejo pojem *"koristnega prostora"* ali *"pravega objectiva"*, na mapah s sekvenčnimi/opcijskimi/vzporednimi cilji brez faze niso zanesljive — push proti drugemu objectivu, ko je aktiven prvi, izgleda enako kot pravi push. Zato se DQL-2 uvede v dveh korakih:

- **Faza A (brez DQL-3):** ocene, ki so fazno nevtralne — trade responsiveness, izolacija/lurk, sacrifice s kavzalnimi dokazi, objective-run kvaliteta (ta ima svoj kontekst že v zapisu).
- **Faza B (po DQL-3):** ocene, ki potrebujejo *"kateri cilj je zdaj pomemben"* — vrednost pridobljenega prostora, kvaliteta pusha, obrambne odločitve.

---

## 4. Prioritete (predlog vrstnega reda)

| Prio | Ukrep | Zakaj prvi | Napor |
|------|-------|-----------|-------|
| **0** | **Popraviti dva živa scoring defekta** (§2a): KIS push multiplier na obrnjeni metriki, prox_score awareness/mechanical osi | ne gre za nov feature — trenutno aktivno kvarita rezultate | S–M |
| **1** | `et_brewdog` (+ manjkajoče) v `objective_zones.json` | 45 rund trenutno šteje kot "brez objectiva" — čista izguba točnih podatkov, majhen napor | S |
| **1b** | **`carrier_event` izenačiti z `objective_run`** (enemies_nearby, nearby_teammates, run_type) | 69 % objective dela opravijo medici in zanje nimamo konteksta; `path_samples` že obstaja na vseh 2.079 vrsticah | M |
| **2** | DQL-1 kontekst giba (izolacija, približevanje objectivu, lokalna premoč) | temelj za vse ostalo; vhodi že obstajajo | M |
| **3** | Razširi `OBJECTIVE_RUNS` logiko na vse igralce (ne samo inženirje) | dokazano deluje, samo posplošitev | M |
| **4** | DQL-2 ocena odločitev + "sacrifice score" | ownerjeva osrednja želja; hrani LURK/OBJECTIVE osi Passporta | L |
| **5** | DQL-3 faze runde | največ dodane vrednosti, a rabi 1+3 **in ownerjevo odločitev A/B o viru faznega stanja** (§DQL-3) | L |
| **6** | Puran Lua redeploy (aim-lock clamp) | ni blokada za DQL, a čisti podatke | S (owner-gated) |

---

## 5. Kaj NE potrebujemo

- **Ne rabimo novega Lua zajema za DQL-1 in DQL-2.** Oba se izračunata iz obstoječih 223 MB poti; Lua spremembe pomenijo redeploy na puran in tveganje. **Izjema je DQL-3**: fazno stanje objectivov v poteh NE obstaja, zato zanj potrebujemo bodisi ročni fazni model per mapa (možnost A, brez Lua) bodisi novo Lua polje (možnost B) — ownerjeva odločitev.
- **Ne rabimo več podatkov, rabimo več pomena.** Zajemamo ~3.400 zapisov na rundo in jih prikazujemo kot povprečja. Vrzel je interpretacija, ne zajem.
- **Ne rabimo dohitevati gibhuba pri log-statih.** Oni imajo XP/stance/shove iz logov; mi imamo prostor in čas, ki ga oni **ne morejo** imeti. DQL je nekaj, česar iz strežniških logov ni mogoče izpeljati.

---

## 6. Vprašanja za ownerja

1. **et_brewdog koordinate**: jih lahko izluščim iz .pk3 (kot za ostalih 14 map), ali imaš raje ročno preverjene?
2. **"Dobra odločitev"** — se strinjaš z definicijo *"kar poveča verjetnost zmage runde"*, ali imaš drugačen občutek (npr. tudi "kar je lepo za gledat")?
3. **Sacrifice okno**: koliko sekund po smrti še šteje kot "posledica moje smrti"? (predlog: 10 s, kot carrier chain)
4. **Fazna delitev**: naj jo izpeljem avtomatsko iz objective dogodkov, ali želiš ročno definirane faze per mapa?
5. **Prikaz**: naj DQL najprej pride kot Discord izpis (`!decisions`), ali kot API + tvoj obstoječi /proximity/ panel?
