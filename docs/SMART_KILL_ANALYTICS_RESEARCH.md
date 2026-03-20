# Community Feedback Research Report — Smart Kill & Revive Analytics

## Kontekst
Community (olympus, superboyy) je na Discordu podal ideje za pametnejše merjenje gibov, reviveov in kill impacta. Ciril želi raziskati kaj lahko iz tega izluščimo — kaj imamo, kaj manjka, kaj je izvedljivo.

---

## DEL 1: Community ideje — povzetek

### Olympus
1. **Gib value ↑ če ima žrtev teammate blizu** — gibi izolirane tarče (ki bi itak tapoutal) so low-value
2. **Gibi med team pushom** — gibanje engija na Supply last stage ko napadajo = ogromna vrednost
3. **Medic proximity** — gib pred revivom → medic ujameš s syringe v roki → double impact
4. **Spawn timing context** — če sta 2/3 sovražnikov že mrtva z 10s do spawna, gib tretjega pri 9s ne šteje nič

### Superboyy
5. **Alternativna brutality definicija** — high dmg/kills + LOW playtime denied = "brutal but ineffective"
6. **Gibi so overrated** — treba trackat kill→revive sekvence v Lua
7. **Fail scenarij** — kill pri 25s do spawna, revive po 10s = velik fail (kill ni naredil nič)
8. **Saved time** — koliko časa si prihranil z gibom (preprečen revive ki bi se zgodil)
9. **Useless revive** — revive nekoga 2s pred spawnom = waste
10. **denied_playtime** — kul stat, ampak ne vemo ali pravilno upošteva gibe in revive

---

## DEL 2: Kaj imamo DANES (brez sprememb kode)

### ✅ Podatki ki jih že trackamo

| Podatek | Tabela | Stolpci | Obseg |
|---------|--------|---------|-------|
| Kill spawn timing | `proximity_spawn_timing` | `spawn_timing_score`, `time_to_next_spawn`, `enemy_spawn_interval` | 1,907 per-kill eventov |
| Izolacija žrtve | `proximity_trade_event` | `nearest_teammate_dist`, `is_isolation_death` | 4,592 isolation deaths |
| Team cohesion ob smrti | `proximity_team_cohesion` | `dispersion`, `straggler_count`, `buddy_pair_guids` | 5,076 vzorcev |
| Crossfire koordinacija | `proximity_crossfire_opportunity` | `angular_separation`, `was_executed`, `damage_within_window` | 1,499 eventov |
| Žrtev class (medic/engi) | `proximity_reaction_metric` | `target_class` (MEDIC/ENGINEER/SOLDIER/COVERTOPS) | 10,642 engagementov |
| Support reakcija | `proximity_reaction_metric` | `support_reaction_ms`, `num_attackers` | per-engagement |
| Gibs (skupno) | `player_comprehensive_stats` | `gibs` (INTEGER) | per-round aggregate |
| Denied playtime | `player_comprehensive_stats` | `denied_playtime` (sekunde) | per-round aggregate |
| Revives skupno | `player_comprehensive_stats` | `revives_given`, `times_revived` | per-round aggregate |
| Useful/useless kills | `player_comprehensive_stats` | `most_useful_kills`, `useless_kills` | per-round aggregate |
| Revive eventi (Lua) | Lua output file `# REVIVES` | `medic_guid`, `revived_guid`, `distance_to_enemy`, `under_fire` | per-event v Lua |

### Kaj lahko danes že izračunamo (brez Lua sprememb)

**1. Kill context scoring** — za vsak kill iz `proximity_spawn_timing`:
- Spawn timing value (0.0–1.0)
- Cross-join s `proximity_trade_event` → ali je bila žrtev izolirana?
- Cross-join s `proximity_team_cohesion` → ali je žrtvin team pushal skupaj?
- Cross-join s `proximity_reaction_metric` → ali je bila žrtev medic/engineer?

**2. "Olympusov scenarij"** — gib izolirane tarče vs. gib med pushom:
- `is_isolation_death = true` → low-value kill (bi itak tapoutal)
- `dispersion < 300` (TIGHT formation) + `target_class = ENGINEER` → high-value kill

**3. Superboyy "denied_playtime audit"**:
- Primerjava `denied_playtime / kills` per-player → average denial per kill
- Korelacija z `gibs / kills` → ali gibalci res denijajo več?

---

## DEL 3: Kaj NE moremo danes (manjkajoči podatki)

### ❌ Kritične vrzeli

| Vprašanje | Status | Razlog |
|-----------|--------|--------|
| **Ali je bil kill gib?** | ❌ NI per-kill flaga | `proximity_spawn_timing` ne loči gibs od killov. `gibs` stolpec je samo aggregate. |
| **Ali je denied_playtime upošteva revive?** | ❌ NE | Engine stat seštetje time-to-spawn ob killu. Če je žrtev revived po 10s, se denied_playtime NE zmanjša. **To je confirmed bug/limitation.** |
| **Kill → revive sekvenca** | ❌ NI v DB | Lua TRACKIRA revive (et_ClientSpawn z revived=1), ampak ta sekcija se NE importira v DB. |
| **Useless revive detection** | ❌ NI možno | Rabimo per-revive timestamp + spawn timer da izračunamo "koliko časa pred spawnom si bil revived". |
| **Saved time from gib** | ❌ NI možno | Rabimo per-gib event + medic proximity + spawn timing. |
| **Medic blizu žrtve ob gibu** | ⚠️ DELNO | `proximity_reaction_metric` ima `target_class`, ampak ne vemo ali je bil kill tudi gib. |

### Ključna ugotovitev: `denied_playtime` je NAPAČEN za revived kille

**Primer:**
```
Kill žrtev pri spawn_timing_score = 0.95 (25s do spawna)
→ denied_playtime += 25s

Žrtev revived po 10s:
→ denied_playtime OSTANE 25s (NE 15s)
→ Dejanski denied time = samo 10s (čas do revive-a)
```

**Posledica:** Igralec ki ubije 20 ljudi ampak jih 15 revivajo, ima ENAK denied_playtime kot igralec ki ubije 20 in jih 15 gibne. To je bistvena pomanjkljivost.

---

## DEL 4: Kaj Lua API omogoča (za prihodnje nadgradnje)

### ET:Legacy Lua callbacki ki jih že imamo

| Callback | Trenutna uporaba | Potencial |
|----------|-----------------|-----------|
| `et_Obituary(victim, killer, MOD)` | Death tracking, spawn timing | **Dodaj `is_gib` flag iz MOD** |
| `et_ClientSpawn(client, revived)` | Spawn tracking | **`revived=1` → revive event z timestampom** |
| `et_Damage(target, attacker, dmg, flags, MOD)` | Ni v uporabi | Gib detection iz `damageFlags` |
| `et_RunFrame(levelTime)` | 250ms sampling | Player state polling |

### Dostopni podatki per-player

```lua
et.gentity_get(id, "sess.playerType")  -- 0=SOLDIER, 1=MEDIC, 2=ENGINEER, 3=FIELDOPS, 4=COVERTOPS
et.gentity_get(id, "sess.gibs")        -- Cumulative gib counter
et.gentity_get(id, "health")           -- Current HP (≤0 = dead)
et.gentity_get(id, "ps.origin")        -- [x, y, z] position
```

### Spawn wave timing

```lua
-- Spawn interval iz cvar
local axis_spawn = tonumber(et.trap_Cvar_Get("g_spawntime_axis"))     -- tipično 30s
local allies_spawn = tonumber(et.trap_Cvar_Get("g_spawntime_allies")) -- tipično 20s
-- Že implementirano v proximity_tracker.lua:recordSpawnTiming()
```

### Means of Death (MOD) za gib detection

```lua
-- Že definirani v proximity_tracker.lua:
MOD_SELFKILL = 37
MOD_FALLING = 38
-- MANJKAJO (treba dodati):
MOD_KNIFE = 2          -- knife gib
MOD_GRENADE = 11       -- grenade gib
MOD_DYNAMITE = 14      -- dynamite gib
MOD_PANZERFAUST = 8    -- panzerfaust gib
MOD_GPG40 = 15         -- rifle grenade gib
MOD_MORTAR = 16        -- mortar gib
-- Plus: damageFlags & DAMAGE_GIB flag za zanesljivo detekcijo
```

---

## DEL 5: Možne nove metrke — kaj lahko iz tega ven dobimo

### TIER 1 — Izvedljivo z Lua v5.1 nadgradnjo

#### A. `GIB_CONTEXT` sekcija (nova)
Za vsak gib event:
```
gib_time;killer_guid;victim_guid;victim_class;means_of_death;
spawn_timing_score;nearest_medic_dist;nearest_teammate_dist;
team_dispersion;is_during_push
```

**Omogoča:**
- **Smart Gib Score** — gib medica med team pushom pri spawn_timing 0.9 = 100 točk. Gib solo izolirane tarče 2s pred spawnom = 5 točk.
- **Medic Denial** — gibanje tarče ko je medic < 500 enot stran (preprečil revive)
- **Push Disruption** — gibanje med TIGHT team cohesion (sovražnik je pushal skupaj)

#### B. `REVIVE_CONTEXT` sekcija (nova)
Za vsak revive event (že imamo v Lua, samo dodamo polja):
```
revive_time;medic_guid;victim_guid;time_since_death;
spawn_timer_remaining;revive_utilization_pct;
distance_to_enemy;under_fire
```

**Omogoča:**
- **Useless Revive Detection** — `spawn_timer_remaining < 3s` → useless (Superboyy)
- **Revive Efficiency** — `(spawn_interval - spawn_timer_remaining) / spawn_interval * 100` → koliko % spawn časa si prihranil
- **Clutch Revive** — `under_fire = true AND distance_to_enemy < 500` → high-risk revive

#### C. `KILL_OUTCOME_TRACKING` sekcija (nova)
Za vsak kill, trackamo kaj se zgodi potem:
```
kill_time;killer_guid;victim_guid;was_gibbed;was_revived;
time_to_revive_ms;revived_by_guid;effective_denied_time
```

**Omogoča:**
- **True Denied Playtime** — `effective_denied = MIN(time_to_revive, time_to_next_spawn)` namesto engine-ove napačne verzije
- **Kill Waste Rate** — `killed_but_revived_quickly / total_kills` → koliko tvojih killov so revivali?
- **Superboyy fail scenarij** — kill pri 25s, revive po 10s → effective_denied = 10s namesto 25s

### TIER 2 — Composite metrke iz novih podatkov

#### D. **Elimination Impact Score** (per-player, per-session)
```
EIS = Σ(per_kill_impact) / kills

per_kill_impact = (
    spawn_timing_weight          × 0.30   # kdaj si ubil (glede na spawn wave)
  + gib_medic_denial_weight      × 0.25   # ali si preprečil revive?
  + team_push_disruption_weight  × 0.20   # ali si razbit push?
  + isolation_penalty            × -0.15  # minus za izoliran kill brez posledic
  + effective_denied_time_weight × 0.10   # dejanski denied čas (ne engine-ov)
)
```

#### E. **Medic Efficiency Rating** (per-medic)
```
MER = (
    revives_saved_time / max_possible_saved_time     × 0.40
  + clutch_revives / total_revives                    × 0.25
  + (1 - useless_revive_rate)                         × 0.20
  + survived_after_revive_pct                         × 0.15
)
```

#### F. **Kill Permanence Rate** (per-player)
```
KPR = gibs_confirmed / kills
  + (kills_not_revived / kills) × 0.5
```
Meri koliko tvojih killov je dejansko "permanentnih" — sovražnik ni bil revived ali je bil gibbed.

#### G. **Team Denial Score** (per-team, per-round)
```
TDS = total_effective_denied_time / round_duration × 100
```
Koliko % časa je sovražna ekipa imela manj igralcev na polju — pravi "man advantage time" (hokej model).

### TIER 3 — Napredni scenariji

#### H. **Anti-Revive Discipline** — ali gibaš PRAVE tarče?
- Gib prioriteta: žrtev z medicem < 500u > žrtev brez medica
- Gib prioriteta: žrtev pri spawn_timing > 0.7 > žrtev pri < 0.3
- Penalizacija: gibanje pri spawn_timing < 0.1 (2-3s do spawna = waste of ammo)

#### I. **Revive Chain Detection**
- Kill → Revive → Re-kill → Gib sekvenca
- Medic ki reviva isto osebo 3× v rundi = "Zombie Medic"
- Kill ki se ponovi na istem playerju v 5s = "Failed Elimination"

#### J. **Predicted Revive Probability**
- Na podlagi medic proximity + team cohesion + under_fire
- ML model: `P(revive) = f(medic_dist, team_dispersion, enemy_pressure)`
- Gib pri P(revive) > 0.8 = visoka vrednost, gib pri P(revive) < 0.1 = nizka

---

## DEL 6: Podatkovne količine in izvedljivost

### Obseg podatkov (iz trenutne DB)

| Tabela | Vrstice | Sej | Pokritost |
|--------|---------|-----|-----------|
| `proximity_spawn_timing` | 1,907 | 2 seji | Per-kill timing |
| `proximity_trade_event` | 11,814 | ~30 sej | Per-death trade analysis |
| `proximity_reaction_metric` | 10,642 | ~30 sej | Per-engagement reaction |
| `proximity_team_cohesion` | 5,076 | ~30 sej | 250ms team sampling |
| `proximity_crossfire_opportunity` | 1,499 | ~30 sej | Coordinated attacks |

### Lua sprememba — obseg dela

| Sprememba | Effort | Datoteke |
|-----------|--------|----------|
| Dodaj `is_gib` flag v `et_Obituary` | Majhna (10 vrstic Lua) | `proximity/lua/proximity_tracker.lua` |
| Nova `# GIB_CONTEXT` sekcija | Srednja (50 vrstic Lua + 100 vrstic parser) | Lua + `proximity/parser/parser.py` |
| Nova `# REVIVE_CONTEXT` z timing | Srednja (40 vrstic Lua + 80 vrstic parser) | Lua + parser |
| `# KILL_OUTCOME` tracking (kill→revive→gib) | Velika (100+ vrstic Lua state mgmt) | Lua + parser + nova DB tabela |
| DB migration za nove tabele | Majhna | `migrations/016_*.sql` |
| API endpoints | Srednja | `website/backend/routers/api.py` |

---

## DEL 7: Povzetek odgovorov na community vprašanja

| Vprašanje | Odgovor | Akcija |
|-----------|---------|--------|
| **Olympus: Gib value ↑ z teammate proximity** | ✅ IZVEDLJIVO. Imamo `nearest_teammate_dist` in `is_isolation_death`. Za medic proximity rabimo dodati class v spawn_timing. | Lua v5.1 |
| **Olympus: Gib med pushom = visoka vrednost** | ✅ IZVEDLJIVO. `proximity_team_cohesion.dispersion` koreliran s kill časom. | Danes (cross-join) |
| **Olympus: Medic nearby = gib bolj vreden** | ⚠️ DELNO. `proximity_reaction_metric.target_class` pove class žrtve. Za medic BLIZU žrtve (ne žrtev sam) rabimo scan v Lua. | Lua v5.1 |
| **Superboyy: denied_playtime pravilnost** | ❌ **POTRJENO: NE upošteva reviveov.** Engine stat je naiven — ne odšteje časa če je žrtev revived. | Lua v5.1 fix |
| **Superboyy: Kill 25s, revive 10s = fail** | ❌ Danes ne moremo detectat. Rabimo kill→revive outcome tracking. | Lua v5.1 (KILL_OUTCOME) |
| **Superboyy: Saved time od giba** | ❌ Danes ne moremo. Rabimo `P(revive)` in gib flag. | Lua v5.1 |
| **Superboyy: Useless revive** | ❌ Danes ne moremo. Rabimo revive timestamp + spawn timer remaining. | Lua v5.1 (REVIVE_CONTEXT) |
| **Superboyy: Gibi overrated** | ✅ Strinjam se — gib brez konteksta (spawn timing, medic proximity) je šibka metrika. Smart gib score rešuje to. | Formula sprememba |
