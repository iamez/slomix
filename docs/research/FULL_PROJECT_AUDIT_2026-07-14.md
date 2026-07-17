# Full Project Audit - Slomix (public copy)

**Audit date:** 2026-07-14
**Immutable baseline:** `main@b29977c0652f28aa16ca9a3a47005e4335ba2392`
**Tree:** `f358c306f3a5abbfca970ac8407a7d128dee9181`
**Scope:** all 1,270 tracked files; the Greatshot feature is excluded except for application-boundary effects.
**Method:** independent source review, formula/data-flow review, static analysis, tests/builds, dependency audit, and read-only dev/production/game-server validation. No production or application data was changed.

> **Redaction notice:** This is the public copy. Security-sensitive specifics — upstream advisory identifiers, affected dependency versions, live-probe results, and production host/path details — are redacted until the corresponding mitigations are deployed. The unredacted audit and its evidence appendix are retained privately by the owner.

## Executive verdict

Slomix is a real, coherent ET:Legacy community platform, not a generic stats dashboard. Its product model is internally consistent: the gaming evening is the product, the website is its memory, and Discord/game-server ingestion supplies the event stream. The strongest parts are the round-canonicalization work, bot/invalid-row gates, broad Python test suite, explicit formula registry, and read-only product surfaces.

The baseline is **operational but not audit-clean**. Four findings affect current or baseline user-visible correctness, two affect deployment/data integrity, and the prediction/rating labels are stronger than their empirical support. The most urgent live issue is not in `main`: the game server is running a stale Lua tracker that has already produced mathematically impossible aim-lock durations.

**Verdict by area**

| Area | Verdict |
|---|---|
| Product idea and architecture | Sound |
| Core PCS/round ingestion | Sound with mature safeguards |
| Good Night Index | Valid as a transparent product heuristic, not a scientific quality measure |
| Story/Map/Fingerprint | Useful product features; Story map count is wrong in the audited baseline |
| ET Rating / SSR / s.effort | Implemented consistently, but ET Rating mixes telemetry epochs and is not externally validated |
| Match prediction | Heuristic only; must not be described as calibrated AI probability |
| Web/API security | Generally defensive, with one applicable upstream-advisory path primitive (details redacted) |
| Deployment/migrations | Needs repair before the migration ledger can be trusted |
| Production health | Services healthy; code/data deployment state has drift |

## Findings

### AUD-001 - HIGH - Deployed Lua differs from the audited tracker and corrupts aim-lock data

The repository tracker clamps duration to confirmed samples and closes open locks at `last_seen`. The deployed game-server copy lacks those protections. Its SHA-256 is `16bf9fc...`, while the audited file is `68cd46b...`.

Read-only production measurement found **10,724** aim-lock events, **56** above `samples * 400 + 400 ms`, a maximum of **51,200 ms**, and a worst ratio of **36x** the permitted bound. The production database therefore contains known inflated headline aim-lock values.

**Action:** deploy the exact audited tracker, preserve the intentional `shot_fired` flag decision separately, then identify/recompute or exclude the 56 impossible rows. Add a deploy hash gate comparing server Lua to the release artifact.

### AUD-002 - HIGH - Migration deployment and the migration runner cannot reliably report truth

Production schema status reports **9 pending migrations** (`052`-`060`) even though these migrations were deployed. Root cause: `deploy_release.sh` records them only through a virtualenv interpreter path that does not exist on the production host (production uses differently-named virtualenvs), and the failure is downgraded to a warning.

The standalone runner also returns normally after a migration error, so failures that it manages to record produce process exit code 0. For SQL files containing an explicit `BEGIN`, PostgreSQL remains in aborted-transaction state after an error; the handler attempts to insert the failure row without rolling back first, so even failure recording is unreliable. Existing fake-connection tests do not model either behavior.

**Action:** use an existing production interpreter, make marking failure fatal to deploy, make each migration/ledger write transactional, rollback before recording failure, and exit non-zero. Reconcile the nine production ledger rows with `--mark` only after verifying their schema objects/checksums.

### AUD-003 - HIGH at baseline, fixed on current main - Betting markets had no first-map cutoff

At `b29977c`, auto-opened markets omit `closes_at`; the lifecycle can therefore leave betting open after the owner-approved cutoff at the end of map one. This is a fairness/integrity defect in a points market.

The fix is already merged after the audit baseline in `32c9802` / PR #496 and adds cutoff derivation, fallback, router enforcement, and tests. It still requires deployment because production runs `b29977c`.

### AUD-004 - MEDIUM at baseline, fixed on current main - Story calls distinct map names "maps played"

The narrative counts `SELECT DISTINCT map_name` from kill outcomes. Replayed maps are omitted. Production session 134 played 8 maps but the baseline reports 6; the same mismatch exists in many historical sessions.

The fix is already merged after the baseline in `18a3f32` / PR #497. It requires deployment.

### AUD-005 - MEDIUM - An applicable upstream request-routing advisory reaches security middleware

A pinned web-framework dependency is affected by a published upstream advisory in request host/path handling, and Slomix's CSRF middleware makes prefix decisions using the affected primitive. Advisory identifiers, affected versions, and live-probe results are redacted from this public copy until the mitigation is deployed.

Impact is reduced because the backend listens on localhost, individual session mutation routes commonly require `X-Requested-With`, and the external proxy may normalize the relevant header. Those are layers, not a proof that every path is protected.

**Action:** upgrade the affected dependency line when compatible, or validate the relevant header before URL construction and use the raw routed path for security decisions. Add a regression test with malformed inputs.

### AUD-006 - MEDIUM - Prediction output is uncalibrated and its inputs include untrusted rounds

The engine is an explicit heuristic: H2H 45%, form 30%, map 25%, linearly forced into a 30-70% band. Production and dev both contain **zero stored predictions**, so there is no accuracy or calibration evidence. Recent-form and map DPM queries do not join `rounds` to require `is_valid` and do not apply bot gates. H2H lookup is disabled by default, yet confidence can still be presented above low based on other availability signals.

**Action:** label output "heuristic estimate"; add valid-round/bot gates; begin outcome collection; publish Brier score, reliability bins, and sample size before calling values probabilities or AI predictions.

### AUD-007 - MEDIUM - ET Rating combines non-comparable coverage periods and missing telemetry as low performance

Global ET Rating divides all-time proximity counts by valid PCS totals and ranks missing proximity defaults (`kill_quality=1`, others `0`) against real values. It does not scope the proximity subqueries through valid rounds or to a common observation window. Players/periods with less telemetry can therefore move for coverage reasons rather than play.

The comment that the constant centers an average player near `0.50` is also false for the stated formula: at median percentiles the signed-weight result is approximately `0.57`. Session/map ratings are PCS-only and rescaled, while global ratings include proximity, so their semantic comparison is approximate.

**Action:** introduce coverage/version epochs, join proximity data to canonical valid rounds, use explicit missingness and minimum coverage, and backtest stability/rank sensitivity before treating tiers as skill truth.

### AUD-008 - MEDIUM - Proximity scores silently turn source-query failures into plausible scores

Ten independent metric queries run with `return_exceptions=True`. Failed sources are omitted; absent values become neutral percentile `0.5`; the endpoint returns a normal-looking score without a degraded/completeness flag. This improves availability but hides data failure from users and downstream consumers.

**Action:** return source status, metric coverage, and a degraded flag; log/alert failed query names; suppress leaderboard ranking below an agreed coverage threshold.

### AUD-009 - MEDIUM - Root dependencies contain known vulnerabilities hidden by CI ignores

`pip-audit` found 12 records (11 distinct advisories) across three packages (an SSH library advisory with no released fix, an imaging library fixed by a version bump already on current main, and the web-framework advisory tracked as AUD-005). CI explicitly ignores the SSH-library and web-framework findings.

The imaging library is primarily used by offline asset tooling outside the excluded Greatshot feature; the baseline exposure is limited. Several of the remaining advisories are not applicable to the observed Linux/FastAPI deployment shape.

**Action:** time-box the remaining ignores with an owner and expiry date; align and lock the dependency sets; remove each ignore as its fix lands.

### AUD-010 - LOW - Production checkout is intentionally dirty and contains an extra secret copy

Production is detached at the correct baseline but has 35 modified tracked frontend files from cache-busting and an untracked `.env` backup copy. Both env files have restrictive permissions, so there is no demonstrated unauthorized read, but extra secret copies increase exposure and confuse dirty-tree health checks.

**Action:** generate cache-busted output outside tracked sources or make it an explicit release artifact; move secret backups outside the repo with retention/permissions policy; document detached-release state.

### AUD-011 - LOW - Authentication policy has duplicate active implementations

`website/backend/dependencies.py` and `website/backend/middleware/auth_helpers.py` both implement user/admin resolution with slightly different identity semantics. Additional older router-local copies are acknowledged in comments. No bypass was proven, but policy changes can land in one path and not another.

**Action:** converge on one dependency module and contract-test every state-changing route against the same identity/tier matrix.

### AUD-012 - LOW - Verification breadth is strong in Python but uneven elsewhere

Baseline GitHub CI is green, Python has thousands of tests, JS lint/typecheck/build pass, and Bandit reports no medium/high finding. Residual gaps are: only 28 React tests across a large staged/live UI, no CI shellcheck gate, 1,190 whole-repo Ruff findings outside the production lint scope, stale documentation claims, and local toolchains below declared versions (Python 3.10 vs 3.11+, root Node 20 vs 22+).

Shellcheck warnings include unsafe `.env` export parsing in `website/start_website.sh`, missing guarded `cd` in two scripts, and overlapping deploy case patterns. These are not demonstrated production failures but should be cleaned up.

## Greatshot boundary

Greatshot internals, rendering, uploads, its schema migration, UI, tests, and sample media were excluded. Boundary inspection found that the main application imports Greatshot modules, but service startup is asynchronous, timeout-bounded, and catches startup failure; the unavailable renderer does not currently prevent `/health` or the rest of Slomix from starting. The shared frontend production build still compiles Greatshot chunks successfully.

## What the closure plan missed

`PLAN_REVIEW_CLOSURE_AND_GOOD_NIGHT_2026-07-13.md` correctly identified that Story, push-death maps, and fingerprint/radar surfaces already exist. It did not prove their data semantics or deployment state. Specifically, it missed:

1. the Story distinct-name undercount;
2. the stale deployed Lua tracker and already-corrupt aim-lock rows;
3. nine unrecorded production migrations;
4. the absence of any prediction calibration dataset;
5. ET Rating coverage/epoch bias;
6. the applicable upstream request-routing advisory.

The plan's "nothing autonomous to build" conclusion was therefore too strong. Feature duplication was unnecessary, but correctness and operational remediation remained.

## Recommended order

1. Deploy the audited Lua tracker and quarantine/recompute impossible aim-lock rows.
2. Repair migration marking/exit semantics and reconcile production ledger 052-060.
3. Deploy current main fixes for betting cutoff and Story count after normal owner review.
4. Mitigate the request-routing advisory (AUD-005).
5. Add validity/coverage semantics to predictions, ET Rating, and proximity scores.
6. Consolidate auth helpers and increase frontend/shell verification depth.

Per-file disposition is in `FULL_PROJECT_AUDIT_COVERAGE_2026-07-14.csv`. The detailed evidence appendix (commands, counts, applicability notes) is retained privately.
