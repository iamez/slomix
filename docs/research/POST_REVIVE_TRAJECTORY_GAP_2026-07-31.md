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
| Files passing identity, quality, clock, write-prefix, canonical dedup and exact-end checks | 197 |
| Observation window | 2026-06-22 19:49:55 UTC to 2026-07-29 21:54:19 UTC |
| Eligible rounds containing at least one human | 197 |
| Eligible human player-rounds | 1,252 |
| Human revive callbacks | 2,384 |
| Human-participant rounds with at least one gap | 196 / 197 (99.49%) |
| Player-rounds with at least one post-revive gap | 934 / 1,252 (74.60%) |
| Merged post-revive windows | 1,991 |
| Missing/unresolved trajectory time | 47,510,700 ms |
| Missing time / observed human participation time | **9.38%** |
| Median gap share among affected player-rounds | 10.00% |
| P95 gap share among affected player-rounds | 28.84% |
| Round time where a complete human-roster snapshot is unavailable | **43.75%** |

This closes the open measurement question in
`docs/PROXIMITY_SPIDER_WEB_SPEC_2026-07.md` §13.2b. The gap is material and
must be treated as a capture limitation, not a presentation caveat.

## What was measured

For each eligible human player in each included raw round:

1. A window starts at every row in the raw `REVIVES` section.
2. It ends at that player's next normal `PLAYER_TRACKS.spawn_time`, or at the
   exact in-game round end when there is no later normal spawn.
3. Overlapping windows for the same player are merged before summation.
4. Each player's denominator starts at their first in-round tracked spawn,
   not at round zero. It ends at an explicit disconnect or exact round end.
   This prevents a late join or reconnect from contributing time when that
   player was not present.
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

- Raw `REVIVES` is the primary revive-callback source only after the
  clock/write-prefix proof below.
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
- A human rejected for overlapping/invalid lives, an invalid revive or an
  orphan revive makes complete-roster state unprovable. Such a round is
  excluded from the complete-roster denominator rather than being evaluated
  from only its surviving players. The strict measured cohort contained zero
  such rounds.
- Tracker V5 is the minimum revive-capable artifact, but its coarse version
  header does **not** prove that the round clock was re-anchored. A read-only
  audit of the live game server verified the currently installed artifact at
  `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/proximity_tracker.lua`:
  mtime `2026-06-22 21:29:06.484508274 +0200`, SHA-256
  `16bf9fc46b33504e75c270fa129f8411b735fbfb91961b576acdee0a457257ff`,
  and the source contains `tracker.round.start_time = levelTime` in the
  `gamestate -> GS_PLAYING` transition. The measurement therefore rejects
  every capture whose `round_start_unix` predates
  `1782156546` (`2026-06-22 19:29:06 UTC`). The first included capture starts
  20 minutes 49 seconds later. This replaces the unsafe V5/V6-version
  inference with an independently checked artifact boundary.
- Historical files have no EOF marker and the downloader did not perform a
  stable-size/close handshake. Absence of an optional `REVIVES` section alone
  therefore cannot prove zero callbacks. The synchronous Lua writer emits
  `KILL_OUTCOME` only after it has evaluated and fully written the `REVIVES`
  branch. Inclusion now requires an on-disk `KILL_OUTCOME` section after
  `REVIVES` when the latter is present. This proves completion of the entire
  measurement-relevant write prefix, including a genuine zero when
  `REVIVES` is absent. All 200 raw captures after the artifact boundary have
  this proof; three then fail other quality checks, leaving 197.
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
| Revive-capable artifact but clock re-anchor not proven | 430 |
| Missing/inconsistent exact in-game round end | 2 |
| Missing/out-of-order later-section write-prefix proof | 0 |
| **Total excluded** | **498** |

No included human player-round remained excluded for an invalid or
overlapping track interval after the warmup boundary rule was applied.

The measured input manifest hash is:

```text
c5fe14e25ab692f80628b70a91e7d1b3b617a69eb4c5e86c62bcc5656a22e730
```

The hash covers each successfully parsed capture's ordered raw filename,
round identity fields and SHA-256 of its complete file bytes. Parse/identity
failures are counted separately and are not represented in this digest.
Same-length content changes to a parsed capture therefore change the manifest.
The report and JSON output contain no player names or GUID values.

## Independent subset cross-check

The enemy-kill-only outcome writer produced 2,228 revived outcomes. All 2,228
matched a raw revive callback on
`(exact round identity, victim GUID, outcome time)`; there were zero outcome
rows without a callback. Those outcomes covered 93.46% of all 2,384 human
revive callbacks.

That is the expected direction:

- `REVIVES` is complete for revive callbacks.
- `KILL_OUTCOME` omits reviveable deaths outside its enemy-kill gate.
- Reversing the source roles would silently lose 156 revives (6.54%).

## Distribution and endpoint checks

Of 2,384 raw revive windows:

- 2,178 ended at the next normal tracked spawn.
- 206 had no later normal tracked spawn and ended at exact round end.
- Merging repeated/overlapping revives reduced them to 1,991 player windows,
  preventing double-counting.

Across all eligible player-rounds, including zero-gap players, the median gap
share was 6.84% and nearest-rank P95 was 27.13%. Among affected player-rounds
the median was 10.00% and nearest-rank P95 was 28.84%.

## Consequences for §4

Historical replay can still expose partial positions, but it cannot claim a
complete roster at an arbitrary timestamp:

1. `get_player_positions()` must surface an explicit incomplete/unavailable
   result when `t` intersects a known post-revive window.
2. No interpolation may bridge a revive window. The endpoints do not prove
   where the player moved or when an unobserved repeat death occurred.
3. Complete-roster validation must exclude the affected 43.75% of eligible
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
  --clock-anchor-not-before-unix 1782156546 \
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
revive merging, late-join participation bounds, warmup boundary
normalization, bot exclusion, corrupt-player complete-roster rejection,
content-sensitive manifests, exact-end rejection, exact canonical gate
matching, clock deployment cutoff, later-section proof (including ordering),
raw section parsing, round-scoped subset matching and parse-exclusion
accounting.
