# Reinforcement clock validation

**Date:** 2026-07-31  
**Protocol:** `reinforcement-clock-v1`  
**Scope:** read-only dev PostgreSQL measurement plus production-code gating  
**Input manifest:** `12b7c15f8e3f234690db110ada1d50e239e8f2c056caf9b2e1997034b6e96a70`

## Decision

The clock can be reconstructed for a subset of historical round-team groups,
but internal agreement between `proximity_spawn_timing` rows is not enough.
Only clocks that also match independent normal `player_track.spawn_time_ms`
landing clusters may feed a consumer.

The previous live implementation was unsafe:

- `_implied_offsets()` quantised candidate offsets to 25 ms and selected the
  mode;
- one disagreeing row could therefore be hidden by a majority;
- `wave-cycles` and `clutch` consumed that result without independent spawn
  validation;
- unlinked rows could be mixed into an otherwise linked round.

The replacement fails closed. It never averages, quantises or selects a mode.
`wave-cycles` requires both team clocks to validate. Clutch detection receives
only each team's validated clock and skips unavailable teams.

## Frozen protocol

The constants were fixed in code before the final database query:

| Parameter | Value |
|---|---:|
| Timing observations per round-team | at least 3 |
| Internal rule | all intervals and all exact inferred offsets unanimous |
| Same-team spawn-cluster diameter | at most 250 ms |
| Independent landing clusters | at least 3 |
| Passing landing residual | at most 250 ms |
| Group pass rule | at least 90% of landing clusters pass |
| Confirmation start | 2026-07-28 |

The cutoff preserves the previously inspected data through 2026-07-27 as
discovery. The 2026-07-29 session is a chronological confirmation block that
was not used to choose the constants.

For a usable timing row:

```text
offset = (interval - time_to_next_spawn - kill_time) mod interval
```

The row must have exact `round_id`, `interval > 0`,
`time_to_next_spawn IS NOT NULL` and non-sentinel
`spawn_timing_score > 0`; kill time must be non-negative and
`time_to_next_spawn` must be in `(0, interval]`. Rounds pass the full quality
gate and bot players are excluded by both the `OMNIBOT%` GUID and `[BOT]%`
name conventions.

A qualifying independent callback is a later same-team player track after a
normal terminal obituary (`killed`, `selfkill`, `fallen`, `world` or
`teamkill`). Initial joins, negative starts, team changes, non-death terminal
states and every player-round containing overlapping lives are excluded.
Post-revive-gap starts remain real normal spawn callbacks, but are labelled
and separately tested below.

Clustering is bounded by the first callback in the cluster. It does not use
transitive single-linkage, so callbacks at 0, 200 and 400 ms with a 250 ms
tolerance cannot become one 400 ms-wide landing. The landing timestamp is the
integer median, and one player cannot contribute twice to a landing.

## Dataset and exclusions

The repeatable-read, read-only transaction observed:

| Table | Raw rows |
|---|---:|
| `proximity_spawn_timing` | 41,652 |
| `player_track` | 59,641 |
| `proximity_revive` | 7,982 |

Attribution filters removed:

| Reason | Rows |
|---|---:|
| Timing unlinked | 127 |
| Timing rejected round | 434 |
| Timing bot player | 7,181 |
| Track unlinked | 2,927 |
| Track rejected round | 425 |
| Track bot player | 6,728 |
| Revive unlinked | 1,088 |
| Revive rejected round | 73 |
| Revive bot player | 698 |

Among otherwise attributed human timing rows, the value gate rejected 1,435
non-positive intervals and 59 negative kill times. No row had a missing or
out-of-range positive-interval countdown.

Spawn qualification recorded 4,166 initial joins, 5,718 candidate transitions
belonging to ambiguous overlapping player-rounds, 213 negative starts and
three non-death terminal transitions. These are exclusions, not zero-valued
observations. No landing cluster contained the same player twice, so the
explicit duplicate-player clustering exclusion removed zero callbacks.

## Internal consistency correction

The ungated historical diagnostic now contains 1,405 round-team groups:

| Status | Groups |
|---|---:|
| Exact internally consistent | 1,317 |
| Inconsistent | 17 |
| Fewer than 3 usable rows | 71 |

All **17/17 inconsistent groups are bot-only**. Every usable observation in
those groups has an `OMNIBOT%`/`[BOT]%` identity. Some parent rounds predate
the `is_bot_round` backfill, so the per-player bot gate is what removes them.
They remain unavailable; this result explains the old inconsistency rather
than selecting one of its candidates.

After exact linkage, full round quality and per-player bot gates, 1,236
round-team groups remain. None is internally inconsistent: 1,167 are
unanimous and 69 have insufficient timing support.

## Independent validation results

| Result | Discovery through 07-27 | Confirmation from 07-28 | All |
|---|---:|---:|---:|
| Round-team groups | 1,200 | 36 | 1,236 |
| Internally consistent | 1,131 | 36 | 1,167 |
| Independently supported | 968 | 36 | 1,004 |
| Validated | 842 | **36** | 878 |
| Validation failed | 126 | **0** | 126 |
| Consistent but support-insufficient | 163 | **0** | 163 |
| Independent landing clusters | 14,000 | **502** | 14,502 |
| Independent spawn callbacks | 31,002 | **1,126** | 32,128 |
| Residual median | 25 ms | **25 ms** | 25 ms |
| Residual p95 | 7,353 ms | **25 ms** | 6,548 ms |
| Residuals within 250 ms | 89.54% | **100%** | 89.90% |

The old-data tail is real: 126 discovery groups fail and are not exposed.
The chronological confirmation is the stronger result: all 36 round-team
groups validate, and all 502 independent landing clusters are within the
frozen 250 ms tolerance.

### Sensitivity checks

- **Post-revive:** 4,037 supported spawn callbacks follow a known post-revive
  gap. Removing every landing containing one leaves 868 validated groups
  overall. In confirmation, 34 remain validated and two become
  support-insufficient; none fails.
- **Singleton/reconnect sensitivity:** retaining only landing clusters with at
  least two distinct players leaves 862 groups validated overall and all
  **36/36** confirmation groups validated. This is not the shipping rule, but
  shows that the confirmation result does not depend on one-player starts.

## Live proof

The new code was called directly against dev PostgreSQL for exact round
`11069` (`etl_adlernest`, 2026-07-29 R1):

| Team | Interval | Offset | Landing clusters | Pass ratio |
|---|---:|---:|---:|---:|
| Allies | 20,000 ms | 4,000 ms | 12 | 100% |
| Axis | 30,000 ms | 4,000 ms | 9 | 100% |

The endpoint returned `status=ok`, protocol `reinforcement-clock-v1`, a
318,150 ms track-derived round length, 23 cycles and zero excluded unlinked
kills. This also verifies that the ledger now covers the round boundary
instead of truncating at the last kill. The clutch endpoint on the same round
returned one exact round, zero skipped-no-clock rounds and four player results.
These were read-only calls; no database row or live service changed.

## Known limits

1. A client disconnect that closes an active track is excluded by its
   `disconnect`/`shutdown` terminal event. A disconnect while already in limbo
   has no separate historical lifecycle row, so a later reconnect after an
   otherwise normal obituary cannot always be identified directly. The
   multi-player-only sensitivity above bounds this risk for confirmation, but
   future telemetry should record explicit connect/disconnect callbacks.
2. Historical validation does not make the exact enemy clock player knowledge.
   It is server/oracle truth unless a recipient-specific observable cue exists.
3. A clock with no kills, fewer than three usable timing rows, fewer than three
   independent landing clusters, failed residuals or ambiguous round identity
   remains null.
4. The 126 failed discovery groups must not be repaired by choosing a mode.
   Their cause can be investigated separately; until explained, null is the
   correct value.

## Reproduction

```bash
set -a
source .env
set +a
python -m scripts.analyze_reinforcement_clock \
  --output /tmp/reinforcement-clock-evidence.json
```

The script starts a `REPEATABLE READ, READ ONLY` transaction and publishes a
content-sensitive SHA-256 manifest over all fetched rows. Unit tests cover
unanimity, sentinel filtering, overlaps, post-revive labelling, bounded
clustering, circular residuals, confirmation splitting and the live
fail-closed modal-conflict path.
