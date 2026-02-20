# C0RNP0RN7 Developer Report (LuaJIT Compatibility)
**Date:** Thursday, February 19, 2026  
**Repo:** `/home/samba/share/slomix_discord`

## 1) Purpose
This report answers:
- what changed
- why it changed
- where it changed
- which files to send to the original `c0rnp0rn7.lua` developer

for the LuaJIT compatibility work.

## 2) Source and Provenance
The checker used is the script shared by ET:Legacy devs:
- `check-etl-luajit-incompatibilities` (Vorschreibung gist)

Historical "unpatched" reference for `c0rnp0rn7.lua` in this repo came from git history:
- path: `test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua`
- last tracked before cleanup in commit: `6a52ed6f18dc65af412cefb34b356c241f769186`
- extracted pre-cleanup version from parent commit:
  - `git show 6a52ed6f18dc65af412cefb34b356c241f769186^:test_suite/2910claudeHISTORYfixes2/c0rnp0rn7.lua`
- exported copy:
  - `docs/reference/c0rnp0rn7_prepatch_from_git_history.lua`

Note:
- root `c0rnp0rn7.lua` itself was not tracked in older history in this repository.
- The historical tracked test-suite copy is the best in-repo pre-patch reference.

## 3) Pre-Patch Findings (Relevant Scripts)
From isolated scan of deployed-relevant scripts (`c0rnp0rn7.lua`, `endstats.lua`, `vps_scripts/stats_discord_webhook.lua`) before patching:
- `c0rnp0rn7.lua`: 8 findings (`LJIT002=5`, `LJIT003=3`)
- `endstats.lua`: 4 findings (`LJIT002=2`, `LJIT003=2`)
- `vps_scripts/stats_discord_webhook.lua`: 0 findings

### `c0rnp0rn7.lua` pre-patch issues
- `LJIT002`: `>>` and `<<` not supported by LuaJIT parser
- `LJIT003`: bitwise `|` and `&` operators not supported by LuaJIT parser

Examples detected by checker:
- reinforcement offsets used `>>` and `1 << ...`
- weapon mask used `dwWeaponMask | (1 << j)`
- pause check used `(1 << 4 & cs)`

## 4) Exact Compatibility Changes (What/Why/Where)

### 4.1 `c0rnp0rn7.lua`
Locations in current patched file:
- `c0rnp0rn7.lua:120`
- `c0rnp0rn7.lua:121`
- `c0rnp0rn7.lua:203`
- `c0rnp0rn7.lua:472`
- `c0rnp0rn7.lua:486`

Changes:

```lua
-- before
offsets[et.TEAM_ALLIES] = reinfSeeds[1] >> REINF_BLUEDELT
offsets[et.TEAM_AXIS]   = math.floor(reinfSeeds[2] / (1 << REINF_REDDELT))

-- after
offsets[et.TEAM_ALLIES] = bit.rshift(reinfSeeds[1], REINF_BLUEDELT)
offsets[et.TEAM_AXIS]   = bit.rshift(reinfSeeds[2], REINF_REDDELT)
```

```lua
-- before
dwWeaponMask = dwWeaponMask | (1 << j)

-- after
dwWeaponMask = bit.bor(dwWeaponMask, bit.lshift(1, j))
```

```lua
-- before
if (1 << 4 & cs) == 1 then
...
if (1 << 4 & cs) == 0 then

-- after
if bit.band(bit.lshift(1, 4), cs) == 1 then
...
if bit.band(bit.lshift(1, 4), cs) == 0 then
```

Why:
- LuaJIT 2.1 uses Lua 5.1 syntax baseline and does not parse Lua 5.3 bitwise operators.
- `bit.*` is the correct LuaJIT-compatible equivalent.

### 4.2 `endstats.lua`
Locations:
- `endstats.lua:1072`
- `endstats.lua:1090`

Changes:

```lua
-- before
if (1 << 4 & cs) == 1 then
...
if (1 << 4 & cs) == 0 then

-- after
if bit.band(bit.lshift(1, 4), cs) == 1 then
...
if bit.band(bit.lshift(1, 4), cs) == 0 then
```

Why:
- same parser compatibility issue (`LJIT002` + `LJIT003`).

## 5) Additional Diff Context (Historical vs Current `c0rnp0rn7.lua`)
There are non-LuaJIT differences between historical tracked copy and current root file.
These include pause/death-time accounting and objective checks. They are visible in:
- `docs/reference/c0rnp0rn7_prepatch_vs_current.diff`

Important:
- Not every hunk in that diff is a LuaJIT compatibility change.
- The LuaJIT-specific edits are the 5 line-level replacements listed in section 4.1.

## 6) Post-Patch Verification
Re-scan results:
- isolated scan of `c0rnp0rn7.lua`, `endstats.lua`, `vps_scripts/stats_discord_webhook.lua`: **No findings**
- isolated scan of proximity scripts: **No findings**

## 7) Files to Send the Developer

### Minimal package (recommended)
1. `docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md`  
Reason: clear narrative of what/why/where.
2. `docs/reference/c0rnp0rn7_prepatch_vs_current.diff`  
Reason: exact patch-level diff.
3. `c0rnp0rn7.lua`  
Reason: final patched script ready to test on LuaJIT build.

### Full provenance package (if he wants source traceability)
1. `docs/reports/C0RNP0RN7_DEVELOPER_REPORT_2026-02-19.md`
2. `docs/reference/c0rnp0rn7_prepatch_from_git_history.lua`
3. `docs/reference/c0rnp0rn7_prepatch_vs_current.diff`
4. `c0rnp0rn7.lua`
5. `endstats.lua` (if he also wants round-end toggle compatibility update)
6. `zac0rna.md` (full repository-wide audit)

## 8) Reproduction Commands
Run checker on a single script:

```bash
tmpdir=$(mktemp -d)
cp c0rnp0rn7.lua "$tmpdir/"
python3 /tmp/check-etl-luajit-incompatibilities --root "$tmpdir"
```

Run checker on the deployed trio:

```bash
tmpdir=$(mktemp -d)
cp c0rnp0rn7.lua "$tmpdir/"
cp endstats.lua "$tmpdir/"
cp vps_scripts/stats_discord_webhook.lua "$tmpdir/"
python3 /tmp/check-etl-luajit-incompatibilities --root "$tmpdir"
```

Expected post-patch output: `No findings.`

