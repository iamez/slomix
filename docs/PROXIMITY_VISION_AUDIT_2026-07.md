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

```text
time, x, y, z, health, speed, weapon, stance, sprint, event
```

To ni "približno kje je igralec" — to je **kje je, s koliko življenja, s katerim orožjem, v kateri drži, ali sprinta in kaj se mu je ravno zgodilo.**

**Ena prava vrzel (popravljeno po reviewu): smer pogleda.** Pot NE vsebuje viewangles, zato iz nje ni mogoče ločiti igralca, ki pravilno drži choke, od tistega, ki na istem mestu gleda stran. Za odločitveno oceno (DQL) je to pomembna razlika. Viewangles obstajajo, a le **dogodkovno**: `SHOT_FIRED` (ob strelu) in `AIM_LOCK` (ko je križec na sovražniku) — torej vemo, kam je gledal, kadar je streljal ali koga sledil, ne pa med zatišjem.

V1 je torej **dosežen za pozicijo/stanje, ne pa za neprekinjeno orientacijo.** Če se izkaže, da DQL rabi zvezno smer pogleda, bi to zahtevalo Lua spremembo (dodatno polje v vzorcu poti). **Ni edina** — popravek po reviewu: DQL-3 možnost B je prav tako Lua sprememba, in med predlogi je še aim-lock postavka. Prvotna formulacija je trdila, da je to edini tak primer v dokumentu; ni.

V bazi (`player_track.path`, JSONB): **63.058 poti, 246 MB** (premerjeno 2026-08-05;
ob pisanju 2026-07-25 je bilo 57.311 poti / 223 MB — raste za ~500 poti na dan). Ena runda etl_adlernest R2 (272 s) da 50 poti in v isti datoteki še:

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

> ⚠️ Ob preverjanju 2026-08-05: `meta` blok v tej datoteki trdi `map_count: 13,
> objective_count: 63`, dejansko pa vsebuje **14 map in 72 objektivov**. Števci v
> `meta` niso bili posodobljeni ob zadnjem dodajanju mape. Nič jih ne bere (koda
> gre neposredno v `maps`), zato ni posledic — a je zavajajoče za bralca.

**Vrzeli:**

1. **Manjkajoča mapa med najbolj igranimi:** `et_brewdog` **nima definicij**.
   Premerjeno 2026-08-05: **33 rund v zadnjih 30 dneh** (3. najbolj igrana, za
   `te_escape2` 93 in `etl_adlernest` 43), **192 rund od 2025-01-23**. Vsak kill
   na brewdogu tako šteje kot "ne pri objectivu", kar sistematsko podceni delo na
   tej mapi. Manjka tudi `et_beach` (6 rund v 30 dneh).
2. **Zone so točke z radijem, ne faze.** Sistem ve *"tu je dinamit"*, ne ve pa *"ta objective je trenutno aktiven / že padel / še ni dosegljiv"*. V stopwatchu je isti prostor v 2. minuti nepomemben in v 6. odločilen — te razlike ne poznamo.
3. **Ni pojma napadalec/branilec po fazi.** Imamo `defender_team` na rundi, nimamo pa "kaj je bil cilj v tem trenutku".

### V3 — ocena odločitev: **❌ NAJVEČJA VRZEL — a bližje, kot izgleda**

Trenutno ocenjujemo **izide** (kill je vreden X), skoraj nič pa **odločitev** (ali je bilo pametno tja iti).

Izjema, ki dokazuje, da je izvedljivo: `OBJECTIVE_RUNS` že **zdaj** zapisuje za vsako inženirsko akcijo:

```text
action_type=dynamite_plant, approach_time_ms=29800, approach_distance=6627,
beeline_distance=2696, path_efficiency=0.407, enemies_nearby=2,
nearby_teammates=0, run_type=contested_solo, self_kills=0, team_kills=0
```

Kontekstna polja (`enemies_nearby`, `nearby_teammates`, `run_type`, `escort_guids`) **so** pravi gradniki ocene odločitve. Toda dve stvari, ki sta se pokazali šele ob ownerjevem ugovoru (2026-07-25) in ju je treba povedati naravnost:

**(a) To NI "inženirska" tabela, ki bi jo bilo treba le posplošiti — je tabela, ki pokriva napačno manjšino.**
`proximity_objective_run` pozna samo štiri akcije, vse inženirske: `dynamite_plant` (1.058), `objective_destroyed` (656), `construction_complete` (643), `dynamite_defuse` (152) — skupaj **2.509**. Nošenje dokumentov/zastave je v ločeni tabeli `proximity_carrier_event` z **2.079** zapisi.

**Pošten razrez (dvakrat popravljeno).** Prvotno besedilo je 69,4 % predstavilo kot delež vsega objective dela; to je bil delež *nosilcev*. Popravek je nato navedel še „28,2 % opravijo medici", kar se ne izide z lastnima številkama tega dokumenta (45,3 % × 69,4 % = 31,4 %) — ujel Codex.

Preračunano proti bazi 2026-08-06: **5.367 objective dogodkov, od tega 2.481 nošenj = 46,2 %** (ob pisanju 2026-07-25 je bilo 4.588 oziroma 45,3 %). Deleža po razredih **ne navajam več**: `proximity_carrier_event` nima stolpca za razred, izpeljati ga je mogoče le s spojem na `player_track`, in moj poskus takega spoja je dal 97,4 % — številko, ki ji ne zaupam dovolj, da bi jo objavil. Sklep na tem ne stoji in ostane: **46 % objective dogodkov je nošenja in zanje nimamo niti enega konteksta odločitve.**

| Polje | objective_run (2.509, inženir) | carrier_event (2.079, 69 % medici) |
|---|---|---|
| `enemies_nearby` / `nearby_teammates` | ✅ | ❌ |
| `run_type`, `escort_guids` | ✅ | ❌ |
| geometrija (distance/beeline/efficiency) | ✅ | ✅ — **samo to** |

Bogat kontekst torej pokriva 55 % objective dogodkov, 45 % (nošenje) pa nima ničesar. Prva naloga ni "posplošiti z inženirja", ampak **carrier_event izenačiti z objective_run**.

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
| `push_quality` | vs uboji v 5 s oknu | 🔴 **OBRNJENA** — <0,5 → 0,90 killov; 0,9–1,2 → 0,60; 1,2+ → 0,43 (pas 0,5–0,9 ni bil izračunan — glej opombo) | **KIS push multiplier (prag 0,9)** |
| `dodge_reaction_ms` | vs pobeg iz spopada | 🔴 **OBRNJENA** — <300 ms → 22 % pobegov; 1000+ ms → 65,7 % | **prox_score "awareness" (nižje = bolje)** |
| `path_efficiency` | vs težavnost in izid | 🔴 **OBRNJENA** — glej §V3 | prikaz objective runs |
| `efficiency` (carrier) | vs izid nošenja | 🔴 **OBRNJENA** — ubit 0,501 > secural 0,489 > izgubil 0,465 | prikaz carrier eventov |
| `angular_separation` | vs izvedba crossfira | 🟠 **BREZ SIGNALA** — 30–60°/60–90°/90+ vsi ~25–26 %; loči le <30° (58,7 %), kar pa ni pravi crossfire | **crossfire leaderboard rangira po njej** |
| `return_fire_ms` | vs pobeg iz spopada | 🟠 **BREZ SIGNALA** — 40,1 / 34,9 / 36,8 / 41,5 % (U-oblika) | **prox_score "mechanical" os** |
| `gravity` | ali meri pozornost ali volumen | 🟠 **ZAMEŠANA** — r=0,897 s št. spopadov, r=0,724 s smrtmi | predlagan vhod za LURK os |
| cohesion `dispersion` | "zbita ekipa = bolje" | 🟠 **NEPODPRTO** — surova razlika (47,8 % vs 55,9 %) je večinoma napadalec/branilec; znotraj vlog ostane le +2 do +5 t. v korist **razpršenih** | cohesion panel, teamplay |

**Od devetih testiranih metrik je nesporno zdrava ena.**

### Dva ŽIVA scoring defekta (ne le prikaz)

> ⚠️ **Manjka pas 0,5–0,9** (Codex, #551). Prvotna analiza ga ni izračunala, in to ni
> postranski pas: premerjeno 2026-08-06 je v `proximity_team_push` **55.193 pushev**
> med 0,5 in 0,9, proti 31.204 pod 0,5, 8.456 med 0,9 in 1,2 in 1.037 nad 1,2 — torej
> **največji pas od vseh štirih, izpuščen iz tabele**. Ubojev na push zanj nimam:
> `proximity_team_push` stolpca za uboje nima, številke v tabeli so plod spoja v
> 5-sekundnem oknu, ki ga tu nisem ponovil. Sklep o obrnjenosti zato drži le za
> pasove, ki so izračunani; z manjkajočim modalnim pasom tabela sama po sebi ne
> zadošča in jo je treba dopolniti, preden se na njej karkoli gradi.

1. **KIS push multiplier stoji na obrnjeni metriki.** `PUSH_QUALITY_THRESHOLD = 0,9` zajame ravno pas z **najmanj** uboji. Vzrok je v formuli: `push_quality = poravnanost × (hitrost/300)` je največja, ko cela ekipa sprinta v isto smer — kar se zgodi ob **odsotnosti stika** (tek iz spawna). Ob dejanskem stiku se hitrost zmanjša in ekipa razprši → "nizka kvaliteta". KIS torej ojača uboje med nemotenim sprintom. (Formula je tudi neomejena: max 2,16, 4.124 od 84.309 vrstic nad 1,0.)

2. **~~prox_score "awareness" os se sama s sabo bori.~~ NAPAČNO — popravljeno po reviewu (Codex, #551).** Preveril sem v kodi: `proximity_scoring.py:288` računa
   `awareness = min(100, esc_rate * 0.5 + max(0, 100 - d_ms / 50) * 0.5)`.
   Surovi `dodge_ms` je res „manj je bolje", a ga prav to odštevanje **obrne** — 1.000 ms
   da 80, 5.000 ms da 0. Obe polovici osi torej kažeta v isto smer in os se s sabo ne bori.
   Ta ugotovitev odpade. Kar ostane: **"mechanical" os stoji na `return_fire_ms`, ki nima
   signala** — to je bilo izmerjeno in drži.

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
- ali je v ozkem grlu — ⚠️ **NE zgolj iz gostote gibanja**: spawn sobe, staging prostori in odprti objectivi so med najgostejšimi mesti na mapi, pa niso ozka grla. Ozko grlo mora zahtevati oboje: visoko gostoto prehodov **in** visoko smrtnost na prehod (kill heatmap / gostota poti), sicer bi metrika kaznovala normalno pot iz spawna;
- **izpostavljenost v tistem trenutku** — koliko nevarnosti je pot vsebovala glede na dejanske pozicije nasprotnikov in zgodovinsko smrtnost te celice.

**Zadnja postavka je odgovor na `path_efficiency`.** Namesto *"kako ravno je šel"* merimo *"koliko nevarnosti je pot vsebovala glede na to, kje so bili takrat nasprotniki"*. Ista pot je lahko odlična ali samomorilska, odvisno od trenutka — ravnost tega ne ve, izpostavljenost pa. Daljša pot skozi varno območje se tako pravilno oceni bolje od kratke skozi ogenj.

**Tri omejitve, ki jih je izpostavil review in brez katerih je izpostavljenost prav tako neveljavna:**

1. **Ni "vidnega polja".** Zvezne smeri pogleda nimamo (§V1), zato izpostavljenosti NE smemo definirati kot "bil je v vidnem polju nasprotnika". Uporabna definicija je brez orientacije: razdalja, prekinjenost pogleda po geometriji mape in zgodovinska smrtnost celice.
2. **Sodi po informaciji, ki jo je igralec IMEL.** Nasprotnik za zidom, ki ga nihče ni videl in ga ni izdal noben signal (strel, zvok, ubit soigralec, spawn wave), ne sme šteti kot "nevarnost, ki bi se ji moral izogniti" — sicer kaznujemo za vsevednost, ki je igralec ni imel. Nevarnost mora izhajati iz **znanih** nasprotnikov: tistih, ki so bili v tem oknu videni, so streljali, ali so bili implicirani po wave-timingu.
3. **Nevarnostna podlaga ne sme vsebovati ocenjevane runde.** Če smrtnost celice računamo iz zgodovine, ki vključuje prav to rundo, se izid pricurlja v lastno oceno (data leakage): igralec, ki tam umre, poveča nevarnost celice in je zato retroaktivno kaznovan zaradi lastne smrti. Podlaga mora biti **leave-one-round-out**.

Rezultat: iz "kje je" dobimo **"v kakšni situaciji je"**.

### DQL-2 — Ocena odločitve

Za vsak **dogodek** (kill, smrt, plant, revive, push) primerjamo kontekst tik pred njim s tem, kar se je zgodilo po njem:

| Odločitev | Dobra, če… | Slaba, če… |
|-----------|-----------|-----------|
| Push naprej | ekipa sledi in **fronta se premakne proti objectivu** (glej opombo o prostoru) | greš sam, umreš, fronta se pomakne nazaj |
| Zadrževanje / lurk | soigralec v tem oknu dejansko izkoristi priložnost (kill/objective napredek, ki ga je omogočila tvoja prisotnost) — **NE** zgolj visok `gravity` | pasivnost brez učinka |
| Sacrifice | umreš, a ekipa v naslednjih N sekundah napreduje **in je napredek povezan s tvojo smrtjo** (glej spodaj) | umreš brez posledice |
| Objective run | pot se je izogibala takratni nevarnosti, prihod pri zdravju, timing usklajen z ekipo | šel skozi znano nevarno cono brez podpore in kritja |

**Opomba o "prostoru" (review):** izgubljenega prostora NE moremo vzeti iz `useless-defense` — ta meri smrt branilca z oddaljenim spawnom, ne premika fronte. Prostor je treba izpeljati posebej, npr. kot premik **težišča stika** (mediana pozicij spopadov obeh ekip) med oknom pred pushem in po njem. Brez te izpeljave je vrstica "ekipa izgubi prostor" neizmerljiva.

**Opomba o lurk (review):** `gravity` ne sme biti dokaz koristnega lurkanja — meri predvsem volumen spopadov in smrti (r=0,897 oz. 0,724, §2a). Igralec z veliko spopadi bi bil samodejno označen za koristnega. Dokaz mora biti **izkoriščena priložnost pri soigralcu**, ne pozornost sama.

Ownerjev "sacrifice, ki nastavi priložnost" postane **merljiv** — a ne naivno.

**Zakaj golo časovno okno ne zadošča (popravljeno po reviewu):** pravilo *"smrt + napredek ekipe v N sekundah = sacrifice"* bi nagradilo vsako smrt, ki ji slučajno sledi napredek — tudi če je bila na drugem koncu mape ali če je ekipa napredovala povsem neodvisno. Igralec bi lahko "nabiral" točke z brezveznim umiranjem ob pravem času.

Zato mora sacrifice zahtevati **več kot sosledje**. Pogoji spodaj so izračunljivi iz obstoječih podatkov:

> ⚠️ Popravek poimenovanja (Codex, #551): tudi ujemanje po podobnih situacijah ostane > **opazovalno, ne vzročno**. Faza runde, stanje nasprotnika, stanje soigralcev in > igralčeva lastna izbira so nemerjeni in lahko pojasnijo razliko. Spodnji pogoji zožijo > primerjavo in odpravijo najbolj očitno farmanje, ne dokazujejo pa vzroka — dokler tega > ne moremo trditi, se metrika ne sme predstavljati kot „ta smrt je ekipi pomagala".

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

- **Faza A (brez DQL-3):** ocene, ki so fazno nevtralne — trade responsiveness, izolacija/lurk, sacrifice s kavzalnimi dokazi.
  ⚠️ **Objective-run kvaliteta NE spada v fazo A** (popravek po reviewu): tabela beleži izključno uspele akcije (`approach_killed` = 0, `denied` = 0, §V3c), zato bi vsaka "kvaliteta" primerjala uspehe z uspehi. Dokler zajem ne beleži tudi prekinjenih poskusov, ta ocena ni izvedljiva — ne v fazi A ne v fazi B.
- **Faza B (po DQL-3):** ocene, ki potrebujejo *"kateri cilj je zdaj pomemben"* — vrednost pridobljenega prostora, kvaliteta pusha, obrambne odločitve.

---

## 4. Prioritete (predlog vrstnega reda)

| Prio | Ukrep | Zakaj prvi | Napor |
|------|-------|-----------|-------|
| **0** | **Popraviti dva živa scoring defekta** (§2a): KIS push multiplier na obrnjeni metriki, prox_score awareness/mechanical osi | ne gre za nov feature — trenutno aktivno kvarita rezultate | S–M |
| **1** | `et_brewdog` (+ manjkajoče) v `objective_zones.json` | 33 rund v 30 dneh (192 vseh) šteje kot "brez objectiva" — čista izguba točnih podatkov, majhen napor | S |
| **1b** | **`carrier_event` izenačiti z `objective_run`** (enemies_nearby, nearby_teammates, run_type) | 46 % objective dogodkov je nošenja in zanje nimamo nobenega konteksta. **Vir ni `path_samples`** — ta je `INTEGER`, torej števec vzorcev, ne pot (Codex, #551). Kontekst je treba izpeljati iz `player_track.path` po času in poziciji nosilca, ali pa ga dodati v Lua ob dogodku. | M–L |
| **2** | DQL-1 kontekst giba (izolacija, približevanje objectivu, lokalna premoč) | temelj za vse ostalo; vhodi že obstajajo | M |
| **3** | Razširi `OBJECTIVE_RUNS` logiko na vse igralce (ne samo inženirje) | dokazano deluje, samo posplošitev | M |
| **4** | DQL-2 ocena odločitev + "sacrifice score" | ownerjeva osrednja želja; hrani LURK/OBJECTIVE osi Passporta | L |
| **5** | DQL-3 faze runde | največ dodane vrednosti, a rabi 1+3 **in ownerjevo odločitev A/B o viru faznega stanja** (§DQL-3) | L |
| **6** | Puran Lua redeploy (aim-lock clamp) | ni blokada za DQL, a čisti podatke | S (owner-gated) |

---

## 5. Kaj NE potrebujemo

- **Ne rabimo novega Lua zajema za DQL-1 in DQL-2.** Oba se izračunata iz obstoječih ~246 MB poti; Lua spremembe pomenijo redeploy na puran in tveganje. **Izjema je DQL-3**: fazno stanje objectivov v poteh NE obstaja, zato zanj potrebujemo bodisi ročni fazni model per mapa (možnost A, brez Lua) bodisi novo Lua polje (možnost B) — ownerjeva odločitev.
- **Ne rabimo več podatkov, rabimo več pomena.** Zajemamo ~3.400 zapisov na rundo in jih prikazujemo kot povprečja. Vrzel je interpretacija, ne zajem.
- **Ne rabimo dohitevati gibhuba pri log-statih.** Oni imajo XP/stance/shove iz logov; mi imamo prostor in čas, ki ga oni **ne morejo** imeti. DQL je nekaj, česar iz strežniških logov ni mogoče izpeljati.

---

## 6. Vprašanja za ownerja

1. **et_brewdog koordinate**: jih lahko izluščim iz .pk3 (kot za ostalih 14 map), ali imaš raje ročno preverjene?
2. **"Dobra odločitev"** — se strinjaš z definicijo *"kar poveča verjetnost zmage runde"*, ali imaš drugačen občutek (npr. tudi "kar je lepo za gledat")?
3. **Sacrifice okno**: koliko sekund po smrti še šteje kot "posledica moje smrti"? (predlog: 10 s, kot carrier chain)
4. **Fazna delitev**: naj jo izpeljem avtomatsko iz objective dogodkov, ali želiš ročno definirane faze per mapa?
5. **Prikaz**: naj DQL najprej pride kot Discord izpis (`!decisions`), ali kot API + tvoj obstoječi /proximity/ panel?

---

## Odzivi na review (Codex, PR #551) — preverjeno 2026-08-06

Dvanajst P2 pripomb na ta dokument. Nobene nisem zavrnil kot neutemeljene;
tri so bile v besedilu že naslovljene, devet spreminja predlog. Kjer je bila
trditev preverljiva, sem jo preveril in ne le sprejel.

| # | Pripomba | Odziv |
|---|----------|-------|
| 1 | Izgubljenega prostora ne izpeljuj iz useless-defense | **Sprejeto.** `compute_useless_defense_deaths` gleda le oddaljenost žrtve od objectiva — o tem, ali je ekipa izgubila prostor, ne pove nič. DQL-2 mora izgubo prostora izpeljati iz pozicij, ne reciklirati te metrike. |
| 2 | Ravna pot ni kakovost odločitve | **Že v dokumentu**, §V3(b), in review to potrjuje: `contested_solo` ima najvišjo `path_efficiency` (0,585), `team_effort` skoraj najnižjo (0,468). Metrika kaže v napačno smer. |
| 3 | Chokepointa ne sklepaj iz gostote prehodov | **Sprejeto.** Gostota ne loči ozkega grla od običajnega prehodnega vozlišča (spawn, staging). Rabi signal zožitve ali pogojevanje s kill-gostoto. |
| 4 | Pred FOV izpostavljenostjo zajemi smer pogleda | **Sprejeto**, in to je ista vrzel kot §V1: poti nimajo viewangles. FOV komponenta DQL-1 je blokirana na istem mestu. |
| 5 | Kakovost objective-runov odloži, dokler ne beležimo neuspehov | **Že v dokumentu**, §V3(c): `approach_killed` = 0 vrstic, `run_type='denied'` = 0. Sprejeto kot izrecna vrstna omejitev, ne le opomba. |
| 6 | Ocenjevane runde izloči iz danger baseline | **Sprejeto.** `map_kill_heatmap` je kumulativen agregat, zato ocenjevana runda pušča svoj izid v lasten vhod. |
| 7 | Gravitacija ni dokaz koristnega lurkanja | **Sprejeto.** Rabi dokaz, da je nastala priložnost za soigralca, ne le prisotnost. |
| 8 | Odločitve sodi po informaciji, ki jo je igralec imel | **Sprejeto.** Uporaba resnične pozicije skritega nasprotnika da DQL vednost, ki je igralec ni imel. |
| 9 | Popravi imenovalec pri nosilcih | **Že popravljeno** v §V3(a): 69,4 % je delež *nosilcev*, ne delež vsega objective dela. |
| 10 | Pred offline zakritjem rabiš vir geometrije | **Sprejeto, in preverjeno danes.** V repu ni razčlenjevalnika BSP, navmesha, AAS ne sledenja žarkov; `.bsp` se pojavi izključno kot končnica imena datoteke (`players_router.py:1526`, `api_helpers.py:120`) in kot vnos v `map_assets_manifest_from_etmain.json`. `website/backend/map_geometry/` vsebuje samo `__pycache__` in v gitu ni ničesar. Zakritje v DQL-1 je blokirano. |
| 11 | Danger baseline gradi le iz podatkov, znanih ob ocenjevanju | **Sprejeto**, isti razred kot #6: leave-one-round-out ne zadošča, ker je agregat vezan na mapo/celico brez časovne dimenzije. |
| 12 | `path_samples` ni shranjena pot nosilca | **Sprejeto, in preverjeno.** Migracija 028 ga definira kot `path_samples INTEGER NOT NULL DEFAULT 0`, in v shemi je `proximity_carrier_event.path_samples : integer` — torej **števec vzorcev, ne trajektorija**. P1b iz njega ne more izpeljati `enemies_nearby`, soigralcev ne `run_type`. |

**Kaj to pomeni za predlog.** DQL-1 (zakritje, FOV) je blokiran na dveh
manjkajočih virih — geometriji in smeri pogleda — in ne le na fazi objectiva,
kot je dokument trdil. DQL-2 potrebuje lasten izračun izgubljenega prostora.
Ocenjevanje objective-runov mora počakati na beleženje neuspehov. To so
omejitve načrta, ne razlogi proti njemu; dokument je zdaj o njih iskren.
