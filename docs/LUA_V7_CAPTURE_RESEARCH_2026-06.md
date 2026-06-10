# Lua v7 Capture Research — ET:Legacy Lua API Capabilities (2026-06)

**Scope**: Research-only. What additional per-player data can `proximity/lua/proximity_tracker.lua`
(v6.02, ~4,300 lines) capture on the ET:Legacy 2.83.1 server, verified against the official Lua API
docs at <https://etlegacy-lua-docs.readthedocs.io/> (pages fetched 2026-06-10: `fields.html`,
`functions.html`, `callbacks.html`, `misc.html`).

**Server constraints (unchanged for v7):**
- Lua **5.4** — no LuaJIT idioms; `string.format("%d", x)` throws on non-integer subtypes
  (use `math.tointeger`, as already done in the SHOT_FIRED path, tracker ~line 4128).
- Deploys go to **homepath** (homepath shadows basepath); **never `lua_restart`** — always a full
  map load (c0rnp0rn8 crashes on lua_restart).
- **All deploys are owner-gated.** This document proposes NO live deploy.
- Tracker samples all players every **200ms** (`sampleAllPlayers`, line 1057) and already wraps
  every `et.gentity_get` in pcall (`safe_gentity_get`, line 354).

**Verification convention**: "VERIFIED" = the exact field/function name appears in the readthedocs
pages fetched above. "RUNTIME-PROVEN" = not fully documented but already exercised by v5/v6.02 in
production (e.g. `trap_Trace` return table). "UNVERIFIED" = not found in docs; do not build on it
without a live testmode probe first.

---

## Summary Table

| # | Candidate | API | Verified in docs | Cost class | Value (1–5) |
|---|-----------|-----|------------------|------------|-------------|
| 1 | Crosshair target / aim-on-enemy | `et.trap_Trace(start, mins, maxs, end, entNum, mask)` + `et.G_HistoricalTrace(ent, ...)` | YES (signatures; return table UNDOCUMENTED but runtime-proven `.fraction`) | per-sample (with FOV prefilter) | **5** |
| 2 | Lean state | `ps.leanf` (float, ro) | YES | per-sample, trivial | 2 |
| 3 | Skill / XP | `sess.skill` (int_array, rw), `sess.medals` (int_array, rw), `ps.persistant` (int_array, rw), `et_UpgradeSkill` / `et_SetPlayerSkill` callbacks, `SK_*` constants 0–6 | YES (PERS_* indices UNVERIFIED) | per-event + per-spawn snapshot | 4 |
| 4 | Spawn point selection | `sess.spawnObjectiveIndex` (int, rw), `pers.lastSpawnTime` (int, ro); `setspawnpt` via `et_ClientCommand` | YES (fields); command capture path plausible, arg format UNVERIFIED | per-event | 4 |
| 5 | Ammo / weapon state | `ps.ammo`, `ps.ammoclip` (int_array, rw), `ps.weaponstate` (int, ro), `ps.classWeaponTime` (int, rw) | YES (`ps.curWeapHeat` NOT exposed) | per-sample | 3 |
| 6 | Velocity / airborne | `ps.velocity` (vec3, rw — already sampled), `s.groundEntityNum` (int, ro) | YES (note: `s.` prefix, not `ps.`) | per-sample, trivial | 3 |
| 7 | Powerups / carry flags | `ps.powerups` (int_array, rw) | YES — **already captured** (v6 carrier tracking, indices 5/6 runtime-proven) | already paid | done |
| 8 | Fireteam membership | No fields/functions exposed; only `pers.autofireteam*EndTime` timers + `et_ClientCommand` interception | **NO** (membership not readable) | per-event (commands only) | 2 |
| 9 | Chat / vsay / command-map pings | `et_ClientCommand(clientNum, command)` + `et.trap_Argc()` / `et.trap_Argv(index)` / `et.ConcatArgs(index)` | YES | per-event, low | 4 |
| 10 | Medic/ammo pack gives | Throws via `et_WeaponFire(clientNum, weapon)`; **no pickup/handoff callback exists** — receive side is heuristic only | PARTIAL | per-event + heuristic in sample loop | 3 |
| 11 | Server-side per-weapon stats & session counters | `sess.aWeaponStats` (weaponstat, ro), `sess.damage_given/received`, `sess.kills/deaths/gibs/self_kills/team_kills`, `sess.time_axis/time_allies`, `ps.eFlags` | YES (aWeaponStats return shape UNVERIFIED) | per-round snapshot | 4 |

---

## 1. Crosshair Target / Aim-on-Enemy

**Goal**: per-sample (or per-shot) flag: "was the player's crosshair on an enemy (or within N° of
one), and which one?" — the missing link between SHOT_FIRED aim data and engagement outcomes.

**Exact API (VERIFIED):**
- `et.trap_Trace( start, mins, maxs, end, entNum, mask )` — documented in `functions.html` with
  parameters: start position, bbox mins/maxs, end position, entity number to ignore, content mask.
  **Return value is NOT documented** on the page — however the tracker has used it in production
  since v5 (`hasLineOfSight`, lines 808–850) and handles a **table with `.fraction`**
  (runtime-proven; the code also defensively handles a numeric return). A v7 crosshair trace must
  additionally read `entityNum`/`endpos` from the result table — **UNVERIFIED in docs; needs a
  testmode probe** (dump `for k,v in pairs(result)` once on a live trace before relying on it).
- `et.G_HistoricalTrace( ent, start, mins, maxs, end, entNum, mask )` — documented: "Runs a trace
  with players in historical positions." This is the antilag-aware variant — the correct choice if
  we want crosshair checks to match what the server's hit detection would see. Same return-shape
  caveat.

**Approach** (cost-controlled, two stages):
1. **Pure-Lua FOV prefilter** (no engine call): for each tracked player, compute forward vector
   from `ps.viewangles` (yaw/pitch → unit vector, ~6 math ops) and dot-product against the
   normalized direction to each living enemy (positions already cached by the sample loop). Only
   enemies within a small cone (e.g. cos > 0.996 ≈ 5°) and within ~3000u proceed to stage 2.
   Cost: 6v6 = 6×6 = 36 dot products per sample tick — negligible.
2. **Confirm with one trace** from eye position along viewangles (or to the candidate's eye
   position, which avoids needing `endpos`/`entityNum` from the result): `fraction >= 0.98` ⇒
   crosshair-on-enemy. Worst case 12 traces per 200ms tick = 60 traces/s — the same order as the
   existing v5 crossfire-opportunity LOS traces, which are proven affordable on this server.

**If trap_Trace had not existed**: pure-Lua FOV math alone (stage 1 only) gives "aim-at" without
occlusion — acceptable fallback, zero engine cost, but counts aiming-through-walls. Not needed:
trap_Trace exists and is already in use.

**Hook point**: end of `sampleAllPlayers()` (positions/teams already gathered that tick), plus
optionally inside `et_WeaponFire` for a per-shot `on_target` bit on SHOT_FIRED rows.

**Output volume**: 2 extra fields per PLAYER_TRACKS path point (`aim_target` slot or -1,
`aim_dot`), or a separate compact AIM_ON_TARGET section with state-change events only
(enter/leave crosshair) — state-change encoding is ~10–50 events/player/round vs ~1,500 path
points, strongly preferred.

**Dump-format impact**: new `# AIM_LOCK` section (event rows: time, guid, target_guid, duration_ms,
ended_by kill/lost/death) — additive, parser ignores unknown sections today.

**Parser/DB impact**: new table `proximity_aim_lock` (round_id, player_guid, target_guid, start_ms,
duration_ms, outcome). Joins naturally with engagements and SHOT_FIRED for true-aim v2.

**Risks**: trace return-shape on this build (probe first); cost spike with many players (cap stage-2
traces per tick, e.g. 16, and skip when >16 players); viewangles binding is already
runtime-validated (Phase 5.3) so the input side is safe.

**Value: 5/5** — directly serves "every player fully tracked vs opponents" and upgrades the entire
aim/engagement story (time-to-target, tracking time before kill, who was being watched).

## 2. Lean State

**Exact API (VERIFIED)**: `ps.leanf` — float, **read-only** (fields.html). Lean amount; 0 = not
leaning, signed value = lean left/right (sign convention UNVERIFIED in docs — confirm in testmode).

**Hook point**: `sampleAllPlayers()` next to the existing `ps.pm_flags` stance read (line 816).

**Output volume**: 1 small float per path point, or fold into the existing stance byte (e.g. stance
codes 0/1/2 gain +4/+8 lean bits) — zero new rows.

**Parser/DB impact**: extend stance decoding; one new smallint column or reuse stance column
encoding in `proximity_position` ingestion.

**Risks**: none meaningful; ro field, pcall-wrapped.

**Value: 2/5** — niche (corner-peeking behavior, covert-ops play style); nearly free, so worth
taking opportunistically.

## 3. Skill / XP / Medals

**Exact API (VERIFIED):**
- `sess.skill` — int_array, rw. Per-skill points. Skill indices documented in `misc.html` with
  values: `SK_BATTLE_SENSE=0`, `SK_EXPLOSIVES_AND_CONSTRUCTION=1`, `SK_FIRST_AID=2`,
  `SK_SIGNALS=3`, `SK_LIGHT_WEAPONS=4`, `SK_HEAVY_WEAPONS=5`,
  `SK_MILITARY_INTELLIGENCE_AND_SCOPED_WEAPONS=6`.
- `sess.medals` — int_array, rw.
- `ps.persistant` — int_array, rw. **PERS_* index constants are NOT documented** on the fetched
  pages (PERS_SCORE=0 is engine lore — UNVERIFIED; probe before use).
- Callbacks (VERIFIED, callbacks.html): `et_UpgradeSkill(clientNum, skill)` — "Called when a client
  gets a skill upgrade" (return -1 overrides); `et_SetPlayerSkill(clientNum, skill)` — "Called when
  a client skill is set" (return -1 overrides).
- Write-side functions also exist (`et.G_AddSkillPoints`, `et.G_XP_Set`, `et.G_ResetXP`) — not
  needed; read-only capture for v7.

**Hook point**: snapshot `sess.skill[0..6]` per player at `et_ClientSpawn` (cheap, low frequency)
plus event rows from `et_UpgradeSkill` (new callback function, additive — the tracker does not
define it today). Note: on this server XP may reset per map/campaign — XP *deltas within a round*
are the meaningful signal, not absolutes.

**Output volume**: ~7 ints per player per round (snapshot) + a handful of upgrade events.

**Dump-format impact**: new `# SKILL_SNAPSHOT` section (guid, sk0..sk6, medals_total) + optional
`# SKILL_UPGRADE` event rows (time, guid, skill, new_level UNVERIFIED — level not passed; re-read
`sess.skill` in the callback).

**Parser/DB impact**: new narrow table `proximity_skill_snapshot` or columns on existing per-round
player rows. Could feed ET Rating v2's class-meta work (in-game skill mix per player).

**Risks**: low. Only gotcha is int_array indexing convention (0-based third arg to `gentity_get`,
matching the existing `ps.stats`/`ps.powerups` usage).

**Value: 4/5** — server-computed skill mix correlates class behavior with our own metrics.

## 4. Spawn Point Selection

**Exact API:**
- `sess.spawnObjectiveIndex` — int, rw — **VERIFIED** (fields.html). Which major spawn point the
  player has selected (0 = auto/default; exact index semantics per map UNVERIFIED — map their
  values in testmode against known spawns).
- `pers.lastSpawnTime` — int, ro — **VERIFIED** (fields.html). Bonus find: server-truth spawn time,
  can cross-check the tracker's own spawn-wave inference.
- `sess.userSpawnPointValue` — **NOT FOUND in docs** (UNVERIFIED; do not use).
- Client command `setspawnpt` — `misc.html` documents `setspawnpt` as a server→client command
  ("Others (… setspawnpt …)"); the *client→server* `setspawnpt <n>` command arriving via
  `et_ClientCommand` is engine lore, plausible but **UNVERIFIED** — capture defensively if seen.

**Hook point**: read `sess.spawnObjectiveIndex` in `et_ClientSpawn` (already implemented at line
3946) — one extra `safe_gentity_get` per spawn. Optionally intercept-and-passthrough `setspawnpt`
in a new `et_ClientCommand` (see §9) to capture *when* the player changed selection (pre-death
intent), not just what they spawned with.

**Output volume**: 1 int per spawn event (~10–30/player/round).

**Dump-format impact**: extra field on the existing spawn/track-start rows (PLAYER_TRACKS metadata)
— no new section needed.

**Parser/DB impact**: one new column on the spawn-timing/track ingestion (e.g.
`spawn_objective_index INT` on `proximity_spawn_timing` or track table).

**Risks**: index→named-spawn mapping is per-map (needs the same kind of per-map config the
objective-coords gate already established); value 0 ambiguity (auto vs first spawn).

**Value: 4/5** — spawn selection is a core competitive-ET decision (back-spawning, objective
pushes); combines directly with existing spawn-wave timing and team-push detection.

## 5. Ammo / Weapon State

**Exact API (VERIFIED, fields.html):**
- `ps.ammo` — int_array, rw (reserve ammo, indexed by weapon/ammo index).
- `ps.ammoclip` — int_array, rw (loaded clip, indexed by weapon).
- `ps.weaponstate` — int, ro (raising/lowering/firing/reloading state machine; WEAPON_* enum values
  UNVERIFIED in docs).
- `ps.classWeaponTime` — int, rw (class special charge bar — panzer/airstrike/medpack charge).
- `ps.curWeapHeat` — **NOT FOUND in docs** (not exposed; mark unavailable).

Array indices = weapon numbers; WP_* values are not on the docs pages, but the tracker already
maintains a MOD→WP mapping (lines 415–434, e.g. WP_MP40=3, WP_THOMPSON=8, WP_MEDIC_SYRINGE=11) —
treat that table as the runtime-proven reference.

**Hook point**: `sampleAllPlayers()` — read `ps.ammoclip[current_weapon]` + `ps.weaponstate` next
to the existing `ps.weapon` read (line 983/1003). `classWeaponTime` only meaningful for charge
classes; sample at lower cadence (every 5th tick) if taken.

**Output volume**: +2 small ints per path point if always-on — this is the heaviest candidate
volume-wise. Better: event-encode "reload started" (weaponstate transition) and "clip empty at
engagement start" rather than raw per-sample values.

**Dump-format impact**: either +2 fields on PLAYER_TRACKS points (format-version bump) or a small
`# WEAPON_STATE_EVENTS` section (preferred).

**Parser/DB impact**: event table `proximity_weapon_state_event` (time, guid, event_type, weapon,
clip_remaining) — enables "died while reloading", "engaged with 3 bullets left", "panzer charge
wasted".

**Risks**: per-weapon ammo index mapping has sharp edges (akimbo/alt-fire weapons share ammo) —
restrict v7 to *current weapon clip* + weaponstate to stay safe.

**Value: 3/5** — "died reloading / forced reload mid-fight" is a genuinely tellable story stat.

## 6. Velocity / Airborne (Trickjump & Route Detection)

**Exact API (VERIFIED):**
- `ps.velocity` — vec3, rw — already read every sample for speed (line 857). v7 change: keep the
  **z component** separately instead of only the 2D speed scalar.
- `s.groundEntityNum` — int, ro — **VERIFIED, note the `s.` prefix** (entityState, not playerState;
  `ps.groundEntityNum` is NOT in the fields list). Airborne when it equals ENTITYNUM_NONE — the
  constant's value (1023 in engine source) is **UNVERIFIED in docs**; probe once in testmode
  (log the value while a player stands on ground vs jumps).

**Hook point**: `sampleAllPlayers()`, alongside the existing velocity read — one extra
`safe_gentity_get(clientnum, "s.groundEntityNum")` per player per tick.

**Output volume**: 1 airborne bit (+ optionally vz rounded) per path point — fold the bit into the
existing stance/sprint flags byte to avoid format growth.

**Parser/DB impact**: extend stance/flags decoding; enables airtime %, jump-spam detection,
trickjump route segments (sustained airborne + high speed), gammajump detection when combined with
SHOT_FIRED grenade timing.

**Risks**: none meaningful (ro field, single int).

**Value: 3/5** — cheap, and movement skill is a visible part of "every player fully tracked".

## 7. Powerups / Carry Flags — ALREADY CAPTURED

`ps.powerups` — int_array, rw — VERIFIED in fields.html, and the tracker already reads indices 5/6
for objective-carrier detection (lines 2258–2259, v6 carrier events; PW_REDFLAG/PW_BLUEFLAG indices
are runtime-proven on this server even though PW_* constants are not on the docs pages).

**v7 opportunity (small)**: sample additional indices for invulnerability-after-spawn
(spawn-protection window — improves kill-outcome fairness scoring) and any map-specific powerups.
Index meanings beyond 5/6 are UNVERIFIED — probe by dumping the full array once per spawn in
testmode. Value 1–2/5, near-zero cost.

## 8. Fireteam Membership — NOT EXPOSED (mostly)

**Findings:**
- Fields: only `pers.autofireteamEndTime`, `pers.autofireteamCreateEndTime`,
  `pers.autofireteamJoinEndTime` (all int, rw) — auto-fireteam UI timers, **not membership**.
- Functions: **no fireteam functions documented** in functions.html.
- `misc.html` documents fireteam *server commands* (application/proposition/invitation) — these are
  server→client UI messages, not a read API.
- Engine stores membership in a configstring (CS_FIRETEAMS in source) — readable in principle via
  `et.trap_GetConfigstring(index)` (function VERIFIED), but the index and encoding are
  **UNVERIFIED in docs**.

**Practical capture path**: intercept-and-passthrough `fireteam` client commands in
`et_ClientCommand` (create/join/leave/invite/propose — arg layout UNVERIFIED, log raw args in
testmode first). This yields membership *changes*, from which membership state can be reconstructed
— but misses pre-existing state on lua load.

**Value: 2/5, cost low but verification burden high** — and on a 6v6 stopwatch server the fireteam
is usually "everyone". **Recommend deferring** unless the configstring probe turns out trivial.

## 9. Chat / Voice Commands / Command-Map Pings

**Exact API (VERIFIED, callbacks.html + functions.html):**
- `intercepted = et_ClientCommand(clientNum, command)` — "Called when a command is received from a
  client." Return 1 to intercept, **0 to pass through** (v7 must always return 0).
- Args: `et.trap_Argc()` ("number of command line arguments in the server command"),
  `et.trap_Argv(index)` ("contents of the command line argument"), `et.ConcatArgs(index)` ("all
  arguments … concatenated into a single string").

The tracker defines **no `et_ClientCommand` today** (grep of `^function et_` confirms) — this is a
brand-new, purely additive callback.

**What arrives**: every client command — `say`, `say_team`, `say_buddy`, `vsay`/`vsay_team`
(voice commands like "Medic!", "Great shot!"), class/team changes, `setspawnpt`, fireteam commands.
The exact arg layout per command (e.g. vsay variant id + text) is **UNVERIFIED in docs** — testmode
should log `Argc` + all `Argv` for a session to build the dispatch table empirically.

**Hook point**: new `function et_ClientCommand(clientNum, command)` with a whitelist dispatch
(`vsay`, `vsay_team`, `say_team`, `setspawnpt`, `fireteam`); ignore everything else and return 0
immediately. Cost: string compare per client command — negligible (per-event, human-rate).

**Output volume**: tens of events per player per round.

**Dump-format impact**: new `# COMM_EVENTS` section (time, guid, type, arg1, sanitized text).
**Privacy note**: full `say` chat is personal — recommend capturing only *voice-command IDs* and
team-comm *counts*, not free-text chat bodies (owner call).

**Parser/DB impact**: `proximity_comm_event` table; correlates "Medic!" calls with revive response
time, comm frequency with cohesion scores — strong teamplay-narrative material.

**Risks**: must never return 1 (would eat the command); pcall the whole handler so a malformed
command can't break gameplay commands; Lua 5.4 string handling of ET color codes already solved
elsewhere in repo.

**Value: 4/5** — communication is the one teamplay axis the system currently cannot see at all.

## 10. Medic / Ammo Pack Gives

**Findings:**
- **No pack-pickup/handoff callback exists** in the documented API (callbacks.html lists no item
  pickup events; EV_* event constants exist in misc.html but Lua cannot hook entity events).
- **Throw side is capturable (VERIFIED)**: `et_WeaponFire(clientNum, weapon)` — "Called whenever a
  weapon is shot" — fires for medkit/ammopack tosses (they are weapon fires). The tracker already
  implements `et_WeaponFire` (line 4088) and counts shots per weapon, so **pack throws are already
  being counted today** under their WP numbers; v7 just needs to record them as positioned events
  (origin + nearest needy teammate) instead of bare counters. WP_MEDKIT/WP_AMMO weapon numbers are
  not on the docs pages — UNVERIFIED; read empirically from existing weapon_fire data (distinct
  weapon ids logged for medics/fieldops).
- **Receive side is heuristic only**: in `sampleAllPlayers`, a teammate whose health rises while no
  revive occurred (revives already tracked via `et_ClientSpawn revived=1`) near a recent medkit
  throw ⇒ attributed pickup. Same for ammo via `ps.ammo` delta (§5). Window+radius tunable;
  mis-attribution possible with two medics — mark events with a confidence flag.
- Syringe revives: already fully covered (MOD_SYRINGE=24 in the tracker's MOD map + `et_ClientSpawn
  revived=1`).

**Output volume**: ~5–40 throw events + matched-pickup events per round.

**Dump-format impact**: new `# PACK_EVENTS` section (time, giver_guid, type med/ammo, ox, oy, oz,
receiver_guid or -, confidence).

**Parser/DB impact**: `proximity_pack_event` table → "support given under fire", medic logistics
score, fieldops ammo discipline.

**Risks**: attribution accuracy (heuristic); weapon-id verification needed first.

**Value: 3/5** — support play is invisible in kill-based stats; fits the "invisible value"
philosophy directly, but the heuristic receive side caps reliability.

## 11. Other Valuable Finds (docs sweep)

- **`sess.aWeaponStats`** — type `weaponstat`, ro (fields.html) — the server's own per-weapon
  hits/shots/kills table (what `/weaponstats` shows). Return shape from `gentity_get` is
  **UNVERIFIED** (special type) — if readable, a per-round snapshot gives a free server-truth
  cross-check of the tracker's `weapon_fire` counters and the endstats parser. Probe in testmode.
  Value 4/5 as a validation source, zero ongoing cost (once per round end).
- **Session counters (all VERIFIED, fields.html)**: `sess.damage_given` /
  `sess.damage_received` / `sess.team_damage_given` (rw), `sess.kills`/`sess.deaths`/`sess.gibs`/
  `sess.self_kills`/`sess.team_kills` (rw), `sess.time_axis`/`sess.time_allies` (ro) — cheap
  end-of-round snapshot for drift detection vs c0rnp0rn8 endstats.
- **`pers.lastSpawnTime`** (int, ro) — server-truth spawn timestamps; validates the spawn-wave
  model that drives KIS reinf timing (see §4).
- **`ps.eFlags`** (int, ro) — entity flags (EF_* values UNVERIFIED in docs); potentially exposes
  zooming/mounted/dead states; probe-only candidate.
- **`et_Print(text)` carries an explicit docs warning** — "DO NOT TRUST STRINGS OBTAINED IN THIS
  WAY!" — reinforces that v7 should not add et_Print scraping.
- **`et_FixedMGFire` / `et_MountedMGFire` / `et_AAGunFire`** (VERIFIED callbacks) — MG-nest fire is
  currently invisible to SHOT_FIRED (only `et_WeaponFire` is hooked); tiny additive win for aim
  completeness on maps with emplaced guns.
- **Not exposed / confirmed absent**: `ps.aimSpreadScale`, `ps.serverCursorHint`,
  `ps.curWeapHeat`, `ps.grenadeTimeLeft`, `ps.weaponTime`, `sess.userSpawnPointValue`,
  `ps.groundEntityNum` (use `s.groundEntityNum`). No fireteam membership read API.

---

## Recommended v7 Scope (by value/cost)

1. **Crosshair-on-enemy (AIM_LOCK)** — §1. Highest value; both APIs verified to exist; FOV
   prefilter keeps cost at the level of already-proven v5 LOS tracing. Prereq: one testmode probe
   of the trap_Trace result-table keys.
2. **Comm events via `et_ClientCommand`** — §9. Verified callback + arg functions; brand-new data
   axis (vsay/team-comm) at per-event cost. Prereq: testmode arg-layout logging; privacy decision
   on free-text chat (recommend: voice-command IDs only).
3. **Spawn selection + server spawn truth** — §4. `sess.spawnObjectiveIndex` + `pers.lastSpawnTime`
   verified; two reads per spawn event; directly strengthens the existing spawn-timing/KIS pillar.
4. **Skill snapshot + upgrade events** — §3. Verified fields/callbacks/constants; trivially cheap;
   feeds ET Rating class-meta.
5. **Airborne bit + lean bits folded into the flags byte** — §6 + §2. Near-zero cost, no new
   sections, movement-skill visibility.

**Validation-only bonus** (no new product surface): end-of-round snapshot of `sess.aWeaponStats` +
`sess.damage_given/received` as a server-truth cross-check (§11), gated behind a successful
testmode probe of the `weaponstat` return shape.

**Defer**: fireteam membership (§8 — not exposed, low value on this server), per-sample ammo
columns (§5 — take only the event-encoded reload/clip-empty variant if at all), pack-receive
attribution (§10 — throw events are fine, receive heuristic needs design time).

**Deployment**: NO live deploy in this effort. All probes above run under the existing testmode
gate on the owner's schedule; any v7 rollout follows the established path — repo change → owner
review → homepath deploy → **full map load (never `lua_restart`)**.
