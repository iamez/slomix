# Oksii Adoption — Research Results (5 ekip)
**Datum**: 2026-03-29 | **Metoda**: Mandelbrot/RCA z 5 vzporednimi ekipami | **Status**: SAMO RESEARCH

---

## KRITIČNE NAJDBE (moramo popraviti pred implementacijo)

### BUG-1: Off-by-one CSV indeks v COMBAT_POSITIONS (KRITIČNO)
**Ekipa**: research-parser, research-lua
**Problem**: Plan trdi `parts[17]` = killer_health. NAROBE — `parts[17]` je `mod` (means_of_death)!
**Pravilni indeksi**:
| Polje | Plan | Pravilno |
|-------|------|----------|
| killer_health | index 17 | **index 18** |
| axis_alive | index 18 | **index 19** |
| allies_alive | index 19 | **index 20** |
**Posledica brez popravka**: Stari fajli bi pisali MOD vrednost (0-66) kot killer_health. Vsi historični KIS izracuni bi bili napacni.

### BUG-2: Reinforcement formula ignorira reinf_offset (VISOKO)
**Ekipa**: research-lua
**Problem**: Plan predlaga novo formulo za killer_time_to_spawn ki ignorira `reinf_offset`. Nasa obstoječa `calculateSpawnTimingScore()` (vrstica 1451) pravilno upošteva offset.
**Popravek**: Uporabi obstojecjo funkcijo za oba teama namesto nove formule:
```lua
local killer_time_to_next, _ = calculateSpawnTimingScore(kill_time, killer_team_num)
```

### BUG-3: Plan citira napacna imena funkcij (SREDNJE)
**Ekipa**: research-kis
**Problem**: Plan citira `compute_kill_impact()` — dejanska funkcija je `_score_kill()` (vrstica 182). `base` spremenljivka ne obstaja — dejanska koda je `total = (1.0 * carrier_mult * ...)`.

### BUG-4: Migracija 032 je ze zasedena (SREDNJE)
**Ekipa**: research-kis
**Problem**: Plan predlaga `032_add_oksii_adoption_fields.sql`, ampak 032 je ze `032_add_storytelling_kill_impact.sql`.
**Popravek**: Naslednja prosta je **033**.

### BUG-5: Extended stance — plan zamenjuje pm_flags z eFlags (VISOKO)
**Ekipa**: research-lua
**Problem**: Plan trdi da nas kod uporablja `eFlags`. NAROBE — uporabljamo `pm_flags`. Za nove stance features potrebujemo OBOJE (locen read).
**Performancni riziko**: 6+ dodatnih `safe_gentity_get()` klicev per player per 200ms = ~960 klicev/s pri polnem serverju.

### BUG-6: Entity scanning (2.3) je ze implementiran (VISOKO)
**Ekipa**: research-lua
**Problem**: Plan predlaga entity scanning za flag coordinates — ampak `scanObjectiveEntities()` (vrstica 2363) to ZE DELA. Vkljucno s `team_WOLF_checkpoint`.

---

## KIS INFLATION ANALIZA

### health_mult (1.3x za kill pod 30 HP): VARNO
- Ocena: 3-8% killov na rundo bi dobilo bonus
- Threshold 30 HP je smiselen za competitive 3v3
- **Ocena: 8/10** — sprejmi

### alive_mult (1.5x outnumbered / 2.0x solo clutch): DELNO PROBLEMATICNO
- Solo clutch (1v3) je dober: ~2-4% killov
- **PROBLEM**: `OUTNUMBERED_THRESHOLD = 2` se NIKOLI ne sprozi v 3v3!
  - 2v3 = diff 1, NE sprozi (threshold je 2)
  - Edini primer z diff >= 2 je 1v3, ki ga ujame SOLO_CLUTCH
  - 1.5x multiplier je MRTVA KODA v 3v3
- **Popravek**: Znizaj OUTNUMBERED_THRESHOLD na 1 za 3v3
- **Ocena: 5/10** — potrebuje recalibration

### reinf_mult (victim_reinf > 15s -> spawn_mult x 1.2): INFLACIJA!
- Pri 30s reinf (pogost): **50% vseh killov** dobi 1.2x bonus
- Spawn_mult ze dosega 2.0x — z 1.2x mnozenje = do 2.4x
- To je ISTI PROBLEM kot push_mult (99.8%)
- **Popravek**: Relativni threshold `victim_reinf > (spawn_interval * 0.75)` ALI hard cap spawn_mult na 2.0
- **Ocena: 3/10** — potrebuje recalibration

### Skupna inflation (worst case)
- Trenutni max KIS: ~6.15 za "dober" kill
- Z vsemi 3 novimi: 6.15 x 1.3 x 2.0 x 1.2 = **19.19** (3.1x inflation!)
- **Priporocilo**: Dodaj total_impact cap (max 15.0) ALI additivni pristop za nove multiplierje

---

## BOX SCORING ARHITEKTURNE ODLOCITVE

### 1. BOX zamenja ali dopolni obstoječ scoring?
**Priporocilo**: Nova datoteka (`box_scoring_service.py`), oba zivita hkrati.
- `StopwatchScoringService` ostane za legacy (Discord bot, session_results)
- `BOXScoringService` za website display
- Postopna migracija ko je BOX stabilen

### 2. Pipeline lokacija
**Priporocilo**: Hibrid
- Bot: hook v `on_round_imported` za persistence v `session_round_scores`
- Website: on-demand izracun za display

### 3. Point sistem je BREAKING CHANGE
- Obstoječ: 1pt/map win
- BOX: 2pt/map win, 1pt/draw
- **Priporocilo**: Nova tabela (`session_round_scores`), stara ostane za legacy

### 4. FK problem
- `session_round_scores` schema ima `REFERENCES gaming_sessions(id)` — **tabela NE OBSTAJA!**
- **Popravek**: Odstrani FK, uporabi navaden INTEGER (konsistentno z obstojecim vzorcem)

### 5. Frontend
- React komponenta ze obstaja za scoring, ampak kaze "Allies/Axis" namesto team imen
- `scoring.team_a_name` / `scoring.team_b_name` podatki ZE obstajajo v API response

---

## MANJKAJOCI KORAKI V PLANU

| # | Kaj manjka | Opis |
|---|-----------|------|
| 1 | Dataclass posodobitve | CombatPosition, SpawnTimingEvent, PathPoint morajo dobiti nova polja z defaults |
| 2 | `_table_has_column` checki | Import funkcije morajo preveriti ali stolpci obstajajo pred INSERT |
| 3 | INSERT batch posodobitev | `_compute_session_kis_locked()` ima hardkodiran INSERT z 23 parametri — mora biti 28 |
| 4 | `_load_combat_positions()` method | KIS nima data loaderja za combat_position podatke — treba dodati |
| 5 | `_load_spawn_timings()` query razsiritev | Obstoječ query ne bere victim_reinf/killer_reinf |
| 6 | Bot restart med parser in Lua deploy | Plan ne omenja da mora bot restartati da nalozi nov parser |
| 7 | Lua backup pred deployem | `cp proximity_tracker.lua proximity_tracker.lua.v6.01.bak` |

---

## REDUNDANTNI FEATURES (preskoci ali poenostavi)

| Feature | Zakaj redundanten |
|---------|------------------|
| 1.4 Spawn distance | `post_spawn_distance` ze obstaja v player_track (parser.py:178) |
| 2.3 Entity scanning | `scanObjectiveEntities()` ze implementiran (vrstica 2363) |
| 3.3 Config validation | `et_InitGame()` ze obravnava prazen output_dir (vrstica 3383) |

---

## DEPLOYMENT

### Pravilno zaporedje
1. DB migracija (033_add_oksii_adoption_fields.sql)
2. Parser update (proximity/parser/parser.py)
3. **Bot restart** (da nalozi nov parser!)
4. Lua deploy + backup (SCP na server)
5. Map reload (SAMO ko ni aktivne igre!)
6. Storytelling/KIS update
7. Website restart
8. Test z eno igro

### Risk matrix
| Tveganje | Verjetnost | Vpliv | Mitigacija |
|----------|-----------|-------|-----------|
| Lua crash na serverju | NIZKA | SREDNJI | Backup + map reload z staro verzijo |
| Parser crash na novih stolpcih | NIZKA | NIZEK | Mock CSV test pred deployem |
| Deploy med aktivno igro | SREDNJA | VISOK | `rcon status` check |
| KIS inflation z novimi mult | SREDNJA | NIZEK | Cap total_impact na 15.0 |
| STATS_READY webhook lost med restart | SREDNJA | NIZEK | endstats_monitor pobere v 60s |

### Priporocen deploy cas
Dead hours (02:00-11:00 CET) ali takoj po koncu gaming sessiona.

---

## VPRASANJA ZA ODLOCITEV

1. **Reinf timing formula**: Uporabimo obstojeco `calculateSpawnTimingScore()` za oba teama? (priporocam DA)
2. **Extended stance performanca (2.1)**: Ali testiramo 6 dodatnih API klicev per player? Ali preskocimo Tier 2 zaenkrat?
3. **Entity scanning (2.3)**: Preskocimo ker je ze implementiran? Ali pa se omeji na drobne izboljsave?
4. **et_Revive (3.1)**: Ali `pers.lastrevive_client` deluje na nasem serverju? Ce da, callback ni potreben.
5. **Turtle detection (2.2)**: Ali hocemo "turtle" (stoji na mestu) ali "ne-sprinta"?
6. **BOX scoring**: Isti PR ali locen?
7. **OUTNUMBERED_THRESHOLD**: 1 (3v3 friendly) ali 2 (6v6 standard)?
8. **KIS inflation cap**: Hard cap 15.0 ali soft cap z diminishing returns?

---

**Ta dokument je RESEARCH. Implementacijski plan mora biti posodobljen z zgornjimi popravki pred zacetkom kodiranja.**
