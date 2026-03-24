# Oksii vs Slomix Proximity - Primerjalna raziskava

**Datum**: 2026-03-24
**Vir**: https://github.com/Oksii/legacy-configs/tree/main/luascripts
**Oksii skripta**: `game-stats-web.lua` v1.2.7 (3068 vrstic)
**Naša skripta**: `proximity/lua/proximity_tracker.lua` v5.2 (~2960 vrstic)

---

## 1. Kaj že IMAMO in pokrivamo enako kot Oksii

### 1.1 Stance per-sample (vrstica 727-741)
Mi beležimo `stance` (0=standing, 1=crouching, 2=prone) in `sprint` (0/1) v **vsakem path samplu** (na 200ms).
Oksii akumulira sekunde per-frame. Oba pristopa dasta iste podatke - naš parser lahko izračuna sekunde iz samplov.

### 1.2 Reinforcement timing na killih (vrstica 1293-1349)
`calculateSpawnTimingScore()` že računa `time_to_next_spawn` in `score` (0.0-1.0) za vsak kill.
Formula je enaka Oksijevi: `interval - ((reinf_offset + elapsed_time) % interval)`.
Zapiše v `SPAWN_TIMING` sekcijo. **Praktično identično.**

### 1.3 Speed per-sample (vrstica 720-723, 847)
Vsak sample beleži `speed` (2D magnitude). Oksii posebej beleži peak in average - naš parser to lahko izračuna iz obstoječih samplov.

### 1.4 Hit region tracking (v5.2, drug agent)
Oksii: delta tracking na `pers.playerStats.hitRegions[0-3]` v `et_Damage`.
Mi: **enako** - drug agent že implementiral identičen pristop.

### 1.5 Kill outcome tracking (v5.2, drug agent)
Oksii: obituary events z metadata.
Mi: **bolj podrobno** - gib/revive/tapout/expired state machine z delta_ms in denied_ms.

### 1.6 Combat positions (v5.2, drug agent)
Oksii: killer+victim xyz na vsak kill.
Mi: **enako** - drug agent že implementiral.

---

## 2. Kaj lahko parser izračuna iz OBSTOJEČIH podatkov (brez Lua sprememb)

### 2.1 Stance akumulacija (sekunde)
**Vir**: Path data ima stance vsakih 200ms.
**Izračun**: `count(samples where stance=X) * 0.2s`
**Primer**: 150 samplov s stance=2 → 30 sekund v prone.

### 2.2 Sprint čas
**Vir**: Path data ima sprint vsakih 200ms.
**Izračun**: `count(samples where sprint=1) * 0.2s`

### 2.3 Peak speed
**Vir**: Path data ima speed v vsakem samplu.
**Izračun**: `max(speed)` čez vse sample v tracku.

### 2.4 Average speed
**Izračun**: `avg(speed where speed > 10)` (filter idle).

### 2.5 Total distance
**Vir**: Path data ima x,y,z vsakih 200ms.
**Izračun**: Vsota 3D razdalj med zaporednimi sampli.

### 2.6 Post-spawn distance
**Vir**: Path data ima event="spawn" na začetku vsakega tracka.
**Izračun**: Vsota razdalj prvih ~15 samplov (3s / 200ms = 15) po spawn eventu.
**Opomba**: To meri koliko daleč se je player premaknil v 3 sekundah po spawnu - ne agresivnost, ampak initial movement pattern.

---

## 3. Kaj MANJKA in potrebuje Lua spremembe

### 3.1 Turtle state detection
**Kaj je**: Stanje ko player NE sprinta - bodisi ker je stamina prazna, polna (nikoli porabljena), ali se polni nazaj.
**Zakaj mi tega nimamo**: Mi beležimo samo `sprint=0/1`. Sprint=0 pomeni "ne sprinta" ampak ne vemo ZAKAJ ne (stamina prazna? se polni? ali preprosto stoji?).
**Oksijeva implementacija**:
```lua
local isTurtle = (sprintTime == 0) or                    -- stamina prazna
                (sprintTime == MAX_SPRINT_TIME) or        -- stamina polna, nikoli porabljena
                (sprintDelta < -STAMINA_CHANGE_THRESHOLD) -- stamina se polni nazaj
```
**Kaj rabiš**: Dodati `stamina` vrednost v path sample (poleg stance/sprint). Nato parser loči:
- `stamina == 0` → stamina prazna (ne more sprintat)
- `stamina == 20000` → stamina polna (ni sprintal)
- `sprintDelta < -50` → stamina se polni (recovers)
**Kompleksnost**: Nizka. Dodaš eno polje v sample, parser interpretira.

### 3.2 MG mounted time
**Kaj je**: Čas preživet na mounted MG42 ali tank MG.
**Oksijeva implementacija**: Preverja `EF_MG42_ACTIVE (0x00000020)` in `EF_MOUNTEDTANK (0x00008000)` v `eFlags`.
**Naše stanje**: Mi beremo `pm_flags` (PMF_DUCKED, PMF_PRONE, PMF_SPRINT). NE beremo `eFlags`.
**Kaj rabiš**: Brati `ps.eFlags` in dodati `mounted` flag v sample (ali ločen stance value, npr. stance=3).
**Kompleksnost**: Nizka. Ena dodatna entiteta v getPlayerMovementState.

### 3.3 Downed state (čaka medica)
**Kaj je**: Player je "downed" (health < 0, leži na tleh, čaka revive ali tapout).
**Oksijeva implementacija**: `health < 0 AND body == BODY_DOWNED (67108864)` - bere `r.contents`.
**Naše stanje**: Nimamo. Ko player umre, endamo track in ne vzorčimo več.
**Kaj rabiš**: Nadaljevati sampling ko je player downed (health < 0 ampak ni v limbo). Alternativno: kill_outcome tracking že meri čas od smrti do gib/revive/tapout, kar pokriva isti podatek na drug način.
**Kompleksnost**: Srednja. Zahteva spremembo logike kdaj se track konča.

### 3.4 Disguise time (Covert Ops)
**Kaj je**: Čas ko je covert ops preoblečen v sovražnika.
**Oksijeva implementacija**: Preverja `ps.powerups[PW_OPS_DISGUISED (7)]` > 0.
**Naše stanje**: Nimamo.
**Kaj rabiš**: Brati `ps.powerups` indeks 7, dodati flag v sample.
**Kompleksnost**: Nizka.

### 3.5 Objective carrier time
**Kaj je**: Čas ko player nosi objective (flag, gold, documents).
**Oksijeva implementacija**: Preverja `ps.powerups[PW_REDFLAG (5)]` ali `ps.powerups[PW_BLUEFLAG (6)]` > 0.
**Naše stanje**: Nimamo.
**Kaj rabiš**: Brati powerups indeksa 5 in 6.
**Kompleksnost**: Nizka.

### 3.6 Vehicle escort time
**Kaj je**: Čas ko player escorta vehicle (tank, truck).
**Oksijeva implementacija**: Preverja `EF_TAGCONNECT (0x00008000)` v eFlags.
**Naše stanje**: Nimamo.
**Kaj rabiš**: Brati eFlags (isto kot za MG mounted).
**Kompleksnost**: Nizka (pridobiš skupaj z 3.2).

### 3.7 Class switch detection
**Kaj je**: Zaznavanje spremembe klase med roundom (npr. soldier→medic).
**Oksijeva implementacija**: V `et_ClientUserinfoChanged` primerja `sess.playerType` s prejšnjo vrednostjo.
**Naše stanje**: Imamo `et_ClientUserinfoChanged` hook (vrstica 2917), ampak le kliče `updateClientCache`. Class beležimo samo ob spawnu.
**Kaj rabiš**: Dodati class switch logiko v obstoječi `et_ClientUserinfoChanged` callback. Shraniti array `{time, from_class, to_class}`.
**Kompleksnost**: Nizka. Hook že obstaja, samo dodaš logiko.

---

## 4. Oksijeve tehnike ki jih NE rabimo (in zakaj)

### 4.1 Metatable lazy caching za clientGuids
Mi imamo `client_cache[]` z eksplicitnim `updateClientCache()`. Funkcionalno enako, drugačen vzorec.

### 4.2 Coordinate-based objective attribution
Oksii dinamično skenira `team_WOLF_checkpoint` entitete. Mi imamo statične koordinate per-map v configu. Oksijevo je bolj robustno za nove mape, ampak naš pristop dela za vse mape ki jih igramo.

### 4.3 5-sekundno shranjevanje weapon statsov
Oksii bere `sess.aWeaponStats[0..27]` vsakih 5 sekund. Mi imamo `et_WeaponFire` hook ki beleži strele v realnem času + endstats datoteke imajo polne weapon state. Naš pristop je natančnejši.

### 4.4 Name enforcement system
Specifično za competitive liga (ETL.lol). Ni relevantno za nas.

### 4.5 Async curl za API submission
Oksii pošilja podatke na REST API. Mi pišemo datoteke ki jih SSH monitor pobere. Drugačna arhitektura.

---

## 5. Predlagan implementacijski plan

### Faza A: Parser izboljšave (brez Lua sprememb)
Izračunaj iz obstoječih path samplov:
1. Stance akumulacija per-player per-round (sekunde v standing/crouching/prone)
2. Sprint čas per-player per-round
3. Peak speed in average speed per-player per-round
4. Total distance per-player per-round
5. Post-spawn distance (prvih 3s po spawn eventu)

### Faza B: Lua minimal - razširi sample polja
Dodaj v `getPlayerMovementState()` in path sample:
1. `stamina` (raw vrednost STAT_SPRINTTIME) → omogoči turtle detection v parserju
2. `eflags_extra` (mounted + escort) → omogoči MG/vehicle čas v parserju
3. `carrying_obj` (powerups 5/6) → omogoči obj carrier čas v parserju
4. `disguised` (powerup 7) → omogoči disguise čas v parserju

### Faza C: Lua - class switch tracking
Dodaj v obstoječi `et_ClientUserinfoChanged`:
1. Primerjaj `sess.playerType` s shranjeno vrednostjo
2. Shrani `{time, from_class, to_class}` v novo sekcijo
3. Parser importira in shrani v DB

### Faza D: DB + API + Frontend
1. Nova tabela `proximity_player_round_stats` za agregirane metrike (stance time, distance, speed, class switches)
2. API endpoint za player round stats
3. Frontend prikaz

---

## 6. Oksijeve eFlags/powerups konstante za referenco

```lua
-- Entity flags (ps.eFlags)
EF_DEAD          = 0x00000001  -- Player je mrtev
EF_CROUCHING     = 0x00000010  -- Crouching (alternativa PMF_DUCKED)
EF_MG42_ACTIVE   = 0x00000020  -- Na mounted MG42
EF_MOUNTEDTANK   = 0x00008000  -- Na tank MG
EF_PRONE         = 0x00080000  -- Prone
EF_PRONE_MOVING  = 0x00100000  -- Crawling
EF_TAGCONNECT    = 0x00008000  -- Vehicle escort (OPOMBA: isti bit kot MOUNTEDTANK!)

-- Powerup indeksi (ps.powerups[N])
PW_REDFLAG       = 5   -- Nosi Axis objective
PW_BLUEFLAG      = 6   -- Nosi Allied objective
PW_OPS_DISGUISED = 7   -- Covert ops disguised

-- Stats indeksi (ps.stats[N])
STAT_SPRINTTIME  = 8   -- Trenutna stamina (0-20000)

-- Body state
BODY_DOWNED      = 67108864  -- r.contents vrednost ko je player downed

-- Sprint
MAX_SPRINT_TIME  = 20000
STAMINA_CHANGE_THRESHOLD = 50
```

---

## 7. Prioritetna ocena

| Prioriteta | Feature | Lua sprememba? | Vrednost |
|-----------|---------|---------------|----------|
| **P1** | Stance/sprint/speed/distance agregacija | NE (parser only) | Visoka - osnovna player analitika |
| **P1** | Post-spawn distance | NE (parser only) | Srednja - movement pattern |
| **P2** | Stamina/turtle v sample | DA (1 polje) | Srednja - stamina management insight |
| **P2** | MG mounted + vehicle escort | DA (eFlags branje) | Srednja - positional play |
| **P2** | Class switch detection | DA (v obstoječi hook) | Srednja - taktične odločitve |
| **P3** | Obj carrier time | DA (powerups) | Nižja - niche |
| **P3** | Disguise time | DA (powerups) | Nižja - samo covert ops |
| **P3** | Downed state tracking | DA (track logika) | Nižja - kill_outcome že pokriva delta čas |

---

*Dokument namenjen za implementacijo s strani agenta. Brez code sprememb - samo raziskava.*
