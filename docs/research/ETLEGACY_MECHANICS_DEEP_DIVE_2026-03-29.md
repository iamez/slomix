# ET:Legacy Engine Mechanics Deep Dive

**Source**: [etlegacy/etlegacy](https://github.com/etlegacy/etlegacy) (master branch)
**Date**: 2026-03-29
**Purpose**: Technical reference for movement, damage, hitboxes, spread, recoil, antilag, and screen shake mechanics.

All values extracted directly from the C source code. File references included per section.

---

## Table of Contents

1. [Movement Speed](#1-movement-speed)
2. [Strafing / ADAD and Hitboxes](#2-strafing--adad-and-hitboxes)
3. [Screen Shake / Damage Feedback](#3-screen-shake--damage-feedback)
4. [Damage Falloff Over Distance](#4-damage-falloff-over-distance)
5. [Hitbox Sizes by Stance](#5-hitbox-sizes-by-stance)
6. [Aimspread / Weapon Spread](#6-aimspread--weapon-spread)
7. [Antilag / Lag Compensation](#7-antilag--lag-compensation)
8. [Recoil Mechanics](#8-recoil-mechanics)
9. [Complete Weapon Data Table](#9-complete-weapon-data-table)

---

## 1. Movement Speed

**Source**: `src/game/bg_pmove.c`, `src/game/g_client.c`, `src/game/g_cvars.c`, `src/game/g_active.c`

### Base Speed

```
g_speed = 320 (default cvar)
```

All classes share the same base speed. There are no class-specific speed modifiers in the source code. Speed differences come only from weapon weight.

### Speed Scale Multipliers (set in ClientSpawn)

| State | Scale | Effective Speed (units/sec) |
|-------|-------|-----------------------------|
| **Sprint** | `sprintSpeedScale = 1.1` | 320 * 1.1 = **352** |
| **Run (normal)** | `runSpeedScale = 0.8` | 320 * 0.8 = **256** |
| **Crouch** | `crouchSpeedScale = 0.25` | 320 * 0.25 = **80** |
| **Prone** | `pm_proneSpeedScale = 0.21` | 320 * 0.21 = **67.2** |

Prone speed is further capped to **40 units/sec** during weapon reloading or alt-weapon switching.

### Heavy Weapon Penalties

| Condition | Multiplier | Effective Run Speed |
|-----------|------------|---------------------|
| Heavy weapon equipped (default) | `0.5` | 160 |
| Heavy weapon + Soldier Dexterity skill | `0.75` | 240 |
| Flamethrower (with dexterity or firing) | `0.7` | 224 |

### Sprint System

- Sprint pool: `SPRINTTIME = 20000ms` (20 seconds of sprint)
- Sprint activates only when `sprintTime > 50ms` remaining
- Sprint requires `BUTTON_SPRINT` input

### Physics Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `pm_stopspeed` | 100 | Below this speed, friction decelerates more aggressively |
| `pm_accelerate` | 10 | Ground acceleration rate |
| `pm_airaccelerate` | 1 | Air acceleration rate (10x slower than ground) |
| `pm_friction` | 6 | Ground friction coefficient |
| `pm_waterfriction` | 1 | Water friction |
| `pm_ladderfriction` | 14 | Ladder friction (very sticky) |
| `pm_waterSwimScale` | 0.5 | Water swim speed cap |
| `pm_slagSwimScale` | 0.3 | Slag swim speed cap |
| `JUMP_VELOCITY` | 270 | Upward velocity on jump |
| `PM_JUMP_DELAY` | 850ms | Minimum delay between jumps |
| `DEFAULT_GRAVITY` | 800 | Gravity (units/sec^2) |
| `STEPSIZE` | 18 | Maximum step-up height |
| `MIN_WALK_NORMAL` | 0.7 | Steepest walkable slope normal |

### Movement Formulas

**Friction** (`PM_Friction`):
```
control = MAX(speed, pm_stopspeed)
drop = control * pm_friction * frametime
newspeed = MAX(0, speed - drop)
velocity = velocity * (newspeed / speed)
```

**Acceleration** (`PM_Accelerate`, Quake 2 style):
```
currentspeed = DotProduct(velocity, wishdir)
addspeed = wishspeed - currentspeed
if (addspeed <= 0) return
accelspeed = accel * frametime * wishspeed
if (accelspeed > addspeed) accelspeed = addspeed
velocity += accelspeed * wishdir
```

**Strafe Jumping**: No speed cap during air movement. Air acceleration is only 1 (vs ground 10), but the Q2-style acceleration formula allows velocity to exceed base speed when the wish direction diverges from current velocity. This is the classic strafe-jumping mechanic inherited from Quake 3 / RTCW.

---

## 2. Strafing / ADAD and Hitboxes

**Source**: `src/game/bg_pmove.c`, `src/game/g_antilag.c`

### No ADAD Penalty

There is **no ADAD (strafe spam) penalty** in the ET:Legacy source code. Both forward and strafe inputs are treated identically when computing the wish velocity vector:

```c
for (i = 0; i < 3; i++) {
    wishvel[i] = pml.forward[i] * fmove + pml.right[i] * smove;
}
```

Forward movement (`fmove`) and strafe movement (`smove`) are simply combined into a normalized direction vector. There is no penalty, slowdown, or spread increase for changing direction rapidly.

### How ADAD Affects Hitboxes

The hitbox moves with the player model in real-time. ADAD strafing makes you harder to hit because:

1. **Bounding box tracks position**: The collision box (`playerMins`/`playerMaxs`) moves with `origin`
2. **Head hitbox is bone-tracked**: When skeletal hitboxes are available, the head box follows the `tag_head` bone, which sways during direction changes
3. **Antilag interpolation**: At high ping, the server linearly interpolates between stored position snapshots. Rapid direction changes create larger interpolation errors, making the effective hitbox less accurate for the shooter

### Antiwarp System

**Source**: `src/game/et-antiwarp.c`

The antiwarp system prevents players from exploiting lag spikes to move faster:

- Commands are queued in a circular buffer (`LAG_MAX_COMMANDS`)
- Movement per server frame is capped at `LAG_MAX_DELTA`
- Stale commands (age > `LAG_MAX_DROP_THRESHOLD`) are dropped
- Speed is calculated as: `speed = max(|fwd|, |right|, |up|) / 127.0`
- Accumulated delta: `delta = speed * timeDelta / LAG_DECAY`
- Excess movement defers to next frame (max 50ms per tick)
- Disabled for spectators, bots, and players connected < 5 seconds

---

## 3. Screen Shake / Damage Feedback

**Source**: `src/cgame/cg_playerstate.c`, `src/cgame/cg_view.c`, `src/cgame/cg_local.h`

### Damage-to-View-Kick Formula (`CG_DamageFeedback`)

**Step 1 - Calculate kick intensity:**
```c
scale = (health < 40) ? 1.0 : 40.0 / health;
kick = Com_Clamp(5, 10, damage * scale);
```
At full health (100): `scale = 0.4`, so 18 damage = kick of 7.2.
At low health (30): `scale = 1.0`, so 18 damage = kick of 10 (capped).

**Kick range is always 5-10 degrees**, regardless of damage amount.

**Step 2 - Apply direction:**

For centered damage (explosions directly on player):
```
v_dmg_roll  = 0
v_dmg_pitch = -kick    (pushes view down)
```

For directional damage:
```
front = DotProduct(damage_dir, viewaxis[0])   // forward component
left  = DotProduct(damage_dir, viewaxis[1])   // left component

v_dmg_roll  = kick * left     // roll based on lateral hit direction
v_dmg_pitch = -kick * front   // pitch based on front/back hit direction
```

**Step 3 - Duration:**
```
damageDuration = kick * 50 * (1 + 2 * (centered ? 1 : 0))
```
- Directional hit: 250-500ms duration
- Centered hit (explosion): 750-1500ms duration

### View Application Timing

**Constants:**
```
DAMAGE_DEFLECT_TIME = 100ms   (ramp up phase)
DAMAGE_RETURN_TIME  = 400ms   (decay phase)
```

**Phase 1** (0-100ms): Linear ramp from 0 to full kick
```
ratio = elapsed / 100
angles[PITCH] += ratio * v_dmg_pitch
angles[ROLL]  += ratio * v_dmg_roll
```

**Phase 2** (100-500ms): Linear decay from full kick to 0
```
ratio = 1.0 - (elapsed - 100) / 400
angles[PITCH] += ratio * v_dmg_pitch
angles[ROLL]  += ratio * v_dmg_roll
```

### Practical Impact

- An SMG bullet (18 dmg) at full health: **kick = 7.2 degrees**, lasts ~360ms
- A headshot (50 dmg) at full health: **kick = 10 degrees** (capped), lasts ~500ms
- A grenade (250 splash) at any health: **kick = 10 degrees**, lasts ~1500ms (centered)
- Below 40 HP, every hit produces maximum kick (10 degrees)

---

## 4. Damage Falloff Over Distance

**Source**: `src/game/g_combat.c`, `src/game/g_weapon.c`

### Activation

Damage falloff only applies to weapons with the `WEAPON_ATTRIBUT_FALL_OFF` flag. This includes SMGs (MP40, Thompson, Sten, MP34, FG42) and pistols. It does NOT apply to rifles (Garand, K43, KAR98) or scoped weapons.

### Falloff Formula (`G_DamageFalloff`)

```c
scale = (dist - 1500.0) / (2500.0 - 1500.0);
scale *= coefficient;
scale = 1.0 - scale;
result = Com_Clamp(1.0 - coefficient, 1.0, scale);
```

| Distance | Body/Legs (coeff=0.5) | Headshot (coeff=0.8) |
|----------|----------------------|---------------------|
| 0-1500 units | **100% damage** | **100% damage** |
| 1500 units | 100% | 100% |
| 2000 units | 75% | 60% |
| 2500+ units | **50% damage** (floor) | **20% damage** (floor) |

### Practical Examples (MP40, 18 base damage)

| Distance | Body Hit | Headshot (2x, 0.8 helmet) |
|----------|----------|---------------------------|
| Close (< 1500u) | 18 | 28 |
| Mid (2000u) | 13 | 17 |
| Long (2500u+) | 9 | 6 |

### Headshot Damage Formula

```c
take = MAX(50, take * 2);           // double damage, minimum 50
if (!(weapon is scoped rifle))
    take *= 0.8;                     // helmet reduces non-sniper headshots by 20%
```

Scoped rifles bypass the 0.8 helmet penalty, dealing full 2x headshot damage.

### Explosion Radius Damage

```
points = damage * (1.0 - dist / radius)
```

Linear falloff from center to edge of radius.

---

## 5. Hitbox Sizes by Stance

**Source**: `src/game/g_client.c`, `src/game/bg_public.h`, `src/game/bg_misc.c`, `src/game/g_combat.c`

### Main Collision Bounding Box

| State | Mins (x,y,z) | Maxs (x,y,z) | Total Height |
|-------|-------------|-------------|--------------|
| **Standing** | (-18, -18, -24) | (18, 18, 48) | **72 units** |
| **Crouching** | (-18, -18, -24) | (18, 18, 24) | **48 units** |
| **Prone** | (-18, -18, -24) | (18, 18, -8) | **16 units** |
| **Dead** | (-18, -18, -24) | (18, 18, -16) | **8 units** |

Note: Crouching maxs Z = CROUCH_BODYHEIGHT (24), Prone maxs Z = PRONE_BODYHEIGHT (-8).

**Width is always 36x36 units** regardless of stance.

### View Heights (camera/eye position, Z offset from origin)

| State | View Height |
|-------|-------------|
| Standing | 40 |
| Crouching | 16 |
| Prone | -8 |
| Dead | -16 |

### Head Hitbox (for headshot detection)

**Default** (`g_realHead` disabled):
- Mins: (-6, -6, -2)
- Maxs: (6, 6, 10)
- Size: **12 x 12 x 12 units**

**Realistic Hitboxes** (`g_realHead` enabled):
- Mins: (-6, -6, -6)
- Maxs: (6, 6, 6)
- Size: **12 x 12 x 12 units** (centered cube)

Head position offset from player origin:
- **Standing**: viewheight (40) + 18 up, 5 forward, 5 right
- **Crouching**: crouchViewHeight (16) - 12 + offset = ~4 units above origin + 18 up
- **Prone**: viewheight (-8) - 60 + offset, 24 units forward
- Uses `tag_head` bone position when skeletal model available

### Prone Leg Hitbox (only exists in prone/dead)

- Mins: (-13.5, -13.5, -24)
- Maxs: (13.5, 13.5, -14.4)
- Size: **27 x 27 x 9.6 units**
- Positioned 32 units behind player in prone direction

### Prone Head Hitbox

- Mins: (-6, -6, -12)
- Maxs: (6, 6, 0)
- Size: **12 x 12 x 12 units**

### Arm Shot Detection

Arm shots use **geometric angle calculation**, not a traced hitbox:
```c
dot = DotProduct(hit_direction, player_facing)
isArmShot = (dot > 0.4 || dot < -0.75)   // perpendicular to facing
```

### Leg Shot Detection (Standing/Crouching)

When not prone, legs are detected by height check:
```
isLegShot = (impact_height < 0.4 * entity_height)
```

### Hitbox Height Reduction Summary

| Stance | Bbox Height | Head Exposure | Height Reduction vs Standing |
|--------|-------------|---------------|------------------------------|
| Standing | 72 units | Full | -- |
| Crouching | 48 units | Lower by ~24u | **33% smaller** |
| Prone | 16 units | 24u forward | **78% smaller** |

---

## 6. Aimspread / Weapon Spread

**Source**: `src/game/bg_pmove.c`, `src/game/g_weapon.c`, `src/game/bg_misc.c`

### Aimspread Scale System

The aimspread system tracks a floating-point value `aimSpreadScaleFloat` (range 0-255) that represents how inaccurate the player's aim currently is.

### Spread Decrease (Recovery)

```
decrease = (cmdTime * AIMSPREAD_DECREASE_RATE) / wpnScale

AIMSPREAD_DECREASE_RATE = 200.0
```

**Stance modifiers on wpnScale (faster recovery when lower):**
- Default: `wpnScale = 1.0`
- Crouching or Prone: `wpnScale *= 0.5` (2x faster recovery)
- Scoped weapon + breath control skill: `wpnScale *= 0.5` (2x faster recovery, stacks)

### Spread Increase (from aim movement)

```
viewchange = (|pitch_delta| + |yaw_delta|) / cmdTime
viewchange -= AIMSPREAD_VIEWRATE_MIN / wpnScale
increase = cmdTime * viewchange * AIMSPREAD_INCREASE_RATE

AIMSPREAD_VIEWRATE_MIN  = 30.0   (degrees/sec deadzone)
AIMSPREAD_VIEWRATE_RANGE = 120.0  (degrees/sec range)
AIMSPREAD_INCREASE_RATE = 800.0
```

For scoped weapons, player velocity components are also added to viewchange.

### Per-Shot Spread Increase

Each shot adds to aimspread:
```
aimSpreadScaleFloat += aimSpreadScaleAdd   (from weapon table)
```

| Weapon | aimSpreadScaleAdd |
|--------|-------------------|
| MP40 / Thompson | 15 |
| Sten / MP34 | 15 |
| FG42 | 100 (!) |
| Mobile MG42 | 20 |
| Garand / K43 / KAR98 | 50 |
| Luger / Colt / Akimbo | 20 |
| Scoped Garand / K43 | (not applicable - no spread) |

### Final Spread Application (Bullet_Fire)

```c
float spread = weaponTable[weapon].spread;

// Apply current aimspread scale
aimSpreadScale = currentAimSpreadScale + 0.15;
aimSpreadScale = MIN(aimSpreadScale, 1.0);

// Airborne override
if (airborne) aimSpreadScale = 2.0;

// Rifles ignore aimspread
if (WEAPON_TYPE_RIFLE) aimSpreadScale = 1.0;

spread *= aimSpreadScale;
```

### Weapon Base Spread Values

| Weapon | Base Spread | spreadScale | After Skill (.65x) |
|--------|-------------|-------------|---------------------|
| MP40 | 400 | 0.6 | 260 |
| Thompson | 400 | 0.6 | 260 |
| Sten | 200 | 0.6 | 130 |
| MP34 | 200 | 0.6 | 130 |
| FG42 | 500 | 0.6 | 325 |
| Mobile MG42 | 2500 | 0.9 | -- |
| Garand / K43 / KAR98 | 250 | 0.5 | -- |
| Luger / Colt | 600 | 0.4 | 390 |
| Akimbo | 600 | 0.4 | 390 |
| Garand/K43 Scope | 700 | 10.0 | -- |
| FG42 Scope | 200 | 10.0 | -- |

The spread value is used in the bullet trajectory calculation:
```c
VectorMA(end, MAX_TRACE, forward, end);
VectorMA(end, crandom() * spread, right, end);   // horizontal random
VectorMA(end, crandom() * spread, up, end);       // vertical random
```

`crandom()` returns -1.0 to 1.0, so the bullet can deviate up to `spread` units at `MAX_TRACE` distance in any direction.

### Stance-Based Spread Modifiers (Machine Guns)

| Condition | Multiplier |
|-----------|------------|
| Mounted (bipod/set) MG42 | `spread *= 0.05` |
| Crouching or Prone (unset MG) | `spread *= 0.6` |
| Standing (unset MG) | No modifier |

### Skill-Based Spread Modifiers

| Skill | Condition | Multiplier |
|-------|-----------|------------|
| Light Weapons Handling (Level 3) | SMG/Pistol (non-scoped, non-akimbo) | `spread *= 0.65` |

### Prone Spread Delay

When `bg_proneDelay` is enabled, spread recovery is blocked for **400ms** after going prone. This prevents instant-accuracy prone shots.

---

## 7. Antilag / Lag Compensation

**Source**: `src/game/g_antilag.c`

### System: Backward Time Frame (B2TF)

The server records player positions each frame and can "rewind" all players to where they were at the shooter's perceived time.

### Algorithm

1. Server receives fire command with `serverTime` timestamp from client
2. For each other player, find two stored position markers bracketing the requested time
3. Linearly interpolate position between the two markers:
   ```
   frac = (requestedTime - marker[i].time) / (marker[j].time - marker[i].time)
   position = marker[i].origin + frac * (marker[j].origin - marker[i].origin)
   ```
4. Also interpolate bounding box `mins`/`maxs`
5. Execute the bullet trace against rewound positions
6. Restore all players to their current actual positions

### Stored Data Per Frame

Each snapshot stores:
- Position (origin, mins, maxs)
- View angles
- Entity flags (prone, dead, etc.)
- Animation frames (torso/legs with timing)
- Ground entity reference

### Time Window

- Storage: circular buffer of `MAX_CLIENT_MARKERS` entries
- Frame period: `1000 / sv_fps` (typically 50ms at 20 fps)
- **Maximum lookback: ~1 second** (20 frames at 50ms each)
- Practical compensation: 50-200ms (limited by snapshot frequency)

### Safety Checks (`G_AntilagSafe`)

Antilag skips entities that are:
- Not in use or not linked
- Spectators (not AXIS or ALLIES)
- In limbo or dead
- Mounted on a tank
- Not in `PM_NORMAL` movement type

### Special Height Adjustment

For melee weapons (syringe), the hitbox height is temporarily adjusted:
- Prone/dead targets: uses `CROUCH_BODYHEIGHT`
- Otherwise: `ClientHitboxMaxZ(client)`

### Movement Prediction

`G_PredictPmove()` forecasts next-frame position using engine physics to prevent players from "skipping" over landmines when antilag is disabled.

### Controlled By

```
g_antilag = 1 (default, enabled)
```

Disabled entirely for bot entities.

---

## 8. Recoil Mechanics

**Source**: `src/game/bg_pmove.c`, `src/game/bg_misc.c`, `src/cgame/cg_view.c`

### Weapon Recoil System (`PM_HandleRecoil`)

Recoil applies view angle modifications during sustained fire:

```c
muzzlebounce[PITCH] -= frametime * FPS_RECOIL_FACTOR * 2 *
                        weapRecoilPitch * cos(...)

FPS_RECOIL_FACTOR = 83
```

### Random Component

```
randomFactor = 0.25 * random() * (1.0 - deltaTime/duration)
```

Randomness decreases as the recoil duration progresses, making the first shot more unpredictable and sustained fire more consistent in pattern.

### Per-Weapon Recoil Values

| Weapon | Duration (ms) | Pitch [min, max] | Yaw [min, max] |
|--------|---------------|-------------------|-----------------|
| MP40 | 0 | (0, 0) | (0, 0) |
| Thompson | 0 | (0, 0) | (0, 0) |
| Sten | 0 | (0, 0) | (0, 0) |
| MP34 | 0 | (0, 0) | (0, 0) |
| FG42 | 0 | (0, 0) | (0, 0) |
| **Luger / Colt** | **100** | **(0.61, 0.31)** | **(0, 0)** |
| **Akimbo (all)** | **100** | **(0.61, 0.31)** | **(0, 0)** |
| **Mobile MG42** | **200** | **(0.75, 0.2)** | **(1.0, 0.25)** |
| **FG42 Scope** | **100** | **(0.9, 0.3)** | **(0, 0)** |
| **Garand/K43 Scope** | **300** | **(0, 0)** | **(1.0, 0.5)** |

Note: SMGs (MP40, Thompson, Sten, MP34, FG42 unscoped) have **zero recoil duration**, meaning they rely entirely on the aimspread system for accuracy degradation rather than viewmodel kick.

### Client-Side Kick Angles (`CG_KickAngles`)

Additional client-side recoil smoothing:

| Parameter | Value |
|-----------|-------|
| `centerSpeed` | {2400, 2400, 2400} per axis |
| `recoilCenterSpeed` | 200 (pitch-specific centering) |
| `recoilMaxSpeed` | 50 (maximum recoil angular velocity) |
| `maxKickAngles` | {10, 10, 10} degrees per axis |

### Mounted MG42 Special

Mounted MG42 uses `VIEWLOCK_JITTER` which applies a special vibration effect separate from the standard recoil system.

---

## 9. Complete Weapon Data Table

**Source**: `src/game/bg_misc.c` (weaponTable[])

### Bullet Weapons

| Weapon | Damage | Spread | SpreadScale | FireDelay | NextShot | AimSpreadAdd | Recoil Dur |
|--------|--------|--------|-------------|-----------|----------|--------------|------------|
| MP40 | 18 | 400 | 0.6 | 0 | 150ms | 15 | 0 |
| Thompson | 18 | 400 | 0.6 | 0 | 150ms | 15 | 0 |
| Sten | 14 | 200 | 0.6 | 0 | 150ms | 15 | 0 |
| MP34 | 14 | 200 | 0.6 | 0 | 150ms | 15 | 0 |
| FG42 | 16 | 500 | 0.6 | 0 | 100ms | 100 | 0 |
| Luger/Colt | 18 | 600 | 0.4 | 0 | 400ms | 20 | 100ms |
| Akimbo (all) | 18 | 600 | 0.4 | 0 | -- | 20 | 100ms |
| Mobile MG42 | 18 | 2500 | 0.9 | 0 | 50ms | 20 | 200ms |
| Garand | 34 | 250 | 0.5 | 0 | 400ms | 50 | 0 |
| K43 | 34 | 250 | 0.5 | 0 | 400ms | 50 | 0 |
| KAR98 | 34 | 250 | 0.5 | 0 | 400ms | 50 | 0 |
| Garand Scope | 50 | 700 | 10.0 | 0 | -- | -- | 300ms |
| K43 Scope | 50 | 700 | 10.0 | 0 | -- | -- | 300ms |
| FG42 Scope | 30 | 200 | 10.0 | 0 | -- | -- | 100ms |
| Flamethrower | 5 | -- | -- | 0 | 50ms | -- | 0 |

### Explosive Weapons

| Weapon | Damage | Splash Dmg | Splash Radius | FireDelay | NextShot | Knockback |
|--------|--------|-----------|---------------|-----------|----------|-----------|
| Panzerfaust | 400 | 400 | 300 | 750ms | 2000ms | 32000 |
| Bazooka | 400 | 400 | 300 | 750ms | -- | 32000 |
| Grenade (both) | 0 | 250 | 250 | -- | -- | -- |
| Rifle Grenade (GPG40/M7) | 0 | 250 | 250 | -- | -- | -- |
| Mortar (set) | 250 | 400 | 400 | 750ms | 1400ms | -- |
| Dynamite | 0 | 400 | 400 | 250ms | -- | -- |
| Satchel | 0 | 250 | 250 | 100ms | -- | -- |
| Landmine | 0 | 250 | 250 | 100ms | -- | -- |
| Smoke Marker | 0 | 140 | 140 | 50ms | 1000ms | -- |
| Map Mortar | 250 | 250 | 120 | 50ms | -- | -- |

### Other Stats

| Weapon | Max Heat | Cool Rate | Heat Recovery |
|--------|----------|-----------|---------------|
| Sten | 1200 | 540 | -- |
| Mobile MG42 | (uses heat) | -- | -- |
| Flamethrower | (uses heat) | -- | -- |

---

## Key Takeaways for Gameplay Analysis

### Movement
- All classes move at the same speed; only weapon weight matters
- Sprint is only 10% faster than run (352 vs 320 base)
- Crouch is very slow (25% of base), prone even slower (21%)
- No ADAD penalty exists - strafing is a pure mechanical advantage
- Strafe jumping works due to Q3 air acceleration formula (no air speed cap)

### Damage
- SMGs do 18 damage, rifles do 34, scoped rifles do 50
- Distance falloff (SMGs only): 100% at <1500u, down to 50% body / 20% headshot at >2500u
- Headshots: 2x damage, MIN 50, with 0.8 helmet penalty for non-scoped weapons
- Explosion damage: linear falloff from center to edge of radius

### Accuracy
- Crouching/prone gives 2x faster spread recovery AND 0.6x MG spread
- FG42 has extreme per-shot spread increase (100 vs 15 for other SMGs)
- Light Weapons skill (level 3) gives 0.65x spread for SMGs/pistols
- Airborne penalty: aimSpreadScale forced to 2.0 (double spread)

### Screen Shake
- Damage kick: 5-10 degree range, 100ms ramp + 400ms decay
- Low health (<40) amplifies kick to maximum every hit
- Explosions (centered): 3x longer duration than directional hits

### Hitboxes
- Crouching: 33% smaller vertical profile (48 vs 72 units)
- Prone: 78% smaller vertical profile (16 vs 72 units)
- Head is always 12x12x12 units regardless of stance
- Width never changes (36x36)

### Antilag
- ~1 second maximum compensation window
- Linear interpolation between stored position snapshots
- ADAD exploits antilag interpolation gaps at high ping differences

---

## 10. Practical Combat Guide (Derived from Source Code)

### The Core Trade-Off: Movement vs Accuracy

The engine creates a fundamental tension:
- **Moving your mouse** increases `aimSpreadScale` at 800/sec (above 30°/sec deadzone)
- **Moving your body (strafe)** has ZERO effect on `aimSpreadScale`
- Therefore: **aim with your keyboard, not your mouse**

Best players "slide" left-right and fire bursts when the crosshair passes over the target. The mouse stays nearly still.

### Burst Fire Discipline

From the spread accumulation formula (3x multiplier on `aimSpreadScaleAdd`):

| Weapon | Shots to max spread (255) | Optimal burst length |
|--------|---------------------------|----------------------|
| MP40/Thompson | 4-5 shots | **3-4 shots** |
| Sten/MP34 | 4-5 shots | **3-4 shots** |
| FG42 | **1 shot** (adds 300+) | **Single taps only** |
| Pistol | 4-5 shots | **2-3 shots** |
| Mobile MG42 | 4-5 shots | **3-4 shots** (or deploy bipod) |

Recovery time between bursts:
- Standing: ~0.77s for SMGs (200/0.6 = 333/sec recovery)
- **Crouching: ~0.38s** (recovery doubled to 667/sec)

### Intermittent Crouch During Duels

Crouching provides two simultaneous advantages:
1. **2x faster spread recovery** (`wpnScale *= 0.5`)
2. **33% smaller hitbox** (72 → 48 units height)

Pattern: burst → crouch → pause 0.3s → stand + burst → repeat

### Asymmetric Drift (Not Symmetric ADAD)

**Problem with symmetric ADAD**: If you oscillate equally left-right around the same center point, an opponent who holds their crosshair still on the center hits you every time you cross through.

**Solution**: Asymmetric drift — vary the amplitude and direction:
```
Bad:  ← → ← → ← →        (same center point, predictable)
Good: ←← → ←←← →→ ← →→→  (center point drifts, unpredictable)
```

- Mix 2 taps one direction, 3 the other — drift unpredictably
- Occasionally hold one direction longer to escape the opponent's crosshair zone
- Add forward/backward movement to change distance (affects damage falloff + apparent target size)
- Combine with intermittent crouching for 2D unpredictability

### Optimal ADAD Distance

At 320 u/s run speed and 20Hz server tick rate (50ms per frame):
- Per frame displacement: 16 units
- Player width: 36 units, head width: 12 units

| Strafe frequency | Displacement | Interpolation error | Effectiveness |
|------------------|-------------|---------------------|---------------|
| Every frame (50ms) | 16 units | ~8 units | Too small — still hittable |
| Every 2-3 frames (100-150ms) | 32-48 units | **16-24 units** | **Optimal** — exceeds head width |
| Every 10 frames (500ms) | 160 units | Large but trackable | Too slow — opponent adjusts |

**Optimal**: short, sharp taps of ~120ms per direction. Total cycle ~250ms. Displacement ~1 body width per direction.

### Screen Shake Counter-Strategy

When hit, kick is 5-10 degrees lasting 400ms. The instinct is to compensate with mouse movement, but this increases `aimSpreadScale`. Better approach:

1. Do NOT compensate shake with mouse — the 400ms passes quickly
2. Crouch immediately — 2x faster spread recovery helps after shake
3. Burst-pause-burst — wait ~0.3s after shake for crosshair to settle

### Sensitivity Considerations

Higher sensitivity makes it easier to flick to new targets, but harder to stay within the 30°/sec aimspread deadzone. The ideal sensitivity allows:
- Strafe-aiming for fine adjustments (mouse stays still)
- Flicks for 90-180° turns with wrist movement
- Micro-adjustments without exceeding the deadzone

### Distance Engagement Rules

From damage falloff data:

| Range | Best target | Why |
|-------|-------------|-----|
| Close (<1500u) | Head | Full 2x damage, no falloff |
| Mid (1500-2500u) | Head (borderline) | Head falloff 60-100%, body 75-100% |
| Long (>2500u) | **Body** | Head retains only 20% dmg vs body 50% |

At long range with SMGs, headshots deal less effective damage than body shots due to the 0.8x headshot falloff coefficient vs 0.5x body coefficient.

### Weapon Selection Guide

| Situation | Best weapon | Reason |
|-----------|-------------|--------|
| Long range duels | Sten/MP34 | Base spread 200 (half of MP40's 400) |
| Close/mid duels | MP40/Thompson | Higher damage (18 vs 14), spread manageable |
| Holding a position | Mobile MG42 (deployed) | 0.05x spread = laser accuracy |
| FG42 | **Single-tap only** | aimSpreadScaleAdd of 100 = instant max spread |

### The "Immovable Object" Formula

Combining all mechanics for maximum lethality while being hardest to hit:
1. **Strafe-aim**: move body to aim, keep mouse under 30°/sec
2. **Asymmetric drift**: never return to the same center point
3. **Burst fire**: 3-4 shots, then 0.3s pause (crouched)
4. **Intermittent crouch**: during pauses between bursts
5. **No jump shooting**: airborne = 2x spread penalty
6. **No shake compensation**: let the 400ms pass naturally
7. **Range awareness**: body shots at distance, headshots up close
8. **LW3 skill**: 35% spread reduction is massive
