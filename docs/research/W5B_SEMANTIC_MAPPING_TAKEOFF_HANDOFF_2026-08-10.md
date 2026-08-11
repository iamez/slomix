# W5b semantic mapping: takeoff, trade-offs and handoff

Date: 2026-08-10

Last updated: 2026-08-11

Status: implementation in progress. Engine identity, Phase 3 dispositions, the Phase 4
lossless ordered program, the override boundary, runtime-control classification and the
bounded single-event symbolic walker and isolated nested-dispatch resolver are locally
and externally reviewed. The bounded nested executor, shared recursive-work budget and
temporal/concurrency frontiers have also completed exact-head external review. PR #633
merged as `e649b0493a1ca0ed9cb3b2a2935ebcd78f494202`; the follow-up frontier-classification
increment is now isolated on `agent/map-geometry-w5b-frontier-classification`.

Current branch: `agent/map-geometry-w5b-frontier-classification`

Current base: `origin/main` at
`e649b0493a1ca0ed9cb3b2a2935ebcd78f494202`

PR #633's last substantive implementation head that completed its five-minute review
quiet period and final refresh:
`abb2ba947dc5c7234830929829cdb55f1af8033e`

Earlier resolver review-closure documentation head:
`63c23e2b16269dc37a58b670e3154056cc9b5875`

The documentation-only commit that advances this pointer cannot contain its own Git
hash. Query PR #633 before relying on this historical checkpoint as current review
state.

Current review correction: after the branch was marked ready and refreshed from
`main`, GitHub Codex found that the executor searched every `followspline` argument
for `wait`. ET:Legacy only interprets `wait` in the optional tail after direction,
spline and speed (and after the buffer index for `accum`/`globalaccum`). A spline
whose target name is literally `wait` was therefore being classified as waiting and
lost its legal immediate continuation. The correction and its exact-head review are
complete at `abb2ba94`; the documentation-only commit recording that closure must
still pass its own exact-head checks before merge.

Scope: read-only ET/ET:Legacy map assets; no database write, deploy, service restart,
Lua change, production API integration, metric or rating change

Primary specification: `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`, especially
sections 3, 5.6, 7.4.1, 8, 9 W5, 12 W5, 13 and 16

Immediate predecessor:
`docs/research/W5A_STATIC_STAGE_ASSET_FOUNDATION_2026-08-08.md`

## How to maintain this document

This is the canonical W5b execution and transfer record. Update it in every
substantive W5b commit, not only at the end. At minimum keep these fields current:

1. branch base and current reviewed head;
2. checklist status and the next executable step;
3. decisions and rejected alternatives;
4. measured real-asset denominators and manifest hashes;
5. test commands and exact results;
6. unresolved review findings and why they block or do not block merge;
7. new unknowns, especially any claim that depends on the live engine write/load path.

Do not rewrite an earlier decision silently. Add a dated decision-log entry that
states what changed and what evidence changed it.

## Sixty-second handoff

W3 knows physical BSP entities: objective brush volumes, objective markers, spawn
points and collision-relevant doors, movers and constructibles. W5a independently
resolves and parses `.script` and `.objdata`, and exposes possible script effects and
trigger-call edges. The two models are intentionally not joined yet.

W5b builds that semantic join. It must identify which concrete BSP entities and
objective descriptions a script identity or effect may refer to, preserve legitimate
one-to-many groups, and return explicit unknowns for zero, conflicting or unproven
matches. It then reports which maps have a defensible static stage graph.

W5b does **not** reconstruct a historical state at time `t`. A static script proves
only that a transition can occur. W5c may later replay timestamped telemetry, but only
after event-family completeness is proven per tracker version. No W5b output may be
consumed as a live objective, spawn or route state.

## What W5b should achieve

For every independently resolved map asset set, publish a deterministic semantic
model with provenance for:

- concrete BSP entities selected by each script block under engine-compatible
  script-name rules;
- objective descriptions keyed by team and objective number;
- candidate links among objective descriptions, objective markers and measured
  objective volumes;
- spawn groups and the candidate set addressed by each `setautospawn` effect;
- dynamic route entities addressed by `setstate`, `gotomarker`, `alertentity` and
  other approved effects;
- ordered possible effects and accumulator guard branches whose semantics have been
  verified against ET:Legacy source;
- unresolved, ambiguous, opaque, unsupported and external/custom identities;
- a per-map static-graph verdict with machine-readable failure reasons.

The output is a graph of legal possibilities and candidate sets. It is not a chosen
objective, a selected player spawn, a runtime transform or a historical transition
timeline.

## What this unlocks

### W5c event-family audit and replay

Once every static transition says which world state it can affect, W5c can enumerate
the exact event families required per map. That turns "we have some carrier and
construction rows" into a testable completeness contract per tracker version.

### Stage-aware dynamic geometry

W4 can currently mark a trace that intersects unresolved runtime geometry as
`indeterminate`. W5b identifies which door, mover or constructible state transitions
could resolve such geometry. Historical resolution still waits for W5c observations.

### Stage-aware spawn and objective candidates

Layer 2 reachability and future Layer 4 objective-control research require the set of
selectable spawns and concurrently live objectives. W5b supplies the static candidate
space from which an observed replay can later derive those sets. It does not supply
the time-varying set by itself.

### Honest coverage denominators

Parser success is not semantic coverage. W5b publishes how many maps have a fully
defensible static graph, which maps are partial, and the exact blockers on each map.
This denominator remains separate from future historical round-time replay coverage.

## Hard boundaries

W5b must not:

- infer a transition timestamp from script order or final round outcome;
- choose one objective or spawn when the engine permits a set;
- use fuzzy, substring or edit-distance matching to improve coverage;
- treat missing custom entities as impossible without checking the load path;
- turn `legacy_numeric` main-objective selectors into target names;
- assume a selected BSP's neighbouring script or objdata is authoritative;
- use objective wording or class as a substitute for world-entity identity;
- interpret all installed script blocks as active without proving entity selection;
- claim a dynamic transform or collision state from a static possibility graph;
- enter any result into a proximity score, rating, leaderboard or API live-state path;
- start W5c replay code before its event-family completeness prerequisite is closed.

Section 8 validation does not approve a W5b graph as a metric. It becomes mandatory
later for every formula that consumes stage-aware state. W5b must preserve enough
provenance and unknown states that those later experiments can fail closed.

## Existing measured foundation

W5a's exact real-asset acceptance on the current assets reports:

| Measurement | Result |
|---|---:|
| BSP maps with independently resolved script and objdata | 20 / 20 |
| Parsed script entities | 583 |
| Event handlers | 2,153 |
| Actions retained | 10,057 |
| Typed possible effects | 2,929 |
| Trigger calls | 1,315 |
| Trigger calls with one internal target | 1,304 |
| Trigger calls without an internal target | 11 |
| Maps with complete internal trigger closure | 13 / 20 |
| Objective descriptions | 250 |
| Explicitly classified objective descriptions | 232 / 250 |

W3's measured asset inventory reports 2,376 spawn points, 158 objective volumes,
96 objective markers and 1,058 collision-relevant brush entities across the same 20
indexed BSP maps.

### W5b takeoff probe

A read-only exploratory probe on 2026-08-10 compared W5a script-block names with raw
BSP identity fields. It is a scope measurement, **not** a mapping algorithm or an
acceptance result. The probe used Python case folding; production matching must use
the verified ET ASCII comparison contract.

| W3 entity kind | Total | Has `script_name` | Naive script-name/block match | Any naive tested-field match |
|---|---:|---:|---:|---:|
| Spawn point | 2,376 | 1,829 | 395 | 494 |
| Objective volume | 158 | 124 | 20 | 23 |
| Objective marker | 96 | 83 | 21 | 21 |
| Collision entity | 1,058 | 530 | 315 | 315 |

The low direct match rate is not automatically a defect. Many concrete entities
legitimately share one script identity, some effects address another namespace, and
spawn selection commonly uses a textual group description. It proves that a generic
join or convenient string heuristic would be unsafe.

A second probe checked all raw BSP entities, not only W3's typed tactical subset.
Of the 583 parsed script blocks, 558 names had at least one naive raw `scriptname`
match and 25 did not. Multiple concrete entities may share one matching script block;
that is a group, not automatically an ambiguity. Selected entities include logical
classes that W3 intentionally does not expose, including `script_multiplayer`,
`target_script_trigger`, `team_WOLF_checkpoint`, flags and visual helpers. Some
unmatched names, including `game_manager` on several maps, may be assigned by an
engine spawn/load path rather than a literal BSP key. They must be researched before
being labelled missing.

The real assets also contain 1,465 `accum`, 141 `globalaccum`, 745 `wait`, 1,315
`trigger`, 1,728 `setstate`, 172 `gotomarker`, 136 `alertentity` and 115
`setautospawn` actions. A graph that ignores accumulator abort conditions or action
order would publish impossible transitions. This is why control flow is part of W5b.

## Frozen engine-source research

The Phase 1 reference is ET:Legacy commit
[`732518efb1c479dcd29b13361f30a2e92df1cf2a`](https://github.com/etlegacy/etlegacy/tree/732518efb1c479dcd29b13361f30a2e92df1cf2a),
checked out read-only on 2026-08-10. The implementation records behaviour, not just
comments or function names:

- [`G_ParseField`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_spawn.c#L696-L784)
  assigns generic BSP fields with ASCII-case-insensitive key matching in spawn-var
  order. In contrast, the special `G_SpawnString` helper compares exact key bytes.
- [`SP_script_multiplayer`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L1391-L1415)
  overwrites the entity's `scriptName` with `game_manager` before script parsing. A
  literal-BSP-only read therefore falsely reports some game-manager blocks missing.
- [`G_Find`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_utils.c#L309-L352)
  scans active entities in order and compares with `Q_stricmp`; that comparison folds
  only ASCII `a-z`, not Unicode.
- [`G_ScriptAction_Trigger`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1720-L1848)
  dispatches to every matching `scriptName`. Shared names are legitimate groups.
- [`G_ScriptAction_SetState`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L4008-L4085)
  and
  [`G_ScriptAction_AlertEntity`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2238-L2292)
  apply to every matching `targetname`.
- [`G_ScriptAction_GotoMarker`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1352-L1450)
  first selects the first registered `path_corner_2`/`info_train_spline_control`, then
  falls back to the first active entity with that `targetname`.
- [`G_ScriptAction_SetAutoSpawn`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L170-L217)
  selects the first runtime `message` match. `SP_team_WOLF_objective` overwrites that
  message from the exact lowercase `description` spawn key and registers a major spawn
  marker. Actual team spawn points are filtered by active state/ownership and selected
  by proximity to that marker, so an autospawn effect does not directly name one BSP
  spawn point.
- `wm_set_main_objective` looks up the first `trigger_objective_info` through its
  `target` field, despite comments calling it a target name. All installed calls remain
  numeric and no-op under the checked current path, so W5a's `legacy_numeric` gate
  remains correct.
- `accum` state belongs to one concrete entity; `globalaccum` state belongs to the
  level. Abort guards set the current stack head to the end, while `trigger_if_equal`
  may replace a script event and stop the caller's current pass. Installed assets use
  only `set`, `inc`, bit set/reset, the six observed abort predicates and
  `trigger_if_equal`; none uses random, wait-while-equal or dynamite-count operations.
- The script runner executes actions in order and stops the current pass when an
  action returns false or a nested event changes the script id. Static control-flow
  projection therefore cannot be reconstructed by collecting typed effects alone.
- [`G_Script_ScriptRun`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L790-L871)
  proves that ordering/stop contract, while
  [`G_Script_ScriptChange`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L629-L654)
  restores the prior event only when a replacement completes synchronously without
  another script-id change.
- [`G_ScriptAction_Accum`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2438-L2693)
  and
  [`G_ScriptAction_GlobalAccum`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2722-L2938)
  are the pinned evidence for local/global storage, abort-to-event-end and conditional
  trigger dispatch.
- [`wait`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1651-L1718),
  [`resetscript`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L3130-L3139)
  and
  [`halt`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L3198-L3240)
  can return false and therefore remain explicit control barriers.
- [`CMod_LoadCustomEntityString`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/qcommon/cm_load.c#L458-L488)
  asks the virtual filesystem for `maps/<map>.ent` before reading the BSP entity
  lump. An override replaces the complete entity identity source; checking only BSP
  read paths cannot prove runtime identity completeness.

These findings establish the checked current-source contract. They do not prove that
the live server build has identical semantics. Any version-sensitive behaviour remains
tagged `unverified_live_build` until its artifact/source is independently identified;
no service inspection or restart is authorized by W5b.

### Engine-effective identity baseline

The first W5b implementation applies the proven `script_multiplayer` class override
and ET ASCII comparison. On the 20 installed indexed BSP maps it measures:

| Identity result | Count |
|---|---:|
| Parsed script blocks | 583 |
| Blocks selecting exactly one concrete BSP entity | 510 |
| Blocks selecting a legitimate concrete-entity group | 50 |
| Blocks without a concrete BSP identity candidate | 23 |
| Concrete entities selected across all blocks | 1,025 |
| Maps with a BSP candidate for every parsed block | 13 / 20 |

This supersedes the naive literal-field count for engine-effective mapping but does not
erase the takeoff probe: the difference is direct evidence that class write paths
matter. The 23 missing blocks remain an inventory, not proof that they are impossible
at runtime. The 13-map result is an identity-input denominator, not a defensible static
graph verdict; trigger, effect, custom-entity and control-flow gates are still pending.

### Installed accumulator projection baseline

The current local implementation projects every installed `accum` and `globalaccum`
action into an entity-scoped or level-scoped typed instruction. It rejects malformed
integer syntax, out-of-range buffers, undefined signed bit shifts, unsupported
operations and incorrect arity as structured issues. This is a typed source-program
projection only; it does not yet execute branches or publish a possibility graph.

| Projection | Count |
|---|---:|
| Deterministic mutations | 994 |
| Abort guards | 313 |
| Conditional triggers | 299 |
| Structured issues in installed assets | 0 |

The 1,606 installed projections contain 414 `set`, 24 `inc`, 289 `bitset`, 267
`bitreset`, 149 `abort_if_equal`, 78 `abort_if_not_equal`, 39
`abort_if_bitset`, 33 `abort_if_not_bitset`, 9 `abort_if_less_than`, 5
`abort_if_greater_than` and 299 `trigger_if_equal` instructions. This freezes the
observed deterministic subset without approving runtime-dependent operations that are
not present in the installed corpus.

### Exact W3 identity-join baseline

The generic BSP identity index is now joined to the W3 tactical catalog only by the
stable BSP `entity_index`. The join rejects provider/source drift, missing indices,
one entity appearing in multiple W3 categories and classname drift. It never re-matches
names. Real-asset acceptance linked all 3,688 W3 entities exactly:

| W3 kind | Exact links |
|---|---:|
| Spawn points | 2,376 |
| Objective volumes | 158 |
| Objective markers | 96 |
| Collision entities | 1,058 |

All linked catalogs deliberately retain `runtime_entity_completeness = unverified`.
An exact static BSP join is not evidence that every raw entity survives the active
game-mode/custom-entity runtime load path.

### Effective entity-source baseline

The local W1/W5b extension indexes optional `maps/<map>.ent` providers both inside
PK3 archives and as a loose `etmain/maps/` file. Different bytes remain ambiguous
because this tool does not know the live virtual-filesystem precedence. Identical
duplicates are content-resolved. Provider reads remain bound to recorded size, CRC32
and SHA-256.

The current developer asset tree has no `.ent` provider for any of the 20 indexed BSP
maps, so their engine-effective identity source falls back to the BSP lump. This is
measured evidence for this indexed tree, not a claim about the live server filesystem.
If an override is later present, the identity source is labelled `ent_override`; the
existing W3 BSP catalog source will intentionally fail its exact-source join until W3
is extracted from the same effective entity source.

### Action-specific effect-projection baseline

The local Phase 3 projector maps all 2,929 typed W5a effects through their verified
action-specific namespaces. Every projection retains the source script-name lookup;
an effect in a parsed block whose concrete runtime entity is unproven is not silently
counted as executable. The result types remain static candidates, not state claims.

| Projection | Count |
|---|---:|
| `setstate` / `alertentity` all-target projections | 1,864 |
| Objective-status description projections | 672 |
| `gotomarker` first-target projections | 172 |
| `setautospawn` marker/team-candidate projections | 115 |
| Winner / round-end global projections | 64 |
| Main-objective projections | 42 |
| Unhandled typed effects | 0 |

Measured blocker and provenance inventory:

- 97 projections originate in script blocks with no concrete static BSP script-name
  identity: 96 `setstate` and one `alertentity` effect across five maps. The alert is
  `sw_goldrush_te` block `defense2_toi` targeting the installed `rubble3` identity;
- across all 1,864 `setstate`/`alertentity` projections, 1,709 have both a static
  source and target, 94 have neither, 58 have a static source but no static target,
  and three have a static target but no static source;
- `setstate` has 1,394 unique targets, 182 legitimate all-match groups and 152
  statically missing targets. Of those 152 effects, 94 also lack a static source and
  58 have an installed source. The engine tolerates a missing target, but W5b cannot
  call it a historical no-op while runtime entity completeness is unverified;
- of those 152 missing-target effects, 137 names are absent from both effective
  entities and parsed script blocks, eight match only the entity `script_name`
  namespace, and seven match only a parsed script block. None proves a `targetname`
  match, so namespace substitution is not permitted;
- all 136 `alertentity` effects have static targets: 72 unique and 64 groups;
- all 172 `gotomarker` destinations resolve under path-corner-first rules; 94 use the
  registered path-corner namespace, 78 use target-name fallback, and the installed
  corpus has no `relative` option;
- 114 of 115 autospawn effects select a static `team_WOLF_objective` marker; the one
  blocker is `erdenberg_t2` Allies `the Command Post`; five successful lookups retain
  shadowed message candidates while selecting only the engine-first marker;
- autospawn publication retains 7,951 per-effect team spawn candidates in aggregate;
  final spawn selection remains runtime active/ownership/proximity dependent;
- 670 objective-status effects have exactly one team/number `.objdata` description;
  `etl_beach` objective 7 lacks both Axis and Allies descriptions;
- all 42 installed main-objective calls remain blocked `legacy_numeric`; none is
  rewritten as an entity name.

### Ordered control-program baseline

The local Phase 4 foundation projects every eligible parsed action into one ordered,
non-executed instruction. It does not yet decide which path is reachable. Exact
real-asset accounting covers all 2,153 event nodes and all 10,057 actions:

| Instruction | Count |
|---|---:|
| Stage-effect projection | 2,929 |
| Source-classified runtime action | 3,413 |
| Plain trigger edge | 1,315 |
| Accumulator mutation | 994 |
| Accumulator abort guard | 313 |
| Accumulator conditional trigger | 299 |
| Explicit control barrier | 794 |

The barriers are 745 `wait`, 25 `resetscript` and 24 `halt` actions. The 3,413
runtime instructions span 38 command names. Their current-event control behavior is
now source-classified; non-immediate categories remain blockers until the path walker
models the corresponding temporal, lifecycle or nested-event behavior.
The most common are `wm_teamvoiceannounce` (589), `setchargetimefactor` (420),
`followspline` (302), `wm_announce` (274), `playsound` (241),
`wm_addteamvoiceannounce` (239) and `wm_removeteamvoiceannounce` (222).

| Current-event control disposition | Installed families/forms | Instructions |
|---|---|---:|
| Immediate continue | 32 families + 9 safe `set` forms | 2,860 |
| Conditional temporal pause | `followspline`, `faceangles` | 445 |
| Deferred source removal | `remove` | 91 |
| May dispatch a death event | `kill` | 13 |
| May replace script context through spawn | no installed `set` form | 0 |
| May stop on spawn failure | `create` | 4 |

The 38 command-to-callback bindings come from the pinned
[`gScriptActions` registry](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L48-L151).
The 32 immediate families were checked through their complete callback return paths in
[`g_script_actions.c` lines 225-718](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L225-L718),
[`992-1085`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L992-L1085),
[`1859-2411`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1859-L2411),
[`3147-3942`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L3147-L3942)
and
[`4094-4500`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L4094-L4500).
"Immediate" here describes only the current event's control result; every runtime
instruction remains in the program because its game-state mutation may matter later.

The special cases are pinned to ET:Legacy's
[`followspline`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L730-L949),
[`faceangles`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2996-L3121),
[`remove`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L3952-L3957),
[`kill`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1296-L1308),
[`set`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L4872-L4963)
and
[`create`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L5127-L5182).
`kill` is not treated as a plain `qtrue`: its target path reaches
[`G_KillEnts`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_target.c#L841-L879),
which can invoke mover death callbacks and therefore nested script events.
Of the nine installed `set` actions, seven set only `origin` and two set both
`contents` and `clipmask`; all nine therefore continue immediately. No installed form
uses `scriptName`, `classname_nospawn` or `classname`. Synthetic source-contract
fixtures prove that the first two supported-but-unobserved forms also continue, while
an actual case-insensitive `classname` key remains a blocker because `G_CallSpawn` can
parse and dispatch a new `spawn` event on the same entity. All 91 installed `remove`
actions return `qtrue` and schedule source removal for the next frame, so the lifecycle
effect is retained but does not block later instructions in the same event pass.

### Single-event symbolic-walker checkpoint

The reviewed Phase 4 increment walks one concrete source entity through one
ordered event program. It requires the caller to provide an explicit initial state:
`zeroed()` is valid at verified level initialization, while a standalone event whose
history is unknown must use `unknown()` or a state propagated by the future graph
walker. There is deliberately no zero-valued default that could fabricate reachability
for a later runtime trigger.

The walker now:

- stores entity accumulators by concrete BSP entity index and global accumulators in a
  shared level scope;
- executes deterministic `set`, `inc`, `bitset` and `bitreset` mutations only when the
  resulting signed 32-bit value is proven, otherwise publishing a blocker; bit index
  31 remains rejected because the pinned callbacks use signed `1 << index`, whose
  sign-bit shift is not a defined engine contract;
- splits every one of the six installed abort predicates into satisfiable true and
  false domains, removes contradictory paths and suppresses later effects on the abort
  branch;
- retains ordered typed effects and their source identity on every surviving path;
- preserves both immediate and delayed `wait` continuations because ET:Legacy skips
  waits during sudden death, while `resetscript` and `halt` retain only their later-pass
  continuation;
- preserves both possible prior-motion and immediate paths for a non-waiting
  `followspline`, delayed completion for waiting movement/rotation, and success plus an
  explicit spawn-failure frontier for `create`;
- records a machine-readable blocker reason and source line instead of stepping over a
  nested trigger, death dispatch, script-context replacement or malformed projection.
- caps all live plus completed symbolic paths at 4,096 by default; exceeding a caller's
  explicit positive budget returns a line-numbered `symbolic_path_budget_exhausted`
  frontier rather than consuming unbounded memory or claiming complete coverage.

This is not yet a map possibility graph. Plain and conditional nested triggers remain
blocked on their dispatching branches; `kill`, same-entity event replacement and the 21
cycle frontiers are also intentionally unresolved. No real-asset reachability count is
published until those transitions are modeled and the Phase 5 analyzer can distinguish
a supported path from an explicit frontier.

The resolved plain-trigger graph has 21 cyclic strongly connected components across
six maps. Every current component is a one-node self-loop and none of those 21 nodes
contains a direct stage effect. This does not make the cycles irrelevant: an iteration
can dispatch other events before returning to itself, so the future walker must retain
the cycle frontier and inspect downstream semantic relevance.

An `.ent` override remains a valid source for script-name, target and message
identity lookups, but its entity indices cannot be joined to the replaced BSP lump.
The projection context therefore retains the override identities while publishing no
W3 references and marking every affected entity-index surface
`unproven_identity_override`. Ordinary mismatched BSP sources still fail closed.

### Nested-dispatch resolution checkpoint

This isolated Phase 4 increment built an index over the ordered programs and resolves
one nested trigger without executing the target program. This separation is
intentional: dispatch identity can be proven independently, while caller replacement,
temporal continuation and cross-entity interleaving still need different executor
rules.

The resolver now:

- accepts only a program and instruction created by the same ordered-program index;
- applies ET's first matching named-or-wildcard trigger-handler rule;
- resolves `trigger self` to only the concrete caller, even when several entities
  share its script name;
- expands script-name dispatch to every selected concrete target entity in engine
  order;
- retains `activator` as no-op and `global`/`player` as runtime-dependent dispatch;
- distinguishes a missing handler, an opaque handler and a valid handler whose static
  target identity is missing;
- prevents a later, engine-unreachable duplicate script block from making a valid
  first block appear opaque.

Read-only acceptance across all 20 installed indexed maps reports:

| Resolution level | Plain trigger | Conditional trigger |
|---|---:|---:|
| Source instructions resolved | 1,291 | 299 |
| Source instructions with missing source identity | 10 | 0 |
| Source instructions with target identity missing | 3 | 0 |
| Source instructions with missing handler | 11 | 0 |
| Concrete source dispatches resolved | 1,588 | 299 |
| Concrete resolved source-target pairs | 1,937 | 299 |
| Resolved pairs targeting the concrete caller itself | 669 | 289 |

Every conditional dispatch currently has one concrete target. Plain concrete
dispatches select one target 1,447 times, two targets 13 times, three targets 104
times, four targets 15 times, six targets twice, eight targets six times and 32
targets once. These are dispatch-group measurements, not path counts or reachable
effect counts.

The 1,304 graph-resolved plain instructions split into 1,291 instructions resolved
from a concrete source, ten whose source block has no static identity and three whose
target handler has no static identity. The existing 11 missing-handler instructions
remain explicit. No missing row is converted into a no-op.

This checkpoint does **not** invoke a target program, merge its accumulator state or
claim nested effects reachable. Same-entity replacement can restore the caller only
after synchronous callee completion. A different-entity callee may pause while the
caller continues, so its future global/local mutations can interleave with later
caller actions. Treating either case as a generic recursive function call would create
false ordering. The next executor increment must model those cases separately or
return an explicit concurrency frontier.

### Bounded nested-executor checkpoint

The local executor now reuses the reviewed single-event walker over ordered program
segments and invokes the reviewed resolver only on the trigger branch. It does not
flatten scripts or treat a nested event as an ordinary Python function call.

The pinned engine source establishes the rules implemented by this increment:

- `G_Script_ScriptChange` restores the previous same-entity script status only when
  the replacement `G_Script_ScriptRun` finishes synchronously without another script
  id change;
- accumulator abort predicates set the active stack head to the event end but the
  accumulator callback still returns `qtrue`, so a synchronously aborted nested event
  restores its caller;
- script-name and conditional dispatch iterate every concrete target in entity order;
  a same-entity replacement sets a termination flag but does not stop that target
  loop early;
- a different-entity callee may pause while its caller keeps running. Its continuation
  can later interleave with caller actions and shared global accumulators, so it cannot
  be merged into the caller's immediate state.

The implementation therefore:

- executes synchronous nested target groups in concrete engine order and resumes the
  caller with shared global state plus entity-keyed local state;
- treats a synchronous accumulator abort as callee completion, not a temporal pause;
- preserves the sudden-death immediate alternative for `wait`;
- stops a different-entity or non-final shared-target callee at its first temporal
  boundary, before executing any later action, and publishes
  `cross_entity_temporal_interleaving_not_modeled` or
  `same_entity_temporal_group_order_not_modeled`;
- permits a final same-entity temporal replacement to continue as the replacement
  event while suppressing the abandoned caller suffix;
- detects active `(entity_index, event_node_id)` cycles and enforces independent path
  and recursion-depth budgets;
- records concrete entity provenance parallel to every effect, guard decision,
  temporal boundary, caller replacement and blocker.

The installed program/dispatch takeoff, before recursive execution, is shown below.
The four cells count 2,236 concrete resolved source-target **pairs**: one target
program can contribute several pairs when a script name selects several entities.
They therefore use a different denominator from the 2,153 eligible event programs
classified in the following paragraph.

| Direct target shape | Other entity pairs | Same entity pairs |
|---|---:|---:|
| Immediate leaf | 899 | 235 |
| Immediate with another nested dispatch | 85 | 278 |
| Temporal leaf | 214 | 28 |
| Temporal with another nested dispatch | 80 | 417 |

The 2,153 target programs themselves split into 926 immediate leaves, 304 immediate
programs with nested dispatch, 459 temporal leaves and 464 temporal programs with
nested dispatch. These counts classify direct syntax only; recursive outcomes are the
executor's responsibility.

A read-only smoke walks every concrete installed event entry from explicit
`SymbolicAccumulatorState.unknown()` with a deliberately small 16-unit global
symbolic-work budget. It is a
runtime/invariant check, **not** a reachability or domain-coverage verdict:

| Smoke result | Count |
|---|---:|
| Concrete entries walked | 2,790 |
| Programs without a static source identity | 48 |
| Result paths | 4,641 |
| Synchronous / eventual / guard-aborted / blocked | 2,078 / 1,155 / 314 / 1,094 |
| Effect occurrences with concrete provenance | 7,911 |
| Guard decisions / nested dispatches | 2,187 / 2,782 |
| Temporal boundaries / same-entity caller replacements | 2,693 / 360 |
| Cross-entity temporal frontiers | 301 |
| Active-frame cycle frontiers | 200 |
| Unknown-entry non-exact mutation frontiers | 447 |
| Global-work-budget frontiers at the 16-unit smoke budget | 103 |

The other smoke blockers are eight unmodeled `kill` death dispatches, 28 missing
handlers, three targets without static identity and four possible `create` failures.
The smaller smoke budget keeps the all-entry acceptance test practical; the public
executor default remains 4,096 and focused tests cover per-event path splitting,
global recursive-work exhaustion and recursion-depth exhaustion.

## Proposed code boundary

Prefer a new sibling module, tentatively
`website/backend/map_geometry/stage_semantics.py`, instead of extending the 1,500-line
lexer/parser module with entity-resolution and graph-validity logic.

The new layer should consume already validated values:

- `BspFile` and a generic raw-entity identity projection;
- `MapEntityCatalog` from W3;
- `StaticStageModel` from W5a;
- the independently resolved W1 providers already retained by those models.

Do not make W5a parsing depend on BSP availability. Parsing and semantic mapping have
different failure boundaries and should remain independently testable.

Likely public concepts, with final names decided during implementation:

```python
class SemanticResolution(StrEnum):
    RESOLVED = "resolved"
    GROUP = "group"
    MISSING = "missing"
    AMBIGUOUS = "ambiguous"
    EXTERNAL = "external"
    OPAQUE = "opaque"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class EntityIdentityLink:
    namespace: str
    requested_value: str
    candidate_entity_indices: tuple[int, ...]
    resolution: SemanticResolution
    provenance: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StaticStageCoverage:
    status: str
    blockers: tuple[str, ...]
    resolved_domains: tuple[str, ...]
    unresolved_domains: tuple[str, ...]
```

These snippets describe required information, not an approved API. Do not commit the
names before engine-source research proves the namespaces and group semantics.

## Implementation plan

### Phase 0 - freeze takeoff and baseline

Status: complete.

1. Record the scope, branch base, W5a/W3 measured baseline and merge gates here.
2. Run documentation link/path checks and `git diff --check`.
3. Commit and push this document before production code begins.
4. Open a draft PR so review can challenge the contract early; keep it draft while
   semantic implementation and measurements are incomplete.

Exit gate: another agent can explain the W5a/W5b/W5c boundary and execute Phase 1
without relying on chat history.

### Phase 1 - verify engine identity and execution semantics

Status: in progress. Identity/action namespaces, installed accumulator operations,
ordered runner and the current-pass behavior of wait/reset/halt are source-verified.
Nested-event restoration and bounded cycle fixtures are implemented locally; death
dispatch remains pending.

Read current ET:Legacy primary source and pin exact source URLs/commit hashes for:

1. how `scriptName` is assigned from BSP keys, class defaults, custom entities and
   `script_multiplayer`/game-manager setup;
2. which comparison function and namespace each action uses: `trigger`, `setstate`,
   `alertentity`, `gotomarker`, `setautospawn`, objective status and main objective;
3. whether multiple concrete entities sharing one script name all receive the same
   block and how declaration-order selection works;
4. local `accum` versus `globalaccum` storage, mutation operations and every abort
   condition used by installed assets;
5. event action ordering, nested trigger dispatch, `wait`, `halt`, `resetscript` and
   recursion/cycle behaviour relevant to a static possibility graph;
6. engine-assigned identities absent from literal BSP fields;
7. any ET versus current ET:Legacy semantic difference that could affect the live
   server or historical map assets.

Convert each verified rule into a focused fixture before implementing the full mapper.
Where current ET:Legacy and the actual live build cannot be proven equivalent, retain
a versioned `unverified_live_build` blocker instead of choosing one behaviour.

Exit gate: every mapping namespace and control-flow rule used by code has a primary
source citation and a unit test that would fail under the most plausible wrong rule.

### Phase 2 - build a generic BSP identity index

Status: in progress. The generic engine-effective identity index, first/all lookup
fixtures and exact W3 typed joins are implemented locally. Semantic-effect publication
and the final coverage surface remain pending.

1. Project stable identity fields from every raw BSP entity, not only W3's typed
   subset. Preserve entity index, classname, all relevant exact names and raw-property
   provenance.
2. Normalize only with the engine-proven ASCII comparison rule. Retain original bytes
   or strings for publication.
3. Represent one-to-many script groups explicitly. Zero matches and conflicting
   namespaces remain distinct failure states.
4. Join the generic identity to W3 typed entities by BSP `entity_index`, never by a
   second string heuristic.
5. Keep external/custom entity provenance separate from BSP-lump provenance.

Exit gate: synthetic fixtures cover zero, one, legitimate many, conflicting many,
case behaviour, class-assigned names and external/unknown identities.

### Phase 3 - map semantic domains

Status: complete. Every current typed W5a effect has an action-specific static
projection and measured real-asset inventory. Entity-target effects publish the four
source/target dispositions independently. Objective-status effects publish numbered
descriptions while explicitly reporting that no engine key proves a world-entity
link; the empty candidate set is not mislabelled as a missing entity.

#### Objectives

1. Map `wm_objective_status` by its verified team/objective-number semantics to
   `.objdata` descriptions.
2. Build candidate links from descriptions to objective markers and measured volumes
   only through proven engine/entity keys.
3. Preserve multiple concurrently relevant objectives and per-team descriptions.
4. Keep all 42 installed `legacy_numeric` main-objective effects unapproved until the
   live-build compatibility path is independently verified.

#### Spawns

1. Resolve `setautospawn` through the engine's exact spawn-description lookup rule.
2. Return the complete candidate spawn set for a team; never select one point.
3. Preserve spawn flags, descriptions, script groups and missing player-specific
   `spawn_select` capability as separate facts.

#### Dynamic routes and collision entities

1. Map approved state/movement effects to concrete doors, movers, constructibles,
   destructibles and required helper markers using their action-specific namespace.
2. Preserve candidate transforms/states; do not claim a runtime transform.
3. Mark a route domain partial when a collision-relevant effect target is unresolved,
   external, unsupported or controlled by an opaque block.

Exit gate: every typed W5a effect either has a typed semantic projection or an explicit
machine-readable reason why it does not.

### Phase 4 - model guarded ordered possibilities

Status: in progress. Every eligible action is retained in source order as a typed
stage, accumulator, trigger, barrier or source-classified runtime-control instruction.
Single-event accumulator state, guard splitting, effect suppression and temporal
continuations are implemented locally. Static nested dispatch identity is implemented
and externally reviewed. Bounded nested execution, same-entity restoration, active
cycle detection and explicit temporal/concurrency frontiers are implemented locally
and await exact-head review; no map-level path reachability is published yet.

1. Represent per-entity accumulator and global-accumulator state symbolically.
2. Apply mutations in script action order.
3. Split possible execution on verified abort guards; do not erase the rejected path.
4. Preserve nested trigger ordering and detect cycles without pretending they execute
   forever or exactly once.
5. Treat unsupported control actions that can guard a semantic effect as a blocker for
   that path/map domain.
6. Keep `wait` as ordering/delay provenance only unless static timing semantics are
   proven necessary and representable. W5b still does not create historical time.

Exit gate: adversarial fixtures prove that a guard can suppress an otherwise parsed
effect, local accumulators do not leak across entities, global accumulators do share
state where specified, and cycles fail closed.

### Phase 5 - static-graph gate and real-asset evidence

Status: pending.

Define the final per-map verdict only after Phases 1-4 reveal the actual failure modes.
At minimum report separate domain coverage for objectives, spawns and dynamic routes,
plus an overall defensible-static-graph verdict. The overall gate should require:

1. independently resolved BSP, script and objdata providers;
2. valid W3 and W5a models;
3. no selected opaque script block affecting a published domain;
4. engine-defensible identity resolution for every effect needed by that domain;
5. proven accumulator/order semantics for every path that can change that domain;
6. no unresolved trigger edge on a required semantic path;
7. no silent dependency on unverified custom/live entities;
8. complete publication of all remaining candidate sets and blockers.

Add an opt-in real-asset analyzer/test that publishes:

- map count by overall and per-domain verdict;
- identity links by resolution reason and entity class;
- all unresolved script blocks and effect targets;
- objective description/marker/volume linkage denominators;
- spawn-effect to spawn-set denominators;
- dynamic-route effect/entity denominators;
- accumulator/guard paths supported versus blocked;
- all 11 W5a missing trigger calls with their final semantic relevance;
- a deterministic, content-sensitive manifest hash.

Never set a target map count before seeing the evidence. Twenty parsed maps is the
input denominator, not a promise that all twenty graphs are defensible.

Exit gate: the evidence report can be regenerated from exact hashed assets, the
manifest is deterministic, and no partial/unknown map is counted as defensible.

### Phase 6 - review closure and merge

Status: pending.

1. Run focused unit tests, the complete map-geometry suite, opt-in real-asset tests,
   Ruff, `git diff --check` and the full repository suite.
2. Publish exact measured proof in the PR body and final research report.
3. Address every actionable review comment and resolve every thread only after its
   fix/evidence is pushed.
4. After every push or review activity, wait at least five minutes for asynchronous
   reviewers, then refresh checks, reviews, comments and unresolved threads.
5. Immediately before merge, perform a separate final refresh.
6. Merge only with green CI, zero unresolved threads and measured proof on the exact
   reviewed head. Retain the remote branch unless the owner says otherwise.

## Trade-off register

### Strict identity versus higher apparent coverage

Decision: exact engine-compatible identity only.

Cost: more maps/domains may remain partial.

Reason: one false objective/door mapping corrupts every later historical state and can
make a plausible but wrong metric. Unknown coverage is measurable and recoverable;
fabricated state is not.

### Generic BSP identity layer versus expanding only W3 typed classes

Provisional decision: add a small generic identity projection and link W3 entities by
entity index.

Cost: another model and publication surface.

Reason: selected script blocks include relay, checkpoint, flag, manager, visual and
helper entities outside W3's tactical geometry types. Expanding W3 into a full script
interpreter would blur its physical-geometry boundary.

### Legitimate groups versus forcing one entity

Decision: preserve one-to-many candidate groups when the engine applies one script
identity or spawn description to several concrete entities.

Cost: consumers must handle sets.

Reason: selecting one point/entity is not more precise; it is false precision.

### Symbolic possibility graph versus a full ET script VM

Decision: model only execution semantics required to determine legal stage effects,
with unsupported paths explicit.

Cost: some maps may remain blocked by actions outside the approved semantic subset.

Reason: a full game-script VM would need runtime entity state, engine callbacks and
timing that static assets do not contain. W5b needs defensible possibilities, not an
offline game server.

### Domain-level partial coverage versus all-or-nothing maps

Decision: publish objective, spawn and route coverage separately, plus a strict
overall verdict.

Cost: a more detailed contract and report.

Reason: an unresolved decorative mover should not erase a proven objective catalog,
but a partial map must not be presented as a complete static stage graph.

### Current ET:Legacy source versus unverified live-build behaviour

Decision: current ET:Legacy is the implementation reference only for semantics proven
compatible; known or plausible version drift is explicit provenance/blocker.

Cost: a few semantics may require later live-build verification.

Reason: W5a already found installed numeric main-objective calls whose behaviour is not
safe to infer from the current target-name path. Version labels do not create parity.

### BSP entity lump versus effective virtual-filesystem entity source

Decision: index optional `.ent` providers and apply the engine's override-before-BSP
rule; reject conflicting provider bytes without verified live VFS precedence.

Cost: one additional optional asset kind and a deliberate W3 join blocker when an
override is present.

Reason: an `.ent` file replaces the full entity dictionary consumed by the game. A
perfect join against the superseded BSP lump would be deterministic and wrong.

### Early draft PR versus local-only implementation

Decision: open a draft PR after this takeoff commit.

Cost: reviewers may comment before code exists.

Reason: identity semantics and acceptance boundaries are cheaper to correct before
they are embedded across code and fixtures. Draft status must not be treated as merge
readiness.

## Risk register

| Risk | Required handling |
|---|---|
| `game_manager` and similar identities may be assigned outside literal BSP keys | Trace class spawn/load path; do not classify from a read query alone |
| Different actions may use different entity namespaces | Verify every action callback separately; never reuse one generic lookup by convenience |
| Multiple concrete entities share one script name | Represent an engine-selected group; do not mark ambiguous unless engine semantics are ambiguous |
| W3 omits logical/helper entity classes by design | Use generic BSP identity projection, then join typed W3 entities by entity index |
| Accumulator aborts remove parsed effects from a legal path | Symbolic ordered control flow is required before publishing the path |
| Nested trigger cycles and waits complicate order | Detect cycles, preserve order/provenance and fail closed where execution cannot be bounded |
| 11 trigger calls have no internal W5a handler | Check BSP/custom entity paths and semantic relevance; missing-in-file is not impossible-at-runtime |
| 42 main-objective effects are legacy numeric | Keep unapproved until actual build semantics are proven |
| Installed maps may depend on custom entity sources or pak precedence | Preserve W1 provenance and publish external/unverified dependencies |
| `maps/<map>.ent` can replace the complete BSP entity lump | Index PK3 and loose overrides; reject byte conflicts and require W3/identity source equality |
| Static graph is mistaken for historical state | Type/name outputs as static/candidate and keep W5c in a separate module/PR |
| Review fixes change denominators | Re-run exact real assets and update this document/report on every semantic change |

## Verification matrix

Expected commands, refined as files are added:

```bash
venv/bin/python -m pytest tests/unit/test_map_geometry_stage_semantics.py -q
venv/bin/python -m pytest tests/unit/test_map_geometry_stage.py \
  tests/unit/test_map_entity_extraction.py \
  tests/integration/test_map_geometry_real_assets.py -q
SLOMIX_RUN_REAL_ASSET_TESTS=1 \
  venv/bin/python -m pytest tests/integration/test_map_geometry_real_assets.py -q
venv/bin/python -m ruff check website/backend/map_geometry tests/unit \
  tests/integration/test_map_geometry_real_assets.py
git diff --check origin/main...HEAD
venv/bin/python -m pytest tests/ -q
```

If the worktree has no local `venv`, use the repository's existing absolute venv path
without changing dependency manifests. Record the exact interpreter version in the
final evidence.

## Merge gate

All conditions are mandatory:

1. every required CI check is green on the exact head;
2. no unresolved review thread remains;
3. the PR contains regenerated real-asset proof, not only green tests;
4. all semantic claims cite the checked engine source/path;
5. the five-minute asynchronous-review quiet period has passed after the last activity;
6. a final fresh review/comment/check/thread query finds nothing new;
7. no owner-gated operation was performed.

Owner-gated and out of scope here: production DB writes, deploy/restart, Lua or Puran
changes, Python runtime replacement, force-push/history deletion and secret rotation.

## Checklist

- [x] Read the complete spider-web specification.
- [x] Read the complete W5a implementation/evidence report.
- [x] Create a clean W5b branch from current `origin/main`.
- [x] Record exploratory W3/W5a/raw-BSP takeoff denominators.
- [x] Freeze W5b scope, boundaries, trade-offs and merge gate in this document.
- [x] Commit and push the docs-only takeoff.
- [x] Open a draft PR.
- [ ] Complete Phase 1 execution/control-flow contract fixtures; accumulator source
  projection and single-event barrier fixtures are complete.
- [ ] Complete Phase 2 publication; generic identity index and exact W3 typed joins
  are complete.
- [x] Complete Phase 3 objective/spawn/route semantic mappings.
- [x] Resolve nested trigger handlers and concrete static target groups without
  executing them.
- [x] Complete review closure for the bounded nested executor,
  same-entity restoration and temporal/concurrency frontiers.
- [ ] Complete Phase 4 accumulator and ordered-possibility modelling.
- [ ] Complete Phase 5 static coverage analyzer and evidence report.
- [ ] Complete all verification and review closure gates.
- [ ] Merge only after the exact-head final refresh.

## Decision log

### 2026-08-10 - split W5 at evidence boundaries remains authoritative

W5a parses static assets, W5b maps static semantics, and W5c audits event completeness
then replays observed historical transitions. No implementation convenience may merge
these evidence levels.

### 2026-08-10 - start with documentation, not code

The first branch commit is docs-only. This gives reviewers and a replacement agent a
stable contract before implementation choices make the scope harder to change.

### 2026-08-10 - raw BSP identity must be considered

The takeoff probe proved that W3's typed catalog is intentionally narrower than the
set of script-selected entities. W5b will not assume that a script block absent from
W3 is absent at runtime.

### 2026-08-10 - W3 joins use entity indices, never a second name match

The W3 extractor already preserves the original BSP entity index. W5b uses that key
and validates source plus classname consistency. This makes source drift or catalog
corruption a visible error instead of attempting to recover with a plausible string
match.

### 2026-08-10 - project installed accumulator syntax before symbolic execution

The source program is first converted into typed entity/global mutations, abort guards
and conditional triggers. Unsupported or malformed instructions are data, not ignored
text. Ordered path execution remains a separate Phase 4 responsibility so a successful
parse cannot be mistaken for a proven reachable effect.

### 2026-08-10 - effect source identity is part of every semantic projection

A parsed effect is attached to its source script block, and actions such as
`gotomarker` mutate that concrete source entity. Every projection therefore carries
the engine-effective all-match source lookup. The measured 97 effects from blocks with
no static BSP identity remain candidates behind an explicit runtime-completeness gap,
not executable static transitions.

### 2026-08-10 - autospawn publishes candidates, not a selected spawn point

The engine first selects a major-spawn marker by message, then chooses among active,
owned player spawns using runtime proximity rules. W5b retains the first static marker
plus every same-team W3 spawn candidate and labels final selection runtime-unverified.
Choosing a nearest static spawn here would conflate map possibility with historical
state.

### 2026-08-10 - entity identity follows `.ent` override-before-BSP load order

The engine write/load path disproved the earlier implicit assumption that BSP entities
are always the effective runtime identity source. W1 now inventories PK3 and loose
`.ent` providers. Different candidate bytes are ambiguous, and a selected override is
not allowed to join a W3 catalog extracted from the superseded BSP entity lump.

### 2026-08-10 - preserve duplicate entity fields in source order

ET generic-field assignment is case-insensitive and last-assignment-wins in source
order, while exact `G_SpawnString` lookup returns the first exact occurrence. A plain
Python dictionary erased the evidence needed to reproduce both behaviours. Parsed
entities now retain every ordered key/value pair while remaining mapping-compatible;
generic aliases use the final source assignment and `team_WOLF_objective` uses the
first exact lowercase `description`, including a present empty value. `gotomarker`
option parsing also consumes the argument after `relative`, so a target literally
named `relative` is not reinterpreted as a second option.

### 2026-08-10 - objective relationships require a proven engine key

`objflags` is not an objective-description-to-volume relationship. The checked mapper
documentation defines it for command-map icon pulsing/type, and current ET:Legacy
parses and stores the value without consuming it as a physical objective join. A
`team_WOLF_objective` is a spawn/objective-region marker used by paths such as
`setautospawn`, but this does not prove a relationship to a numbered `.objdata`
description or a `trigger_objective_info` volume. Those links therefore remain
explicitly unproven instead of being recovered through wording, class or proximity.

### 2026-08-10 - legacy numeric main-objective calls remain blocked

The original Enemy Territory source at commit
[`40342a9e`](https://github.com/id-Software/Enemy-Territory/blob/40342a9e3690cb5b627a433d4d5cbf30e3c57698/src/game/g_script_actions.c#L2693-L2730)
contains the numeric `G_ScriptAction_SetMainObjective` implementation only inside a
commented-out body. Current ET:Legacy implements a target-field lookup, while all 42
installed calls use numeric arguments. This verifies neither a numeric runtime effect
nor a conversion to target names, so all 42 stay `legacy_numeric` and unapproved.

### 2026-08-10 - source and target failures remain independent

A fresh run of the real projector corrected an erroneous intermediate handoff claim
that all 97 missing sources belonged to `setstate`. The verified split is 96
`setstate` plus one `alertentity`; the latter is `sw_goldrush_te` block
`defense2_toi`, whose `rubble3` target resolves. Across all 1,864 entity-target
effects, the machine-readable disposition matrix is 1,709 static source+target, 94
neither, 58 source-only and three target-only. This distinction matters because a
missing source and a missing target are different runtime-completeness questions and
must not be collapsed into one generic unresolved result.

### 2026-08-11 - project every action before executing any path

Phase 4 first creates a lossless ordered program and validates that its instruction
count equals the parsed action count. Accumulators, stage effects, plain triggers and
the three source-verified barriers receive typed instructions. Every other runtime
action is retained with `control_semantics_not_classified`; the executor may not skip
it merely because its name appears cosmetic. This deliberately exposes 3,413 blockers
now rather than producing high but indefensible path coverage.

A focused drift test removed a typed `setstate` effect while leaving its parsed action
in place. The first implementation silently reclassified that action as an unknown
runtime blocker. The projector now consumes a single canonical stage-effect command
set shared with graph compilation and raises if any such action lacks its typed effect;
extra effects and trigger edges were already rejected after each event projection.

Review also exposed that requiring an already-linked W3 catalog made the ordered
program unavailable when a valid `.ent` override supplied the runtime identity list.
The context now separates source-valid identity lookups from source-proven BSP index
links: override projections proceed, but every W3 candidate remains empty and typed as
unproven rather than borrowing an index from the replaced BSP entity lump.

### 2026-08-11 - current-event control and runtime mutation are separate axes

The 38 residual runtime command families were checked against their registered
ET:Legacy callbacks. Thirty-two always continue the current event; six have temporal,
lifecycle, nested-event, spawn or script-context consequences. An immediate return is
not evidence that an action has no game-state effect, so every action stays in the
ordered program even when it is not a control blocker. Conversely, a temporal
`qfalse` is not a permanent path abort: the engine may resume the same instruction on
a later frame. The future walker must publish both facts instead of collapsing them
into one executable/blocked flag.

### 2026-08-11 - classify callback control from concrete arguments

Command names alone over-blocked all nine installed `set` actions even though none
contains the `classname` key that can reach `G_CallSpawn`. Classification now consumes
the parsed action: the installed `origin` and `contents`/`clipmask` forms continue the
current event, as do supported-but-unobserved `scriptName` and `classname_nospawn`
forms, while an actual case-insensitive `classname` key remains fail-closed. `remove`
retains its deferred lifecycle effect but no longer publishes a current-pass blocker
because the callback returns `qtrue` before the next-frame deletion. The real corpus
moves exactly nine instructions from the spawn-context blocker to immediate continue;
no installed semantic action is erased.

### 2026-08-11 - require explicit entry state and split runtime-dependent waits

A one-event interpreter cannot assume that an arbitrary event begins at level
initialization. Its API therefore requires an explicit accumulator state. This costs a
little call-site verbosity, but prevents every later trigger event from silently
starting with zero local and global buffers. Entity-scoped values are keyed by the
concrete selected source index; global values remain shared in the propagated state.

All six supported abort predicates refine a signed 32-bit symbolic domain and retain
only satisfiable branches. Non-exact arithmetic and unverified overflow stop at an
explicit line-numbered frontier. `wait` publishes immediate and delayed continuations
because the pinned callback returns immediately during sudden death, while
`resetscript` and `halt` return false on their first pass and only continue later.
Nested trigger/death dispatch is deliberately still a blocker rather than an assumed
no-op; the next increment must model caller restoration and cycles before any corpus
reachability denominator is meaningful.

### 2026-08-11 - review hardening keeps undefined sign-bit shifts blocked

Exact-head review correctly found that directly constructed typed instructions could
bypass the parser's operand validation and raise inside the public walker. Mutations,
abort guards and conditional guards now independently validate their runtime inputs and
return line-numbered blockers; domain refinement returns no candidate for an invalid
operand instead of raising.

The suggested alternative of normalizing bit index 31 was rejected. Both checked
ET:Legacy accumulator callbacks evaluate bit operations as signed `1 << Q_atoi(token)`.
W5b cannot turn that undefined C sign-bit shift into a portable two's-complement rule.
The shared approved maximum therefore remains bit 30, with synthetic index-31 fixtures
proving both the projector and walker fail closed. The same review added a 4,096-path
default budget and an explicit smaller-budget regression, preventing repeated waits or
movement alternatives from growing the public analysis without bound.

### 2026-08-11 - resolve nested dispatch before executing nested programs

Nested trigger identity is now a separate deterministic projection. This makes the
engine's first-handler lookup, wildcard behavior, concrete `self` identity and
all-target script-name groups testable without introducing recursive execution at the
same time. The real corpus contains 669 plain and 289 conditional source-target pairs
that return to the same concrete entity, so treating every nested dispatch as an
ordinary call would be a material semantic error rather than a rare edge case.

Execution remains a later increment. A synchronously completing same-entity callee can
restore the caller, while a temporal replacement discards that caller. A temporal
different-entity callee can coexist with the continuing caller and mutate shared
global state later. The first executor version must preserve this distinction and
publish a bounded cycle or concurrency frontier whenever it cannot prove an ordering.

### 2026-08-11 - stop unsafe callees at the first temporal boundary

The nested executor reuses the single-event walker in ordered segments instead of
copying accumulator/effect logic into a second interpreter. Same-entity callees resume
their caller only after a fully synchronous result; a synchronously triggered
accumulator abort qualifies because the engine callback returns `qtrue`. A final
same-entity callee that pauses replaces the caller and suppresses its suffix.

Different-entity and non-final shared-target callees use a stricter mode: their delayed
branch stops at the first temporal boundary before any later action is evaluated. The
frontier therefore contains only the immediate prefix, not effects or global mutations
from an invented future ordering. Active concrete event frames close recursive cycles,
and path plus depth budgets bound acyclic expansion. This deliberately leaves temporal
scheduling explicit until real domain relevance proves that a more complex interleaving
model is needed.

### 2026-08-11 - make the path budget global recursive work

Exact-head review found that bounding each recursive frame's returned paths did not
bound aggregate work: every admitted parent path could independently invoke a child
that again produced up to `max_paths` paths. The executor now shares one mutable budget
across the entire root walk. Every non-empty ordered-program segment consumes one unit
per symbolic result, the next segment receives only the remaining allowance, and the
first exhaustion stops further recursion with exactly one
`symbolic_path_budget_exhausted` frontier.

An empty caller suffix is completion, not work. The first shared-budget draft charged
that empty return and could reject a root trigger plus synchronous leaf callee even
when two units admitted both real segments. A regression now freezes the correct
two-unit completion as well as exhaustion before a third nested segment. The 16-unit
real-asset smoke additionally asserts no concrete entry publishes more than one budget
frontier. This budget is a deterministic analyzer safety boundary, not an engine timing
model or a claim that exhausted paths are unreachable.

## Current handoff state

Current step: close review and measured evidence for the completed frontier
classification before designing a scheduler. Guard splitting, explicit local/global
accumulator state, effect suppression, concrete nested target selection, synchronous
caller restoration, final same-entity temporal replacement, active-frame cycle
detection, first-boundary temporal/concurrency frontiers and the shared work budget have
completed exact-head implementation review. Phase 2's final public coverage surface
remains intentionally deferred until the evidence PR is merged and the required
suspended-continuation scheduler is implemented separately.

Verify the target/write path for all 13 `kill` actions and model death dispatch only
from that evidence. If cross-entity temporal frontiers block required domains
materially, add an explicit suspended-continuation scheduler; do not merge eventual
callee state into an immediate caller by convenience. Then define the Phase 5
per-domain static-graph gate and deterministic evidence manifest.

Known blockers: none for read-only research and local implementation. Any required
live-build inspection that changes or restarts a service becomes owner-gated; retain
the affected semantic result as unverified and continue with independent domains.

### Post-#633 frontier-classification takeoff

Follow-up branch: `agent/map-geometry-w5b-frontier-classification`

Follow-up base: `origin/main` at
`e649b0493a1ca0ed9cb3b2a2935ebcd78f494202`

Current substantive follow-up head:
`04e65133` (`fix(map-geometry): close frontier review gaps`). The
documentation-only verification commit that records this pointer cannot contain its
own hash; query PR #638 before treating it as the final reviewed head.

The next increment closes two evidence gaps before Phase 5: source-verified `kill`
dispatch and per-domain classification of every remaining frontier. It still does not
publish a runtime state, metric or rating. A frontier classification means only that
an unresolved continuation **may** hide an objective, spawn or dynamic-route effect;
it is not evidence that the effect occurred.

#### Installed `kill` inventory

A fresh read-only projection over all installed indexed assets found exactly 13
actions. Every target lookup is a unique ET-style `targetname` lookup:

| Map | Source event and line | Target | Concrete runtime class | Static death handler |
|---|---|---|---|---|
| `bremen_b3` | `truck_construct spawn`, 1066 | `truck` | entity 135 `script_mover`, spawnflags 58 | `truck death` |
| `bremen_b3` | `truck trigger deathcheck`, 2003 | `truck_construct` | entity 123 `func_constructible`, spawnflags 10 | none |
| `etl_beach` | `world_clip trigger load_mg42_1`, 659-660 | `mg42_1`, `mg42_1m` | entity 150 `misc_mg42`; entity 481 `func_static` | none |
| `etl_beach` | `world_clip trigger load_mg42_2`, 668-669 | `mg42_2`, `mg42_2m` | entity 195 `misc_mg42`; entity 482 `func_static` | none |
| `etl_beach` | `world_clip trigger load_mg42_3`, 677-678 | `mg42_3`, `mg42_3m` | entity 149 `misc_mg42`; entity 448 `func_static` | none |
| `etl_beach` | `world_clip trigger load_mg42_4`, 686-687 | `mg42_4`, `mg42_4m` | entity 237 `misc_mg42`; entity 480 `func_static` | none |
| `sw_goldrush_te` | `tank trigger deathcheck`, 1129 | `tank_construct` | entity 421 `func_constructible`, spawnflags 553 | none |
| `sw_goldrush_te` | `tank_construct spawn`, 1229 | `tank` | entity 790 `script_mover`, spawnflags 190 | `tank death` |
| `sw_goldrush_te` | `truck trigger deathcheck`, 2405 | `truck_construct` | entity 1 `func_constructible`, spawnflags 9 | none |

Pinned ET:Legacy source narrows the control contract further:

- `G_ScriptAction_Kill` parses one target and calls `G_KillEnts` before returning
  `qtrue`;
- `G_KillEnts` dispatches through `die` only for an eligible `script_mover` or
  `ET_CONSTRUCTIBLE`; other targets are unlinked and scheduled for removal;
- `script_mover_die` synchronously emits the target's `death ""` script event;
- both installed target movers are created without the trigger-spawn bit, so their
  initial `die = script_mover_die` assignment is source-supported;
- the two installed mover death handlers contain only one entity-local accumulator
  bit-set each and no temporal or stage effect;
- the three targeted constructible script blocks expose no `death` or `destroyed`
  handler, while the eight MG42/static targets cannot reach a script death callback
  through `G_KillEnts`.

The implementation must therefore replace the generic death-dispatch blocker with a
typed target lookup. The 11 non-handled targets continue synchronously. The two mover
targets retain both statically legal lifecycle alternatives: dispatch the proven
`death ""` handler when `die` is installed, or continue without a handler when prior
runtime lifecycle state may already have cleared it. W5b does not know that history.
No synthetic death event may be attached to `misc_mg42`, `func_static` or a
constructible merely because a same-named script block exists.

The suffix probe also found no direct typed stage effect after a `kill`. Several
constructible deathcheck suffixes do contain nested triggers, so relevance must be
computed from the actual continuation graph rather than from the current instruction
alone. This is the first acceptance case for the frontier classifier.

#### Frontier-classification contract

The classifier will report a deterministic set drawn from `objective`, `spawn` and
`dynamic_route` for every blocked path. It must inspect only continuations that the
current executor could not order:

1. caller suffix after an unresolved dispatch or concurrent target;
2. target suffix after the first temporal boundary;
3. reachable nested programs until another explicit frontier;
4. the selected typed W3 references of each stage effect, not its command spelling.

`ObjectiveStatusEffectProjection` and `MainObjectiveEffectProjection` belong to the
objective domain. `AutoSpawnEffectProjection` belongs to spawn. Collision-relevant
`EntityTargetEffectProjection` candidates and source/destination collision references
from `GotoMarkerEffectProjection` belong to dynamic route. Global round winner/end
effects are published but are not silently relabelled as one of these three domains.
Missing identity or an opaque program remains `unknown_domain_relevance` when the
analyzer cannot enumerate the continuation; it must not be reported as irrelevant.

First measure the real corpus with this conservative contract. Add a suspended-
continuation scheduler only if cross-entity temporal frontiers materially hide a
required domain. If their relevance is empty, the scheduler adds state-space and
ordering assumptions without improving the Phase 5 verdict and remains deferred.

#### Follow-up acceptance evidence

Before this increment can merge it must publish, for the exact installed asset hashes:

- all 13 `kill` actions by target class and dispatch disposition;
- the count of death-handler branches and their downstream domains;
- every existing blocker reason split by objective/spawn/dynamic-route/unknown
  relevance;
- the maps whose per-domain verdict changes after source-verified kill handling;
- the deterministic manifest hash and exact test head.

The PR starts as documentation-only. Code, corpus evidence and review corrections stay
on this branch, and this section is updated with every substantive commit.

The deterministic installed-asset manifest is the SHA-256 of canonical JSON for
`Pk3GeometryIndex.manifest(index.map_names)["maps"]`, using sorted keys, compact
separators and ASCII output. This deliberately excludes the machine-specific absolute
`etmain_dir`, while retaining every selected/provider path, member index, size, CRC32
and content SHA-256. For the exact 20-map installed corpus on substantive test head
`04e65133`, the manifest hash is:

`86ddd0ec23b3c6120136195af34aa633ad249eb358ea0fb6cd6e490dd81b220d`

The source-verified `kill` change removes a generic frontier that previously stopped
the caller before its suffix. A per-action continuation probe on the same head found
the following per-map domain deltas:

| Map | Kill actions | Dynamic-route verdict delta | Objective delta | Spawn delta |
|---|---:|---|---|---|
| `bremen_b3` | 2 | blocked -> reachable for 2/2 suffixes | unchanged, none | unchanged, none |
| `etl_beach` | 8 | blocked -> reachable for 4/8 suffixes | unchanged, none | unchanged, none |
| `sw_goldrush_te` | 3 | blocked -> reachable for 2/3 suffixes | unchanged, none | unchanged, none |

No other installed map contains a `kill`, so every other map is unchanged. This table
is a delta in the static domain evidence that feeds Phase 5, not a claim that the
transition occurred in a played round. Phase 5's final defensible/partial/unknown map
verdict does not exist yet and therefore is not backfilled by inference here. The four
optional mover death-handler branches themselves add no objective, spawn or route
domain; they contain only the measured entity-local accumulator mutation.

#### Typed-kill implementation checkpoint

The first follow-up implementation replaces all 13 generic runtime instructions with
`KillInstruction`, an exact `targetname` lookup and per-target source disposition. The
20-map corpus measures:

| Result | Count |
|---|---:|
| Direct removal with no script event (`misc_mg42`, `func_static`) | 8 |
| Constructible with no handled `death`/reachable `destroyed` event | 3 |
| Script mover with an optional handled `death` event | 2 |
| Generic `may_dispatch_death_event` instructions/blockers | 0 |

At the existing 16-unit per-entry smoke budget, the two mover actions produce four
reachable death-dispatch branches across all concrete event entries. The aggregate
result changes from 4,641 to 4,645 paths: synchronous completions 2,078 to 2,084,
eventual completions 1,155 to 1,157 and blocked paths 1,094 to 1,090. The old eight
generic death blockers disappear. Four death-handler branches reach their entity-local
`bitset` with unknown entry state and therefore move the existing
`non_exact_accumulator_mutation` count from 447 to 451. W5b does not replace that
unknown with zero; frontier relevance must classify the hidden continuation next.

Focused verification at this checkpoint:

- 93/93 ordered-possibility unit tests passed on Python 3.13;
- the ordered-program and bounded-executor real-asset acceptance tests passed over all
  installed indexed assets;
- Ruff, formatter check and `git diff --check` passed for the touched files.

This checkpoint deliberately leaves constructibles with a matching runtime
`death`/`destroyed final|stage2|stage3` handler blocked. Their selected event depends on
runtime destruction-stage fields, unlike the single `script_mover_die -> death ""`
path. Installed targets have no such handler, so guessing that state would add
complexity without changing current corpus coverage.

#### Frontier-classification checkpoint and scheduler decision

The classifier records ordered continuation provenance when blocker line and entity
index are available, a deterministic subset of `objective`, `spawn` and
`dynamic_route`, an explicit `unknown_domain_relevance` flag and machine-readable
unknown reasons. Missing blocker provenance produces an empty continuation tuple and
the named `frontier_provenance_missing` reason. The classifier walks only statically
reachable suffixes and nested programs. It treats a known missing handler as having no
target effect while retaining the caller suffix; missing target identity, opaque script
identity, budget exhaustion and unresolved route identity stay unknown rather than
being reported as irrelevant.

The 1,090 current blocked paths split as follows at the 16-unit smoke budget:

| Hidden-domain set | Paths |
|---|---:|
| none | 408 |
| dynamic route only | 300 |
| objective only | 7 |
| objective + spawn | 2 |
| dynamic route + objective | 226 |
| dynamic route + spawn | 18 |
| all three | 129 |

Across overlapping sets, 673 blockers hide dynamic-route semantics, 364 hide objective
semantics and 149 hide spawn semantics. Of all blockers, 421 have complete domain
classification and 669 retain at least one named unknown reason. The dominant unknowns
are non-W3-linked runtime motion/lifecycle sources (`faceangles`, `stoprotation`,
`remove`, `attachtotag`, `setrotation`, `setspeed`) and 130 missing typed effect targets;
these are coverage facts, not permission to relabel the action as irrelevant.

The scheduler decision is now evidence-driven. Among the 301 cross-entity temporal
frontiers:

| Hidden-domain set | Paths |
|---|---:|
| none | 59 |
| dynamic route only | 170 |
| objective only | 2 |
| dynamic route + objective | 47 |
| dynamic route + spawn | 18 |
| all three | 5 |

Only 59/301 have no currently identified required domain; 242/301 hide at least one.
214/301 are completely classified and 87 retain named identity/route uncertainty.
Therefore a bounded suspended-continuation scheduler is required before Phase 5. It
must model ordering alternatives explicitly; it may not merge delayed callee state into
the immediate caller or erase the current concurrency frontier merely to raise
coverage.

The scheduler should be scoped to cross-entity and shared-target temporal continuations
that the classifier proves relevant. Empty, fully classified frontiers do not need
state-space expansion. Unknown relevance remains fail-closed and is not a scheduling
target until its identity/semantic reason is resolved.

Exact-head self-review corrected an initial undercount before review closure. A
temporal frontier hides not only the suffix after `followspline`/`faceangles`, but also
completion of that suspended route action itself. A work-budget frontier similarly
points at the next unexecuted instruction, so relevance begins at that instruction,
not after it. Regression tests freeze both boundaries. The corrected counts above
replace the earlier exploratory 238-domain/63-empty temporal split.

Verification on Python 3.13.14 at this checkpoint:

- 99/99 focused ordered-possibility unit tests passed, including adversarial temporal,
  missing-handler, missing-identity and non-exact-state cases;
- 274/274 expanded W1-W5b unit tests passed;
- all 15 opt-in real-asset tests passed over the exact 20-map installed corpus in
  202.06 seconds;
- the complete repository suite passed 4,329 tests with 93 expected skips in 30.38
  seconds;
- Ruff, formatter check and `git diff --check` passed for every touched Python file.

CodeRabbit's first PR #638 review exposed two defensive gaps and three test/evidence
gaps. Substantive correction head `04e65133` now rejects a kill death-handler projection
whose target entity is not selected by that handler, retains the named
`frontier_continuation_entity_not_selected` unknown, treats a resolved nested dispatch
without a handler as intrinsically unknown, and indexes instruction lines once per
ordered-program index. Focused executor coverage is 105/105 and the expanded W1-W5b
unit selection is 277/277. Documentation head `2aef9c40` then passed all 16 opt-in
real-asset tests over the exact manifest above in 202.08 seconds. The complete repository
suite passed 4,335 tests with 94 expected environment/fixture-gated skips in 53.03
seconds; Ruff and `git diff --check` were also clean. This paragraph is a
documentation-only record of those exact heads and cannot contain the hash of its own
commit.

### Adjacent live-test handoff received 2026-08-11

Fable left a read-only live-test report in
`docs/research/FINDINGS_FOR_CODEX_2026-08-11.md` in the main worktree. That file was
still untracked when reviewed and is therefore not copied into or claimed by this PR.
Its two actionable proximity findings belong after the current W5b checkpoint:

- the stats SSH monitor suppresses parent-round ingestion from 02:00 through 10:59
  Europe/Paris, while proximity ingestion continues every two minutes and the relinker
  declares orphans permanent after six hours; the constants and early-return mismatch
  are present in the current source and require a separate measured relinker-policy
  change;
- a measured forced-map-change case has exact proximity/stats start and end timestamps
  but disagrees on `round_number`, so future relinker work must evaluate an exact-time
  identity path instead of requiring the engine round number unconditionally.

The report's `VEHICLE_PROGRESS` observation is not a missing parser feature in the
current repository: the Lua writer, parser, database import, relinker fanout and web
serving paths already contain explicit vehicle-progress support. The live/repository
hash drift still needs deployment provenance work, but it does not block or alter W5b
stage-script execution. The report's bot-round and trade-window observations are owned
by Fable and must not be folded into this branch.

Current local verification (Python 3.13.14): the expanded 277-test W1/map-geometry
unit suite passed without coverage tracing. The focused single-event/resolver/executor
module contributes 83 passing tests. The expanded resolver-shape acceptance passed in
57.25 seconds; after the final caller-replacement correction, the every-entry bounded
executor smoke passed in 25.53 seconds with the shared global work budget. All 15
current opt-in real-asset tests then passed together in 220.75 seconds without
coverage tracing. On the reviewed resolver head, all 14 then-existing opt-in tests had
passed in 193.48 seconds. The current acceptance proves no `.ent` override exists
for any of the 20 indexed BSP maps, includes
all 2,929 typed effect projections and the blocker inventory above, and rechecks W1-W5a,
patch collision and trace fail-closed baselines. An initial full-asset run exposed two
30-second test timeouts because the effective-source helper reparsed an already loaded
BSP; the helper now accepts that exact indexed BSP, validates its source and reuses it.
The preceding fully timed run recorded its two largest corpus checks at 47.68 and
47.46 seconds under repo-wide coverage tracing. Earlier direct runs without tracing
measured materially less time. The opt-in
real-asset module now has a measured 90-second hang guard; this is acceptance-test
headroom, not a production performance claim or SLO change.

The post-ready review correction for `followspline` was checked against
ET:Legacy `G_ScriptAction_FollowSpline` at pinned engine commit
`732518efb1c479dcd29b13361f30a2e92df1cf2a`. The engine consumes direction,
target name and speed first; `accum` and `globalaccum` directions additionally
consume a buffer index, while `length` and `roll` consume one and two option values.
The corrected sequential scan therefore cannot mistake a spline target or option
value named `wait` for the actual `wait` option. Local Python 3.13.14 verification
passed 87/87 focused executor units and 281/281 expanded W1/map-geometry units. The
exact every-entry executor acceptance passed in 26.60 seconds with all published
counts unchanged, and all 15 opt-in real-asset tests passed together in 205.06
seconds. The CI-equivalent dependency set then passed the complete local test suite:
4,317 passed and 93 expected environment/fixture-gated tests skipped in 35.84
seconds; the separately enabled real-asset suite covers its 15 default skips.
Production-path Ruff and `git diff --check` also passed. On exact substantive head
`abb2ba94`, all 13 GitHub check runs plus the CodeRabbit status passed, GitHub Codex
reported no new issue, all 17 historical review threads were resolved, and the
five-minute quiet period plus separate final refresh found no new activity. Local,
remote and PR heads matched, and GitHub reported the PR clean and mergeable. This
paragraph is the documentation-only closure record described at the top of the file;
the PR remains authoritative for the status of this record's own commit.
The duplicate-field correction was followed by a direct scan of all 20 indexed maps;
none contains a `team_WOLF_objective` whose first exact lowercase `description` is
empty, so the synthetic empty-value compatibility fix does not alter the measured
real-asset baseline.
Ruff and `git diff --check` passed. The full repository suite remains required before
merge.

The bounded nested-executor implementation and review correction through `89d2ac30`
passed 13/13 GitHub check-run gates on that exact SHA, including Python 3.11/3.13,
Bandit, CodeQL, Codacy, frontend checks and the Docker build. Exact-head CodeRabbit
review found the mixed target-pair/program denominator and the per-frame rather than
global work budget; both were corrected. Its review-summary nitpick was also applied,
and the two Codacy production-`assert` findings were replaced with explicit invariant
handling. CodeRabbit completed the follow-up review without another finding, Codacy
reported zero issues, all 16 review threads were resolved, the five-minute quiet period
passed, and a separate final refresh found no new activity. Local, remote and PR heads
all matched `89d2ac30`. The PR remains draft and behind moving `main`; no merge or
history rewrite was attempted.

The bounded symbolic-walker implementation through `9eb59758` passed 13/13 GitHub
check-run gates attached to that exact head, including both Python versions, static and
security analysis, frontend checks and the Docker build. It also completed incremental
external review, zero unresolved threads, the five-minute quiet period and a separate
final refresh on 2026-08-11. This is separate from the local real-asset scope recorded
above; the full repository suite remains pending. Local, remote and PR head SHAs matched
during that refresh. This documentation-only checkpoint advances the historical
reviewed-head pointer; later implementation must still repeat the same closure cycle.

The nested-dispatch resolver implementation through `fb1ab791` then passed 13/13
GitHub check-run gates and external incremental review. Review found one inaccurate
future-tense sentence in the handoff; `63c23e2b` corrected it, CodeRabbit explicitly
confirmed the correction, and the follow-up head again passed 13/13 check-run gates.
The resolver corpus proof remains 260/260 relevant units, 14/14 opt-in real-asset
tests, exact dispatch denominators and zero unresolved threads. After the final review
activity, the five-minute quiet period and a separate final refresh completed on
2026-08-11 with matching local, remote and PR SHAs. The PR remains draft and behind a
moving `main`; no merge or history rewrite was attempted.

## Copy-paste handoff prompt

> Work from branch `agent/map-geometry-w5b-semantic-mapping`. Read
> `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`,
> `docs/research/W5A_STATIC_STAGE_ASSET_FOUNDATION_2026-08-08.md`, and this document
> in full before changing code. Continue from the explicit `Current handoff state`;
> do not substitute the broad checklist order for its measured dependency order.
> W5b maps W5a static effects to BSP/objective/spawn/route identities and publishes
> defensible static-graph coverage; it does not replay historical state. Verify every
> identity namespace and accumulator/order rule against ET:Legacy primary source,
> preserve candidate sets and unknowns, and never use fuzzy matching or final outcomes.
> Update this handoff in every substantive commit with exact tests, real-asset
> denominators, manifest hashes, decisions and review state. Do not perform production
> writes, deploys/restarts, Lua changes, force-pushes or secret operations. Merge only
> with green CI, zero unresolved threads, measured exact-head proof, the five-minute
> quiet period and a final fresh review refresh.
