# Slomix — Full Project Audit Remediation & Analytics Trust Plan

**Date:** 2026-07-14 (verification refreshed 2026-07-15)
**Audit source:** `docs/research/FULL_PROJECT_AUDIT_2026-07-14.md` (12 findings, AUD-001…AUD-012, independent review at baseline `main@b29977c`)
**Verification:** Findings independently re-verified read-only against dev, production VM, and the game server on 2026-07-15 (see §2). No production data was changed.
**Audience:** Anyone (human or agent) picking up this work without prior context.

> **Redaction notice:** This is the public copy. Security-sensitive specifics — upstream advisory identifiers, affected dependency versions, live-probe results, and production host/path details — are redacted until the corresponding mitigations are deployed. Unredacted versions are retained privately by the owner.

---

## 1. What Slomix is and what we are building

Slomix is a community ET:Legacy platform made of several connected systems:

- A **Lua tracker** on a separate game server captures combat, movement, teamplay, objective, and proximity telemetry into files.
- A **Python parser/importer** links Lua events to canonical rounds, stores them in PostgreSQL, and builds aggregates from them.
- A **Discord bot** (20 cogs, 80+ commands) runs the voice/session workflow, teams, results, betting, notifications, and experimental match predictions.
- A **FastAPI backend** exposes sessions, players, Story, Good Night, BOX scoring, KIS/OIS/SSR, ET Rating, s.effort, and proximity analytics.
- Production serves **legacy JS for most pages plus four live React routes**; the remaining React pages are intentionally staged. Legacy JS is the production canon — React builds are not a verification substitute.
- The product goal is not "more stats" but an **explainable, friendship-safe story of the gaming evening**: what happened, who contributed, where the turning points were, and how a player develops.
- **Greatshot** needs an external renderer that currently does not exist. Its internals, rendering, uploads, and schema stay excluded from this plan; we only verify it cannot prevent the main application from starting.

### Terminology

- **ROUND** = one stats file (R1 or R2), one half of a match.
- **MATCH** = R1 + R2 together (one complete map played).
- **GAMING SESSION** = multiple matches within 60-minute gaps.

---

## 2. Verified state (read-only evidence, 2026-07-15)

| Area | Verified truth |
|---|---|
| Code | Local `main` is at `7666f7b` (#507). Production runs `b29977c` (#494), so **#495–#507 are not deployed** — including the betting cutoff fix (#496), the Story map-count fix (#497), and the entire Good Night wave (#499–#507). |
| Working tree | Dev working tree is clean apart from untracked audit documents (committed alongside this plan). An earlier report of concurrent dirty work is stale. |
| Aim lock | 10,724 aim-lock rows; exactly **56 impossible** (`duration_ms > samples*400+400`), all from **2026-06-11**; 726,050 ms total phantom time, max 51,200 ms, worst ratio 36×. No new violations since. |
| Lua | Game-server tracker SHA-256 is `16bf9fc46b…` (file dated 2026-06-22); the repo tracker is `68cd46b4…` and includes the `last_seen` close + duration clamp merged in PR #403 (2026-06-30). **The forward fix is not deployed.** Clean recent data lowers incident severity; it does not remove the deploy drift. |
| Migrations | Schema objects for `052`–`060` exist in production, but the `schema_migrations` ledger does not record them. Root cause confirmed in `scripts/deploy_release.sh` (lines ~356–369): raw `psql` applies migrations, then a best-effort `--mark` runs via a virtualenv interpreter path that does not exist on the production host; the failure is downgraded to a `WARN`. |
| Web dependency advisory | A published upstream advisory affects the pinned web-framework line used in production, and the CSRF middleware makes prefix decisions using the affected path primitive (`website/backend/main.py:165`). An earlier "not affected" verdict inspected the wrong Python environment. Specifics redacted; see the private audit copy. |
| Predictions | Production and dev both contain **0 stored predictions**; the 45/30/25 formula is an uncalibrated heuristic, not a learned model. Feature queries do not gate on `rounds.is_valid` or bot participation. |
| ET Rating | v2 mixes PCS history from 2025 with proximity telemetry that only reliably exists from 2026-03-24; the "constant centers the median player at 0.50" comment is false — the stated formula yields ≈0.57 at median percentiles. |
| Proximity scores | `compute_prox_scores()` (`website/backend/routers/proximity_scoring.py`) can turn a failed source query into neutral 0.5 percentiles and return a normal-looking response with no degraded flag. |
| Coverage epoch | Kill outcome and combat position telemetry are reliably present from **2026-03-24**; production has **799 valid rounds** since then. That is the common epoch for ET Performance v3. |

### Audit finding disposition after verification

| Finding | Severity | Verified status |
|---|---|---|
| AUD-001 Lua drift + corrupt aim-lock rows | HIGH | **Confirmed, split in two**: (a) historical — 56 impossible rows, all 2026-06-11, needs guarded cleanup; (b) forward — deployed Lua still lacks the clamp fix, needs owner-gated redeploy. |
| AUD-002 migration ledger/runner | HIGH | **Confirmed** (missing interpreter + WARN-instead-of-fail observed in the script; ledger drift 052–060 observed in production). |
| AUD-003 betting cutoff | HIGH at baseline | Fixed on main (#496); **not yet deployed**. |
| AUD-004 Story map count | MEDIUM at baseline | Fixed on main (#497); **not yet deployed**. |
| AUD-005 request-routing advisory | MEDIUM | **Confirmed applicable** (details redacted). Earlier dismissal was based on the wrong Python environment. |
| AUD-006 predictions uncalibrated | MEDIUM | Confirmed (0 stored predictions; no validity gates). |
| AUD-007 ET Rating epoch mixing | MEDIUM | Confirmed (epoch mixing; median ≈0.57 vs documented 0.50). |
| AUD-008 prox score silent failure | MEDIUM | Confirmed in `proximity_scoring.py`. |
| AUD-009 dependency vulnerabilities | MEDIUM | Confirmed; imaging library already bumped on main; web-framework advisory actionable as AUD-005; the SSH library has no released fix (time-boxed exception needed). |
| AUD-010 dirty prod checkout + `.env` backup copy | LOW | Confirmed (35 modified cache-busted files + an untracked env backup). |
| AUD-011 duplicate auth implementations | LOW | Confirmed (`dependencies.py` vs `middleware/auth_helpers.py`). |
| AUD-012 uneven verification breadth | LOW | Confirmed (28 React tests, no shellcheck gate, repo-wide Ruff debt outside lint scope). |

---

## 3. Locked product decisions

1. Delivery splits into an **urgent production wave** and then independent **quality/scoring programs** that do not block each other.
2. **ET Rating splits** into *ET Performance* (individual performance composite) and a separate *Match Skill* (outcome-based rating with uncertainty). They are never blended into one number.
3. **Predictions run in silent shadow first**: feature snapshots and outcomes are stored; Discord publishes nothing until promotion gates pass.
4. No formula is promoted because it "looks reasonable"; each needs a **formula version, model card, coverage, backtest, slice results, and owner sign-off**.
5. **Owner-gated forever:** production deploy, migration `--mark`, DB `--apply`, Lua copy/reload, secret handling, PR merges, and final model promotion. An implementation agent never executes these autonomously.
6. Lua on the game server is **never** reloaded via `lua_restart` (known crash); always a full map load.

---

## 4. Urgent wave (Wave 0)

Ordered steps; PR items are dev-side, OPS items are owner-executed with commands prepared in the PR descriptions.

### U0 — Isolation and evidence freeze (this PR)

Commit this plan plus the audit deliverables so the evidence baseline is in git (public copies redacted per the notice above). Each release from here on records a manifest: commit, requirement lock hashes, migration checksums, Lua SHA-256, frontend build hash.

### U1 — Migration runner + deploy integration (PR-1)

`scripts/apply_migrations.py`:

- Add `--validate` (compare ledger vs files: pending / failed / checksum mismatch) and `--status --json`.
- Apply each migration and its ledger *success* row **in the same transaction**; on error, roll back, record the failure row in a **new** transaction, re-raise, and exit **non-zero**.
- Treat an explicit inner `BEGIN`/`COMMIT` in a migration file as an error unless it is a verified outer wrapper that the runner strips; inner transaction control means the migration is rejected.
- Checksum mismatch against a previously applied migration is an error, not a warning.

`scripts/deploy_release.sh` (~lines 349–369):

- Use the explicit production web virtualenv interpreter; a missing interpreter aborts the deploy.
- Run migrations **through the runner** (drop the raw `psql` + best-effort `--mark` path entirely).
- Ledger drift, unknown CLI arguments, or a failed modern-frontend build abort the deploy instead of warning.

### U2 — Web security (PR-2)

- All security path decisions (CSRF middleware first) switch from `request.url.path` to `request.scope["path"]` via a shared `routed_path(request)` helper.
- Add host-validation middleware (`TrustedHostMiddleware`) as the **outermost** middleware, configured by a `TRUSTED_HOSTS` env variable. Production refuses to start without the setting.
- Regression tests: malformed host inputs → 400; the correct proxy host passes; middleware ordering asserted.
- **Separate spike, not in the mitigation PR:** attempt the web-framework upgrade to a patched line. Verify actually-published compatible versions, run `pip check` + the full suite; only then bump pins and remove the corresponding audit ignores. If the spike is red, the mitigation above remains the defense and the ignore stays time-boxed with an expiry comment.

### U3 — Aim-lock cleanup guard (PR-1)

`scripts/backfill_aim_lock_clamp.py`:

- Dry-run prints candidate count, total phantom ms, newest violation date, and a SHA-256 fingerprint of the ordered candidate ID list.
- `--apply` requires exactly `count=56`, `phantom_ms=726050`, newest date `2026-06-11`, and a matching fingerprint; any mismatch aborts before writing.
- Before apply (owner-executed): DB backup + old/new row snapshot. After apply: 0 violations, unchanged row count, and a second dry-run must be empty.

### OPS-MIG — One-time ledger reconciliation (owner)

**Precondition (runner staging):** the production baseline still ships the OLD `apply_migrations.py`, which does NOT recognise `--validate` (its arg dispatch falls through to `cmd_apply()`) and cannot check checksum drift. OPS-MIG precedes REL-1 in the ordering, so the hardened runner from PR-1/#509 must be **staged first** — either land #509, or copy the hardened `scripts/apply_migrations.py` onto the VM and run *that* (e.g. `venv-web/bin/python scripts/apply_migrations.py --validate`). Running the baseline runner's `--validate` would silently apply pending migrations instead of validating.

For migrations 052–060, compare actual production objects (`pg_get_indexdef`, `pg_get_viewdef`, column types/defaults/nullability, constraints) against the committed SQL. Only on full match run the hardened runner's `--mark` for exactly those nine files. Goal: `--validate` reports 0 pending / 0 failed / 0 missing / 0 checksum mismatch.

### OPS-LUA — Forward Lua deploy (owner)

Copy the release artifact `proximity/lua/proximity_tracker.lua` (repo SHA-256 `68cd46b4…`) to the game server's luascripts directory, then perform a **full map load** (never `lua_restart`).

**Two known intentional live-vs-repo differences — never blind-copy:**

1. The repo ships `shot_fired = false` (default-off, protected by a guard test); the live server intentionally runs `true` — it is the aim-telemetry data source. After copying, flip `shot_fired = true` on the server and compute the verification hash over **that adjusted artifact** (or use a diff gate that whitelists exactly this line).
2. `c0rnp0rn8.lua` on the live server is AHEAD of the repo (live-only fixes); it is not part of this deploy and must not be overwritten.

Verify the deployed Lua by hashing the FILE on the VM, not via round output: the tracker emits only the coarse `# PROXIMITY_TRACKER_V6` header (the parser reads only that version marker), so a round cannot "carry" the artifact hash. Post-copy, `ssh <vm> sha256sum <path>/proximity_tracker.lua` must equal the approved adjusted-artifact hash (§OPS-LUA). Then the next real round must produce zero `duration_ms > samples*400+400` violations.

### OPS-DATA — Historical cleanup (owner)

**Precondition (ordering hazard):** the production baseline (`b29977c`) still ships the OLD, UNGUARDED `scripts/backfill_aim_lock_clamp.py`, which accepts `--apply` with no count/date/fingerprint preconditions and updates *every* row matching the predicate. Because REL-1 (which deploys PR-1/#509 with the guarded version) runs *after* this step, **do not run the production copy.** First stage the guarded PR-1 script — either land #509 before this step, or copy the guarded script onto the VM and verify its `--expect-count`/`--expect-fingerprint` flags exist — then run that. Otherwise the "guarded backfill" instruction below silently executes the unguarded predicate-wide update.

After the guarded script is in place: DB backup + candidate snapshot, run the guarded backfill `--apply` (with the dry-run's exact `--expect-*` values), prove 0 violations / unchanged row count / empty re-dry-run. The next two real rounds must stay clean.

### REL-1 — Application deploy (owner)

A clean release containing #496 (betting cutoff), #497 (Story map count), the Good Night wave, and the urgent PRs. Pre-restart: ledger clean. Post-restart smoke: malformed host inputs rejected, Story session 134 returns 8 maps, betting rejects wagers after the first-map cutoff, both services active, Good Night/Moment Director endpoints respond.

### Rollback (Wave 0)

Code returns to the previous tag; Lua returns to the preserved previous artifact with another full map load; the aim cleanup restores from the old-row snapshot; all Wave-0 migrations are additive only.

---

## 5. Program A — Predictions shadow (PR-3)

- Next free migration extends `match_predictions` with `model_version`, `publish_state`, `prediction_event_key`, `feature_snapshot JSONB`, `feature_coverage JSONB`, `eligibility_reasons`, `gaming_session_id`, `brier_score`.
- `PREDICTION_SHADOW_ENABLED=true` generates and stores predictions; `PREDICTION_PUBLISH_ENABLED=false` suppresses every Discord embed. Silence requires filtering **every** public surface, not just `/api/predictions/recent`: the bot's `!predictions`/`!prediction_stats`/`!my_predictions`/trends/leaderboard/map commands (`bot/cogs/predictions_cog.py`) also add `WHERE publish_state='published'` (the admin cog intentionally still sees shadow rows). Storage is independent of the optional embed builder so a degraded env still collects rows.
- Feature queries take `as_of=prediction_time` and see only **valid, human, completed-before** rounds (`rounds.is_valid` + bot gates). A later result must not leak into the snapshot.
- Every factor returns `score`, `available`, `sample_size`, `window_start/end`; a missing factor is never presented as evidence. Non-eligible cases are stored but excluded from calibration reports.
- `prediction_event_key` is a deterministic hash of date, map, format, sorted rosters, **and a split-episode occurrence id**. The occurrence component is essential: date+map+format+rosters alone would collapse a legitimate same-evening rematch of the same roster into the first prediction's key and silently drop its calibration sample. The occurrence is the EPISODE identifier — minted once when a split is first detected and cleared when it ends — NOT a wall-clock cooldown bucket (a bucket splits a re-detection straddling a boundary and collapses two rematches inside one bucket). So a re-prediction of the same episode dedups while a genuine rematch (a new episode) gets its own row. Resolution is idempotent; the resolver defers dates spanning more than one gaming session to manual resolution rather than assigning a whole-date aggregate to each rematch, and records the actual `gaming_session_id` when unambiguous.
- Draw/cancelled outcomes are reported separately and excluded from binary Brier/log-loss.
- **Promotion gate:** ≥100 resolved eligible predictions, ≥95 % outcome resolution, Brier < 0.25, log loss < 0.693, five equal-frequency reliability bins, ECE ≤ 0.08, and no major format materially worse than the 50/50 baseline. First calibrator is Platt/sigmoid; isotonic is not used at this sample size.
- The formula registry entry moves from "live" to "shadow"; README/UI say **"experimental heuristic estimate"**, never "AI probability".

References: scikit-learn probability calibration guide; Google production-ML monitoring; Model Cards for Model Reporting; NIST AI RMF *Measure*.

---

## 6. Program A — ET Performance v3 + Match Skill (PR-5)

### ET Performance v3 (shadow)

- Common telemetry epoch **2026-03-24+**; canonical `round_id`, `rounds.is_valid`, human gates for **all** PCS and proximity counters; identical denominator window for crossfire/trade/clutch rates (no more all-time counts divided by short-window denominators).
- `proximity_processed_files` gains `tracker_version`, `round_key`, `capabilities JSONB`. **The columns alone are not sufficient:** the current tracker emits only the coarse `# PROXIMITY_TRACKER_V6` header (stored as integer version 6), and an optional section (e.g. AIM_LOCK) is written only when it has rows — so an *enabled* feature with zero events is byte-identical to a *disabled* one. Distinguishing a true 0 from "never captured" therefore requires the Lua tracker to emit an explicit per-feature capability manifest AND the parser to persist it into `capabilities`. Until that lands, the v3 scorer must NOT infer coverage from a value equalling its neutral default (it would misclassify observed zeros) — this is why v3 currently ranks all observed values and stays shadow-only.
- Formula fix isolated from tuning: keep absolute v2 weights, remove the incorrect centering constant, invert "lower is better" metrics first:
  `score = Σ abs(weight) * directed_midrank_percentile`, where `directed = percentile if weight > 0 else 1 - percentile`. Each metric column has mean 0.5 and the absolute weights sum to 1, so the population **mean** is mathematically 0.50 (this is the AUD-007 centering the v2 constant only claimed). The **median** is empirical — near, but not forced to, 0.50 — because a weighted sum of midrank columns is not median-preserving for mixed rankings.
- Eligibility: ≥20 valid rounds and ≥80 % telemetry-round coverage. Partial-coverage handling for eligible players: v3 ranks every OBSERVED metric value (a real zero ranks at the bottom); it does NOT invent values for absent metrics and does NOT treat a value equal to its neutral default as "missing" (that would inflate genuine zeros). The precise observed-zero-vs-never-captured split needs the migration-062 capability manifest (see above) and is why coverage is a coarse proxy and v3 stays shadow-only. API returns `formula_version`, `observation_start/end`, coverage + `coverage_note`, `eligible`, `unrated_reasons`, per-metric sample size, `mean_rating` (the centered statistic) and empirical `median_rating`.
- v2 stays public; v3 runs shadow for ≥30 days and ≥8 session dates.
- **Promotion gate:** ≥20 eligible players, split-half Spearman ≥ 0.70, `abs(corr(score, coverage)) ≤ 0.15`, leave-one-family-out median rank shift ≤ 3. Every shift of more than five places between v2 and v3 gets a documented explanation (data window, missingness, or formula effect). Owner reviews top/bottom and role/class slices before v3 is user-visible.
- On promotion the UI is renamed **ET Performance v3**; `s.effort` gets a new formula version with re-measured `POOL_NEUTRAL`; v2 and v3 history are never aggregated together.

### Match Skill (research only)

Chronological backtest of an Elo baseline vs a pinned OpenSkill Plackett-Luce candidate (mu, sigma, draws, partial-play weights for substitutions). Stays research until it beats both 50/50 and Elo log-loss on a chronological holdout of ≥100 future maps. TrueSkill-style approaches fit because they model team outcomes and explicit uncertainty (Microsoft TrueSkill2).

---

## 7. Program B — Proximity Score v2 quality contract (PR-4)

- All ten source queries return `source`, `success`, `row_count`, `duration_ms`, and an internal error code; public responses never expose exception text.
- On **any** source failure the ranking is withheld: `status="degraded"`, `ranking_available=false`, `players=[]` — never neutral 0.5 substitution.
- With all sources healthy, true zeros come from a LEFT JOIN against the cohort; latency without a sample stays *missing*; a player is scored only at ≥80 % effective metric-weight coverage; ties use midrank so an identical cohort scores 0.5, not 1.0. Semantics change ⇒ `formula_version: "prox-web-v2.0"`.
- API additively gains a top-level `formula_version` and a `quality` object; `failed_sources`, `ranking_available`, `metric_weight_coverage`, and `below_coverage_dropped` live INSIDE `quality` (not at the top level), and each player row carries `missing_metrics`. Coverage/availability in `quality` reflect the players actually returned (recomputed after any response `limit`).
- Frontend (**legacy JS canon**) shows an unavailable state on degraded/unrated and does not keep a cached result as current.
- Prometheus metrics use low-cardinality labels only (`{source, outcome}` + duration histogram; never GUID/player labels). Alert on any source error or 15 minutes of degraded state.

Reference response shape:

```json
{
  "status": "degraded",
  "formula_version": "prox-web-v2.0",
  "quality": {
    "ranking_available": false,
    "successful_sources": 9,
    "total_sources": 10,
    "failed_sources": ["proximity_reaction_metric"]
  },
  "players": []
}
```

---

## 8. Program B — Architecture, deploy, and CI (PR-6)

- **Auth consolidation:** one canonical `SessionPrincipal` with a required `discord_id`, optional `website_user_id` (never a Discord fallback), and a permission tier. Converge `website/backend/dependencies.py` and `website/backend/middleware/auth_helpers.py`. `require_operator` stays env-based for diagnostics; `require_tier("admin")` is DB-based for product write routes. Every non-Greatshot mutation endpoint gets a contract test across anonymous/user/mod/admin/root + CSRF.
- **Reproducible deploy:** cache-busting and the React build are produced in a staging artifact and swapped atomically; the production git checkout must be clean after a deploy. Building the four live React routes is fatal on failure, not a warning. Env backup copies move out of the repo checkout into a root-only backup location with a documented retention rule.
- **Supply chain / CI:** reproducible bot/web locks, `pip check`, dependency-review PR gate, time-boxed audit-ignore exceptions with owner + expiry date, ShellCheck gate, Python 3.11/3.13 matrix, Node 22.13.1, and a Ruff ratchet without a mass unrelated refactor.
- **Model/formula cards** for predictions, ET Performance, Match Skill, and Prox v2: purpose, non-goals, data, epoch, feature definitions, missingness, sample size, slice results, limitations, owner, rollback.

---

## 9. Reference implementation contracts

```python
def routed_path(request: Request) -> str:
    return str(request.scope.get("path") or "")
```

```python
async with conn.transaction():
    await conn.execute(unwrap_valid_outer_transaction(sql))
    await record_migration_success(conn, migration)
# on error: transaction auto-rolls back; failure row is written in a NEW
# transaction; the exception re-raises and the process exits non-zero
```

```python
directed = percentile if weight > 0 else 1.0 - percentile
et_performance_v3 += abs(weight) * directed
```

---

## 10. Verification, rollout, and rollback

- **Migration tests** run on real CI PostgreSQL and prove: successful atomicity, rollback on SQL error, failure ledger written in a new transaction, checksum mismatch detection, process exit ≠ 0. FakeConn tests remain a unit complement only.
- **Security tests** cover malformed host inputs, the correct proxy host, raw routed path, CSRF, session cookie, middleware order.
- **Aim tests** cover round-end close on `last_seen`, duration clamp, stale sweep, candidate fingerprint, wrong preconditions, idempotent backfill.
- **Prediction tests** cover temporal leakage, bot/invalid gates, missing factors, dedup, no-publish shadow, roster orientation, draw handling, outcome resolver.
- **ET/Prox tests** use synthetic coverage epochs: true zero vs missing, ties, partial coverage, source exceptions, rank suppression.
- **Production smoke** (owner, per release): `/health`, `/api/status`, Story session 134 = 8 maps, betting cutoff, Prox quality contract, formula registry, four live React routes, no new error-log classes.
- **Rollback:** code → previous immutable tag; Lua → preserved previous artifact + full map load; aim cleanup → old-row snapshot; shadow models → feature flag off without deleting collected data.
- AUD-001–012 close **individually** only when the remediation ledger contains evidence-before, PR, tests, deploy, evidence-after, rollback, and owner sign-off. A merged PR alone is not closure.

---

## 11. Owner gate summary

| Gate | What the owner runs / decides |
|---|---|
| PR merges | Every PR in this plan, individually. |
| OPS-MIG | Ledger reconciliation + `--mark` for 052–060. |
| OPS-LUA | Lua copy to the game server + hash check + full map load. |
| OPS-DATA | DB backup + `backfill_aim_lock_clamp.py --apply`. |
| REL deploys | Production deploys (currently #495–#507 + urgent PRs). |
| Flags | `PREDICTION_SHADOW_ENABLED`, shadow→public promotions, `TRUSTED_HOSTS` production value. |
| Promotions | Prediction publish, ET Performance v3 public, Match Skill graduation. |

---

## 12. Definition of Done

- Production runs the **approved release Lua tracker** — identical to the repo artifact except the single intentional `shot_fired = true` line (§OPS-LUA), verified by a hash over that adjusted artifact or a diff gate that whitelists exactly that line — and produces no impossible aim-lock events. (Byte-identity to the repo is deliberately NOT the criterion: the repo ships `shot_fired = false`.)
- The migration ledger is complete, checksum-validated, and can no longer be skipped by a deploy.
- Malformed host inputs never reach application routing; the upstream advisory is absent from the canonical environments (or explicitly mitigated + time-boxed).
- #496/#497 and the Good Night wave are deployed and confirmed against known production cases (session 134 = 8 maps; betting closes after map one).
- No prediction or score presents itself as a calibrated probability or complete ranking without the required evidence and coverage.
- Every user-facing score reports formula version, data window, sample size/coverage, and a clear unavailable/degraded state.
- The production checkout is clean, builds are reproducible, secret backups are outside the repo, and CI prevents recurrence of the audited failure classes.
