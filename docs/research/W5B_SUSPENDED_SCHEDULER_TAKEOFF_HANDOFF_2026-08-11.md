# W5b suspended-continuation scheduler: takeoff and handoff

Date: 2026-08-11

Status: implementation contract; documentation-only takeoff

Base: `origin/main` at `d6136cdd994870fddf4e4d0ff1968eb91418e497`

Predecessor: `docs/research/W5B_SEMANTIC_MAPPING_TAKEOFF_HANDOFF_2026-08-10.md`

Installed-asset manifest:
`86ddd0ec23b3c6120136195af34aa633ad249eb358ea0fb6cd6e490dd81b220d`

Pinned ET:Legacy reference:
`732518efb1c479dcd29b13361f30a2e92df1cf2a`

## Executive decision

W5b needs one more static-analysis increment before its Phase 5 per-domain graph gate:
a bounded scheduler for suspended cross-entity continuations. The current executor
correctly refuses to combine a delayed callee with an immediate caller, but this leaves
301 cross-entity temporal frontiers. Measured frontier classification shows that 244 of
those 301 frontiers hide at least one required objective, spawn or dynamic-route domain.
Deferring all 301 would therefore make the Phase 5 verdict knowingly incomplete.

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
2. Enumerate only source-defensible order alternatives between runnable caller work and
   relevant suspended work.
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

## Proposed scheduler model

The following names communicate the required information. They are not frozen APIs
until S0 proves the transition contract.

```python
@dataclass(frozen=True, slots=True)
class SymbolicFrame:
    node_id: str
    entity_index: int
    instruction_offset: int
    call_stack: tuple[tuple[int, str], ...]
    origin: str


@dataclass(frozen=True, slots=True)
class SuspendedContinuation:
    frame: SymbolicFrame
    boundary_command: str
    boundary_line: int
    wake_constraint: str
    effect_footprint: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SymbolicScheduleState:
    accumulator_state: SymbolicAccumulatorState
    runnable: tuple[SymbolicFrame, ...]
    suspended: tuple[SuspendedContinuation, ...]
    effects: tuple[StageEffectProjection, ...]
    provenance: tuple[str, ...]
    ordering_decisions: tuple[str, ...]
    unknown_reasons: tuple[str, ...]
```

Required properties:

- Every frame identifies one concrete entity, one ordered program and one instruction
  offset.
- A frame's call/replacement provenance cannot be reconstructed from line number alone.
- Suspended continuations are separate tasks. Their state is not copied into an
  immediate caller result before they run.
- Accumulator state is shared exactly according to the existing local/global contract.
- Effects preserve source entity and program provenance.
- Collections have a deterministic canonical order independent of Python set/dict
  iteration.
- Unknown reasons are part of output identity, not log-only text.

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

1. freeze its next legal continuation as `SuspendedContinuation`;
2. keep its state at the boundary, without applying unexecuted mutations or effects;
3. keep the caller suffix or remaining shared targets independently runnable where the
   source contract permits;
4. enumerate only the source-permitted choice of which runnable task advances next;
5. record that choice in ordering provenance;
6. resume the suspended task only through a source-proven wake transition.

The scheduler must never implement this as `caller_state | eventual_callee_state` or as
an unordered union of effects.

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

### S1 - immutable state and canonicalization

1. Add scheduler-owned frame, continuation, state, decision and result types.
2. Validate index/program ownership and offsets at construction boundaries.
3. Define deterministic ordering and canonical visited keys.
4. Add one global positive work budget with named exhaustion.

Exit: type/unit tests prove equal semantic states canonicalize equally, meaningful
differences do not collide, and malformed ownership fails loudly.

### S2 - one suspended cross-entity continuation

1. Run one caller and one different-entity target to the first temporal boundary.
2. Preserve caller suffix and suspended target separately.
3. Enumerate only source-permitted next-task alternatives.
4. Resume the target with exact state and provenance.

Exit: a synthetic map proves both legal orderings where permitted, suppresses an
illegal ordering and retains a frontier where wake semantics are unverified.

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
2. Publish before/after tables for all 301 cross-entity temporal frontiers.
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
- caller suffix before callee wake where source permits it;
- callee completion before later caller work where source permits it;
- absence of an ordering the source does not permit;
- synchronous nested local-accumulator mutation controlling a later caller guard;
- cross-entity local accumulators remaining isolated;
- suspended `globalaccum` mutation changing a later task's guard;
- contradictory refined domains being removed;
- unknown entry state never becoming zero implicitly;
- same-entity synchronous restoration;
- same-entity temporal caller abandonment;
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
| Starting denominator | 301 cross-entity temporal frontiers; 244 domain-relevant |
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
- [ ] Commit and push the documentation-only takeoff.
- [ ] Open the draft PR and record its URL/head here.
- [ ] Complete S0 source verification.
- [ ] Complete S1 immutable state/canonicalization.
- [ ] Complete S2 single suspended continuation.
- [ ] Complete S3 nested state/shared-target handling.
- [ ] Complete S4 bounded search/reduction.
- [ ] Complete S5 exact corpus evidence.
- [ ] Complete S6 Phase 5 static graph gate, or split it into a successor PR with an
  explicit handoff.
- [ ] Complete all review and merge gates.

## Handoff record

At every substantive commit, append:

- commit SHA and whether it changes contract, code, tests or evidence;
- focused and full verification results;
- exact corpus denominators and resource measurements if changed;
- newly resolved and newly introduced frontier reasons;
- review findings and their disposition;
- the next incomplete checklist item;
- any owner-gated operation prepared but not executed.

The next agent must begin at S0 and re-run source verification. Chat history is not a
substitute for the pinned source, tests and measured artifacts recorded here.
