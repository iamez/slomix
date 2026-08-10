# W5b semantic mapping: takeoff, trade-offs and handoff

Date: 2026-08-10

Status: implementation in progress; engine identity foundation is locally verified

Branch: `agent/map-geometry-w5b-semantic-mapping`

Base: `origin/main` at `8cb34d9975d1679417b782b3c05ef09bf008741c`

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

- [`G_ParseField`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_spawn.c#L740-L784)
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
- [`G_ScriptAction_GotoMarker`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1365-L1450)
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

Status: in progress in this docs-only commit.

1. Record the scope, branch base, W5a/W3 measured baseline and merge gates here.
2. Run documentation link/path checks and `git diff --check`.
3. Commit and push this document before production code begins.
4. Open a draft PR so review can challenge the contract early; keep it draft while
   semantic implementation and measurements are incomplete.

Exit gate: another agent can explain the W5a/W5b/W5c boundary and execute Phase 1
without relying on chat history.

### Phase 1 - verify engine identity and execution semantics

Status: in progress. Identity/action namespaces and installed accumulator operations
are source-verified; accumulator/control-flow fixtures remain pending.

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

Status: in progress. The generic engine-effective identity index and first/all lookup
fixtures are implemented locally; W3 typed joins and publication remain pending.

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

Status: pending.

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

Status: pending.

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
- [ ] Complete Phase 1 accumulator/control-flow contract fixtures.
- [ ] Complete Phase 2 generic identity index, W3 typed joins and publication.
- [ ] Complete Phase 3 objective/spawn/route semantic mappings.
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

## Current handoff state

Current step: Phase 1 accumulator/control-flow contract fixtures, followed by the
remaining Phase 2 W3 typed joins.

Next action: verify each identity namespace and accumulator/execution rule against
primary ET:Legacy source. Do not begin by writing a generic string join.

Known blockers: none for read-only research and local implementation. Any required
live-build inspection that changes or restarts a service becomes owner-gated; retain
the affected semantic result as unverified and continue with independent domains.

Current local verification (Python 3.13.14): 10 W5b identity unit tests passed; 81
combined W5a/W5b/W3 unit tests passed; the exact W5b real-asset identity acceptance
passed with eight unrelated real-asset tests deselected; Ruff and `git diff --check`
passed. The full real-asset and repository suites remain required before merge.

## Copy-paste handoff prompt

> Work from branch `agent/map-geometry-w5b-semantic-mapping`. Read
> `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`,
> `docs/research/W5A_STATIC_STAGE_ASSET_FOUNDATION_2026-08-08.md`, and this document
> in full before changing code. Continue from the first unchecked checklist item.
> W5b maps W5a static effects to BSP/objective/spawn/route identities and publishes
> defensible static-graph coverage; it does not replay historical state. Verify every
> identity namespace and accumulator/order rule against ET:Legacy primary source,
> preserve candidate sets and unknowns, and never use fuzzy matching or final outcomes.
> Update this handoff in every substantive commit with exact tests, real-asset
> denominators, manifest hashes, decisions and review state. Do not perform production
> writes, deploys/restarts, Lua changes, force-pushes or secret operations. Merge only
> with green CI, zero unresolved threads, measured exact-head proof, the five-minute
> quiet period and a final fresh review refresh.
