# TASK: Redesign ET Rating / Skill Rating stran

## Kontekst

Slomix.fyi je ET:Legacy stats platforma. ET Rating stran (/#/skill-rating) prikazuje leaderboard individualnih performancnih ocen igralcev. Rating temelji na 9 percentile-normalized metrikah, podobno HLTV 2.0 / Valorant ACS sistemu.

Trenutna stran je funkcionalna ampak zelo basic — dolgocasna flat tabela brez vizualne privlacnosti ali storytellinga. Potrebuje redesign.

## Kaj stran trenutno prikazuje

### 1. Header sekcija
- Naslov "ET Rating" z "EXPERIMENTAL" oznako
- Kratek opis: "Individual performance rating based on percentile-normalized stats across 9 metrics"
- "Formula" dropdown gumb (ki razkrije formulo)

### 2. Top Rated Player hero kartica
- Krozni progress ring z ratingom (0.887)
- Ime igralca, tier badge (ELITE), stevilo rund
- 3 highlight metrike kot pills: "DPM 98%", "Survival 98%", "Accuracy 94%"

### 3. Leaderboard tabela
- Stolpci: RANK, PLAYER, RATING, TIER, ROUNDS
- 27 igralcev
- Klik na vrstico razsiri percentile breakdown z barvnimi barovi (9 metrik)
- Tier badges: ELITE (zlato), VETERAN (zeleno), EXPERIENCED (cyan), REGULAR (sivo), NEWCOMER (sivo/dimmed)

### 4. Percentile breakdown (expandable per player)
- Krozni ring z ratingom
- 9 horizontalnih barov:
  - DPM, Deaths/Round, Kills/Round, Accuracy, Revives, Survival, Objectives, Useful Kills, Denied Time
  - Barve: rumena (visok percentile), cyan (nizek ali deaths)
  - Procent na desni strani

## UX problemi ki sem jih identificiral

### Problem 1: Tabela je dolgocasna in nepregledna
Flat tabela z 27 vrsticami, kjer je vecina podatkov skrita za klik. Med "bronzelow-" (0.747, 1048 rund) in "Peep" (0.708, 15 rund) ni vizualne razlike — obadva sta VETERAN. Ampak eden igra 3 leta, drug 15 rund.

### Problem 2: Tiers nimajo vizualne moci
ELITE/VETERAN/EXPERIENCED/REGULAR/NEWCOMER so samo barvni badgi. Ni obcutka progresije ali prestiza. Ko imas 300 igralcev, bo 150 REGULAR brez razlikovanja.

### Problem 3: Hero kartica je premalo informativna
Top rated player hero prikazuje samo 3 od 9 metrik. Uporabnik ne vidi "zakaj" je ta igralec najboljsi. Radar chart ali spider diagram bi takoj pokazal profil.

### Problem 4: Ni filtriranja ali sortiranja
Ne mores filtrirati po tieru, sortirati po posamezni metriki, ali iskati igralca. Ko bo 300 igralcev, to ne gre.

### Problem 5: Sredina tabele je prazna
Med imenom igralca in ratingom je ogromna prazna vrstica. Ta prostor bi lahko uporabil za mini vizualizacijo (sparkline, radar, contribution breakdown).

### Problem 6: Ni casovne dimenzije
Ne vidis ali nekdo napreduje ali nazaduje. Ali je rating stabilen ali volatilen. Za 27 igralcev gre, za 300 bo folk hotel vedeti trende.

### Problem 7: "Rounds" stolpec ne pomeni nic brez konteksta
Igralec z 6 rundami in 0.643 ratingom (G4rch4) je povsem drugacen od igralca z 1754 rundami in 0.618 (olz). Zanesljivost ratinga ni prikazana.

## Podatki ki so na voljo iz API-ja

### Endpoint: /api/skill/leaderboard?limit=50
Vrne za vsakega igralca:
- rank, display_name, et_rating, games_rated, last_rated_at
- components objekt z 9 metrikami, vsaka ima: raw, weight, percentile, contribution

### Endpoint: /api/skill/formula
Vrne:
- ime, opis, formula string
- constant: 0.15
- weights za vseh 9 metrik
- min_rounds: 5
- opise metrik

### Primer podatkov za enega igralca (components):
```json
{
  "dpm": {"raw": 519.031, "weight": 0.18, "percentile": 0.981, "contribution": 0.1767},
  "dpr": {"raw": 10.279, "weight": -0.12, "percentile": 0.019, "contribution": -0.0022},
  "kpr": {"raw": 14.721, "weight": 0.15, "percentile": 0.87, "contribution": 0.1306},
  "accuracy": {"raw": 41.325, "weight": 0.05, "percentile": 0.944, "contribution": 0.0472},
  "revive_rate": {"raw": 1.131, "weight": 0.12, "percentile": 0.611, "contribution": 0.0733},
  "survival_rate": {"raw": 0.709, "weight": 0.1, "percentile": 0.981, "contribution": 0.0981},
  "objective_rate": {"raw": 0.361, "weight": 0.12, "percentile": 0.944, "contribution": 0.1133},
  "useful_kill_rate": {"raw": 0.277, "weight": 0.1, "percentile": 0.611, "contribution": 0.0611},
  "denied_playtime_pm": {"raw": 46.209, "weight": 0.06, "percentile": 0.648, "contribution": 0.0389}
}
```

### Trenutna tier distribucija (27 igralcev):
- ELITE: 1 (rating >= 0.85)
- VETERAN: 5 (rating >= 0.70)
- EXPERIENCED: 5 (rating >= 0.55)
- REGULAR: 12 (rating >= 0.40)
- NEWCOMER: 4 (rating < 0.40)

### Rounds distribucija:
- Min: 6, Max: 1754, Avg: 478
- Rating range: 0.117 do 0.887

## Formula
ET_Rating = 0.15 + sum(weight_i * percentile(metric_i))

Weights (po tezi):
- DPM: 0.18 (najvecja)
- Kills/Round: 0.15
- Deaths/Round: -0.12 (kazen!)
- Revives: 0.12
- Objectives: 0.12
- Survival: 0.10
- Useful Kills: 0.10
- Denied Time: 0.06
- Accuracy: 0.05 (najmanjsa)

## Redesign predlogi

### 1. Tier-based visual grouping
Namesto flat tabele, vizualno grupiraj po tierih. Vsak tier ima svojo sekcijo z barvo/ikono. ELITE na vrhu z zlatim/premium obcutkom, NEWCOMER spodaj z bolj subtle stilom. Kar pomaga tudi ko bo 300 igralcev — vidis da si "top 5% VETERAN" ne samo "nek rank".

### 2. Mini radar/spider chart v vsaki vrstici
V praznem prostoru med imenom in ratingom poakzi mini radar z 9 tockami. Takoj vidis "profil" igralca — ali je all-rounder, ali specialist (visok DPM ampak nizek survival), ali medic main (visoke revives).

### 3. Confidence/reliability indikator
Ob ratingu pokazi kako zanesljiv je — igralec s 6 rundami bi imel siroko confidence interval / dimmed rating, igralec z 1754 rundami pa trdno stevilko. Lahko kot sirsi/ozji ring okoli ratinga, ali kot opacity, ali kot tooltip.

### 4. Contribution stacked bar
Namesto ali poleg ratinga pokazi stacked horizontal bar ki vizualizira koliko vsaka metrika PRISPEVA k skupnemu ratingu. Vidis da squazetest2026 ima 0.887 od tega 0.177 iz DPM, 0.131 iz kills, -0.002 iz deaths itd. To pove VEC kot sam rating number.

### 5. Search + filter + sort
- Search box za iskanje igralca
- Filter po tieru (klikni na VETERAN da vidis samo veterane)
- Sortiranje po posamezni metriki (klikni "DPM" header da sortiras po DPM percentilu)

### 6. Animirani hero sekcija
Top 3 players namesto samo top 1 — "podium" stil ali 3 kartice. Vsak s spider chartom. To naredi stran bolj vizualno zanimivo in daje cilj vecim igralcem ("hocm v top 3").

### 7. Player card redesign
Ko kliknes na igralca v tabeli, namesto simple percentile barov pokazi polno kartico:
- Spider/radar chart (9 osi)
- Stacked contribution bar
- "Strongest: DPM (98th percentile)" in "Weakest: Deaths (2nd percentile)"
- Morda primerjava z povprecjem ali s prejsnjim/naslednjim v ranku

### 8. Mobile-friendly cards
Na mobilnih napravah tabela ne dela. Pretvori v kartice z enim igralcem per kartica, ki vsebuje mini radar in rating ring.

## Tehnicni detajli

### Stil platforme
- Dark theme (bg ~#0f1729)
- Neon barvne kartice (cyan, green, yellow, magenta borders)
- Font: Space Grotesk
- Tailwind CSS
- Chart.js ze vkljucen na strani

### Trenutna implementacija
- Stran je v js/skill-rating.js (ali podobno ime — route je skill-rating)
- Leaderboard se renderira kot HTML tabela z expandable rows
- Percentile bars so custom CSS (ne chart.js)

### API endpointi
- GET /api/skill/leaderboard?limit=50 — vrne vse igralce z components
- GET /api/skill/formula — vrne formulo, weights, opise

### Tier barve (trenutne)
- ELITE: gold/amber (#f59e0b border, zlat ring)
- VETERAN: green (#22c55e)
- EXPERIENCED: cyan (#06b6d4)
- REGULAR: gray (#6b7280)
- NEWCOMER: dim gray

## Vsi igralci za referenco

| Rank | Player | Rating | Tier | Rounds |
|------|--------|--------|------|--------|
| 1 | squazetest2026 | 0.887 | ELITE | 61 |
| 2 | //^?/M.Demonslayer | 0.753 | VETERAN | 21 |
| 3 | bronzelow- | 0.747 | VETERAN | 1048 |
| 4 | vid | 0.717 | VETERAN | 1674 |
| 5 | Peep | 0.708 | VETERAN | 15 |
| 6 | SuperBoyy | 0.704 | VETERAN | 1606 |
| 7 | G4rch4 | 0.643 | EXPERIENCED | 6 |
| 8 | -slo.carniee- | 0.624 | EXPERIENCED | 1222 |
| 9 | olz | 0.618 | EXPERIENCED | 1754 |
| 10 | Zlatorog | 0.600 | EXPERIENCED | 79 |
| 11 | ^fnx | 0.592 | EXPERIENCED | 15 |
| 12 | s&o.lgz | 0.545 | REGULAR | 1426 |
| 13 | Cru3lzor. | 0.539 | REGULAR | 426 |
| 14 | //^?/M.Gekku | 0.537 | REGULAR | 15 |
| 15 | i p k i s s | 0.536 | REGULAR | 12 |
| 16 | endekk | 0.527 | REGULAR | 1158 |
| 17 | immoo | 0.491 | REGULAR | 85 |
| 18 | v_kt_r | 0.472 | REGULAR | 646 |
| 19 | .wjs | 0.467 | REGULAR | 832 |
| 20 | -C3jZi | 0.462 | REGULAR | 6 |
| 21 | XI-WANG | 0.452 | REGULAR | 695 |
| 22 | konrad! | 0.443 | REGULAR | 15 |
| 23 | //^?/M.rAzzdOG | 0.439 | REGULAR | 21 |
| 24 | Imbecil | 0.322 | NEWCOMER | 7 |
| 25 | MrAvAc | 0.193 | NEWCOMER | 6 |
| 26 | KaNii | 0.175 | NEWCOMER | 44 |
| 27 | Rakun | 0.117 | NEWCOMER | 21 |
