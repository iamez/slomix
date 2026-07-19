# Slomix implementation review follow-up

**Review date:** 2026-07-18  
**Reviewed commit:** `3952ffe25593d85b588557a64882ab46233174fc`  
**Compared against:** `7666f7b` and `docs/PLAN_FULL_PROJECT_AUDIT_REMEDIATION_2026-07-14.md`  
**Review type:** read-only implementation audit; no application code changed  
**Excluded:** Greatshot, as requested; its render server is not available  
**Status:** open findings awaiting an independent re-review after remediation

## Purpose

This document preserves the implementation-review findings from the remediation
wave merged through PRs #508-#514. It is intentionally self-contained so a new
reviewer can verify or reject each finding without relying on chat history.

The reviewed wave changed 49 files (`+6084/-453`). All referenced line numbers
describe commit `3952ffe`; later edits can move them. A merged PR or green CI is
not evidence that the production and data owner gates are complete.

## Executive verdict

The implementation is substantial and several urgent controls are good, but it
does **not** complete the full remediation plan. Three behavior-level findings
should block promotion or deployment of the affected paths:

1. deploy paths can still bypass migration-ledger enforcement;
2. prediction rematches inside one gaming session receive aggregated outcomes;
3. Prox v2 still treats some real event-count zeros as missing telemetry.

ET Performance v3 is appropriately shadow-only, but its API currently calls
players eligible without enforcing the planned telemetry coverage requirement.
PR-6 and the owner-operated production gates are mostly still outstanding.

## Findings

### IMP-001 - Deploy paths can bypass migration safety

**Severity:** HIGH  
**Plan contract:** the migration ledger can no longer be skipped by a deploy.

Evidence:

- [`deploy_release.sh`](../../scripts/deploy_release.sh#L439) lets
  `--skip-migrations` skip both migration application and `--validate`.
- [`rsync_deploy_vm.sh`](../../scripts/rsync_deploy_vm.sh#L129) only counts SQL
  files, says migrations must be applied manually, and then restarts services.
- [`deploy_to_vm.sh`](../../scripts/deploy_to_vm.sh#L243) applies the canonical
  schema with raw `psql`, `ON_ERROR_STOP=0`, and treats a missing DB password as
  a warning that skips the schema step.
- [`deploy_clean.sh`](../../scripts/deploy_clean.sh#L288) has the same raw-schema
  pattern. Its web dependency update also installs root `requirements.txt`
  rather than `website/requirements.txt` at line 282.
- After services have stopped, the release failure trap restarts them on
  "whatever code is currently checked out" instead of first restoring the
  previous release ([`deploy_release.sh`](../../scripts/deploy_release.sh#L226)).
  A migration failure can therefore start new code against an incomplete schema.
- `scripts/release_configs/` contains configs only for `v1.14.2` and `v1.20.0`.
  There is no config for the pending `v1.26.0` release even though migrations
  061 and 062 must be accounted for.

Required recheck:

- Identify and declare exactly one production deploy entry point.
- Other production-capable scripts must delegate to it or fail closed.
- Ledger validation must run even when no migrations are expected.
- Exercise a migration failure after service stop and prove old code is restored
  before services restart.
- Dry-run the actual release tag with its committed release configuration.

### IMP-002 - Prediction rematches are resolved at gaming-session granularity

**Severity:** HIGH  
**Impact:** corrupt shadow calibration labels; no public prediction impact while
publishing remains disabled.

Slomix defines a gaming session as multiple matches separated by no more than 60
minutes. The resolver maps a prediction to `gaming_session_id` using time windows
([`prediction_engine.py`](../../bot/services/prediction_engine.py#L524)), selects
all `session_results` for that session at line 601, and aggregates every
roster-overlapping row at line 607. It has no match or split-episode outcome key.

Read-only reproduction against the real resolver:

- two predictions, same rosters, prediction times 1000 and 2000;
- one gaming session with window 900-3000;
- first rematch result A wins 2-0, second rematch result B wins 2-0.

Observed output:

```text
resolved=2
outcomes=[(prediction 1, draw, 2, 2), (prediction 2, draw, 2, 2)]
```

Both predictions incorrectly receive the aggregate 2-2 draw. Existing tests
cover two different gaming-session IDs but not two matches within one gaming
session ([`test_prediction_auto_resolve.py`](../../tests/unit/test_prediction_auto_resolve.py#L101)).

Required recheck:

- Bind outcomes to a durable match/split-episode key, or leave ambiguous rows
  pending for manual resolution as the plan originally specified.
- Add a regression test with two opposite-result rematches in one gaming session.
- Prove resolution is idempotent and roster orientation ties are not guessed.

### IMP-003 - Prox v2 does not preserve true event-count zeros

**Severity:** HIGH  
**Impact:** coverage and percentile cohorts favor players who generated events;
players with genuine zero trades/crossfire/focus events can be treated as
missing and dropped.

The source merge constructs the player cohort from rows returned by any source
([`prox_scoring.py`](../../website/backend/services/prox_scoring.py#L451)). Event
sources such as crossfire, trade kills, and focus fire return rows only when an
event exists (lines 535-568). No cohort `LEFT JOIN` or capability-aware zero fill
adds a `0` for a qualified player with no events. Coverage counts only non-`None`
metrics at line 286, so a genuine zero becomes missing coverage.

The quality tests inject already-populated dictionaries and do not exercise
this SQL merge behavior
([`test_prox_scoring_quality.py`](../../tests/unit/test_prox_scoring_quality.py#L132)).

A related contract violation exists at lines 281-331 of `prox_scoring.py`: a
single-player request can score the requested player even when that player is
below `MIN_ENGAGEMENTS`, provided another cohort member qualifies. The tests also
intentionally return a below-coverage single player, although the plan says a
player is scored only at 80% effective metric-weight coverage.

Required recheck:

- Build one explicit engagement-qualified cohort and left-join event-count
  sources against it.
- Zero-fill only capability-confirmed event counts; keep unsampled latency `NULL`.
- Test true zero versus missing, below-minimum engagement, and below-coverage
  single-player requests through the actual merge path.

### IMP-004 - ET Performance v3 eligibility and capability contract is incomplete

**Severity:** MEDIUM  
**Impact:** internal/shadow output metadata overstates eligibility.

[`skill_rating_v3.py`](../../website/backend/services/skill_rating_v3.py#L213)
marks every player with at least 20 rounds as eligible. It reports one coarse,
population-level coverage value at line 231; it does not enforce 80%
telemetry-round coverage per player or return the planned per-player coverage,
observation window, and per-metric sample sizes.

Migration 062 adds `tracker_version`, `round_key`, and `capabilities`
([`062_proximity_processed_files_capabilities.sql`](../../migrations/062_proximity_processed_files_capabilities.sql#L16)),
but the parser still writes only `filename` and `aggregates_applied`
([`parser.py`](../../proximity/parser/parser.py#L1602)). The same columns are
missing from the canonical fresh schema
([`schema_postgresql.sql`](../../tools/schema_postgresql.sql#L3013)).

The code correctly acknowledges this limitation and keeps v3 shadow-only. The
remaining error is calling the round-qualified population `eligible` before the
coverage eligibility gate can be evaluated.

Required recheck:

- Persist an explicit Lua capability manifest and canonical round key.
- Synchronize migration, parser, canonical schema, and fresh-install tests.
- Separate `round_qualified` from `eligible`, and enforce/report coverage only
  when the required evidence exists.

### IMP-005 - Prox degraded-state observability is incomplete

**Severity:** MEDIUM

- Every source gets the same concurrent-batch wall time, not its own query
  duration ([`prox_scoring.py`](../../website/backend/services/prox_scoring.py#L722)).
- There is no checked-in alert for any source error or 15 minutes of degraded
  state; only a counter and batch histogram exist
  ([`metrics.py`](../../website/backend/metrics.py#L43)).
- HTTP caching bypasses `{"status":"error"}` but not
  `{"status":"degraded"}`
  ([`http_cache_middleware.py`](../../website/backend/middleware/http_cache_middleware.py#L156)).
  `/api/proximity/` responses can therefore cache a transient degraded result
  for the 300-second leaderboard TTL.
- `website/requirements.txt` omits `redis`, `prometheus-client`, and
  `prometheus-fastapi-instrumentator`. A fresh web venv installed from that
  manifest silently uses no-op metrics and can fall back from Redis.
- The player profile silently substitutes a separate CF/TR formula when the
  Prox quality result is degraded or below coverage
  ([`proximity_player.py`](../../website/backend/routers/proximity_player.py#L177)).
  The returned user-facing Teamplay value does not expose that formula switch.

### IMP-006 - Architecture/deploy/CI PR-6 is mostly outstanding

**Severity:** MEDIUM  
**Classification:** incomplete plan scope, not a regression introduced by one
specific PR.

Still missing:

- canonical `SessionPrincipal` and mutation role/CSRF contract matrix;
- convergence of [`dependencies.py`](../../website/backend/dependencies.py#L85)
  and [`auth_helpers.py`](../../website/backend/middleware/auth_helpers.py#L20);
- removal of the forbidden Discord-ID fallback for `website_user_id`
  ([`auth_helpers.py`](../../website/backend/middleware/auth_helpers.py#L88));
- reproducible bot/web locks and a dependency-review PR gate;
- Python 3.11/3.13 matrix (CI currently selects only 3.11);
- broader Ruff ratchet;
- clean artifact-based production deploy instead of in-checkout legacy asset
  rewrites;
- model/formula cards for Prediction, ET Performance, Match Skill, and Prox v2;
- chronological Elo versus pinned OpenSkill Match Skill research/backtest.

The added `pip check`, ShellCheck gate, and time-boxed audit ignores are useful,
but they are only part of PR-6.

### IMP-007 - Security regression tests do not load the real app stack

**Severity:** LOW

The strict Host parser, outermost Host middleware, routed-path CSRF, cache keys,
and rate-limit bucketing are correctly implemented. However, the security test
constructs a minimal replica instead of loading `website.backend.main.app`
([`test_host_path_security.py`](../../tests/security/test_host_path_security.py#L39)).
A future middleware-order regression in the actual app could therefore pass the
test. Security-event classification in
[`logging_middleware.py`](../../website/backend/middleware/logging_middleware.py#L231)
also still reads `request.url.path`; the current outer Host gate limits the risk.

### IMP-008 - Migration runner has a latent non-atomic escape path

**Severity:** LOW

The normal migration path is transactional and well tested. SQL detected as
requiring `CONCURRENTLY`, however, runs statement by statement and records the
ledger separately
([`apply_migrations.py`](../../scripts/apply_migrations.py#L654)). A mid-file
failure can leave earlier statements applied, contrary to the plan's universal
same-transaction contract. No currently committed migration uses this path, so
this is latent rather than an active production blocker.

### IMP-009 - Diff hygiene

**Severity:** LOW

`git diff --check 7666f7b..3952ffe` reports trailing whitespace on the new
`.gitignore` lines 13-24, apparently from line-ending churn. This is not a
runtime defect but should be covered by a whitespace gate.

## Correctly implemented areas

The review found the following implementation work materially correct:

- migration discovery, checksum validation, normal transactional apply path,
  failure ledger, non-zero failure behavior, `--validate`, and status output;
- guarded aim-lock backfill preconditions and fingerprinting;
- outermost strict Host validation and routed-path use in CSRF, cache, and rate
  limiting;
- prediction shadow/publish separation and filtering of shadow rows from public
  bot/API surfaces;
- prediction temporal cutoff plus valid-human gates in the reviewed feature
  queries;
- Prox fail-closed response on any source-query exception;
- midrank tie handling and effective-weight coverage arithmetic;
- ET Performance v3 directed-midrank formula and its shadow-only exposure;
- `pip check`, ShellCheck, and time-boxed audit-ignore CI groundwork.

## Verification performed

- `git diff --check 7666f7b..3952ffe` was run.
- 121 targeted unit tests passed locally in 75.72 seconds, covering migration
  runner, aim backfill, prediction shadow/resolution, Prox scoring, ET v3, and
  formula registry behavior.
- The combined GitHub Actions run for `3952ffe` was green, including PostgreSQL
  integration and security tests.
- Local PostgreSQL integration could not be independently completed because the
  local test database/venv was not correctly provisioned. Local TestClient
  security runs hung in the available local environments. The green remote CI
  reduces but does not erase this environment-specific verification gap.
- The prediction same-gaming-session rematch defect was reproduced directly
  against `PredictionEngine.auto_resolve_predictions()` with an in-memory fake
  DB; no source file was modified.

## Production snapshot observed during review

Read-only production inspection on 2026-07-17 showed:

- deployed commit `b29977c`, not reviewed main `3952ffe`;
- `slomix-web` and `slomix-bot` active;
- tracked legacy frontend files modified in the production checkout;
- untracked `.env.bak_20260714_kis` in the checkout.

Therefore PRs #495-#514, OPS-MIG, OPS-LUA, OPS-DATA, the release deployment, and
the post-release smoke evidence were not closed by the reviewed merge. This
snapshot must be re-queried; it is historical evidence, not a claim about later
production state.

## Independent re-review protocol

The next reviewer should:

1. Record the exact new `HEAD`, base commit, production commit, and dirty status.
2. Review each `IMP-*` independently; do not accept existing comments or green
   tests as proof without tracing the actual behavior.
3. Re-run the prediction rematch reproducer and add an equivalent committed test.
4. Exercise Prox true-zero versus missing through the real query/merge contract,
   preferably against disposable PostgreSQL fixtures.
5. Enumerate every production-capable deploy script and prove there is no ledger
   bypass, including skip flags and failure recovery.
6. Verify fresh schema parity and fresh isolated bot/web dependency installs.
7. Run full Python, PostgreSQL integration, security, frontend, ShellCheck,
   dependency audit, and `git diff --check` gates.
8. Re-query owner-operated production gates separately from code correctness.
9. For every rejected finding, record the counterexample, command/test output,
   and exact lines that invalidate it.
10. Keep Greatshot excluded until its render server exists, unless the owner
    explicitly changes that scope.

## Closure rule

An item closes only with all of the following: corrected implementation or a
demonstrated false-positive explanation, regression test, relevant full-suite
checks, deployment evidence when applicable, rollback evidence, and owner
sign-off for owner-gated operations.
