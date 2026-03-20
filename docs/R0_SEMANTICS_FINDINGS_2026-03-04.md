# R0 Semantics Findings (Deferred Work)

Date: 2026-03-04  
Status: documented, deferred  
Scope: `round_number=0` (R0) behavior vs `round_number IN (1,2)` (R1/R2)

## Executive Summary

We confirmed that `R0` currently has mixed semantics and cannot be treated as a universally correct "R1+R2 total row" for all fields.

- Some fields in `R0` behave like map totals (`R1+R2`).
- Some fields in `R0` behave like `R2-only`.
- A few fields are mixed/inconsistent depending on map/history/import path.

This explains long-standing confusion where some stats match external reports and others do not.

## Primary Root Cause

`R0` is created from Round 2 cumulative payload in parser/import flow:

- `bot/community_stats_parser.py` attaches `match_summary` and sets `round_num = 0`.
- Importer stores that as `round_number = 0`.

At the same time, parser uses `R2_ONLY_FIELDS`, where several objective/support counters are explicitly treated as R2-only behavior.

Result: `R0` row contains a semantic mix rather than one coherent aggregation model.

## Key Evidence Collected

### 1) Data shape and coverage

- `rounds` counts:
  - `round_number=0`: `587`
  - `round_number=1`: `633`
  - `round_number=2`: `625`
- `player_comprehensive_stats` rows tied to `R0`: `3926`

Implication: even basic coverage differs (`R0` is not present for all `R2` rows).

### 2) Full DB comparison (`R0` vs paired `R2`)

Across all paired rows (`587` map pairs, `3926` player rows), many key fields are not equal between `R0` and `R2` (expected for total-like fields), while some fields are often equal.

### 3) Recent-period semantic check (`>= 2026-01-30`)

Using strict `R0`/`R1`/`R2` triples (45 map triples, 287 player triple-rows):

- `R0 ~= R1+R2` (very high):
  - `kills`: `99.7%`
  - `deaths`: `99.3%`
  - `damage_given`: `99.3%`
  - `damage_received`: `99.3%`
- `R0 ~= R2` (very high):
  - `kill_assists`: `100%`
  - `denied_playtime`: `97.9%`
  - `times_revived`: `100%`
  - `revives_given`: `100%`
  - `headshot_kills`: `100%`
- Mixed/problematic:
  - `time_played_seconds`: `R0==R1+R2` only `47.4%`, `R0==R2` `4.9%`

Conclusion: `R0` is hybrid by field.

### 4) Session-specific validation (2026-03-03, `gaming_session_id=94`)

- `denied_playtime` ingestion was verified exact for real rounds (`R1/R2`):
  - Raw files vs DB: `96/96` exact matches, `0` mismatches.
- SuperBoyy denied total:
  - Raw: `1122`
  - DB (`R1+R2`): `1122`

This confirmed `time_denied` pipeline is correct in `R1/R2`; confusion came from summary semantics, not raw ingestion.

## Why Assist Mismatch Happened

Observed mismatch was amplified by comparing against `R0` in one analysis path.

- `kill_assists` in current behavior is effectively R2-like inside `R0`.
- Correct session total for assist comparisons must use `SUM(...)` over `round_number IN (1,2)`.

## Impacted/Relevant Code Paths

Creation/write paths:

- `bot/community_stats_parser.py` (`match_summary` / `round_num=0`)
- `postgresql_database_manager.py` (imports/stores `round_number=0`)
- `bot/ultimate_bot.py` (legacy/parallel summary insertion logic)

Reader paths with direct `R0` dependency:

- `bot/services/automation/ssh_monitor.py` (match summary query uses `round_number=0`)
- `bot/services/round_correlation_service.py` (`summary_round_id` linkage, optional metadata linkage)

Most session APIs and views already aggregate by explicit session round IDs (`R1/R2`) and are less exposed to this issue.

## Confirmed Safe/Unsafe Assumptions

Unsafe:

- "Anything reading `R0` can just read `R2`."

Reason: combat totals (`kills/deaths/damage`) would become wrong.

Conditionally safe:

- Replacing `R0` with `R2` for fields that are confirmed R2-like (e.g., assists/denied in current behavior) may work, but only field-by-field.

## Deferred Recommendation (for future implementation)

Use staged migration, not hard removal:

1. Keep current `R0` writes temporarily.
2. Add a canonical match summary computation based on `R1+R2` with explicit per-field semantics.
3. Dual-run old vs new summary and log deltas.
4. Move readers to new summary path.
5. Disable new `R0` writes behind flag.
6. Remove/archive historical `R0` data only after soak period.

This avoids regressions and keeps rollback straightforward.

## Notes for Future Work

- Migration should be "expand then contract" with guardrails.
- Do not treat `R0` as a single truth source for all metrics.
- Keep `time_denied` logic untouched unless tests prove a defect in `R1/R2` path.

