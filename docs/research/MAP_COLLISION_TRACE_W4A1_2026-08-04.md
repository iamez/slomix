# W4a1 map collision trace: measured foundation

Date: 2026-08-04  
Scope: read-only offline geometry; no API route, metric, database write, Lua change, deploy, or service restart

## Verdict

The convex-brush point-trace foundation is implemented and fails closed around every collision input it cannot yet
prove. It is suitable for review and for building W4a2. It is **not** a completed W4a collision model and must not feed
a player score or visibility metric.

The implementation can return a definitive static-world brush block. It can return `clear` only when the caller has
explicitly marked runtime entity completeness and state as verified and the segment does not cross an uncompiled solid
patch. The normal catalog-backed path leaves those runtime gates unverified, so a non-blocked segment is
`indeterminate`.

## Implemented contract

- BSP traversal clips each point segment through the node tree and tests only referenced leaf brushes/surfaces.
- Convex brushes use the ET:L interval-clipping behavior and `SURFACE_CLIP_EPSILON = 0.125`.
- An axis-aligned broad phase is derived only from exact axial brush planes. Its clip padding is scaled by each plane's
  axial coefficient, so non-unit normals remain conservative. The final decision always uses all convex half-spaces; an
  AABB never establishes a block.
- Every result carries a named mask and raw bits:
  - `line_of_sight_solid`: `CONTENTS_SOLID` (`0x00000001`)
  - `player_movement_solid_playerclip`: `CONTENTS_SOLID | CONTENTS_PLAYERCLIP` (`0x00010001`)
- The implemented shape is explicitly `point`. The movement mask is available for content selection, but this PR does
  not claim an ET:L player-box movement trace.
- Observer eye offsets match the current Slomix Lua contract: standing `+56`, crouching `+36`, prone `+12`.
- Target bounds use ET:L's axis-aligned player bounds: XY `[-18, 18]`, minimum Z `-24`, and maximum Z `48/24/16` for
  standing/crouching/prone.
- The frozen target set contains six labelled endpoints: eye-to-eye, upper torso, and four axis-aligned side points.
  Availability uses `any_clear`. Output is named `line_of_sight_availability`, never `saw`.
- Missing stance, missing/invalid BSP traversal, intersected uncompiled solid patch, any dynamic submodel without an
  observed runtime transform,
  unverified runtime state, or unverified runtime-entity completeness remains machine-readable `indeterminate`.
- W6 validation status is carried as `unvalidated_until_w6`.

The implementation is independent Python based on the documented interval/half-space behavior. No ET:L GPL source was
copied into this MIT repository. ET:L source commit `7a784b4504977caf1c44acf668f02cacd2153632` was used as a compatibility
reference for constants and behavior.

## Synthetic proof

`tests/unit/test_map_geometry_trace.py` covers:

1. exact box entry fraction including the 0.125 clip epsilon;
2. a slanted half-space case that rejects an AABB-style false block;
3. a nearly axial large-coordinate plane that cannot create a non-conservative broad-phase bound;
4. non-unit axial normals receive coefficient-scaled world-space padding;
5. empty brushes are ignored like ET:L rather than treated as universal solids;
6. `startsolid`/`allsolid` reporting, including overlapping brushes with equal zero-fraction hits;
7. `PLAYERCLIP` ignored by LOS but included by the named movement-content mask;
8. intersecting solid patch returns `indeterminate`, while a non-intersecting patch does not poison a clear segment;
9. unverified runtime completeness cannot return clear;
10. dynamic inline-models remain `indeterminate` without supplied transforms, even if coverage flags are verified;
11. missing/cyclic BSP trees and missing stance fail closed;
12. frozen stance bounds, eye heights, target labels, any-clear aggregation, and W6 label.

Measured targeted suite on Python 3.13.14: **53 passed** across the new trace tests plus the existing W2/W3 contracts.

## Real-asset proof

Command:

```bash
venv/bin/python scripts/analyze_map_collision_trace.py --pairs-per-map 16
```

Input and sample:

| Item | Measured |
|---|---:|
| Parsed maps | 20 |
| Brushes | 202,749 |
| Empty brushes | 0 |
| Planes | 1,324,006 |
| Non-finite/zero normals | 0 / 0 |
| Patch surfaces | 4,794 |
| Solid patch surfaces | 4,524 |
| Catalog collision entities | 1,058 |
| Deterministic cross-team spawn pairs | 320 |
| Frozen target endpoint traces | 1,920 |

Result classification:

| Context | Blocked | Clear | Indeterminate |
|---|---:|---:|---:|
| Static-only diagnostic, pair-level | 278 | 42 | 0 |
| Catalog-backed fail-closed, pair-level | 278 | 0 | 42 |
| Static-only diagnostic, endpoint-level | 1,674 | 246 | 0 |

The 42 static-only clear pairs becoming 42 indeterminate pairs is the required runtime collision gate, not a quality
failure. Catalog flags do not supply observed transforms; static-only clear means only that this incomplete kernel found
no covered blocker. It is not an engine-validated visibility claim.

The real-asset integration test repeats one deterministic pair on every map and asserts that the normal unverified
runtime context can never return clear.

## Cost measurement

Measured on the local developer host; timings exclude PK3 scan/BSP parsing and include point-tree traversal, broad phase,
exact brush tests, and patch AABB gates:

| Per endpoint | Time |
|---|---:|
| p50 | 774.450 us |
| p95 | 2,037.985 us |
| max | 3,158.994 us |

| Candidate work per endpoint | Mean | Max |
|---|---:|---:|
| BSP leaves | 21.967 | 57 |
| Exact convex-brush tests | 15.860 | 73 |
| Solid patch AABB tests | 0.188 | 15 |

The first deliberately conservative prototype traversed an average 317 leaves and 1,272 brushes per ray and measured a
47.3 ms median for six endpoints. ET:L-style clipped traversal reduced that to 13.4 ms; axial broad phase then reduced
exact brush tests to the final values above.

This still fails the eventual full-round budget. At 66 pairs, six endpoints, and a 1,000 ms analysis cadence over a
12-minute round, there are 285,120 endpoint traces. Multiplying by the measured p50 gives roughly **221 seconds**, before
timeline reconstruction or patch facets. The 200 ms capture cadence would be five times worse. These are workload
projections, not a benchmark of a future batched implementation.

Required before a consumer exists:

- batch shared-origin/tree work across endpoints and pairs;
- choose analysis cadence from the measured budget, independent of the 200 ms capture cadence;
- cache only immutable static geometry work with explicit keys;
- remeasure after W4a2 patch facets, because their cost is currently absent;
- meet the Spider Web full-round acceptance budget or materialize a proven intermediate representation.

## Deliberately unresolved

1. **Patch facets (W4a2):** a patch AABB is only an uncertainty gate. It never blocks and never proves clear. W4a is not
   complete until a license-safe ET:L-compatible facet implementation passes hand-checked tests and W6 comparison.
2. **Dynamic submodels:** W3 initial bounds identify affected segments, but exact transformed submodel tracing and
   timestamped state are not implemented. W5 must supply defensible state; absent that, results remain indeterminate.
3. **Runtime entity completeness:** the actual server's custom entities and `func_fakebrush` instances are not inventoried.
4. **Engine agreement:** no paired `et.trap_Trace` C4 fixtures exist. All output remains unvalidated until W6.
5. **Metric validity:** no signal or weight is introduced. Section 8 is not bypassed; it becomes mandatory only after the
   measurement layer is complete, independently validated, and cheap enough to evaluate without selection shortcuts.
6. **Spawn-pair representativeness:** the deterministic sample is proof of real-file execution and cost, not a gameplay
   accuracy sample.

## Next review unit

W4a2 should implement patch collision as a separate PR. Its acceptance evidence must include curved and planar patch
fixtures, edge/corner epsilon cases, all 20 real maps, a new cost table, and continued `indeterminate` behavior for
runtime/custom-entity uncertainty. W5 must not start consuming line-of-sight output merely because this foundation is
merged.
