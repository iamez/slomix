# Post-revive trajectory gap measurement

**Date:** 2026-07-31

**Scope:** read-only dev measurement, no database writes, no Lua deployment

**Tool:** `scripts/analyze_post_revive_trajectory_gap.py`

**Verdict:** **material capture gap**

## Executive result

The current Lua writer stops a player's trajectory in `et_Obituary` and does
not start or resume one in `et_ClientSpawn(..., revived=1)`. The raw capture
history confirms that this is not a rare edge case:

| Measurement | Result |
|---|---:|
| Raw capture files inspected | 695 |
| Files passing identity, quality, capability, canonical dedup and exact-end checks | 618 |
| Observation window | 2026-03-03 20:25:43 UTC to 2026-07-29 21:54:19 UTC |
| Eligible rounds containing at least one human | 563 |
| Eligible human player-rounds | 3,527 |
| Human revive callbacks | 6,398 |
| Human-participant rounds with at least one gap | 537 / 563 (95.38%) |
| Player-rounds with at least one post-revive gap | 2,501 / 3,527 (70.91%) |
| Merged post-revive windows | 5,255 |
| Missing/unresolved trajectory time | 124,934,725 ms |
| Missing time / eligible human player-round time | **8.98%** |
| Median gap share among affected player-rounds | 9.80% |
| P95 gap share among affected player-rounds | 29.38% |
| Round time where a complete human-roster snapshot is unavailable | **41.32%** |

This closes the open measurement question in
`docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` §13.2b. The gap is material and
must be treated as a capture limitation, not a presentation caveat.

## What was measured

For each eligible human player in each included raw round:

1. A window starts at every row in the raw `REVIVES` section.
2. It ends at that player's next normal `PLAYER_TRACKS.spawn_time`, or at the
   exact in-game round end when there is no later normal spawn.
3. Overlapping windows for the same player are merged before summation.
4. The denominator is exact in-game round duration multiplied by each
   eligible human participant in that round.
5. A complete-roster snapshot is unavailable whenever at least one eligible
   human has an open merged window.

The window means **known-or-unresolved state and trajectory unavailability**.
It does not claim that the player stayed alive for the whole interval. A
repeat self-kill, world death or team-kill can occur inside it, but the
current writer emits no complete obituary stream from which to recover that
transition. Ending the interval only at the next normal tracked spawn is
therefore the conservative reconstruction rule.

## Source and identity rules

The measurement deliberately does not trust the currently stored
`player_track.round_id` links. Earlier inventory found source-start
disagreement in historical linked rows. Instead:

- Raw `REVIVES` is the primary and complete revive-callback source.
- Raw `KILL_OUTCOME outcome=revived` is only an enemy-kill subset cross-check.
- Raw files are matched to `rounds` by exact `(map, round, round_start_unix)`
  or exact `(map, round, round_end_unix)`.
- A match must resolve to exactly one canonical row.
- No canonical `rounds.id` may be represented by more than one raw capture;
  both candidates are rejected when that invariant is breached.
- The established round gate is applied:
  `round_number IN (1,2)`, `is_valid IS DISTINCT FROM FALSE`,
  `is_bot_round IS DISTINCT FROM TRUE`, and status is completed,
  substitution or NULL.
- Human players are filtered negatively; the only verified bot GUID prefix
  in this capture is `OMNIBOT`.
- A capture with no eligible human GUID contributes no human-roster round
  time, even when its historical `is_bot_round` flag was never backfilled.
- Tracker V5 is the minimum accepted revive-capable artifact. Git history
  shows V5 introduced both the revive callback collection and `REVIVES`
  output; V4 explicitly returned from revived spawns without recording one.
  Since the writer emits the optional section only when events exist, version
  capability distinguishes a supported zero from an unsupported absence.
- Exact in-game round end comes from completed
  `PLAYER_TRACKS.death_type=round_end` rows. A maximum 1 ms writer jitter is
  accepted.

Old captures can contain warmup-crossing lives on the same game clock.
Negative starts are clamped to `t=0`; lives ending at or before `t=0` are
ignored because they contribute no in-round state. This rule was verified
against the write path and is covered by unit tests.

### Capture exclusions

| Reason | Files |
|---|---:|
| No exact start/end match in `rounds` | 42 |
| Ambiguous exact canonical identity | 1 |
| Rejected by the established round quality gate | 4 |
| Tracker artifact predates verified revive capture (V4) | 19 |
| Missing/inconsistent exact in-game round end | 9 |
| Duplicate raw captures for one canonical `rounds.id` | 2 |
| **Total excluded** | **77** |

No included human player-round remained excluded for an invalid or
overlapping track interval after the warmup boundary rule was applied.

The measured input manifest hash is:

```text
ad5b99de5c7d736f33776d2d634e5f1b20707590948d43d3bf45d3a9582beb67
```

The hash covers ordered raw filenames, round identity fields and file sizes.
The report and JSON output contain no player names or GUID values.

## Independent subset cross-check

The enemy-kill-only outcome writer produced 5,964 revived outcomes. All 5,964
matched a raw revive callback on
`(exact round identity, victim GUID, outcome time)`; there were zero outcome
rows without a callback. Those outcomes covered 93.22% of all 6,398 human
revive callbacks.

That is the expected direction:

- `REVIVES` is complete for revive callbacks.
- `KILL_OUTCOME` omits reviveable deaths outside its enemy-kill gate.
- Reversing the source roles would silently lose 434 revives (6.78%).

## Distribution and endpoint checks

Of 6,398 raw revive windows:

- 5,811 ended at the next normal tracked spawn.
- 587 had no later normal tracked spawn and ended at exact round end.
- Merging repeated/overlapping revives reduced them to 5,255 player windows,
  preventing double-counting.

Across all eligible player-rounds, including zero-gap players, the median gap
share was 6.05% and nearest-rank P95 was 27.14%. Among affected player-rounds
the median was 9.80% and nearest-rank P95 was 29.38%.

## Consequences for §4

Historical replay can still expose partial positions, but it cannot claim a
complete roster at an arbitrary timestamp:

1. `get_player_positions()` must surface an explicit incomplete/unavailable
   result when `t` intersects a known post-revive window.
2. No interpolation may bridge a revive window. The endpoints do not prove
   where the player moved or when an unobserved repeat death occurred.
3. Complete-roster validation must exclude the affected 41.32% of eligible
   round time. Coverage must be published beside every result.
4. Grid, distance, path, adjacency and space-control candidates may be
   developed as infrastructure, but historical results must use only complete
   snapshots until an independently verified source reconstructs the gap.
5. W3/W4/W5 do not make the missing samples reappear. Their validation sets
   must carry this availability mask from the first API boundary.

## Consequences for §7

The quality layer cannot interpret missing revived players as absent, dead or
stationary:

1. Opportunity denominators requiring all-player geometry must use only
   complete snapshots.
2. A target/player trajectory intersecting a gap is ineligible for path,
   control, spacing, support-arrival or pressure attribution.
3. Coverage becomes part of every candidate's evidence. A score is withheld
   when its predeclared minimum complete-time support is not met.
4. The §8 within-round bootstrap still applies after this availability gate.
   This measurement defines coverage only; it approves no formula or weight.
5. Historical backtests must report how many rounds, player-rounds and
   opportunity windows the gap filter removed.

Because the loss is material, future capture work should resume/start a
trajectory on revive and add a complete, independent obituary stream for
every later death category. That touches the game server and remains
owner-gated: this work does not change or deploy Lua.

## Reproduction

From the repository root with the normal read-only dev DB configuration:

```bash
python scripts/analyze_post_revive_trajectory_gap.py \
  --input-dir local_proximity \
  --output /tmp/post-revive-gap.json
```

The script performs `SELECT` queries against `rounds` for quality gating and
writes only the requested local JSON file. It has no database mutation path.
`--skip-db-gates` exists for synthetic fixtures and explicitly degraded
exploration; it was not used for the reported result.

Focused verification:

```bash
pytest tests/unit/test_analyze_post_revive_trajectory_gap.py -q --no-cov
ruff check scripts/analyze_post_revive_trajectory_gap.py \
  tests/unit/test_analyze_post_revive_trajectory_gap.py
```

The focused suite covers normal-spawn and round-end endpoints, repeated
revive merging, warmup boundary normalization, bot exclusion, overlapping
life rejection, exact-end rejection, exact canonical gate matching, raw
section parsing (including pathless nine-field rows), round-scoped subset
matching and parse-exclusion accounting.
