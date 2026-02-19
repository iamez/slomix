# Slomix AI System Audit Master Prompt

**Prompt ID:** `slomix-system-audit-master`  
**Version:** `2026.02.19-v1.3.0`  
**Execution Lock ID:** `SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19`  
**Status:** `ACTIVE`  
**Created UTC:** `2026-02-18`  
**Last Updated UTC:** `2026-02-19`  
**Standards Snapshot UTC:** `2026-02-18`  
**Last Run UTC:** `2026-02-19T02:52:21Z`  
**Last Run Outcome:** `pass`  
**Last Run Branch:** `feat/availability-multichannel-notifications`  
**Last Run Commit SHA:** `1939baa0655a3fbc1c7d38e1a68845e1281766f0`  
**Run Counter:** `3`  
**Last Run Artifact Index:** `docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md`  
**Owner:** `Slomix maintainers`

---

## What This File Is

This is the canonical, reusable, long-form prompt you can point an AI agent to any time you want a full-system audit + controlled hardening pass.

It is designed to be:

- verbose and explicit,
- versioned,
- safe by default,
- evidence-driven,
- maintainable across repeated runs.

---

## Strict Launch Contract (Prevent Plan Confusion)

When launching another agent, always include all of:

1. Exact file path: `docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md`
2. Expected version string: `2026.02.19-v1.3.0`
3. Execution lock ID: `SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19`
4. Explicit profile selection:
   - `Profile A` (full audit + hardening), or
   - `Profile B` (system-log follow-up only).
5. Hard stop instruction: if version/lock/profile mismatch is detected, stop and ask operator.

Operator launch template:

```md
Execute only this plan:
- File: docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md
- Version: 2026.02.19-v1.3.0
- Lock ID: SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19
- Profile: <A or B>

Rules:
- Do not use any other audit prompt unless I explicitly approve.
- If file/version/lock/profile do not match exactly, stop and ask me.
- Start with Context Sync and report the selected profile before coding.
```

---

## Versioning Rules

- `MAJOR`: structure/contract changes to the prompt.
- `MINOR`: scope expansion (new subsystems/standards/docs packs).
- `PATCH`: wording/clarity updates, command fixes, typo fixes.

Version format:

- `YYYY.MM.DD-vMAJOR.MINOR.PATCH`

## Prompt Changelog

- `2026.02.19-v1.3.0`:
  - Consolidated validated external-research merge into mega prompt baseline.
  - Added execution lock ID and strict launch contract to prevent plan mix-ups.
  - Added baseline drift snapshot requirements before implementation.
  - Added validated carry-forward tasks (CI secrets hardening, additive security scans, container hardening).
- `2026.02.18-v1.2.1`:
  - Added validated ChatGPT research artifact references.
  - Added discovery note about external-AI baseline drift and mandatory claim matrix validation.
- `2026.02.18-v1.2.0`:
  - Added compatibility model for specialized execution-only prompts.
  - Added System Log Follow-Up execution profile mapping (`F-001`..`F-006`).
  - Added external research intake and double/triple-check verification protocol.
  - Added claim verification template and merge workflow for future ChatGPT research.
- `2026.02.18-v1.1.0`:
  - Added standards snapshot metadata and explicit run metadata fields.
  - Added durable run-log template contract.
  - Added AGENTS fallback behavior when file is not present in repo.
  - Added standards verification snapshot with dated primary links.
- `2026.02.18-v1.0.0`:
  - Initial master prompt.

---

## Pre-Run Update Checklist (Manual)

Before each audit run:

1. Update `Last Updated UTC`.
2. Set `Last Run UTC` to planned start time (or leave `NEVER`).
3. Verify docs listed in "Context Pack" still exist.
4. Add any new incident/handoff docs from latest work.
5. Verify `Standards Snapshot UTC` is still acceptable (refresh at least monthly or after major incidents).
6. If prompt logic changed, bump version.

After each audit run:

1. Update `Last Run UTC`, `Last Run Outcome`, `Last Run Branch`, `Last Run Commit SHA`, and increment `Run Counter`.
2. Append a run entry to `docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md`.
3. Add new discoveries to "Discovery Carry-Forward" section in this file.
4. If standards moved (new versions), update "Standards Watchlist" and `Standards Snapshot UTC`.

### Run Log Entry Contract (Copy Per Run)

```md
## RUN-<NNN> - <UTC timestamp>
- Branch:
- Commit SHA:
- Operator:
- Mode: `audit-only` | `audit+fix`
- Scope:
- Outcome: `pass` | `pass-with-known-gaps` | `failed`
- Key findings (1-5):
  - ...
- Artifacts:
  - docs/AUDIT_SYSTEM_MAP_<date>.md
  - docs/AUDIT_FINDINGS_SECURITY_<date>.md
  - docs/AUDIT_FINDINGS_CODE_QUALITY_<date>.md
  - docs/AUDIT_PIPELINE_HEALTH_CHECKLIST_<date>.md
  - docs/AUDIT_REPRO_RELEASE_CHECKLIST_<date>.md
  - docs/AUDIT_DRIFT_MATRIX_<date>.md
  - docs/AUDIT_IMPLEMENTATION_PLAN_<date>.md
- Change summary:
  - files touched:
  - db/migration notes:
- Follow-ups:
  - owner + due date:
```

---

## Discovery Carry-Forward (Living)

Update this section after each run with short, durable discoveries.

Use this format:

- `YYYY-MM-DD`: discovery, why it matters, where evidence lives.

## 2026-02-18 (Bootstrap)

- Need strict source-of-truth hierarchy to avoid stale docs overriding runtime reality.
- Need mandatory two-gate execution (`Audit-only` then `Approved implementation`).
- Need standardized findings schema across sub-agents.
- Need stronger supply-chain baseline references updated to current versions.

## 2026-02-19 (External Research Validation)

- External AI research can be materially stale even within the same week; run claim-matrix validation before merging.
- Frequent drift points: CI maturity, Docker/container presence, lint/security tooling presence.
- Keep additive recommendations (e.g., `pip-audit`/`bandit`) but do not replace existing controls (e.g., CodeQL) without evidence.
- Missing optional DB columns in crossref-style enrichment paths should degrade to NULL-safe projections, not hard-fail the endpoint.
- Secret baseline generation must match hook include/exclude scope, otherwise repos get noisy, unstable baseline churn.

---

## Standards Watchlist (Living, With Primary Sources)

These are the baseline standards/frameworks this prompt expects audits to align with.

Verification snapshot date: `2026-02-18`.

1. OWASP ASVS (`5.0.0`, active stable release):
   - https://owasp.org/www-project-application-security-verification-standard/
2. OWASP WSTG (stable release stream + development track):
   - https://owasp.org/www-project-web-security-testing-guide/
   - https://owasp.org/www-project-web-security-testing-guide/stable/
3. OWASP SAMM (maturity model baseline):
   - https://owaspsamm.org/model/
4. NIST SSDF SP 800-218 v1.1 (final publication):
   - https://csrc.nist.gov/pubs/sp/800/218/final
5. NIST SSDF v1.2 IPD/draft (watch for finalization):
   - https://csrc.nist.gov/News/2025/draft-ssdf-version-1-2
6. SLSA (spec stream, current published version path includes v1.2):
   - https://slsa.dev/spec/
   - https://slsa.dev/spec/v1.2/
7. CycloneDX (SBOM spec overview, includes current supported versions):
   - https://cyclonedx.org/specification/overview
8. SPDX (machine-readable SBOM/license standard):
   - https://spdx.github.io/spdx-spec/v3.0.1/
   - https://spdx.dev/learn/overview/
9. OpenSSF Scorecard:
   - https://github.com/ossf/scorecard
10. OpenSSF Best Practices Badge:
   - https://openssf.org/projects/best-practices-badge/
11. OWASP API Security Top 10 (API threat baseline):
   - https://owasp.org/API-Security/

Notes:

- When using external standards, prefer official project pages/specs and cite exact version/date where available.
- If standards conflict, document the conflict and choose one baseline explicitly.

---

## Context Pack (Must Read Before Audit)

## Tier 1 (Authoritative, Mandatory)

- `AGENTS.md` (+ nested overrides) if present in repo root; otherwise use operator-provided AGENTS instructions for this run.
- `docs/CLAUDE.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/COMPLETE_SYSTEM_RUNDOWN.md`
- `docs/OMNIBOT_PROJECT.md`
- `docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md`
- `docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md`
- `docs/reports/LIVE_PIPELINE_AUDIT_2026-02-18.md`
- `docs/LIVE_MONITORING_GUIDE.md`
- `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`
- `docs/UPLOAD_SECURITY.md`
- `docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md`
- `docs/INFRA_HANDOFF_2026-02-18.md`
- `docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md`
- `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`
- `docs/R2_ENDSTATS_ACHIEVEMENTS_INVESTIGATION_2026-02-18.md`
- `docs/TIMING_SHADOW_HANDOFF_2026-02-18.md`
- `proximity/docs/README.md`
- `proximity/docs/TRACKER_REFERENCE.md`
- `proximity/docs/INTEGRATION_STATUS.md`
- `proximity/docs/GAPS_AND_ROADMAP.md`
- `proximity/docs/PROXIMITY_BEHAVIOR_AUDIT_HANDOFF_2026-02-18.md`

## Tier 2 (Use As Needed)

- `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
- `docs/TWO_WEEK_CLOSEOUT_REPORT_2026-02-16.md`
- `docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md`
- `docs/reports/NIGHTLY_FINDINGS_SNAPSHOT_2026-02-18.md`
- `docs/reports/PR37_STABILIZATION_FINDINGS_2026-02-18.md`
- `docs/reports/TIMING_SHADOW_INVESTIGATION_2026-02-18.md`
- `docs/evidence/2026-02-16_ws1_live_session.md`
- `docs/SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md`
- `docs/SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md`
- `docs/AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_2026-02-18.md`
- `docs/research/inbox/RESEARCH_INBOX_2026-02-19_chatgpt.md`
- `docs/research/validated/RESEARCH_VALIDATED_2026-02-19_CHATGPT.md`

## Tier 3 (Archive)

- Ignore `docs/archive/*` by default.
- Only use archive docs when a Tier 1/Tier 2 doc explicitly references them.

---

## Source Precedence Rule

When docs/code/runtime disagree, use this precedence:

1. Runtime evidence (logs, DB rows, service status, live artifacts)
2. Current code behavior
3. Tier 1 docs
4. Tier 2 docs
5. Archive docs

Always record conflicts in a drift matrix with file references.

---

## Prompt Compatibility Model (Master + Specialized Prompts)

Use this master prompt as the base contract. Specialized prompts are allowed as overlays if they do not violate base safety and evidence rules.

Composition order:

1. Master prompt (`docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md`)
2. Specialized overlay prompt (if present)
3. Most recent validated research addendum

Conflict resolution:

1. Base safety/evidence rules in the master prompt always win.
2. Overlay priority/order is accepted only if it does not skip mandatory evidence.
3. If overlay says "do not re-investigate", still re-open if contradictory runtime evidence exists.

Compatibility status for current overlay:

- Overlay file: `docs/AI_AGENT_EXEC_PROMPT_SYSTEM_LOG_AUDIT_2026-02-18.md`
- Status: `Compatible with conditions`
- Conditions:
  - Keep Gate A/Gate B behavior for broad audits.
  - For targeted fix runs, overlay can operate as Gate B-only execution profile.
  - Must still emit code/test/log/DB evidence per workstream.

---

## Execution Profiles

### Profile A: Full Audit + Hardening (Default)

Use the "Copy/Paste Execution Prompt" below (A-H agent model, full Gate A then Gate B).

### Profile B: System Log Follow-Up (Targeted)

Use when these documents are present and approved as source findings:

1. `docs/SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md`
2. `docs/SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md`

Priority order (from findings/delegation):

1. `F-001` Greatshot crossref schema drift (High)
2. `F-003` restart churn / runtime stability
3. `F-002` DNS/SSH resilience
4. `F-004` endstats duplicate-key hygiene
5. `F-005` warning budget reduction
6. `F-006` game-server log hygiene follow-up

Profile B guardrails:

1. Do not skip evidence bundle requirements.
2. Do not claim resolved unless log + DB + test evidence agrees.
3. Keep patches incremental and reversible.
4. If a "proven" finding no longer reproduces, record as `stale/needs-revalidation` with evidence.

---

## External Research Intake (Double/Triple-Check Protocol)

When external AI research arrives (ChatGPT or any source), treat it as unverified input until validated.

Intake steps:

1. Save raw research to `docs/research/inbox/RESEARCH_INBOX_<date>_<source>.md`.
2. Split research into atomic claims (`C-001`, `C-002`, ...).
3. For each claim, classify type:
   - runtime/log
   - database/schema
   - code behavior
   - standards/compliance
   - architecture/process
4. Validate each claim with independent evidence:
   - Medium/Low claims: minimum 2 independent sources.
   - High/Critical claims: minimum 3 independent sources.
5. Approved evidence source classes:
   - local code references
   - local logs/artifacts
   - DB query outputs
   - official standards primary sources
   - reproducible command/test outputs
6. Rejected evidence:
   - model assertion without reproducible proof
   - stale docs contradicted by runtime evidence
7. Mark each claim:
   - `verified`
   - `partially-verified`
   - `unverified`
   - `false`
8. Promote only `verified`/`partially-verified` claims into the master prompt or run plans.

Claim verification record template:

```md
| Claim ID | Claim | Severity if true | Evidence A | Evidence B | Evidence C | Status | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| C-001 | ... | high | file:line | SQL/log cmd | standards URL | verified | ... |
```

Merge workflow after research validation:

1. Create `docs/research/validated/RESEARCH_VALIDATED_<date>.md`.
2. Add durable discoveries to this master prompt ("Discovery Carry-Forward").
3. Update prompt version/changelog if behavior/contracts changed.
4. Append run notes to `docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md`.

Latest validated external research artifact:

- `docs/research/validated/RESEARCH_VALIDATED_2026-02-19_CHATGPT.md`

Validated carry-forward from that artifact:

1. Enforce baseline drift checks before using external recommendations.
2. Treat dependency/security scan additions (`pip-audit`, `bandit`) as additive to existing controls (e.g., CodeQL).
3. Keep CI secret hygiene as a concrete P1 task.
4. Keep container hardening as targeted improvements, not a mandatory rewrite.

---

## Copy/Paste Execution Prompt (Agent Input)

```md
You are codex-cli 5.3 working on Slomix (Discord bot + ingestion + DB + website + proximity telemetry).

Execution lock check (mandatory):
- Expected prompt version: `2026.02.19-v1.3.0`
- Expected lock ID: `SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19`
- If mismatch is detected, stop and ask operator before any changes.

Goal:
Run a deep, evidence-based system audit, then implement the smallest safe set of improvements that materially reduces risk and improves maintainability.

Non-negotiables:
- Only local/dev/staging controlled targets.
- No destructive production data operations.
- Backward-compatible DB changes only, with rollback notes.
- Evidence-first: no “fixed” claims without tests + logs + DB evidence.
- Incremental patch waves only.
- Do not revert unrelated local changes in a dirty worktree.

Mandatory Phase Gates:
- Gate A: Audit + plan only. No code changes.
- Gate B: Implement approved P0/P1 subset only after Gate A outputs exist.

ABSOLUTE FIRST STEP: Context Sync
1) Read AGENTS.md (+ nested overrides) if present; if missing, use operator-provided AGENTS instructions and log that fallback.
2) Read Tier 1 context pack.
3) Build doc->code->runtime drift matrix.
4) State assumptions and unknowns before execution.

Mandatory Baseline Drift Snapshot (before Gate A findings):
1) Verify current CI workflows and what they actually run (lint/tests/security/build).
2) Verify current containerization assets (Dockerfiles/compose/runtime assumptions).
3) Verify current lint/security tooling already in use (e.g., ruff, CodeQL, detect-secrets).
4) Verify dependency pinning model (fully pinned vs ranged requirements by file).
5) Emit `docs/AUDIT_BASELINE_SNAPSHOT_<date>.md` and mark stale external claims.

Source precedence:
runtime evidence > code > Tier 1 docs > Tier 2 docs > archive docs

Multi-agent parallelization (A-H, required):
- A Docs/Contract
- B Architecture/Dataflow + trust boundaries
- C Pipeline correctness/reliability
- D Security (OWASP ASVS/WSTG themes)
- E Supply chain + secure SDLC (SSDF/SLSA/SBOM)
- F Performance/reliability hotspots
- G Code quality/maintainability
- H Audit runner/test harness

Every agent returns normalized JSON:
{
  "agent": "A",
  "findings": [
    {
      "id": "A-001",
      "severity": "high|med|low",
      "title": "...",
      "evidence": ["path:line", "query/log snippet"],
      "impact": "...",
      "repro_steps": ["..."],
      "recommended_fix": "...",
      "confidence": "high|med|low"
    }
  ],
  "assumptions": [],
  "open_questions": []
}

Severity policy:
- High: fix now in Gate B or document mitigation + owner + due date.
- Medium: fix if low-risk and small; otherwise mitigate + backlog.
- Low: document and backlog.

Gate A required outputs:
1) docs/AUDIT_SYSTEM_MAP_<date>.md
2) docs/AUDIT_FINDINGS_SECURITY_<date>.md
3) docs/AUDIT_FINDINGS_CODE_QUALITY_<date>.md
4) docs/AUDIT_PIPELINE_HEALTH_CHECKLIST_<date>.md
5) docs/AUDIT_REPRO_RELEASE_CHECKLIST_<date>.md
6) docs/AUDIT_DRIFT_MATRIX_<date>.md
7) docs/AUDIT_IMPLEMENTATION_PLAN_<date>.md
8) docs/AUDIT_BASELINE_SNAPSHOT_<date>.md

Gate A implementation plan must include:
- Prioritized P0/P1/P2 backlog.
- Exact files/DB objects to touch.
- Risk analysis per change.
- Rollback plan per DB change.
- Test/verification plan with measurable acceptance criteria.

Gate B scope (approved P0/P1 only):
- Idempotency ledger (`round_id`, `post_type`, `dedupe_key`, `message_id`, `posted_at`, `payload_hash`, retry/error fields)
- Readiness gate hardening
- Structured observability
- CI quality guardrails (Ruff + at least one security scan tool, low-friction rollout)
- 1–3 evidence-backed performance improvements only
- CI secret hygiene fixes where literals are present (replace with secrets/ephemeral values)
- Container hardening quick wins (non-root runtime user, digest pinning policy, optional multi-stage where justified)

Change budget:
- Wave 1 (P0): reliability only, minimum file touch.
- Wave 2 (P1): security quick wins + quality gates.
- Wave 3 (optional): perf improvements with before/after evidence.
- No large rewrites.

Required evidence per implemented fix:
1) passing tests
2) DB query evidence
3) log evidence
4) rollback notes (if DB/schema related)

Structured logging field contract:
- component
- event
- round_id
- match_id
- session_date
- post_type
- dedupe_key
- readiness_state
- attempt
- result
- error

Hard Definition of Done:
- newest rounds persist correctly
- dedupe <=1 publish per (round_id, post_type)
- readiness gates prevent premature/incorrect posts
- bot restarts do not spam reposts
- one-command repeatable audit/checklist exists
- high severity issues fixed or explicitly mitigated with owner+due date
- run metadata is updated in both:
  - docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md
  - docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md
```

---

## Operational Use Notes

- Always run this prompt against a branch.
- Commit in small reviewable slices with clear change intent.
- Keep one “audit snapshot” doc per run date, do not overwrite old reports.
- Append run metadata to `docs/AI_AGENT_SYSTEM_AUDIT_RUN_LOG.md`.

---

## Quick Start (What You Actually Point Agent To)

If your AI tool can read file instructions directly, point it to:

- `docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md`
- `docs/AI_AGENT_PROMPT_LAUNCH_CARD_v1.3.0.md` (operator handoff helper)

Then instruct:

- "Execute the Copy/Paste Execution Prompt in this file. Produce Gate A first."

Strict operator message (recommended):

```md
Execute only this plan:
- File: docs/AI_AGENT_SYSTEM_AUDIT_MASTER_PROMPT.md
- Version: 2026.02.19-v1.3.0
- Lock ID: SLOMIX-AUDIT-MEGA-v1.3.0-2026-02-19
- Profile: A

Do not use any other prompt.
If version/lock/profile mismatch exists, stop and ask me.
Start with Context Sync + Baseline Drift Snapshot and return Gate A outputs only.
```
