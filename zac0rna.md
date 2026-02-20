# zac0rna.md

## LuaJIT Compatibility Audit (SI + EN + Lua)
**Date:** Thursday, February 19, 2026  
**Repository root:** `/home/samba/share/slomix_discord`  
**Checker used:** `check-etl-luajit-incompatibilities` (Vorschreibung gist)

---

## 1) Slovensko (SI): Povzetek

Ta dokument je podroben pregled LuaJIT kompatibilnosti za vse `.lua` skripte v repozitoriju.

- Skupno pregledanih skript: **23**
- Skupno najdenih zadetkov: **44**
- Tipi napak:
  - `LJIT002` (`<<` ali `>>`): **25**
  - `LJIT003` (`&` ali `|` kot bitwise operator): **19**

Ključno:

- Aktivne/kljucne skripte, ki jih uporabljate za stats/proximity pipeline, so po patchu ciste:
  - `c0rnp0rn7.lua` -> **0 findings**
  - `endstats.lua` -> **0 findings**
  - `vps_scripts/stats_discord_webhook.lua` -> **0 findings**
  - `proximity/lua/proximity_tracker.lua` -> **0 findings**
  - `proximity_tracker.lua` -> **0 findings**
  - `proximity_tracker_v2.lua` -> **0 findings**
  - `proximity_tracker_v3.lua` -> **0 findings**

Najdene napake so vecinoma v:
- backup/dev/reference/test/prompt kopijah
- starih ali ne-deployanih variantah

---

## 2) English (EN): Executive Summary

This is a full LuaJIT compatibility audit for all `.lua` scripts in the repository.

- Total scripts scanned: **23**
- Total findings: **44**
- Rule distribution:
  - `LJIT002` (`<<` / `>>`): **25**
  - `LJIT003` (`&` / `|` bitwise syntax): **19**

Important:

- The production-relevant scripts are clean after patching:
  - `c0rnp0rn7.lua` -> **0 findings**
  - `endstats.lua` -> **0 findings**
  - `vps_scripts/stats_discord_webhook.lua` -> **0 findings**
  - `proximity/lua/proximity_tracker.lua` -> **0 findings**
  - `proximity_tracker.lua` -> **0 findings**
  - `proximity_tracker_v2.lua` -> **0 findings**
  - `proximity_tracker_v3.lua` -> **0 findings**

Most findings are in backup/dev/reference/test/prompt copies, not in the currently used runtime scripts.

---

## 3) Test Method / Metoda testiranja

Command used for full repository scan:

```bash
python3 /tmp/check-etl-luajit-incompatibilities \
  --root /home/samba/share/slomix_discord \
  --json > /tmp/luajit_all_findings.json
```

Script inventory:

```bash
find . -type f -name '*.lua' | sed 's#^./##' | sort
```

Per-file zero/non-zero verification was also done with isolated temp-root scans for selected files.

---

## 4) Full Per-Script Report (All 23 scripts)

### 4.1 Scripts with findings

#### `backups/fiveeyes_pre_implementation_20251006_075852/c0rnp0rn4.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `117:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `118:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `241:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `241:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `backups/fiveeyes_pre_implementation_20251006_075852/dev/c0rnp0rn4.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `117:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `118:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `241:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `241:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `dev/c0rnp0rn.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `117:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `118:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `200:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `200:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `dev/c0rnp0rn4.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `117:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `118:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `241:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `241:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `docs/reference/oksii-game-stats-web.lua`
- Findings: **12** (`LJIT002=3`, `LJIT003=9`)
- `673:20` `LJIT003` -> `return (eFlags & EF_READY) ~= 0`
- `1316:44` `LJIT003` -> `local isDead = (eFlags & EF_DEAD) ~= 0`
- `1348:61` `LJIT003` -> `local isCrouching = (eFlags & EF_CROUCHING) ~= 0`
- `1349:57` `LJIT003` -> `local isProne = (eFlags & EF_PRONE_MOVING) ~= 0 or (eFlags & EF_PRONE) ~= 0`
- `1349:92` `LJIT003` -> `local isProne = (eFlags & EF_PRONE_MOVING) ~= 0 or (eFlags & EF_PRONE) ~= 0`
- `1350:59` `LJIT003` -> `local isMounted = (eFlags & EF_MG42_ACTIVE) ~= 0 or (eFlags & EF_MOUNTEDTANK) ~= 0`
- `1350:93` `LJIT003` -> `local isMounted = (eFlags & EF_MG42_ACTIVE) ~= 0 or (eFlags & EF_MOUNTEDTANK) ~= 0`
- `1360:68` `LJIT003` -> `local isVehicleConnected = (eFlags & EF_TAGCONNECT) ~= 0`
- `1548:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `1549:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `2688:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `2688:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `prompt_instructions/c0rnp0rn3.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `120:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `121:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `202:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `202:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `prompt_instructions/gamestats_from_develper_of_cornporn/game-stats.lua`
- Findings: **2** (`LJIT002=1`, `LJIT003=1`)
- `58:35` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `58:40` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `prompt_instructions/newchat/c0rnp0rn3.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `120:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `121:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `202:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `202:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

#### `server/endstats_modified.lua`
- Findings: **2** (`LJIT003=2`)
- `680:16` `LJIT003` -> `if (cs & 8) == 8 then`
- `684:16` `LJIT003` -> `if (cs & 8) ~= 8 then`

#### `test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua`
- Findings: **4** (`LJIT002=3`, `LJIT003=1`)
- `117:45` `LJIT002` -> `offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT`
- `118:61` `LJIT002` -> `offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))`
- `200:34` `LJIT003` -> `dwWeaponMask = dwWeaponMask | (1 << j)`
- `200:39` `LJIT002` -> `dwWeaponMask = dwWeaponMask | (1 << j)`

### 4.2 Scripts without findings

- `c0rnp0rn.lua` -> **0**
- `c0rnp0rn7.lua` -> **0**
- `c0rnp0rn7real.lua` -> **0**
- `c0rnp0rnMAYBEITSTHISONE.lua` -> **0**
- `endstats.lua` -> **0**
- `proximity/lua/proximity_tracker.lua` -> **0**
- `proximity_tracker.lua` -> **0**
- `proximity_tracker_v2.lua` -> **0**
- `proximity_tracker_v3.lua` -> **0**
- `server/c0rnp0rn3.lua` -> **0** (placeholder file in this repo)
- `venv/lib/python3.10/site-packages/matplotlib/mpl-data/kpsewhich.lua` -> **0**
- `vps_scripts/stats_discord_webhook.lua` -> **0**
- `website/venv/lib/python3.10/site-packages/matplotlib/mpl-data/kpsewhich.lua` -> **0**

---

## 5) Lua Examples: Original vs Patched

### 5.1 Reinforcement bit shifts

```lua
-- Original (Lua 5.3 syntax, not LuaJIT-compatible)
offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT
offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))

-- Patched (LuaJIT-compatible)
offsets[et.TEAM_ALLIES] = bit.rshift(reinfSeeds[1], REINF_BLUEDELT)
offsets[et.TEAM_AXIS]   = bit.rshift(reinfSeeds[2], REINF_REDDELT)
```

### 5.2 Weapon mask bit set

```lua
-- Original
dwWeaponMask = dwWeaponMask | (1 << j)

-- Patched
dwWeaponMask = bit.bor(dwWeaponMask, bit.lshift(1, j))
```

### 5.3 Pause flag check

```lua
-- Original
if (1 << 4 & cs) == 1 then
    paused = true
end

if (1 << 4 & cs) == 0 then
    paused = false
end

-- Patched
if bit.band(bit.lshift(1, 4), cs) == 1 then
    paused = true
end

if bit.band(bit.lshift(1, 4), cs) == 0 then
    paused = false
end
```

---

## 6) Notes for team chat (SI + EN)

### SI
- Ja, patch je bil narejen med kompatibilnostnim pregledom.
- Gre za ciljno menjavo `<<`, `>>`, `|`, `&` v `bit.*` klice.
- Aktivne skripte so po zadnjem skenu ciste.

### EN
- Yes, the patch was applied during compatibility validation.
- Changes are targeted replacements of `<<`, `>>`, `|`, `&` with `bit.*` calls.
- Active scripts are clean in the latest scan.

---

## 7) Practical next step

If you want strict repeatability, run this before deployment:

```bash
python3 /tmp/check-etl-luajit-incompatibilities \
  --root /home/samba/share/slomix_discord \
  --exclude-dir backups \
  --exclude-dir docs \
  --exclude-dir prompt_instructions \
  --exclude-dir dev \
  --exclude-dir test_suite \
  --exclude-dir server \
  --exclude-dir node_modules \
  --exclude-dir .git
```

Expected result for production-relevant scripts after patch: `No findings.`

---

## 8) Git History Evidence (Where pre-patch came from)

### SI
- V tej kodi **root `c0rnp0rn7.lua` ni bil tracked** v Git zgodovini.
- Najdena pa je starejsa tracked kopija:
  - `test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua`
- Commit, kjer je bila ta pot odstranjena iz trackinga:
  - `6a52ed6f18dc65af412cefb34b356c241f769186` (2025-11-03)
- Pre-patch verzijo dobis iz parent commit-a:

```bash
git show 6a52ed6f18dc65af412cefb34b356c241f769186^:test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua
```

Ta zgodovinska verzija vsebuje ne-LuaJIT sintakso, npr.:
- `reinfSeeds[1] >> REINF_BLUEDELT`
- `dwWeaponMask = dwWeaponMask | (1 << j)`

### EN
- In this repository, **root `c0rnp0rn7.lua` was not tracked** in git history.
- A tracked historical copy exists at:
  - `test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua`
- Commit where that path was removed from tracking:
  - `6a52ed6f18dc65af412cefb34b356c241f769186` (2025-11-03)
- Retrieve the pre-patch content from the parent commit:

```bash
git show 6a52ed6f18dc65af412cefb34b356c241f769186^:test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua
```

This historical version includes non-LuaJIT bitwise syntax, e.g.:
- `reinfSeeds[1] >> REINF_BLUEDELT`
- `dwWeaponMask = dwWeaponMask | (1 << j)`
