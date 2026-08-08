# W5a static stage asset foundation

Date: 2026-08-08

Scope: read-only ET/ET:Legacy map assets; no database writes, deploy, service restart or Lua change

Specification: `docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md`, section 9 W5

## Decision

W5 is split at the evidence boundary:

1. **W5a (this change):** independently resolve, parse and inventory `.script` and `.objdata`; expose possible
   effects and trigger-call edges without asserting that any transition happened.
2. **W5b (later):** map parsed effects to BSP objective/spawn/route identities and prove which static graphs are
   semantically defensible.
3. **W5c (later):** replay historical state only after event-family completeness is proven per tracker version.

This is not a full W5 closure. It is the parsing and provenance foundation needed to avoid building the replay on
regular expressions, filesystem proximity or guessed script semantics.

## Why this boundary is required

A map script describes transitions which *can* occur. It has no historical timestamp and cannot prove that a
transition happened in one round. The current telemetry contains timestamped carrier, construction and objective-run
records, but the writer is not yet a completeness oracle:

- carrier pickup depends on an `Item:` console pattern;
- carrier secure detection depends on English announcement substrings;
- returns and checkpoint captures use popup parsing and nearest-player attribution;
- generic `Repair:` writes `construction_complete` without a track name, then resolves a nearby constructible;
- `proximity_processed_files.capabilities` exists, but historical event-family completeness is not yet populated and
  proven for every required tracker version.

Relevant write paths are in `proximity/lua/proximity_tracker.lua:4531-4733`; parser section discovery begins at
`proximity/parser/parser.py:908`. These events are useful evidence, but consuming them as a complete state log before
an audit would convert missing callbacks and heuristic identities into false certainty.

## Engine compatibility research

The parser contract was checked against ET:Legacy primary source rather than inferred only from the installed maps:

- [`G_Script_ScriptParse`](https://github.com/etlegacy/etlegacy/blob/master/src/game/g_script.c) parses entity blocks,
  event headers and action stacks. While expecting a script name, it skips every case-insensitive `entity` token as
  an introducer. After a block name matches the concrete entity's `scriptName`, event and action names are accepted
  only when present in the engine's `gScriptEvents` and `gScriptActions` registries. Nonmatching blocks are skipped by
  balanced braces without registry validation. Event parameters remain arbitrary strings consumed until a token
  beginning with `{`; the registry does not impose parameter arity. Normal action arguments end at a physical newline.
- `set`, `create` and `delete` are the exception: their arguments are enclosed in a brace block.
- [`COM_ParseExt`](https://github.com/etlegacy/etlegacy/blob/master/src/qcommon/q_shared.c) defines quote and comment
  handling. Its regular-word path retains punctuation, including quotes and braces, until ASCII whitespace. Line
  comments preserve the newline boundary; block comments do not create an action boundary. The script parser tests
  the first byte of returned tokens for structural braces, including quoted or punctuation-attached brace tokens.
  An empty quoted token is indistinguishable from its empty control return and is rejected rather than represented
  as an argument.
- [`G_ScriptAction_SetMainObjective`](https://github.com/etlegacy/etlegacy/blob/master/src/game/g_script_actions.c)
  documents the target-name form while retaining compatibility handling for old scripts.
- `G_ScriptAction_Trigger` gives `self`, `global` and `player` special dispatch semantics, while the current
  `activator` branch is an explicit no-op. `self` is scoped to the concrete source entity, even when another block has
  the same script name. These targets are not ordinary script-name targets and are represented separately.

All 42 installed `wm_set_main_objective` calls use a numeric first argument. Current ET:Legacy source looks up the
first argument as an objective target and returns without changing state when that lookup fails; its numeric handling
is explicitly described as obsolete compatibility. The model therefore preserves the selector as a string and marks
all installed calls `legacy_numeric`, distinct from `target_name`. It does not assume that either the live build or an
older ET-compatible path applies numeric selection semantics, and it does not rewrite the assets.

## Implemented contract

`website/backend/map_geometry/stage.py` provides:

- a fail-closed lexer with source line/column provenance, ET newline semantics, line/block comments, quoted tokens,
  braced `set/create/delete` arguments, NUL rejection and ET token-length enforcement;
- exact current ET:Legacy event/action registry inventory, `entity` introducer handling and first-byte brace
  classification matching the engine parser;
- ASCII-only identifier folding and canonical ASCII integer gates prevent Python Unicode/numeric syntax from
  creating effects or trigger dispatch that ET's byte-oriented C paths would not recognize;
- structured `.objdata` records for map descriptions and per-team objective identities;
- explicit `primary`, `secondary`, `additional` or `unknown` classification, based only on the asset text;
- a structured map-script AST retaining every compatible entity/event/action argument plus a source-located issue
  for any entity whose remaining contents must stay opaque;
- typed projections for objective status, main objective, winner, autospawn, entity state, marker movement,
  entity alert and round end;
- trigger-call edges with direct/self dispatch, explicit `global`/`player` runtime dispatch and the current
  `activator` no-op, plus `resolved`, `missing`, `ambiguous`, `runtime_dispatch` or `no_op` results;
- independent W1 resolution of script and objdata before either file is read;
- `missing`, `ambiguous`, `invalid` and `resolved` load states. No partial model is returned for invalid input.

Every engine-recognized action remains in the AST even when it has no typed W5a projection. An unfamiliar event or
action makes only its containing `ScriptEntity` opaque: the AST records a source-located `registry_issue`, the parser
skips the rest of that block with the engine's balanced-brace rule, and the graph emits no node, effect or edge from
it. The whole asset is not marked invalid because ET:Legacy accepts an unfamiliar name in a block that matches no
live entity. W5b must make the mapped stage unknown if such a block is proven selected; until BSP identity mapping is
available, treating either all or none of these blocks as active would overstate the evidence.

Known-but-unprojected actions preserve evidence without inventing stage meaning for animation, accumulator, sound or
other commands outside W5a's approved semantic surface.

## Real-asset acceptance measurement

Command:

```bash
SLOMIX_RUN_REAL_ASSET_TESTS=1 \
  venv/bin/python -m pytest tests/integration/test_map_geometry_real_assets.py -q
```

The opt-in test re-scans `/home/samba/share/etmain`, independently resolves each asset, parses the exact hashed bytes
and freezes these totals:

| Measurement | Result |
|---|---:|
| BSP maps with independently resolved script + objdata | 20 / 20 |
| Stage assets parsed to a model | 20 / 20 |
| Script entities | 583 |
| Event handlers | 2,153 |
| Actions retained | 10,057 |
| Opaque entity blocks with registry issues | 0 |
| Distinct action command names | 52 |
| Objective descriptions | 250 |
| Explicit objective classes | 232 / 250 |
| Unknown objective classes | 18 / 250 |
| Typed possible effects | 2,929 |
| Trigger actions | 1,315 |
| Trigger edges with exactly one target handler | 1,304 / 1,315 |
| Trigger edges without a target handler | 11 / 1,315 |
| Trigger edges with multiple target handlers | 0 / 1,315 |
| Runtime-dispatch trigger edges in installed assets | 0 / 1,315 |
| Maps with complete internal trigger closure | 13 / 20 |
| Maps with explicit classes for every objective | 18 / 20 |

Typed effect inventory:

| Effect | Count |
|---|---:|
| Entity state | 1,728 |
| Objective status | 672 |
| Goto marker | 172 |
| Alert entity | 136 |
| Autospawn | 115 |
| Winner | 42 |
| Main objective | 42 |
| Round end | 22 |

The 18 unclassified descriptions are not parser failures:

- `etl_base`: 6 descriptions use headings such as `^7Radars` and `^7CP`, not primary/secondary/additional.
- `etl_ice`: 12 descriptions have no classification prefix.

They remain `unknown`. Objective number or wording is not accepted as a substitute classification rule.

All 42 main-objective effects are additionally marked `legacy_numeric`; none is approved as an effective target-name
selection until the live build and target mapping are verified.

## Unresolved trigger inventory

The following calls have no matching `trigger <parameter>` handler in the resolved script. They are retained as
`missing`; the graph does not invent a destination.

| Map | Script line | Target entity | Trigger |
|---|---:|---|---|
| `erdenberg_t2` | 192 | `main_gate` | `open` |
| `etl_braundorf` | 118 | `city_door` | `invisible` |
| `frostbite` | 337 | `spawnpost_damaged_model` | `enable` |
| `frostbite` | 566 | `axis_compost_damaged_model` | `enable` |
| `missile_b3` | 38 | `game_manager` | `setstatesoff` |
| `missile_b3` | 1269 | `truckbox_animation` | `attach` |
| `missile_b4` | 38 | `game_manager` | `setstatesoff` |
| `missile_b4` | 674 | `axisonlydoor2` | `open` |
| `missile_b4` | 1210 | `truckbox_animation` | `attach` |
| `supply` | 1110 | `truck` | `deathcheck` |
| `sw_goldrush_te` | 1208 | `tank` | `bot_active_check` |

Some may be harmless calls to entities with no handler; others may depend on a custom entity or override source not
present in the indexed input. W5b must cross-reference W3 entity `script_name`/`target_name` identities and the live
custom-entity inventory before classifying them. “Missing in this file” is the measured claim; “impossible at runtime”
is not.

## What is still unknown

This change intentionally does **not** provide:

- a historical stage at time `t`;
- selectable spawn sets at time `t`;
- live objective sets at time `t`;
- runtime transforms or collision states for doors, movers and constructibles;
- a mapping from every script string to one BSP entity/objective volume;
- a static-graph W5 acceptance verdict for all maps;
- historical unambiguous round-time coverage.

Consequently no proximity metric, W4 collision decision or rating weight may consume this model as live state yet.
The only safe outputs are the parsed possibility graph, its provenance and its explicit unknowns.

## Required next work

### W5b: semantic mapping and static coverage

1. Join script entity names and targets to W3 `script_name`, `target_name`, objective markers, objective volumes and
   spawn descriptions without fuzzy matching.
2. Treat zero or multiple candidates as unknown; publish every unresolved identity.
3. Model accumulator guards and ordered trigger effects only where their semantics are proven from ET:Legacy source.
4. Produce candidate **sets** of objectives, spawns and dynamic routes; do not select one convenient member.
5. Define a per-map “defensible static graph” gate and report its map denominator separately from parser coverage.

### W5c prerequisite: event-family completeness audit

Before replay code is written:

1. inventory tracker hashes/versions and non-null capability manifests across eligible files;
2. enumerate the transition families required by each mapped static graph;
3. verify callback coverage, identity, deduplication, ordering and round linkage in controlled fixtures;
4. publish completeness per event family and tracker version;
5. allow replay only for a round whose manifest covers every transition family needed by that map.

The replay then starts from a uniquely defined initial state, applies timestamped observed transitions in order and
becomes `unknown` at the first missing, duplicate, out-of-order or ambiguous transition. A later observation may
restore a known state only when it uniquely distinguishes all legal candidates. Final round outcome must never be
used to fabricate a transition timestamp.

## Verification performed

- W5a unit tests: 24 passed.
- Targeted map-geometry regression suite: 98 passed.
- Exact W5a real-asset acceptance: 1 passed, 7 deselected.
- Full real-map geometry/stage integration file: 8 passed in 136.09 seconds.
- Full repository suite: 4,158 passed, 75 skipped, 30 existing warnings in 50.38 seconds.
- Ruff on changed Python files: passed.
- `git diff --check`: passed.
