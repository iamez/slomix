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

### V1 — popolna telemetrija: **✅ ŽE DOSEŽENO** (in bolje, kot si owner misli)

Lua `proximity_tracker.lua` vzorči **vsakih 200 ms** in za vsak vzorec zapiše:

```
time, x, y, z, health, speed, weapon, stance, sprint, event
```

To ni "približno kje je igralec" — to je **kje je, s koliko življenja, s katerim orožjem, v kateri drži, ali sprinta in kaj se mu je ravno zgodilo.** Točno V1.

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

To **je** ocena odločitve: kako naravnost je šel, ali je šel sam v contested prostor, koliko sovražnikov je bilo blizu. Manjka samo, da isto logiko razširimo z inženirja na **vsak gib** — vsi vhodni podatki (pozicije, zdravje, soigralci, sovražniki, faza) so že v `player_track.path`.

---

## 3. Predlog: Decision Quality Layer (DQL)

Trije gradniki, vsak samostojno uporaben. **Nobeden ne zahteva sprememb Lua** — vse računamo iz obstoječih poti.

### DQL-1 — Kontekst giba (temelj)

Za vsak 200 ms vzorec izračunamo (offline, ob importu):
- razdalja do najbližjega objectiva in ali se mu **približuje ali oddaljuje**;
- št. soigralcev/sovražnikov v radiju (že imamo pozicije vseh);
- ali je sam (`isolation`) — ownerjeva lurk os;
- ali je v znanem chokepointu (izpeljemo iz movement heatmap gostote).

Rezultat: iz "kje je" dobimo **"v kakšni situaciji je"**.

### DQL-2 — Ocena odločitve

Za vsak **dogodek** (kill, smrt, plant, revive, push) primerjamo kontekst tik pred njim s tem, kar se je zgodilo po njem:

| Odločitev | Dobra, če… | Slaba, če… |
|-----------|-----------|-----------|
| Push naprej | ekipa sledi (cohesion pade < X), pridobiš prostor/objective | greš sam, umreš, ekipa izgubi prostor (že merimo kot useless-defense) |
| Zadrževanje / lurk | ustvariš priložnost soigralcem (enabler/gravity) | pasivnost brez učinka |
| Sacrifice | umreš, a ekipa v naslednjih N sekundah napreduje | umreš brez posledice |
| Objective run | `path_efficiency` visok, timing usklajen z ekipo | contested_solo brez podpore |

Ownerjev "sacrifice, ki nastavi priložnost" postane **merljiv**: smrt + napredek ekipe v oknu po njej = pozitivna odločitev, ne minus v K/D.

### DQL-3 — Fazna zavest (rabi V2 dopolnitev)

Rundo razrežemo na faze iz objective dogodkov (`OBJECTIVE_RUNS`, `CONSTRUCTION_EVENTS`, carrier): *"pred prvim plantom"*, *"med escortom"*, *"po padcu prve ovire"*. Vsaka odločitev se ocenjuje glede na fazo — kill v mrtvem času ni isto kot kill 10 s pred iztekom pri zadnjem objectivu.

---

## 4. Prioritete (predlog vrstnega reda)

| Prio | Ukrep | Zakaj prvi | Napor |
|------|-------|-----------|-------|
| **1** | `et_brewdog` (+ manjkajoče) v `objective_zones.json` | 45 rund trenutno šteje kot "brez objectiva" — čista izguba točnih podatkov, majhen napor | S |
| **2** | DQL-1 kontekst giba (izolacija, približevanje objectivu, lokalna premoč) | temelj za vse ostalo; vhodi že obstajajo | M |
| **3** | Razširi `OBJECTIVE_RUNS` logiko na vse igralce (ne samo inženirje) | dokazano deluje, samo posplošitev | M |
| **4** | DQL-2 ocena odločitev + "sacrifice score" | ownerjeva osrednja želja; hrani LURK/OBJECTIVE osi Passporta | L |
| **5** | DQL-3 faze runde | največ dodane vrednosti, a rabi 1+3 | L |
| **6** | Puran Lua redeploy (aim-lock clamp) | ni blokada za DQL, a čisti podatke | S (owner-gated) |

---

## 5. Kaj NE potrebujemo

- **Ne rabimo novega Lua zajema.** Vse zgoraj se izračuna iz obstoječih 223 MB poti. Lua spremembe pomenijo redeploy na puran in tveganje — brez potrebe.
- **Ne rabimo več podatkov, rabimo več pomena.** Zajemamo ~3.400 zapisov na rundo in jih prikazujemo kot povprečja. Vrzel je interpretacija, ne zajem.
- **Ne rabimo dohitevati gibhuba pri log-statih.** Oni imajo XP/stance/shove iz logov; mi imamo prostor in čas, ki ga oni **ne morejo** imeti. DQL je nekaj, česar iz strežniških logov ni mogoče izpeljati.

---

## 6. Vprašanja za ownerja

1. **et_brewdog koordinate**: jih lahko izluščim iz .pk3 (kot za ostalih 14 map), ali imaš raje ročno preverjene?
2. **"Dobra odločitev"** — se strinjaš z definicijo *"kar poveča verjetnost zmage runde"*, ali imaš drugačen občutek (npr. tudi "kar je lepo za gledat")?
3. **Sacrifice okno**: koliko sekund po smrti še šteje kot "posledica moje smrti"? (predlog: 10 s, kot carrier chain)
4. **Fazna delitev**: naj jo izpeljem avtomatsko iz objective dogodkov, ali želiš ročno definirane faze per mapa?
5. **Prikaz**: naj DQL najprej pride kot Discord izpis (`!decisions`), ali kot API + tvoj obstoječi /proximity/ panel?
