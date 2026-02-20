# AI Agent Execution Prompt - System Log Audit Follow-Up (2026-02-18)

Use this prompt with a coding agent to execute the follow-up work from the completed system log audit.

---

## Copy/Paste Prompt

```md
You are the execution agent for Slomix follow-up work.

Your mission is to implement fixes from:
1) `docs/SYSTEM_LOG_AUDIT_FINDINGS_2026-02-18.md`
2) `docs/SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md`

## Operating Mode

1. Execute workstreams in priority order: P0 -> P1 -> P2.
2. Do not re-investigate already-proven findings unless new evidence contradicts them.
3. Use smallest safe patches first (incremental, reviewable).
4. Do not revert unrelated changes in the repo.
5. Keep all changes backward compatible unless explicitly justified.

## Required First Step

Read both documents fully and produce a short execution plan:

1. Selected workstream(s) for this run
2. Files to change
3. Risk notes
4. Validation commands you will run

Do not start coding until that plan is shown.

## Priority Execution Order

1. Workstream 1 (`F-001`, High): Greatshot crossref schema drift (`skill_rating` missing).
2. Workstream 2 (`F-003`, Medium): Bot restart churn + noisy test DB errors in production logs.
3. Workstream 3 (`F-002`, Medium): DNS/SSH resilience and fallback host handling.
4. Workstream 4 (`F-004`, Medium-Low): Endstats duplicate-key error hygiene.
5. Workstream 5 (`F-005`, Low): Warning budget reduction.
6. Workstream 6 (`F-006`, Low): Game-server log hygiene follow-up.

## Non-Negotiable Validation

For each completed workstream, return:

1. Code evidence:
   - files changed with short reason per file
2. Test evidence:
   - exact test command(s) run
   - pass/fail summary
3. Runtime/log evidence:
   - exact grep/query commands
   - before/after evidence lines
4. DB evidence (if relevant):
   - read-only SQL queries
   - result summary

If any check cannot be run, state exactly why and what is missing.

## Output Format (strict)

### Section 1 - Completed
List completed workstreams and outcomes.

### Section 2 - Evidence
For each workstream: code/tests/logs/db evidence.

### Section 3 - Remaining
List unfinished items with blocker/reason.

### Section 4 - Next Command Set
Provide exact commands for the next agent/operator to continue.

## Definition of Success

1. High-severity finding (`F-001`) is fixed and verified.
2. No regressions introduced in bot ingestion or website API behavior.
3. Evidence is complete enough that another agent can continue without re-triage.
```

---

## Operator Note

If you want to enforce strictly phased execution, run this in two passes:

1. Pass A: only Workstream 1 (`F-001`) + validation.
2. Pass B: remaining workstreams in order.

