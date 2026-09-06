# Novi dizajn spletne strani — pregled

**Datum pregleda:** 23. 8. 2026 · **Predmet:** `Slomix design refresh discussion2.zip`
**Status:** zapiski, nič ni implementirano · **Dokumenti:** [01 preverjene trditve](01_PREVERJENE_TRDITVE.md) ·
[02 po zaslonih](02_PO_ZASLONIH.md) · [03 tokeni in stil](03_TOKENI_IN_STIL.md) ·
[04 izvedbeni načrt](04_IZVEDBENI_NACRT.md)

---

## Kaj je prišlo

V korenu projekta sta **dva** arhiva design bota:

| Arhiv | Čas | Datotek | Kaj je notri |
|---|---|---|---|
| `Slomix design refresh discussion.zip` | 22. 8. 04:23 | 25 | 7 zaslonov |
| `Slomix design refresh discussion2.zip` | 22. 8. 04:41 | 26 | **8 zaslonov** — doda `landing.dc.html`, prepiše `home.dc.html` (14,3 → 25,2 KB) |

`README.md` in `support.js` sta v obeh arhivih **bajt-identična** (isti md5). To pomeni:
README opisuje **staro** domačo stran in landing strani sploh ne pozna. Kjer se README in
`home.dc.html` ne ujemata, velja prototip.

Razpakirano je tu (ne v gitu, ker nosi 5,2 MB slik):

```
/home/samba/share/slomix-archive/design_handoff_2026-08-22/design_handoff_slomix_redesign/
cd .../prototypes && python3 -m http.server 8899   # potem odpri home.dc.html
```

Prototipi so `.dc.html` — HTML z lastnim runtimeom (`support.js`, 69 KB, razred `DCLogic`,
`<sc-for>`, `{{ }}`). README to sam pove: **`support.js` se ne prenaša**, to so reference,
ne koda.

---

## Sodba

Predaja je **nenavadno dobra**. Ni moodboard — je specifikacija. Tri stvari jo ločijo od
običajnega "design bot je nekaj naredil":

1. **Preverljive trditve.** Ko reče "escaped = 300 enot za 5 sekund", to res piše v
   `proximity/lua/proximity_tracker.lua:70-71`. Preveril sem trinajst takih konstant in
   endpointov; večina drži do bajta (limiti uploadov, prag 6 igralcev, štirje statusi,
   `/api/build` polja, vseh sedem proximity metrik).
2. **Razume našo domeno.** Score na session-detail je Team A / Team B, ne Allies / Axis, ker
   se strani vsako mapo zamenjajo — to je točno tisto, kar se v obstoječi strani ponavlja
   narobe. Prav tako: sekcija za popolnost podatkov, "vsaka številka proti tvojemu lastnemu
   30-dnevnemu povprečju", "kar ni ožičeno, naj piše neznano, ne nič".
3. **Sam pove, kje ugiba.** V `proximity.dc.html` piše: *"Speed bands — defaults chosen here;
   tell me the real cut-offs and I'll change them."* To je pošteno in redko.

Kar predaja **zamolči**, pa je dražje od tega, kar zna: nekaj trditev o naši arhitekturi je
napačnih, in ena od njih premakne oceno dela za red velikosti.

---

## Pet stvari, ki jih moraš vedeti, preden se karkoli začne

### 1. React ni produkcija — 4 route od 31

README pravi: *"recreate these designs in the Slomix web front end using its existing
environment: React 19 + TypeScript + Vite under `website/frontend/`"*.

V `website/js/route-registry.js` je **4 MODERN in 27 LEGACY**. React v živo poganja natanko
`proximity-player`, `proximity-replay`, `proximity-teams` in `skill-rating`. Vseh pet
zaslonov, ki jih predaja hoče prerisati — Home, Session detail, Proximity, Uploads,
Availability — je v produkciji **legacy vanilla JS**.

React različice teh strani **obstajajo** (26 strani, 11.245 vrstic), samo nič jih ne kliče.
Vir zmote je najbrž `website/frontend/src/runtime/catalog.ts`, ki trdi `mode: 'modern'` za 19
rout — a je zastarel artefakt, ki hrani samo dev preview.

To ni malenkost: **"prerisati v React" pomeni najprej prižgati React**, in to je ločena,
tvegana selitev, ne dizajnersko delo. Podrobnosti in tri poti naprej so spodaj.

### 2. Barve strani so pripisane viru, ki jih nima

README: *"Faction/side colours (from `website/js/replay.js`): Allies `#8bb0d6`, Axis `#d1857c`"*.

Ti dve vrednosti v repotu **ne obstajata**. `replay.js:827` ima `#3b82f6` / `#ef4444`, kanon
je `proximity.js:112-115` (`TEAM_COLORS`). Kot **izbira** sta novi barvi v redu — mirnejši
sta in se ujemata s paleto. Kot **navedba vira** je izmišljena, in to je edino mesto, kjer
sem predajo ujel pri navajanju neobstoječe kode.

Praktična posledica: sprememba barv strani ni "prevzem obstoječega", ampak sprememba, ki se
mora zgoditi na štirih mestih v `replay.js` in v `proximity.js` — sicer bo replay risal
drugačno modro kot ostala stran.

### 3. Hitrostno obarvane poti so poceni — podatki že tečejo

To je edino veliko presenečenje v našo korist. `player_track.path` že nosi `speed` in `sprint`
na vzorec (preverjeno v bazi: `{"x":-3771.8,...,"speed":352,"sprint":1}`),
`proximity_journey.py:33-53` ju že prenaša do brskalnika, risanje ene poti na life pa že
obstaja v `proximity.js:2709` (`drawJourneyLife`).

Danes je barva po **bližini sovražnika** (`journeyDangerColor`, rampa 1500 enot). Za predajo
manjka torej ena funkcija barvne rampe, ne pipeline.

Dve opozorili, ki ju predaja nima:
- `player_track` pokriva **905 rund / 13 map** — realno ~11 map s potmi, ne vse.
- Predlagani pasovi (20/120/240) so ugibanje; edina referenca v kodi je
  `proximity.js:3159` (*"sprint ~300 u/s"*), izmerjeni vzorci pa gredo do 352. Zgornji pas
  mora biti odprt.

### 4. Zemljevidi: prototip pozna 7 map, mi jih imamo 21 — in eno ključno je spustil

`map_transforms.json` ima **21 kalibriranih map** — in predaja to datoteko **priloži v celoti**.
Kljub temu je prototip ročno prepisal sedem map v konstanto `MAP_TRANSFORMS`, in med njimi
**ni `sw_goldrush_te`** — naše 5. najbolj igrane mape (188 rund).

Implementacija naj bere `map_transforms.json` v teku (kot že dela `replay.js:131-140`), ne
prepisuje tabele. Sicer bo vrstica "mape po vrsti" na domači strani imela luknje ob prvem
pravem večeru.

Pozor tudi: alias tabela za imena map obstaja samo v `sessions.js:23-64` in je **nedosegljiva**
iz risalne kode (`proximity.js:176-180` in `replay.js:142-150` ne aliasirata). Zato
`etl_supply`, `sp_delivery_te`, `et_beach` danes 404-ajo, čeprav slika obstaja.

### 5. Nekaj zaslonov ni redizajn, ampak nova funkcionalnost

Predaja jih predstavi kot enakovredne zaslone. Niso:

| Stvar | Stanje |
|---|---|
| Clips stran | **Nova.** `#/clips` ne obstaja. Greatshot video je za prijavo (`_require_user`) in rabi ločen, ročno sprožen render — "auto-cut" ni predvajljiv video. |
| Števec ogledov (`plays`) | **Nov.** Danes obstaja `downloads`. |
| Poster frame na strežniku | **Nov.** Danes se poster zajame v brskalniku, samo za `.mp4` (`uploads.js:485`). |
| Glasovanje o mapah | **Novo.** Danes se glasuje o **imenu ekipe** (`planning.py:767`). |
| Glasovanje o uri začetka | **Novo.** Ne obstaja. |
| Kategorije image / audio / backup | **Nove.** Rabijo vnose v štiri slovarje v `upload_validators.py`. |
| Hitrostni pasovi | **Novi** (a poceni, glej točko 3). |

---

## Velika odločitev: v čem sploh graditi

> ✅ **ODLOČENO 23. 8. 2026: React, zgrajen na novo na dev.**
> Razlogi, zavrnjene alternative in štiri pravila, ki iz tega sledijo, so v
> [05_ODLOCITEV_SKLADA](05_ODLOCITEV_SKLADA.md). Spodnja razprava o treh poteh je ohranjena
> zato, ker vsebuje izmerjene številke, ne zato, da bi se odpirala znova.


To je edina odločitev, ki jo je treba sprejeti pred prvo vrstico kode. Tri poti:

### A) Legacy najprej (najmanj tveganja)

Novi videz uveljavimo v `website/js/` + `index.html`, torej tam, kjer stran **danes res teče**.
Tokeni gredo v `website/tailwind.config.cjs` (v3) in v `css/tailwind.input.css`.

- ➕ Vsak PR je takoj viden na produkciji; ni selitve rout.
- ➕ Ne podvajamo 11.245 vrstic obstoječega Reacta.
- ➖ Delo dela v skladu, ki ga načeloma opuščamo; ob kasnejši selitvi v React se dizajn dela
  drugič.
- Obseg: dotakniti se je treba 213 `glass-card`, 205 `glass-panel`, 277 `font-black` v legacyju.

### B) React najprej (največ tveganja, najboljši končni izid)

Najprej prižgemo React route (`mode: MODERN`), potem v njih delamo dizajn.

- ➕ Delo se dela enkrat, v skladu, ki je prihodnost.
- ➖ Preklop ene rute na React **tiho odvzame podatke**: React `SessionDetail.tsx` je ~38 %
  legacy strani, `Story` ~15 %. Preklop brez izenačitve je regresija za uporabnika.
- ➖ Dva Tailwinda hkrati; tokeni se morajo vzdrževati dvakrat, dokler traja prehod.

### C) Mešano — dizajn najprej tam, kjer je React že živ (priporočam)

Tokeni in tipografija se uveljavijo **v obeh skladih hkrati** (to je itak neizogibno, glej
[03](03_TOKENI_IN_STIL.md)), nato:

1. Novi videz najprej na **štirih route, kjer React že teče** — tam je to čisto dizajnersko
   delo brez selitve (`proximity-player`, `proximity-replay`, `proximity-teams`, `skill-rating`).
2. Vzporedno **legacy** dobi tokene in tipografijo (brez prestrukturiranja postavitve) —
   stran postane enotna, ne da bi karkoli selili.
3. Šele potem, zaslon po zaslon, odločitev "prižgemo React ali prerišemo legacy", **z merilom
   pariteta podatkov**, ne datuma.

Landing stran je posebej dober prvi korak: **je nova**, torej ne ruši ničesar, in je edini
zaslon, ki lahko takoj pokaže cel novi jezik.

---

## Kaj sem pri tem našel o nas samih (ne o dizajnu)

Številke na strani `about.dc.html` so dobesedno prepisane iz našega `README.md`
(vrstice 19-20, 37-44, 180-186). Meritev na dev bazi kaže, da **README šteje tudi vrstice
`round_number = 0`** — znano past R0, ki podvaja kille in damage:

| | README / About | dev, R1+R2 | dev, vse vrstice |
|---|---|---|---|
| kills | 230.343 | 122.226 | 238.561 |
| headshot kills | 49.918 | 27.221 | 52.589 |
| revives | 26.412 | 14.535 | 28.083 |
| rounds | 2.987 | 2.105 (1.991 brez botov) | 3.114 |

Meritev je z dev baze; pred kakršnokoli objavo jo je treba ponoviti na produkcijski. Če se
potrdi, je popraviti **README**, ne dizajn — in About stran naj številke bere v živo
(`round_number IN (1,2)`, brez bot rund), ne prepisuje.
