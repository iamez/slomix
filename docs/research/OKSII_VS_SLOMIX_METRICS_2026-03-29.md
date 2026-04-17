# Oksii vs Slomix: Metric-by-Metric Primerjava
**Datum**: 2026-03-29 (posodobljeno z commit d5c332f 28.3.2026) | **Oksii**: stats.lua v2.2.0 (15 Lua datotek) | **Slomix**: c0rnp0rn3 + proximity v6.01

---

## EXECUTIVE SUMMARY

| Kategorija | Oksii | Slomix | Zmagovalec |
|-----------|-------|--------|------------|
| **Osnovna natančnost** (kills, deaths, accuracy) | Enako | Enako | Izenačeno — oba bereta iz sess.aWeaponStats |
| **Per-event kontekst** (stance, health, reinf, alive counts) | ⭐⭐⭐ | ⭐⭐ | Oksii — bogati snapshoti na vsak event |
| **Movement analytics** | ⭐⭐⭐ | ⭐⭐ | Oksii — per-frame, spawn distance, turtle |
| **Engagement analytics** | ⭐ | ⭐⭐⭐ | Slomix — state machine, crossfire, trade, focus |
| **Scoring / Rating** | ⭐ (samo match score) | ⭐⭐⭐ | Slomix — ET Rating, KIS, session score |
| **Objective tracking** | ⭐⭐⭐ | ⭐⭐ | Oksii — TOML patterns, 20+ map, carrier attribution |
| **Modularnost** | ⭐⭐⭐ | ⭐ | Oksii — 14 modulov po ~200 vrstic |
| **Match management** | ⭐⭐⭐ | ⭐ | Oksii — gather, auto-start, BO3 scoring |
| **Weapon fire tracking** | ⭐⭐ (opcijsko) | ❌ | Oksii — per-shot pitch/yaw (high volume) |
| **Config/DevOps** | ⭐⭐⭐ | ⭐⭐ | Oksii — env vars, version check, config validation |

**Zaključek**: Oksii je boljši pri **zbiranju surovih podatkov** (več konteksta na vsak event) in **match management** (BO3 scoring, gather automation). Slomix je boljši pri **analizi in scoringu** (derivirane metrike, formule, rating sistem). Idealno: Oksiijev nivo zbiranja + Slomixov nivo analize.

---

## 1. CORE STATS — Enake osnove

### Kills / Deaths / Headshots

| Aspekt | Oksii | Slomix | Ujemanje? |
|--------|-------|--------|-----------|
| **Vir** | `sess.aWeaponStats[j].kills/deaths` | Endstats datoteka (isti engine podatki) | ✅ Enako |
| **28 weapon slotov** | Da, iterira 0-27 | Da, bitmask-driven parsing | ✅ Enako |
| **R2 differential** | N/A (pošlje per-round) | Da, Python odšteje R1 od R2 | Slomix ima extra korak |
| **Headshots** | `sess.aWeaponStats[j].headshots` = headshot HITS | Dva ločena metrika: weapon headshot hits + TAB[14] headshot kills | ⚠️ Oksii ima samo hits, Slomix ima oboje |
| **Reconnect handling** | Ni dokumentirano | Avtomatska detekcija (≥2 padcev) → fallback na raw R2 | Slomix bolj robusten |

**Verdict**: Enaki surovi podatki iz engine-a. Slomix ima bolj robusten post-processing (R2 differential, reconnect detection).

### Accuracy

| Aspekt | Oksii | Slomix |
|--------|-------|--------|
| **Formula** | `hits/atts` per weapon — consumer izračuna | `(SUM(hits)/SUM(shots))*100` agregirano |
| **Vir** | `sess.aWeaponStats` | Endstats weapon section |
| **Per-weapon breakdown** | Da (v JSON outputu) | Da (v bazi) |

**Verdict**: Enako. Oba bereta iz istega engine vira.

### Damage

| Aspekt | Oksii | Slomix |
|--------|-------|--------|
| **Aggregate** | `sess.damage_given/received` + `team_damage_given/received` | TAB[0-3], enake engine vrednosti |
| **Per-event** | `et_Damage()` callback z damage amount + flags + hit region | Proximity `et_Damage()` z damage + hit region |
| **DPM** | Ni predračunan (consumer izračuna) | `(damage_given * 60) / time_played_seconds` v Pythonu |

**Verdict**: Enaki surovi podatki. Slomix predračuna DPM.

---

## 2. PER-EVENT KONTEKST — Oksii prevladuje

### Kill Events

| Polje | Oksii | Slomix (proximity) | Razlika |
|-------|-------|---------------------|---------|
| killer_pos (x,y,z) | ✅ | ✅ | Enako |
| victim_pos (x,y,z) | ✅ | ✅ | Enako |
| killer_health | ✅ | ❌ | **Oksii boljši** |
| killer_class | ✅ | ✅ (iz engagement) | Enako |
| victim_class | ✅ | ✅ (iz engagement) | Enako |
| killer_stance (prone/crouch/mg/lean/obj/disguise/sprint) | ✅ 7 stanj | ⚠️ 3 stanja (stand/crouch/prone) | **Oksii boljši** — več stance tipov |
| victim_stance | ✅ 7 stanj | ⚠️ 3 stanja | **Oksii boljši** |
| allies_alive | ✅ | ❌ | **Oksii boljši** — kontekst za clutch kills |
| axis_alive | ✅ | ❌ | **Oksii boljši** |
| killer_reinf (sek do wave) | ✅ | ✅ spawn_timing_score | **Enako** (oba računata reinf timing) |
| victim_reinf | ✅ | ✅ | Enako |
| weapon (meansOfDeath) | ✅ | ✅ | Enako |
| hit_region | ✅ (na damage events) | ✅ (na damage events) | Enako |

**Manjkajoče pri Slomix**:
- `killer_health` ob kill eventu — koliko HP je imel killer, ko je ubil (low HP kill = clutch)
- `allies_alive` / `axis_alive` — koliko igralcev je bilo živih ob killu (1v5 = epic)
- Razširjeni stance (mg mounted, leaning, obj carrier, disguised, sprint)

### Damage Events

| Polje | Oksii | Slomix (proximity) |
|-------|-------|---------------------|
| damage amount | ✅ | ✅ |
| damage flags | ✅ | ❌ |
| weapon (MOD) | ✅ | ✅ |
| hit_region | ✅ | ✅ |
| killer context (pos/stance/health) | ✅ | Delno (pos iz sampling) |
| victim context | ✅ | Delno |

---

## 3. MOVEMENT — Oksii natančnejši

| Metrika | Oksii | Slomix | Razlika |
|---------|-------|--------|---------|
| **Distance (total)** | ✅ Per-frame akumulacija, v metrih | ⚠️ Samo per-engagement, ni total | **Oksii boljši** |
| **Spawn distance** | ✅ Prvih 3s po spawnu | ❌ | **Oksii boljši** — spawn aggressiveness |
| **Speed (avg/peak)** | ✅ UPS/KPH/MPH, filtered >10 UPS | ⚠️ Per-sample, ni agregiran peak | **Oksii boljši** — čistejša agregacija |
| **Position sampling** | ✅ Per-frame (~every 50ms) | ✅ Every 200ms | Oksii višja ločljivost |
| **Stance akumulacija** | ✅ 10 stanj, sekundno štetje | ⚠️ 3 stanja (stand/crouch/prone) | **Oksii boljši** — 7 dodatnih stanj |

### Oksii stance ki jih Slomix NIMA:

| Stance | Oksii metoda | Vrednost za analitiko |
|--------|-------------|----------------------|
| `in_mg` (mounted MG) | `eFlags & EF_MG42_ACTIVE` ali weapon==47/50 | Čas na MG = defensivni stil |
| `in_lean` | `ps.leanf ~= 0` | Leaning = taktično pokukovanje |
| `in_objcarrier` | `powerups[PW_REDFLAG/BLUEFLAG] > 0` | Čas z zastavico = objective focused |
| `in_vehiclescort` | `eFlags & EF_TAGCONNECT` | Čas ob tanku |
| `in_disguise` | `powerups[PW_OPS_DISGUISED] > 0` | Covert ops čas v preobleki |
| `in_sprint` | Stamina delta >50 | Bolj natančno kot PMF_SPRINT flag |
| `in_turtle` | Stamina ==0 ali ==MAX ali recovering | Stojanje na mestu |
| `is_downed` | health<0 AND contents==BODY_DOWNED | Čas na tleh pred revive/tapout |

**Skupaj**: Oksii ima ~7 stance tipov ki jih Slomix ne sledi. Ti podatki so bogati za player archetype analizo.

---

## 4. SCORING — Slomix DRASTIČNO prevladuje

| Scoring sistem | Oksii | Slomix |
|----------------|-------|--------|
| **Match scoring** | ✅ BO3 stopwatch z clinch, side validation (80% GUID threshold), persistent JSON state, score announce v chat | ✅ Stopwatch scoring service (osnovnejši, brez BO3/clinch) |
| **ET Rating (player skill)** | ❌ | ✅ 9-metrična percentile formula |
| **Kill Impact Score (KIS)** | ❌ | ✅ 7 multiplikatorjev per kill |
| **Session Composite Score** | ❌ | ✅ 7-kategorij weighted (0-100) |
| **Player Archetypes** | ❌ | ✅ Slayer, Medic, Engineer, etc. |
| **Momentum tracking** | ❌ | ✅ Round-by-round momentum |
| **Team synergy** | ❌ | ✅ 5 sub-metrik |
| **MVP formula** | ❌ | ✅ kd*10 + efficiency + dmg/100 |
| **Tier system** | ❌ | ✅ Elite/Veteran/Experienced/Regular/Newcomer |

**Oksii pošilja surove podatke API-ju** — scoring je na consumer strani.
**Slomix ima celoten scoring pipeline** — od kill-level do player-level do session-level.

---

## 5. ENGAGEMENT ANALYTICS — Slomix DRASTIČNO prevladuje

| Feature | Oksii | Slomix |
|---------|-------|--------|
| **Engagement state machine** | ❌ | ✅ Create→hit→escape/kill z duration, damage, attackers |
| **Crossfire detection** | ❌ (samo logs 2+ attackers) | ✅ Angular separation + executed boolean + damage |
| **Trade kill detection** | ❌ | ✅ Teammate kills your killer within window |
| **Focus fire scoring** | ❌ | ✅ timing_tightness*0.6 + dps_score*0.4 |
| **Team push detection** | ❌ | ✅ Quality score z speed, direction, cohesion |
| **Team cohesion time-series** | ❌ | ✅ Centroid, dispersion, buddy pairs, straggler count |
| **Reaction metrics** | ❌ | ✅ return_fire_ms, dodge_reaction_ms, support_reaction_ms |
| **Kill outcome tracking** | ❌ (samo gamelog) | ✅ State machine: gibbed/revived/tapped + delta_ms + gibber/reviver |
| **Survivability scoring** | ❌ | ✅ escapes/total_engagements |

**To je Slomixova največja prednost.** Oksii logira surove evente, Slomix jih analizira v real-time.

---

## 6. OBJECTIVE TRACKING — Oksii prevladuje

| Feature | Oksii | Slomix |
|---------|-------|--------|
| **Objective types** | 12 tipov (plant, defuse, destroy, repair, take, secure, return, carrier_killed, flag_captured, escort, misc, shove) | Endstats: 5 tipov (plant, defuse, stolen, returned, repairs). Proximity v6: carrier events, construction, vehicle, objective runs |
| **Map patterns** | ✅ TOML config za 20+ map | ❌ Hardkodiran v Lua/Python |
| **Attribution** | ✅ Player ID iz print line + coordinate proximity + carrier cache | ✅ Entity scanning v v6 |
| **Dynamite attribution** | ✅ Planter GUID cached, used for destroy attribution | ❌ Samo plant/defuse count |
| **Repair attribution** | ✅ 2s announcement buffer za korelacijo | ❌ Samo count |
| **Shove tracking** | ✅ Shover + target | ❌ |
| **Flag capture attribution** | ✅ Nearest player to known coords | ✅ V v6 carrier events |

**Oksii ima bolj natančno atribucijo** — ve KDO je naredil KAJ za vsak objective. Slomix ve samo COUNT per player iz endstats.

---

## 7. MATCH MANAGEMENT — Oksii prevladuje (Slomix nima)

| Feature | Oksii | Slomix |
|---------|-------|--------|
| **Auto-rename** | ✅ Teams renamed to match roster names | ❌ |
| **Auto-sort** | ✅ Players assigned to correct teams | ❌ |
| **Auto-start** | ✅ State machine z countdown, warnings, API validation | ❌ |
| **Auto-map** | ✅ Next map from match config | ❌ |
| **Auto-config** | ✅ Server settings from match type | ❌ |
| **BO3 scoring** | ✅ Full stopwatch rules, clinch, fullhold, side validation | ⚠️ Samo basic stopwatch scoring |
| **Tech pause** | ✅ Per-team quotas, extended timeout | ❌ |
| **Team lock** | ✅ Auto-lock on round start | ❌ |

---

## 7b. WEAPON FIRE TRACKING — Oksii ima (opcijsko), Slomix nima

| Feature | Oksii | Slomix |
|---------|-------|--------|
| **Per-shot logging** | ✅ `et_WeaponFire` + `et_FixedMGFire` (za `COLLECT_WEAPON_FIRE=true`) | ❌ |
| **Pitch/yaw ob strelu** | ✅ Angle data za vsak shot | ❌ |
| **Stance ob strelu** | ✅ | ❌ |
| **Volume warning** | Da — "very high volume", privzeto OFF | N/A |

**Potencialna uporaba**: Aimbot detekcija (neobičajni pitch/yaw vzorci), spray pattern analiza, shot-to-hit korelacija.
**Trade-off**: Enormen data volume. Za 20-min round z 12 igralci = tisoče eventov.

## 7c. CONFIG & DEVOPS — Oksii bolj zrel

| Feature | Oksii | Slomix |
|---------|-------|--------|
| **Env var overrides** | ✅ Vsak config setting overridable, Docker-friendly | ⚠️ `.env` za bot, hardkodirano v Lua |
| **Config validation** | ✅ API token, URL, map config preverjanje ob init | ❌ |
| **Version check** | ✅ API-based, deferred na prvi RunFrame | ❌ |
| **Log buffering** | ✅ `buffer_start()`/`buffer_flush()` za batch init writes | ❌ |
| **Deferred init** | ✅ Version check ne blokira init | ❌ |
| **Spawn weapon detection** | ✅ `et.GetCurrentWeapon()` ob `et_ClientSpawn` | ❌ |
| **Revive callback** | ✅ `et_Revive` | ❌ (kill_outcome state machine zaznava revive drugače) |

---

## 8. SPECIFIČNE NATANČNOSTNE RAZLIKE

### Score (XP) Handling
| | Oksii | Slomix |
|-|-------|--------|
| **Vir** | `ps.persistant[PERS_SCORE]` | TAB[9] (isti engine podatek) |
| **Uporaba** | Surovi XP v JSON outputu | Shranjeno v bazi, NI uporabljeno v nobeni formuli |
| **Natančnost** | R2-ONLY (engine resetira med roundi) | R2-ONLY pravilno obravnavan |

**Verdict**: Enako. Ampak nobeden ne uporablja XP za scoring — oba vesta da je ET:Legacy XP slab proxy za skill.

### DPM (Damage Per Minute)
| | Oksii | Slomix |
|-|-------|--------|
| **Izračun** | Consumer-side iz `dmg_given` + `time_played` | `(damage_given * 60) / time_played_seconds` |
| **Time source** | `sess.time_played` (engine) | TAB[22] per-player Lua time ali round duration |
| **Self/team damage** | Ločeno: `sess.damage_given` = samo enemy | Ločeno: TAB[0] = samo enemy |

**Verdict**: Enako vir, enaka formula. Oba pravilno izključujeta self/team damage.

### Alive% / Time Played
| | Oksii | Slomix |
|-|-------|--------|
| **Vir** | `sess.time_played` (ms) + `pct_played` (derived) | TAB[8] + TAB[22] + TAB[25] |
| **R2 handling** | N/A (per-round) | **Kompleksno**: recalculated iz absolutnih alive-time vrednosti (popravek marec 2026) |
| **Natančnost** | Engine vrednost, zanesljiva | Engine vrednost + Python rekalkulacija za R2 |

**Verdict**: Oksii je preprostejši (engine vrednost per-round). Slomix ima dodatno kompleksnost zaradi R2 differential, ampak je bil popravljen.

### Reconnect Handling
| | Oksii | Slomix |
|-|-------|--------|
| **Detekcija** | Ni dokumentirano | ≥2 cumulative fields padejo → fallback na raw R2 |
| **Posledica** | Možni napačni cumulative totali | Robustno obravnavanje |

**Verdict**: **Slomix boljši** — avtomatsko detektira reconnecte.

---

## 9. WHAT COULD WE ADOPT?

### Enostavne izboljšave (brez Lua sprememb):

| # | Kar | Kako | Trud |
|---|-----|------|------|
| 1 | **Distance pre-computation** | Agregiraj position samples v total_distance v Python post-procesiranju | 2 ure |
| 2 | **Peak/avg speed** | Agregiraj speed samples v Python | 1 ura |
| 3 | **KIS distance multiplier** | Poveži combat_positions razdaljo s KIS | 1 ura |

### Lua izboljšave (~135 vrstic):

| # | Kar | Dodaj v proximity_tracker | Trud |
|---|-----|--------------------------|------|
| 4 | **killer_health na kill** | `et.gentity_get(attacker, "health")` v on_kill | 5 vrstic |
| 5 | **alive_count na kill** | Preštej žive igralce per team ob killu | 15 vrstic |
| 6 | **Razširjeni stance** | Dodaj eFlags za MG, lean, objcarrier, disguise, vehicle | 30 vrstic |
| 7 | **Spawn distance** | 3s tracking window po spawnu | 30 vrstic |
| 8 | **Turtle detection** | Raw stamina value v sampling | 10 vrstic |
| 9 | **Entity scan za flag coords** | `et.gentity_get(i, "classname")` ob init | 40 vrstic |

### Scoring izboljšave (Python):

| # | Kar | Trud |
|---|-----|------|
| 10 | **alive_count v KIS** | Dodaj multiplier: solo kill (1v3+) = 2.0x, outnumbered = 1.5x | 2 ure |
| 11 | **killer_health v KIS** | Low HP kill (<30) = 1.3x, full HP = 1.0x | 1 ura |
| 12 | **Stance v archetype classification** | MG time → defensive, sprint time → aggressive | 2 ure |

---

## 10. KLJUČNA UGOTOVITEV

### Oksii je boljši pri:
1. **Surovi podatki per-event** (7 stance tipov, health, alive counts)
2. **Movement analytics** (per-frame, spawn distance, turtle, total distance)
3. **Objective attribution** (20+ map patterns, dynamite planter tracking, repair attribution)
4. **Match management** (gather, BO3, auto-start)
5. **Modularnost** (14 datotek, dependency injection, clean resets)

### Slomix je boljši pri:
1. **Derivirana analitika** (engagements, crossfire, trade kills, focus fire, team cohesion)
2. **Scoring formule** (ET Rating, KIS, session composite, archetypes)
3. **R2 differential handling** (reconnect detection, alive% fix)
4. **Kill outcome tracking** (state machine z gibbed/revived/tapped + delta_ms)
5. **Reaction metrics** (return_fire, dodge_reaction, support_reaction)

### Idealna kombinacija:
```
Oksiijev nivo zbiranja (stance, health, alive, distance, objectives)
    +
Slomixov nivo analize (engagements, scoring, ratings, archetypes)
    =
Najboljša ET:Legacy stats platforma
```

---

## NAPREJ

Naš proximity_tracker že ima infrastrukturo za dodajanje Oksii-jevih manjkajočih podatkov. Biggest wins z najmanj dela:

1. **killer_health + alive_count** na kill events (20 vrstic Lua) → takoj uporabno v KIS
2. **Razširjeni stance** v path sampling (30 vrstic Lua) → bogati archetype klasifikacijo
3. **Spawn distance** (30 vrstic Lua) → nova "spawn aggressiveness" metrika
4. **Total distance** aggregacija (Python, brez Lua sprememb) → movement leaderboard
