# Oksii legacy-configs Lua Scripts Analysis
**Datum**: 2026-03-29 | **Repo**: github.com/Oksii/legacy-configs

---

## Pregled repozitorija

Kompletna ET:Legacy competitive server konfiguracija:
- **2 Lua skripta** (root): `stats.lua` (v2.2.0, ~600 vrstic), `combinedfixes.lua` (v1.2, ~340 vrstic)
- **12 Lua sub-modulov** v `luascripts/stats/` (~180KB skupne kode)
- **config.toml** (~20KB) — map objective vzorci za 20+ map
- **9 server config** datotek v `configs/`
- **26 map scriptov** v `mapscripts/`
- **README** s kompletno JSON shemo in TypeScript type definicijami

---

## Inventar skript

### Root skripta

| Skripta | Verzija | Vrstic | Namen |
|---------|---------|--------|-------|
| `stats.lua` | v2.2.0 | ~600 | Entry point — registrira ET callbacks, naloži config, inicializira 12 sub-modulov |
| `combinedfixes.lua` | v1.2 | ~340 | Server admin: default class, GUID blocker, tech pause, team lock, bans, spawn invuln |

### Sub-moduli v `luascripts/stats/`

| Modul | Vrstic | Namen |
|-------|--------|-------|
| `players.lua` | ~200 | GUID cache z lazy metatable, player snapshots (health, pos, stance, flags), class-switch tracking |
| `movement.lua` | ~300 | Per-frame pozicija, razdalja, hitrost (peak/avg), stance akumulacija (10 stanj), spawn distance |
| `events.lua` | ~200 | Obituary/damage/command procesiranje, **hit-region detekcija via differential snapshots**, reinf time |
| `objectives.lua` | ~600 | Pattern-matching na `et_Print` za objective/buildable/flag/shove, carrier tracking, dynamite atribucija |
| `gamelog.lua` | ~200 | In-memory event buffer, strukturirano beleženje z unix timestamps |
| `stats.lua` (sub) | ~250 | Weapon stats iz ET internalov, JSON sestava, API submit via async curl |
| `gamestate.lua` | ~130 | Gamestate machine (warmup/playing/intermission), orkestrira module reset, delayed stats save |
| `gather.lua` | ~950 | Full match management: auto_rename, auto_sort, auto_start (state machine), auto_map, scoring, API |
| `scores.lua` | ~500 | Best-of-3 scoring, stopwatch pravila, fullhold/clinch detection |
| `api.lua` | ~120 | Match ID fetch, version check, route validation |
| `config.lua` | ~130 | TOML config loader z map/buildable normalizacijo |
| `util/http.lua` | ~100 | Async + sync curl helperji, temp file payload handling |
| `util/log.lua` | ~70 | Timestamped file logger z buffered init writes |
| `util/utils.lua` | ~100 | String utilities, distance calculations, JSON sanitization |

---

## Ključne tehnike in vzorci

### A. Hit Region Detection via Differential Snapshots ⭐

ET:Legacy akumulira hit region štetja (`pers.playerStats.hitRegions`). Oksii cachira prejšnji snapshot in primerja ob vsakem damage eventu:

```lua
local function get_hit_region(clientNum)
    local current = get_all_hit_regions(clientNum)
    if not _hit_region_cache[clientNum] then
        _hit_region_cache[clientNum] = current
        return HR_NONE
    end
    for _, ht in ipairs(HR_TYPES) do
        if current[ht] > (_hit_region_cache[clientNum][ht] or 0) then
            _hit_region_cache[clientNum] = current
            return ht
        end
    end
    _hit_region_cache[clientNum] = current
    return HR_NONE
end
```

**Primerjava s Slomix**: Naš proximity_tracker.lua NE sledi hit regionom. Ta pristop je izjemno poceni in daje HR_HEAD, HR_ARMS, HR_BODY, HR_LEGS atribucijo na vsak damage event.

### B. Rich Player Snapshots ⭐

`players.lua` daje `get_snapshot()` s 12+ state flags:

```lua
return {
    guid, team, class, health, pos,
    is_prone, is_crouch, is_mounted, is_leaning,
    is_carrying_obj, is_disguised, is_downed, is_sprint
}
```

Sprint detekcija z delta na `ps.stats[8]` (STAT_SPRINTTIME) s threshold za izogib šumu.

**Primerjava**: Naš proximity_tracker ujame pozicijo in nekaj stanja, ampak ne do te ravni detajla. Sprint detekcija via stamina delta je nekaj česar mi ne delamo.

### C. Spawn Distance Tracking ⭐

`movement.lua` detektira spawn via `pers.lastSpawnTime` in sledi razdalji v prvih 3 sekundah po spawnu → "spawn aggressiveness" metrika.

```lua
if last_spawn > 0
and (level_time - last_spawn) < SPAWN_DETECTION_THRESHOLD
and last_spawn > sp.last_detected_spawn_time then
    -- Track for SPAWN_TRACK_DURATION (3000ms)
```

**Primerjava**: Imamo spawn timing v proximity_tracker, ampak ne izoliramo first-3-seconds metrike.

### D. Reinforcement Wave Timing ⭐

`events.lua` izračuna natančen čas reinforcement wave na vsak kill event:

```lua
local function calc_reinf_time(team)
    local start_time  = tonumber(et.trap_GetConfigstring(et.CS_LEVEL_START_TIME))
    local deploy_time = tonumber(et.trap_Cvar_Get(deploy_cvar))
    local offset = _aReinfOffset[team]
    return (deploy_time - ((offset + _level_time - start_time) % deploy_time)) * 0.001
end
```

Vsakemu kill eventu doda `killer_reinf` in `victim_reinf` (sekunde do naslednjega wave). Omogoča analizo "clutch kill" pred waveom vs "free kill" po waveu.

**Primerjava**: Mi NE izračunavamo reinforcement timinga. To je močan kandidat za prevzem (~15 vrstic kode).

### E. Objective Attribution via Coordinate Proximity

`objectives.lua` za flag capture in escort uporablja coordinate-based atribucijo — najde najbližjega igralca znanim objective koordinatam:

```lua
local function find_nearest_players(coordinates, team)
    -- Iterira connected players, izračuna 3D razdaljo
    -- Vrne players znotraj MAX_OBJ_DISTANCE (500 game units)
```

Flag koordinate so delno auto-odkrite s skeniranjem entity `team_WOLF_checkpoint` classnames ob map init.

**Primerjava**: Naš proximity_tracker ima objective coordinate tracking v v6.01, ampak Oksiijev pristop skeniranja entity classnames za flag pozicije ob runtime je nekaj kar bi lahko prevzeli za zmanjšanje hardkodiranih koordinatnih tabel.

### F. TOML-Based Map Objective Config

`config.toml` vsebuje 20+ map z natančnimi vzorci za vsak tip objectiva: construct, destruct, plant, steal, secure, return, flag capture, escort.

```toml
[goldrush]
objectives = [
    { name = "Bank Door", type = "destruct", text = "Allied team has destroyed the bank doors!" },
    { name = "Bank Bars", type = "destruct", text = "Allied team has destroyed the bank bars!" },
    { name = "Gold Crate 1", type = "steal", text = ".*has stolen a Gold Crate!" },
]
buildables = [
    { name = "Tank Barrier", construct = "Allied team has built the Tank Barrier!", destruct = "..." },
]
```

**Primerjava**: Naše objective sledenje v Lua plasti je minimalno — večino delamo v Python parserju iz endstats. TOML pristop je čistejši.

### G. Async HTTP z Temp File Pattern

```lua
os.execute(string.format("sleep 15 && rm -f %s &", http.shell_escape(tmp)))
```

Piše JSON v temp file in pošlje curl z `--data-binary @tmpfile`. Varnejše za velike payloade.

### H. Delayed Stats Save

Čaka 3 sekunde po intermission preden shrani stats. Preprečuje frame lag ob natančnem prehodnem trenutku.

### I. Gamestate Machine

Čista state machine za warmup → playing → intermission prehode. Orkestrira vse module resete.

### J. Gather Match Auto-Start

Polna state machine za competitive match management:
```
IDLE → ARMED → WARNING_60 → WARNING_10 → COUNTDOWN → START_ATTEMPT → DONE
                                                                  → LATE_JOIN_COUNTDOWN
```

Route validacija (re-preverja z API da je match še aktiven pred countdownom).

---

## Error Handling vzorci

1. **pcall wrapping**: Vsi `et.gentity_get` klici za hit regions oviti v pcall
2. **Config validacija ob init**: Preveri API token format, URL veljavnost, map config prisotnost
3. **Deferred init**: Version check odložen na prvi `et_RunFrame` da ne blokira init
4. **Log buffering**: `buffer_start()`/`buffer_flush()` za batch file writes ob init
5. **Init timing**: Meri in logira initialization time v ms
6. **Route validacija**: Pred T-60 opozorilom re-preveri da je match še registriran
7. **Konsistentni nil guards**: Vsak modul varuje pred nil iz `players.guids`, nil pozicijami, nil health

---

## Arhitekturna primerjava

| Aspekt | Oksii | Slomix |
|--------|-------|--------|
| **Arhitektura** | 14 modularnih Lua datotek z dependency injection | 2 monolitni Lua datoteki (1420 + 4271 vrstic) |
| **Data Output** | En JSON payload na API endpoint per round | CSV/text datoteke via SSH + ločen webhook |
| **Objective Tracking** | 20+ map s polnimi TOML vzorci | Omejeno, večina v Python parserju |
| **Hit Regions** | Differential snapshot, per-damage-event | Ni |
| **Movement/Stance** | 10 stance tipov, speed, distance, spawn distance | Position tracking, osnovna razdalja |
| **Gamelog** | Rich timeline z vsakim event tipom | Ločeni proximity eventi samo |
| **Error Handling** | pcall wraps, config validacija, route validacija | Osnovni nil guards |
| **Konfiguracija** | Env vars + TOML, Docker-friendly | .env za bot, hardkodirano v Lua |
| **Match Management** | Full gather sistem (rename/sort/start/map/config/scores) | Ni (ročno) |
| **Dokumentacija** | Kompletni README s TypeScript tipi | Inline komentarji |

---

## Priporočila za prevzem (po prioriteti)

### Visoka prioriteta (velik učinek, zmeren trud)

| # | Kaj | Zakaj | Trud |
|---|-----|-------|------|
| 1 | **Hit Region Tracking** | Differential snapshot = low-cost, per-damage HR_HEAD/ARMS/BODY/LEGS | ~50 vrstic Lua + DB tabela |
| 2 | **Reinforcement Wave Timing** | `killer_reinf`/`victim_reinf` na kill events = clutch vs free kill analiza | ~15 vrstic Lua |
| 3 | **Spawn Distance Metric** | Razdalja v prvih 3s po spawnu = spawn aggressiveness | ~30 vrstic Lua |
| 4 | **Entity Scanning za Flag Coords** | Auto-discover checkpoint pozicije ob map init | ~40 vrstic Lua, manj hardkodiranja |

### Srednja prioriteta (dober učinek, nizek trud)

| # | Kaj | Zakaj | Trud |
|---|-----|-------|------|
| 5 | **TOML Map Objective Config** | Čistejše kot hardkodirani vzorci | config datoteka + loader |
| 6 | **Delayed Stats Save** | 3s zamik po intermission prepreči frame lag | ~10 vrstic |
| 7 | **Log Buffering ob Init** | Batch log writes zmanjša I/O | Trivialno |
| 8 | **Temp File za HTTP Payloade** | Varnejše za velike JSON payloade | ~20 vrstic |

### Dolgoročno (aspiracijsko)

| # | Kaj | Zakaj | Trud |
|---|-----|-------|------|
| 9 | **Modularizacija proximity_tracker** | 14 modulov po ~200 vrstic >> 1 datoteka 4271 vrstic | Velik refactor |
| 10 | **API-first data submission** | JSON na API namesto CSV datoteke via SSH | Arhitekturna sprememba |
| 11 | **Gather Match Management** | Auto-rename/sort/start za organized play | Nov feature |

---

## Ključni zaključek

Oksiijev stats sistem je **produkcijsko zrel competitive match statistics platform** zasnovan za organizirano igro. Izstopajo:

1. **Data richness**: Vsak kill/damage event nosi polno kontekstualno stanje (pozicija, stance, health, class, reinforcement timing, hit region)
2. **Modularnost**: 14 datotek po ~200 vrstic vs naši 2 monoliti
3. **API-first design**: JSON na centralni API, brez SSH pollinga in file parsinga
4. **Objective intelligence**: 20+ map s polnim pattern matchingom

Najbolj akcijski prevzemi za Slomix: **hit region tracking** + **reinforcement timing** + **spawn distance** + **entity scanning za coords**. To so 4 low-cost additions (~135 vrstic Lua skupaj) ki bistveno obogatijo naše analytics.
