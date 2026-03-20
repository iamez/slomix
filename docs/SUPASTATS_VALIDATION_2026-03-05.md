# Supastats Validation 2026-03-05

Date checked: `2026-03-06`
Session validated: `2026-03-05`
Canonical session id: `95`
Compared screenshots: `docs/archive/root-artifacts/screenshots/supastats9.png` through `docs/archive/root-artifacts/screenshots/supastats13.png`

## What validates cleanly

These screenshot fields map directly to canonical repo data and matched on the March 5 session:

- `DG` -> `damage_given`
- `DR` -> `damage_received`
- `K` -> `kills`
- `G` -> `gibs`
- `SK` -> `self_kills`
- `D` -> `deaths`
- `KD` -> `kills / deaths`
- Team totals for the same fields
- Per-map `DPM`
- Per-map `Kills`
- Round durations when sourced from `lua_round_teams.actual_duration_seconds`

The per-map validation must use the exact ordered R1+R2 match pairs, not `GROUP BY map_name`, because `te_escape2` appears three times in the same session.

March 5 ordered match pairs:

1. `etl_adlernest`
2. `supply`
3. `etl_sp_delivery`
4. `te_escape2` pair 1
5. `te_escape2` pair 2
6. `te_escape2` pair 3
7. `et_brewdog`
8. `sw_goldrush_te`

## Where the false mismatches came from

### `A`

The March 5 screenshot proves that `A` is still unresolved.

What we know:

- the repo parser maps Lua `TAB[12]` / `topshots[3]` to `kill_assists`
- those values are stored in `player_comprehensive_stats.kill_assists`
- the screenshot `A` values in `supastats12.png` do not equal the canonical March 5 `kill_assists` totals

March 5 examples:

- `bronze`: screenshot `48`, canonical `kill_assists 44`
- `carniee`: screenshot `46`, canonical `40`
- `SuperBoyy`: screenshot `46`, canonical `42`

Conclusion:

- the screenshot `A` column is not yet proven to be the same metric as repo `kill_assists`
- it may be an upstream assist formula with different semantics, or a metric that the repo does not currently ingest

Validation rule:

- do not mark screenshot `A` as a repo math failure yet
- compare repo `kill_assists` separately
- treat screenshot `A` as `unresolved / upstream-only` until the source formula is traced

R0 caveat:

- do not validate assists from `round_number = 0` match-summary rows
- on session `95`, `R1+R2` and `R0` agree for most `kills`, but they diverge for `kill_assists`
- example: `bronze` has `R1+R2 kill_assists = 44` vs `R0 kill_assists = 22`
- this means future screenshot validation should continue using ordered `R1+R2` session scope, not `R0`

### `TMP`

`supastats TMP` is not the same as the repo's legacy `tmp_pct`.

Current repo behavior:

- `tmp_pct` in the API is a backward-compat alias for `alive_pct`
- screenshot `TMP` aligns much better with Lua-backed `played_pct_lua`

Validation rule:

- for supastats compatibility, use:
  - `supastats_tmp_pct = played_pct_lua ?? played_pct`
  - `supastats_tmp_ratio = supastats_tmp_pct / 100`
- do not compare screenshot `TMP` against `tmp_pct` or `alive_pct`

### `EFFORT`, `EXPECTED`, `PERF`

These do not currently exist as canonical repo-backed metrics.

What this means:

- they are not implemented in the bot, API, or website as a shared formula
- they cannot be validated numerically from repo code alone
- comparing them today as if they were canonical repo stats creates false failures

Validation rule:

- mark these as `external-only / unverified` until the upstream formulas are imported into the repo

## March 5 concrete check

Summary totals from `supastats12.png` matched the canonical session very closely.

Examples:

- `bronze`: screenshot `31.2K DG`, `164 K`, `141 D`, `TMP 0.81`
  canonical `31247 DG`, `164 K`, `141 D`, Lua played `% 81.5`
- `carniee`: screenshot `31.7K`, `140 K`, `135 D`, `0.78`
  canonical `31698`, `140`, `135`, Lua played `% 78.7`
- `SuperBoyy`: screenshot `25.9K`, `134 K`, `146 D`, `0.76`
  canonical `25861`, `133`, `146`, Lua played `% 76.7`

Team totals also matched:

- screenshot `Team red`: `87.2K DG`, `79.6K DR`, `424 K`
- canonical Team A: `87187 DG`, `79563 DR`, `424 K`

## Canonical comparison contract going forward

Use this mapping when validating new supastats images:

- `DG` -> `damage_given`
- `DR` -> `damage_received`
- `K` -> `kills`
- `A` -> unresolved / upstream-only
- `G` -> `gibs`
- `SK` -> `self_kills`
- `D` -> `deaths`
- `KD` -> `kd`
- `TMP` -> `supastats_tmp_pct` or `supastats_tmp_ratio`
- `EFFORT` -> external-only
- `EXPECTED` -> external-only
- `PERF` -> external-only

## Fixes applied

To reduce future validation drift:

- session-detail payload now exposes canonical `kill_assists`
- session-detail payload now exposes `supastats_tmp_pct`
- session-detail payload now exposes `supastats_tmp_ratio`
- canonical validator script added: `scripts/validate_supastats_session.py`

Run it against the locked March 5 fixture with:

```bash
python3 scripts/validate_supastats_session.py \
  --session-date 2026-03-05 \
  --fixture tests/fixtures/supastats_validation_2026-03-05.json
```

This does not solve `EFFORT`, `EXPECTED`, or `PERF`. Those still need the real upstream formula source before they can be treated as canonical.
