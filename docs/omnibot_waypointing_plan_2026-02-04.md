# Omni-bot Waypointing Plan (2026-02-04)

This is a step-by-step plan to create missing waypoints for:
- `et_brewdog`
- `erdenberg_t2`

We’ll use Omni-bot waypoint tools locally (not on the dedicated server).

## Why local?
Waypointing requires the Omni-bot **mod** running in-game (client), and is not supported on a dedicated server.

## Prep Checklist
- A local ET install with Omni-bot enabled.
- The target map PK3 installed locally.
- `omnibot_enable 1` in local config.
- Load the map in a local server or listen server.

## Core Waypointing Commands
These are the basics you’ll use in-game:
- `waypoint_add` → add a waypoint at your location.
- `waypoint_connect <id1> <id2>` → link two waypoints.
- `waypoint_save` → write `.way` to disk.
- `waypoint_load` → load existing waypoints.
- `waypoint_delete <id>` → remove a bad node.
- `waypoint_save` again after edits.

## Flow (Per Map)
1. Load the map.
2. Enable waypoint mode and start placing a **basic path**:
   - spawn → objectives → exits/returns
3. Connect nodes so bots can traverse both directions.
4. Add extra nodes for:
   - ladders / jump spots
   - narrow alleys
   - alternate routes
5. Save the `.way` file.

## Goals / Scripts
For objective maps, bots also need:
- `mapname.gm`
- `mapname_goals.gm`

These define objectives and behaviors. If you can’t author them manually, use the map’s existing goals file as a base (if available) and adjust.

## Deliverables to Upload
Upload these files to the server nav directory:
```
/home/et/etlegacy-v2.83.1-x86_64/legacy/omni-bot/et/nav
```
Files needed:
- `mapname.way`
- `mapname.gm`
- `mapname_goals.gm`

Omni-bot loads these by **exact map name**.

## Verification
1. Restart map (`map_restart 0`)
2. Watch bots:
   - If they get stuck, add waypoints and reconnect.
   - If they ignore objectives, check goals file.

## Optional: Split Work
- You can waypoint a map in stages:
  - First: basic pathing
  - Second: objective routes
  - Third: refinement & cleanup
