# Session Notes: 2026-01-18

## Goal
Refactor the proximity tracker to create a simplified "test mode" for validating core player lifecycle tracking before testing advanced analytics.

## Problem Statement
The proximity tracker v4.0 had many advanced features (crossfire detection, escape detection, heatmaps) tightly coupled with core tracking. For live testing, we needed:
1. A way to disable advanced features independently
2. Focus on core lifecycle: spawn → movement → end state
3. Human-readable output for debugging player journeys
4. Death type categorization (killed/selfkill/fallen/etc.)

## Solution: Proximity Tracker v4.1

### New Features

#### 1. Test Mode Configuration
```lua
config.test_mode = {
    enabled = false,            -- Master toggle
    lifecycle_log = true,       -- Output human-readable log
    action_annotations = true,  -- Track damage events
}
```
When `test_mode.enabled = true`, all advanced features are automatically disabled.

#### 2. Feature Flags
```lua
config.features = {
    engagement_tracking = true,   -- Damage analytics
    crossfire_detection = true,   -- Multi-attacker detection
    escape_detection = true,      -- Escape timeout tracking
    heatmap_generation = true,    -- Spatial heatmaps
}
```
Each feature can be controlled independently, or all disabled via test_mode.

#### 3. Death Type Categorization
New `getDeathType()` function categorizes end states:
- `killed` - Died to enemy player
- `selfkill` - /kill command (MOD 37)
- `fallen` - Fall damage (MOD 38)
- `world` - Environmental death
- `teamkill` - Killed by teammate
- `round_end` - Alive when round ends
- `disconnect` - Player disconnected

#### 4. Action Event Tracking
Damage events (received/dealt) are now stored in track.actions:
```lua
{
    time = 5000,
    type = "dmg_recv",  -- or "dmg_dealt"
    amount = 25,
    from_name = "Player2",
    weapon = 8
}
```

#### 5. Lifecycle Log Output
New human-readable `_lifecycle.txt` file format:
```
[SPAWN] guid=ABC123 name=Player1 team=AXIS class=SOLDIER pos=(100,200,0) time=5000
  +500ms: MOVE pos=(150,220,0) speed=70.5 health=100
  +1000ms: ACTION type=dmg_recv amount=15 from=Player2 weapon=10
  +1500ms: MOVE pos=(180,250,0) speed=45.0 health=85
[END] guid=ABC123 type=killed killer=Player2 pos=(200,280,0) time=6500 duration=1500ms
```

### Files Modified

| File | Changes |
|------|---------|
| `lua/proximity_tracker.lua` | v4.0 → v4.1: test_mode config, feature flags, death type categorization, action tracking, lifecycle log output, feature guards around advanced analytics |
| `parser/parser.py` | Added death_type to PlayerTrack dataclass, backward-compatible parsing for v4/v4.1 formats |

### Output Format Changes

PLAYER_TRACKS format updated (backward compatible):
- v4.0: `guid;name;team;class;spawn_time;death_time;first_move_time;samples;path`
- v4.1: `guid;name;team;class;spawn_time;death_time;first_move_time;death_type;samples;path`

Parser auto-detects format based on field count.

## Usage

### Enable Test Mode
Edit `proximity_tracker.lua`:
```lua
test_mode = {
    enabled = true,
    lifecycle_log = true,
    action_annotations = true,
},
```

### Output Files
- Normal: `{date}-{map}-round-{N}_engagements.txt` (always generated)
- Test mode: `{date}-{map}-round-{N}_lifecycle.txt` (only in test mode)

### What Gets Disabled in Test Mode
- Engagement creation and tracking
- Crossfire detection
- Escape detection
- Heatmap generation

### What Remains Active in Test Mode
- Player spawn tracking
- Position sampling every 500ms
- Death/end state detection
- Death type categorization
- Action event annotations (damage received/dealt)
- Revive event tracking
- Lifecycle log output

## Testing Plan
1. Enable test_mode in config
2. Run a live session
3. Check `_lifecycle.txt` for player journeys
4. Verify: spawn → movement samples → damage events → end state
5. Validate death types are correctly categorized

## Next Steps
- Live testing to validate lifecycle tracking
- Once core tracking is validated, re-enable advanced features one by one
- Consider adding fire/grenade action tracking (requires additional ET:Legacy hooks)
