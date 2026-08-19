# KIS validity audit — kaj uboj dejansko naredi

**Datum:** 19. 8. 2026 · **Povod:** superboyyjeva vprašanja na Discordu +
ownerjeva definicija KIS-a · **Status:** meritev, nič spremenjeno
**Skript:** `scripts/backtest_kis_v6.py` (READ-ONLY, `SET default_transaction_read_only = on`)
**Vzorec:** 34.597 ubojev / 638 rund (od 40.613 vrstic `kis-v5`, 85,2 %)

---

## 0. Povzetek v petih vrsticah

1. **`spawn` in `reinf` sta ista številka** — obe izhajata iz Luaovega
   `time_to_next`. 37,7 % razpona KIS-a je ena količina, všteta dvakrat.
2. **Trije multiplikatorji merijo nasprotno od tega, kar plačujejo**
   (`health`, `alive`/clutch, `class`), eden pa **nasprotno po vlogi**
   (`objective`: napadalec −5,2 o. t., branilec +6,6 o. t.).
3. **Dva stolpca sta mrtva** — `push` (upokojen v v5) in `dist` (ni podatka)
   sta vedno 1,0, a se v UI-ju še vedno rišeta.
4. **Nobena utež ne prekaša golega štetja ubojev.** Null model »vsak uboj = 1«
   napove zmagovalca runde v 65,4 %, v5 v 64,8 %, vseh pet kandidatov za v6 v
   64,0–64,3 %. Nobena razlika ni značilna (p ≥ 0,3).
5. **Lestvica KIS = lestvica ubojev**: ρ(vsota KIS, št. ubojev) = **0,996**.

> ⚠️ Točka 4 velja za **v5 in za prve kandidate v6**. Isti dan je nastala
> različica v6 s tremi novimi proximity osmi, ki golo štetje **prekaša**
> (69,12 % proti 66,93 %, McNemar p = 0,039) — glej **§9**, ki dopolnjuje
> točko 4 in preseže §7.1.

---

## 1. Metoda in filtri (vedno priloži filtre)

Vse meritve tečejo na `storytelling_kill_impact` `formula_version = 'kis-v5'`,
z `JOIN proximity_kill_outcome` → `rounds`, in:

- `rounds.is_valid`, `NOT is_bot_round`, `winner_team IN (1,2)`, `defender_team IN (1,2)`
- brez botov na obeh straneh (`OMNIBOT%`, `[BOT]%`)
- stran ubijalca iz `proximity_combat_position.attacker_team` (join nosi tudi
  `victim_guid`, sicer dva uboja z istim `event_time` razpihneta vrstice);
  pokritost 85,2 %. ⚠️ Prva različica te raziskave je brala
  `proximity_spawn_timing.killer_team` (86,1 %, 34.955 ubojev) — commitana
  skripta tega ne počne več, zato so vse številke tu iz `combat_position` poti.
- `defender_team` se **bere**, nikoli ne kodira: `etl_ice` je edina mapa v bazi,
  kjer branijo Allies

**Osnovi sta ločeni po vlogi**, ker se globalna osnova (~51 %) izkaže za past:

| vloga | n ubojev | osnova (zmaga runde) |
|---|---:|---:|
| napadalec | 14.435 | **65,08 %** |
| branilec | 20.520 | **40,90 %** |

Meritev proti globalnemu ~51 % obrne predznake — isto opozorilo kot memory
`kis-round-swing-2026-08-01` in `et-metrics-what-fails-2026-08-17`.

---

## 2. Dvojno štetje spawn ure

`proximity_tracker.lua:1674-1698` (`calculateSpawnTimingScore`) izračuna
**eno** količino, `time_to_next` — koliko časa žrtvina ekipa še čaka na val —
in jo shrani dvakrat:

```lua
local score = time_to_next / interval          -- -> spawn_timing_score
...
local victim_reinf_ms = time_to_next           -- -> victim_reinf (sekunde)
```

`kis.py:_score_kill` ju nato **pomnoži oba**: `spawn_mult = 1 + score`
(razpon 1,0–2,0) in `reinf_mult` po `REINF_MULT_TIERS` (0,70–1,40).

| meritev | vrednost |
|---|---:|
| r(ln spawn_mult, ln reinf_mult) | **0,852** |
| var(ln total_impact) | 0,2844 |
| var brez `spawn` | 0,2004 |
| var brez `spawn` in `reinf` | 0,1767 |
| **delež razpona KIS-a iz spawn ure** | **37,7 %** |

Druga pot (aditivna dekompozicija variance po multiplikatorjih, celotna baza,
40.613 ubojev): `spawn` 0,0364 + `reinf` 0,0406 + 2·kovarianca 0,0557 = 0,133
od 0,2972 = **44,7 %**. Dve poti, ista velikostna stopnja → meritev drži.

Posledica za lestvico: če odstranimo podvojeno kopijo, se 5 od 14 igralcev
(≥200 ubojev) premakne za **≥3 mesta**, ρ = 0,688.

---

## 3. Vsak multiplikator, znotraj vloge

Odklon v odstotnih točkah od osnove **te vloge** (65,08 % / 40,90 %):

| multiplikator | v5 plača | napadalec n | ATT | branilec n | DEF | sodba |
|---|---|---:|---:|---:|---:|---|
| `reinf` 20 s+ vs 0–5 s | ×1,40 / ×0,70 | 3.092 / 3.706 | +3,9 / −4,2 | 344 / 6.531 | +3,0 / −1,6 | ✅ edina os s pravo smerjo v obeh vlogah |
| `spawn` | ×1,0–2,0 | — | ista količina kot `reinf` | — | — | ⛔ dvojno štetje |
| `objective` | ×1,4 obema | 2.458 | **−5,2** | 2.770 | **+6,6** | ⚠️ nasprotna smer po vlogi |
| `gibbed` | ×1,3 | 326 | +5,5 | 450 | +2,4 | ✅ smer pravilna |
| `revived` | ×0,5 | 2.869 | −2,0 | 4.032 | −1,2 | ⚠️ smer pravilna, kazen ~10× prevelika |
| `crossfire` | ×1,5 | 1.767 | +2,7 | 2.581 | −0,0 | ⚠️ le napadalčev signal, in šibkejši od ×1,5 |
| `class` (medic) | ×1,5 | 12.915 | −0,2 | 15.457 | +0,0 | ⛔ ni učinka (surovo +5,0 je Simpsonov paradoks) |
| `health` <30 HP | ×1,3 | 2.058 | −4,6 | 2.080 | −0,2 | ⛔ meri težavnost, ne učinka |
| `alive` (outnumbered/clutch) | ×1,5–2,0 | 1.151 | −6,1 | 1.299 | −5,7 | ⛔ meri, da si v godlji |
| `carrier` | ×3,0–5,0 | 1 | — | 799 | +3,3 | ⚠️ največja utež v sistemu, +3,3 o. t. dokaza |
| `push` | ×1,0 (upokojen) | — | — | — | — | mrtev stolpec |
| `dist` | ×1,0 vedno | — | — | — | — | mrtev stolpec |

**Objective je ownerjev ugovor, izmerjen.** Napadalčev uboj ob objektivu je
**slabši** od njegovega povprečnega uboja (59,9 % proti 65,1 %), branilčev je
boljši (47,5 % proti 40,9 %). Enoten ×1,4 obema je torej napačen v obe smeri
hkrati — natanko »z logiko skregano«, kot je owner rekel.

**`class` je šolski primer Simpsonovega paradoksa.** Surovo: uboj medica
napove zmago v 51,8 % proti 46,8 % (+5,0). Znotraj vloge: −0,2 in +0,0.
Razlika je bila sestava vlog, ne vrednost medica.

---

## 4. Ali utež sploh kaj kupi? (odločilni test)

⚠️ **Merilo:** ta razdelek in ves §9–§11 uporabljajo **parni test po rundah**
(seštej stran, razlika AXIS−ALLIES, centriraj po mapi, ali predznak imenuje
zmagovalca). Razdelek 2 dokumenta `METRIC_FOUNDATIONS_2026-08-19.md` uporablja
**drugo merilo** — klasifikacijsko točnost s CV in lutkami za mapo, kjer sam
večinski razred da 64,1 %. Številk med meriloma **ni mogoče primerjati**;
primerjajo se lahko samo razlike znotraj istega merila.

Parna primerjava po rundah: seštej kandidata za vsako stran, vzemi razliko
AXIS−ALLIES, odštej povprečno razliko **te mape** (izloči stran/mapo), in
poglej, ali predznak imenuje zmagovalca. 625 parnih rund, isti imenovalec za
vse kandidate (32.911 ubojev, ki jih zna oceniti vsak kandidat).

| kandidat | točnost | McNemar proti štetju |
|---|---:|---|
| **`kills` (null model: vsak uboj = 1)** | **65,44 %** | — |
| v5 (produkcija) | 64,80 % | 41 : 45, p = 0,666 |
| v5 brez dvojnega štetja | 64,64 % | 31 : 36, p = 0,541 |
| v6a odvzet čas (`effective_denied_ms`) | 64,32 % | 35 : 42, p = 0,425 |
| v6b faza vala (`victim_reinf`) | 64,00 % | 34 : 43, p = 0,305 |
| v6c val + izid (gib/revive) | 64,32 % | 33 : 40, p = 0,413 |
| v6d val + izid + bonusi po vlogi | 64,16 % | 38 : 46, p = 0,383 |

**Naključna kontrola:** če iste ocene premešamo *znotraj runde* (število ubojev
ostane nedotaknjeno, uteži se naključno prerazporedijo med igralce), točnost
pade le na **63,68 %** (5 tekov, sd 1,10 o. t.). Torej celoten razpon med
»nič uteži« in »najboljša utež« znaša ~1,8 o. t., večino tega pa pojasni šum.

⚠️ **Poštena opomba o nestabilnosti.** V prvi izvedbi (širši obseg, 638 rund,
brez zahteve, da uboj zna oceniti *vsak* kandidat) je v5 dosegel 68,3 % proti
66,6 % za štetje — torej +1,7 o. t. v drugo smer, prav tako neznačilno
(McNemar 45 : 34, p = 0,216). Ko se obseg zoži na skupni imenovalec, se
prednost obrne. **Učinek, ki spremeni predznak ob spremembi filtra, ni učinek.**

---

## 5. Kaj torej lestvica KIS meri

Na 14 igralcih z ≥200 uboji:

| meritev | vrednost |
|---|---:|
| ρ(vsota KIS v5, število ubojev) | **0,996** |
| ρ(vsota KIS v6d, število ubojev) | 0,991 |
| razpon povprečja na uboj (v5) | 2,31–2,47 (sd 0,045) |
| šumno dno za povprečje na uboj | ±0,026 |

Devet multiplikatorjev loči najboljšega od najslabšega igralca za **6 %**
povprečja na uboj, pri šumnem dnu ±1 %. Signal obstaja, a je za red velikosti
manjši, kot ga UI sugerira (stolpci od 0,5 do 5,0).

---

## 6. Zunanja primerjava

- **HLTV Rating 3.0** (avg. 2025) je opustil multiplikativni Impact in uvedel
  **Round Swing** = sprememba verjetnosti dobitka runde po vsakem uboju, s
  stanjem (živi, ekonomija, bomba, mapa). Oktobra 2025 so ga **oslabili** in
  povečali težo golih ubojev — kontekstna utež je prehitela produkcijo.
  <https://www.hltv.org/news/42485/introducing-rating-30> ·
  <https://www.hltv.org/news/43047/rating-30-adjustments-go-live>
- **Xenopoulos et al. (2020), arXiv 2011.01324** — akademski standard:
  `vrednost akcije = P(zmaga|po) − P(zmaga|pred)`, model stanja učen na 70 M
  dogodkih. <https://arxiv.org/pdf/2011.01324>
- Oba merita **stanje** (koliko jih je živih), ker je v CS smrt trajna. V ET je
  smrt **časovna**. Prenos formule ni mogoč; prenosljiva je le metoda —
  in metoda pravi: *najprej model verjetnosti, šele nato razlika*.
- Naš vzorec je za to premajhen: 625–638 rund s polnim stanjem proti 70 M
  dogodkom. Model stanja sme imeti 3–4 spremenljivke, sicer se prilagaja šumu.

---

## 7. Priporočilo (dopolnjeno — glej §9, ki ga deloma preseže)

**Ne uvajaj v6 kot novo množico uteži.** Meritev pravi, da uteži ne kupijo
ničesar merljivega, torej bi bila v6 z novimi številkami samo lepše zavita ista
napaka.

Trije koraki, po vrsti, vsak s svojim dokazom:

1. **Higiena, brez nove formule (majhen, varen PR).**
   - odstrani `spawn_multiplier` iz produkta (dvojno štetje) — `reinf` ostane;
   - `health`, `alive`, `class` → 1,0 (ostanejo kot opisna polja za panele);
   - `objective` → samo branilec; `crossfire` → samo napadalec, ×1,15;
   - `carrier` z ×3,0/5,0 na ×1,5/2,0;
   - `push` in `dist` odstrani iz UI tabele (vedno 1,0, samo begata);
   - `FORMULA_VERSION = "kis-v6"`, `kis_shadow.py` + `formula_registry.py`
     usklajena, nato `scripts/backfill_kis_recompute.py`.
   Pričakovan učinek na napovedno moč: **nič** (in to odkrito povej v UI-ju) —
   učinek je poštenost razlage, ne točnost.

2. **Manjkajoča polovica: kaj uboj naredi, ne kdaj se zgodi.**
   Vse današnje uteži so *okoliščine* uboja. Kar KIS ne vidi, je posledica:
   ali je nasprotnik izgubil položaj, ali je objektiv napredoval. Podatki za to
   že obstajajo in jih nihče ne bere:
   `proximity_carrier_event` (2.727 vrstic: trajanje, razdalja, `efficiency`),
   `proximity_escort_credit` (346), `proximity_objective_run` (3.156),
   `proximity_team_cohesion` (1,1 M vzorcev na 500 ms).
   To je hkrati odgovor na superboyyjevo drugo vprašanje.

3. **Šele nato Round Swing**, in samo če 2. korak pokaže, da imamo dovolj
   stanja: `P(zmaga | prednost v živih, faza vala, vloga, faza runde)`.
   Prag za uvedbo naj bo vnaprej postavljen: mora prekašati golo štetje ubojev
   z **p < 0,05** na parnem testu iz razdelka 4. Če ga ne, ostane štetje.

---

## 8. Reprodukcija

```bash
PGPASSWORD=… venv/bin/python3 scripts/backtest_kis_v6.py
```

Izpis (7 razdelkov A–G) vsebuje vse številke iz tega dokumenta.
Pomožni SQL-i iz prve poti so v scratchpadu seje
(`kis_validity.sql`, `kis_team.sql`, `kis_strat.sql`, `kis_role.sql`).


---

## 9. Dopolnitev istega dne: KIS v6 izmerjen (preseže §7, točka 1)

§7 je priporočal »ne uvajaj v6 kot novo množico uteži«, ker takratni kandidati
niso ničesar kupili. Ownerjeva zahteva (»probava mu dodat še kaj iz proximity?«)
je pripeljala do treh **novih** osi in do **drugačnega merila**. Rezultat je
drugačen, zato ta razdelek preseže §7.1.

### 9.1 Novo merilo: zanesljivost, ne napoved runde

Napoved zmagovalca runde je za per-kill oceno prešibka (638 rund). Zato je
glavno merilo odslej **split-half zanesljivost** po igralcu: naključno razpolovi
uboje vsakega igralca, primerjaj povprečji, korelacija čez igralce
(Spearman-Brown, 200 ponovitev). Kontrola: ostanek po odštetju povprečja vloge.

⚠️ **Metodološka past, ki jo je treba zapisati:** prvotna kontrola je bila
povprečje celice (mapa, stran). Vseh 20 celic v bazi pripada **natanko eni
vlogi** (Axis brani povsod razen na `etl_ice`), zato ta kontrola pri
vlogo-pogojeni oceni odšteje prav strukturo, ki jo merimo. Skript izpiše obe
številki; razsodba uporablja kontrolo po vlogi.

### 9.2 Nove osi (vse iz proximity, vse doslej neuporabljene)

| os | vir | pokritost | kaj je |
|---|---|---:|---|
| `stood` / `answered` | samo-join `proximity_kill_outcome` | 100 % | ali je sovražnik uboj **vrnil** v 10 s (30,4 % ubojev ga) |
| `isolation` | `proximity_trade_event.is_isolation_death` | 100 % | žrtev je bila odrezana od svojih (31 %) |
| razdalja uboja | `proximity_combat_position` obe koordinati | 100 % | mediana 490 u = 12,4 m; Garand Scope 2.508 u = 64 m |

Ko je uboj vrnjen, ubijalec vrne povprečno **8,5 s od 8,7 s**, ki jih je vzel —
časovno je tak uboj skoraj ničeln. To je ET-native različica »untraded kill«.

### 9.3 Model določi, tabela pokaže

Logistična regresija **po vlogi**, vse osi hkrati, `man_adv` kot kontrola že v
prvem prilagajanju, CI iz cluster bootstrapa po rundah (200×):

| os | ATT coef [CI] | DEF coef [CI] | v6 utež ATT / DEF |
|---|---|---|---|
| `wave_z` | 0,178 [0,123, 0,247] | 0,064 [−0,010, 0,136] | β = 0,178 (do ×1,43) / — |
| `stood` | 0,271 [0,179, 0,348] | 0,062 [−0,000, 0,138] | ×1,31 / — |
| `isolation` | −0,064 [−0,145, 0,041] | 0,175 [0,077, 0,262] | — / ×1,19 |
| `objective` | −0,330 [−0,529, −0,154] | 0,317 [0,093, 0,517] | — / ×1,37 |
| `crossfire` | 0,154 [0,021, 0,282] | 0,000 [−0,118, 0,117] | ×1,17 / — |
| `carrier`, `gibbed`, `revived` | CI čez ničlo | CI čez ničlo | ×1,00 |
| `man_adv` (kontrola) | 0,198 [0,148, 0,249] | 0,092 [0,031, 0,161] | ni utež |

Ownerjeve odločitve (19. 8.): **samo bonusi ≥ 1,0** (napadalčev `objective`
−0,330 zato ne postane kazen, ampak ×1,00); **razdalja nikoli ne točkuje**;
`gib`/`revive` na ×1,00. Rezultat: 40,7 % ubojev je natanko ×1,00 — ownerjev
»filler kill je navaden kill«.

### 9.4 Kaj se je izmerilo

| meritev | v5 | v6 |
|---|---:|---:|
| razpon ocene (mediana / p90 / max) | 2,10 / 4,14 / 13,04 | 1,19 / 1,53 / 2,19 |
| ⚠️ zanesljivost je iz **končnega** teka; vmesni tek je dal 0,729 — razlika je posledica determinizma (`ORDER BY` v poizvedbi, 200 ponovitev namesto 20) | | |
| zanesljivost (kontrola po vlogi) | **0,260** [−2,08, 0,81] | **0,755** [0,07, 0,93] |
| ⚠️ intervali so **Spearman-Brown transformirani**, zato lahko sežejo pod −1: transformacija `2r/(1+r)` pri r blizu −1 divergira. Beri jih kot »ni merljivega signala«, ne kot velikost. | | |
| zanesljivost samo napadalec | 0,508 | **0,716** |
| zanesljivost samo branilec | −0,119 | 0,429 |
| napoved zmagovalca runde | 67,71 % | **69,12 %** |
| McNemar proti golemu štetju (66,93 %) | 45 : 40, p = 0,588 | **30 : 16, p = 0,039** |

⭐ **v6 je prva utež v tej raziskavi, ki prekaša golo štetje ubojev.**

### 9.5 Kar je treba povedati zraven (in v UI)

1. **Prednost ni dokazana, je obetavna.** Bootstrap čez runde: +2,42 o. t.,
   95 % CI **[−0,00, +5,02]** — spodnji rob se dotika ničle. Leave-one-map-out
   je sicer pozitiven na vseh desetih mapah (+1,47 do +2,65 o. t.), kar govori
   proti temu, da bi šlo za eno samo mapo.
2. **Zanesljivost je ocenjena na 15 igralcih** in ima zato zelo širok interval.
   Edina os s tesnim intervalom je `answered` (0,861 [0,54, 0,96]).
3. **Na braniteljski strani KIS ne loči igralcev** — ne v5 (−0,12) ne zanesljivo
   v6: ocena niha med 0,02 in 0,43, odvisno od praga vzorca. Braniteljsko
   številko je treba objaviti kot še-ne-merljivo.
4. Prva izvedba z 20 ponovitvami je dala 0,735 in 0,662 v dveh tekih — ker
   poizvedba ni imela `ORDER BY` in je vrstni red vrstic vplival na delitev.
   Popravljeno (`ORDER BY`, 200 ponovitev, CI); vsak, ki bo to ponavljal, naj
   preveri determinizem, preden verjame tretji decimalki.

### 9.6 Kaj sledi

Skript `scripts/backtest_kis_v6.py` (razdelki A–J) reproducira vse zgornje
številke in izpiše razsodbo proti vnaprej postavljenim pragovom. Formula se
**ne** spreminja, dokler owner ne potrdi, da so opozorila iz §9.5 sprejemljiva.


---

## 10. Dopolnitev po inventarju vzporednega agenta (isti dan)

Vzporedni agent je pregledal preostale proximity tabele in našel tri per-kill
signale, ki jih noben multiplikator ne pokriva. Vsi trije so šli v isti model.

| nova os | vir | ATT coef [CI] | DEF coef [CI] | izid |
|---|---|---|---|---|
| `revenge` (uboj je bil maščevanje) | `proximity_lua_trade_kill` (Lua `checkTradeKill`, okno 3 s) | −0,023 [−0,117, 0,081] | 0,007 [−0,099, 0,109] | ⛔ pade |
| `clean_pick` (žrtev ni zadela nazaj) | `reaction_metric.return_fire_ms IS NULL` | 0,060 [−0,016, 0,140] | **0,078 [0,021, 0,146]** | ✅ samo branilec, ×1,08 |
| `long_duel` (>3 s) | `reaction_metric.duration_ms` | 0,056 [−0,011, 0,134] | 0,024 [−0,040, 0,094] | ⛔ pade |

`revenge` je **neodvisna druga pot** do iste ideje kot `stood` (prva je izpeljana
v parserju, druga je server-side Lua). Ko je `stood` v modelu, `revenge` ne
prispeva ničesar — kar je pravilna razlaga: maščevalni uboj je pogosto tudi sam
vrnjen. Pravilo dveh poti je s tem izpolnjeno.

⚠️ `clean_pick` **ni** »brez odpora«: Lua zahteva, da je žrtev zadela prav
svojega napadalca, zato v isti koš padeta »instanten pick« in »žrtev je vse
zgrešila«. Koeficient je majhen (×1,08) in tako ga je treba tudi opisati.

### Končna tabela v6 (6 osi)

| | napadalec | branilec |
|---|---|---|
| `wave` (faza vala) | β = 0,179 → do ×1,43 | ×1,00 |
| `stood` (uboja niso vrnili) | ×1,31 | ×1,00 |
| `crossfire` | ×1,17 | ×1,00 |
| `isolation` | ×1,00 | ×1,19 |
| `objective` | ×1,00 | ×1,37 |
| `clean_pick` | ×1,00 | ×1,08 |

Vse ostalo ×1,00. 28,8 % ubojev je natanko ×1,00.

### Rezultat s šesto osjo

| meritev | v5 | v6 |
|---|---:|---:|
| zanesljivost (kontrola po vlogi) | 0,260 | **0,756** [0,10, 0,93] |
| samo napadalec | 0,508 | **0,716** |
| napoved zmagovalca runde | 67,71 % | **69,75 %** |
| McNemar proti štetju (66,93 %) | 45 : 40, p = 0,588 | **31 : 13, p = 0,007** |
| leave-one-map-out (v6 − štetje) | — | +2,20 do +3,36 o. t., **pozitiven na vseh 10 mapah** |

⚠️ Opozorili iz §9.5 **ostajata**: bootstrap CI razlike je [+0,00, +4,70] —
spodnji rob se še vedno dotika ničle; braniteljska zanesljivost na igralca pa
niha (0,38 / −0,20 / 0,01 / 0,01 pri pragovih 100/150/200/300 ubojev) in je
treba objaviti kot **nemerljivo pri tem vzorcu**.

Znani artefakt: `carrier` pri napadalcu ima coef −17,6, ker je v vzorcu **en
sam** tak uboj (popolna separacija). CI zajame ničlo, zato os pade na ×1,00 —
izid je pravilen, številka pa je smeti in ne sme nikamor v razlago.


---

## 11. Carrier kontekst — ownerjeva ideja, izmerjena

Skript: `scripts/backtest_carrier_context.py` (READ-ONLY, razdelki A–J).
Vzorec: 34.597 ubojev / 638 rund, 2.568 carry dogodkov v 493 rundah,
1.190 nosilcev z rekonstruirano potjo (`player_track.path`).

### 11.1 Najprej motnja, šele nato učinek

**Carry sam napove rundo:** v rundah s carry-jem napadalec zmaga **73,6 %**,
brez njega **40,0 %**. Vsaka surova številka o »escort ubojih« je večinoma to.
Zato je pravilna primerjalna osnova *isti igralec, ista vloga, ista runda, a
uboj izven carry okna*: napadalec 68,64 %, branilec **33,92 %**.

⛔ In izid carry-ja je endogen: escort uboji med carry-jem, ki se je končal
`secured`, napovedo zmago v **99,8 %** — ker je bil objektiv zavarovan, zato je
bila runda dobljena. Izid carry-ja **ni nikoli vhod**, le diagnostika.
⚠️ Ta diagnostika šteje **escort uboje** po izidu carry-ja (564 / 575 / 443), ne
carry-jev samih (secured 342 / dropped 1.383 / killed 822) — enot ne mešaj.

### 11.2 Učinki po vlogi, na treh nivojih kontrole

| kategorija | n | delež | surovo | v carry rundi | + izenačeno št. živih |
|---|---:|---:|---:|---:|---:|
| escort uboj (mi nosimo), napadalec | 1.593 | 4,6 % | +13,4 | +9,8 | **+6,3** |
| nosilčev lastni uboj, napadalec | 576 | 1,7 % | +10,0 | +6,4 | **+4,6** |
| **branilec ubije nosilca** | 799 | 2,3 % | +3,3 | +10,3 | **+9,8** |
| branilec ubije koga drugega med njihovim carry-jem | 2.215 | 6,4 % | −9,6 | −2,6 | **−2,8** |

⭐ **Popravek prve ocene:** uboj nosilca sem sprva primerjal z globalno osnovo
branilca (41 %) in dobil +2,8 o. t. To je bila napačna primerjava — ko nasprotnik
nosi, branilec **izgublja** (osnova 33,9 %). Proti pravi osnovi je uboj nosilca
**+9,8 o. t.**, torej najmočnejši kontrolirani učinek v celotni raziskavi.

### 11.3 Bližina nosilcu (ownerjeva teza »če si v proximity, mu pomagaš«)

1.358 od 1.593 escort ubojev (85 %) ima znano razdaljo do nosilca; mediana 885 u
(22 m). Proti osnovi 68,64 % (izenačeno 67,82 %):

| pas | n | zmaga | odklon | izenačeno |
|---|---:|---:|---:|---:|
| < 500 u (< 13 m) | 318 | 78,0 % | +9,4 | +5,1 |
| **500–1200 u (13–30 m)** | 567 | **81,5 %** | **+12,8** | **+8,6** |
| 1200–2500 u | 366 | 77,3 % | +8,7 | +5,9 |
| > 2500 u | 107 | 73,8 % | +5,2 | +3,6 |

Ownerjeva intuicija drži, a jo meritev izostri: koristni escort ni lepljenje na
nosilca, ampak **čiščenje prostora na 13–30 m**. ⚠️ Pristranost: escort uboji
brez nosilčeve poti (n=235) zmagajo 75,3 % proti 78,9 % s potjo — manjkajoči so
nekoliko slabši, kar razdaljni os rahlo napihne.

### 11.4 Model z vsemi osmi hkrati (kontrola prevlade, cluster bootstrap)

| os | napadalec | branilec |
|---|---|---|
| **`escort_any`** | **0,588 [0,336, 0,851] → ×1,80** ✅ | ni primerov |
| `escort_band` (500–1200 u) | 0,257 [−0,035, 0,575] ⛔ | — |
| `stop_kill` (ubil nosilca) | n=5 | 0,062 [−0,170, 0,293] ⛔ |
| `trade_carrier` | n=185, negativen ⛔ | ni primerov |
| `wave_z` | 0,155 [0,100, 0,224] ✅ | 0,065 [−0,009, 0,135] ⛔ |
| `stood` | 0,283 [0,193, 0,360] ✅ | ⛔ |
| `crossfire` | 0,160 [0,028, 0,295] ✅ | ⛔ |
| `isolation` | ⛔ | 0,171 [0,075, 0,258] ✅ |
| `objective` | −0,311 (negativen → ×1,00) | 0,310 [0,090, 0,511] ✅ |
| `clean_pick` | ⛔ | 0,072 [0,016, 0,137] ✅ |

⭐ **`escort_any` je najmočnejša os v celotnem sistemu (×1,80)** in preživi ob
vseh drugih ter ob kontroli prevlade.

Dve pomembni negativni ugotovitvi:
- **razdaljni pas ne doda ničesar** nad golo zastavico »escort uboj« — enostavna
  zastavica je dovolj, razdalja ostane opisna;
- **uboj nosilca ne preživi modela** (branilec 0,062, CI čez ničlo), čeprav je
  surovo +9,8 o. t. — ker ga `objective` že zajame: nosilca ubijaš na objektivu.
  Torej ni neodvisna os, je ista os z drugim imenom.

### 11.5 Ne-ubojni del (za PWC, ne za KIS)

- kritni damage v carry oknih: **41.019 dogodkov / 877.539 škode**
- škoda naravnost **na nosilca**: 8.116 zadetkov / 169.008 škode na 790 carry-jih
- carry-ji, ki so prejeli škodo: 1.278 → nosilec ubit 799, preživel 479
  (podlaga za os »skoraj smo ga ustavili«)
- trade za nosilca (ubil tistega, ki je v 5 s poškodoval našega nosilca):
  **le 185 primerov**, izenačeno −0,2 o. t. → premalo in brez učinka
- ⛔ **`proximity_shot_fired` ni uporaben za primerjavo igralcev**: pokritost je
  neenakomerna po mapah (et_brewdog 45,1 % … etl_adlernest 70,8 %), zato je
  število strelov med igralci neprimerljivo. Ostane opisno.

### 11.6 Napaka v prvem teku (zapisana, da se ne ponovi)

Prva izvedba je pri zveznih oseh **seštevala vrednosti namesto štela sprožitve**
(`sum(fn(k))` namesto `sum(1 for k if fn(k))`), zato je `wave_z` dobil »−22
killov« in bil izločen kot premalo pogost. Popravljeno; verdikt se je s tem
spremenil. Vsak prag na številu primerov mora šteti, ne seštevati.
