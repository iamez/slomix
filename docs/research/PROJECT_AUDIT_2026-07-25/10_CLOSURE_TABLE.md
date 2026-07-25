# Closure table — audit remediation stack

Prepared by: Claude (Opus 5) · Date: 2026-07-25
Base: `main` at `6253fb6` (v1.27.0) · Owner granted merge authority for this batch.

Every row maps a Codex finding to the commit that closed it, the test that
pins it, and the runtime evidence. Rows without reproducible evidence are
marked OPEN.

---

## 1. Head SHAs at time of action

| PR | Branch | Head at close | Codex snapshot head | Changed since review? |
|---|---|---|---|---|
| #546 | `fix/kis-gsid-backfill` | merged `fc82c11` | `656df3c` | yes — re-reviewed, 0 open |
| #547 | `fix/kis-v4-recompute` | `9b6e92c0a63c` | `fd9044f` | yes — hardened after review |
| #548 | `fix/proximity-serving-layer` | `3b3938f` | `3b3938f` | no |
| #549 | `fix/data-integrity-dedup` | see PR | `00a3c27` | yes — re-reviewed, 0 open |
| #550 | `chore/audit-housekeeping` | `0e303d4` | `0e303d4` | no |
| #551 | `docs/vision-design-2026-07` | `8fc2ed8`+ | `5fd56fd` | yes — docs only, review withheld |
| #552 | `feat/objective-zones-missing-maps` | merged `1a80736` | `dcc2589` | yes — re-reviewed, 0 open |
| #553 | `fix/invalid-scoring-terms` | see PR | `8077ad3` | yes — re-reviewed |
| #554 | `fix/narrative-baseline-cutoff` | new | n/a | new (DATA-01) |

---

## 2. Finding → commit → test → evidence

| # | Finding (severity) | Commit | Test | Runtime evidence | Residual risk |
|---|---|---|---|---|---|
| KIS-01 | #546 delete/warm scope mismatch (HIGH) | `9cfc939` | `test_kis_cache_invalidation_hook.py` — two-sessions-one-date, multi-gsid warm fan-out, no-gsid fallback, warm params | warm now sends `gaming_session_id`, avoiding the story-scope 409 that followed a successful delete | residual in-flight-compute race unchanged (pre-existing, documented in `_invalidate_kis_cache`) |
| KIS-01b | NULL-gsid rows deleted across sessions (HIGH, P1) | `de9c213`+ | same file — delete predicate asserts round-key EXISTS clause | 2026-03-25 (4 sessions): old predicate matched **1,128** NULL rows, new matches **74**, spares **1,054** | rows matching no resolvable round are never deleted and never rescored — by design |
| KIS-01c | 064 diverged from canonical gate | `de9c213` | `test_kis_gsid_stamping.py` — asserts `round_number IN (1,2)` and COALESCE join | migration re-applied on dev, 0 further rows; no R0 rows existed (19,172 R1 + 14,905 R2, 0 R0) | legacy rounds with no start time now attributable; previously skipped |
| FORM-01a | SSR credited retired push signal (HIGH) | `12e84cc` | `test_ssr_service.py` fixture dispatches on the new predicate | `situ` filter no longer contains `is_during_push` | — |
| FORM-01b | SSR formula changed without a version bump | `8dcfbbd` | `test_ssr_service.py` pins `ssr-v0.3` | registry imports live, follows automatically | — |
| FORM-01c | Player radar duplicated both retired terms | `12e84cc` | — (endpoint shape asserted via registry test) | awareness = escape-rate only; mechanical → `unscored`; `player-radar-v2` | — |
| FORM-01d | React radar hardcoded 5 axes (P1) | `8dcfbbd` | `npx tsc --noEmit` clean | chart rendered **nothing** for every player before the fix | Vitest coverage for the component not added |
| FORM-01e | `power-v2` published by two different formulas | `8dcfbbd`+ | registry contract test | radar → `player-radar-v2` + `axis_definitions_from` | — |
| FORM-01f | Retired-term sweep | `12e84cc` | — | remaining `is_during_push` consumers report COUNTS/context only, never score | — |
| INT-02 | #548 ↔ #553 semantic conflict (HIGH) | `796b00a` (branch `integ/548-553`) | `test_proximity_serving_layer_audit.py` — 4-axis composite + surviving #548 semantics | conflict resolved by rule; full suite 3,703 pass | **not yet landed** — see §4 |
| INT-02b | Gate is attribution, not quality | `796b00a` | attribution bucket split + coverage denominator | live DB 2026-07-01+: 17,229 total / 15,894 linked-valid / 0 invalid / **1,335 unlinked (92.2% coverage)** | compatibility mode keeps unknown rows; strict mode not implemented |
| PARSER-01a | #549 stale PR description | PR body edit | — | description now states the host-local contract and why the tz change was reverted | — |
| PARSER-01b | No direct migration/parser tests | `5e2431c` | `test_migration_065_dedup.py` (11 tests) | — | no live-fixture integration test (unit-level SQL assertions only) |
| PARSER-01c | Orphan dedup ignored `round_number` | `759a5cd` | same file, count assertion | — | — |
| PARSER-01d | `DO NOTHING` discarded resolved links | `759a5cd` | link-refresh clauses + no-measurement-update assertion | live DB, rolled-back txn: unlinked insert then replay with `round_id=11013` → one row, `round_id=11013` | — |
| PARSER-01e | Unguarded legacy date cast | latest on branch | — | rolled-back txn: `'BROKEN-DATE'` → NULL, `'2026-07-21 20:00'` → date | dev has 0 non-ISO rows; prod unverified |
| ZONE-01 | #552 body vs diff, invariants, EOF | `feca16f` | `test_objective_zone_catalog.py` (7 tests) | catalog 15 maps / 74 objectives; gate passes | 4 low-play maps deliberately deferred (cabinet dedup, transforms, curated etl_supply) |
| KIS-02 | #547 recompute controls | `9b6e92c` | `test_kis_recompute_controls.py` (7 tests) | dry-run default; `--apply` without backup refuses; without `--expect-db` refuses; mismatched target aborts pre-connect | **#547 not yet rebased onto v5** — see §4 |
| DATA-01 | Narrative baseline cutoff | `#554` | `test_narrative_baseline_cutoff.py` (3 tests) | cutoff = `scope.gaming_session_id` | — |
| DOC-01 | #551 design threads | `8fc2ed8` | — | 13 threads closed with decisions (units, leakage, survivorship, capability, versioning) | **review withheld** — fresh Codex review required |

---

## 3. Merged

In the order the audit package required. Each merged only with 12/12 checks
green AND zero unresolved review threads at that moment.

| # | PR | Merge commit | Why this position |
|---|---|---|---|
| 1 | #546 KIS gsid backfill | `fc82c11` | foundation — migration 064, everything else reads the column |
| 2 | #552 objective zones | `1a80736` | must precede any recompute so brewdog kills score |
| 3 | #549 identity + dedup | `7aff22e` | migration 065, independent of the formula work |
| 4 | #553 retired scoring terms | `7d6a2d2` | establishes kis-v5 / power-v2 before anything consumes them |
| 5 | #548 proximity serving sweep | `ab2809d` | carried the semantic integration with #553 |
| 6 | #547 historical recompute | `3a92cd0` | rebased last of the formula set, so it targets kis-v5 + current zones |
| 7 | #550 housekeeping | `25e7ffb` | registry/docs describe the FINAL state, so it merges after it exists |

Post-merge verification on `main`: 3,740 unit tests pass, ruff clean on
`bot/` + `website/backend/`, `git diff --check` clean, migration ledger
66 applied / 0 failed / 0 checksum mismatches, and the registry reports
`kis-v5`, `power-v2`, `player-radar-v2`, `ssr-v0.3`.

---

## 4. Still open

| Item | State | Why |
|---|---|---|
| **#554** narrative baseline cutoff | open, CI running | DATA-01; last review round asked for non-vacuous tests, which are now in — merge once green |
| **#551** vision/design docs | open by design | Codex withheld review; 13 threads were closed with decisions, but a FRESH review against a stable head is required before this becomes an implementation contract |
| **#556** `prox_score` validity audit | new blocking issue | third formula (`prox-web-v2.1`) still weights `return_fire_ms` 0.20 and `dodge_ms` 0.15 — measured as no-signal and inverted. Deliberately not half-fixed: `headshot_pct` in the same category is also suspect (r = −0.610 vs kills), so the category needs measuring as a whole |
| **REL-01** corrective release config | not started, owner-gated | no `v1.27.x` config exists; newest lists migrations 060/061/062 only, so deploying the merged stack against it would run current code against a schema without 063–065. Now recorded in `docs/KNOWN_ISSUES.md` |
| **OPS-01 / OPS-02 / SEC-01 / IP-01** | not started, owner-gated | deploy, prod migrations, ledger reconciliation, credential rotation, visibility/licence |

### Verification the audit asked for but that was NOT performed

- **No production deploy, no production migration, no rollback rehearsal.**
  All owner-gated.
- **No browser smoke** (WEB-01) — the React typecheck passed and the radar
  fix was reasoned from the code, but no Playwright run covered the real
  routes.
- **No live-fixture integration test** for migration 065; its coverage is
  unit-level SQL assertions plus rolled-back transactions against dev.

---

## 5. Standing constraints honoured

- No production deploy or production migration was performed.
- Dev database changes were limited to migrations 064/065 and the KIS
  recompute, all of which the owner approved earlier in the session, each
  with a `pg_dump` taken first.
- `/greatshot/` untouched.
- No credential values written to any PR, issue, comment or log.
- No history rewrite, no visibility or licence change.
