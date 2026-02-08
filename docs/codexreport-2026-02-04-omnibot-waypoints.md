# Codex Report — Omni-bot Waypoints Audit (2026-02-04)

## Summary
Checked the server’s Omni-bot nav directory to see which maps in your rotation already have waypoint/goals data.

## Waypoints found (ready)
These have `.way` + `.gm` + `_goals.gm` in:
`/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/nav`

- `supply`
- `etl_sp_delivery`
- `te_escape2`
- `sw_goldrush_te`
- `braundorf_b4`

## Missing / Mismatch
These maps from your rotation do **not** have an exact match in nav:

- `etl_adlernest`  
  Present as `adlernest` / `adlernest_2`, but **not** `etl_adlernest`.
- `etl_frostbite`  
  Present as `etl_frostbite_v3`, `_v4`, `_v10`, but **not** `etl_frostbite`.
- `et_brewdog`  
  No nav files found.
- `erdenberg_t2`  
  Found in `incomplete_navs/with_script` (not in main nav).

## Why this matters
Omni-bot loads waypoints by **map name**. If the map name doesn’t match the `.way/.gm` filenames exactly, bots won’t load them.

## Next options
1. Pull waypoint packs from the Omni-bot Assembla SVN repository and check for missing map names.
2. If missing, create new waypoints locally using Omni-bot waypoint tools, then upload `.way/.gm/_goals.gm` to the server.
3. If the `etl_` map is identical to vanilla (e.g. adlernest), duplicate files and rename carefully to match the map name.

## Actions Taken (2026-02-04)
- Created **backups** in:
  - `/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/nav_backups/2026-02-04`
- Duplicated nav files to match ETL map names:
  - `adlernest.*` → `etl_adlernest.*`
  - `etl_frostbite_v4.*` → `etl_frostbite.*`
- Verified new files exist:
  - `etl_adlernest.way / .gm / _goals.gm`
  - `etl_frostbite.way / .gm / _goals.gm`

## Incomplete Navs (Potential Stopgap)
Found these in:
`/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/incomplete_navs/with_script`

- `erdenberg_t2.way`
- `erdenberg_t2.gm`
- `erdenberg_t2_goals.gm`

If you want, we can temporarily copy these into the main nav folder to give bots *some* pathing,
but they are marked incomplete.

## Assembla SVN Status
Attempted to access the Omni-bot Assembla SVN URLs without credentials.  
The server responded **401 Unauthorized**, so we need valid credentials or a public mirror.

## Public Pack Attempt (Fearless-Assassins)
Tried downloading Omni-bot 0.81 from Fearless-Assassins, but it returned an HTML login page
instead of a zip (no public direct access).

## Stopgap Applied
Copied incomplete `erdenberg_t2.*` into the main nav folder to give bots baseline pathing:
- `erdenberg_t2.way`
- `erdenberg_t2.gm`
- `erdenberg_t2_goals.gm`
