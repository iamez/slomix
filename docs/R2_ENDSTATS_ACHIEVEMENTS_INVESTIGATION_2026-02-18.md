# R2 Endstats/Achievements Investigation (2026-02-18)

Status: Investigated (no code changes in this session)  
Date investigated: 2026-02-18  
Scope: Round 2 missing/partial `endstats.lua` -> missing "achievements" output.

## Executive Summary

There are two distinct R2 failure modes:

1. `etl_adlernest` R2 produced **split endstats files**; bot ultimately posted the smaller file, so awards/achievements were missing.
2. `supply` R2 produced **no endstats file at all** upstream; bot had nothing to post.

These are separate root causes and should be fixed separately.

## Incident A: `etl_adlernest` R2 posted partial endstats (awards missing)

### What happened

- Webhook first processed `2026-02-18-215111-etl_adlernest-round-2-endstats.txt`:
  - parsed as `27 awards, 12 VS` (`logs/webhook.log:3433`, `logs/bot.log:96213`)
  - round unresolved, retry scheduled (`logs/webhook.log:3434`, `logs/webhook.log:3435`)
- Main R2 stats file arrived right after (`logs/webhook.log:3436` to `logs/webhook.log:3441`).
- A second endstats file appeared and was processed by polling:
  - `2026-02-18-215112-etl_adlernest-round-2-endstats.txt`
  - parsed `0 awards, 6 VS` and posted (`logs/bot.log:96316` to `logs/bot.log:96325`).

### Hard evidence

- Server gamestats has duplicate R2 endstats filenames:
  - `2026-02-18-215111-etl_adlernest-round-2-endstats.txt`
  - `2026-02-18-215112-etl_adlernest-round-2-endstats.txt`
  - plus stats file `2026-02-18-215113-etl_adlernest-round-2.txt`
  - (captured from `/home/et/.etlegacy/legacy/gamestats`)
- File contents prove split payload:
  - `local_stats/2026-02-18-215111-etl_adlernest-round-2-endstats.txt` -> 39 lines, includes awards + partial VS
  - `local_stats/2026-02-18-215112-etl_adlernest-round-2-endstats.txt` -> 6 lines, VS only
- DB confirms only the small file won:
  - `processed_endstats_files`: only `...215112...` success for `round_id=9874`
  - `round_awards` for `round_id=9874`: `0`
  - `round_vs_stats` for `round_id=9874`: `6`

### Root causes (A)

1. **Upstream file-splitting bug in `endstats.lua`**
   - `send_table()` builds filename from `os.date('%Y-%m-%d-%H%M%S-')` on each call (`endstats.lua:1380`)
   - and writes rows immediately (`endstats.lua:1382` to `endstats.lua:1393`)
   - `send_table()` is called multiple times per round:
     - awards table call (`endstats.lua:636`)
     - per-player VS table calls (`endstats.lua:684`)
   - If clock second changes between calls, one round is split across multiple files.

2. **Webhook retry logic drops follow-up attempts in this path**
   - retry scheduled once (`bot/ultimate_bot.py:4742` to `bot/ultimate_bot.py:4754`)
   - retry path calls `_schedule_endstats_retry()` again when unresolved (`bot/ultimate_bot.py:4815`)
   - but scheduler sees existing task and returns `"Retry already scheduled"` (`bot/ultimate_bot.py:4721` to `bot/ultimate_bot.py:4724`, `logs/webhook.log:3438`)
   - no later `retry 2/5` logged for this filename.

3. **Round-level dedupe favors whichever filename succeeds first**
   - if one filename already succeeded for same round, later one is skipped (`bot/ultimate_bot.py:4886` to `bot/ultimate_bot.py:4908`).
   - In this incident, the 6-line file succeeded first for round 9874.

## Incident B: `supply` R2 had no endstats file generated

### What happened

- Bot processed and posted `2026-02-18-221029-supply-round-2.txt` normally (`logs/webhook.log:3500` to `logs/webhook.log:3504`, `logs/bot.log:96644` onward).
- No webhook trigger for any `...supply-round-2-endstats.txt`.
- No polling-detected endstats file for supply R2.

### Hard evidence

- Server gamestats list for 2026-02-18 supply:
  - `2026-02-18-220154-supply-round-1-endstats.txt`
  - `2026-02-18-220156-supply-round-1.txt`
  - `2026-02-18-221029-supply-round-2.txt`
  - **no** `...supply-round-2-endstats.txt`
- `etconsole.log` around R2 end shows:
  - `Exit: Allies Surrender` (`/home/et/.etlegacy/legacy/etconsole.log:5078`)
  - weaponstats lines emitted (`...:5110` to `...:5115`)
  - **no** `Endstats:` lines afterward (checked window around this segment)
- DB impact:
  - `round_id=9877` (`supply` R2) has no `processed_endstats_files` success row
  - `round_awards=0`, `round_vs_stats=0`

### Likely root cause (B, upstream in `endstats.lua`)

`endstats.lua` generation requires a fragile state-machine path:

1. exact exit text match to set `kendofmap=true` (`endstats.lua:796` to `endstats.lua:807`)
2. enough parsed `WeaponStats` to satisfy `endplayerscnt == tblcount` (`endstats.lua:762` to `endstats.lua:790`)
3. delayed callback to `topshots_f(-2)` (`endstats.lua:1108` to `endstats.lua:1112`)
4. file writing inside `send_table` (`endstats.lua:1382` to `endstats.lua:1393`)

When this chain breaks, no endstats file is written and bot has nothing to ingest.

## About the "R1 usually needs 1/5 retries" observation

Confirmed: this is typically ordering/race, not corruption.

- Endstats often arrives before main stats row exists, so first attempt cannot resolve round id.
- Bot schedules retry and succeeds once stats import is done.
- Example on 2026-02-18:
  - supply R1 retry scheduled (`logs/webhook.log:3467`)
  - then successful endstats post (`logs/webhook.log:3479`)

## Fix Plan (next session, no changes made now)

### Priority 1: Make endstats file generation atomic per round

`endstats.lua`:
- generate one stable filename once per round-finalization, not per `send_table()` call.
- append all awards + all VS rows to that single file.
- remove timestamp-from-now behavior inside `send_table()`.

### Priority 2: Hardening in `endstats.lua` state machine

- replace exact equality checks on exit strings with robust matching (`startswith`/pattern).
- add structured logs for:
  - `kendofmap` set/not set
  - `tblcount`, `endplayerscnt`
  - `eomap_done` and `topshots_f(-2)` invocation.
- ensure endplayers counting uses reliable connected/team criteria.

### Priority 3: Fix webhook retry self-block

`bot/ultimate_bot.py` retry flow:
- allow `_retry_webhook_endstats_link()` to schedule next attempt from within active retry task.
- or clear current task marker before re-scheduling.
- verify attempts progress `1/5 -> 2/5 -> ...` when unresolved persists.

### Priority 4: Prefer richer duplicate file when same round maps to multiple filenames

Before final publish for a round:
- compare candidate payload quality (e.g., awards count + vs count + bytes).
- prefer richer payload for same round_id.
- do not let sparse duplicate overwrite richer one.

### Priority 5: Add guardrails/alerts

- alert when R2 stats file is posted without matching endstats within N seconds.
- alert when duplicate endstats filenames appear for same map/round within short window.
- alert when endstats rows are `0 awards` for active 3v3/6-player rounds.

## Delegation-ready task breakdown

1. `endstats.lua` owner:
   - atomic filename design + state-machine logging + robust exit matching.
2. Bot pipeline owner:
   - retry scheduling fix + duplicate-quality selection + dedupe policy.
3. QA/ops owner:
   - replay stopwatch R1/R2 and surrender endings; validate one-file-per-round and full awards persistence.

## Validation checklist after fixes

1. For one full stopwatch map:
   - exactly one `*-endstats.txt` per round (R1 and R2).
2. R2 with surrender ending:
   - endstats file still generated and posted.
3. If endstats arrives early:
   - retries advance beyond attempt 1 when unresolved.
4. DB:
   - `processed_endstats_files` has expected successful filename per round.
   - `round_awards` and `round_vs_stats` populated for both rounds.
5. Discord:
   - R2 awards/achievements content appears (not VS-only empty-award embed).
