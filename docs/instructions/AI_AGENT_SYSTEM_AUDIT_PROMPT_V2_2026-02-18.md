# AI Agent System Audit Prompt Review + V2

**Date:** 2026-02-18  
**Purpose:** Review and strengthen the mega-prompt for a full Slomix system audit run by an AI agent.

---

## 1) Review of Current Mega-Prompt

Your current prompt is strong on ambition, safety, and deliverables. The main problems are execution ambiguity and scope overload.

### Strengths

- Clear safety constraints.
- Evidence-first mindset.
- Strong reliability targets (idempotency, readiness, retries).
- Good requirement for repeatable health checks.
- Good emphasis on docs/code drift and production-like reliability.

### Gaps / Holes

1. **No source-of-truth hierarchy for docs.**
   - "Read /docs" is too broad and includes stale archives that can conflict with current contracts.

2. **No explicit stale-doc policy.**
   - Agent can accidentally treat `docs/archive/*` guidance as current.

3. **No phase gate between audit and implementation.**
   - Prompt asks for deep audit and code changes in one pass without a mandatory checkpoint.

4. **No contradiction-resolution rule.**
   - When docs conflict with code/runtime evidence, there is no explicit priority order.

5. **No findings schema.**
   - Multi-agent outputs can be hard to consolidate if not normalized.

6. **No severity rubric or fix policy.**
   - Missing explicit "what gets fixed now vs logged with mitigation."

7. **No change budget.**
   - "Small safe set" is stated, but not bounded in files/LOC/patch waves.

8. **No mandatory rollback template for non-trivial DB changes.**
   - You mention rollback notes, but not required structure.

9. **No explicit requirement for dirty-worktree safety.**
   - Agent should avoid reverting unrelated local changes.

10. **No explicit "offline/tooling realism" rule.**
    - Heavy scans can fail or add noise if toolchain/deps are unavailable.

11. **No confidence scoring requirement.**
    - Audit conclusions should state confidence and data quality limits.

12. **No canonical observability field contract.**
    - Structured logs asked for, but field names are not standardized.

---

## 2) Recommended Upgrades

1. Add a **doc tiering model** with "must-read first" set and archive exclusion by default.
2. Add a **two-gate workflow**:
   - Gate A: audit + plan only.
   - Gate B: implement approved P0/P1 subset.
3. Add a **source precedence rule**:
   - runtime evidence > code > current docs > archived docs.
4. Add a **standard finding schema** and severity rubric.
5. Add a **change budget** and explicit patch waves.
6. Add a **rollback section template** for every DB migration.
7. Add a **minimum proof pack** for each fix (test + query + log correlation).
8. Add **structured logging field contract** for reliability debugging.

---

## 3) Copy/Paste Prompt V2 (Recommended)

Use this as the agent instruction prompt.

```md
You are codex-cli 5.3 auditing the Slomix system (Discord bot + ingestion + DB + website).
Goal: run a deep, evidence-based audit and then implement the smallest safe risk-reduction set.

## Safety and Scope (Non-Negotiable)
- Only use local/dev/staging assets we control.
- No offensive testing against public/external targets.
- No destructive production-data actions.
- DB changes must be backward-compatible and include rollback SQL notes.
- Never claim “fixed” without test + logs + DB evidence.
- Work incrementally in small, reviewable patch waves.
- Do not revert unrelated local changes in a dirty worktree.

## Phase Gates (Mandatory)
- Gate A (Audit Only): produce findings + plan, no code changes.
- Gate B (Implementation): only after Gate A outputs exist, implement approved P0/P1 subset.

## Context Sync (Mandatory, Order Matters)
1) Read AGENTS.md (root + nested overrides) and summarize active instructions.
2) Read mandatory docs (Tier 1) listed below.
3) Build doc->code drift matrix with file refs.

### Tier 1 Docs (authoritative for this audit)
- docs/CLAUDE.md
- docs/SYSTEM_ARCHITECTURE.md
- docs/COMPLETE_SYSTEM_RUNDOWN.md
- docs/OMNIBOT_PROJECT.md
- docs/TWO_WEEK_EXECUTION_TRACKER_2026-02-11.md
- docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md
- docs/reports/LIVE_PIPELINE_AUDIT_2026-02-18.md
- docs/LIVE_MONITORING_GUIDE.md
- docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md
- docs/UPLOAD_SECURITY.md
- docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md
- docs/INFRA_HANDOFF_2026-02-18.md
- docs/LUA_R2_MISSING_ROOT_CAUSE_2026-02-18.md
- docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md
- docs/R2_ENDSTATS_ACHIEVEMENTS_INVESTIGATION_2026-02-18.md
- docs/TIMING_SHADOW_HANDOFF_2026-02-18.md
- proximity/docs/README.md
- proximity/docs/TRACKER_REFERENCE.md
- proximity/docs/INTEGRATION_STATUS.md
- proximity/docs/GAPS_AND_ROADMAP.md
- proximity/docs/PROXIMITY_BEHAVIOR_AUDIT_HANDOFF_2026-02-18.md

### Tier 2 Docs (optional, as needed)
- docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md
- docs/TWO_WEEK_CLOSEOUT_REPORT_2026-02-16.md
- docs/ROAD_AHEAD_EXECUTION_RUNBOOK_2026-02-12.md
- docs/reports/NIGHTLY_FINDINGS_SNAPSHOT_2026-02-18.md
- docs/reports/PR37_STABILIZATION_FINDINGS_2026-02-18.md
- docs/reports/TIMING_SHADOW_INVESTIGATION_2026-02-18.md

### Tier 3 Docs (archive)
- Ignore `docs/archive/*` unless a Tier 1/2 doc explicitly references it.

## Source Precedence Rule
When sources conflict, prefer in this order:
1) Runtime evidence (logs, DB rows, service state)
2) Current code behavior
3) Tier 1 docs
4) Tier 2 docs
5) Archive docs

## Multi-Agent Execution (A-H)
Run these in parallel and return normalized JSON per agent:
- A Docs/Contract
- B Architecture/Dataflow
- C Pipeline Correctness
- D Security (OWASP ASVS/WSTG themes)
- E Supply Chain/Secure SDLC (SSDF/SLSA concepts)
- F Performance/Reliability
- G Code Quality/Maintainability
- H Test Harness/Audit Runner

Each agent output must use:
{
  "agent": "A",
  "findings": [
    {
      "id": "A-001",
      "severity": "high|med|low",
      "title": "...",
      "evidence": ["file:line", "query/log snippet"],
      "impact": "...",
      "repro_steps": ["..."],
      "recommended_fix": "...",
      "confidence": "high|med|low"
    }
  ],
  "open_questions": [],
  "assumptions": []
}

## Severity and Fix Policy
- High: fix now in Gate B or provide explicit mitigation + owner + due date.
- Medium: fix if low-risk/small; else add tracked mitigation.
- Low: document and backlog.

## Gate A Deliverables (No Code Changes)
1) docs/AUDIT_SYSTEM_MAP_<date>.md
2) docs/AUDIT_FINDINGS_SECURITY_<date>.md
3) docs/AUDIT_FINDINGS_CODE_QUALITY_<date>.md
4) docs/AUDIT_PIPELINE_HEALTH_CHECKLIST_<date>.md
5) docs/AUDIT_REPRO_RELEASE_CHECKLIST_<date>.md
6) docs/AUDIT_DRIFT_MATRIX_<date>.md
7) docs/AUDIT_IMPLEMENTATION_PLAN_<date>.md

`AUDIT_IMPLEMENTATION_PLAN` must include:
- P0/P1/P2 items with effort and risk.
- Exact files to change.
- DB migration plan + rollback SQL.
- Test plan and measurable acceptance criteria.

## Gate B Scope (Approved P0/P1 only)
Implement smallest safe set, prioritized:
- idempotency ledger (at-most-once per round_id/post_type)
- readiness gate hardening
- structured observability
- CI quality guardrails (Ruff + one security scan tool, minimally disruptive)
- 1–3 performance improvements only if evidence-backed

## Change Budget
- Wave 1 (P0): reliability only, minimal files.
- Wave 2 (P1): security quick wins + CI guardrails.
- Wave 3 (optional): perf improvements with before/after evidence.
- Avoid large rewrites.

## Required Evidence Per Fix
For every implemented fix include:
1) tests (new/updated) passing
2) DB query evidence
3) log evidence
4) rollback note (if DB-related)

## Structured Log Field Contract
Use consistent fields where applicable:
- `component`
- `event`
- `round_id`
- `match_id`
- `session_date`
- `post_type`
- `dedupe_key`
- `readiness_state`
- `attempt`
- `result`
- `error`

## Hard Definition of Done
- newest rounds persist correctly
- dedupe <=1 publish per `(round_id, post_type)`
- readiness gate prevents premature publish
- restart does not trigger repost spam
- audit runner/checklist is repeatable by one command
- high severity issues fixed or mitigated with explicit owners
```

---

## 4) Practical Notes for Your Team

1. Keep this prompt paired with a short runbook that says which environment to run in first.
2. Re-run only Gate A when docs/pipeline change significantly.
3. Treat this as a living doc and version it (`_V3`, `_V4`) as your architecture stabilizes.

