# W5b suspended-continuation scheduler: takeoff and handoff

Date: 2026-08-11

Last reverified: 2026-08-13

Status: implementation in progress; S0-S3 implementation complete, S3 closure pending exact-head review/CI gate

Current base: `origin/main` at `5f4ebc0ed65f38268ecafa8c45fb01f6fbc84576` (`v1.36.0`)

Original branch base: `origin/main` at `d6136cdd994870fddf4e4d0ff1968eb91418e497`

Predecessor: `docs/research/W5B_SEMANTIC_MAPPING_TAKEOFF_HANDOFF_2026-08-10.md`

Supersession: this document overrides only the predecessor's statement that exact
nested-state propagation belongs to a "W5c suspended-continuation executor". The
scheduler and exact static state propagation are W5b prerequisites for Phase 5. The
rest of the predecessor remains authoritative unless this document explicitly says
otherwise.

Installed-asset manifest:
`86ddd0ec23b3c6120136195af34aa633ad249eb358ea0fb6cd6e490dd81b220d`

Pinned ET:Legacy reference:
`732518efb1c479dcd29b13361f30a2e92df1cf2a`

## Executive decision

W5b needs one more static-analysis increment before its Phase 5 per-domain graph gate:
a bounded scheduler for suspended cross-entity continuations. The current executor
correctly refuses to combine a delayed callee with an immediate caller. The predecessor
measured 301 cross-entity temporal frontiers; S0a then found and corrected omitted
`gotomarker` control. The exact post-S0a baseline is 452 cross-entity temporal
frontiers, 386 of which hide at least one required objective, spawn or dynamic-route
domain. Deferring the class would therefore make the Phase 5 verdict knowingly
incomplete.

This scheduler remains **W5b**. It enumerates source-defensible static ordering
possibilities; it does not decide which ordering happened in a played round. **W5c**
starts only after static event-family completeness is closed and may then replay
timestamped observations against the W5b possibility graph.

The implementation must not erase uncertainty to improve coverage. It must either:

1. publish a legal static alternative with exact state and provenance; or
2. retain a named, machine-readable frontier explaining why the alternative is not
   defensible.

No production DB write, deploy, service restart, Python runtime replacement, Lua change
or live API integration belongs in this increment.

## What this increment achieves

The scheduler will provide four capabilities that the present recursive executor does
not provide together:

1. Preserve a delayed target event as a first-class suspended continuation instead of
   merging its eventual state into the caller.
2. Preserve source-defensible execution order between immediate caller work and
   relevant suspended work, branching only where the static entry context cannot prove
   the later entity-pass or event-replacement order.
3. Carry exact entity-local and level-global accumulator exit states across synchronous
   and resumed frames, including nested handlers whose mutations control later guards.
4. Produce deterministic, bounded inputs for W5b Phase 5's objective, spawn and
   dynamic-route coverage verdicts.

This unlocks:

- closure of the measured cross-entity temporal coverage gap;
- exact removal, where proven, of
  `frontier_relevance_nested_accumulator_state_unpropagated`;
- a defensible Phase 5 per-map static graph gate;
- later W5c event-family audit and historical replay over explicit candidate paths;
- offline materialization or caching without putting the full corpus traversal on a
  request path.

## What this increment does not achieve

The scheduler does not:

- infer timestamps, frame durations, wake times or historical ordering;
- choose one candidate path as the path that happened;
- replay proximity, Lua or round telemetry;
- invent a transition for an opaque identity, unresolved handler or unclassified
  runtime action;
- make W5b output eligible for a metric or player rating;
- deploy anything to dev, production or Puran;
- change the 200 ms telemetry sampling policy;
- implement W5c under a scheduler name.

Symbolic wake constraints describe partial order only. They must not contain fabricated
milliseconds or a fake global clock.

## Measured reason for doing the work

The predecessor's exact-head acceptance produced 1,090 blocked paths at the 16-unit
all-entry smoke budget:

| Hidden-domain set | All blocked paths | Cross-entity temporal paths |
|---|---:|---:|
| none | 370 | 57 |
| dynamic route only | 372 | 171 |
| objective only | 15 | 2 |
| spawn only | 1 | 0 |
| objective + spawn | 1 | 0 |
| dynamic route + objective | 211 | 49 |
| dynamic route + spawn | 22 | 18 |
| all three | 98 | 4 |
| **Total** | **1,090** | **301** |

Across all blocked paths, 703 hide dynamic-route semantics, 325 hide objective
semantics and 122 hide spawn semantics. Only 310/1,090 have a complete domain
classification. Among the 301 cross-entity temporal frontiers, 244 hide a required
domain, 175 are completely classified and 126 retain named uncertainty.

The final self-review also measured 435 blocked paths with
`frontier_relevance_nested_accumulator_state_unpropagated`, including 50 of the 301
cross-entity paths. Those paths prove that a relevance-only nested walk is insufficient:
a callee can change `accum` or `globalaccum`, return, and alter the feasibility of a
later caller guard.

These are static possibility denominators, not played-round counts.

### S0 denominator correction completed

The pinned callback proves that `gotomarker` has control behavior in addition to its
already typed dynamic-route effect. Before S0a, the ordered projection emitted only an
immediate `StageEffectInstruction`, so the walker never saw its waiting boundary.

Read-only installed-corpus inventory found:

| `gotomarker` surface | Count |
|---|---:|
| Installed actions | 172 |
| With `wait` | 139 |
| Without `wait` | 33 |
| Resolved cross-entity dispatch pairs targeting a waiting program | 133 |
| Resolved same-entity dispatch pairs targeting a waiting program | 28 |

S0a now projects the effect and control result in one instruction and distinguishes a
prior asynchronous movement from a movement started by the current action. The exact
20-map post-S0a denominator is:

| Hidden-domain set | All blocked paths | Cross-entity temporal paths |
|---|---:|---:|
| none | 382 | 66 |
| dynamic route only | 503 | 289 |
| objective only | 23 | 10 |
| spawn only | 1 | 0 |
| objective + spawn | 2 | 2 |
| dynamic route + objective | 214 | 55 |
| dynamic route + spawn | 28 | 26 |
| all three | 98 | 4 |
| **Total** | **1,251** | **452** |

The corrected run walks 2,790 concrete event entries into 5,174 paths. It records 7,754
effects, 4,011 temporal boundaries and 473 caller replacements. Boundary state counts
are 3,065 `current_action_waiting`, 701 `prior_movement_active` and 245
`next_frame_reentry`. Of the 1,251 blocked paths, 400 have complete domain
classification; of the 452 cross-entity temporal paths, 264 are complete and 188 retain
named uncertainty.

Cross-entity temporal paths split by boundary command into `wait` 190, `faceangles` 49,
`gotomarker` 171, `followspline` 18, `halt` 22 and `resetscript` 2. The original 301/244
table remains the pre-correction comparison, not the scheduler starting denominator.

### S0b alert-dispatch correction completed

S0b keeps the alert effect and its selected targets in one ordered instruction, then
dispatches only source-proven `death`/`rebirth` handlers through the existing nested
event walker. Missing or arbitrary callbacks, script-producing use chains, malformed
numeric properties, `func_explosive` lifecycle ambiguity and a possible
`trigger_objective_info` parent death all remain named fail-closed paths.

The exact installed surface is 136 alert actions selecting 1,688 static targets:

| Alert target disposition | Count |
|---|---:|
| Proven no script event | 1,675 |
| `death` handler missing | 11 |
| Resolved script-event dispatch | 2 |

The two resolved dispatches are one Adlernest `func_explosive death` and one Goldrush
tank `script_mover rebirth`. The latter handler waits. The Goldrush truck is not a
dispatch: although its resurrectable bit and handler exist, its zero initial
`health`/`count` makes the callback a no-event path. `TRIGGERSPAWN` is also checked
because ET returns before copying static health into count on that initialization path.

The exact post-S0b executor still walks 2,790 concrete entries into 5,174 paths, but it
now records 7,755 effects and two typed runtime event dispatches. Blocked paths rise
from 1,251 to 1,252 because the Goldrush rebirth reaches a previously omitted
non-exact accumulator mutation; dynamic-route-only blocked paths rise from 503 to 504,
and complete-domain counts remain 400. Cross-entity temporal counts remain 452 because
the new blocked path is classified by the existing non-exact-state frontier rather
than the temporal-interleaving frontier.

## Existing contracts to preserve

The scheduler builds on the reviewed contracts in
`website/backend/map_geometry/stage_possibilities.py`:

- `OrderedStageProgramIndex` is the only ordered-program registry.
- `OrderedEventProgram` and its typed instructions remain the source program.
- `SymbolicAccumulatorState` stores local values by concrete entity index and global
  values in level scope.
- `SymbolicEventPath` remains the evidence carrier for effects, guard decisions,
  dispatches, temporal boundaries, replacements and blockers.
- `resolve_symbolic_nested_dispatch()` remains the identity/handler resolver.
- `walk_symbolic_event_program()` remains the deterministic single-event segment
  executor.
- W3 joins continue to use entity indices, never a second fuzzy name match.
- `.ent` override identities remain usable for script dispatch but unproven for W3
  entity-index linkage.
- unsupported or ambiguous states remain explicit frontiers.
- `StageEffectInstruction`'s default immediate treatment is not authoritative for
  `gotomarker`; the implemented S0a contract already carries its source-verified
  control result without duplicating the effect projection.

The scheduler should be a sibling module, tentatively
`website/backend/map_geometry/stage_scheduler.py`. It may extend public contracts only
where a scheduler-specific type is necessary. It must not duplicate the parser, round
slicing, identity lookup or instruction semantics.

## Source-truth gate before implementation

The current executor's ordering contract is pinned to ET:Legacy commit
[`732518ef`](https://github.com/etlegacy/etlegacy/tree/732518efb1c479dcd29b13361f30a2e92df1cf2a).
Before scheduler code is accepted, re-read the complete write/run path, not only helper
names or comments:

- [`G_Script_ScriptRun`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L790-L871)
  for action order, false-return suspension and script-id replacement;
- [`G_Script_ScriptChange`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L629-L654)
  for same-entity restoration after synchronous completion;
- [`G_ScriptAction_Trigger`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1720-L1848)
  for concrete target iteration and caller replacement;
- [`G_ScriptAction_Accum`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2438-L2693)
  and
  [`G_ScriptAction_GlobalAccum`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2722-L2938)
  for storage scope, guards and conditional dispatch;
- [`wait`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L1651-L1718),
  [`followspline`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L730-L949)
  and
  [`faceangles`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2996-L3121)
  for false-return and later-pass behavior.

Wave S0 must answer, with pinned line evidence:

1. Which owner/update loop resumes each suspended script and in what entity order?
2. Whether a runnable caller suffix can execute before a different entity's suspended
   action completes.
3. What exact program counter or event-stack state is retained at each false-return
   action family.
4. Whether completion of `wait`, `followspline` and `faceangles` mutates state before
   the next script action runs.
5. Which same-frame order facts are guaranteed and which remain runtime-dependent.
6. Whether multiple suspended entities can become runnable in the same update pass and
   what deterministic iteration order then applies.

Until each answer is verified through the actual write and resume path, label it
`unverified`; do not encode it as a scheduler rule. A source comment alone is not
sufficient evidence.

### S0 pinned-source findings

The first read of the complete pinned run path changes the initial scheduling model:

1. `G_Script_ScriptChange` stores the old same-entity status, installs the target event
   at stack head zero and immediately calls `G_Script_ScriptRun`. It restores the old
   status only when that run completes synchronously with the expected script id.
2. `G_Script_ScriptRun` re-invokes the current stack item after an action returns
   `qfalse`. It advances `scriptStackHead` only after `qtrue`. A suspended continuation
   therefore needs action-specific re-entry state, not only the following instruction
   offset.
3. `G_ScriptAction_Trigger` invokes every selected target synchronously in entity order.
   A different-entity target may pause, but the trigger action still returns `qtrue` and
   the caller suffix runs immediately. The scheduler must not publish a callee-resume-
   before-caller-suffix alternative for this transition.
4. [`G_RunFrame`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_main.c#L4561-L4682)
   clears `runthisframe` and normally visits allocated entities in ascending entity
   index. A target triggered before its ordinary turn can be called again later in the
   same frame; a target whose turn has passed normally waits until the next frame.
5. [`G_RunEntity`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_main.c#L4284-L4523)
   can run a tag parent before the child and uses `runthisframe` to avoid the later
   duplicate. Raw entity index alone is therefore insufficient to reconstruct every
   normal-pass order when tag-parent dependencies are present.
6. Non-client entities reach the script runner through `G_RunThink`; invisible entities
   call it directly, movers update motion before `G_RunThink`, and item/missile paths
   also call `G_RunThink`. Client script calls occur later through `ClientEndFrame` in
   sorted-client order and remain outside statically selected W5b map-entity dispatch.
7. A fixed `wait` returns false through its deadline and has a sudden-death immediate
   branch. `resetscript` and `halt` return false on the first `level.time` and true on a
   later frame; `halt` applies its stop-motion mutation only on the first call.
8. A waiting `followspline` stays on the same stack item until trajectory completion.
   A non-waiting `followspline` returns `qtrue`, advances the script immediately and
   leaves only `SCFL_GOING_TO_MARKER` lifecycle work for later runner calls. That later
   movement completion is not a suspended script suffix and must be represented
   separately.
9. `faceangles` initializes on the first call, remains on the same stack item and
   advances only after trajectory completion.
10. `gotomarker` was silently under-modeled. The callback can return false while prior
    `SCFL_GOING_TO_MARKER` lifecycle work is active; a newly started action with `wait`
    also remains on the same item until its trajectory completes. A newly started
    non-waiting action returns true and leaves asynchronous lifecycle work, like a
    non-waiting spline. The current W5b projection records its route effect but not any
    of these control branches.

### S0 replacement and tag-parent inventory

The complete pinned write path gives this replacement matrix for an event delivered to
an entity that already owns a suspended script status:

| Delivered-event result | Retained script status | Caller consequence |
|---|---|---|
| no matching handler | old suspended status unchanged | caller/group continues |
| new handler completes synchronously with expected id | old status restored exactly | callee effects and accumulator mutations persist; caller/group continues |
| new handler returns false | new handler status retained; old status discarded | different-entity caller/group continues |
| new handler recursively changes script id | outer backup is not restored | deepest retained status follows the same rules |
| same-entity action observes changed id | replacement status retained | replaced caller suffix is abandoned |

This is not an optional interleaving: `G_Script_ScriptChange` owns the backup/restore
decision and `trigger`, `accum trigger_if_equal` and `globalaccum trigger_if_equal`
iterate concrete targets synchronously. Scheduler identity must therefore retain the
current event owner per entity; a suspended frame cannot coexist with a replacement
frame for the same entity unless source proves the older status was restored.

Exact installed projection inventory contains 1,315 explicit `trigger` instructions,
299 accumulator conditional triggers and 13 `kill` instructions. There is no installed
`cvar trigger_if_equal` action. The existing unclassified-action gate remains correct
for that absent surface.

Pinned [`G_RunEntity`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_main.c#L4284-L4523)
order is deterministic only when the frame-start `tagParent` relation is known: the
child is marked run, its parent is recursively run first, and later ordinary visits
return through `runthisframe`. The installed static surface is:

| Tag-parent surface | Count |
|---|---:|
| `attachtotag` action occurrences | 43 |
| Distinct child entities | 39 |
| Distinct parent entities | 12 |
| Distinct child-parent pairs | 39 |
| Actions resolved by unique `targetname` | 43 |
| Candidate-child programs | 103 |
| Candidate-child programs with temporal control | 42 |
| Resolved dispatch pairs targeting a candidate child | 53 |
| Different-entity pairs targeting a candidate child | 41 |

Those 42 temporal programs contain 47 `wait` and 13 `faceangles` instructions. All 43
actions resolve statically; 37 action occurrences select a `script_mover` parent and 6
select `misc_gamemodel`. However, an isolated event entry cannot prove whether an
earlier event already executed a persistent attachment. The scheduler may use an exact
relation established inside its own root schedule; otherwise it must retain typed
`tag_parent_state_unknown` wake provenance. Raw entity index is not a valid fallback.

### S0 adversarial fixture contracts

The following fixture pairs freeze the source result before scheduler transitions are
introduced. S1 provides their executable state-identity assertions; transition-order
assertions remain S2-S3 work because the current recursive walker intentionally stops
at the first cross-entity temporal frontier.

**R1 - replacement of an already suspended target**

1. A caller triggers target event `long`, whose first `wait 100` is explicitly fixed to
   the ordinary false-return/suspended branch. The sudden-death immediate branch is not
   part of R1.
2. The different-entity caller continues and triggers `replacement` on the same target.
3. Variant R1-sync makes `replacement` complete synchronously. ET restores the exact
   backed-up `long` status, so its boundary action remains the target's current owner;
   replacement effects persist and the caller continues.
4. Variant R1-wait makes `replacement` return false. ET does not restore `long`; the
   replacement boundary becomes the only retained target status and the caller still
   continues.

R1-sync and R1-wait must never share a canonical state. A model that keeps both old
and replacement continuations simultaneously is also invalid.

**T1 - tag parent reverses raw entity order**

1. Give child entity index `c` a lower value than parent index `p`.
2. Without an established attachment, the ordinary pass visits `c` before `p`.
3. With `c.tagParent = p`, `G_RunEntity(c)` recursively runs `p`, marks it
   `runthisframe`, then runs `c`; the later ordinary visit of `p` is skipped.
4. A root that executed `attachtotag` may establish that relation exactly for its later
   schedule. An isolated entry with the same static entities cannot infer whether the
   persistent relation already exists and must retain `tag_parent_state_unknown`.

T1 has three distinct canonical states: source-proven attached, source-proven
unattached and unknown persistent attachment. The attached variant must publish
parent-before-child; the proven-unattached variant may use ordinary child-before-parent
entity order; the unknown isolated variant must not choose either order merely from
entity indices. No pair of these three states may canonicalize together.

### S0b alert-event correction

Pinned [`alertentity`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script_actions.c#L2242-L2292)
calls each selected target's `use` callback synchronously. Exact-corpus inventory found
136 alert actions. Two select the Goldrush tank/truck resurrectable `script_mover`
entities, but only the tank has non-zero `health`, which initializes `count`, so
[`script_mover_use`](https://github.com/etlegacy/etlegacy/blob/732518efb1c479dcd29b13361f30a2e92df1cf2a/src/game/g_script.c#L1054-L1073)
must deliver `rebirth` only for the tank; its handler contains a `wait`. The truck's
zero `count` makes its callback a proven no-event path despite the handler existing.

Before S0b, `StageEffectInstruction` recorded those alerts only as target effects and
did not dispatch the tank `rebirth`, so scheduler state built on that projection was
incomplete. `func_explosive_use` also delivers `death`: 12 installed
alert targets reach that callback, 11 have no handler and one Adlernest target resolves
an immediate handler. Two installed `target_relay` alert targets fan out only to
speakers, and the other installed alert target chains contain no
`target_script_trigger`; those are measured corpus facts, not a general claim about
arbitrary maps.

S0b now adds the typed, ordered alert-dispatch contract for source-proven callbacks,
fails closed on alert/use paths whose script-event behavior is not proven, and freezes
the corrected corpus denominator before S1 canonical state.

These findings prove caller-before-suspended-target-resume for a cross-entity trigger.
They do **not** yet prove a closed global schedule because later caller actions or other
entities can trigger a new event on the suspended target and replace its retained
status. S0b alert dispatch is implemented, and executable S1 adversaries now freeze the
R1 replacement owner and all three T1 tag-parent identities. Canonical state types may
therefore proceed; transition behavior remains gated on S2-S3 tests.

## Proposed scheduler model

The following names communicate the required information. They are not frozen APIs
until S0 proves the transition contract.

```python
class SymbolicResumeMode(StrEnum):
    REENTER_BOUNDARY_ACTION = "reenter_boundary_action"


@dataclass(frozen=True, slots=True)
class PendingDispatchContext:
    dispatch_node_id: str
    dispatch_line: int
    caller_node_id: str
    caller_entity_index: int
    caller_instruction_offset: int
    ordered_target_entity_indices: tuple[int, ...]
    target_cursor: int


@dataclass(frozen=True, slots=True)
class SymbolicFrame:
    node_id: str
    entity_index: int
    instruction_offset: int
    call_stack: tuple[tuple[int, str], ...]
    pending_dispatch: PendingDispatchContext | None
    origin: str


@dataclass(frozen=True, slots=True)
class SuspendedContinuation:
    frame: SymbolicFrame
    boundary_command: str
    boundary_line: int
    resume_mode: SymbolicResumeMode
    boundary_state: tuple[str, ...]
    wake_constraint: str
    effect_footprint: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SymbolicScheduleState:
    accumulator_state: SymbolicAccumulatorState
    runnable: tuple[SymbolicFrame, ...]
    suspended: tuple[SuspendedContinuation, ...]
    async_lifecycles: tuple[SymbolicAsyncMovementLifecycle, ...]
    effects: tuple[StageEffectProjection, ...]
    provenance: tuple[str, ...]
    ordering_decisions: tuple[str, ...]
    unknown_reasons: tuple[str, ...]
```

Required properties:

- Every frame identifies one concrete entity, one ordered program and one instruction
  offset.
- Every pending group dispatch identifies the parent dispatch, caller-resume cursor,
  complete ordered target list and current target cursor.
- Every `SuspendedContinuation` re-enters its exact boundary action. When a non-waiting
  movement action has already advanced the script while lifecycle work remains, S1
  records it only as a separate `SymbolicAsyncMovementLifecycle`.
- Action-specific boundary state is typed before implementation; a generic string
  tuple in the sketch is not an approved representation.
- A frame's call/replacement provenance cannot be reconstructed from line number alone.
- Suspended continuations are separate tasks. Their state is not copied into an
  immediate caller result before they run.
- Caller-suffix and target-group continuation are runnable-frame origins, not alternate
  resume modes for a suspended boundary action.
- Accumulator state is shared exactly according to the existing local/global contract.
- Effects preserve source entity and program provenance.
- Collections have a deterministic canonical order independent of Python set/dict
  iteration.
- Unknown reasons are part of output identity, not log-only text.

The canonical state key must include `pending_dispatch`, `resume_mode` and typed
boundary state. Collision tests must differ only in parent dispatch, caller cursor,
target cursor, selected target order, boundary action or resume mode and prove that
none of those states are merged.

`wake_constraint` must initially be a small enum or typed relation such as
`AFTER_BOUNDARY_COMPLETION`, not a free-form timestamp. If S0 cannot distinguish two
relations, publish `wake_semantics_unverified` instead of choosing one.

## Transition semantics

### Deterministic segment

Run one selected frame through the existing single-event walker until it:

- completes synchronously;
- aborts through a proven guard;
- replaces a same-entity caller;
- reaches a temporal boundary;
- reaches a nested dispatch requiring another frame; or
- produces a named blocker.

Do not re-project actions in the scheduler.

### Synchronous nested completion

When pinned source proves the callee completes synchronously:

1. consume the callee's exact exit `SymbolicAccumulatorState`;
2. retain its effects and provenance;
3. continue the remaining concrete targets in engine order;
4. restore or abandon the caller only under the existing same-entity replacement rule;
5. evaluate later caller guards against the callee exit state.

This is the direct fix for the 435 named nested-state uncertainty paths. The unknown
reason may disappear only on paths where exact exit-state propagation succeeds.

### Temporal cross-entity boundary

When a different-entity target reaches a proven temporal boundary:

1. freeze its current boundary action and source-proven re-entry mode as
   `SuspendedContinuation`;
2. keep its state at the boundary, without applying unexecuted mutations or effects;
3. complete the remaining synchronously selected targets in engine order where the
   source callback continues its loop;
4. run the caller suffix immediately after the trigger returns `qtrue`;
5. only after that immediate work, make the suspended task eligible for its ordinary
   entity pass or a source-proven event replacement;
6. record same-frame-later, next-frame, tag-parent-order-unknown or replacement
   provenance explicitly;
7. resume the suspended task only through a source-proven wake/re-entry transition.

The scheduler must never implement this as `caller_state | eventual_callee_state` or as
an unordered union of effects. It must also never publish callee-resume before the
caller suffix merely because both tasks exist in the symbolic state.

### Non-waiting movement lifecycle

A non-waiting `followspline` is not a suspended frame. Its action returns true, the
script stack advances and the caller suffix executes while movement remains active.
The scheduler must retain movement-completion relevance separately from a script
continuation. It may not re-run the `followspline` source action or delay its suffix.

Waiting `followspline` and `faceangles` remain action re-entry continuations. Their
completion mutations occur before the stack advances and therefore belong to the
resumed boundary transition.

### Same-entity replacement

Same-entity temporal replacement is not ordinary concurrency:

- a final same-entity target can abandon the caller suffix;
- synchronous completion may restore the caller under the pinned ScriptChange rule;
- a same-entity target within a shared target group must preserve the remaining group
  iteration contract;
- a temporal same-entity group ambiguity retains
  `same_entity_temporal_group_order_not_modeled` until a dedicated rule is proven.

Do not place same-entity replacement and cross-entity scheduling behind one generic
recursive-call abstraction.

### Shared target groups

The existing resolver preserves every selected concrete target. The scheduler must:

- retain engine entity order where source proves it;
- preserve each target's concrete identity;
- retain not-yet-started targets when an earlier target suspends;
- distinguish remaining targets from a resumed caller suffix;
- avoid choosing one representative target;
- fail closed if runtime `scriptName` mutation invalidates the selected group.

### Kill/death dispatch

Source-verified kill projections may create a death-handler frame. The scheduler must
retain the existing optional no-event branch, concrete target identity and one-shot
handler uncertainty. Constructible runtime destruction stages and opaque/runtime-
mutable script identities remain blockers unless separately source-proven.

### Accumulator domains

Continue to use exact/refined `SymbolicIntegerDomain` values:

- local accumulators are keyed by concrete entity;
- global accumulators are shared across runnable and suspended tasks;
- guard splits refine the selected branch;
- contradictory branches disappear;
- a non-exact mutation remains a named blocker;
- no schedule state may reset unknown entry state to zero;
- a resumed task observes the global state created by the selected earlier schedule
  steps.

This last rule is why ordering alternatives cannot be collapsed before their later
global-accumulator guards have been evaluated.

## Relevance scope

The initial scheduler is deliberately narrower than a general ET script runtime:

1. Start from cross-entity/shared-target temporal frontiers already identified by the
   W5b executor.
2. Expand a fully classified frontier only when it hides objective, spawn or
   dynamic-route semantics.
3. Do not expand the 57 currently empty cross-entity frontiers merely to raise an
   execution count.
4. Keep unknown relevance fail closed. Resolve the identity, route, accumulator or
   cycle reason first; do not schedule through it by assumption.
5. Preserve the complete denominator so skipped-empty, scheduled-relevant and
   unknown-not-scheduled frontiers remain distinguishable.

If implementation evidence proves that a supposedly empty frontier shares mutable
global state with a relevant task, it is no longer independent and must be included or
reported unknown. Empty domain labels alone do not prove commutativity.

## Boundedness and partial-order reduction

Naive interleaving grows exponentially. Boundedness is part of correctness, not only
performance.

### One global budget

Use one explicit work/state budget for the whole root schedule. Nested helpers must not
each receive a fresh full budget. Budget exhaustion returns one deterministic named
frontier such as `symbolic_schedule_budget_exhausted` with the runnable/suspended
summary and source provenance.

Record separately:

- states created;
- transitions evaluated;
- maximum runnable tasks;
- maximum suspended tasks;
- maximum frame depth;
- deduplicated states;
- budget and cycle frontiers;
- elapsed time and peak RSS for the exact corpus.

### Canonical state identity

Visited-state identity must include every field that can affect later semantics:

- ordered runnable frames;
- ordered suspended continuations and their wake constraints;
- parent dispatch identity, ordered target group, target cursor and caller-resume
  cursor;
- boundary action, typed boundary state and resume mode;
- local/global symbolic accumulator state;
- same-entity replacement/call-stack state;
- relevant lifecycle/identity uncertainty;
- the next unexecuted instruction for every task.

Effect history may be represented by an immutable digest plus retained provenance only
if equality cannot collapse two different Phase 5 outcomes.

### Dominance and subsumption

Do not implement dominance from intuition. One state may subsume another only when a
testable proof shows that every future effect and blocker of the removed state is
preserved by the retained state. Broadening an exact accumulator value to unknown is
not harmless: it can convert a proven guard result into both branches.

### Partial-order reduction

Two task steps may commute only when S0/source evidence and explicit footprints prove:

- they touch disjoint entity-local accumulators;
- neither touches a global accumulator used by the other;
- neither mutates identity/lifecycle used by the other;
- neither dispatches to or replaces the other's entity/program;
- their effect order is irrelevant to all three Phase 5 domains.

If any footprint is unknown, retain both orderings or a named
`schedule_independence_unproven` frontier. Do not infer independence from different
entity indices alone.

### Cycles

Cycle keys must use canonical schedule state, not only `(entity_index, node_id)`. A
return to the same frame with different accumulator or suspended-task state is not the
same state. Conversely, an exact repeated schedule state can close as a named cycle
frontier without pretending it ran once or forever.

## Architecture and ownership boundary

Recommended module split:

- `stage_possibilities.py`: ordered instruction projection, single-frame execution,
  dispatch resolution and current public evidence types;
- `stage_scheduler.py`: runnable/suspended state, scheduling transitions,
  canonicalization, bounded search and scheduler-specific results;
- `stage_semantics.py`: existing static entity/effect projections; no scheduler code;
- opt-in real-asset analyzer/test: corpus aggregation and deterministic evidence;
- Phase 5 analyzer: consumes scheduler results but does not run the full corpus on an
  HTTP request.

The scheduler may call existing private helpers only after they are promoted behind a
small tested interface. Do not duplicate several hundred lines to avoid an interface
decision. Conversely, do not expand `SymbolicEventPath` into an all-purpose runtime
object if a scheduler-owned type keeps responsibilities clearer.

Request-time behavior is out of scope. The predecessor's exact corpus acceptance took
427.88 seconds with 494,292 KiB peak RSS. Phase 5/W5c must use offline precomputation,
content-addressed caching or an equivalent explicit materialization boundary.

## Implementation waves

### S0 - source truth and adversarial fixtures

1. Re-read the pinned runner, update loop and relevant action callbacks.
2. Add exact line citations and a transition table: immediate, suspended, resumed,
   replaced, aborted and blocked.
3. Build minimal fixtures that distinguish synchronous return from delayed
   cross-entity continuation.
4. Mark every remaining claim unverified rather than encoding it.

Exit: reviewers can trace every scheduling rule to primary source and at least one
adversarial test.

### S0a - close the typed `gotomarker` control gap

1. Represent `gotomarker` route effect and control behavior in one ordered instruction
   contract; do not emit two same-line instructions that make line-to-offset identity
   ambiguous.
2. Preserve distinct paths for pre-existing movement blocking the action, a newly
   started waiting movement and a newly started non-waiting movement.
3. Record whether the effect has actually started on each branch. A prior-motion
   boundary must not claim that the new destination was already selected.
4. Re-enter a waiting boundary at the same action. If a prior asynchronous movement
   blocked the action, preserve that re-entry identity but do not invent a second route:
   the pinned callback completes the current action after the old movement clears.
   Advance a newly started non-waiting action while retaining only asynchronous
   lifecycle provenance.
5. Regenerate the complete corpus denominator and update every affected expectation
   before scheduler state types freeze.

Exit: focused source-contract tests pass, the 172-action/139-wait inventory is frozen,
and the exact 20-map run publishes the corrected cross/same temporal frontier baseline.

### S0b - close source-proven `alertentity` event dispatch

1. Keep the alert effect and selected-target order in one instruction contract.
2. Project `rebirth` only for a statically selected `script_mover` whose resurrectable
   spawnflag and non-zero health prove the callback branch.
3. Run the handler through the existing event resolver and preserve the same
   synchronous/suspended/replacement rules as explicit trigger delivery.
4. Fail closed for a target callback or target-chain script dispatch that is not
   source-proven; do not infer safety from the installed corpus having no example.
5. Freeze the 136-action target-class/chain inventory, both resolved event dispatches and the
   regenerated exact executor denominator.

Exit: focused tests distinguish no-handler, synchronous rebirth and waiting rebirth;
the Goldrush tank case produces a real temporal frontier instead of an immediate-only
effect; no general target-use chain is silently classified as harmless.

### S1 - immutable state and canonicalization

1. Add scheduler-owned frame, continuation, state, decision and result types.
2. Validate index/program ownership and offsets at construction boundaries.
3. Define deterministic ordering and canonical visited keys.
4. Add one global positive work budget with named exhaustion.

Exit: type/unit tests prove equal semantic states canonicalize equally, meaningful
differences do not collide, and malformed ownership fails loudly.

S1 must include current per-entity event ownership and typed tag-parent state in the
canonical key. A relation is exact only if the root schedule established it or the
entry contract supplied it; otherwise ordinary wake order remains unknown.

### S2 - one suspended cross-entity continuation

1. Run one caller and one different-entity target to the first temporal boundary.
2. Preserve caller suffix, remaining target cursor and suspended target separately.
3. Prove the immediate caller suffix executes before ordinary target resumption.
4. Distinguish same-frame-later from next-frame resumption where static entity-pass
   provenance is sufficient; retain a named unknown otherwise.
5. Resume the target by re-entering the exact boundary action with exact state and
   provenance.

Exit: a synthetic map proves caller-before-resume, rejects the inverse ordering,
distinguishes target cursor and caller cursor, and retains a frontier where ordinary
entity-pass/wake semantics are unverified.

### S3 - nested state return and shared targets

1. Propagate synchronous callee exit state into remaining targets and caller guards.
2. Model local `accum` isolation and shared `globalaccum` interleaving.
3. Preserve concrete shared-target order and remaining-target continuations.
4. Keep same-entity replacement distinct from cross-entity scheduling.
5. Integrate source-verified optional death dispatch without widening constructible
   handling.

Exit: focused tests prove the 435-class nested-state gap is fixed only where exact and
that no caller suffix survives an abandoned same-entity replacement.

### S4 - bounded search and partial-order reduction

1. Add canonical visited-state detection.
2. Add only footprint-proven independence reductions.
3. Add exact cycle and budget frontiers.
4. Add adversarial exponential fixtures and deterministic truncation assertions.

Exit: runtime and state count remain bounded, output is deterministic, and no unknown
or effect disappears merely due to task ordering.

### S5 - exact installed-corpus measurement

1. Re-run all 20 maps against the exact asset manifest.
2. Publish before/after tables for the regenerated post-S0a cross-entity temporal
   frontier denominator, with the original 301 shown separately for traceability.
3. Report domain resolution, remaining reasons, scheduler states, runtime and RSS.
4. Verify that the 57 empty/complete frontiers are not expanded unless mutable-state
   evidence made them relevant.
5. Record every denominator; do not publish only improved percentages.

Exit: exact-head results are reproducible from hashed assets and every removed unknown
has a source/test/evidence trail.

### S6 - W5b Phase 5 static graph gate

Only after S5 stabilizes, implement the per-map objective, spawn and dynamic-route
verdicts already specified in the predecessor document. A map/domain remains partial or
unknown if any required scheduler frontier remains unresolved. Overall defensible may
not hide a partial domain.

Exit: the static graph report is deterministic, content-sensitive and explicitly
separate from W5c historical truth.

## Required test matrix

### Unit/source-contract tests

- one immediate caller plus one suspended different-entity callee;
- caller suffix before an ordinary callee resume;
- absence of callee-resume-before-caller-suffix;
- same-frame-later versus next-frame resume based on entity-pass position;
- tag-parent pass ordering retained as unknown when not represented;
- later caller action replacing a suspended target event;
- two states differing only by parent dispatch identity not canonicalizing together;
- two states differing only by target cursor not canonicalizing together;
- two states differing only by selected-target order not canonicalizing together;
- two states differing only by caller-resume cursor not canonicalizing together;
- two states differing only by action-specific boundary state or resume mode not
  canonicalizing together;
- synchronous nested local-accumulator mutation controlling a later caller guard;
- cross-entity local accumulators remaining isolated;
- suspended `globalaccum` mutation changing a later task's guard;
- contradictory refined domains being removed;
- unknown entry state never becoming zero implicitly;
- same-entity synchronous restoration;
- same-entity temporal caller abandonment;
- non-waiting `followspline` advancing its suffix while retaining asynchronous movement
  lifecycle work;
- waiting `followspline` re-entering its current action;
- `gotomarker wait` starting its route effect and re-entering the same action;
- `gotomarker` blocked by a prior movement without prematurely recording the new route
  effect;
- non-waiting `gotomarker` advancing its suffix while retaining asynchronous movement
  lifecycle work;
- shared-target continuation retaining every remaining concrete target;
- multi-target identity and engine order;
- optional kill death-dispatch event/no-event alternatives;
- runtime-mutable script identity remaining unknown;
- missing handler, opaque identity and malformed projection remaining named blockers;
- wake semantics unverified;
- exact repeated-state cycle;
- same frame with different state not treated as a cycle;
- global budget exhaustion from nested branching;
- permutation-invariant public output ordering;
- canonical-key collision adversaries.

### Integration tests

- real `OrderedStageProgramIndex` plus scheduler, not hand-injected result dictionaries;
- a fixture whose SQL/parser-independent assets contain two entities sharing one script
  name and one target suspends;
- a fixture proving nested `globalaccum` exit state changes published domains;
- exact opt-in installed-asset suite pinned to the manifest hash;
- deterministic output on two independent runs;
- corpus resource ceiling assertion or recorded benchmark, kept opt-in if environment
  variance makes a hard CI ceiling unreliable.

### Regression invariants

- all existing W1-W5b focused tests remain green;
- the predecessor's typed instruction and dispatch counts change only with explained
  evidence;
- no frontier reason disappears without a corresponding schedule outcome or more
  specific frontier;
- no candidate target group shrinks by selecting one representative;
- no Phase 5 domain becomes complete through budget exhaustion;
- no full-corpus traversal enters an ordinary HTTP request test.

## Measurement and Definition of Done

The PR body and this handoff must record evidence for the exact reviewed substantive
head:

| Evidence | Required publication |
|---|---|
| Starting denominator | Pre-correction 301/244 plus a regenerated post-S0a baseline |
| Result split | resolved, still blocked, skipped empty/complete, unknown not scheduled |
| Domain split | objective, spawn, dynamic route and overlaps before/after |
| State uncertainty | 435 overall and 50 cross-entity nested-state reasons before/after |
| Search size | states, transitions, deduplications, cycles, budget exhaustion |
| Fan-out | maximum runnable/suspended tasks and frame depth |
| Performance | elapsed time and peak RSS over exact 20-map corpus |
| Reproducibility | asset manifest, Python version and substantive commit |
| Verification | focused, expanded map-geometry and complete repository suites |

Acceptance rules:

1. No unknown disappears because it was filtered from the denominator.
2. Every resolved frontier has a source-defensible schedule and test evidence.
3. Every unresolved frontier retains a stable machine-readable reason.
4. Output is deterministic under the exact asset manifest.
5. One explicit global budget bounds the root search.
6. Ruff and `git diff --check` pass.
7. The full repository suite passes.
8. CI is green on the exact final head.
9. Zero unresolved review threads remain.
10. Measured proof is present on the PR, not only a statement that tests passed.
11. Five quiet minutes pass after the last push or review activity, followed by a fresh
    check/review/comment/thread refresh immediately before merge.

## Trade-offs and decisions

### General interleaving engine vs scoped relevant scheduler

Decision: build the smallest engine-source-defensible scheduler that closes the
measured relevant temporal frontier. A general ET runtime would carry unbounded state
and duplicate the game engine. The scoped scheduler still preserves unknowns that can
affect required domains.

### Symbolic partial order vs invented time

Decision: represent wake/order constraints symbolically. W5b lacks observations and
must not assign milliseconds. Timestamp alignment belongs to W5c.

### Exact state vs broad unknown

Decision: propagate exact/refined accumulator state while the existing domain model can
prove it; otherwise retain a named frontier. Broad unknown is safer than a false exact
value but cannot be used as a reason to publish both branches as historical truth.

### Exhaustive schedules vs partial-order reduction

Decision: enumerate legal alternatives and reduce only footprint-proven commuting
steps. Different entity identities alone do not prove independence because
`globalaccum`, dispatch and lifecycle state cross entity boundaries.

### Inline executor expansion vs sibling scheduler module

Decision: prefer a sibling scheduler module using reviewed W5b primitives. The existing
module already owns projection and deterministic path walking; scheduling is a distinct
state/search responsibility.

### Request-time calculation vs offline materialization

Decision: keep exact corpus analysis offline. The measured predecessor runtime/RSS is
incompatible with a normal API request, and scheduling adds more state.

### Coverage gain vs honest unknowns

Decision: optimize for a defensible denominator, not a high completion percentage. A
named unknown is a correct result when source, identity or budget evidence is missing.

## Risks and mandatory mitigations

| Risk | Mitigation |
|---|---|
| State explosion | One root budget, canonical states, proof-based reduction, named exhaustion |
| False ordering | Pin update/resume source; retain unverified wake frontier |
| Lost global state | Include global accumulator domains in canonical identity and footprints |
| Local state leaks | Key local accumulators by concrete entity and test adversarially |
| Caller suffix executed after replacement | Separate same-entity transition rules and fixtures |
| Shared target silently dropped | Preserve ordered concrete target list in every continuation |
| Unknown removed to improve metrics | Before/after denominator accounting and stable reason invariants |
| Corpus analyzer enters API path | Offline/materialized architecture boundary and regression test |
| Source drift | Pin commit URLs and record any later ET:Legacy comparison separately |
| Asset drift | Require the deterministic installed-asset manifest in evidence |

## Owner-gated and deferred work

Do not perform within this work:

- production or dev DB writes that change persisted data;
- deploy or service restart;
- Python 3.11 environment replacement;
- Lua/Puran changes;
- force-push, history deletion or remote branch deletion;
- secret rotation;
- W5c telemetry replay;
- Phase 5 publication into live API or rating formulas;
- telemetry sampling-policy changes.

Code, tests, documentation, ordinary commits/pushes, draft/ready PR transitions, review
responses and merge are autonomous under the standing merge gate. Remote branches stay
retained.

## PR and review protocol

1. First commit and push this documentation-only takeoff.
2. Open a draft PR before scheduler code so review can challenge the contract.
3. Keep one focused PR for the scheduler. Split Phase 5 publication if the scheduler
   diff becomes too large to review rigorously.
4. After every substantive push, inspect all reviews, issue comments and GraphQL review
   threads. Answer and resolve a thread only after the fix/evidence is pushed.
5. Treat P1 correctness questions about state, ordering, identity, budgets or
   denominators as merge blockers.
6. If an automated reviewer is rate-limited, perform and publish an exact-head
   self-review; still process any later external review before merge.
7. Wait at least five minutes after the last push or review activity.
8. Immediately before merge, refresh CI, head SHA, mergeability, comments, reviews and
   unresolved threads again.
9. Merge only when every check is green, unresolved threads are zero and exact-head
   measured evidence is present.

## Handoff checklist

- [x] Establish a clean branch from merged W5b frontier-classification main.
- [x] Correct the boundary: scheduler is W5b; W5c remains historical replay.
- [x] Record the exact predecessor denominators and manifest.
- [x] Define scope, non-goals, trade-offs, risks and owner gates.
- [x] Define source-truth questions, transition model, tests and Definition of Done.
- [x] Commit and push the documentation-only takeoff (`b9919eaa`).
- [x] Open draft PR [#649](https://github.com/iamez/slomix/pull/649).
- [x] Complete S0 source verification; runner/action reads, installed surfaces and
  adversarial replacement/tag-parent fixture contracts are recorded. S1 executes their
  canonical identity assertions; transition ordering remains assigned to S2-S3.
- [x] Complete S0a typed `gotomarker` control/effect correction and regenerate the
  frontier denominator.
- [x] Complete S0b source-proven `alertentity` event dispatch and regenerate the
  denominator.
- [x] Complete S1 immutable state/canonicalization.
- [x] Complete S2 single suspended continuation.
- [x] Complete S3 nested state/shared-target handling.
- [ ] Complete S4 bounded search/reduction.
- [ ] Complete S5 exact corpus evidence.
- [ ] Complete S6 Phase 5 static graph gate, or split it into a successor PR with an
  explicit handoff.
- [ ] Complete all review and merge gates.

## Handoff record

### 2026-08-11 - documentation-only takeoff

- Contract commit: `b9919eaa`.
- Draft PR: [#649](https://github.com/iamez/slomix/pull/649).
- Scope: documentation only; no runtime or owner-gated operation.
- Verification: `git diff --cached --check` passed; branch base matched
  `origin/main` at `d6136cdd` before the commit.
- Next item: S0 source verification of the engine update/resume path.

### 2026-08-11 - early review and S0 correction

- CodeRabbit's rate-limited early contract review still reported two valid issues:
  pending dispatch/resume identity was incomplete, and the predecessor's stale W5c
  phase assignment needed explicit supersession. Both are corrected in this document.
- Pinned source proves a different-entity target runs synchronously to its first false
  return, remaining target iteration completes, and the caller suffix runs before the
  target's ordinary later resume. The original free-order sketch was removed.
- A read-only corpus probe splits the existing 301 frontiers into `wait` 231,
  `faceangles` 49, waiting `followspline` 10, `halt` 9 and `resetscript` 2.
- A separate read-only inventory found 172 `gotomarker` actions (139 waiting, 33
  non-waiting) and 133 cross-entity plus 28 same-entity resolved pairs targeting a
  waiting program. The executor at that head did not project that control result, so
  S0a had to precede scheduler implementation and regenerate all denominators.
- No owner-gated operation was performed.

### 2026-08-11 - S0a typed temporal-control correction

- Code/test commit: `45025749`.
- `gotomarker` remains one source-ordered instruction, now carrying both its route
  projection and source-verified conditional control contract.
- `prior_movement_active`, `current_action_waiting` and `next_frame_reentry` are typed
  boundary states; effect evidence is emitted only after the current movement starts.
- Exact source review corrected an initially over-broad local implementation: after an
  older asynchronous movement clears, ET re-enters the blocked action with an old
  stack-change time and completes it without starting the new route.
- Verification: 120 focused possibility tests, 260 map-geometry unit tests, both exact
  inventory/dispatch regressions and the exact 2,790-entry corpus executor passed. The
  exact corpus numbers are frozen in the post-S0a table above and in the real-asset
  regression test.
- No production write, deploy, service restart or other owner-gated operation was
  performed.
- Next item: close the remaining S0 replacement/tag-parent source gates, then begin S1
  immutable scheduler state and canonicalization after review of this corrected
  baseline.

### 2026-08-11 - S0 replacement/tag-parent inventory

- Pinned replacement source establishes one retained event owner per entity: a
  synchronous replacement restores the old suspended status, while a suspended or
  recursively replaced event discards it. Different-entity caller iteration continues;
  a changed same-entity script id abandons the caller suffix.
- Exact static dispatch surface: 1,315 explicit triggers, 299 accumulator conditional
  triggers and 13 kills; no installed cvar conditional trigger.
- Exact tag surface: 43 `attachtotag` actions, 39 distinct children, 12 parents and 39
  child-parent pairs. Forty-two candidate-child programs contain temporal control and
  41 different-entity dispatch pairs target a candidate child.
- `alertentity` source review found an additional pre-S1 gap: one of 136 installed
  alerts synchronously delivers a waiting `rebirth` to the Goldrush tank. The truck has
  the handler and resurrectable bit but no health/count, so its callback delivers no
  event. One Adlernest `func_explosive death` handler is also reachable immediately.
- Next item: implement S0b typed alert dispatch, freeze its adversarial fixtures and
  regenerate the exact denominator before S1.

### 2026-08-13 - current-main sync and S0b alert dispatch

- Main sync commit: `62e69a3d`; code/test commit: `fc6a889b`.
- The branch was 74 main commits behind after the pause. `origin/main` at `f51edc88`
  touched CI and broader runtime dependencies but none of the W5b source/test/doc
  paths. It was merged normally to preserve published history; no force-push occurred.
- Pinned source review added four conditions beyond the initial corpus observation:
  `TRIGGERSPAWN` prevents static health from initializing `script_mover.count`, a
  `trigger_objective_info` can make `func_explosive_use` dispatch parent `death`, and
  malformed numeric BSP properties must not silently become zero. A `script_mover`
  without `RESURRECTABLE` or `TRIGGERSPAWN` has no `use` callback, so alerting it is a
  fatal source path rather than an immediate no-event continuation.
- S0b preserves selected-target order, records typed runtime dispatch provenance,
  executes exactly one source-proven handler through the existing nested walker and
  fails closed for multi-handler groups or any unresolved callback/lifecycle/parent
  path.
- Exact installed inventory: 136 alert actions, 1,688 selected targets, 1,675 proven
  no-event targets, 11 missing `death` handlers and two resolved dispatches (`death`
  and `rebirth`). No installed alert target has the possible parent-death condition.
- Exact executor: 2,790 entries, 5,174 paths, 7,755 effects, two runtime event
  dispatches, 1,252 blocked paths and 452 cross-entity temporal paths. The only new
  blocker is one previously hidden `non_exact_accumulator_mutation` reached from the
  Goldrush rebirth handler.
- Verification on the synced base: 132 focused tests, Ruff and `git diff --check`
  passed; the exact alert inventory and full 20-map executor acceptance tests passed.
  No owner-gated operation was performed.
- The valid CodeRabbit wording finding is corrected: S0a is described as already
  implemented, not as future work. Review/CI must run again after push.
- S0 freezes R1 sync-versus-wait replacement ownership and T1 attached, proven-
  unattached and unknown tag-parent ordering as adversarial fixture contracts. S1 now
  supplies executable canonicalization assertions; transition assertions remain S2-S3
  work.
- CodeRabbit's exact-head `876de54d` source review independently traced the
  `script_mover` flags/health/count path, target order, fail-closed dispositions,
  nested dispatch and corpus arithmetic and reported no defect. The Codex review
  request remains pending at this record point.
- Next item: begin S1 immutable state and canonicalization only after exact-head S0
  review is clean.

### 2026-08-13 - S1 immutable state and canonicalization

- Main sync commits: `15b873bc` and `efbf89f9`; S1 code/review commits: `4f53c782`, `3ad4d981`,
  `08928faf`, `b45bfd0c`, `1df54390`, `076856bc`, `c5623426` and `58ba5af0`. The branch base is current
  `origin/main` at `42fe7819`; main is an ancestor and there are no unmerged main
  commits at this record point.
- The second sync integrated eight sick-leave/identity commits after the exact-head
  evidence review. Their 14 changed paths do not overlap the W5b source, tests or
  handoff; the normal merge completed without conflict. Post-merge verification passed
  all 149 focused scheduler/possibility tests, all 289 map-geometry unit tests, Ruff and
  `git diff --check`. The merged head still requires a new exact-head CI/review gate.
- `SymbolicScheduleState.create()` is the sole validated construction boundary. Its
  canonical identity includes program identity, accumulator state, ordered runnable
  frames, order-independent suspended continuations, asynchronous movement
  lifecycles, current event owners, three-valued tag-parent disposition, ordered
  effects and provenance, accumulated ordering constraints and named unknowns.
- Dispatch identity is bound to the concrete caller frame, target program cursor,
  selected-target ordinal and invocation ordinal. Construction rejects reordered or
  out-of-range dispatches, terminal mismatches and a pending target cursor that does
  not match its invocation.
- The only legal suspended resume is re-entry at the boundary action. Non-waiting
  movement is represented separately as `SymbolicAsyncMovementLifecycle`, because its
  script frame has already advanced; waiting movement cannot use that lifecycle.
- The R1 fixture proves distinct canonical ownership for synchronous completion versus
  a suspended replacement. The T1 fixture proves attached, proven-unattached and
  unknown tag-parent states remain distinct. Transition-order behavior remains S2-S3
  scope.
- Final S1 local evidence at `58ba5af0`: all 163 scheduler plus possibility tests and
  all 303 map-geometry unit tests passed; Ruff and `git diff --check` passed. No corpus
  denominator changes in S1 because this wave introduces state identity, not traversal.
- Review found and closed five construction-boundary defect classes: stale S0 wording,
  missing executable adversaries, incomplete tag-parent state, dispatch ordinal not
  bound to the active frame, and pending target cursor not bound to the invocation.
  A final review then found the suspended/async lifecycle conflation; `1df54390`
  removed the invalid resume variants and separated the lifecycle types.
- Two later full-boundary reviews found and closed ten more malformed-state classes:
  concrete effect ownership, same-entity movement conflict, cross-entity saved stacks,
  empty/out-of-range accumulator domains, non-ET numeric syntax, missing invocation
  ancestry, missing `gotomarker` route evidence, decision/task-shape mismatch and
  inconsistent exhaustion reasons. Each has a focused negative regression; valid
  prior-motion, runnable, suspended and complete shapes have positive regressions.
- A third full-boundary review closed six further gaps: current-attempt effect identity
  no longer collides with historical `gotomarker` effects, redundant accumulator
  exclusions canonicalize away, budget exhaustion retains its frontier, heterogeneous
  alert handlers fail closed, next-frame commands require a next-frame wake, and result
  alternatives are non-empty, deduplicated and permutation-invariant.
- All 21 review threads on `58ba5af0` were resolved and CodeRabbit reported no remaining
  S1 state-construction defect. Exact-head CI was still completing at this record point;
  this handoff-only evidence commit must receive a fresh full CI/review gate and quiet-
  window refresh before S2 starts.
- No production write, deploy, service restart, Python replacement, Lua change or
  other owner-gated operation was performed.
- Next item: pass the exact-head documentation gate, then implement S2 as one suspended
  cross-entity continuation without starting S3 behavior.

### 2026-08-13 - S2 single suspended cross-entity continuation

- S2 code commits: `7695bb7a` and `fcf14726`; the latter is the reviewed substantive
  head. `step_symbolic_schedule()` executes one source-ordered transition and remains
  deliberately narrower than the S3 shared-target/replacement runner and S4 bounded
  search.
- The accepted entry is one statically resolved `trigger`, one concrete selected
  target and different caller/target entities. The first transition runs the target
  through the existing single-event walker to its first temporal boundary, stores the
  exact boundary cursor/state and keeps the caller suffix runnable. Shared groups and
  same-entity replacement remain named S3 frontiers; multiple runnable or suspended
  tasks remain named S4 frontiers.
- `SuspendedContinuation.caller_suffix_completed` is canonical state identity. The
  target cannot re-enter while it is false. The next transition runs the exact caller
  suffix and only then sets it true; a direct premature-resume regression proves the
  inverse ordering is rejected.
- A `resetscript`/`halt` next-frame boundary re-enters its exact action and then runs
  the target suffix. The synthetic fixture proves caller-then-target effect order and
  reaches a task-empty `COMPLETE` state. Fixed waits use ordinary entity-pass order
  only when the target is explicitly proven unattached: a later entity gets
  `SAME_FRAME_LATER`, an already visited entity gets `NEXT_FRAME`, and a same-frame
  false re-entry advances only the wake constraint, not the script cursor. Completion
  time remains `wait_completion_time_unverified`, not an invented clock value.
- Missing/unknown tag-parent entry state produces `TAG_PARENT_ORDER_UNKNOWN` plus
  `tag_parent_state_unknown`; an attached relation outside S2 produces
  `tag_parent_order_not_modeled`. Movement completion remains
  `movement_completion_time_unverified`. None of these paths falls back to raw entity
  order or silently resolves an unknown.
- Review found one P1 at `7695bb7a`: deferred caller or resumed-target suffixes kept
  the blocker but discarded already executed prefix state. `fcf14726` retains
  `path.state`, appends source-bound effect records and places the terminal evidence
  frame at the exact later instruction. Regressions prove caller local accumulator 0
  remains 7, target local accumulator 1 remains 9, both `setstate` effects remain in
  source order and both terminal cursors identify the later wait.
- Exact local evidence at `fcf14726`: 171/171 scheduler plus possibility tests,
  311/311 map-geometry unit tests with one unrelated existing skip, and the complete
  repository suite at 4,532 passed / 97 environment or opt-in skips / 30 warnings.
  Ruff and `git diff --check` passed. Exact-head GitHub CI passed on Python 3.11 and
  3.13, CodeQL, Codacy, security, Docker, JavaScript/React and shell checks.
- CodeRabbit reviewed exact head `fcf14726`, confirmed the P1 closure and reported no
  remaining S2 blocker. All 21 existing review threads remained resolved. The Codex
  exact-head request had not returned at this record point; this documentation-only
  checkpoint must receive a fresh complete review/thread/CI/quiet-window gate before
  S3 starts.
- No installed-corpus denominator changes are claimed in S2. S5 still owns the exact
  20-map before/after measurement; no unknown disappeared from a denominator here.
- No production write, deploy, service restart, Python replacement, Lua change or
  other owner-gated operation was performed.
- Next item: pass this exact-head evidence gate, then implement S3 nested state return,
  shared concrete target order and same-entity replacement without opening S4 early.

### 2026-08-13 - S3 exact nested dispatch and shared-target state return

- Main sync commit: `c5d6d878`; S3 code/test commit: `9ebb1e2c`. The pause-time
  change from the prior base to `origin/main` at `d1c89142` was the `v1.35.0`
  release metadata merge only. It did not overlap the W5b implementation, tests or
  handoff paths; the branch was merged normally and no history was rewritten.
- `step_symbolic_schedule()` now propagates exact synchronous callee exit state into
  remaining concrete targets and caller guards. Entity-local `accum` values remain
  isolated by concrete entity while `globalaccum` mutations are shared in source
  order. The scheduler preserves every selected target, its ordinal, pending-dispatch
  cursor and invocation ancestry.
- Same-entity delivery follows the pinned `G_Script_ScriptChange` contract:
  synchronous completion restores the caller, temporal completion replaces it and
  abandons its suffix, and a replacement of an already suspended target retains only
  the old or new owner according to the exact sync-versus-false-return result. The
  trigger loop still visits later shared targets before reporting same-entity
  termination.
- Source-proven `alertentity` handlers and optional `kill` death handlers use the same
  transition path. Optional death delivery retains exact event/no-event alternatives;
  the no-event branch is emitted only after the complete kill projection reaches the
  expected dispatch frontier, so a fatal sibling target cannot be bypassed.
- Non-waiting `gotomarker` and `followspline` starts are now explicit path evidence,
  then become `SymbolicAsyncMovementLifecycle` state without delaying the script
  suffix. This fixed nested and resumed-suffix lifecycle loss. State-aware filtering
  removes the impossible prior-motion branch when no lifecycle exists and removes the
  impossible new-translation branch while one is active.
- A direct pinned-callback re-read corrected an over-broad S1 invariant:
  `gotomarker` and `followspline` reject a new translation while
  `SCFL_GOING_TO_MARKER` is set, but `faceangles` does not inspect that flag. A waiting
  `faceangles` continuation may therefore coexist with one asynchronous positional
  lifecycle; the regression distinguishes it from the two translational commands.
- Focused regressions cover synchronous local/global return, conditional taken and
  not-taken refinement, same-entity sync restoration and temporal abandonment, R1
  replacement ownership, concrete shared-target order, alert and optional-death
  dispatch, mixed fatal kill targets, direct/nested/resumed asynchronous movement,
  state-filtered prior/current movement and the `faceangles` source distinction.
- Local evidence at `9ebb1e2c`: 182 scheduler plus possibility tests passed before
  the final source corrections; the final scheduler suite passed 54/54, all 328
  map-geometry unit tests passed, Ruff and `git diff --check` passed, and the complete
  repository suite passed 4,549 tests with 97 environment or opt-in skips and 30
  warnings. The opt-in real-asset executor passed separately in 32.24 seconds.
- The frozen real-asset assertions remain unchanged: 2,790 entries, 5,174 paths,
  7,755 effects, 4,011 temporal boundaries, 473 caller replacements and the existing
  452 cross-entity temporal frontiers. S3 adds scheduler transitions and does not claim
  an S5 denominator reduction before exact bounded-search measurement.
- No production write, deploy, service restart, Python replacement, Lua change or
  other owner-gated operation was performed. Exact-head GitHub CI, external/self
  review, zero-thread and quiet-window gates remain open for this documentation head.
- Next item: pass the S3 exact-head gate, then implement S4 canonical visited-state
  search, cycle/budget frontiers and only footprint-proven reductions. Do not begin S5
  measurement or S6 graph verdicts early.

### 2026-08-13 - late S2/S3 review closure follow-up

- Code/test commit: `2cf41622`. A late Codex review against the earlier S2 evidence
  head produced five still-actionable findings even though their original diff anchors
  were outdated. They were treated as blockers rather than dismissed as stale.
- Main sync commits: `05feb195` and `e8de37c1`. While this follow-up was being verified,
  `origin/main` advanced from `d1c89142` to `66567ed8` through identity-merge Phase 3,
  the KIS modal fix and `v1.36.0` release configuration, then to the tagged
  `5f4ebc0e` release-metadata merge. None of the 17 changed main paths overlapped the
  scheduler, its tests or this handoff; main was merged normally and no history was
  rewritten.
- The scheduler now walks the caller's complete known tag-parent ancestor chain before
  using raw entity order. A direct or transitive target ancestor has already run and
  therefore wakes only on `NEXT_FRAME`; an absent/unknown caller relation or a cycle
  remains `TAG_PARENT_ORDER_UNKNOWN` with a named reason. It no longer fabricates a
  same-frame re-entry merely because the target has a later raw entity index.
- A target blocked before its first temporal boundary now retains the current target
  cursor, every remaining concrete target ordinal and the executable caller suffix,
  together with already executed accumulator/effect state. A direct blocker in the
  selected target event retains its exact instruction offset. If the blocker belongs
  to a deeper nested owner that the current `SymbolicFrame` contract cannot encode
  together with the outer pending dispatch, the state retains the complete outer
  group and state but adds `s3_blocker_frontier_identity_unresolved`; it does not
  silently label offset zero as exact. S4/S5 may not count that named frontier as
  resolved without extending the frame identity.
- The other three late findings were already substantively closed by `9ebb1e2c` and
  now have explicit disposition evidence: impossible current movement-start branches
  are filtered against active lifecycles; direct, nested and resumed non-waiting
  movement starts create source-bound lifecycle state; and a final-instruction trigger
  marks suspended target continuations with `caller_suffix_completed=True` rather than
  rejecting an empty suffix. The final-trigger case gained a dedicated regression in
  `2cf41622`.
- Exact local evidence after this follow-up and main sync: 60/60 scheduler tests,
  334/334 map-geometry unit tests and the complete repository suite at 4,557 passed /
  97 environment or
  opt-in skips / 30 warnings. Ruff, byte compilation and `git diff --check` passed.
  The full opt-in installed-asset suite passed 16/16 in 213.69 seconds with coverage
  instrumentation disabled. With coverage enabled, one projection test exceeded the
  generic 90-second timeout; its isolated no-coverage rerun passed in 24.06 seconds,
  and the complete no-coverage asset rerun confirmed this was instrumentation cost,
  not a semantic failure. PostgreSQL skips remain environment gates.
- No frozen installed-asset denominator was changed or reinterpreted. The prior
  2,790 entries, 5,174 paths, 7,755 effects, 4,011 temporal boundaries, 473 caller
  replacements and 452 cross-entity temporal frontiers remain the last exact corpus
  assertions. This follow-up changes scheduler transitions only.
- No production write, deploy, service restart, Python replacement, Lua change or
  other owner-gated operation was performed. The new exact head still requires full
  GitHub CI, review, zero-thread and five-minute quiet-window gates before S4 begins.

At every substantive commit, append:

- commit SHA and whether it changes contract, code, tests or evidence;
- focused and full verification results;
- exact corpus denominators and resource measurements if changed;
- newly resolved and newly introduced frontier reasons;
- review findings and their disposition;
- the next incomplete checklist item;
- any owner-gated operation prepared but not executed.

The next agent must begin at the first unchecked implementation wave and re-run every
source verification relevant to that wave. Chat history is not a substitute for the
pinned source, tests and measured artifacts recorded here.
