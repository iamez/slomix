# TASK: Redesign Round Selector za Proximity Intelligence modul

## Kontekst

Slomix.fyi je ET:Legacy stats platforma. Proximity Intelligence je prototip modul ki analizira bližino/engagement med igralci. Ima 3-stopenjski scope filter: **SESSION → MAP → ROUND**. Problem je v ROUND selectorju.

## Problem — kaj uporabnik vidi danes

Trenuten Round selector je navaden `<select>` dropdown. Ko izbereš mapo sw_goldrush_te na dan Mar 25, 2026, dobiš **26 rund** v flat listi:

```
All rounds
R2 • 01:33 AM (189 ev)
R2 • 01:44 AM (95 ev)
R1 • 01:49 AM (16 ev)
R2 • 01:51 AM (13 ev)
R1 • 01:53 AM (11 ev)
R2 • 01:54 AM (11 ev)
... 20 more ...
```

Vse izgledajo enako. Uporabnik nima pojma **katera runda je bila "prava igra"** in katera je bil 59-sekundni warmup z 11 eventi. Ni nobenega vizualnega signala.

## Zakaj je to kritično za skaliranje

Danes je 30 aktivnih igralcev. Ko bo 300 igralcev in 10+ iger goldrush na dan, bo ta dropdown imel 50+ identično izgledajočih vnosov. Popolnoma neuporabno.

## Podatki ki so na voljo iz API-ja

Endpoint: `/api/proximity/scopes?range_days=365`

Za vsako rundo imaš:
- `round_number` (1 ali 2)
- `round_start_unix` (unix timestamp)
- `round_end_unix` (unix timestamp)
- `engagements` (število proximity eventov)

Iz tega se da izračunati:
- **Trajanje runde** (end - start) — od 55 sekund do 12 minut
- **Engagement gostota** — engagements per minute
- **Časovne vrzeli med rundami** — gap med eno in naslednjo rundo

## Analiza dejanskih podatkov (goldrush, Mar 25)

26 rund se naravno grupira v **4 časovne gruče** (clustere) z >10min vrzelmi med njimi:

| Cluster | Čas (UTC) | Rund | Engagements | Opis |
|---------|-----------|------|-------------|------|
| 1 | 00:33 – 01:10 | 19 | 605 | Jutranja sesija — 19 rund v 37min, večina warmup/kratkih (pod 2 min), samo par pravih |
| 2 | 01:44 – 01:49 | 3 | 40 | Kratka sesija, skoraj vse warmup |
| 3 | 12:45 – 13:09 | 2 | 300 | Popoldanska igra — 2 polni rundi (12 min, 150+ ev vsaka) |
| 4 | 20:37 – 21:01 | 2 | 384 | Večerna igra — 2 polni rundi (12 min, 150-234 ev) |

Od 26 rund jih je **20 krajših od 2 minut** (warmup/aborted) in samo **6 pravih iger** (5+ min).

## UX predlogi

### 1. Grupiranje po časovnih clusterih
Namesto flat liste pokaži gruče: "Morning session (00:33-01:10) — 19 rounds", "Afternoon (12:45-13:09) — 2 rounds", "Evening (20:37-21:01) — 2 rounds". Uporabnik takoj ve kdaj se je igral.

### 2. Vizualna velikost/pomembnost
Runde z več engagementi in daljšim trajanjem naj bodo vizualno večje/bolj poudarjene. Runda z 234 eventi in 12 min trajanja mora izstopati proti rundi z 11 eventi in 59 sekund.

### 3. Filtriranje/dimming warmupov
Runde pod 2 min ali pod 15 eventov označi kot "warmup/short" z dimmed/gray stilom ali skrij za toggle. Večina uporabnikov jih ne bo nikoli želela analizirati.

### 4. Timeline/visual layout namesto dropdown
Razmisli o horizontalnem timeline baru ali card grid namesto `<select>`. Vsaka runda je blokek z: čas, trajanje, event count, morda mini bar za relativno velikost.

### 5. Quick pick
"Biggest round", "Latest full game", "All full games only" kot hitri filtri na vrhu.

## Tehnični detajli

### Value format za select opcije
Format je `round_number|round_start_unix`, npr. `2|1774398788`. To se mora ohraniti za API klice.

### Kaskadni scope selector
Scope selector deluje kaskadno: Session → Map → Round. Ko izbereš mapo, se round lista požene iz `scopes.sessions[].maps[].rounds[]`. Funkcija ki to renderira je `renderScopeSelectors()` v `proximity.js`, ki kliče `setSelectOptions()`.

### Stil platforme
- Dark theme (bg ~#0f1729)
- Neon barvne kartice (cyan, green, yellow, magenta borders)
- Font: Space Grotesk
- Tailwind CSS

## API primer — struktura runde v scopes

```json
{
  "round_number": 2,
  "round_start_unix": 1774471936,
  "round_end_unix": 1774472502,
  "engagements": 234
}
```

## Vsi goldrush rounds za referenco (Mar 25, 2026)

```json
[
  {"rn":2, "start":1774398788, "end":1774399434, "eng":189, "duration_sec":646},
  {"rn":2, "start":1774399450, "end":1774399768, "eng":95, "duration_sec":318},
  {"rn":1, "start":1774399784, "end":1774399843, "eng":16, "duration_sec":59},
  {"rn":2, "start":1774399873, "end":1774399932, "eng":13, "duration_sec":59},
  {"rn":1, "start":1774399983, "end":1774400042, "eng":11, "duration_sec":59},
  {"rn":2, "start":1774400072, "end":1774400127, "eng":11, "duration_sec":55},
  {"rn":1, "start":1774400143, "end":1774400238, "eng":27, "duration_sec":95},
  {"rn":2, "start":1774400143, "end":1774400238, "eng":27, "duration_sec":95},
  {"rn":2, "start":1774400254, "end":1774400322, "eng":17, "duration_sec":68},
  {"rn":1, "start":1774400338, "end":1774400397, "eng":14, "duration_sec":59},
  {"rn":2, "start":1774400428, "end":1774400487, "eng":12, "duration_sec":59},
  {"rn":1, "start":1774400517, "end":1774400621, "eng":31, "duration_sec":104},
  {"rn":2, "start":1774400517, "end":1774400621, "eng":31, "duration_sec":104},
  {"rn":1, "start":1774400637, "end":1774400696, "eng":13, "duration_sec":59},
  {"rn":1, "start":1774400750, "end":1774400809, "eng":17, "duration_sec":59},
  {"rn":2, "start":1774400750, "end":1774400809, "eng":17, "duration_sec":59},
  {"rn":1, "start":1774400833, "end":1774400932, "eng":23, "duration_sec":99},
  {"rn":2, "start":1774400833, "end":1774400932, "eng":23, "duration_sec":99},
  {"rn":1, "start":1774400948, "end":1774401007, "eng":18, "duration_sec":59},
  {"rn":1, "start":1774403066, "end":1774403125, "eng":16, "duration_sec":59},
  {"rn":1, "start":1774403225, "end":1774403284, "eng":10, "duration_sec":59},
  {"rn":2, "start":1774403314, "end":1774403373, "eng":14, "duration_sec":59},
  {"rn":1, "start":1774442728, "end":1774443447, "eng":114, "duration_sec":719},
  {"rn":2, "start":1774443477, "end":1774444196, "eng":186, "duration_sec":719},
  {"rn":1, "start":1774471043, "end":1774471762, "eng":150, "duration_sec":719},
  {"rn":2, "start":1774471936, "end":1774472502, "eng":234, "duration_sec":566}
]
```
