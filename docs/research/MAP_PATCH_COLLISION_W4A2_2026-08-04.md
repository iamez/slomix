# W4a2 quadratic patch collision: measured static-world closure

Date: 2026-08-04  
Scope: read-only offline ET:L BSP point traces; no API route, metric, database write, Lua change, deploy, or restart

## Verdict

The W4 point-trace kernel now compiles and traces every local quadratic `MST_PATCH` surface instead of treating a crossed
patch AABB as permanent uncertainty. All **4,794** patches across the 20 local BSP maps compiled into **39,124**
one-sided point-collision facets with **zero compilation failures**. Of those, 4,524 solid patches produced 36,652
facets eligible for the line-of-sight mask.

This closes the static patch portion of W4a. It does **not** make the output a claim that a player saw another player.
Dynamic submodels, historical transforms, live custom entities and `func_fakebrush` completeness remain unresolved, and
the offline result remains `unvalidated_until_w6` until paired `et.trap_Trace` fixtures exist.

## Implemented contract

- Patch dimensions and control-point ranges remain the strict W2 parser's responsibility.
- Each odd quadratic control grid is adaptively flattened in both parameter directions. Subdivision continues while the
  curve midpoint differs from the linear midpoint by at least 16 game units, matching the ET:L compatibility constant.
- Degenerate adjacent grid columns collapse with the 0.1-unit point tolerance. Degenerate triangles produce no facet,
  matching the engine's no-hit treatment rather than becoming universal solids.
- Each remaining grid cell becomes two oriented planar facets. Point traces collide only from the facet's front side,
  use the exact plane intersection for facet containment, and report the engine-compatible 0.125 plane-distance pushoff.
  Like ET:L, an existing pushed trace fraction limits the raw next-facet intersection before that facet applies its own
  pushoff; a regression test freezes this order-dependent compatibility behavior.
- Patch bounds are expanded by one game unit for the broad phase. Bounds never establish a block; the oriented facet
  test makes the final decision.
- `CONTENTS_SOLID` and `CONTENTS_PLAYERCLIP` remain purpose-specific. A playerclip-only patch does not block the named
  LOS mask and does block the named movement-content mask.
- A compiled patch hit reports `solid_patch`, the BSP surface index, facet index, fraction and measured candidate work.
- A missing/failed compilation remains `solid_patch_uncompiled` and `indeterminate` whenever its conservative bounds
  can affect the segment. Non-finite control points have no trusted bounds and therefore cannot fail open.
- A nearer brush wins over a farther patch; a nearer patch wins over a farther known brush. Any definitive static block
  is sufficient for line-of-sight unavailability.
- An all-endpoints blocked availability result uses the aggregate `static_geometry_blocked` reason; endpoint results
  retain the exact `solid_brush` or `solid_patch` provenance.

The Python implementation is independent. ET:Legacy source commit
`7a784b4504977caf1c44acf668f02cacd2153632` was used as the behavioral reference for grid orientation, one-sided point
traces and constants; no ET:L source file is included in this MIT repository.

## Synthetic proof

`tests/unit/test_map_geometry_patch.py` and `tests/unit/test_map_geometry_trace.py` cover:

1. planar 3x3 control grids collapsing to two facets;
2. exact 0.125 plane-distance pushoff;
3. front-to-back collision and back-to-front non-collision;
4. edge/corner inclusion and an immediately outside miss;
5. curved-grid subdivision with an independently evaluated quadratic midpoint;
6. degenerate patch no-hit behavior and malformed/non-finite input rejection;
7. BSP leaf-surface integration and surface/facet provenance;
8. LOS versus playerclip mask behavior;
9. nearest brush-versus-patch ordering;
10. fail-closed behavior for unavailable and non-finite compilation;
11. injected patch-catalog validation; and
12. aggregate versus endpoint-specific block provenance.

Measured W2/W3/W4 targeted suite on Python 3.13.14: **66 passed**. The repository-wide suite also completed with
**4,071 passed and 74 skipped**; the skips require unavailable test PostgreSQL credentials, optional local fixtures, or
the separately executed real-asset opt-in.

## Real-asset proof

Command:

```bash
venv/bin/python scripts/analyze_map_collision_trace.py --pairs-per-map 16
```

Input and compilation:

| Item | Measured |
|---|---:|
| Parsed maps | 20 |
| BSP patch surfaces | 4,794 |
| Solid patch surfaces | 4,524 |
| All compiled facets | 39,124 |
| Solid-mask facets | 36,652 |
| Patch compilation failures | 0 |
| Mean compile time per map | 35.168 ms |
| Maximum compile time for one map | 69.412 ms |
| Deterministic cross-team spawn pairs | 320 |
| Frozen target endpoint traces | 1,920 |

Endpoint result provenance:

| Reason | Endpoints |
|---|---:|
| `solid_brush` | 1,662 |
| `solid_patch` | 12 |
| `static_geometry_clear` diagnostic | 246 |

All 12 real-asset patch hits occurred on `sw_goldrush_te` in this deterministic sample. Pair-level classification remains
278 blocked and 42 static-only diagnostic-clear; the normal catalog-backed path remains 278 blocked, 42 indeterminate
and **0 clear**. The 12 patch results replace farther brush provenance at those endpoints rather than changing the
pair-level any-clear result.

The real-asset integration gate independently recompiles every patch and asserts the exact 4,794 / 39,124 / 0 totals.
The existing all-map spawn test continues to prove that the normal unresolved-runtime path never returns clear.

## Cost measurement

Timings exclude PK3 scan, BSP parsing and the separately reported one-time patch compilation. They include BSP traversal,
brush broad phase/exact clipping, patch bounds and facet tests:

| Per endpoint | W4a1 brush foundation | W4a2 with facets |
|---|---:|---:|
| p50 | 774.450 us | 830.272 us |
| p95 | 2,037.985 us | 2,240.269 us |
| max | 3,158.994 us | 4,214.349 us |

| Candidate work per endpoint | Mean | Max |
|---|---:|---:|
| BSP leaves | 21.967 | 57 |
| Exact convex-brush tests | 15.860 | 73 |
| Candidate solid patch surfaces | 7.520 | 83 |
| Exact patch-facet tests | 5.838 | 224 |

The p50 increased by about 7.2% and p95 by about 9.9% on this developer host. The max is sample-sensitive and increased
by about 33.4%, so the tail requires attention before a consumer exists. Patch-surface accounting is also stricter than W4a1:
blocked brush traces now continue far enough to determine whether a nearer patch owns the first hit.

At 66 pairs, six endpoints, a 1,000 ms analysis cadence and a 12-minute round, 285,120 endpoint traces multiplied by the
measured p50 project to roughly **237 seconds**. This remains far outside the full-round one-second budget. The 200 ms
capture cadence is not an analysis budget and would multiply this cost by five.

## Remaining gates

1. **W6 engine agreement:** synthetic geometry proves internal behavior, not equivalence to every ET:L facet edge case.
   Paired live `et.trap_Trace` inputs are mandatory before any visibility consumer or metric.
2. **Dynamic transforms:** any catalogued door, mover or constructible keeps non-blocked traces indeterminate until W5
   supplies timestamped transforms/state. Coverage flags alone do not carry transforms.
3. **Runtime completeness:** live custom-entity sources and `func_fakebrush` instances remain owner-gated inventory work.
4. **Performance:** batch shared tree work, immutable collision caches and a separately chosen analysis cadence must meet
   the Spider Web full-round budget after measurement. No cache may hide runtime-state provenance.
5. **Metric validity:** this PR introduces no score, weight, exposure claim or information-state belief. Section 8 remains
   mandatory after W5/W6 and performance gates; line-of-sight availability alone never means `saw`.

## Reproduction

```bash
venv/bin/python -m pytest \
  tests/unit/test_bsp_reader.py \
  tests/unit/test_map_entity_extraction.py \
  tests/unit/test_map_geometry_patch.py \
  tests/unit/test_map_geometry_trace.py -q

SLOMIX_RUN_REAL_ASSET_TESTS=1 venv/bin/python -m pytest \
  tests/integration/test_map_geometry_real_assets.py::test_w4a2_compiles_every_real_patch_without_fail_open_gaps \
  tests/integration/test_map_geometry_real_assets.py::test_w4a_real_spawn_segments_never_clear_with_unverified_runtime_collision -q

venv/bin/python scripts/analyze_map_collision_trace.py --pairs-per-map 16
```
