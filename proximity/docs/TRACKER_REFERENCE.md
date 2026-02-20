# Proximity Tracker Reference (v4.2)

Complete reference of what `proximity/lua/proximity_tracker.lua` captures and writes.

## Runtime Hooks

Lua callbacks used by the tracker:

- `et_InitGame(levelTime, randomSeed, restart)`
- `et_RunFrame(levelTime)`
- `et_Damage(target, attacker, damage, damageFlags, meansOfDeath)`
- `et_Obituary(victim, killer, meansOfDeath)`
- `et_ClientSpawn(clientNum, revived, teamChange, restoreHealth)`
- `et_ClientDisconnect(clientNum)`
- `et_ClientConnect(clientNum, firstTime, isBot)`
- `et_ClientUserinfoChanged(clientNum)`

## Key Config Defaults

Current defaults from tracker code:

- `position_sample_interval = 200` ms
- `crossfire_window_ms = 1000`
- `escape_time_ms = 5000`
- `escape_distance = 300`
- `reaction_window_ms = 5000`
- `dodge_angle_threshold_deg = 45`
- `dodge_min_step_units = 24`
- `objective_tracking = true`
- `objective_radius = 500`

## Output Sections

Per round, tracker writes:

1. `ENGAGEMENTS`
2. `PLAYER_TRACKS`
3. `KILL_HEATMAP`
4. `MOVEMENT_HEATMAP`
5. `OBJECTIVE_FOCUS` (optional)
6. `REACTION_METRICS` (optional, feature-flagged)

Exact field layouts: `proximity/docs/OUTPUT_FORMAT.md`.

## PLAYER_TRACKS

One row per tracked life/spawn window.

Metadata fields:

- `guid`
- `name`
- `team` (`AXIS` / `ALLIES`)
- `class` (`SOLDIER` / `MEDIC` / `ENGINEER` / `FIELDOPS` / `COVERTOPS`)
- `spawn_time`
- `death_time`
- `first_move_time`
- `death_type` (`killed`, `selfkill`, `fallen`, `world`, `teamkill`, `round_end`, `disconnect`, `unknown`)
- `samples`

Path sample tuple (per point):

- `time,x,y,z,health,speed,weapon,stance,sprint,event`

## ENGAGEMENTS

One row per target-under-pressure combat window.

Core fields include:

- identity: `id`, `target_guid`, `target_name`, `target_team`
- timing: `start_time`, `end_time`, `duration`
- result: `outcome`, `killer_guid`, `killer_name`
- pressure: `total_damage`, `num_attackers`
- coordination: `is_crossfire`, `crossfire_delay`, `crossfire_participants`
- spatial: start/end coords, `distance_traveled`, full `positions` path
- attacker bundle: serialized attacker list with damage/hits/timings/weapons

## Crossfire Detection

Crossfire is set when second attacker lands hit inside `crossfire_window_ms` from first hit on same target.

Stored:

- boolean `is_crossfire`
- `crossfire_delay` ms
- participant GUID list

## Escape Detection

Engagement closes as `escaped` when both hold:

- no incoming hit for `escape_time_ms`
- moved at least `escape_distance` from last-hit position

## Objective Focus (Optional)

When `objective_tracking` is enabled and map coords exist:

- nearest objective sampled for tracked players
- average objective distance accumulated
- time within objective radius accumulated
- top objective label selected for output row

Written in `OBJECTIVE_FOCUS`.

## Reaction Metrics (Tier-B)

Damage-triggered response timings captured per engagement in `REACTION_METRICS`.

Fields:

- `return_fire_ms`: target damages an original attacker after first incoming hit.
- `dodge_reaction_ms`: first significant direction change after first hit.
- `support_reaction_ms`: teammate damages original attacker after first hit.
- plus: `target_class`, `num_attackers`, `start_time`, `end_time`, `duration`.

Notes:

- Empty value means no qualifying event inside `reaction_window_ms`.
- Metrics are only written when `reaction_tracking` feature flag is on.

## Heatmaps

`KILL_HEATMAP`:

- `grid_x`, `grid_y`, `axis_kills`, `allies_kills`

`MOVEMENT_HEATMAP`:

- `grid_x`, `grid_y`, `traversal`, `combat`, `escape`

## Player Identity and Class Resolution

- GUID from `cl_guid` when available, else slot fallback (`SLOT{n}`).
- Class from `sess.playerType`.
- Team from `sess.sessionTeam`.
- Names sanitized for delimiter safety.

## Data Not Captured Yet

Still missing / partial:

- authoritative round winner + objective completion state timeline
- persistent scrim-team identity beyond axis/allies side
- directional damage vectors / projectile trajectories
- full per-objective phase transitions

Use `proximity/docs/GAPS_AND_ROADMAP.md` for roadmap priorities.
