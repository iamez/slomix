# W3 Map Entity Geometry Evidence

Date: 2026-07-31

Status: implementation and local real-asset validation complete; GitHub review
and CI still required.

## Purpose

This report closes the extraction part of Spider Web §9 W3. It records how the
toolchain reads spawn points, measured objective volumes, objective markers,
and collision-relevant inline brush entities from ET BSP entity/model lumps.

This is geometry infrastructure. It does not implement a trace, infer a live
door or constructible state, rank players, or approve any Layer 4 metric.
Consequently the §8 signal-weight protocol is not applicable to this PR. W4
and every later metric remain behind their own validation gates.

## Implementation

The implementation adds:

- `website/backend/map_geometry/entities.py`: typed, fail-closed extraction;
- `scripts/analyze_map_entity_geometry.py`: deterministic read-only evidence
  publisher;
- synthetic unit contracts and an opt-in real-PK3 integration test.

The extractor publishes:

| Entity family | BSP class |
|---|---|
| Allied spawn | `team_CTF_bluespawn` |
| Axis spawn | `team_CTF_redspawn` |
| Measured objective volume | `trigger_objective_info` |
| Objective marker | `team_WOLF_objective` |
| Doors | `func_door`, `func_door_rotating` |
| Movers | `script_mover`, `func_rotating`, `func_bobbing`, `func_button` |
| Conditional/static brush candidates | `func_static`, `func_leaky` |
| Construction state | `func_constructible` |
| Destruction state | `func_explosive` |

`func_invisible_user` and trigger classes are deliberately not called
collision blockers. ET:L assigns trigger contents to those entities. W4 must
define a purpose-specific trace mask rather than treating every inline model
as solid.

## Geometry Contract

An objective volume is the union of its convex BSP brushes, not its model AABB.
For every brush plane, world-space containment is:

```text
normal dot point <= world_distance
world_distance = local_distance + normal dot entity_origin
```

The sign and origin transformation were checked against ET:Legacy's
`src/qcommon/cm_load.c`, `src/qcommon/cm_trace.c`, and
`src/server/sv_game.c` at commit
`7a784b4504977caf1c44acf668f02cacd2153632`.
`trigger_objective_info` was checked through `InitTrigger` in
`src/game/g_trigger.c`.

The model AABB is retained as provenance and is named
`origin_translated_bounds`. Exact containment does not use it as an
authoritative shortcut because the BSP parser does not prove that model bounds
enclose every referenced brush. It is also not a runtime world-space AABB for
a mover that rotates or changes position. All extracted collision candidates
publish `runtime_state = "unresolved"`; W4 must apply an observed
transform/state or return `indeterminate`.

The extractor fails closed on:

- a missing, malformed, world-model, or out-of-range inline model reference;
- non-finite coordinates, bounds, or planes;
- empty/inverted model bounds;
- an objective trigger with a non-zero rotation;
- an objective inline model without brushes.

Every measured objective has `source = "measured_bsp_volume"`. The type system
also reserves `source = "legacy_guess"` for display-only legacy metadata, but
this extractor never creates such geometry. A missing or ambiguous BSP
publishes `objective_volumes: null`.

## Full Local Asset Measurement

Command:

```bash
python -m scripts.analyze_map_entity_geometry \
  --etmain-dir /home/samba/share/etmain \
  --output /tmp/map-entity-geometry-w3.json
```

Result across all 20 indexed BSP maps:

| Quantity | Count |
|---|---:|
| Team spawn points | 2,376 |
| Measured objective volumes | 158 |
| Objective markers | 96 |
| Collision-relevant brush entities | 1,058 |

Collision-relevant brush classes:

| Class | Count |
|---|---:|
| `func_explosive` | 458 |
| `script_mover` | 268 |
| `func_static` | 173 |
| `func_constructible` | 79 |
| `func_door_rotating` | 60 |
| `func_rotating` | 12 |
| `func_bobbing` | 3 |
| `func_button` | 2 |
| `func_door` | 2 |
| `func_leaky` | 1 |

All 158 objective model references resolved. They contain 142 six-plane, four
seven-plane, and 12 ten-plane convex brushes. Forty-three objective entities
have non-zero origins, so ignoring the model translation would have produced
incorrect world coordinates. All 158 measured model-box centres passed exact
brush-union containment. No current objective trigger uses a non-zero
rotation.

The content-sensitive manifest hash, which excludes the machine-specific
absolute `etmain` path, is:

```text
8503edd3ab28c93bd8e94805442ff75a0bbbaf669ff3927100b937eee028f867
```

The complete JSON evidence is intentionally written to `/tmp`; it is 4.2 MiB
and contains external game-asset-derived data, so it is not committed.

## Played-Map Boundary

The 19-map R1/R2 scope was measured independently:

| Map | Status | Spawns | Volumes | Markers | Brush entities |
|---|---|---:|---:|---:|---:|
| `adlernest` | measured | 44 | 6 | 3 | 61 |
| `braundorf_b4` | measured | 60 | 7 | 4 | 32 |
| `bremen_b3` | measured | 80 | 9 | 5 | 30 |
| `decay_sw` | measured | 118 | 10 | 5 | 74 |
| `erdenberg_t2` | measured | 97 | 4 | 5 | 39 |
| `et_brewdog` | measured | 41 | 4 | 3 | 23 |
| `etl_adlernest` | measured | 96 | 6 | 3 | 62 |
| `etl_ice` | measured | 96 | 7 | 5 | 39 |
| `etl_sp_delivery` | measured | 96 | 5 | 3 | 42 |
| `supply` | measured | 158 | 9 | 4 | 25 |
| `sw_goldrush_te` | measured | 144 | 10 | 4 | 50 |
| `sw_oasis_b3` | measured | 115 | 11 | 4 | 50 |
| `te_escape2` | measured | 47 | 6 | 3 | 42 |
| `etl_frostbite` | no geometry | null | null | null | null |
| `et_beach` | no geometry | null | null | null | null |
| `radar` | no geometry | null | null | null | null |
| `sp_delivery_te` | no geometry | null | null | null | null |
| `etl_supply` | no geometry | null | null | null | null |
| `mp_sillyctf` | no geometry | null | null | null | null |

The played-map manifest has 13 measured and six explicit no-geometry results:

```text
311286db7907e8785aa7e05e167810a457737c0ac7e25df9adc718db708de7f4
```

This proves the required null boundary for `etl_frostbite` and the other five
uncovered maps. Legacy radius-500 objective spheres are not substituted.

## Verification

Synthetic W1-W3 unit bundle:

```text
49 passed
```

Opt-in integration suite loading every real indexed BSP:

```text
5 passed
```

The real suite asserts exact aggregate counts, measured-volume provenance,
brush containment, and unresolved dynamic state. The analyzer was then run
twice, once for every indexed BSP and once for the played-map boundary.

Local validation used an isolated Python 3.13 test environment because the
running development service still uses Python 3.10 while the repository and
CI require Python 3.11 or newer. No service environment was changed.

## Remaining Gates

W3 does not establish any of the following:

1. The BSP entity lump is the complete live server entity set. ET:L custom
   entity sources and runtime `func_fakebrush` creation remain unverified.
2. A door, mover, constructible, explosive, or conditional static brush's
   transform and linked/solid state at historical time `t`.
3. ET:L-compatible patch collision or a purpose-specific line-of-sight mask.
4. The currently active objective/spawn set at historical time `t`.
5. Offline/live trace agreement.

Therefore W4 must return `indeterminate` when a trace can intersect an
unresolved brush entity, and the affected server/map configuration remains
incomplete until its runtime entity sources are inventoried. W5 owns the
stage-state replay. W6 owns validation against live `trap_Trace`.

No database write, production deploy, service restart, Lua change, or game
server mutation was performed.
